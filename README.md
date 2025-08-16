Weinstein Screener

A Python-based stock screener that scans all S&P 500 companies and identifies candidates in Stan Weinstein’s Stage 2 (breakout) phase.
The logic follows Weinstein’s principles of buying stocks when they break above their base and trade stronger than the market.

📌 Features

Fetches all S&P 500 tickers dynamically

Uses yfinance for price data

Computes 30-week moving average (approximated from daily data)

Screens for stocks:

Trading above their 30-week SMA

Showing relative strength vs SPY

With volume support (optional extension)

Outputs results to weinstein_candidates.csv

📦 Installation

Clone this repository:

git clone https://github.com/YOUR_USERNAME/weinstein-screener.git
cd weinstein-screener


Install dependencies:

pip install -r requirements.txt

▶️ Usage

Run the screener:

python weinstein_screener.py


Example log output:

2025-08-09 22:43:36,224 INFO: Starting Weinstein Stage 2 screener...
2025-08-09 22:43:40,237 INFO: Candidate: AMD | Close: 172.76 | SMA30: 118.75
2025-08-09 22:43:43,527 INFO: Candidate: AXON | Close: 842.50 | SMA30: 665.47
2025-08-09 22:44:20,926 INFO: Saved 6 candidates to weinstein_candidates.csv
2025-08-09 22:44:20,927 INFO: Done in 45s. Found 6 candidates.

📊 Output

Results are saved into weinstein_candidates.csv, e.g.:

Ticker	Close	SMA30	Relative Strength
AMD	172.76	118.75	Strong
AXON	842.50	665.47	Strong
🛠 Requirements

Python 3.9+

yfinance

pandas

numpy

requests

Install all at once with:

pip install -r requirements.txt

📖 Background

Stan Weinstein’s Stage Analysis breaks market behavior into 4 stages:

Stage 1 – Base building

Stage 2 – Breakout (buy zone)

Stage 3 – Top distribution

Stage 4 – Breakdown (decline)

This screener automates finding Stage 2 stocks within the S&P 500.

🚀 Roadmap

 Add weekly data support (instead of approximating from daily)

 Add volume breakout filter

 Add charts for candidates

 Extend to Nasdaq / Russell 2000

⚠️ Disclaimer

This project is for educational purposes only.
It is not financial advice. Always do your own research before making investment decisions.

👨‍💻 Author

Built by Minhui Roh