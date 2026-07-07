# 한국 주식 종가 조회 프로그램 — 단계적 구현 계획 (IMPLEMENTATION_PLAN.md)

> `PLAN.md`(설계 문서)의 후속 문서. `PLAN.md`의 Open Questions가 모두 확정된 뒤,
> 실제 코딩에 들어가기 전 순서와 산출물을 정리한 구현 계획이다. 아직 코드는 작성하지 않았다.

## Context

`PLAN.md`의 설계는 이미 확정되었다 (Open Questions 1~4 모두 답변 완료):
- Google Sheets 접근: **공개 CSV export 방식** (서비스 계정 인증 불필요)
- 재시도: **없음**
- 실패 알림: 별도 알림 없음 (stdout JSON 결과에만 반영)
- Sheet 컬럼: 헤더 행 존재, **이름 → 티커 → 거래소** 순서
- 실제 대상 Sheet: `https://docs.google.com/spreadsheets/d/1d9mGD1QpxQqaGEpmHSZuwHmYlsIPekQxo5852pv0W7Q/edit`

다만 `PLAN.md` 3.1절의 config 예시 스키마는 여전히 Sheets API(서비스 계정) 기준으로 작성되어 있어, 5절의 CSV export 결정과 불일치한다. 이 문서는 그 불일치를 해소하고, CSV export 방식에 맞춘 최종 config 스키마와 코드 구조를 확정한 뒤, 실제 코딩 순서를 정리한다.

## 사전 확인 필요 사항 (사용자 액션)

- 대상 Google Sheet(`1d9mGD1QpxQqaGEpmHSZuwHmYlsIPekQxo5852pv0W7Q`)의 공유 설정이 **"링크가 있는 모든 사용자 - 뷰어"**로 되어 있는지 확인 필요. CSV export 방식은 인증 없이 접근하므로 비공개 상태면 다운로드가 실패한다. (코드로 확인 불가 — Drive에서 직접 확인)

## 1. config 스키마 재설계 (CSV export 기준)

기존 `korea_stock_config.json`의 역할을 "Sheet 위치·파싱 설정"으로 교체한다. Sheets API 전용 필드(`auth.credentials_path`, `google_sheet.range`)는 제거하고 CSV export에 필요한 최소 필드만 남긴다.

```json
{
  "google_sheet": {
    "spreadsheet_id": "1d9mGD1QpxQqaGEpmHSZuwHmYlsIPekQxo5852pv0W7Q",
    "gid": 0,
    "has_header": true,
    "columns": { "name": 0, "ticker": 1, "exchange": 2 }
  },
  "options": {
    "timeout_sec": 10
  }
}
```

- `gid`: 대상 시트 탭의 gid (기본 탭이면 0)
- `retry_count` 필드는 Open Question #2 결정(재시도 없음)에 따라 제외

## 2. 프로젝트 구조

```
tracker/
├── korea_stock_config.json   # 재설계된 config (기존 파일 내용 교체)
├── requirements.txt          # FinanceDataReader, pandas, requests
├── main.py                   # CLI 진입점 (--config 인자)
└── src/
    ├── config_loader.py      # config 로드 + 스키마 검증
    ├── sheet_client.py       # CSV export URL 조립, 다운로드, 파싱 → 종목 리스트
    └── price_fetcher.py      # FinanceDataReader로 종목별 최근 종가 조회
```

`gspread`, `google-api-python-client`, `google-auth`는 CSV export 방식에서는 불필요하므로 requirements에서 제외한다.

## 3. 모듈별 구현 계획

**config_loader.py**
- JSON 로드, 필수 키(`google_sheet.spreadsheet_id`, `columns`) 존재 검증
- 누락 시 명확한 에러 메시지로 예외 발생

**sheet_client.py**
- URL 조립: `https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}`
- `requests.get(url, timeout=options.timeout_sec)`로 다운로드 (재시도 없음)
- CSV 파싱 시 `has_header=true`면 첫 행 스킵, `columns` 매핑대로 (name, ticker, exchange) 튜플 리스트 생성
- 다운로드/파싱 실패는 예외로 상위 전파 → `PLAN.md` 8절 "Sheet 조회 자체 실패 = 전체 프로세스 실패" 정책 반영

**price_fetcher.py**
- 종목별로 `FinanceDataReader.DataReader(ticker)` 호출을 개별 try/except로 감쌈 (한 종목 실패가 전체를 막지 않음)
- 정상: 최근 행의 종가·거래일 추출 → `{"name","ticker","close","date","status":"ok"}`
- 실패: `{"name","ticker","close":null,"status":"error","message":...}`
- 휴장일 등으로 당일 데이터가 없으면 FDR이 반환하는 가장 최근 거래일 종가를 쓰고 `date` 필드로 실제 조회일을 명시

**main.py**
- `argparse`로 `--config` 인자 (기본값 `korea_stock_config.json`)
- 흐름: config 로드 → sheet_client로 종목 리스트 조회(실패 시 에러 JSON 출력 + `exit(1)`) → price_fetcher로 종목별 조회 → `{"query_date": ..., "results": [...]}` 조립 → `json.dumps(..., ensure_ascii=False)`로 stdout 출력 → `exit(0)`

## 4. Claude Code 루틴 연동 설계 (실제 등록은 구현 단계에서 수행)

- **session-start-hook**: Python 가상환경 확인, `requirements.txt` 설치. (인증 키 확인 절차는 CSV export 방식이라 불필요 — `PLAN.md` 4절에서 해당 항목 제외)
- **cron 트리거**: `0 7 * * 1-5` (UTC, 평일 KST 16:00), `create_new_session_on_fire: true`
- **루틴 prompt**: "korea_stock_config.json을 인자로 main.py를 실행하고, stdout의 JSON 결과를 파싱하여 종목별 종가를 요약 보고. 조회 실패 종목이 있으면 별도로 알려줘."

## 5. 검증 계획

구현 완료 후:
1. `python main.py --config korea_stock_config.json` 수동 실행 → stdout JSON 확인
2. 정상 종목, 존재하지 않는 티커(개별 에러), 휴장일 케이스 각각 결과 확인
3. `spreadsheet_id`를 잘못된 값으로 바꿔 Sheet 접근 실패 시나리오 재현 → 에러 JSON + `exit(1)` 확인
4. cron 등록 전 위 수동 실행으로 정상 동작을 먼저 확인
