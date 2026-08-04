"""
FETCH REAL DATA FOR index_weighting_analysis.py

Pulls monthly dividend-adjusted (total return) price history from Yahoo
Finance's public chart API and writes data.csv in the exact format the
analysis script expects: date, series_a, series_b.

Defaults: SPY (cap-weighted S&P 500) vs RSP (equal-weighted S&P 500).
RSP launched April 2003, so common history starts there. Swap the tickers
below to compare anything else (SMH vs SOXX, VOO vs VTI, ...).

Why adjclose? Yahoo's adjusted close folds dividends and splits back into
the price series, which makes month-over-month percent changes a total
return, not just a price return. That is what you want for CAGR.

SETUP
  pip install pandas requests
  python fetch_data.py
"""

import datetime as dt
import time

import pandas as pd
import requests

# =============================================================================
# CONFIG
# =============================================================================
TICKER_A = "SPY"   # -> series_a  (label it NAME_A in the analysis script)
TICKER_B = "RSP"   # -> series_b  (label it NAME_B in the analysis script)
START = "1993-01-01"   # fetch from here; the join trims to common history
OUT_PATH = "data.csv"

CHART_URL = "https://query{n}.finance.yahoo.com/v8/finance/chart/{ticker}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}


def fetch_monthly_adjclose(ticker, start, retries=4):
    """Monthly dividend-adjusted closes for one ticker, as a pandas Series."""
    period1 = int(dt.datetime.strptime(start, "%Y-%m-%d").timestamp())
    period2 = int(time.time())
    params = {
        "interval": "1mo",
        "period1": period1,
        "period2": period2,
        "events": "div,split",
    }

    last_err = None
    for attempt in range(retries):
        # alternate between Yahoo's two query hosts on retries
        url = CHART_URL.format(n=1 + attempt % 2, ticker=ticker)
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                raise RuntimeError("rate limited (HTTP 429)")
            r.raise_for_status()
            result = r.json()["chart"]["result"][0]
            break
        except Exception as e:  # noqa: BLE001 - retry any transient failure
            last_err = e
            wait = 2 ** (attempt + 1)
            print(f"  {ticker}: attempt {attempt + 1} failed ({e}), retrying in {wait}s")
            time.sleep(wait)
    else:
        raise RuntimeError(f"could not fetch {ticker} after {retries} attempts: {last_err}")

    timestamps = result["timestamp"]
    adjclose = result["indicators"]["adjclose"][0]["adjclose"]

    idx = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("America/New_York")
    s = pd.Series(adjclose, index=idx.normalize().tz_localize(None), name=ticker).dropna()

    # Yahoo stamps monthly bars at the first trading day of the month and the
    # bar's close is that month's latest close — so the bar for the current
    # month is partial. Drop it.
    now = dt.date.today()
    s = s[~((s.index.year == now.year) & (s.index.month == now.month))]

    # re-stamp to calendar month-end so both series align exactly
    s.index = s.index.to_period("M").to_timestamp("M")
    return s


def main():
    print(f"Fetching {TICKER_A} ...")
    a = fetch_monthly_adjclose(TICKER_A, START)
    print(f"  {len(a)} months, {a.index[0].date()} to {a.index[-1].date()}")

    print(f"Fetching {TICKER_B} ...")
    b = fetch_monthly_adjclose(TICKER_B, START)
    print(f"  {len(b)} months, {b.index[0].date()} to {b.index[-1].date()}")

    df = pd.concat({"series_a": a, "series_b": b}, axis=1).dropna()
    df.index.name = "date"
    df.to_csv(OUT_PATH, float_format="%.6f")

    print(f"\nWrote {OUT_PATH}: {len(df)} rows of common history, "
          f"{df.index[0].date()} to {df.index[-1].date()}")
    print(f"  series_a = {TICKER_A}, series_b = {TICKER_B} "
          f"(dividend-adjusted monthly closes)")
    print("\nNext: python index_weighting_analysis.py")
    print("Heads up: with ~20 years of common history and a 10-year rolling")
    print("window you get ~10 years of rolling windows. Set ROLL_YEARS = 5 in")
    print("index_weighting_analysis.py if you want more windows to look at.")


if __name__ == "__main__":
    main()
