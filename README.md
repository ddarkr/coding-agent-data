# Coding Agent Data

제가 실 사용 환경에서 Coding Agent를 사용하면서 수집한 데이터와 통계를 공유합니다.

<!-- REPORT:START -->

## Latest 7 KST dates

Cutoff: **2026-11-26T13:23:27.701Z**. Source coverage: 2026-10-16 through 2026-11-26T13:23:27.701Z.

[운영·사용법·장기 통계](HANDOFF.md)

TPS는 출력 토큰을 전체 요청시간으로 나눈 대기 포함 처리량입니다. 실제 생성 속도와는 다르며, 미상은 응답 tier 미기록을 뜻합니다.

![Coding agent pulse](report.svg)

Successful timed responses: **7,250** across **143** sessions. Excluded: errors 29, aborted 24, other/invalid timing or output 0.

| Provider / model / tier | n | Sessions | E2E TPS | TTFT median ms |
|---|---:|---:|---:|---:|
| doda / gpt-6.1-terra / unknown | 8 | 1 | 45.18 | 10,120.92 |
| openai-codex / gpt-6.1-terra / default | 2988 | 72 | 36.43 | 2,676.41 |
| openai-codex / gpt-6.1-terra / priority | 564 | 7 | 78.34 | 2,545.16 |
| openai-codex / gpt-6.1-terra / unknown | 0 | 0 | — | — |
| openai-codex / gpt-6.2-astra / default | 1762 | 20 | 29.83 | 3,981.26 |
| openai-codex / gpt-6.2-astra / unknown | 0 | 0 | — | — |
| openai-codex / gpt-6.2-sol / default | 1792 | 44 | 36.20 | 2,335.40 |
| openai-codex / gpt-6.2-sol / priority | 136 | 4 | 61.19 | 1,463.00 |
| openai-codex / gpt-6.2-sol / unknown | 0 | 0 | — | — |

## Fast comparison · matched 3-hour buckets

Priority and default are compared only within the same provider/model and buckets containing valid timed responses from both tiers. Unknown/auto/flex/scale are not default. Observational, not causal; workload and session differences remain. Fewer than 30 responses or 5 sessions per tier is a tiny sample.

![일반과 Fast 비교](fast-comparison.svg)

<details>
<summary>표본·TTFT·토큰 길이 상세</summary>

| Provider / model | Tier | Matched buckets | n | Sessions | E2E TPS | TTFT ms | Input median | Context median | Output median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| doda / gpt-6.1-terra | Not comparable | 0 | — | — | — | — | — | — | — |
| openai-codex / gpt-6.1-terra | priority | 2 | 564 | 7 | 78.34 | 2,545.16 | 1,742.00 | 499,399.00 | 510.50 |
| openai-codex / gpt-6.1-terra | default | 2 | 1563 | 58 | 37.94 | 2,027.34 | 675.00 | 94,058.00 | 269.00 |
| openai-codex / gpt-6.2-astra | Not comparable | 0 | — | — | — | — | — | — | — |
| openai-codex / gpt-6.2-sol | priority ⚠ tiny sample | 1 | 136 | 4 | 61.19 | 1,463.00 | 2,376.50 | 166,496.50 | 873.00 |
| openai-codex / gpt-6.2-sol | default ⚠ tiny sample | 1 | 64 | 2 | 41.84 | 1,614.36 | 2,179.50 | 113,096.50 | 565.50 |

</details>

<!-- REPORT:END -->

## 데이터 사용

제한 없음, 자유입니다.