import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- 1. DEFINICE FUNKCÍ ---
def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    return {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

# Týdenní cache s podtržítkem pro vyřešení hashování
@st.cache_data(ttl=604800)
def get_earnings_data(_tickers):
    earnings_info = {}
    today = datetime.now().date()
    # Převedeme _tickers na standardní seznam, aby se s ním lépe pracovalo
    ticker_list = list(_tickers)
    for t in ticker_list:
        if not str(t).startswith("^"):
            try:
                tk = yf.Ticker(str(t))
                cal = tk.calendar
                e_date = None
                if isinstance(cal, pd.DataFrame) and not cal.empty: e_date = cal.iloc[0, 0]
                elif isinstance(cal, dict): e_date = cal.get('Earnings Date', [None])[0]
                
                if e_date and hasattr(e_date, 'date'):
                    e_date = e_date.date()
                    if e_date >= today:
                        earnings_info[str(t)] = {"date": e_date.strftime('%d.%m.%Y'), "days": (e_date - today).days}
                        continue
            except: pass
        earnings_info[str(t)] = {"date": "-", "days": "-"}
    return earnings_info

@st.cache_data(ttl=600)
def load_market_data(_tickers):
    data = {}
    all_symbols = [str(t).strip() for t in _tickers if str(t).strip()]
    all_symbols += ["^GSPC", "^GDAXI"]
    
    try:
        raw_hist = yf.download(all_symbols, period="2y", interval="1d", group_by='ticker', progress=False, actions=True)
    except:
        raw_hist = pd.DataFrame()

    for t in all_symbols:
        try:
            cp = 0
            if not raw_hist.empty:
                try:
                    t_df = raw_hist[t].dropna(subset=['Close']) if len(all_symbols) > 1 else raw_hist.dropna(subset=['Close'])
                    if not t_df.empty: cp = t_df['Close'].iloc[-1]
                except: pass
            data[t] = {"price": cp}
        except:
            data[t] = {"price": 0}
    return data

# --- 2. LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    tickers = df_raw["Ticker"].unique()
    m_data = load_market_data(tickers)
    earn_data = get_earnings_data(tickers)
    fx = get_fx_rates()

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "⚙️ Ostatní"])
    
    processed = []
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        info = m_data.get(t, {"price": 0})
        earn = earn_data.get(t, {"date": "-", "days": "-"})
        val_czk = float(r['Ks']) * info["price"] * fx.get(str(r["Měna"]).strip(), 1.0)
        processed.append({**r, **info, **earn, "Hodnota CZK": val_czk})
    df_p = pd.DataFrame(processed)

    if page == "💰 Přehled":
        st.subheader("Aktuální stav portfolia")
        st.table(df_p[['Název', 'price', 'date', 'days']])
    else:
        st.subheader("Rozložení měn")
        st.plotly_chart(px.sunburst(df_p, path=['Měna', 'Název'], values='Hodnota CZK'))

except Exception as e:
    st.error(f"Chyba: {e}")
