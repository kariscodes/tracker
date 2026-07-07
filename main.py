"""한국 주식 종가 조회 프로그램 — CLI 진입점.

사용법:
  python main.py --config korea_stock_config.json
  python main.py --print-csv-url --config korea_stock_config.json
  python main.py --config korea_stock_config.json --csv-file sheet.csv
  <CSV 내용> | python main.py --config korea_stock_config.json --csv-file -

결과를 stdout에 JSON으로 출력하고 종료한다 (파일 저장 없음).

`--csv-file`은 아웃바운드 네트워크가 제한된 환경(예: Claude Cloud 루틴
샌드박스)을 위한 옵션이다. 이 경우 호출자가 `--print-csv-url`로 얻은
URL을 자체 도구(WebFetch 등)로 미리 받아 파일 또는 stdin으로 넘긴다.
"""

import argparse
import datetime
import json
import sys

from src.config_loader import ConfigError, load_config
from src.price_fetcher import fetch_prices
from src.sheet_client import (
    SheetFetchError,
    build_csv_export_url,
    fetch_stock_list,
    parse_stock_list,
)


def _error_exit(message):
    print(
        json.dumps({"status": "error", "message": message}, ensure_ascii=False),
        file=sys.stdout,
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="한국 주식 종가 조회")
    parser.add_argument(
        "--config", default="korea_stock_config.json", help="config 파일 경로"
    )
    parser.add_argument(
        "--print-csv-url",
        action="store_true",
        help="config에서 계산한 Google Sheet CSV export URL만 출력하고 종료",
    )
    parser.add_argument(
        "--csv-file",
        default=None,
        help=(
            "이미 받아온 Sheet CSV 파일 경로. 지정하면 이 파일을 파싱하고 "
            "직접 네트워크로 다운로드하지 않는다. '-'를 넘기면 stdin에서 읽는다."
        ),
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as e:
        _error_exit(str(e))
        return

    if args.print_csv_url:
        print(build_csv_export_url(config["google_sheet"]))
        sys.exit(0)

    try:
        if args.csv_file:
            if args.csv_file == "-":
                csv_text = sys.stdin.read()
            else:
                with open(args.csv_file, "r", encoding="utf-8-sig") as f:
                    csv_text = f.read()
            stocks = parse_stock_list(csv_text, config["google_sheet"])
        else:
            stocks = fetch_stock_list(config)
    except (SheetFetchError, OSError) as e:
        _error_exit(str(e))
        return

    results = fetch_prices(stocks)

    output = {
        "query_date": datetime.date.today().isoformat(),
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
