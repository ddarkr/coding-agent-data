<!-- REPORT:START -->

## Latest 7 KST dates

Cutoff: **2026-10-22T19:22:13.579Z**. Source coverage: 2026-10-16 through 2026-10-22T19:22:13.579Z.

[운영·사용법·장기 통계](HANDOFF.md)

![Coding agent pulse](report.svg)

Successful timed responses: **46,094** across **1,086** sessions. Excluded: errors 799, aborted 46, other/invalid timing or output 0. Generation-eligible: 46,094.

| Provider / model / tier | n | Sessions | Gen TPS | E2E TPS | TTFT median ms |
|---|---:|---:|---:|---:|---:|
| openai-codex / gpt-6-astra / default | 5236 | 24 | 31.31 | 26.14 | 2,849.36 |
| openai-codex / gpt-6-astra / priority | 522 | 4 | 34.44 | 30.85 | 2,339.09 |
| openai-codex / gpt-6-astra / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6-luna / default | 3426 | 181 | 95.43 | 82.68 | 1,936.89 |
| openai-codex / gpt-6-luna / priority | 350 | 14 | 101.59 | 84.22 | 2,125.07 |
| openai-codex / gpt-6-luna / unknown | 0 | 0 | — | — | — |
| openai-codex / gpt-6.1-sol / default | 35310 | 833 | 40.66 | 32.67 | 2,254.83 |
| openai-codex / gpt-6.1-sol / priority | 1250 | 36 | 53.01 | 42.40 | 1,761.05 |
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
| openai-codex / gpt-6-astra | priority ⚠ tiny sample | 2 | 522 | 4 | 34.44 | 30.85 | 2,339.09 | 2,283.00 | 137,959.00 | 616.00 |
| openai-codex / gpt-6-astra | default | 2 | 1965 | 17 | 27.07 | 22.95 | 2,981.44 | 1,276.00 | 118,646.00 | 361.00 |
| openai-codex / gpt-6-luna | priority | 1 | 309 | 13 | 102.14 | 84.15 | 2,155.17 | 4,899.00 | 113,061.00 | 667.00 |
| openai-codex / gpt-6-luna | default | 1 | 348 | 19 | 105.06 | 92.39 | 2,070.08 | 8,478.00 | 102,461.00 | 673.00 |
| openai-codex / gpt-6.1-sol | priority | 2 | 1250 | 36 | 53.01 | 42.40 | 1,761.05 | 937.50 | 54,039.00 | 152.50 |
| openai-codex / gpt-6.1-sol | default | 2 | 4659 | 154 | 35.82 | 29.67 | 2,283.98 | 989.00 | 45,881.00 | 164.00 |
| opencode-go / omen-alpha | Not comparable | 0 | — | — | — | — | — | — | — | — |
| opencode-go / step-5-preview-free | Not comparable | 0 | — | — | — | — | — | — | — | — |

</details>

<!-- REPORT:END -->
