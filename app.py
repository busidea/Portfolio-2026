import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- FUNKCE A STYLY (VAŠE FUNKČNÍ VERZE) ---
def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

st.markdown("""
<style>
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 8px; text-align: right; }
    .portfolio-table td { padding: 7px; border-bottom: 1px solid #ddd; }
    .num { text-align: right; font-family: monospace; }
    .pos { color: #2e7d32; font-weight: bold; }
    .neg { color: #d32f2f; font-weight: bold; }
    .warn { background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_market_data(_tickers):
    data = {}
    all_symbols = [str(t).strip() for t in _tickers if str(t).strip()]
    all_symbols += ["^GSPC", "^GDAXI"]
    try:
        raw_hist = yf.download(all_symbols, period="2y", interval="1d", group_by='ticker', progress=False)
    except: raw_hist = pd.DataFrame()
    for t in all_symbols:
        try:
            # Oprava: ffill() zajistí spojitost grafu
            hist = raw_hist[t]['Close'].ffill().dropna() if t in raw_hist else pd.Series()
            data[t] = {"price": hist.iloc[-1] if not hist.empty else 0, "history": hist}
        except: data[t] = {"price": 0, "history": pd.Series()}
    return data

# --- LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
df_raw = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv").dropna(subset=['Ticker'])
m_data = load_market_data(df_raw["Ticker"].unique())
target_days = 21 # Výchozí

processed = []
total_val = 0
for _, r in df_raw.iterrows():
    t = str(r["Ticker"]).strip()
    price = m_data.get(t, {}).get("price", 0)
    val = float(str(r['Ks']).replace(',','.')) * price * 23.4
    total_val += val
    processed.append({**r, "TC": price, "Val": val, "History": m_data.get(t, {}).get("history", pd.Series())})
df_p = pd.DataFrame(processed)

# --- STRÁNKY ---
page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost"])

if page == "💰 Přehled":
    html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>Cena</th><th>CZK</th></tr></thead><tbody>"
    for _, r in df_p.iterrows():
        html += f"<tr><td>{r['Název']}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num'>{format_cz(r['Val'], 0)}</td></tr>"
    st.write(html + "</tbody></table>", unsafe_allow_html=True)

elif page == "🖼️ Grafika":
    fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Obor (Sektor)', 'Název'], values='Val')
    fig.update_layout(height=800)
    st.plotly_chart(fig, use_container_width=True)

elif page == "📈 Výkonnost":
    idx_t = st.radio("Index:", ["^GSPC", "^GDAXI"], horizontal=True)
    sel = st.multiselect("Srovnání:", df_p["Název"].tolist())
    idx_h = m_data[idx_t]["history"].tail(target_days)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="Index (Srovnání)", line=dict(dash='dash')))
    
    port_h = pd.Series(0.0, index=idx_h.index)
    for _, r in df_p.iterrows():
        h = r["History"].reindex(idx_h.index, method='ffill')
        if not h.empty:
            port_h += (h/h.iloc[0]-1)*100 * (r["Val"]/total_val)
            if r["Název"] in sel: fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=r["Název"]))
    fig.add_trace(go.Scatter(x=port_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4)))
    st.plotly_chart(fig, use_container_width=True)
