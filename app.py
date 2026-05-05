import requests
import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# Setup browser-like session to prevent 403 errors on cloud servers
import requests
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

st.set_page_config(page_title="Stock Screener Pro", layout="wide")

def calculate_rsi(data, window=14):
    """Manual RSI calculation to avoid pandas-ta/numba dependencies."""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def get_tickers(market_choice):
    try:
        if "Nifty" in market_choice:
            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
            return [f"{t}.NS" for t in pd.read_csv(url)['Symbol'].tolist()]
        else:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            return pd.read_html(url)[0]['Symbol'].replace('\\.', '-', regex=True).tolist()
    except Exception as e:
        st.error(f"Error loading symbols: {e}")
        return []

def run_screener(tickers, status_box, table_box, progress_bar):
    results = []
    batch_size = 10
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        status_box.info(f"Scanning {i} to {min(i+batch_size, len(tickers))}...")
        
        try:
            data = yf.download(batch, period="2mo", interval="1d", group_by='ticker', silent=True, session=session)
            
            for ticker in batch:
                try:
                    df = data[ticker] if len(batch) > 1 else data
                    if df.empty or len(df) < 30: continue
                    
                    # Volume Ratio calculation
                    avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
                    vol_ratio = df['Volume'].iloc[-1] / avg_vol if avg_vol > 0 else 0
                    
                    # Manual RSI calculation
                    rsi_series = calculate_rsi(df['Close'])
                    current_rsi = rsi_series.iloc[-1]
                    
                    if vol_ratio > 2 and current_rsi > 50:
                        t_obj = yf.Ticker(ticker, session=session)
                        info = t_obj.info
                        pe = info.get('trailingPE')
                        price = info.get('currentPrice', df['Close'].iloc[-1])
                        
                        if pe and pe < 20:
                            results.append({
                                "Ticker": ticker,
                                "Price": round(price, 2),
                                "P/E": round(pe, 2),
                                "Vol Ratio": round(vol_ratio, 2),
                                "RSI": round(current_rsi, 2)
                            })
                            # Real-time ranked display
                            res_df = pd.DataFrame(results).sort_values(by="Vol Ratio", ascending=False)
                            table_box.dataframe(res_df, use_container_width=True)
                except: continue
        except: continue
        
        progress_bar.progress(min((i + batch_size) / len(tickers), 1.0))
        time.sleep(0.5)
    return pd.DataFrame(results)

st.title("📊 Alpha Market Screener")
market = st.sidebar.radio("Market", ["Nifty 500 (NSE)", "S&P 500 (US)"])

if st.sidebar.button("🚀 Start Full Scan"):
    all_tickers = get_tickers(market)
    if all_tickers:
        final_df = run_screener(all_tickers, st.empty(), st.empty(), st.progress(0))
        if not final_df.empty:
            st.success("Scan Complete!")
            st.download_button("Download CSV", final_df.to_csv(index=False), "results.csv")
