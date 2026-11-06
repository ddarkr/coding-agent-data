# coding-agent-data 인수인계

로컬 OMP 응답의 생성 속도와 지연 시간을 누적 관찰하는 개인용 프로젝트입니다. Python 3.11+ 표준 라이브러리만 사용하며 실행 파일은 `analyze.py` 하나입니다. 개인 작업의 관찰 자료이지 모델 성능 순위나 Fast 요금제의 인과 효과를 입증하는 벤치마크가 아닙니다.

[최신 보고서](README.md) · [추세 SVG](report.svg) · [일반/Fast 비교 SVG](fast-comparison.svg) · [에이전트 작업 규칙](AGENTS.md)

## 문서 역할

- `README.md`에는 `Latest 7 KST dates`와 `Fast comparison · matched 3-hour buckets` 두 보고서 섹션을 둡니다. 각 섹션의 그래프·표본·상세표는 유지합니다.
- 사용법, 저장 구조, 운영 안내, 주의사항과 장기 통계는 이 문서에 둡니다.
- 에이전트는 작업 전에 `AGENTS.md`와 이 문서를 읽습니다. 요청 없는 commit/push, Release 업로드, 결제 설정 변경은 하지 않습니다.
- `report`는 README의 `REPORT` 영역과 이 문서의 `HISTORY` 영역만 갱신합니다. 그 밖의 운영 메모는 보존합니다.

## 로컬 사용

```sh
python3 analyze.py collect
python3 analyze.py report
python3 analyze.py validate
python3 analyze.py self-test
```

`collect`는 기본 프로필과 모든 `profiles/*/agent/sessions`를 읽습니다. 기본 시작일은 `2026-10-16`이며 수집 시작 시점의 UTC cutoff를 고정합니다. 파일명 날짜가 아니라 응답 timestamp로 KST 날짜와 3시간 구간을 결정합니다. 네트워크, git, Release 업로드는 수행하지 않습니다.

`report`는 로컬의 검증된 일별 아카이브에서 월별 통계, 최신 7일 집계 스냅샷, SVG 두 장과 문서를 만듭니다. 공개 집계 스냅샷으로는 해당 최신 7일 보고서만 재생성할 수 있습니다. 다른 기간이나 `--rebuild`는 로컬 원본으로 `collect`해 로컬 아카이브 인덱스를 만든 뒤 사용할 수 있습니다.

## 저장 구조와 장기 데이터

- 로컬 원본 로그는 Mac에만 보존합니다. 대화 내용·도구 인자·계정·인증 정보·원시 식별자는 게시하지 않습니다.
- `.cache/collector.sqlite3`는 변경된 파일을 찾는 로컬 상태입니다. 응답 내용이 바뀐 날짜만 다시 내보내며 삭제된 원본의 과거 측정값은 유지합니다.
- `.cache/archives/YYYY-MM-DD.<SHA256>.jsonl.gz`는 허용 목록으로 정제한 응답별 숫자 측정값입니다. Git에 넣지 않습니다. 해시는 익명성을 보장하지 않습니다.
- 월별 GitHub Release `data-YYYY-MM`에 내용 주소형 일별 아카이브를 보관합니다. 같은 날짜가 바뀌면 새 asset을 만들고 이전 파일은 자동 삭제하지 않습니다.
- `data/index.json`의 `archives`와 `source_cutoff`는 게시된 응답별 아카이브의 범위입니다. `aggregate_snapshot`은 더 최신인 공개 집계 스냅샷의 경로·SHA-256·기준 시각을 별도로 가리킵니다.
- `data/latest-report.json`은 최신 7일 보고서 재생성에 필요한 집계만 담습니다. `data/monthly/YYYY-MM.json`은 일별·3시간별 집계와 로컬 입력 해시를 담습니다. 최신 응답별 아카이브는 공개하지 않았습니다.
- 같은 날짜는 기존 집계를 교체합니다. 새 합계를 기존 합계에 더해 중복 집계하지 않습니다. 구간 TPS 평균이나 중앙값의 중앙값으로 장기 지표를 만들지 않습니다.

## 원격 게시와 Actions

공개 저장소: https://github.com/ddarkr/coding-agent-data. 기존 Release의 응답별 아카이브도 공개되어 있습니다.

추가 원격 변경은 사용자의 현재 요청에 근거해 수행합니다. `publish-archives`는 비공개 저장소에만 업로드하며 별도 CLI 확인 플래그가 필요합니다. 공개 저장소의 최신 데이터는 응답별 아카이브 대신 집계 스냅샷과 월별 집계로 반영합니다.

다음 절차는 **비공개 저장소의 응답별 아카이브 게시**에만 적용합니다.

1. 로컬 수집·리포트·검증을 완료합니다. 원본 로그와 `.cache`는 추적하지 않습니다.
2. 승인된 아카이브 업로드를 실행합니다.

   ```sh
   python3 analyze.py publish-archives --repo ddarkr/coding-agent-data --confirm
   ```

3. 원격 asset의 존재와 바이트 검증 후, 승인된 git 작업으로 코드·문서·`data/index.json`·집계를 올립니다. **Release 아카이브 업로드가 index 푸시보다 먼저입니다.** 새 저장소를 다시 구성한다면 먼저 README만 있는 `main` 커밋을 준비합니다.

`main`의 `data/index.json`, `analyze.py`, workflow 파일 변경이 Actions를 실행합니다. 공개 집계 스냅샷이 지정되면 스냅샷·월별 파일의 SHA-256과 분석 코드 해시를 검증하고 보고서를 재생성합니다. 응답별 아카이브 모드에서는 정확한 Release asset을 받아 SHA-256·크기·스키마를 검증합니다. PR은 읽기 전용 self-test와 validate만 실행합니다.

수동 실행의 `rebuild`는 로컬 또는 접근 가능한 응답별 아카이브가 있을 때만 사용할 수 있습니다. 스케줄 실행과 PAT는 없고 `GITHUB_TOKEN`만 사용합니다. 원격 main이 실행 시작 SHA에서 변경되면 생성물 커밋을 거부하며 경쟁 변경을 덮지 않습니다.

초기 Actions 실행은 코드 단계 전에 계정 결제 실패 또는 지출 한도 문제로 차단됐습니다. 당시 실행 기록: https://github.com/ddarkr/coding-agent-data/actions/runs/39834014757 . 이는 과거 관측이며 재실행 전 현재 상태를 확인해야 합니다. 결제 설정을 자동으로 변경하거나 같은 실패를 확인하려고 반복 재실행하지 않습니다.

GitHub 공식 한도는 Release당 asset 1,000개, 파일당 2 GiB 미만입니다. 도구의 일별 압축 한도는 128 MiB입니다. 수정본도 asset 수에 포함되므로 정리는 현재·과거 index 참조와 복구 정책을 검토한 뒤 별도 승인받습니다. 근거: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

## 검증과 재실행

`self-test`는 가중 집계·중앙값·KST 경계·중복 제거·아카이브 변조·비밀 필드 제외·불완전 로그·실패 후 복구·과거 시점 조회·공개 집계 스냅샷 검증과 보고서 재생성을 확인합니다.

실제 데이터를 갱신한 뒤에는 `report`와 `validate`를 실행하고 SVG를 브라우저에서 확인합니다. 같은 index로 `report`를 다시 실행하면 동일 출력은 다시 쓰지 않습니다. `collect --until <기존 source_cutoff>`로 같은 기준 시각을 재현할 수 있습니다.

`.cache/collector.sqlite3`를 잃으면 남아 있는 로컬 로그를 다시 읽어야 합니다. 공개 집계만으로 개별 응답이나 임의 기간의 정확한 중앙값을 복구할 수는 없습니다. 원본을 삭제하기 전에는 별도의 안전한 보관·복구 가능 여부를 확인해야 합니다.

## 해석 주의사항

이 보고서의 TPS는 출력 토큰을 전체 요청시간으로 나눈 대기 포함 처리량(E2E)입니다. TTFT는 첫 출력 대기이며, E2E는 모델의 순수 생성 속도나 사용자 체감 지연과 같지 않습니다.

`report.svg` 상단은 모델과 tier별 E2E TPS 추세를 분리합니다. 같은 모델은 같은 색이며 일반(default)은 실선·채운 점, Fast(priority)는 파선·빈 점입니다. 라벨에는 provider와 tier를 표시합니다. 미상은 일반으로 간주하지 않고 기타 tier는 점선과 실제 tier 이름으로 구분합니다. 끝값은 각 계열의 마지막 유효 관측값이며 하단 정상 응답 수만 모든 tier를 합칩니다.

`fast-comparison.svg`의 일반/Fast 비교는 같은 provider/model의 default와 priority가 모두 존재하는 3시간 구간으로 제한합니다. 추세 그래프와 달리 겹치는 구간만 비교하며 tier 미상은 일반으로 간주하지 않습니다. 응답 수와 독립 세션 수를 함께 보고, 어느 한쪽이 30건 또는 5세션 미만이면 표본 부족을 경고합니다. 입력·context·출력 길이, 작업 종류, 시간대와 네트워크·서버 상태는 통제되지 않았습니다.

월별 집계의 `generation_tps` 등 기존 필드는 첫 출력 후 시간으로 계산한 참고값이며 실제 생성 속도를 보장하지 않습니다. 보고서에는 사용하지 않습니다. context 중앙값은 입력 + 캐시 읽기 토큰의 대리지표이며, 세션 수는 집계 구간 간 단순 합산할 수 없습니다.

`doda` 응답에는 첫 출력과 완료 사이가 10ms 미만인 표본이 다수 있어 버퍼링 또는 계측 영향이 의심됩니다. 이 경로의 생성 TPS는 실제 스트리밍 속도로 해석하지 않습니다. 세션의 Fast 요청 설정과 응답에서 확인된 tier도 별개이며, 설정만으로 `unknown` 응답을 `priority`로 바꾸지 않습니다.

## Terra 초기 관측 (2026-10-27)

아래는 수집 cutoff `2026-10-27T01:36:31.145Z`의 초기 스냅샷입니다. 최신 보고서와 구분해서 읽습니다. `openai-codex`의 응답 timestamp가 KST 10:31:12.569 이상, 10:36:31.145 미만인 같은 시간대만 비교했습니다.

| 모델·tier | 정상 응답 수 | 세션 수 | 생성 TPS | 대기 포함 TPS | TTFT 중앙값 |
|---|---:|---:|---:|---:|---:|
| gpt-6.1-terra / default | 59 | 3 | 86.06 | 26.99 | 2.05초 |
| gpt-6.1-sol / default | 48 | 4 | 48.48 | 19.43 | 4.12초 |

Terra 정상 응답은 모두 일반(default)이며 Fast(priority) 표본은 없습니다. Terra 로그에는 정상 응답 외에 tier 미상의 중단 1건이 있고 오류는 0건입니다. TTFT의 표본 p95는 17.87초, 최대는 22.58초이며 7/59건이 10초를 초과했습니다. p95는 원표본 정렬 후 선형보간한 값입니다.

두 모델 모두 5세션 미만이고 입력·문맥·출력 길이와 작업 구성이 다릅니다. 같은 시각의 관찰 비교이지 통제 벤치마크가 아니며, 속도 차이의 원인이나 코딩 정확도·수정 품질은 평가하지 않았습니다. Luna·Astra는 이 짧은 비교 구간에 유효 표본이 없어 제외했습니다.

## Terra Fast 설정 전후 관측 (2026-10-28)

수집 cutoff `2026-10-28T14:50:25.537Z`. `doda / gpt-6.1-terra` 한 세션에서 KST 23:40:43의 `priority` 설정 전후 각 9분 42초를 비교했습니다. 전환 전에 시작한 응답은 전 구간으로 분류했습니다. 설정 전 tier와 실제 서버 적용 tier는 확인되지 않아 일반 대 Fast의 확정 비교가 아닙니다.

![Terra Fast 설정 전후 추세](terra-fast-observation.svg)

| 구간 | 정상 응답 | 대기 포함 TPS | 첫 출력 대기 중앙값 | 전체 응답시간 중앙값 | 출력 토큰 중앙값 | Context 중앙값 |
|---|---:|---:|---:|---:|---:|---:|
| 설정 전 · tier 미확인 | 23 | 60.94 | 10.11초 | 13.54초 | 828 | 253,453 |
| Fast 설정 후 | 22 | 83.73 | 8.79초 | 14.25초 | 1,122 | 334,742.5 |

설정 후 중단 4건은 처리량에서 제외했습니다. 두 구간 각각 7건의 첫 출력과 완료 사이가 10ms 미만이어서 생성 TPS는 비교하지 않았습니다. 별도 세션의 Fast 설정 후 17건은 이 비교에 합치지 않았습니다. 응답 기록에는 실제 적용 tier가 없고 이전 요청 설정도 미상입니다. 작업·문맥·출력 길이가 통제되지 않은 1세션 관찰이므로 속도 변화의 원인을 Fast로 단정할 수 없습니다.

수치와 5분 구간은 [구조화된 관측 데이터](data/observations/2026-10-28-terra-fast.json)에 보존합니다. 요청 설정은 로컬 세션의 분기 조상과 요청 시작 시각으로 확인했으며, 일별 응답 아카이브에는 이 설정 정보가 없어 해당 아카이브만으로 설정 전후 분류를 재현할 수 없습니다.

## 장기 통계

아래 영역은 `report`가 직접 계산한 일별 집계에서 최근 12개월 통계를 생성합니다. 데이터가 없는 날짜와 월을 0 TPS로 취급하지 않습니다.

<!-- HISTORY:START -->


### Twelve-month daily trend

Calendar-month summary of direct daily aggregates; rates below are ratios of summed eligible tokens/time, never averaged TPS or medians. Absent dates remain unobserved, not zero.

| Month | Observed dates | Successful | E2E TPS | Errors / aborted / invalid |
|---|---:|---:|---:|---|
| 2025-12 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-01 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-02 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-03 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-04 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-05 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-06 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-07 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-08 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-09 | 0 | 0 | — | 0 / 0 / 0 |
| 2026-10 | 16 | 109235 | 34.50 | 1620 / 303 / 0 |
| 2026-11 | 5 | 11336 | 32.90 | 251 / 80 / 0 |

Timing is local client-observed. E2E TPS is total output tokens divided by total request duration, not a direct measurement of generation speed. Context median is input + cache-read tokens, a workload proxy, not a controlled context measurement. Session counts are distinct within each population and are not additive.

<!-- HISTORY:END -->
