"""
Weinstein Stage 2 Screener for S&P 500
File: weinstein_screener.py

Purpose:
- Scan all S&P 500 companies and return those that currently meet Stan Weinstein's Stage 2 buy criteria:
  * Weekly breakout above prior base resistance (default: 20-week high)
  * Price > 30-week simple moving average (SMA) and 30-week SMA is rising
  * Breakout week volume > VOL_MULTIPLIER * average 30-week volume
  * (Optional) Relative Strength (RS) vs benchmark (SPY) is rising

Notes:
- This is a *screening* script only. It does NOT backtest or place trades.
- It uses weekly confirmed signals (based on weekly close). Entry would typically be at next session open.

Usage:
- pip install yfinance pandas numpy requests beautifulsoup4 tqdm
- python weinstein_screener.py

Outputs:
- Prints and saves a CSV `weinstein_candidates.csv` listing tickers that meet the criteria and relevant metrics.

"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from time import sleep
import logging

# ---------------------------
# CONFIG
# ---------------------------
START = "2010-01-01"
END = None  # None means up to today
SMA_WEEKS = 30
BASE_LOOKBACK_WEEKS = 20
VOL_AVG_WEEKS = 30
VOL_MULTIPLIER = 1.5
RS_REQUIRED = True
RS_LOOKBACK = 8
BATCH_SIZE = 50  # download tickers in batches to reduce chance of throttling
REQUEST_PAUSE = 1.0  # seconds between yfinance batch downloads

OUTPUT_CSV = "data/weinstein_candidates-daily.csv"

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# ---------------------------
# HELPERS
# ---------------------------

def fetch_sp500_tickers():
    """Fetch current S&P 500 tickers from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find('table', {'id': 'constituents'})
    if table is None:
        # fallback: try first sortable wikitable
        table = soup.find('table', {'class': 'wikitable sortable'})
    tickers = []
    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) >= 1:
            tick = cols[0].text.strip()
            # yfinance uses BRK-B vs BRK.B style; replace '.' with '-' for tickers like BRK.B -> BRK-B
            tick = tick.replace('.', '-')
            tickers.append(tick)
    return tickers


def to_weekly(df_daily):
    weekly = df_daily.resample('W-FRI').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
    weekly = weekly.dropna()
    return weekly


def compute_indicators(weekly, benchmark_weekly=None):
    w = weekly.copy()
    w['SMA30'] = w['Close'].rolling(SMA_WEEKS).mean()
    w['SMA30_slope'] = w['SMA30'].diff()
    w['avg_vol30'] = w['Volume'].rolling(VOL_AVG_WEEKS).mean()
    w['vol_spike'] = w['Volume'] > (VOL_MULTIPLIER * w['avg_vol30'])
    if benchmark_weekly is not None:
        b = benchmark_weekly['Close'].reindex(w.index).ffill()
        w['B_Close'] = b
        w['RS'] = w['Close'] / w['B_Close']
        w['RS_slope'] = w['RS'].diff(periods=RS_LOOKBACK)
    return w


def is_weinstein_buy(weekly_ind):
    """Return True if the last weekly row meets Weinstein buy criteria.
       Assumes the indicators have been computed on the weekly_ind dataframe.
    """
    if len(weekly_ind) < (SMA_WEEKS + BASE_LOOKBACK_WEEKS):
        return False, None

    last = weekly_ind.iloc[-1]
    # breakout: last close > prior BASE_LOOKBACK_WEEKS highs
    prior_high = weekly_ind['Close'].iloc[-(BASE_LOOKBACK_WEEKS+1):-1].max()
    cond_breakout = last['Close'] > prior_high
    cond_above_sma = (not pd.isna(last['SMA30'])) and (last['Close'] > last['SMA30'])
    cond_sma_up = (not pd.isna(last['SMA30_slope'])) and (last['SMA30_slope'] > 0)
    cond_vol = (not pd.isna(last['avg_vol30'])) and bool(last['vol_spike'])
    cond_rs = True
    if 'RS_slope' in weekly_ind.columns and RS_REQUIRED:
        cond_rs = (not pd.isna(last['RS_slope'])) and (last['RS_slope'] > 0)

    details = {
        'close': last['Close'],
        'prior_high': prior_high,
        'SMA30': last['SMA30'],
        'SMA30_slope': last['SMA30_slope'],
        'vol': last['Volume'],
        'avg_vol30': last['avg_vol30'],
        'vol_spike': bool(last['vol_spike']) if 'vol_spike' in last.index else False,
        'RS': last.get('RS', np.nan),
        'RS_slope': last.get('RS_slope', np.nan)
    }

    meets = cond_breakout and cond_above_sma and cond_sma_up and cond_vol and cond_rs
    return bool(meets), details

# ---------------------------
# MAIN SCREENER
# ---------------------------

def run_screener():
    tickers = fetch_sp500_tickers()
    logging.info(f"Fetched {len(tickers)} S&P 500 tickers")

    # Prepare results container
    candidates = []

    # We'll download SPY once as benchmark
    logging.info("Downloading benchmark SPY daily data...")
    spy = yf.download('SPY', start=START, end=END, progress=False, auto_adjust=False)

    # Flatten MultiIndex columns by taking first level only:
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)

    spy.index = pd.to_datetime(spy.index)
    spy_weekly = to_weekly(spy)

    # Process tickers in batches
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i+BATCH_SIZE]
        logging.info(f"Downloading batch {i//BATCH_SIZE + 1}: {len(batch)} tickers")
        try:
            data = yf.download(batch, start=START, end=END, progress=False, group_by='ticker', threads=True)
        except Exception as e:
            logging.warning(f"Batch download failed: {e}. Retrying individually.")
            data = None

        # small pause to avoid throttling
        sleep(REQUEST_PAUSE)

        for t in batch:
            try:
                if data is None:
                    df_daily = yf.download(t, start=START, end=END, progress=False)
                else:
                    if (isinstance(data.columns, pd.MultiIndex)):
                        # multi-ticker download
                        if t in data.columns.levels[0]:
                            df_daily = data[t].dropna()
                        else:
                            # ticker not in batch data
                            df_daily = yf.download(t, start=START, end=END, progress=False)
                    else:
                        # single ticker only
                        df_daily = data

                if df_daily is None or df_daily.empty:
                    logging.debug(f"No daily data for {t}, skipping.")
                    continue

                df_daily.index = pd.to_datetime(df_daily.index)
                weekly = to_weekly(df_daily)
                weekly_ind = compute_indicators(weekly, spy_weekly)
                meets, details = is_weinstein_buy(weekly_ind)
                if meets:
                    details['ticker'] = t
                    candidates.append(details)
                    logging.info(f"Candidate: {t} | Close: {details['close']:.2f} | SMA30: {details['SMA30']:.2f}")

            except Exception as e:
                logging.warning(f"Failed processing {t}: {e}")

    # Save results
    # After collecting all candidates:
    if candidates:
        df_cand = pd.DataFrame(candidates).set_index('ticker')

        # Add market cap column
        market_caps = {}
        for ticker in df_cand.index:
            try:
                info = yf.Ticker(ticker).info
                market_caps[ticker] = info.get("marketCap", None)
            except Exception as e:
                logging.warning(f"Could not fetch market cap for {ticker}: {e}")
                market_caps[ticker] = None

        df_cand["market_cap"] = pd.Series(market_caps)

        # Sort by market cap descending
        df_cand = df_cand.sort_values(by="market_cap", ascending=False)

        # Save sorted results
        df_cand.to_csv(OUTPUT_CSV)
        logging.info(f"Saved {len(candidates)} candidates to {OUTPUT_CSV} (sorted by market cap)")
    else:
        logging.info("No candidates found meeting the criteria.")

    return candidates

if __name__ == '__main__':
    import time
    start_time = datetime.now()
    logging.info("Starting Weinstein Stage 2 screener...")
    cands = run_screener()
    logging.info(f"Done in {(datetime.now() - start_time).total_seconds():.0f}s. Found {len(cands)} candidates.")
