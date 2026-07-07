"""FinanceDataReader로 종목별 최근 종가 조회."""

import datetime

import FinanceDataReader as fdr

LOOKBACK_DAYS = 14


def _fetch_latest_close(ticker):
    start = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    df = fdr.DataReader(ticker, start)
    if df is None or df.empty:
        raise ValueError(f"'{ticker}'에 대한 시세 데이터가 없습니다")

    last_row = df.iloc[-1]
    date = df.index[-1]
    close = int(last_row["Close"])
    change_rate = round(float(last_row["Change"]) * 100, 2)
    return close, change_rate, date.strftime("%Y-%m-%d")


def fetch_prices(stocks):
    """종목별로 개별 실패를 허용하며 최근 종가와 전일 대비 등락률을 조회한다."""
    results = []
    for stock in stocks:
        entry = {"name": stock["name"], "ticker": stock["ticker"]}
        try:
            close, change_rate, date = _fetch_latest_close(stock["ticker"])
            entry.update(close=close, change_rate=change_rate, date=date, status="ok")
        except Exception as e:
            entry.update(close=None, change_rate=None, status="error", message=str(e))
        results.append(entry)
    return results
