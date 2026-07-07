# 한국 주식 종가 조회 프로그램 — 구현 문서 (IMPLEMENTATION_PLAN.md)

> `PLAN.md`(초기 설계 문서)의 후속 문서. 이 문서가 **최종 구현 상태**를 반영한다.
> `PLAN.md`의 3~7절과 5절(인증 방식)은 이 문서로 대체된다.

## 어쩌다 이렇게 됐나 (요약)

1. 루틴이 `main.py`로 Sheet를 직접 CSV export 다운로드 → 샌드박스 프록시 403
2. Google Drive 커넥터로 Sheet 읽기는 우회 성공, 그러나 `FinanceDataReader`의
   시세 조회(`fchart.stock.naver.com`)는 여전히 샌드박스 직접 호출이라 동일하게 403
3. `check_network.py`로 확인한 결과 KRX/Naver/Yahoo/Google 도메인 전부 차단 —
   당시엔 루틴 환경(Claude Code Web)의 아웃바운드가 기본적으로 전부 막혀 있고
   예외가 없는 줄 알았음
4. GitHub Actions가 대신 계산해서 Sheet에 써주는 방식(서비스 계정 필요), 이어서
   루틴을 API로 직접 fire해서 결과를 텍스트로 넘기는 방식까지 검토
5. **하지만 루틴 편집 화면의 환경(Environment) 설정에 "Custom 네트워크 접근 +
   Allowed domains" 옵션이 있다는 걸 뒤늦게 발견.** `fchart.stock.naver.com`을
   허용 목록에 추가하니 샌드박스 안에서도 시세 조회가 정상 동작 — 애초에
   가장 간단했던 A안(도메인 허용)으로 해결됨. GitHub Actions/서비스 계정 관련
   코드는 모두 제거했다.

## 최종 아키텍처

```
[Claude Cloud 루틴, cron 평일 16:00 KST]
  1. Google Drive 커넥터로 Sheet를 CSV로 읽음 (download_file_content,
     exportMimeType="text/csv") — Sheet 공개 여부와 무관하게 동작
  2. 받은 CSV 원문을 파일 저장 없이 Bash heredoc으로 바로
     `python main.py --config korea_stock_config.json --csv-file -` 의 stdin에 흘림
  3. main.py 내부에서 FinanceDataReader가 fchart.stock.naver.com에 직접 접속해
     종목별 종가·등락률 조회 (환경의 Allowed domains에 추가되어 있어 정상 동작)
  4. stdout의 JSON을 파싱해 표로 정리, Slack 채널에 전송
  5. 파일 저장 없음 — 완전히 무상태(stateless)
```

당초 `PLAN.md`가 의도했던 구조(루틴이 `main.py`를 직접 실행하고 결과를 즉시
반환·보고) 그대로다. 다만 종목 리스트를 읽는 부분만 공개 CSV export 대신
Drive 커넥터를 쓴다 (Sheet를 공개로 유지하지 않아도 되는 부가 이점이 있음).

## 컴포넌트별 역할

| 파일 | 역할 |
|---|---|
| [korea_stock_config.json](korea_stock_config.json) | Sheet 위치, 컬럼 매핑, 옵션 |
| [src/config_loader.py](src/config_loader.py) | config 로드/검증 |
| [src/sheet_client.py](src/sheet_client.py) | 공개 CSV export 다운로드·파싱(`fetch_stock_list`), CSV 텍스트 파싱(`parse_stock_list`), 행→종목 변환 공통 로직(`rows_to_stocks`) |
| [src/price_fetcher.py](src/price_fetcher.py) | FinanceDataReader로 종목별 종가·등락률 조회 |
| [main.py](main.py) | CLI 진입점. `--csv-file`로 이미 받아온 CSV(Drive 커넥터 결과)를 stdin/파일로 받거나, `--print-csv-url`로 CSV export URL만 출력하거나, 인자 없이 직접 다운로드 |
| [check_network.py](check_network.py) | 진단용: 후보 도메인 아웃바운드 연결 가능 여부 일괄 점검 |

## config 스키마 (최종)

```json
{
  "google_sheet": {
    "spreadsheet_id": "1d9mGD1QpxQqaGEpmHSZuwHmYlsIPekQxo5852pv0W7Q",
    "gid": 0,
    "has_header": true,
    "columns": { "name": 0, "ticker": 1, "exchange": 2 }
  },
  "options": { "timeout_sec": 10 }
}
```

## 반환 JSON 스키마

```json
{
  "query_date": "2026-07-08",
  "results": [
    {"name": "삼성전자", "ticker": "005930", "close": 296000, "change_rate": -6.92, "date": "2026-07-07", "status": "ok"},
    {"name": "카카오", "ticker": "035720", "close": null, "change_rate": null, "status": "error", "message": "..."}
  ]
}
```

## 루틴 설정

- **cron**: 평일 07:00 UTC(=16:00 KST)
- **환경(Environment)**: 편집 화면 → Instructions 아래 클라우드 아이콘 → 환경 설정 →
  Network access를 **Custom**으로 바꾸고 **Allowed domains**에
  `fchart.stock.naver.com` 추가. **"Also include default list of common
  package managers" 체크를 반드시 켜야 한다** — 꺼두면 기존 Trusted 기본
  허용 목록(PyPI 등)이 사라져서 `pip install`이 403으로 실패한다 (실제로
  겪은 문제).
- **커넥터**: Google Drive, Slack
- **Setup script는 사용하지 않는다** — `pip install -r requirements.txt`는
  계속 매 실행마다 루틴 지침 1번 단계로 수행한다 (이미 설치돼 있으면
  거의 즉시 스킵되므로 실질적인 지연은 없음).

## 루틴 지침 (최종)

```
저장소 tracker를 clone/pull 받은 뒤 그 디렉터리에서 다음을 수행해줘.

1. 의존성이 없다면 `pip install -r requirements.txt`로 설치한다.
2. Google Drive 커넥터의 download_file_content 도구를
   fileId="1d9mGD1QpxQqaGEpmHSZuwHmYlsIPekQxo5852pv0W7Q",
   exportMimeType="text/csv" 로 호출해 Sheet 내용을 CSV로 받는다.
3. 응답의 content 필드(base64)를 디코딩해 CSV 원문(첫 줄은 헤더:
   이름,티커,거래소)을 얻는다.
4. 디코딩한 CSV 원문을 파일로 저장하지 말고, Bash heredoc으로 바로
   main.py의 stdin에 흘려보낸다 (작은따옴표 'EOF' 구분자 사용):

   python main.py --config korea_stock_config.json --csv-file - <<'EOF'
   <디코딩된 CSV 원문>
   EOF

5. stdout에 출력된 JSON을 파싱한다.
   - 최상위에 "status": "error"가 있으면 실행 실패로 간주하고 그 사실을
     message와 함께 Slack #channel-name 채널에 보낸다.
   - 정상인 경우 6번으로 진행한다.
6. results 배열을 표로 정리해 Slack #channel-name 채널에 전송한다:
   - 제목 줄: "한국 주식 종가 조회 결과 (query_date)"
   - 표 컬럼: 종목명 | 종가 | 등락률 | 조회일
   - "status": "error"인 종목은 표에서 빼고, 하단에 "조회 실패 종목"
     목록(이름/티커/사유)을 별도로 추가한다. 실패 종목이 없으면 생략.
7. 결과를 파일에 저장하지 않는다. Slack 전송이 유일한 결과 보고 채널이다.
```

## 검증 계획 (완료)

1. 로컬: `python main.py --config korea_stock_config.json --csv-file -`에 샘플 CSV를 흘려서 정상/개별 실패 케이스 확인 — 완료
2. 루틴 환경의 Allowed domains에 `fchart.stock.naver.com` 추가 후 저장 — 완료
3. "Also include default list of common package managers" 미체크로 `pip install` 403 발생 → 체크 후 재시도 — 완료, 해결
4. 루틴을 실제로 실행해 Slack 메시지가 정상 도착하는지 확인 — **완료, 정상 동작 확인**

이 프로젝트는 이 시점부터 정식 운영(평일 16:00 KST 자동 실행) 단계로 전환한다.
