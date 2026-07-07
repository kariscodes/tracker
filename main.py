"""한국 주식 종가 조회 프로그램 — CLI 진입점.

사용법: python main.py --config korea_stock_config.json
결과를 stdout에 JSON으로 출력하고 종료한다 (파일 저장 없음).
"""

import argparse
import datetime
import json
import sys

from src.config_loader import ConfigError, load_config
from src.price_fetcher import fetch_prices
from src.sheet_client import SheetFetchError, fetch_stock_list


def main():
    parser = argparse.ArgumentParser(description="한국 주식 종가 조회")
    parser.add_argument(
        "--config", default="korea_stock_config.json", help="config 파일 경로"
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        stocks = fetch_stock_list(config)
    except (ConfigError, SheetFetchError) as e:
        print(
            json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False),
            file=sys.stdout,
        )
        sys.exit(1)

    results = fetch_prices(stocks)

    output = {
        "query_date": datetime.date.today().isoformat(),
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
