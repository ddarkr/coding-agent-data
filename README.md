# Coding Agent Data

제가 실 사용 환경에서 Coding Agent를 사용하면서 수집한 데이터와 통계를 공유합니다.

<!-- REPORT:START -->

## Latest 7 KST dates

Cutoff: **2026-11-05T18:30:39.094Z**. Source coverage: 2026-10-16 through 2026-11-05T18:30:39.094Z.

[운영·사용법·장기 통계](HANDOFF.md)

TPS는 출력 토큰을 전체 요청시간으로 나눈 대기 포함 처리량입니다. 실제 생성 속도와는 다르며, 미상은 응답 tier 미기록을 뜻합니다.

![Coding agent pulse](report.svg)

Successful timed responses: **11,339** across **346** sessions. Excluded: errors 251, aborted 80, other/invalid timing or output 0.

| Provider / model / tier | n | Sessions | E2E TPS | TTFT median ms |
|---|---:|---:|---:|---:|
| doda / gpt-6.1-terra / unknown | 282 | 2 | 48.80 | 15,273.83 |
| openai-codex / gpt-6-astra / default | 1234 | 11 | 18.33 | 4,148.92 |
| openai-codex / gpt-6-astra / priority | 129 | 3 | 26.70 | 2,410.76 |
| openai-codex / gpt-6-astra / unknown | 0 | 0 | — | — |
| openai-codex / gpt-6.1-sol / default | 294 | 23 | 29.76 | 2,344.73 |
| openai-codex / gpt-6.1-sol / priority | 73 | 5 | 45.30 | 1,511.57 |
| openai-codex / gpt-6.1-sol / unknown | 0 | 0 | — | — |
| openai-codex / gpt-6.1-terra / default | 8779 | 278 | 43.00 | 1,811.42 |
| openai-codex / gpt-6.1-terra / priority | 548 | 30 | 62.60 | 1,314.88 |
| openai-codex / gpt-6.1-terra / unknown | 0 | 0 | — | — |

## Fast comparison · matched 3-hour buckets

Priority and default are compared only within the same provider/model and buckets containing valid timed responses from both tiers. Unknown/auto/flex/scale are not default. Observational, not causal; workload and session differences remain. Fewer than 30 responses or 5 sessions per tier is a tiny sample.

![일반과 Fast 비교](fast-comparison.svg)

<details>
<summary>표본·TTFT·토큰 길이 상세</summary>

| Provider / model | Tier | Matched buckets | n | Sessions | E2E TPS | TTFT ms | Input median | Context median | Output median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| doda / gpt-6.1-terra | Not comparable | 0 | — | — | — | — | — | — | — |
| openai-codex / gpt-6-astra | priority ⚠ tiny sample | 1 | 129 | 3 | 26.70 | 2,410.76 | 2,515.00 | 169,716.00 | 622.00 |
| openai-codex / gpt-6-astra | default | 1 | 95 | 7 | 17.99 | 3,569.13 | 2,270.00 | 98,539.00 | 935.00 |
| openai-codex / gpt-6.1-sol | priority | 1 | 73 | 5 | 45.30 | 1,511.57 | 8,258.00 | 79,956.00 | 476.00 |
| openai-codex / gpt-6.1-sol | default ⚠ tiny sample | 1 | 30 | 4 | 34.22 | 3,358.49 | 9,850.50 | 33,966.50 | 280.50 |
| openai-codex / gpt-6.1-terra | priority | 1 | 548 | 30 | 62.60 | 1,314.88 | 1,209.00 | 57,634.50 | 197.00 |
| openai-codex / gpt-6.1-terra | default | 1 | 983 | 40 | 38.76 | 1,549.84 | 533.00 | 57,953.00 | 230.00 |

</details>

<!-- REPORT:END -->

## 데이터 사용

제한 없음, 자유입니다.