"""Google Sheet 공개 CSV export에서 종목 리스트 조회."""

import csv
import io

import requests

CSV_EXPORT_URL = "https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


class SheetFetchError(Exception):
    """Sheet 다운로드/파싱 실패."""


def fetch_stock_list(config):
    google_sheet = config["google_sheet"]
    timeout_sec = config["options"]["timeout_sec"]

    url = CSV_EXPORT_URL.format(
        spreadsheet_id=google_sheet["spreadsheet_id"],
        gid=google_sheet["gid"],
    )

    try:
        response = requests.get(url, timeout=timeout_sec)
        response.raise_for_status()
    except requests.RequestException as e:
        raise SheetFetchError(f"Google Sheet 다운로드 실패: {e}")

    reader = csv.reader(io.StringIO(response.content.decode("utf-8-sig")))
    rows = list(reader)

    if google_sheet["has_header"] and rows:
        rows = rows[1:]

    columns = google_sheet["columns"]
    name_idx = columns["name"]
    ticker_idx = columns["ticker"]
    exchange_idx = columns["exchange"]

    stocks = []
    for row in rows:
        if not row or not any(cell.strip() for cell in row):
            continue
        try:
            stocks.append(
                {
                    "name": row[name_idx].strip(),
                    "ticker": row[ticker_idx].strip(),
                    "exchange": row[exchange_idx].strip(),
                }
            )
        except IndexError:
            raise SheetFetchError(f"Sheet 행의 컬럼 수가 부족합니다: {row}")

    if not stocks:
        raise SheetFetchError("Sheet에서 조회된 종목이 없습니다")

    return stocks
