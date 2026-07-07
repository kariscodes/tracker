"""Cloud 루틴 샌드박스에서 후보 금융 데이터 도메인들의 아웃바운드 연결 가능 여부를
한 번에 점검하는 일회성 진단 스크립트. 실제 시세 조회는 하지 않는다.

사용법: python check_network.py
"""

import json

import requests

CANDIDATES = {
    "krx (data.krx.co.kr)": "https://data.krx.co.kr",
    "yahoo (query2.finance.yahoo.com)": "https://query2.finance.yahoo.com",
    "naver (fchart.stock.naver.com)": "https://fchart.stock.naver.com",
    "google_sheets (docs.google.com)": "https://docs.google.com",
}

TIMEOUT_SEC = 8


def check(url):
    try:
        r = requests.get(url, timeout=TIMEOUT_SEC)
        return {"reachable": True, "status_code": r.status_code}
    except requests.RequestException as e:
        return {"reachable": False, "error": str(e)}


def main():
    results = {name: check(url) for name, url in CANDIDATES.items()}
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
