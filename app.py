import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- 1. FUNKCE ---
def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=600)
def load_market_data(_tickers):
    data = {}
    all_symbols = [str(t).strip() for t in _tickers if str(t).strip()]
    all_symbols += ["^GSPC", "^GDAXI"]
    try:
        # Stáhneme data a zajistíme spojitost pomocí ffill()
        raw_hist = yf.download(all_symbols, period="2y", interval="1d", group_by='ticker', progress=False)
        if len(all_symbols) == 1: raw_hist = {all_symbols[0]: raw_hist}
    except: raw_hist = pd.DataFrame()

    for t in all_symbols:
        try:
            hist = pd.Series()
            if t in raw_hist:
                hist = raw_hist[t]['Close'].ffill().dropna()
            data[t] = {"price": hist.iloc[-1] if not hist.empty else 0, "history": hist}
        except: data[t] = {"price": 0, "history": pd.Series()}
    return data

# --- 2. LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
df_raw = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv").dropna(subset=['Ticker'])
m_data = load_market_data(df_raw["Ticker"].unique())

st.sidebar.title("💎 MENU")
page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
target_days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[st.sidebar.selectbox("Období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)]

# Výpočet pro zobrazení
processed = []
total_val = 0
for _, r in df_raw.iterrows():
    t = str(r["Ticker"]).strip()
    price = m_data.get(t, {}).get("price", 0)
    val = float(str(r['Ks']).replace(',','.')) * price * 23.4 # Zjednodušený přepočet
    total_val += val
    processed.append({**r, "TC": price, "Val": val, "History": m_data.get(t, {}).get("history", pd.Series())})
df_p = pd.DataFrame(processed)

# --- STRÁNKY ---
if page == "💰 Přehled":
    st.write(df_p[['Název', 'TC', 'Val']].style.format({"TC": "{:.2f}", "Val": "{:,.0f}"}))

elif page == "📈 Výkonnost":
    col1, col2 = st.columns([1, 3])
    with col1:
        idx_t = st.radio("Index:", ["^GSPC", "^GDAXI"], horizontal=True)
        sel = st.multiselect("Srovnání:", df_p["Název"].tolist())
    
    idx_h = m_data[idx_t]["history"].tail(target_days)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="Index (Srovnání)", line=dict(dash='dash', color='gray')))
    
    # Portfolio linka
    port_h = pd.Series(0.0, index=idx_h.index)
    for _, r in df_p.iterrows():
        h = r["History"].reindex(idx_h.index, method='ffill')
        if not h.empty:
            port_h += (h/h.iloc[0]-1)*100 * (r["Val"]/total_val)
            if r["Název"] in sel: fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=r["Název"]))
    
    fig.add_trace(go.Scatter(x=port_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4, color='#2ecc71')))
    st.plotly_chart(fig, use_container_width=True)

elif page == "🖼️ Grafika":
    fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Obor (Sektor)', 'Název'], values='Val')
    st.plotly_chart(fig, use_container_width=True)
