"""Google Sheet 공개 CSV export에서 종목 리스트 조회.

`fetch_stock_list()`는 로컬 등 아웃바운드 네트워크가 열린 환경에서 직접
CSV를 다운로드한다. 네트워크가 제한된 샌드박스(예: Claude Cloud 루틴)에서는
호출자(에이전트)가 `build_csv_export_url()`로 URL을 얻어 자체 도구로 CSV를
가져온 뒤, 그 텍스트를 `parse_stock_list()`에 전달하는 방식을 쓴다.
"""

import csv
import io

import requests

CSV_EXPORT_URL = "https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


class SheetFetchError(Exception):
    """Sheet 다운로드/파싱 실패."""


def build_csv_export_url(google_sheet):
    return CSV_EXPORT_URL.format(
        spreadsheet_id=google_sheet["spreadsheet_id"],
        gid=google_sheet["gid"],
    )


def rows_to_stocks(rows, google_sheet):
    """CSV/Sheets API 어느 쪽에서 왔든, 행 목록(list of list[str])을 종목 리스트로 변환한다."""
    if google_sheet["has_header"] and rows:
        rows = rows[1:]

    columns = google_sheet["columns"]
    name_idx = columns["name"]
    ticker_idx = columns["ticker"]
    exchange_idx = columns["exchange"]

    stocks = []
    for row in rows:
        if not row or not any(str(cell).strip() for cell in row):
            continue
        try:
            stocks.append(
                {
                    "name": str(row[name_idx]).strip(),
                    "ticker": str(row[ticker_idx]).strip(),
                    "exchange": str(row[exchange_idx]).strip(),
                }
            )
        except IndexError:
            raise SheetFetchError(f"Sheet 행의 컬럼 수가 부족합니다: {row}")

    if not stocks:
        raise SheetFetchError("Sheet에서 조회된 종목이 없습니다")

    return stocks


def parse_stock_list(csv_text, google_sheet):
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    return rows_to_stocks(rows, google_sheet)


def fetch_stock_list(config):
    """CSV를 직접 다운로드해 파싱한다 (아웃바운드 네트워크가 열린 환경 전용)."""
    google_sheet = config["google_sheet"]
    timeout_sec = config["options"]["timeout_sec"]
    url = build_csv_export_url(google_sheet)

    try:
        response = requests.get(url, timeout=timeout_sec)
        response.raise_for_status()
    except requests.RequestException as e:
        raise SheetFetchError(f"Google Sheet 다운로드 실패: {e}")

    return parse_stock_list(response.content.decode("utf-8-sig"), google_sheet)
