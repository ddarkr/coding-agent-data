<!-- REPORT:START -->

## Latest 7 KST dates

Cutoff: **2026-10-23T13:52:56.697Z**. Source coverage: 2026-10-16 through 2026-10-23T13:52:56.697Z.

[운영·사용법·장기 통계](HANDOFF.md)

![Coding agent pulse](report.svg)

Successful timed responses: **54,429** across **1,259** sessions. Excluded: errors 833, aborted 57, other/invalid timing or output 0. Generation-eligible: 54,429.

| Provider / model / tier | n | Sessions | Gen TPS | E2E TPS | TTFT median ms |
|---|---:|---:|---:|---:|---:|
| openai-codex / gpt-6-astra / default | 6522 | 41 | 31.18 | 26.12 | 2,822.24 |
| openai-codex / gpt-6-astra / priority | 1009 | 13 | 35.93 | 32.12 | 2,134.49 |
| openai-codex / gpt-6-astra / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6-luna / default | 4240 | 222 | 96.52 | 84.17 | 1,913.17 |
| openai-codex / gpt-6-luna / priority | 497 | 24 | 100.37 | 84.67 | 2,010.56 |
| openai-codex / gpt-6-luna / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6.1-sol / default | 39549 | 914 | 39.36 | 31.96 | 2,290.33 |
| openai-codex / gpt-6.1-sol / priority | 2612 | 65 | 50.15 | 41.63 | 1,700.84 |
| openai-codex / gpt-6.1-sol / unknown | 0 | 0 | — | — | — |
| opencode-go / omen-alpha / unknown | 0 | 0 | — | — | — |
| opencode-go / step-5-preview-free / unknown | 0 | 0 | — | — | — |

## Fast comparison · matched 3-hour buckets

Priority and default are compared only within the same provider/model and buckets containing valid timed responses from both tiers. Unknown/auto/flex/scale are not default. Observational, not causal; workload and session differences remain. Fewer than 30 responses or 5 sessions per tier is a tiny sample.

![일반과 Fast 비교](fast-comparison.svg)

<details>
<summary>표본·TTFT·토큰 길이 상세</summary>

| Provider / model | Tier | Matched buckets | n | Sessions | Gen TPS | E2E TPS | TTFT ms | Input median | Context median | Output median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai-codex / gpt-6-astra | priority | 3 | 1009 | 13 | 35.93 | 32.12 | 2,134.49 | 1,894.00 | 131,648.00 | 484.00 |
| openai-codex / gpt-6-astra | default | 3 | 2680 | 27 | 28.92 | 24.34 | 2,969.00 | 1,284.00 | 115,475.50 | 348.50 |
| openai-codex / gpt-6-luna | priority | 4 | 497 | 24 | 100.37 | 84.67 | 2,010.56 | 5,233.00 | 102,969.00 | 685.00 |
| openai-codex / gpt-6-luna | default | 4 | 846 | 47 | 101.59 | 90.45 | 1,892.16 | 7,813.00 | 96,111.50 | 643.50 |
| openai-codex / gpt-6.1-sol | priority | 4 | 2612 | 65 | 50.15 | 41.63 | 1,700.84 | 913.00 | 59,092.00 | 177.00 |
| openai-codex / gpt-6.1-sol | default | 4 | 6563 | 202 | 36.48 | 30.55 | 2,235.10 | 978.00 | 50,380.00 | 176.00 |
| opencode-go / omen-alpha | Not comparable | 0 | — | — | — | — | — | — | — | — |
| opencode-go / step-5-preview-free | Not comparable | 0 | — | — | — | — | — | — | — | — |

</details>

<!-- REPORT:END -->
