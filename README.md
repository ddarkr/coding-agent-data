# Coding Agent Data

제가 실 사용 환경에서 Coding Agent를 사용하면서 수집한 데이터와 통계를 공유합니다.

<!-- REPORT:START -->

## Latest 7 KST dates

Cutoff: **2026-10-28T14:50:25.537Z**. Source coverage: 2026-10-16 through 2026-10-28T14:50:25.537Z.

[운영·사용법·장기 통계](HANDOFF.md)

주의: `doda`의 생성 TPS는 버퍼링 또는 계측 영향으로 실제 스트리밍 속도를 나타내지 않을 수 있습니다. Fast 설정 관측은 운영 문서를 참고하세요.

![Coding agent pulse](report.svg)

Successful timed responses: **55,179** across **1,332** sessions. Excluded: errors 1,036, aborted 104, other/invalid timing or output 0. Generation-eligible: 55,179.

| Provider / model / tier | n | Sessions | Gen TPS | E2E TPS | TTFT median ms |
|---|---:|---:|---:|---:|---:|
| doda / gpt-5.4-mini / unknown | 0 | 0 | — | — | — |
| doda / gpt-6-luna / unknown | 54 | 1 | 1,323.46 | 30.56 | 4,652.65 |
| doda / gpt-6.1-sol / unknown | 87 | 5 | 98.68 | 29.38 | 9,230.80 |
| doda / gpt-6.1-terra / unknown | 3213 | 111 | 232.58 | 52.78 | 5,940.60 |
| openai-codex / gpt-6-astra / default | 6759 | 57 | 26.80 | 22.72 | 2,936.05 |
| openai-codex / gpt-6-astra / priority | 1425 | 18 | 32.49 | 28.81 | 2,312.76 |
| openai-codex / gpt-6-astra / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6-luna / default | 4073 | 214 | 99.81 | 86.83 | 1,956.09 |
| openai-codex / gpt-6-luna / priority | 723 | 36 | 95.61 | 81.98 | 1,968.76 |
| openai-codex / gpt-6-luna / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6.1-sol / default | 30291 | 694 | 33.82 | 28.06 | 2,725.72 |
| openai-codex / gpt-6.1-sol / priority | 3625 | 88 | 45.53 | 38.54 | 1,777.30 |
| openai-codex / gpt-6.1-sol / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6.1-terra / default | 4929 | 148 | 80.08 | 48.35 | 2,462.52 |
| openai-codex / gpt-6.1-terra / unknown | 0 | 0 | — | — | — |

## Fast comparison · matched 3-hour buckets

Priority and default are compared only within the same provider/model and buckets containing valid timed responses from both tiers. Unknown/auto/flex/scale are not default. Observational, not causal; workload and session differences remain. Fewer than 30 responses or 5 sessions per tier is a tiny sample.

![일반과 Fast 비교](fast-comparison.svg)

<details>
<summary>표본·TTFT·토큰 길이 상세</summary>

| Provider / model | Tier | Matched buckets | n | Sessions | Gen TPS | E2E TPS | TTFT ms | Input median | Context median | Output median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| doda / gpt-5.4-mini | Not comparable | 0 | — | — | — | — | — | — | — | — |
| doda / gpt-6-luna | Not comparable | 0 | — | — | — | — | — | — | — | — |
| doda / gpt-6.1-sol | Not comparable | 0 | — | — | — | — | — | — | — | — |
| doda / gpt-6.1-terra | Not comparable | 0 | — | — | — | — | — | — | — | — |
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