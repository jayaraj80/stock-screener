import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime

st.set_page_config(page_title="Stock Screener Pro", layout="wide")

@st.cache_data(ttl=3600)
def get_tickers(market_choice):
    if "Nifty" in market_choice:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df = pd.read_csv(url)
        return [f"{t}.NS" for t in df['Symbol'].tolist()]
    else:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(url)[0]
        return df['Symbol'].replace('\\.', '-', regex=True).tolist()

def run_screener(tickers, status_box, table_box, progress_bar):
    results = []
    batch_size = 20
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        status_box.info(f"Scanning {i} to {min(i+batch_size, len(tickers))}...")
        
        try:
            # Bulk fetch to respect rate limits
            data = yf.download(batch, period="1mo", interval="1d", group_by='ticker', silent=True)
        except:
            continue
            
        for ticker in batch:
            try:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 20: continue
                
                vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
                rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                
                if vol_ratio > 2 and rsi > 50:
                    info = yf.Ticker(ticker).info
                    pe = info.get('trailingPE')
                    price = info.get('currentPrice', df['Close'].iloc[-1])
                    
                    if pe and pe < 20:
                        results.append({
                            "Ticker": ticker,
                            "Price": round(price, 2),
                            "P/E": round(pe, 2),
                            "Vol Ratio": round(vol_ratio, 2),
                            "RSI": round(rsi, 2)
                        })
                        # Update Ranked Table Live on Web Page
                        res_df = pd.DataFrame(results).sort_values(by="Vol Ratio", ascending=False)
                        table_box.dataframe(res_df, use_container_width=True)
            except:
                continue
        progress_bar.progress((i + batch_size) / len(tickers) if (i+batch_size) < len(tickers) else 1.0)
        time.sleep(1) # Ethical delay for API limits
    return pd.DataFrame(results)

st.title("📊 Real-Time Market Screener")
st.sidebar.header("Controls")
market_choice = st.sidebar.radio("Market", ["Nifty 500 (NSE)", "S&P 500 (NYSE Proxy)"])
auto_refresh = st.sidebar.checkbox("Auto-Refresh Loop")

status_msg = st.empty()
progress = st.progress(0)
table_placeholder = st.empty()

if st.sidebar.button("Run Full Scan"):
    tickers = get_tickers(market_choice)
    final_df = run_screener(tickers, status_msg, table_placeholder, progress)
    if not final_df.empty:
        status_msg.success(f"Finished! Found {len(final_df)} matches.")
        st.download_button("Export to CSV", final_df.to_csv(index=False), "results.csv")
    else:
        status_msg.warning("No matches found.")
    
    if auto_refresh:
        time.sleep(60)
        st.rerun()
