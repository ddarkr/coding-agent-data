#!/usr/bin/env python3
"""Private, reproducible OMP measurements. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import fcntl
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import unittest

SCHEMA_VERSION = 1
METRIC_VERSION = 1
KST = timezone(timedelta(hours=9))
DEFAULT_SINCE = "2026-10-16"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_DECODED_BYTES = 1024 * 1024 * 1024
SAMPLE_KEYS = {"id", "session", "provider", "model", "tier", "timestamp_ms", "completed_at_ms",
               "stop", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
               "duration_ms", "ttft_ms"}
TIERS = {"default", "priority", "auto", "flex", "scale", "unknown"}
STOPS = {"stop", "toolUse", "error", "aborted", "length", "other"}
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,199}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamp requires an explicit timezone")
    return result


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def day_of(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, KST).date().isoformat()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def write_bytes(path: Path, content: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return False
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def write_json(path: Path, value) -> bool:
    return write_bytes(path, json_bytes(value))


def exact_keys(obj: dict, expected: set[str], label: str):
    if not isinstance(obj, dict) or set(obj) != expected:
        raise ValueError(f"Unexpected fields in {label}")


def is_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def validate_sample(row: dict, day: str | None = None):
    exact_keys(row, SAMPLE_KEYS, "measurement")
    for key in ("id", "session"):
        if not isinstance(row[key], str) or not SHA.fullmatch(row[key]):
            raise ValueError("Invalid non-identifying measurement hash")
    for key in ("model", "provider"):
        if not isinstance(row[key], str) or not SAFE_NAME.fullmatch(row[key]):
            raise ValueError("Invalid model/provider name")
    if row["tier"] not in TIERS or row["stop"] not in STOPS:
        raise ValueError("Invalid tier/stop enum")
    for key in ("timestamp_ms", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
        if type(row[key]) is not int or row[key] < 0:
            raise ValueError("Invalid integer measurement")
    if row["timestamp_ms"] >= 32_503_680_000_000:
        raise ValueError("Measurement timestamp out of supported range")
    completed = row["completed_at_ms"]
    if completed is not None and (type(completed) is not int or completed < row["timestamp_ms"]):
        raise ValueError("Invalid completion timestamp")
    for key in ("duration_ms", "ttft_ms"):
        if row[key] is not None and (not is_number(row[key]) or row[key] < 0):
            raise ValueError("Invalid timing measurement")
    if day is not None and day_of(row["timestamp_ms"]) != day:
        raise ValueError("Archive contains a measurement from another KST day")


def validate_index(index: dict):
    exact_keys(index, {"schema_version", "metric_version", "timezone", "since", "source_cutoff", "scan", "archives"}, "index")
    if index["schema_version"] != SCHEMA_VERSION or index["metric_version"] != METRIC_VERSION:
        raise ValueError("Unsupported index schema/metric version; explicit migration required")
    if index["timezone"] != "Asia/Seoul":
        raise ValueError("Unsupported reporting timezone")
    since = date.fromisoformat(index["since"])
    cutoff = parse_time(index["source_cutoff"])
    if datetime.combine(since, datetime.min.time(), KST) > cutoff:
        raise ValueError("Coverage begins after cutoff")
    exact_keys(index["scan"], {"files", "changed_files", "malformed_lines", "incomplete_lines", "duplicates"}, "scan counters")
    if any(type(v) is not int or v < 0 for v in index["scan"].values()):
        raise ValueError("Invalid scan counters")
    if not isinstance(index["archives"], list):
        raise ValueError("Invalid archive list")
    seen_days = set()
    for entry in index["archives"]:
        exact_keys(entry, {"day", "release_tag", "asset", "sha256", "bytes", "rows"}, "archive manifest")
        day = date.fromisoformat(entry["day"])
        if day < since or day > cutoff.astimezone(KST).date() or day in seen_days:
            raise ValueError("Invalid/duplicate archive day")
        seen_days.add(day)
        if not isinstance(entry["sha256"], str) or not SHA.fullmatch(entry["sha256"]):
            raise ValueError("Invalid archive hash")
        if entry["asset"] != f"{day}.{entry['sha256']}.jsonl.gz" or entry["release_tag"] != f"data-{day:%Y-%m}":
            raise ValueError("Unsafe/noncanonical Release asset name")
        if type(entry["bytes"]) is not int or not 0 < entry["bytes"] <= MAX_ARCHIVE_BYTES:
            raise ValueError("Archive compressed size out of bounds")
        if type(entry["rows"]) is not int or entry["rows"] < 1:
            raise ValueError("Invalid archive row count")


def read_index(project: Path) -> dict:
    value = json.loads((project / "data/index.json").read_text())
    validate_index(value)
    return value


def validate_repo(repo: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Expected owner/repository, not a URL")


def load_archive(project: Path, entry: dict, repo: str | None = None) -> list[dict]:
    # Validate names before constructing a path or passing arguments to gh.
    if entry["asset"] != f"{entry['day']}.{entry['sha256']}.jsonl.gz" or not SHA.fullmatch(entry["sha256"]):
        raise ValueError("Unsafe archive entry")
    if entry["release_tag"] != "data-" + entry["day"][:7]:
        raise ValueError("Unsafe archive release tag")
    path = project / ".cache/archives" / entry["asset"]
    if not path.exists():
        if not repo:
            raise ValueError(f"Archive {entry['day']} is not cached; supply --repo after authorized publication")
        validate_repo(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as temporary:
            downloaded = Path(temporary) / "archive.gz"
            subprocess.run(["gh", "release", "download", entry["release_tag"], "--repo", repo,
                            "--pattern", entry["asset"], "--output", str(downloaded)], check=True)
            if downloaded.stat().st_size != entry["bytes"] or downloaded.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ValueError("Downloaded archive size differs from index")
            content = downloaded.read_bytes()
            if digest(content) != entry["sha256"]:
                raise ValueError("Downloaded archive SHA256 differs from index")
            write_bytes(path, content)
    if path.stat().st_size != entry["bytes"] or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive size differs from index")
    compressed = path.read_bytes()
    if digest(compressed) != entry["sha256"]:
        raise ValueError("Archive SHA256 differs from index")
    rows = []
    seen = set()
    decoded = 0
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        while True:
            line = stream.readline(1024 * 1024 + 1)
            if not line:
                break
            decoded += len(line)
            if len(line) > 1024 * 1024 or decoded > MAX_DECODED_BYTES:
                raise ValueError("Archive decoded size limit exceeded")
            row = json.loads(line)
            validate_sample(row, entry["day"])
            if row["id"] in seen:
                raise ValueError("Duplicate response ID in archive")
            seen.add(row["id"])
            rows.append(row)
    if len(rows) != entry["rows"]:
        raise ValueError("Archive row count differs from index")
    return rows


@contextmanager
def project_lock(project: Path):
    cache = project / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another project command is running") from exc
        yield


def clean_timing(value):
    return float(value) if is_number(value) and value >= 0 else None


def clean_count(value):
    return value if type(value) is int and value >= 0 else 0


def normalize_message(entry: dict, session_hash: str) -> dict | None:
    message = entry.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return None
    stamp = message.get("timestamp")
    provider = message.get("provider")
    model = message.get("model")
    if type(stamp) is not int or stamp < 0:
        return None
    if not all(isinstance(v, str) and SAFE_NAME.fullmatch(v) for v in (provider, model)):
        return None
    response = message.get("responseId")
    identity = [provider, response] if isinstance(response, str) and response else [provider, model, entry.get("id"), stamp]
    if not response and not isinstance(entry.get("id"), str):
        return None
    completed = message.get("completedAt")
    completed = completed if type(completed) is int and completed >= stamp else None
    usage = message.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    tier = message.get("serviceTier")
    stop = message.get("stopReason")
    row = {"id": digest(json.dumps(identity, separators=(",", ":")).encode()), "session": session_hash,
           "provider": provider, "model": model, "tier": tier if tier in TIERS else "unknown",
           "timestamp_ms": stamp, "completed_at_ms": completed,
           "stop": stop if stop in STOPS else "other",
           "input_tokens": clean_count(usage.get("input")), "output_tokens": clean_count(usage.get("output")),
           "cache_read_tokens": clean_count(usage.get("cacheRead")),
           "cache_write_tokens": clean_count(usage.get("cacheWrite")),
           "duration_ms": clean_timing(message.get("duration")), "ttft_ms": clean_timing(message.get("ttft"))}
    validate_sample(row)
    return row


def source_rows(path: Path, size: int):
    """Read one bounded file snapshot. Defer a concurrently written JSON suffix."""
    rows = {}
    incomplete = 0
    # Local file path only contributes to a one-way hash if no session header exists.
    session_hash = digest(str(path.resolve()).encode())
    with path.open("rb") as source:
        remaining = size
        while remaining:
            line = source.readline(remaining)
            if not line:
                raise ValueError("A source file shrank during collection; rerun without altering logs")
            remaining -= len(line)
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                if remaining == 0 and not line.endswith(b"\n"):
                    incomplete += 1
                    break
                raise ValueError("Malformed complete JSON line in source; index not updated") from exc
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "session" and isinstance(entry.get("id"), str):
                session_hash = digest(entry["id"].encode())
            row = normalize_message(entry, session_hash)
            if row:
                old = rows.get(row["id"])
                if old and old != row:
                    raise ValueError("Conflicting response copies within a source file")
                rows[row["id"]] = row
    return list(rows.values()), incomplete


def collect(project: Path, omp_home: Path, since: str, until: datetime | None = None) -> dict:
    cutoff = until or datetime.now(timezone.utc)
    begin = datetime.combine(date.fromisoformat(since), datetime.min.time(), KST)
    if begin > cutoff:
        raise ValueError("Collection cutoff precedes coverage")
    old_index = read_index(project) if (project / "data/index.json").exists() else None
    if old_index and since > old_index["since"]:
        raise ValueError("Refusing to discard historical coverage; retain the existing --since date")
    if old_index and cutoff < parse_time(old_index["source_cutoff"]):
        raise ValueError("Collection cutoff cannot move backwards; use report --until for historical views")
    roots = [omp_home / "agent/sessions"]
    profiles = omp_home / "profiles"
    if profiles.is_dir():
        roots.extend(p / "agent/sessions" for p in sorted(profiles.iterdir()) if (p / "agent/sessions").is_dir())
    roots = [p for p in roots if p.is_dir()]
    if not roots:
        raise ValueError("No OMP session roots found")
    cache = project / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(cache / "collector.sqlite3")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,mtime_ns INTEGER,size INTEGER,incomplete INTEGER)")
    connection.execute("CREATE TABLE IF NOT EXISTS samples(path TEXT,id TEXT,day TEXT,stamp INTEGER,completed INTEGER,payload TEXT,PRIMARY KEY(path,id))")
    connection.execute("CREATE INDEX IF NOT EXISTS samples_day ON samples(day)")
    connection.execute("CREATE INDEX IF NOT EXISTS samples_id ON samples(id)")
    connection.execute("CREATE TABLE IF NOT EXISTS dirty_days(day TEXT PRIMARY KEY)")
    changed = 0
    discovered = set()
    try:
        with connection:
            for root in roots:
                for path in sorted(root.rglob("*.jsonl")):
                    if not path.is_file():
                        continue
                    resolved = str(path.resolve())
                    if resolved in discovered:
                        continue
                    discovered.add(resolved)
                    stat = path.stat()
                    old = connection.execute("SELECT mtime_ns,size FROM files WHERE path=?", (resolved,)).fetchone()
                    if old == (stat.st_mtime_ns, stat.st_size):
                        continue
                    # Unknown old files cannot affect the requested range unless previously indexed.
                    if old is None and stat.st_mtime < begin.timestamp():
                        continue
                    rows, incomplete = source_rows(path, stat.st_size)
                    old_rows = {r[0]: (r[1], r[2]) for r in connection.execute(
                        "SELECT id,day,payload FROM samples WHERE path=?", (resolved,))}
                    new_rows = {r["id"]: (day_of(r["timestamp_ms"]), json.dumps(
                        r, sort_keys=True, separators=(",", ":"), allow_nan=False), r) for r in rows}
                    changed_ids = {key for key, (day, payload, _) in new_rows.items()
                                   if old_rows.get(key) != (day, payload)}
                    changed_ids.update(old_rows.keys() - new_rows.keys())
                    affected = {old_rows[key][0] for key in changed_ids if key in old_rows}
                    affected.update(new_rows[key][0] for key in changed_ids if key in new_rows)
                    connection.executemany("INSERT OR IGNORE INTO dirty_days VALUES(?)", [(d,) for d in affected])
                    connection.executemany("DELETE FROM samples WHERE path=? AND id=?", [(resolved, key) for key in changed_ids])
                    connection.executemany("INSERT INTO samples VALUES(?,?,?,?,?,?)", [
                        (resolved, key, new_rows[key][0], new_rows[key][2]["timestamp_ms"],
                         new_rows[key][2]["completed_at_ms"], new_rows[key][1])
                        for key in changed_ids if key in new_rows])
                    connection.execute("INSERT OR REPLACE INTO files VALUES(?,?,?,?)", (resolved, stat.st_mtime_ns, stat.st_size, incomplete))
                    changed += 1
        # Store only hashes/metrics, then resolve duplicate copies before day partitioning.
        # ponytail: metadata walk is O(files); SQLite skips unchanged log contents. Revisit only if the walk becomes measurable.
        low, high = int(begin.timestamp() * 1000), int(cutoff.timestamp() * 1000)
        condition = "stamp>=? AND stamp<? AND (completed IS NULL OR completed<=?)"
        parameters = (low, high, high)
        total, count = connection.execute(f"SELECT count(*),count(DISTINCT id) FROM samples WHERE {condition}", parameters).fetchone()
        days = [r[0] for r in connection.execute(f"SELECT DISTINCT day FROM samples WHERE {condition} ORDER BY day", parameters)]
        dirty = {r[0] for r in connection.execute("SELECT day FROM dirty_days")}
        old_entries = {e["day"]: e for e in old_index["archives"]} if old_index else {}
        if old_index:
            previous_high = int(parse_time(old_index["source_cutoff"]).timestamp() * 1000)
            if high > previous_high:
                dirty.update(r[0] for r in connection.execute(
                    f"SELECT DISTINCT day FROM samples WHERE {condition} AND (stamp>=? OR completed>?)",
                    (*parameters, previous_high, previous_high)))
        if old_index is None or since != old_index["since"]:
            dirty.update(days)
        archives = []
        rebuilt_days = 0

        def flush(day, content, row_count):
            compressed = gzip.compress(bytes(content), compresslevel=6, mtime=0)
            checksum = digest(compressed)
            if len(compressed) > MAX_ARCHIVE_BYTES:
                raise ValueError("One day exceeds archive size limit; explicit schema partition migration required")
            asset = f"{day}.{checksum}.jsonl.gz"
            write_bytes(cache / "archives" / asset, compressed)
            return {"day": day, "release_tag": "data-" + day[:7], "asset": asset,
                    "sha256": checksum, "bytes": len(compressed), "rows": row_count}

        for day in days:
            previous = old_entries.get(day)
            if day not in dirty and previous and (cache / "archives" / previous["asset"]).exists():
                archives.append(previous)
                continue
            query = f"""SELECT payload FROM (
                SELECT payload,id,ROW_NUMBER() OVER(PARTITION BY id ORDER BY path) AS copy
                FROM samples WHERE day=? AND {condition}
            ) WHERE copy=1 ORDER BY id"""
            buffer = bytearray()
            day_rows = 0
            for (payload,) in connection.execute(query, (day, *parameters)):
                buffer.extend(payload.encode() + b"\n")
                day_rows += 1
            archives.append(flush(day, buffer, day_rows))
            rebuilt_days += 1
        index = {"schema_version": SCHEMA_VERSION, "metric_version": METRIC_VERSION, "timezone": "Asia/Seoul",
                 "since": since, "source_cutoff": iso_utc(cutoff),
                 "scan": {"files": len(discovered), "changed_files": changed, "malformed_lines": 0,
                          "incomplete_lines": connection.execute("SELECT coalesce(sum(incomplete),0) FROM files").fetchone()[0],
                          "duplicates": total - count}, "archives": archives}
        validate_index(index)
        write_json(project / "data/index.json", index)
        with connection:
            connection.execute("DELETE FROM dirty_days")
        return {"cutoff": index["source_cutoff"], "roots": len(roots), "files": len(discovered),
                "changed_files": changed, "days": len(archives), "rebuilt_days": rebuilt_days, "measurements": count,
                "duplicates": total - count, "incomplete_lines": index["scan"]["incomplete_lines"]}
    finally:
        connection.close()


def publish_archives(project: Path, repo: str, confirmed: bool) -> dict:
    if not confirmed:
        raise ValueError("Remote writes require explicit --confirm and current user authorization")
    validate_repo(repo)
    info = json.loads(subprocess.check_output(["gh", "repo", "view", repo, "--json", "visibility"]))
    if info.get("visibility") != "PRIVATE":
        raise ValueError("Measurement publication requires a private repository")
    index = read_index(project)
    # Validate all local bytes before any remote mutation.
    for entry in index["archives"]:
        load_archive(project, entry)
    uploaded = 0
    for tag in sorted({e["release_tag"] for e in index["archives"]}):
        result = subprocess.run(["gh", "api", f"repos/{repo}/releases/tags/{tag}"], capture_output=True, text=True)
        if result.returncode:
            # A failed lookup is not proof of absence (auth/network errors must not create releases).
            if "404" not in result.stderr:
                raise ValueError("Cannot inspect Release; no upload attempted")
            subprocess.run(["gh", "release", "create", tag, "--repo", repo, "--title", f"Sanitized measurements {tag[5:]}",
                            "--notes", "Numeric, anonymized OMP measurements; immutable SHA256-addressed daily archives.",
                            "--latest=false"], check=True)
            existing = set()
        else:
            release = json.loads(result.stdout)
            existing = {asset["name"] for asset in release.get("assets", [])}
        for entry in (e for e in index["archives"] if e["release_tag"] == tag):
            if entry["asset"] in existing:
                # Never clobber content-addressed assets. Verify existing bytes independently.
                with tempfile.TemporaryDirectory() as temporary:
                    target = Path(temporary) / "asset.gz"
                    subprocess.run(["gh", "release", "download", tag, "--repo", repo, "--pattern", entry["asset"], "--output", str(target)], check=True)
                    if target.stat().st_size != entry["bytes"] or digest(target.read_bytes()) != entry["sha256"]:
                        raise ValueError("An existing immutable Release asset does not match its hash")
                continue
            subprocess.run(["gh", "release", "upload", tag, str(project / ".cache/archives" / entry["asset"]), "--repo", repo], check=True)
            uploaded += 1
    return {"uploaded": uploaded, "referenced_archives": len(index["archives"]), "git_changed": False}


def validate_project(project: Path) -> dict:
    index = read_index(project)
    for path in sorted((project / "data/monthly").glob("*.json")):
        data = json.loads(path.read_text())
        if data.get("schema_version") != SCHEMA_VERSION or data.get("metric_version") != METRIC_VERSION:
            raise ValueError("Unsupported monthly aggregate version")
        if data.get("month") != path.stem or not isinstance(data.get("days"), dict):
            raise ValueError("Malformed monthly aggregate")
    return {"archives": len(index["archives"]), "source_cutoff": index["source_cutoff"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parent)
    commands = parser.add_subparsers(dest="command", required=True)
    collection = commands.add_parser("collect", help="Local collection only; never uploads or commits")
    collection.add_argument("--omp-home", type=Path, default=Path.home() / ".omp")
    collection.add_argument("--since", default=None)
    collection.add_argument("--until", type=parse_time)
    reporting = commands.add_parser("report", help="Rebuild reports from verified cached/Release archives")
    reporting.add_argument("--repo")
    reporting.add_argument("--rebuild", action="store_true")
    reporting.add_argument("--days", type=int, default=7)
    reporting.add_argument("--until", type=parse_time)
    publication = commands.add_parser("publish-archives", help="Authorized Release upload only; never changes Git")
    publication.add_argument("--repo", required=True)
    publication.add_argument("--confirm", action="store_true")
    commands.add_parser("validate", help="Validate tracked data without network access")
    commands.add_parser("self-test", help="Run embedded, isolated regression checks")
    args = parser.parse_args(argv)
    if args.command == "self-test":
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    project = args.project_dir.resolve()
    try:
        with project_lock(project):
            if args.command == "collect":
                previous = read_index(project) if (project / "data/index.json").exists() else None
                since = args.since or (previous["since"] if previous else DEFAULT_SINCE)
                result = collect(project, args.omp_home.expanduser(), since, args.until)
            elif args.command == "report":
                if args.days < 1 or args.days > 366:
                    raise ValueError("--days must be between 1 and 366")
                result = build_report(project, args.repo, args.rebuild, args.days, args.until)
            elif args.command == "publish-archives":
                result = publish_archives(project, args.repo, args.confirm)
            else:
                result = validate_project(project)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

# Reporting fragment: integrated into analyze.py; uses the shared archive/index APIs.
import hashlib
import html
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def summarize_samples(rows):
    """One-pass population classification; rates are ratios of exact sums."""
    rows = list(rows)
    valid = []
    errors = aborted = invalid = 0
    for row in rows:
        if row['stop'] == 'error':
            errors += 1
        elif row['stop'] == 'aborted':
            aborted += 1
        elif (row['stop'] in ('stop', 'toolUse')
              and isinstance(row['duration_ms'], (int, float))
              and math.isfinite(row['duration_ms']) and row['duration_ms'] > 0
              and row['output_tokens'] > 0):
            valid.append(row)
        else:
            invalid += 1
    generation = [r for r in valid if isinstance(r['ttft_ms'], (int, float))
                  and math.isfinite(r['ttft_ms']) and 0 <= r['ttft_ms'] < r['duration_ms']]
    ttfts = [r['ttft_ms'] for r in valid if isinstance(r['ttft_ms'], (int, float))
             and math.isfinite(r['ttft_ms']) and 0 <= r['ttft_ms'] < r['duration_ms']]
    output = sum(r['output_tokens'] for r in valid)
    duration = sum(r['duration_ms'] for r in valid)
    gen_output = sum(r['output_tokens'] for r in generation)
    gen_ms = sum(r['duration_ms'] - r['ttft_ms'] for r in generation)
    def median(field):
        return statistics.median(r[field] for r in valid) if valid else None
    return dict(n=len(valid), errors=errors, aborted=aborted, invalid=invalid,
                output_tokens=output, duration_ms=duration,
                generation_output_tokens=gen_output, generation_ms=gen_ms,
                generation_n=len(generation), generation_tps=gen_output * 1000 / gen_ms if gen_ms else None,
                e2e_tps=output * 1000 / duration if duration else None,
                ttft_median_ms=statistics.median(ttfts) if ttfts else None,
                sessions=len({r['session'] for r in valid}),
                input_median_tokens=median('input_tokens'), output_median_tokens=median('output_tokens'),
                context_median_tokens=statistics.median(r['input_tokens'] + r['cache_read_tokens'] for r in valid) if valid else None)


def _report_key(row):
    return row['provider'], row['model'], row['tier']


def _report_bucket(row):
    return datetime.fromtimestamp(row['timestamp_ms'] / 1000, KST).replace(
        hour=(datetime.fromtimestamp(row['timestamp_ms'] / 1000, KST).hour // 3) * 3,
        minute=0, second=0, microsecond=0)


def _report_groups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[_report_key(row)].append(row)
    return [dict(provider=k[0], model=k[1], tier=k[2], **summarize_samples(v))
            for k, v in sorted(groups.items())]


def _report_day(rows, digest):
    buckets = defaultdict(list)
    for row in rows:
        buckets[_report_bucket(row)].append(row)
    return dict(archive_sha256=digest, daily=_report_groups(rows),
                buckets=[dict(start=t.isoformat(), groups=_report_groups(v))
                         for t, v in sorted(buckets.items())])


def _report_curve(points):
    """Monotone Hermite interpolation, with zero slopes at extrema."""
    if not points:
        return ''
    path = f'M{points[0][0]:.2f},{points[0][1]:.2f}'
    if len(points) == 1:
        return path
    secants = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(points, points[1:])]
    slopes = [secants[0]]
    for left, right in zip(secants, secants[1:]):
        slopes.append(0 if left * right <= 0 else 2 * left * right / (left + right))
    slopes.append(secants[-1])
    for i, (a, b) in enumerate(zip(points, points[1:])):
        dx = (b[0] - a[0]) / 3
        path += f' C{a[0]+dx:.2f},{a[1]+slopes[i]*dx:.2f} {b[0]-dx:.2f},{b[1]-slopes[i+1]*dx:.2f} {b[0]:.2f},{b[1]:.2f}'
    return path


def _layout_svg_labels(endpoints, top_bound, bottom_bound, min_dist=22):
    """Collision-free 1D label placement with bounded relaxation."""
    if not endpoints:
        return []
    sorted_endpoints = sorted(endpoints, key=lambda e: e[0])
    n = len(sorted_endpoints)
    if n == 1:
        yy, xx, value, model, color = sorted_endpoints[0]
        return [(max(top_bound, min(bottom_bound, yy)), yy, xx, value, model, color)]
    pos = [e[0] for e in sorted_endpoints]
    for i in range(1, n):
        if pos[i] < pos[i - 1] + min_dist:
            pos[i] = pos[i - 1] + min_dist
    if pos[-1] > bottom_bound:
        diff = pos[-1] - bottom_bound
        for i in range(n):
            pos[i] -= diff
    for i in range(n - 2, -1, -1):
        if pos[i] > pos[i + 1] - min_dist:
            pos[i] = pos[i + 1] - min_dist
    if pos[0] < top_bound:
        diff = top_bound - pos[0]
        for i in range(n):
            pos[i] += diff
    for _ in range(8):
        for i in range(n):
            target = sorted_endpoints[i][0]
            low = pos[i - 1] + min_dist if i > 0 else top_bound
            high = pos[i + 1] - min_dist if i < n - 1 else bottom_bound
            if low <= high:
                pos[i] = max(low, min(high, pos[i] + (target - pos[i]) * 0.35))
    return [(pos[i], e[0], e[1], e[2], e[3], e[4]) for i, e in enumerate(sorted_endpoints)]


def _svg_time_ticks(first, last, starts, left, right, x_func):
    """Calculate tick marks, prioritizing actual calendar midnights in KST."""
    first_kst = first.astimezone(KST)
    last_kst = last.astimezone(KST)
    span = last_kst - first_kst
    ticks = []
    if span > timedelta(days=1):
        cur = first_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        midnights = []
        while cur <= last_kst:
            if cur >= first_kst:
                midnights.append(cur)
            cur += timedelta(days=1)
        if len(midnights) >= 2:
            step = max(1, math.ceil(len(midnights) / 10))
            for m in midnights[::step]:
                xm = x_func(m)
                if left <= xm <= right:
                    ticks.append((xm, m.strftime("%m/%d")))
        elif midnights:
            for m in midnights:
                xm = x_func(m)
                if left <= xm <= right:
                    ticks.append((xm, m.strftime("%m/%d")))
    if not ticks:
        step = max(1, math.ceil(len(starts) / 6))
        for i in range(0, len(starts), step):
            st = starts[i].astimezone(KST)
            xm = x_func(st)
            fmt = "%m/%d" if st.hour == 0 else "%H:%M"
            ticks.append((xm, st.strftime(fmt)))
    return ticks


def _nice_svg_scale(value, divisions=4, integral=False):
    value = max(value, 1)
    magnitude = 10 ** math.floor(math.log10(value / divisions))
    step = next(n * magnitude for n in (1, 2, 4, 5, 10) if n * magnitude >= value / divisions)
    if integral:
        step = max(1, step)
    return math.ceil(value / step) * step, step


def _svg_theme():
    return (
        '<style>'
        ':root{--bg:#ffffff;--text:#172033;--muted:#667085;--grid:#e4e8ed;--axis:#98a2b3;--font:ui-sans-serif,system-ui,-apple-system,sans-serif;--series0:#087c92;--series1:#8b6227;--series2:#087f5b;--series3:#6d3be8;--series4:#b42363;--series5:#a85d08;--series6:#2458c4;--series7:#326f61}'
        '@media(prefers-color-scheme:dark){:root{--bg:#0b1016;--text:#e8edf2;--muted:#96a2af;--grid:#2b333d;--axis:#596574;--series0:#24d5f5;--series1:#d8c090;--series2:#35d996;--series3:#af92ff;--series4:#f28ab9;--series5:#edb76c;--series6:#88aaff;--series7:#84d1c0}}'
        'text{font-family:var(--font);fill:var(--text);font-variant-numeric:tabular-nums}'
        '.muted{fill:var(--muted)}'
        '.grid{stroke:var(--grid);stroke-width:0.8}'
        '.line{fill:none;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}'
        '</style>'
    )


def render_fast_svg(comparisons, cutoff, days=7):
    """Paired bars from the exact same matched populations as the detailed table."""
    esc = lambda value: html.escape(str(value), quote=True)
    populations = defaultdict(dict)
    for row in comparisons:
        if row['tier'] in ('default', 'priority') and row['n'] > 0:
            populations[(row['provider'], row['model'])][row['tier']] = row
    pairs = [(key, values) for key, values in sorted(populations.items())
             if set(values) == {'default', 'priority'}]
    cutoff = cutoff.astimezone(KST)
    first = cutoff.date() - timedelta(days=days - 1)
    height = 190 + len(pairs) * 126 + 72 if pairs else 270
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" style="max-width:100%;height:auto" role="img" aria-labelledby="fast-title fast-desc">',
        '<title id="fast-title">일반과 Fast의 모델별 처리 속도 비교</title>',
        '<desc id="fast-desc">같은 provider와 모델의 겹치는 3시간 구간만 비교합니다. 막대는 가중 TPS이며 관찰 차이는 인과 효과가 아닙니다.</desc>',
        _svg_theme(),
        f'<rect width="1000" height="{height}" fill="var(--bg)"/>',
        '<text x="68" y="36" font-size="26" font-weight="650">일반 vs Fast</text>',
        f'<text x="68" y="62" font-size="13" class="muted">{first:%m.%d} — {cutoff:%m.%d} · {cutoff:%Y-%m-%d %H:%M} KST 기준</text>',
        '<rect x="68" y="90" width="18" height="9" rx="3" fill="var(--muted)" fill-opacity=".6"/>',
        '<text x="94" y="100" font-size="13">일반 · default</text>',
        '<rect x="244" y="90" width="18" height="9" rx="3" fill="var(--series0)"/>',
        '<text x="270" y="100" font-size="13">Fast · priority</text>',
    ]
    if not pairs:
        svg += [
            '<text x="68" y="155" font-size="18" font-weight="600">비교 가능한 표본이 없습니다</text>',
            '<text x="68" y="182" font-size="13" class="muted">같은 모델·시간 구간에 일반과 Fast 응답이 모두 필요합니다.</text>',
            '<text x="68" y="238" font-size="12" class="muted">누락된 tier와 비교 불가 표본을 0 TPS로 표시하지 않습니다.</text>',
            '</svg>',
        ]
        return '\n'.join(svg) + '\n'
    maximum, tick_step = _nice_svg_scale(max(
        row[field] for _, values in pairs for row in values.values()
        for field in ('generation_tps', 'e2e_tps') if row[field] is not None))
    columns = [('generation_tps', '생성 TPS', 350, 595, 635),
               ('e2e_tps', '대기 포함 TPS', 700, 915, 960)]
    plot_bottom = 190 + len(pairs) * 126 - 18
    for field, title, left, right, value_x in columns:
        svg.append(f'<text x="{left}" y="139" font-size="16" font-weight="600">{title}</text>')
        svg.append(f'<text x="{right}" y="139" text-anchor="end" font-size="11" class="muted">tokens/s</text>')
        for tick in range(round(maximum / tick_step) + 1):
            value = tick * tick_step
            xx = left + value / maximum * (right - left)
            svg.append(f'<path class="grid" d="M{xx:.2f},176 V{plot_bottom}"/>')
            svg.append(f'<text x="{xx:.2f}" y="163" text-anchor="middle" font-size="12" class="muted">{value:g}</text>')
    for index, ((provider, model), values) in enumerate(pairs):
        yy = 190 + index * 126
        name = model if len(model) <= 26 else model[:24] + '…'
        svg.append(f'<text x="68" y="{yy+12}" font-size="16" font-weight="650">{esc(name)}<title>{esc(provider+" / "+model)}</title></text>')
        svg.append(f'<text x="68" y="{yy+30}" font-size="11" class="muted">{esc(provider)}</text>')
        low_sample = any(row['n'] < 30 or row['sessions'] < 5 for row in values.values())
        for tier, offset in (('default', 0), ('priority', 24)):
            row = values[tier]
            label = '일반' if tier == 'default' else 'Fast'
            color = 'var(--muted)' if tier == 'default' else 'var(--series0)'
            opacity = '.6' if tier == 'default' else '1'
            svg.append(f'<text x="68" y="{yy+52+offset}" font-size="12" class="muted">{label} {row["n"]:,}건 · {row["sessions"]:,}세션</text>')
            for field, _, left, right, value_x in columns:
                value = row[field]
                if value is None:
                    svg.append(f'<text x="{value_x}" y="{yy+52+offset}" text-anchor="end" font-size="14" class="muted">—</text>')
                    continue
                width = value / maximum * (right - left)
                svg.append(f'<rect x="{left}" y="{yy+40+offset}" width="{width:.3f}" height="12" rx="4" fill="{color}" fill-opacity="{opacity}" data-provider="{esc(provider)}" data-model="{esc(model)}" data-tier="{tier}" data-metric="{field}" data-value="{value}"><title>{esc(model)} · {label}: {value:.2f} TPS</title></rect>')
                svg.append(f'<text x="{value_x}" y="{yy+52+offset}" text-anchor="end" font-size="14" font-weight="600">{value:.1f}</text>')
        for field, _, left, _, _ in columns:
            standard, fast = values['default'][field], values['priority'][field]
            if standard is not None and fast is not None and standard > 0:
                change = (fast / standard - 1) * 100
                svg.append(f'<text x="{left}" y="{yy+12}" font-size="12" class="muted">관측 차이 {change:+.1f}%</text>')
        warning = '표본 주의 · ' if low_sample else ''
        matched = values['priority']['matched_buckets']
        svg.append(f'<text x="68" y="{yy+104}" font-size="12" style="fill:{"var(--series5)" if low_sample else "var(--muted)"}">{warning}겹친 3시간 구간 {matched:,}개</text>')
    svg += [
        f'<text x="68" y="{height-42}" font-size="12" class="muted">같은 모델·겹치는 시간 구간만 비교 · 입력 길이·작업·세션 차이는 통제하지 않은 관찰 자료입니다.</text>',
        f'<text x="68" y="{height-20}" font-size="12" class="muted">표본 주의: 어느 한쪽이 30건 미만 또는 5세션 미만 · 세션 수는 같은 모집단 안에서 중복 제거합니다.</text>',
        '</svg>',
    ]
    return '\n'.join(svg) + '\n'


def render_svg(bucket_rows, cutoff):
    """Render a polished, restrained two-panel SVG chart with midnight date ticks."""
    esc = lambda value: html.escape(str(value), quote=True)
    cutoff = cutoff.astimezone(KST)
    ordered = sorted(bucket_rows, key=lambda b: parse_time(b['start']))
    if not ordered:
        ordered = [dict(start=cutoff.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), groups=[])]
    # Combine tier populations using sufficient statistics, not rates or medians.
    combined = []
    for bucket in ordered:
        populations = defaultdict(list)
        for group in bucket['groups']:
            populations[(group['provider'], group['model'])].append(group)
        groups = []
        for (provider, model), values in sorted(populations.items()):
            gen_ms = sum(g['generation_ms'] for g in values)
            gen_tokens = sum(g['generation_output_tokens'] for g in values)
            groups.append(dict(provider=provider, model=model, n=sum(g['n'] for g in values),
                               generation_tps=gen_tokens * 1000 / gen_ms if gen_ms else None))
        combined.append(dict(start=bucket['start'], groups=groups))
    ordered = combined
    models = sorted({(g['provider'], g['model']) for b in ordered for g in b['groups']
                     if g['generation_tps'] is not None})
    def model_color(model):
        for index, fragment in enumerate(('sol', 'luna', 'astra', 'step')):
            if fragment in model[1].lower():
                return f'var(--series{index})'
        checksum = hashlib.sha256((' / '.join(model)).encode()).digest()
        return f'var(--series{4 + checksum[0] % 4})'

    left, right = 68, 770
    top = 110
    plot_height = max(240, len(models) * 26)
    bottom = top + plot_height
    count_top = bottom + 80
    count_height = 125
    count_bottom = count_top + count_height
    height = count_bottom + 66

    starts = [parse_time(b['start']) for b in ordered]
    first = starts[0]
    # Full-width final bucket, even when its observed fraction is tiny.
    last = max(starts[-1] + timedelta(hours=3), first + timedelta(hours=3))
    x = lambda t: left + (t - first).total_seconds() / (last - first).total_seconds() * (right - left)
    maximum, speed_step = _nice_svg_scale(max(
        [g['generation_tps'] for b in ordered for g in b['groups'] if g['generation_tps'] is not None] or [1]))
    y = lambda value: bottom - value / maximum * plot_height
    counts = [sum(g['n'] for g in b['groups']) for b in ordered]
    count_max, count_step = _nice_svg_scale(max(counts or [0]), divisions=3, integral=True)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" style="max-width:100%;height:auto" role="img" aria-labelledby="title desc">',
        '<title id="title">Coding agent generation speed and response activity</title>',
        '<desc id="desc">Three-hour KST buckets. Gaps mean no valid measurement, not zero speed. Curves are observational.</desc>',
        '<defs>',
        '  <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">',
        '    <stop stop-color="var(--series0)" stop-opacity=".25"/>',
        '    <stop offset="1" stop-color="var(--series0)" stop-opacity="0"/>',
        '  </linearGradient>',
        '</defs>',
        _svg_theme(),
        f'<rect width="1000" height="{height}" fill="var(--bg)"/>',
        '<text x="68" y="36" font-size="26" font-weight="650">모델별 처리 속도</text>',
        f'<text x="68" y="62" font-size="13" class="muted">{esc(first.strftime("%m.%d"))} — {esc(cutoff.strftime("%m.%d"))} · 3시간 집계 · {esc(cutoff.strftime("%Y-%m-%d %H:%M"))} KST 기준</text>',
        '<text x="68" y="94" font-size="15" font-weight="600">생성 TPS <tspan font-size="12" font-weight="400" class="muted">· 첫 토큰 대기 제외</tspan></text>',
    ]

    # Upper panel: grid & labels
    for i in range(round(maximum / speed_step) + 1):
        value = speed_step * i
        yy = y(value)
        svg.append(f'<path class="grid" d="M{left},{yy:.2f} H{right}"/>')
        svg.append(f'<text x="{left - 12}" y="{yy + 4:.2f}" text-anchor="end" font-size="13" class="muted">{value:g}</text>')

    # Upper panel: model runs & endpoints
    endpoints = []
    for model in models:
        color = model_color(model)
        runs, current = [], []
        for bucket, stamp in zip(ordered, starts):
            group = next((g for g in bucket['groups'] if (g['provider'], g['model']) == model), None)
            value = group['generation_tps'] if group else None
            if value is None:
                if current:
                    runs.append(current)
                    current = []
            else:
                if current and x(stamp + timedelta(hours=1.5)) - current[-1][0] > (right - left) * 10800 / (last - first).total_seconds() * 1.01:
                    runs.append(current)
                    current = []
                current.append((x(stamp + timedelta(hours=1.5)), y(value), value))
        if current:
            runs.append(current)
        for run in runs:
            svg.append(f'<path class="line" stroke="{color}" d="{_report_curve([(a, b) for a, b, _ in run])}"/>')
            for xx, yy, value in run:
                svg.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="2.5" fill="{color}"><title>{esc(" / ".join(model))}: {value:.2f} TPS</title></circle>')
        if runs:
            xx, yy, value = runs[-1][-1]
            svg.append(f'<circle cx="{xx:.2f}" cy="{yy:.2f}" r="4" fill="{color}"/>')
            endpoints.append((yy, xx, value, model, color))

    # Collision-free endpoint labels
    guide_x = right + 10
    text_x = right + 18
    placed = _layout_svg_labels(endpoints, top + 6, bottom - 6, min_dist=22)
    for label_y, yy, xx, value, model, color in placed:
        if xx >= right - 60:
            if abs(label_y - yy) < 1.0:
                svg.append(f'<path d="M{xx:.2f},{yy:.2f} H{guide_x}" fill="none" stroke="{color}" stroke-opacity=".5" stroke-width="1.2"/>')
            else:
                mx = (xx + guide_x) / 2
                svg.append(f'<path d="M{xx:.2f},{yy:.2f} C{mx:.2f},{yy:.2f} {mx:.2f},{label_y:.2f} {guide_x},{label_y:.2f}" fill="none" stroke="{color}" stroke-opacity=".5" stroke-width="1.2"/>')
        else:
            mx = (xx + guide_x) / 2
            svg.append(f'<path d="M{xx:.2f},{yy:.2f} C{mx:.2f},{yy:.2f} {mx:.2f},{label_y:.2f} {guide_x},{label_y:.2f}" fill="none" stroke="{color}" stroke-opacity=".35" stroke-width="1.2" stroke-dasharray="3,3"/>')
        name = model[1] if len(model[1]) <= 18 else model[1][:16] + '…'
        svg.append(f'<text x="{text_x}" y="{label_y + 5:.2f}" font-size="14" font-weight="600" style="fill:{color}">{esc(name)}<title>{esc(" / ".join(model))}</title></text>')
        svg.append(f'<text x="970" y="{label_y + 5:.2f}" text-anchor="end" font-size="15" font-weight="650" style="fill:{color}">{value:.1f}</text>')

    # Lower panel header
    svg.append(f'<text x="68" y="{bottom + 38}" font-size="16" font-weight="600">정상 응답 수 <tspan font-size="12" font-weight="400" class="muted">· 구간별 표본, 건</tspan></text>')

    # Lower panel: area curve
    count_points = [(x(t + timedelta(hours=1.5)), count_bottom - c / count_max * (count_bottom - count_top)) for t, c in zip(starts, counts)]
    if count_points:
        curve = _report_curve(count_points)
        if len(count_points) == 1:
            cx, cy = count_points[0]
            svg.append(f'<rect x="{cx - 10:.2f}" y="{cy:.2f}" width="20" height="{count_bottom - cy:.2f}" fill="url(#area)" rx="3"/>')
            svg.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="3" fill="var(--series0)"/>')
        else:
            svg.append(f'<path d="{curve} L{count_points[-1][0]:.2f},{count_bottom} L{count_points[0][0]:.2f},{count_bottom} Z" fill="url(#area)"/>')
            svg.append(f'<path d="{curve}" class="line" stroke="var(--series0)" stroke-width="2.2"/>')

    # Lower panel: grid & labels
    for i in range(round(count_max / count_step) + 1):
        value = count_step * i
        yy = count_bottom - value / count_max * (count_bottom - count_top)
        svg.append(f'<path class="grid" d="M{left},{yy:.2f} H{right}"/>')
        svg.append(f'<text x="{left - 12}" y="{yy + 4:.2f}" text-anchor="end" font-size="13" class="muted">{value:,.0f}</text>')
    if count_points and max(counts) > 0:
        peak = counts.index(max(counts))
        peak_x, peak_y = count_points[peak]
        svg.append(f'<circle cx="{peak_x:.2f}" cy="{peak_y:.2f}" r="3.5" fill="var(--series0)"/>')
        annotation_x = min(max(peak_x, left + 48), right - 48)
        svg.append(f'<text x="{annotation_x:.2f}" y="{peak_y - 12:.2f}" text-anchor="middle" font-size="12" font-weight="600">최다 {counts[peak]:,}</text>')
        last_x, last_y = count_points[-1]
        svg.append(f'<circle cx="{last_x:.2f}" cy="{last_y:.2f}" r="4" fill="var(--series0)"/>')
        svg.append(f'<text x="{text_x}" y="{last_y + 5:.2f}" font-size="14" style="fill:var(--series0)">정상 응답</text>')
        svg.append(f'<text x="970" y="{last_y + 5:.2f}" text-anchor="end" font-size="15" font-weight="650" style="fill:var(--series0)">{counts[-1]:,}</text>')

    # Time axis: midnight dates
    time_ticks = _svg_time_ticks(first, last, starts, left, right, x)
    for xm, label in time_ticks:
        svg.append(f'<path d="M{xm:.2f},{count_bottom} v4" stroke="var(--axis)" stroke-width="1"/>')
        anchor = "start" if xm - 18 < left else ("end" if xm + 18 > right else "middle")
        svg.append(f'<text x="{xm:.2f}" y="{count_bottom + 24}" text-anchor="{anchor}" font-size="13" class="muted">{esc(label)}</text>')

    # Footer note
    partial = cutoff < starts[-1] + timedelta(hours=3)
    partial_msg = f' · 마지막 {starts[-1].strftime("%H:%M")}–{cutoff.strftime("%H:%M")} 부분 집계' if partial else ''
    svg.append(f'<text x="68" y="{count_bottom + 50}" font-size="12" class="muted">빈 구간은 응답 없음 · 곡선은 표시용 보간{esc(partial_msg)}</text>')

    svg.append('</svg>')
    return '\n'.join(svg) + '\n'


def _report_text(path, content):
    encoded = content.encode('utf-8')
    if not path.exists() or path.read_bytes() != encoded:
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_bytes(encoded)
        temporary.replace(path)


def _report_md(value):
    return html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')


def _report_number(value):
    return '—' if value is None else f'{value:,.2f}'


def build_report(project, repo=None, rebuild=False, days=7, until=None):
    project = Path(project)
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError('days must be a positive integer')
    index = read_index(project)
    canonical_cutoff = parse_time(index['source_cutoff'])
    cutoff = until if until is not None else canonical_cutoff
    if cutoff.tzinfo is None or cutoff > canonical_cutoff:
        raise ValueError('report cutoff must be aware and not exceed source_cutoff')
    if cutoff < parse_time(index['since'] + 'T00:00:00+09:00'):
        raise ValueError('report cutoff precedes coverage')
    readme = project / 'README.md'
    narrative = readme.read_text(encoding='utf-8')
    begin, end = '<!-- REPORT:START -->', '<!-- REPORT:END -->'
    if narrative.count(begin) != 1 or narrative.count(end) != 1 or narrative.index(begin) >= narrative.index(end):
        raise ValueError('README requires exactly one ordered REPORT marker pair')
    handoff = project / 'HANDOFF.md'
    handoff_narrative = handoff.read_text(encoding='utf-8')
    history_begin, history_end = '<!-- HISTORY:START -->', '<!-- HISTORY:END -->'
    if (handoff_narrative.count(history_begin) != 1 or handoff_narrative.count(history_end) != 1
        or handoff_narrative.index(history_begin) >= handoff_narrative.index(history_end)):
        raise ValueError('HANDOFF requires exactly one ordered HISTORY marker pair')
    analysis_hash = hashlib.sha256((project / 'analyze.py').read_bytes()).hexdigest()
    monthly_dir = project / 'data' / 'monthly'
    monthly_dir.mkdir(parents=True, exist_ok=True)
    existing = {}
    for path in sorted(monthly_dir.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema_version') != SCHEMA_VERSION or data.get('metric_version') != METRIC_VERSION:
                raise ValueError('monthly schema/metric mismatch: ' + path.name)
            if data.get('month') != path.stem or not isinstance(data.get('days'), dict):
                raise ValueError('invalid monthly file: ' + path.name)
            existing[path.stem] = data
        except (ValueError, TypeError) as exc:
            if not rebuild:
                raise ValueError('invalid monthly cache; use --rebuild: ' + path.name) from exc
    memo = {}
    def archive(entry):
        key = (entry['day'], entry['sha256'])
        if key not in memo:
            rows = load_archive(project, entry, repo)
            for row in rows:
                if (row['timestamp_ms'] < parse_time(index['since']+'T00:00:00+09:00').timestamp()*1000
                    or row['timestamp_ms'] >= canonical_cutoff.timestamp()*1000
                    or (row['completed_at_ms'] is not None and row['completed_at_ms'] > canonical_cutoff.timestamp()*1000)):
                    raise ValueError('archive sample outside manifest coverage')
            memo[key] = rows
        return memo[key]
    rebuilt_days = reused_days = 0
    months = {}
    entries = {entry['day']: entry for entry in index['archives']}
    for day, entry in sorted(entries.items()):
        month = day[:7]
        target = months.setdefault(month, dict(schema_version=SCHEMA_VERSION, metric_version=METRIC_VERSION,
                    analysis_sha256=analysis_hash, month=month, days={}))
        old = existing.get(month, {})
        cached = old.get('days', {}).get(day)
        if (not rebuild and old.get('analysis_sha256') == analysis_hash and isinstance(cached, dict)
            and cached.get('archive_sha256') == entry['sha256'] and isinstance(cached.get('daily'),list)
            and isinstance(cached.get('buckets'),list)):
            target['days'][day] = cached
            reused_days += 1
        else:
            target['days'][day] = _report_day(archive(entry), entry['sha256'])
            rebuilt_days += 1
    for month, data in months.items():
        write_json(monthly_dir / (month+'.json'), data)
    for path in monthly_dir.glob('*.json'):
        if path.stem not in months:
            path.unlink()
    local_cutoff = cutoff.astimezone(KST)
    window_start = local_cutoff.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)
    recent = []
    for day, entry in sorted(entries.items()):
        if window_start.date().isoformat() <= day <= local_cutoff.date().isoformat():
            recent.extend(r for r in archive(entry) if r['timestamp_ms'] < cutoff.timestamp()*1000
                          and (r['completed_at_ms'] is None or r['completed_at_ms'] <= cutoff.timestamp()*1000))
    bucket_samples = defaultdict(list)
    for row in recent:
        bucket_samples[_report_bucket(row)].append(row)
    buckets = []
    stamp = window_start
    while stamp < local_cutoff:
        buckets.append(dict(start=stamp.isoformat(), groups=_report_groups(bucket_samples.get(stamp, []))))
        stamp += timedelta(hours=3)
    svg = render_svg(buckets, cutoff)
    summary = summarize_samples(recent)
    lines = [f'## Latest {days} KST dates', '', f'Cutoff: **{_report_md(iso_utc(cutoff))}**. Source coverage: {index["since"]} through {_report_md(index["source_cutoff"])}.', '',
             '[운영·사용법·장기 통계](HANDOFF.md)', '',
             '![Coding agent pulse](report.svg)', '',
             f'Successful timed responses: **{summary["n"]:,}** across **{summary["sessions"]:,}** sessions. Excluded: errors {summary["errors"]:,}, aborted {summary["aborted"]:,}, other/invalid timing or output {summary["invalid"]:,}. Generation-eligible: {summary["generation_n"]:,}.', '',
             '| Provider / model / tier | n | Sessions | Gen TPS | E2E TPS | TTFT median ms |', '|---|---:|---:|---:|---:|---:|']
    for group in _report_groups(recent):
        lines.append('| '+_report_md(' / '.join(_report_key(group)))+' | '+ ' | '.join(str(group[k]) if k in ('n','sessions') else _report_number(group[k]) for k in ('n','sessions','generation_tps','e2e_tps','ttft_median_ms'))+' |')
    lines += ['', '## Fast comparison · matched 3-hour buckets', '',
              'Priority and default are compared only within the same provider/model and buckets containing valid timed responses from both tiers. Unknown/auto/flex/scale are not default. Observational, not causal; workload and session differences remain. Fewer than 30 responses or 5 sessions per tier is a tiny sample.', '',
              '![일반과 Fast 비교](fast-comparison.svg)', '',
              '<details>', '<summary>표본·TTFT·토큰 길이 상세</summary>', '',
              '| Provider / model | Tier | Matched buckets | n | Sessions | Gen TPS | E2E TPS | TTFT ms | Input median | Context median | Output median |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    pairs = sorted({(r['provider'],r['model']) for r in recent})
    comparisons = []
    for pair in pairs:
        candidates = [r for r in recent if (r['provider'],r['model']) == pair]
        tier_buckets = {tier: {_report_bucket(r) for r in candidates if r['tier']==tier and summarize_samples([r])['n']} for tier in ('priority','default')}
        overlap = tier_buckets['priority'] & tier_buckets['default']
        if not overlap:
            lines.append('| '+_report_md(' / '.join(pair))+' | Not comparable | 0 | — | — | — | — | — | — | — | — |')
            continue
        for tier in ('priority','default'):
            stats = summarize_samples(r for r in candidates if r['tier']==tier and _report_bucket(r) in overlap)
            warning = ' ⚠ tiny sample' if stats['n'] < 30 or stats['sessions'] < 5 else ''
            comparisons.append(dict(provider=pair[0],model=pair[1],tier=tier,matched_buckets=len(overlap),**stats))
            lines.append('| '+_report_md(' / '.join(pair))+' | '+tier+warning+' | '+str(len(overlap))+' | '+' | '.join(str(stats[k]) if k in ('n','sessions') else _report_number(stats[k]) for k in ('n','sessions','generation_tps','e2e_tps','ttft_median_ms','input_median_tokens','context_median_tokens','output_median_tokens'))+' |')
    lines += ['', '</details>', '']
    report_lines = lines
    lines = []
    # Twelve calendar months, with daily rates taken from direct per-day populations.
    month_number = local_cutoff.year * 12 + local_cutoff.month - 1
    first_number = month_number - 11
    trend_start = f'{first_number//12:04d}-{first_number%12+1:02d}-01'
    trend_days = {}
    for month in months.values():
        for day, data in month['days'].items():
            if trend_start <= day <= local_cutoff.date().isoformat():
                if until is not None and day == local_cutoff.date().isoformat():
                    entry = entries[day]
                    rows = [r for r in archive(entry) if r['timestamp_ms'] < cutoff.timestamp()*1000 and (r['completed_at_ms'] is None or r['completed_at_ms'] <= cutoff.timestamp()*1000)]
                    trend_days[day] = _report_groups(rows)
                else:
                    trend_days[day] = data['daily']
    lines += ['', '### Twelve-month daily trend', '',
              'Calendar-month summary of direct daily aggregates; rates below are ratios of summed eligible tokens/time, never averaged TPS or medians. Absent dates remain unobserved, not zero.', '',
              '| Month | Observed dates | Successful | Gen TPS | E2E TPS | Errors / aborted / invalid |', '|---|---:|---:|---:|---:|---|']
    for number in range(first_number,month_number+1):
        month = f'{number//12:04d}-{number%12+1:02d}'
        observed = [v for day,v in trend_days.items() if day.startswith(month)]
        values = [g for groups in observed for g in groups]
        totals = {k:sum(g[k] for g in values) for k in ('n','generation_output_tokens','generation_ms','output_tokens','duration_ms','errors','aborted','invalid')}
        gen = totals['generation_output_tokens']*1000/totals['generation_ms'] if totals['generation_ms'] else None
        e2e = totals['output_tokens']*1000/totals['duration_ms'] if totals['duration_ms'] else None
        lines.append(f'| {month} | {len(observed)} | {totals["n"]} | {_report_number(gen)} | {_report_number(e2e)} | {totals["errors"]} / {totals["aborted"]} / {totals["invalid"]} |')
    lines += ['', 'Timing is local client-observed. TTFT must be finite and 0 ≤ TTFT < duration for generation TPS; otherwise the response can remain E2E-valid. Context median is input + cache-read tokens, a workload proxy, not a controlled context measurement. Session counts are distinct within each population and are not additive.', '']
    replacement = begin+'\n\n'+'\n'.join(report_lines)+'\n'+end
    updated = narrative[:narrative.index(begin)] + replacement + narrative[narrative.index(end)+len(end):]
    history_replacement = history_begin+'\n\n'+'\n'.join(lines)+'\n'+history_end
    updated_handoff = (handoff_narrative[:handoff_narrative.index(history_begin)]
                       + history_replacement
                       + handoff_narrative[handoff_narrative.index(history_end)+len(history_end):])
    _report_text(project/'report.svg', svg)
    _report_text(project/'fast-comparison.svg', render_fast_svg(comparisons, cutoff, days))
    _report_text(readme, updated)
    _report_text(handoff, updated_handoff)
    return dict(rebuilt_days=rebuilt_days,reused_days=reused_days,normal_responses=summary['n'],
                cutoff=iso_utc(cutoff),comparison=comparisons,**{k:v for k,v in summary.items() if k!='n'})

class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project"
        self.home = Path(self.temporary.name) / "omp"
        self.source = self.home / "agent/sessions/work/session.jsonl"
        self.source.parent.mkdir(parents=True)
        self.cutoff = parse_time("2026-10-23T12:00:00+09:00")
        self.stamp = int(parse_time("2026-10-22T23:59:59+09:00").timestamp() * 1000)

    def entry(self, **changes):
        message = {"role": "assistant", "provider": "openai-codex", "model": "gpt-6.1-sol",
                   "timestamp": self.stamp, "completedAt": self.stamp + 500,
                   "responseId": "opaque-response", "serviceTier": "default", "stopReason": "stop",
                   "usage": {"input": 100, "output": 80, "cacheRead": 20}, "duration": 500, "ttft": 100,
                   "content": [{"type": "text", "text": "DO-NOT-EXPORT-PROMPT"}], "credentialId": "PRIVATE-ACCOUNT"}
        message.update(changes)
        return {"type": "message", "id": "entry-id", "message": message}

    def save(self, path, entries, suffix=b""):
        path.parent.mkdir(parents=True, exist_ok=True)
        body = [{"type": "session", "id": "independent-session"}, *entries]
        path.write_bytes(b"".join(json.dumps(e).encode() + b"\n" for e in body) + suffix)

    def run_collect(self, cutoff=None):
        return collect(self.project, self.home, DEFAULT_SINCE, cutoff or self.cutoff)

    def test_incremental_profiles_dedup_and_no_private_fields(self):
        self.save(self.source, [self.entry()])
        fork = self.home / "profiles/new-profile/agent/sessions/fork.jsonl"
        self.save(fork, [self.entry()])
        first = self.run_collect()
        self.assertEqual((first["roots"], first["measurements"], first["duplicates"]), (2, 1, 1))
        index = read_index(self.project)
        row = load_archive(self.project, index["archives"][0])[0]
        self.assertEqual(set(row), SAMPLE_KEYS)
        exported = json.dumps(index) + json.dumps(row)
        for forbidden in ("DO-NOT-EXPORT-PROMPT", "PRIVATE-ACCOUNT", "opaque-response", str(self.home)):
            self.assertNotIn(forbidden, exported)
        second = self.run_collect()
        self.assertEqual((second["changed_files"], second["rebuilt_days"]), (0, 0))
        self.assertEqual(read_index(self.project)["archives"], index["archives"])

    def test_revision_replaces_day_and_deleted_source_is_retained(self):
        self.save(self.source, [self.entry()])
        self.run_collect()
        old = read_index(self.project)["archives"][0]["sha256"]
        self.save(self.source, [self.entry(usage={"output": 200})])
        self.run_collect()
        index = read_index(self.project)
        self.assertNotEqual(old, index["archives"][0]["sha256"])
        self.assertEqual(index["archives"][0]["rows"], 1)
        self.assertEqual(load_archive(self.project, index["archives"][0])[0]["output_tokens"], 200)
        self.source.unlink()
        retained = self.run_collect()
        self.assertEqual(retained["measurements"], 1)

    def test_append_rebuilds_only_affected_day(self):
        tomorrow = self.stamp + 60000
        first = self.entry()
        second = self.entry(timestamp=tomorrow, completedAt=tomorrow + 500, responseId="second")
        self.save(self.source, [first, second])
        self.run_collect()
        original = read_index(self.project)["archives"][0]
        third = self.entry(timestamp=tomorrow + 60000, completedAt=tomorrow + 60500, responseId="third")
        self.save(self.source, [first, second, third])
        result = self.run_collect()
        self.assertEqual(result["rebuilt_days"], 1)
        self.assertEqual(result["measurements"], 3)
        self.assertEqual(read_index(self.project)["archives"][0], original)

    def test_failed_index_write_keeps_dirty_revision_recoverable(self):
        self.save(self.source, [self.entry()])
        self.run_collect()
        original = (self.project / "data/index.json").read_bytes()
        self.save(self.source, [self.entry(usage={"output": 999})])
        with patch.dict(collect.__globals__, write_json=lambda *_: (_ for _ in ()).throw(OSError("fixture disk failure"))):
            with self.assertRaises(OSError):
                self.run_collect()
        self.assertEqual((self.project / "data/index.json").read_bytes(), original)
        recovered = self.run_collect()
        self.assertEqual(recovered["changed_files"], 0)
        entry = read_index(self.project)["archives"][0]
        self.assertEqual(load_archive(self.project, entry)[0]["output_tokens"], 999)

    def test_cutoff_and_midnight_and_deferred_completion(self):
        before = self.entry()
        midnight = int(parse_time("2026-10-23T00:00:00+09:00").timestamp() * 1000)
        after = self.entry(timestamp=midnight, completedAt=midnight + 1000, responseId="after-midnight")
        self.save(self.source, [before, after])
        first = self.run_collect(parse_time("2026-10-23T00:00:00+09:00"))
        self.assertEqual(first["measurements"], 1)
        second = self.run_collect(parse_time("2026-10-23T00:00:01+09:00"))
        self.assertEqual(second["changed_files"], 0)
        self.assertEqual(second["measurements"], 2)
        self.assertEqual([e["day"] for e in read_index(self.project)["archives"]], ["2026-10-22", "2026-10-23"])

    def test_partial_line_deferred_and_complete_corruption_preserves_index(self):
        self.save(self.source, [self.entry()], b'{"type":')
        first = self.run_collect()
        self.assertEqual((first["measurements"], first["incomplete_lines"]), (1, 1))
        index_path = self.project / "data/index.json"
        previous = index_path.read_bytes()
        self.save(self.source, [self.entry()], b'{"type":\n')
        with self.assertRaises(ValueError):
            self.run_collect()
        self.assertEqual(index_path.read_bytes(), previous)
        self.save(self.source, [self.entry()])
        self.assertEqual(self.run_collect()["incomplete_lines"], 0)

    def test_archive_integrity_and_traversal_rejected(self):
        self.save(self.source, [self.entry()])
        self.run_collect()
        entry = read_index(self.project)["archives"][0]
        path = self.project / ".cache/archives" / entry["asset"]
        content = bytearray(path.read_bytes())
        content[-1] ^= 1
        path.write_bytes(content)
        with self.assertRaises(ValueError):
            load_archive(self.project, entry)
        unsafe = dict(entry, asset="../../outside.gz")
        with self.assertRaises(ValueError):
            load_archive(self.project, unsafe)

    def test_unknown_tier_and_nonfinite_timing_not_inferred(self):
        row = normalize_message(self.entry(serviceTier=None, duration=float("nan")), "b" * 64)
        self.assertEqual(row["tier"], "unknown")
        self.assertIsNone(row["duration_ms"])
        stats = summarize_samples([row])
        self.assertEqual((stats["n"], stats["invalid"]), (0, 1))

    def test_publish_requires_authorization_before_network(self):
        with self.assertRaises(ValueError):
            publish_archives(self.project, "owner/repo", False)

    def test_hash_mismatch_and_discarding_coverage_are_not_silent(self):
        self.save(self.source, [self.entry()])
        self.run_collect()
        with self.assertRaises(ValueError):
            collect(self.project, self.home, "2026-10-20", self.cutoff)
        with self.assertRaises(ValueError):
            self.run_collect(parse_time("2026-10-22T00:00:00+09:00"))


import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


class ReportTests(unittest.TestCase):
    def sample(self, **changes):
        row = dict(id='a'*64, session='b'*64, provider='provider', model='model', tier='default',
                   timestamp_ms=int(parse_time('2026-10-22T00:30:00+09:00').timestamp()*1000),
                   completed_at_ms=None, stop='stop', input_tokens=100, output_tokens=100,
                   cache_read_tokens=20, cache_write_tokens=0, duration_ms=2000.0, ttft_ms=1000.0)
        row.update(changes)
        return row

    def test_population_conservation_weighting_and_median(self):
        rows = [self.sample(), self.sample(duration_ms=10000,ttft_ms=2000,output_tokens=900),
                self.sample(ttft_ms=None), self.sample(stop='error'), self.sample(stop='aborted'),
                self.sample(duration_ms=0), self.sample(stop='length')]
        stats = summarize_samples(rows)
        self.assertEqual(stats['n']+stats['errors']+stats['aborted']+stats['invalid'],len(rows))
        self.assertEqual(stats['output_tokens'],1100)
        self.assertEqual(stats['duration_ms'],14000)
        self.assertEqual(stats['generation_output_tokens'],1000)
        self.assertEqual(stats['generation_ms'],9000)
        self.assertAlmostEqual(stats['generation_tps'],1000/9)
        self.assertEqual(stats['ttft_median_ms'],1500)
        self.assertEqual(stats['sessions'],1)
        self.assertEqual(summarize_samples([self.sample(ttft_ms=2000)])['generation_n'],0)
        self.assertEqual(summarize_samples([self.sample(ttft_ms=float('nan'))])['n'],1)

    def test_direct_daily_median_and_sparse_escaped_svg(self):
        rows = [self.sample(ttft_ms=10),self.sample(ttft_ms=20),self.sample(ttft_ms=1000,
                timestamp_ms=int(parse_time('2026-10-22T06:30:00+09:00').timestamp()*1000))]
        day = _report_day(rows,'c'*64)
        self.assertEqual(day['daily'][0]['ttft_median_ms'],20)
        day['buckets'][0]['groups'][0]['model']='<unsafe & model>'
        svg = render_svg(day['buckets'],parse_time('2026-10-22T07:00:00+09:00'))
        ET.fromstring(svg)
        self.assertIn('&lt;unsafe &amp; model&gt;',svg)
        self.assertNotIn('<unsafe',svg)

    def test_incremental_hash_historical_projection_and_fast(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project/'analyze.py').write_text('# fixture\n',encoding='utf-8')
            (project/'README.md').write_text('before\n<!-- REPORT:START -->\nold\n<!-- REPORT:END -->\nafter\n',encoding='utf-8')
            (project/'HANDOFF.md').write_text('notes before\n<!-- HISTORY:START -->\nold\n<!-- HISTORY:END -->\nnotes after\n',encoding='utf-8')
            cutoff = parse_time('2026-10-22T12:00:00+09:00')
            entry = dict(day='2026-10-22',sha256='c'*64)
            manifest = dict(since='2026-10-16',source_cutoff=iso_utc(cutoff),archives=[entry])
            rows = [self.sample(), self.sample(tier='priority',session='d'*64),
                    self.sample(timestamp_ms=int(parse_time('2026-10-22T09:00:00+09:00').timestamp()*1000))]
            with patch.dict(build_report.__globals__, read_index=lambda p:manifest,
                            load_archive=lambda p,e,r:rows):
                first = build_report(project)
                self.assertEqual(first['rebuilt_days'],1)
                self.assertEqual(first['normal_responses'],3)
                self.assertEqual(len(first['comparison']),2)
                monthly = project/'data/monthly/2026-10.json'
                canonical = monthly.read_bytes()
                second = build_report(project)
                self.assertEqual(second['reused_days'],1)
                self.assertEqual(monthly.read_bytes(),canonical)
                historical = build_report(project,until=parse_time('2026-10-22T01:00:00+09:00'))
                self.assertEqual(historical['normal_responses'],2)
                self.assertEqual(monthly.read_bytes(),canonical)
                text = (project/'README.md').read_text()
                self.assertTrue(text.startswith('before\n'))
                self.assertTrue(text.endswith('\nafter\n'))
                handoff_text = (project/'HANDOFF.md').read_text()
                self.assertTrue(handoff_text.startswith('notes before\n'))
                self.assertTrue(handoff_text.endswith('\nnotes after\n'))
                handoff_path = project/'HANDOFF.md'
                valid_handoff = handoff_path.read_text()
                handoff_path.write_text('unmarked user notes\n')
                previous_report = (project/'README.md').read_bytes()
                with self.assertRaises(ValueError):
                    build_report(project)
                self.assertEqual((project/'README.md').read_bytes(), previous_report)
                self.assertEqual(handoff_path.read_text(), 'unmarked user notes\n')
                handoff_path.write_text(valid_handoff)
                (project/'analyze.py').write_text('# changed\n')
                self.assertEqual(build_report(project)['rebuilt_days'],1)
                entry['sha256']='e'*64
                self.assertEqual(build_report(project)['rebuilt_days'],1)
                data=json.loads(monthly.read_text())
                data['metric_version']=-1
                monthly.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    build_report(project)
                self.assertEqual(build_report(project,rebuild=True)['rebuilt_days'],1)
                with self.assertRaises(ValueError):
                    build_report(project,until=cutoff+timedelta(seconds=1))
                manifest['archives']=[]
                build_report(project)
                self.assertFalse(monthly.exists())

    def test_svg_combines_tiers_by_sums(self):
        rows = [self.sample(model='gpt-sol', duration_ms=2000,ttft_ms=1000,output_tokens=100),
                self.sample(model='gpt-sol',tier='priority',duration_ms=10000,ttft_ms=1000,output_tokens=900)]
        bucket = _report_day(rows,'c'*64)['buckets']
        svg = render_svg(bucket,parse_time('2026-10-22T03:00:00+09:00'))
        tree = ET.fromstring(svg)
        namespace = {'s':'http://www.w3.org/2000/svg'}
        titles = [node.text for node in tree.findall('.//s:circle/s:title',namespace)]
        self.assertEqual(len(titles),1)
        self.assertIn('100.00 TPS',titles[0])

    def test_fast_bars_use_shared_scale_and_actual_rates(self):
        cutoff = parse_time('2026-10-22T03:00:00+09:00')
        cohorts = []
        for tier, output in (('default', 100), ('priority', 200)):
            stats = summarize_samples([self.sample(tier=tier, output_tokens=output)])
            cohorts.append(dict(provider='provider', model='model', tier=tier, matched_buckets=1, **stats))
        tree = ET.fromstring(render_fast_svg(cohorts, cutoff))
        namespace = {'s':'http://www.w3.org/2000/svg'}
        for metric in ('generation_tps', 'e2e_tps'):
            bars = tree.findall(f'.//s:rect[@data-metric="{metric}"]', namespace)
            by_tier = {bar.attrib['data-tier']: bar for bar in bars}
            self.assertEqual(set(by_tier), {'default', 'priority'})
            self.assertAlmostEqual(float(by_tier['priority'].attrib['width']) /
                                   float(by_tier['default'].attrib['width']), 2, places=4)
            for cohort in cohorts:
                self.assertAlmostEqual(float(by_tier[cohort['tier']].attrib['data-value']), cohort[metric])

    def test_fast_missing_tier_or_ttft_is_not_a_zero_bar(self):
        cutoff = parse_time('2026-10-22T03:00:00+09:00')
        standard = dict(provider='provider', model='model', tier='default', matched_buckets=1,
                        **summarize_samples([self.sample()]))
        namespace = {'s':'http://www.w3.org/2000/svg'}
        empty = ET.fromstring(render_fast_svg([standard], cutoff))
        self.assertEqual(empty.findall('.//s:rect[@data-metric]', namespace), [])
        fast = dict(provider='provider', model='model', tier='priority', matched_buckets=1,
                    **summarize_samples([self.sample(tier='priority', ttft_ms=None)]))
        tree = ET.fromstring(render_fast_svg([standard, fast], cutoff))
        self.assertEqual(len(tree.findall('.//s:rect[@data-metric="generation_tps"]', namespace)), 1)
        self.assertEqual(len(tree.findall('.//s:rect[@data-metric="e2e_tps"]', namespace)), 2)

    def test_cutoff_is_half_open_and_completed_boundary_inclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project/'analyze.py').write_text('# fixture\n')
            (project/'README.md').write_text('<!-- REPORT:START --><!-- REPORT:END -->')
            (project/'HANDOFF.md').write_text('<!-- HISTORY:START --><!-- HISTORY:END -->')
            cutoff = parse_time('2026-10-22T03:00:00+09:00')
            later = cutoff + timedelta(hours=3)
            ms = int(cutoff.timestamp()*1000)
            rows = [self.sample(timestamp_ms=ms-1,completed_at_ms=ms),
                    self.sample(timestamp_ms=ms,completed_at_ms=ms+1),
                    self.sample(timestamp_ms=ms-2,completed_at_ms=ms+1)]
            manifest = dict(since='2026-10-16',source_cutoff=iso_utc(later),
                            archives=[dict(day='2026-10-22',sha256='c'*64)])
            captured = []
            renderer = render_svg
            def capture(buckets, asof):
                captured.extend(buckets)
                return renderer(buckets,asof)
            with patch.dict(build_report.__globals__,read_index=lambda p:manifest,
                            load_archive=lambda p,e,r:rows,render_svg=capture):
                result = build_report(project,days=1,until=cutoff)
            self.assertEqual(result['normal_responses'],1)
            self.assertEqual(len(captured),1)
            self.assertEqual(parse_time(captured[-1]['start']).hour,0)

if __name__ == "__main__":
    raise SystemExit(main())
