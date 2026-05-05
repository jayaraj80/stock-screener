import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Stock Screener Pro", layout="wide")

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_tickers(market_choice):
    try:
        if "Nifty" in market_choice:
            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
            df = pd.read_csv(url)
            return [f"{t}.NS" for t in df['Symbol'].tolist()]
        else:
            # Using S&P 500 for US market to ensure high-quality data
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            df = pd.read_html(url)[0]
            return df['Symbol'].replace('\\.', '-', regex=True).tolist()
    except Exception as e:
        st.error(f"Error fetching ticker list: {e}")
        return []

def run_screener(tickers, status_box, table_box, progress_bar):
    results = []
    # Smaller batches are more stable for cloud-based fetching
    batch_size = 10 
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        status_box.info(f"Scanning {i} to {min(i+batch_size, len(tickers))}...")
        
        try:
            # Bulk download historical data for technicals
            data = yf.download(batch, period="1mo", interval="1d", group_by='ticker', silent=True)
            
            for ticker in batch:
                try:
                    df = data[ticker] if len(batch) > 1 else data
                    if df.empty or len(df) < 20: 
                        continue
                    
                    # 1. Technical Indicators
                    # Calculate Volume Ratio (Current / 20-day Average)
                    avg_vol = df['Volume'].rolling(window=20).mean().iloc[-1]
                    curr_vol = df['Volume'].iloc[-1]
                    vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
                    
                    # Calculate RSI (14)
                    df['RSI'] = ta.rsi(df['Close'], length=14)
                    rsi = df['RSI'].iloc[-1]
                    
                    # Filter: Volume > 2x and RSI > 50
                    if vol_ratio > 2 and rsi > 50:
                        # 2. Fundamental Check (Slow call - only done for tech matches)
                        stock_info = yf.Ticker(ticker).info
                        pe = stock_info.get('trailingPE')
                        price = stock_info.get('currentPrice', df['Close'].iloc[-1])
                        
                        # Filter: P/E < 20
                        if pe and pe < 20:
                            results.append({
                                "Ticker": ticker,
                                "Price": round(price, 2),
                                "P/E": round(pe, 2),
                                "Vol Ratio": round(vol_ratio, 2),
                                "RSI": round(rsi, 2)
                            })
                            # Update the Ranked Table in the UI immediately
                            res_df = pd.DataFrame(results).sort_values(by="Vol Ratio", ascending=False)
                            table_box.dataframe(res_df, use_container_width=True)
                except Exception:
                    continue # Skip specific ticker if data is missing
        except Exception as e:
            st.warning(f"Batch download failed: {e}")
            
        progress_bar.progress(min((i + batch_size) / len(tickers), 1.0))
        time.sleep(0.5) # Gentle delay to stay within API rate limits
        
    return pd.DataFrame(results)

# --- UI LAYOUT ---
st.title("📊 Real-Time Market Screener")
st.markdown("Filtering for: **P/E < 20** | **Volume > 2x Avg** | **RSI > 50**")

with st.sidebar:
    st.header("Screener Settings")
    market = st.radio("Select Market", ["Nifty 500 (NSE)", "S&P 500 (US)"])
    auto_refresh = st.checkbox("Enable Auto-Refresh Loop")
    run_btn = st.button("🚀 Run Full Scan", use_container_width=True)

status_msg = st.empty()
progress = st.progress(0)
table_placeholder = st.empty()

if run_btn:
    tickers_list = get_tickers(market)
    if tickers_list:
        final_results = run_screener(tickers_list, status_msg, table_placeholder, progress)
        
        if not final_results.empty:
            status_msg.success(f"Scan Finished! Found {len(final_results)} stocks matching your criteria.")
            st.download_button(
                label="📥 Download Results as CSV",
                data=final_results.to_csv(index=False),
                file_name=f"screener_results_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            status_msg.warning("Scan complete. No stocks currently match all three criteria.")
    
    if auto_refresh:
        time.sleep(300) # Wait 5 minutes before rerunning
        st.rerun()
