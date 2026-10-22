# coding-agent-data

로컬 OMP 응답의 생성 속도와 지연 시간을 누적 관찰하는 개인용 프로젝트입니다. Python 3.11+ 표준 라이브러리만 사용하며 실행 파일은 `analyze.py` 하나입니다. 개인 작업에서 얻은 관찰 자료이지 모델 성능 순위나 Fast 요금제의 인과 효과를 입증하는 벤치마크가 아닙니다.

[최신 추세](report.svg) · [일반/Fast 비교](fast-comparison.svg) · [집계 기준과 운영 규칙](AGENTS.md)

## 로컬 사용

```sh
python3 analyze.py collect
python3 analyze.py report
python3 analyze.py validate
python3 analyze.py self-test
```

`collect`는 모든 로컬 OMP 프로필을 읽고 기본적으로 2026-10-16부터 수집 시작 시점의 UTC cutoff까지 집계합니다. 네트워크, git, Release 업로드는 수행하지 않습니다. `report`는 원본 로그를 읽지 않고 검증된 일별 아카이브에서 월별 통계와 차트를 만듭니다. CLI 전체와 수식은 AGENTS.md에 있습니다.

## 원격 저장소를 사용할 때

현재 로컬 프로젝트를 만드는 작업 자체는 저장소 생성·커밋·푸시·업로드를 허가하지 않습니다. 사용자가 별도로 허가한 경우에만 다음 순서로 운영합니다.

1. 사용자가 private GitHub 저장소를 만들고 원격 작업을 명시적으로 승인합니다. 비어 있는 원격에는 먼저 README만 있는 `main` 커밋을 준비합니다. 아카이브가 없는 상태에서 전체 workflow/index를 먼저 푸시하지 않습니다.
2. 로컬에서 수집·리포트·검증을 완료합니다. 원본 로그와 `.cache`는 추적하지 않습니다.
3. 아카이브 업로드를 별도로 승인받은 뒤 실행합니다. `OWNER/REPO`는 실제 private 저장소 이름으로 바꿉니다.

   ```sh
   python3 analyze.py publish-archives --repo OWNER/REPO --confirm
   ```

4. 해당 아카이브가 존재하는 것을 확인한 뒤, 별도 승인된 git 작업으로 코드와 `data/index.json` 및 생성물을 `main`에 올립니다. **Release 아카이브 업로드가 index 푸시보다 먼저입니다.**

`data/index.json`은 cutoff와 일별 아카이브의 SHA-256·크기·행 수를 담는 입력 manifest입니다. `main`의 이 파일, `analyze.py`, 워크플로 파일 변경이 Actions를 실행합니다. Actions는 캐시가 없을 때만 `gh`로 manifest에 지정된 정확한 Release asset을 내려받고, 캐시 적중 여부와 무관하게 SHA-256 및 스키마를 검증합니다. 월별 Release 태그는 `data-YYYY-MM`, 파일 이름은 날짜와 전체 내용 해시를 포함합니다. 수정된 날짜는 새 asset을 참조하며 이전 asset은 자동 삭제하지 않습니다. 삭제는 현재 및 과거 manifest의 참조·복구 정책을 검토한 뒤 별도 승인해야 합니다.

PR에서는 읽기 전용 권한으로 `self-test`와 `validate`만 실행하며 다운로드·생성물 커밋을 하지 않습니다. 신뢰된 `main`의 push 또는 `main`에서 시작한 수동 실행만 생성물을 기록할 수 있습니다. 수동 실행의 `rebuild` 옵션은 일별 집계를 다시 계산합니다. 스케줄 실행과 PAT는 없고 `GITHUB_TOKEN`만 사용합니다. 원격 main이 실행 시작 SHA에서 변경되면 생성물 커밋을 거부하며 pull/rebase/force push는 하지 않습니다.

## 검증과 재실행

`self-test`는 가중 집계·중앙값·KST 날짜/구간 경계·중복 제거·날짜 수정·아카이브 변조·비밀 필드 제외·불완전 로그·실패 후 복구·과거 시점 조회를 격리된 임시 파일로 검증합니다. 실제 데이터를 갱신한 뒤에는 `report`와 `validate`를 실행하고 SVG를 브라우저에서 확인합니다.

같은 index로 `report`를 다시 실행하면 과거 날짜 집계를 재사용하고 동일 출력은 다시 쓰지 않습니다. 원본 로그가 계속 기록되는 동안에도 `collect --until <기존 source_cutoff>`로 같은 기준 시각을 재현할 수 있습니다. `.cache/collector.sqlite3`를 잃으면 남아 있는 로컬 로그를 다시 읽어야 하므로, 원본을 삭제하기 전에는 Release 아카이브의 발행·복구 가능 여부를 확인해야 합니다.

## 생성 리포트

아래 영역만 `report`가 갱신합니다. 차트와 수치는 실제 로컬 수집 후 생성되며 초기 문서에는 측정값을 넣지 않습니다. 최근 기본 7일은 3시간 버킷으로, 장기 추세는 최근 12개월의 일별 집계로 표시합니다.

<!-- REPORT:START -->

## Latest 7 KST dates

Cutoff: **2026-10-22T18:40:47.724Z**. Source coverage: 2026-10-16 through 2026-10-22T18:40:47.724Z.

![Coding agent pulse](report.svg)

Successful timed responses: **45,332** across **1,073** sessions. Excluded: errors 797, aborted 45, other/invalid timing or output 0. Generation-eligible: 45,332.

| Provider / model / tier | n | Sessions | Gen TPS | E2E TPS | TTFT median ms |
|---|---:|---:|---:|---:|---:|
| openai-codex / gpt-6-astra / default | 5049 | 24 | 31.25 | 26.13 | 2,850.65 |
| openai-codex / gpt-6-astra / priority | 472 | 4 | 33.80 | 30.20 | 2,310.61 |
| openai-codex / gpt-6-astra / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6-luna / default | 3426 | 181 | 95.43 | 82.68 | 1,936.89 |
| openai-codex / gpt-6-luna / priority | 322 | 14 | 102.04 | 83.97 | 2,146.32 |
| openai-codex / gpt-6-luna / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6.1-sol / default | 34866 | 822 | 40.74 | 32.70 | 2,253.71 |
| openai-codex / gpt-6.1-sol / priority | 1197 | 34 | 52.77 | 42.27 | 1,791.46 |
| openai-codex / gpt-6.1-sol / unknown | 0 | 0 | — | — | — |
| opencode-go / omen-alpha / unknown | 0 | 0 | — | — | — |
| opencode-go / step-5-preview-free / unknown | 0 | 0 | — | — | — |

### Fast comparison · matched 3-hour buckets

Priority and default are compared only within the same provider/model and buckets containing valid timed responses from both tiers. Unknown/auto/flex/scale are not default. Observational, not causal; workload and session differences remain. Fewer than 30 responses or 5 sessions per tier is a tiny sample.

![일반과 Fast 비교](fast-comparison.svg)

<details>
<summary>표본·TTFT·토큰 길이 상세</summary>

| Provider / model | Tier | Matched buckets | n | Sessions | Gen TPS | E2E TPS | TTFT ms | Input median | Context median | Output median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai-codex / gpt-6-astra | priority ⚠ tiny sample | 2 | 472 | 4 | 33.80 | 30.20 | 2,310.61 | 2,119.00 | 135,776.00 | 564.00 |
| openai-codex / gpt-6-astra | default | 2 | 1778 | 17 | 26.63 | 22.69 | 2,997.42 | 1,280.50 | 119,243.50 | 370.00 |
| openai-codex / gpt-6-luna | priority | 1 | 309 | 13 | 102.14 | 84.15 | 2,155.17 | 4,899.00 | 113,061.00 | 667.00 |
| openai-codex / gpt-6-luna | default | 1 | 348 | 19 | 105.06 | 92.39 | 2,070.08 | 8,478.00 | 102,461.00 | 673.00 |
| openai-codex / gpt-6.1-sol | priority | 2 | 1197 | 34 | 52.77 | 42.27 | 1,791.46 | 953.00 | 55,631.00 | 164.00 |
| openai-codex / gpt-6.1-sol | default | 2 | 4215 | 143 | 35.83 | 29.55 | 2,275.15 | 993.00 | 44,238.00 | 159.00 |
| opencode-go / omen-alpha | Not comparable | 0 | — | — | — | — | — | — | — | — |
| opencode-go / step-5-preview-free | Not comparable | 0 | — | — | — | — | — | — | — | — |

</details>


### Twelve-month daily trend

Calendar-month summary of direct daily aggregates; rates below are ratios of summed eligible tokens/time, never averaged TPS or medians. Absent dates remain unobserved, not zero.

| Month | Observed dates | Successful | Gen TPS | E2E TPS | Errors / aborted / invalid |
|---|---:|---:|---:|---:|---|
| 2025-11 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2025-12 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-01 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-02 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-03 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-04 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-05 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-06 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-07 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-08 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-09 | 0 | 0 | — | — | 0 / 0 / 0 |
| 2026-10 | 8 | 51482 | 44.79 | 36.20 | 888 / 55 / 0 |

Timing is local client-observed. TTFT must be finite and 0 ≤ TTFT < duration for generation TPS; otherwise the response can remain E2E-valid. Context median is input + cache-read tokens, a workload proxy, not a controlled context measurement. Session counts are distinct within each population and are not additive.

<!-- REPORT:END -->
