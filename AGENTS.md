# 프로젝트 작업 지침

## 범위와 권한

- Python 3.11+ 표준 라이브러리만 사용하고 최종 실행 파일은 `analyze.py` 하나로 유지한다. 웹 앱, 패키지 의존성, 별도 설정 프레임워크, 스케줄러를 추가하지 않는다.
- 로컬 분석 허가는 git 초기화·커밋·푸시, 원격 저장소 생성, Release 업로드 허가가 아니다. 사용자의 명시적 원격 작업 허가가 필요하며, 아카이브 발행은 별도 허가를 받는다. `--confirm`은 CLI 안전장치이지 사용자 허가의 대체물이 아니다.
- Actions의 생성물 커밋은 향후 승인된 저장소 운영을 위한 설정이다. 로컬 작업 중 자동으로 실행하지 않는다. cron과 PAT를 사용하지 않는다.

## CLI 계약

공통 `--project-dir PATH`는 격리된 검증용 출력 루트를 지정하며 기본값은 스크립트가 있는 디렉터리다.

```text
python3 analyze.py collect [--omp-home PATH] [--since YYYY-MM-DD] [--until ISO8601]
python3 analyze.py report [--repo OWNER/REPO] [--rebuild] [--days 7] [--until ISO8601]
python3 analyze.py validate
python3 analyze.py self-test
python3 analyze.py publish-archives --repo OWNER/REPO --confirm
```

- `collect`: 기본 시작일은 `2026-10-16`, 종료는 스캔 전에 고정한 현재 UTC다. 로컬 OMP 로그만 읽으며 네트워크·git·업로드를 하지 않는다. `--omp-home`으로 OMP 루트를 바꿀 수 있다.
- `report`: 기본 as-of는 index의 `source_cutoff`, 최근 기본 7개 KST 날짜를 표시한다. `--until`은 cutoff보다 늦을 수 없다. 원본 로그 접근은 금지한다. 로컬 캐시를 사용하고, 없을 때 `--repo`가 있으면 `gh`로 정확한 Release asset만 받는다. `--rebuild`는 기존 집계를 다시 만든다.
- `validate`: manifest와 생성물 스키마를 검증한다. 다운로드하지 않는다.
- `self-test`: 실제 동작에 대한 표준 라이브러리 unittest를 실행한다. 임시 테스트 파일 외에 프로젝트 결과를 바꾸거나 원격에 접근하지 않는다.
- `publish-archives`: `--repo`와 `--confirm`을 요구한다. Release에만 쓰며 git은 변경하지 않는다. 이 명령을 분석 작업의 부수 효과로 실행하지 않는다.

## 수집·시간·중복

한 프로필만 보지 않는다. 기본 프로필 및 `profiles/*/agent/sessions`를 포함해 실제로 존재하는 모든 프로필을 수집한다. 알려진 solar, opus, ox, codex 외에도 새 프로필과 workflow-plus 계열을 이름으로 제외하지 않는다. 비어 있는 프로필은 측정값이 없다. 계정이나 프로필을 모델 성능 집계 차원으로 노출하지 않는다.

파일 수정 날짜나 파일명 날짜가 아닌 **응답 timestamp**를 KST 날짜와 3시간 버킷 배정 기준으로 사용한다. 수집 시작 전에 UTC cutoff를 고정해 `data/index.json`의 `source_cutoff`에 보존한다. 시작 경계와 cutoff를 적용하며 완료 시점까지 확인해 미완료·cutoff 이후 응답을 섞지 않는다. 과거 `--until` 리포트는 해당 시점으로 필터링하지만 정규 월별 통계를 과거 부분 날짜 값으로 덮어쓰지 않는다.

provider response ID를 우선 사용하고 없으면 entry ID·provider·model·timestamp 조합으로 결정적 SHA-256 ID를 만든다. fork/복제 파일을 넘어 중복 제거한다. session header가 있으면 그 ID를 해시한다. header가 없는 파일만 로컬 경로의 해시를 대체 키로 사용하므로, 그 경우 세션 수가 정확한 독립 작업 수라는 보장은 없다. 원시 경로나 ID는 아카이브에 넣지 않는다.

`.cache/collector.sqlite3`는 변경된 파일만 다시 파싱하는 로컬 상태다. 파일 수정은 기존 sample ID별 내용과 비교하여 실제 달라진 날짜만 아카이브를 다시 생성하며 오류 카운터를 누적 가산하지 않는다. 삭제된 원본의 과거 측정값은 유지한다. 끝의 불완전 JSON 조각은 다음 수집까지 보류하고, 완성된 잘못된 JSON 줄은 실패 처리하여 새 index를 발행하지 않는다. index 기록 실패 시 dirty 날짜를 유지해 다음 실행에서 복구한다. 시작일 변경 시 관련 아카이브를 다시 내보내되 과거 범위를 조용히 삭제하지 않는다.

## 지표와 해석

provider·model·tier를 분리한다. tier는 `default`, `priority`, `auto`, `flex`, `scale`, `unknown`이다. 누락된 tier는 `unknown`이며 default나 priority로 추정하지 않는다. Fast 비교는 같은 provider/model의 **priority 대 default**만 사용한다.

정상 표본 `n`은 stop이 `stop` 또는 `toolUse`이고, 유한한 `duration_ms > 0` 및 `output_tokens > 0`인 응답이다. error·aborted는 별도 집계하고 토큰/시간 합산에서 제외한다. 나머지 부적합 표본은 invalid로 분리한다. 음수는 유효한 측정값으로 쓰지 않고 비유한 수는 null 처리한다.

- E2E TPS = `1000 × Σ output_tokens / Σ duration_ms`.
- Generation TPS = `1000 × Σ output_tokens / Σ(duration_ms − ttft_ms)`; 유한하고 `0 ≤ ttft_ms < duration_ms`인 표본만 분자와 분모에 함께 포함한다. 이 부분집합의 `generation_n`, `generation_output_tokens`, `generation_ms`를 별도로 유지한다.
- TTFT는 유효 표본의 중앙값이다. TTFT가 없거나 부적합해도 duration/output이 유효하면 E2E에는 남을 수 있다.
- 개별 TPS의 단순 평균, 버킷 TPS 평균, 중앙값의 중앙값으로 전체 수치를 만들지 않는다. 일별 지표도 해당 날짜 원표본에서 직접 계산한다.
- 응답 수와 서로 다른 session 수를 함께 표시한다. 토큰 합과 시간 합은 같은 유효 집합을 사용한다.

Fast 비교는 차트 기간 내 두 tier가 모두 존재하는 동일 3시간 버킷으로 한정한다. 한쪽 tier만 있으면 비교 불가다. 가중 생성/E2E TPS, TTFT 중앙값, n 및 세션 수를 보여 주고 작은 표본을 경고한다. 입력/context/출력 길이, 작업 종류, 시간대, 네트워크, 서버 상태와 사용자 선택이 다른 관찰 자료다. 모델·tier 간 속도 차이를 인과 효과나 유료 기능의 보장 성능으로 단정하지 않는다. TPS(생성 속도), TTFT(첫 토큰 대기), E2E(전체 응답 지연)를 혼동하지 않는다.

## 개인정보와 저장 형식

추적 파일에는 원문 프롬프트·응답·도구 인자/결과·계정·비용·로컬 경로·원시 ID·응답별 원자료를 넣지 않는다. 로컬 원본 로그를 복사하거나 업로드하지 않는다. 아카이브의 허용 필드는 해시 ID/session, provider/model/tier, timestamp/completed_at, stop, 토큰 수, duration/TTFT뿐이다. 허용 목록 밖의 필드는 거부한다. 해시도 익명성의 보장이 아니므로 저장소는 private으로 운영한다.

- `data/index.json`: 스키마/지표 버전, KST, since, 고정 cutoff, scan 카운터와 일별 asset 참조만 저장한다.
- `.cache/archives/YYYY-MM-DD.<전체 SHA256>.jsonl.gz`: 정제된 응답별 자료이며 git 추적 금지. gzip은 mtime=0·파일명 없음으로 결정적으로 생성한다.
- 월별 Release `data-YYYY-MM`: 내용 주소형 아카이브를 저장한다. 날짜 수정은 새 asset 및 index 참조로 반영하고 이전 asset을 덮어쓰거나 자동 삭제하지 않는다. 정리는 현재/과거 index 참조와 복구 요구를 확인하고 별도 승인받는다.
- GitHub 공식 한도는 Release 하나당 asset 1,000개, asset 하나당 2 GiB 미만이다. 이 도구의 일별 압축 파일 한도는 더 보수적인 128 MiB다. 잦은 부분 날짜 재발행도 월별 asset 수에 포함되므로 발행 전에 확인하고, 한도 접근 시 승인된 정리 또는 Release 분할 정책을 먼저 정한다. 한도를 피하려고 과거 참조 파일을 자동 삭제하지 않는다. 근거: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- 캐시와 다운로드 모두 압축 바이트의 manifest SHA-256·크기, 제한된 gzip 해제, 허용 필드·값·날짜·ID 중복·coverage를 검증한다. Actions cache를 신뢰 근거로 삼지 않는다. 임의 URL은 받지 않는다.
- index는 해당 아카이브가 준비된 후에만 교체한다. JSON은 결정적·원자적으로 쓰고 동일 내용이면 파일을 건드리지 않는다.

## 수정 이력과 장기 통계

`data/monthly/YYYY-MM.json`은 날짜별 archive 해시와 daily 및 3시간 bucket 통계를 보존한다. 스키마/지표 버전이 다르면 실패하거나 명시적으로 rebuild한다. `analysis_sha256`은 `analyze.py` 전체 바이트 해시다. 코드가 바뀌면 과거 날짜도 다시 계산하며, 그대로면 archive 해시가 같은 날짜를 재사용한다. 제거된 index 참조를 집계에 남기지 않고 중복 합산하지 않는다. 최근 비교와 월별 집계가 같은 아카이브를 사용하면 실행 내에서 한 번만 읽는다.

전체 월별 이력은 계속 보존하고 최근 차트 범위 때문에 과거 자료를 삭제하지 않는다. README에는 최근 12개월 일별 집계 기반 장기 추세를 둔다. 7일 차트의 합이나 버킷 평균으로 장기 지표를 대신하지 않는다.

## 차트와 문서 소유권

독립적으로 열리는 `report.svg`는 약 1000px 너비의 간결한 두 패널로 만든다. 위는 provider/model별 생성 TPS와 마지막 유효값 직접 라벨이며 tier는 토큰·시간 합으로 합친다. 아래는 cyan 그라데이션 정상 응답 수와 최다 구간·마지막 값이다. 한국어 제목, 읽기 쉬운 큰 글씨, 정돈된 눈금, 실제 KST 자정 날짜축을 사용한다. Sol cyan·Luna champagne·Astra emerald·Step violet의 의미를 유지하되 라이트/다크 대비는 별도 팔레트로 맞춘다. 중복 범례·과도한 빈 띠·장식 카드는 추가하지 않는다. 누락 TPS는 0으로 채우지 않고 선을 끊으며 마지막 부분 구간을 표시한다. 곡선은 overshoot 없는 monotone cubic이고 집계값을 평활화하지 않는다. 많은 모델은 높이를 늘리고 끝 라벨을 충돌 없이 배치한다. SVG는 외부 채팅 CSS 변수에 의존하지 않고 XML을 escape하며, 실제 브라우저의 라이트/다크 모드·라벨 잘림·좁은 화면 크기를 확인한다.

`fast-comparison.svg`는 같은 기간의 동일 provider/model·겹치는 3시간 구간을 사용하여 일반(default)과 Fast(priority)의 생성 TPS·대기 포함 TPS를 나란한 막대로 비교한다. 기존 Fast 상세표와 같은 모집단을 사용하고 두 패널의 TPS 축은 0부터 동일한 범위로 고정한다. 각 tier의 응답 수·세션 수, 겹친 구간 수, 관측 변화율과 표본 부족 경고를 함께 표시한다. 한쪽 tier가 없으면 비교 불가 상태를 표시하고, TTFT가 없으면 생성 TPS를 0으로 그리지 않는다. 생성 TPS의 응답 집합은 `generation_n`으로 따로 구분되며 표시된 전체 응답 수는 E2E 유효 모집단이다. 상세 TTFT·토큰 길이 표는 README의 접힌 영역에 보존한다.

README의 생성 영역은 정확히 한 쌍의 `<!-- REPORT:START -->` 및 `<!-- REPORT:END -->` 사이뿐이다. 바깥 사용자의 설명을 보존한다. cutoff·coverage·포함/제외 수·모델/tier·Fast 비교·차트 링크·장기 추세를 생성하되 실제 데이터 없는 측정 결과를 꾸며 쓰지 않는다.

## Actions 신뢰 경계

PR job은 `contents: read`와 자격 증명을 남기지 않는 checkout으로 `self-test` 및 `validate`만 실행한다. 아카이브 다운로드, cache 복원, report, 원격 쓰기는 하지 않는다. PR 코드 실행에는 쓰기 토큰이나 별도 secret을 제공하지 않는다.

생성 job은 신뢰된 main의 push 또는 main에서 요청한 workflow_dispatch에만 `contents: write`를 부여한다. `GITHUB_TOKEN`을 사용하고 `gh`가 설치된 Ubuntu runner를 전제로 한다. 재사용 cache 범위는 `.cache/archives`만이며 collector DB나 소스 로그를 포함하지 않는다. `report --repo "$GITHUB_REPOSITORY"`는 매번 외부 manifest를 기준으로 asset을 검증한다.

concurrency로 같은 ref의 실행을 직렬화한다. 생성 직전 remote main tip이 시작 SHA와 같은지 확인하고 다르면 중단한다. 이후 경쟁은 일반 non-force push가 거부한다. pull/rebase/force 또는 새 입력 덮어쓰기를 하지 않는다. 변경된 `README.md`, `report.svg`, `fast-comparison.svg`, `data/monthly`만 stage/commit하며 index·코드·원자료는 자동 커밋하지 않는다. 출력 전용 커밋은 입력 paths에 걸리지 않고 GITHUB_TOKEN의 재트리거 제한도 있으므로 자기 반복하지 않는다.

저장소 설정에서 Actions 쓰기 및 main의 bot push가 허용되어야 한다. 브랜치 보호가 거부하면 정책을 우회하지 않고 실패를 보고한다. cache는 최적화일 뿐, Release와 index를 복구 가능한 진실의 원천으로 유지한다.
