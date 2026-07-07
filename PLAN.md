# 한국 주식 종가 조회 프로그램 — 설계 계획 (PLAN.md)

> **⚠️ 이 문서는 초기 설계 기록이며, 3~7절과 5절(인증 방식)은 실제 구현과 다소 다릅니다.**
> 루틴 환경의 네트워크가 기본적으로 제한되어 있어 한동안 우회 아키텍처(GitHub
> Actions + 서비스 계정, API 트리거 등)를 검토했으나, 최종적으로는 루틴 편집
> 화면의 **환경(Environment) 설정에서 Allowed domains에 필요한 도메인을 추가**하는
>것으로 해결되어 애초 의도했던 "루틴이 `main.py`를 직접 실행" 구조 그대로
> 남았습니다. 종목 리스트만 공개 CSV export 대신 Drive 커넥터로 읽습니다.
> **최종 아키텍처는 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)를 참고하세요.**

## 1. 개요

- **목적**: 대한민국 주식의 종가(closing price)를 조회하여, 호출한 프로그램(Claude Code 루틴)에 결과를 반환한다.
- **실행 주체**: Claude Code 루틴(cron 기반 트리거)이 세션 내에서 실행한다.
- **핵심 특성**
  - 무상태(stateless): 조회 결과를 파일/DB 등에 저장하지 않는다.
  - 호출-응답 구조: 실행할 때마다 결과를 구조화된 형태로 즉시 반환하고 종료한다.
  - 조회 대상 종목 리스트는 로컬 config 파일이 아니라 **Google Drive의 Sheet**에서 읽어온다. config 파일에는 그 Sheet의 위치(경로/ID) 및 접근 정보만 명시한다.

## 2. 기술 스택

| 구성 요소 | 선택 |
|---|---|
| 언어 | Python 3.x |
| 주가 조회 | FinanceDataReader |
| 종목 리스트 소스 | Google Sheets (Google Drive) |
| Sheets 접근 | Google Sheets API (google-api-python-client + google-auth) 또는 gspread |
| 환경 준비 | session-start-hook 스킬 기반 자동화 |
| 실행 트리거 | Claude Code Routine (cron) |

## 3. 아키텍처

### 3.1 입력: config 파일

리포지토리에 config 파일(예: `config.yaml` 또는 `config.json`)을 두고, 다음 정보를 담는다.

- `google_sheet.spreadsheet_id` — 대상 Google Sheet의 ID (또는 전체 URL)
- `google_sheet.range` — 종목 리스트가 있는 시트명/범위 (예: `Sheet1!A2:C`)
- `google_sheet.columns` — 컬럼 매핑 (예: `name`, `ticker`, `exchange`가 각각 몇 번째 컬럼인지)
- `auth.credentials_path` — 서비스 계정 키 파일 경로 (또는 이를 가리키는 환경변수 이름)
- 기타 실행 옵션 — 재시도 횟수, timeout 등

> 기존 `korea_stock_config.json`은 종목 리스트를 직접 담고 있었으나, 이번 설계에서는 이 파일의 역할이 "Google Sheet 위치 및 접근 설정"으로 바뀐다. 실제 종목 리스트(이름/티커/거래소)는 Sheet 쪽에서 관리한다.

### 3.2 실행 흐름

1. config 파일 로드
2. config에 명시된 Google Sheet에서 종목 리스트(이름, 티커, 거래소 등) 조회
3. FinanceDataReader로 각 종목의 최근 종가 조회
   - 정상 거래일이면 당일 종가
   - 휴장일/데이터 미존재 시 가장 최근 거래일 종가 + 해당 사실 표시
4. 종목별 결과를 구조화된 형태(JSON)로 집계
5. 결과를 표준출력(stdout)으로 반환하고 프로세스 종료 — **파일 저장 없음**
6. 일부 종목 조회 실패 시, 해당 종목만 에러로 표시하고 나머지는 정상 진행 (전체 실패로 처리하지 않음)

### 3.3 "API" 형태에 대한 결정

"Claude Code 루틴에서 실행할 수 있는 API"를 만드는 방법에는 두 가지 선택지가 있다.

| 방식 | 설명 | 적합성 |
|---|---|---|
| **A. CLI 스크립트 + stdout JSON 반환** | `python main.py --config config.yaml` 실행 → 표준출력으로 JSON 반환 | ✅ 권장 | - A 방식 적용
| B. 상시 구동 HTTP 서버 | 로컬 REST API 서버를 띄우고 루틴이 HTTP 호출 | ❌ 비권장 |

Claude Code 루틴은 트리거마다 새 세션에서 실행되는 모델이라, 상시 구동 서버(B)는 프로세스 관리·헬스체크 등 불필요한 복잡도를 추가한다. 반면 CLI 스크립트가 실행 즉시 결과를 stdout에 JSON으로 출력하고 종료하는 방식(A)은 "함수 호출"에 가깝게 동작하여 세션 기반 실행 모델과 잘 맞는다. 이를 "API"로 채택한다: 인자(config 경로)를 입력받아 표준화된 JSON을 출력하는 것이 곧 이 프로그램의 계약(contract)이다.

Claude Code 루틴은 이 스크립트를 Bash로 실행하고, stdout에 출력된 JSON을 파싱하여 사용자에게 요약을 보고하는 역할을 담당한다.

## 4. 환경 준비: session-start-hook

세션이 시작될 때마다 다음이 자동으로 준비되어야 한다.

- Python 실행 환경 확인 (가상환경 사용 여부 결정)
- `requirements.txt`에 명시된 의존성 설치 (`FinanceDataReader`, `google-api-python-client`, `google-auth` 등)
- Google 서비스 계정 인증 키의 존재 여부 확인 (환경변수 또는 시크릿 경로)
- 위 준비 과정을 `session-start-hook` 스킬을 통해 SessionStart 훅으로 등록하여, 매 루틴 실행마다 수동 설치 없이 즉시 스크립트를 실행할 수 있도록 한다.

## 5. Google Sheets 인증 방식 — 결정 필요

두 가지 방식이 가능하며, 아래 트레이드오프를 바탕으로 선택이 필요하다.

1. **서비스 계정 방식 (권장)**
   - Google Cloud 프로젝트에서 서비스 계정 생성 후 키(JSON) 발급
   - 대상 Google Sheet에 해당 서비스 계정 이메일을 "뷰어" 권한으로 공유
   - 키 파일은 리포지토리에 커밋하지 않고, 환경변수(예: `GOOGLE_APPLICATION_CREDENTIALS`)로 경로만 참조
   - 비공개 Sheet도 사용 가능, 가장 안전한 방식
2. **공개 CSV export 방식**
   - Sheet를 "링크가 있는 모든 사용자에게 공개"로 설정
   - `https://docs.google.com/spreadsheets/d/<ID>/export?format=csv` 형태의 URL로 인증 없이 조회
   - 구현이 단순하지만 시트 내용이 외부에 노출됨

→ 종목 리스트 자체는 민감 정보가 아닐 수 있으나, 보안 원칙상 **서비스 계정 방식을 기본안**으로 하고, 사용자가 간단함을 우선한다면 공개 CSV 방식도 대안으로 남겨둔다.
→ 민감정보가 아니므로 **공개 CSV export 방식**으로 진행한다.

## 6. 데이터 구조 (예시 스키마)

### config 파일 예시 구조
```yaml
google_sheet:
  spreadsheet_id: "<SHEET_ID>"
  range: "Sheet1!A2:C"
  columns:
    name: 0
    ticker: 1
    exchange: 2
auth:
  credentials_path_env: "GOOGLE_APPLICATION_CREDENTIALS"
options:
  retry_count: 2
  timeout_sec: 10
```

### 반환 JSON 예시 구조
```json
{
  "query_date": "2026-07-07",
  "results": [
    {"name": "삼성전자", "ticker": "005930", "close": 71000, "change_rate": -6.92, "date": "2026-07-07", "status": "ok"},
    {"name": "카카오", "ticker": "035720", "close": null, "change_rate": null, "status": "error", "message": "데이터 조회 실패"}
  ]
}
```

## 7. Claude Code 루틴 설계

- **트리거 방식**: cron 기반, `create_new_session_on_fire: true` (매 실행마다 새 세션에서 깨끗하게 시작)
- **실행 시각**: 평일 KST 16:00 (= UTC 07:00), 한국 정규장(15:30 마감) 이후 종가 확정 시간을 고려
- **cron 표현식 예시**: `0 7 * * 1-5` (UTC 기준)
- **세션 시작 시**: session-start-hook으로 Python 환경 및 의존성 자동 준비
- **루틴 prompt(지시문)**: "config.yaml을 인자로 main.py를 실행하고, stdout의 JSON 결과를 파싱하여 종목별 종가를 요약 보고. 조회 실패 종목이 있으면 별도로 알려줘."

## 8. 에러/예외 처리 정책

- Google Sheets 조회 자체가 실패하는 경우 → 전체 프로세스 실패로 간주, N회 재시도 후 최종 실패 시 에러 상태 반환
- 개별 종목의 종가 조회 실패 → 해당 종목만 `status: "error"`로 표시, 나머지 종목은 정상 진행
- 휴장일(주말/공휴일) → FinanceDataReader가 반환하는 가장 최근 거래일 데이터를 사용하고, 응답에 실제 조회된 날짜를 명시하여 당일 종가가 아님을 구분 가능하게 함

## 9. 결정이 필요한 사항 (Open Questions)

1. Google Sheets 인증 방식: 서비스 계정 vs 공개 CSV export - 공개 CSV export 방식 사용 
2. 재시도 횟수/timeout 등 구체적인 정책 수치 - 재시도 하지 않음. 
3. 조회 실패 시 별도 알림(Slack 등) 필요 여부 — "저장은 하지 않음"과는 별개의 문제로, 실행 결과 보고와 알림은 분리해서 결정 필요 - 조회 실패 시 별도 알림하지 않음.
4. Google Sheet의 컬럼 스키마(이름/티커/거래소 순서 및 헤더 존재 여부)를 실제 사용할 Sheet 기준으로 확정 - 첫번째 행에 헤더를 둠. 이름, 티커, 거래소 순으로 함

## 10. 다음 단계

1. 위 Open Questions 확정 (특히 Google Sheets 인증 방식)
2. 실제 사용할 Google Sheet의 컬럼 구조 확인
3. config 스키마 최종 확정
4. 확정된 설계를 바탕으로 실제 구현 착수
