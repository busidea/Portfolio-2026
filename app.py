import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Investiční Portál", layout="wide")

# CSS Styly
st.markdown("""
<style>
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 8px; text-align: right; }
    .portfolio-table td { padding: 7px; border-bottom: 1px solid #ddd; }
    .num { text-align: right; font-family: monospace; }
    .pos { color: #2e7d32; font-weight: bold; }
    .neg { color: #d32f2f; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Data
@st.cache_data(ttl=600)
def get_data(tickers):
    fx = {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}
    data = {}
    all_sym = list(set(tickers + ["^GSPC", "^GDAXI"]))
    raw = yf.download(all_sym, period="2y", interval="1d", group_by='ticker', progress=False)
    for t in all_sym:
        hist = raw[t]['Close'].ffill().dropna() if t in raw else pd.Series()
        div = raw[t]['Dividends'].sum() if 'Dividends' in raw[t].columns else 0
        data[t] = {"price": hist.iloc[-1] if not hist.empty else 0, "history": hist, "div": div}
    return data, fx

# Načtení
df_raw = pd.read_csv("https://docs.google.com/spreadsheets/d/1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA/export?format=csv").dropna(subset=['Ticker'])
m_data, fx = get_data(df_raw["Ticker"].unique().tolist())

# Sidebar
page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
target_days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[st.sidebar.selectbox("Období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)]

# Výpočty
processed = []
total_val = 0
for _, r in df_raw.iterrows():
    t = str(r["Ticker"]).strip()
    m = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series()})
    ks = float(str(r['Ks']).replace(',','.'))
    ref_b = float(str(r['Průměrná nákupní cena' if view_mode == "Standard" else 'Nákupní cena včetně opcí']).replace(',','.'))
    val_czk = ks * m["price"] * fx.get(str(r["Měna"]).strip(), 1.0)
    total_val += val_czk
    zisk = ((m["price"] - ref_b) / ref_b * 100)
    processed.append({**r, "TC": m["price"], "Val": val_czk, "Zisk%": zisk, "Div": m["div"] * ks * fx.get(str(r["Měna"]).strip(), 1.0), "History": m["history"]})
df_p = pd.DataFrame(processed)

# Stránky
if page == "💰 Přehled":
    html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>Cena</th><th>CZK</th><th>Zisk %</th><th>Div</th></tr></thead><tbody>"
    for _, r in df_p.iterrows():
        tc_cls = "pos" if r["TC"] >= float(str(r['Průměrná nákupní cena']).replace(',','.')) else "neg"
        z_cls = "pos" if r["Zisk%"] >= 0 else "neg"
        html += f"<tr><td>{r['Název']}</td><td class='num {tc_cls}'>{r['TC']:.2f}</td><td class='num'>{r['Val']:,.0f}</td><td class='num {z_cls}'>{r['Zisk%']:.2f}%</td><td class='num'>{r['Div']:,.0f}</td></tr>"
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
    fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="Index", line=dict(dash='dash')))
    port_h = pd.Series(0.0, index=idx_h.index)
    for _, r in df_p.iterrows():
        h = r["History"].reindex(idx_h.index, method='ffill')
        if not h.empty:
            port_h += (h/h.iloc[0]-1)*100 * (r["Val"]/total_val)
            if r["Název"] in sel: fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=r["Název"]))
    fig.add_trace(go.Scatter(x=port_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4)))
    st.plotly_chart(fig, use_container_width=True)

elif page == "⚙️ Ostatní":
    st.plotly_chart(px.sunburst(df_p, path=['Měna', 'Název'], values='Val'), use_container_width=True)
