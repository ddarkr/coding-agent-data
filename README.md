# Coding Agent Data

제가 실 사용 환경에서 Coding Agent를 사용하면서 수집한 데이터와 통계를 공유합니다.

<!-- REPORT:START -->

## Latest 7 KST dates

Cutoff: **2026-10-27T01:36:31.145Z**. Source coverage: 2026-10-16 through 2026-10-27T01:36:31.145Z.

[운영·사용법·장기 통계](HANDOFF.md)

![Coding agent pulse](report.svg)

Successful timed responses: **49,892** across **1,155** sessions. Excluded: errors 999, aborted 80, other/invalid timing or output 0. Generation-eligible: 49,892.

| Provider / model / tier | n | Sessions | Gen TPS | E2E TPS | TTFT median ms |
|---|---:|---:|---:|---:|---:|
| openai-codex / gpt-6-astra / default | 6595 | 55 | 26.78 | 22.71 | 2,955.69 |
| openai-codex / gpt-6-astra / priority | 1425 | 18 | 32.49 | 28.81 | 2,312.76 |
| openai-codex / gpt-6-astra / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6-luna / default | 4479 | 233 | 99.76 | 86.72 | 1,939.82 |
| openai-codex / gpt-6-luna / priority | 723 | 36 | 95.61 | 81.98 | 1,968.76 |
| openai-codex / gpt-6-luna / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6.1-sol / default | 32986 | 759 | 35.11 | 28.79 | 2,635.60 |
| openai-codex / gpt-6.1-sol / priority | 3625 | 88 | 45.53 | 38.54 | 1,777.30 |
| openai-codex / gpt-6.1-sol / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6.1-terra / default | 59 | 3 | 86.06 | 26.99 | 2,048.71 |
| openai-codex / gpt-6.1-terra / unknown | 0 | 0 | — | — | — |

## Fast comparison · matched 3-hour buckets

Priority and default are compared only within the same provider/model and buckets containing valid timed responses from both tiers. Unknown/auto/flex/scale are not default. Observational, not causal; workload and session differences remain. Fewer than 30 responses or 5 sessions per tier is a tiny sample.

![일반과 Fast 비교](fast-comparison.svg)

<details>
<summary>표본·TTFT·토큰 길이 상세</summary>

| Provider / model | Tier | Matched buckets | n | Sessions | Gen TPS | E2E TPS | TTFT ms | Input median | Context median | Output median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai-codex / gpt-6-astra | priority | 4 | 1425 | 18 | 32.49 | 28.81 | 2,312.76 | 1,727.00 | 132,005.00 | 473.00 |
| openai-codex / gpt-6-astra | default | 4 | 4399 | 45 | 27.36 | 23.05 | 3,021.72 | 1,241.00 | 119,404.00 | 352.00 |
| openai-codex / gpt-6-luna | priority | 5 | 723 | 36 | 95.61 | 81.98 | 1,968.76 | 5,958.00 | 98,320.00 | 644.00 |
| openai-codex / gpt-6-luna | default | 5 | 1598 | 81 | 98.34 | 87.30 | 1,896.97 | 7,452.00 | 93,757.50 | 638.50 |
| openai-codex / gpt-6.1-sol | priority | 5 | 3625 | 88 | 45.53 | 38.54 | 1,777.30 | 941.00 | 64,589.00 | 204.00 |
| openai-codex / gpt-6.1-sol | default | 5 | 10630 | 363 | 37.33 | 29.61 | 2,216.60 | 909.00 | 42,569.50 | 145.00 |
| openai-codex / gpt-6.1-terra | Not comparable | 0 | — | — | — | — | — | — | — | — |

</details>

<!-- REPORT:END -->

## 데이터 사용

제한 없음, 자유입니다.