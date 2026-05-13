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

@st.cache_data(ttl=3600)
def get_fx_rates():
    return {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

@st.cache_data(ttl=604800)
def get_earnings_data(_tickers):
    data = {}
    today = datetime.now().date()
    for t in list(_tickers):
        t_str = str(t).strip()
        earn_dt, days_to = "-", "-"
        if not t_str.startswith("^"):
            try:
                tk = yf.Ticker(t_str)
                cal = tk.calendar
                e_date = None
                if cal is not None:
                    if isinstance(cal, pd.DataFrame) and not cal.empty: e_date = cal.iloc[0, 0]
                    elif isinstance(cal, dict): e_date = cal.get('Earnings Date', [None])[0]
                if e_date and hasattr(e_date, 'date'):
                    e_date = e_date.date()
                    if e_date >= today:
                        earn_dt = e_date.strftime('%d.%m.%Y')
                        days_to = (e_date - today).days
            except: pass
        data[t_str] = {"earn_dt": earn_dt, "days_to": days_to}
    return data

@st.cache_data(ttl=600)
def load_market_data(_tickers):
    data = {}
    all_symbols = [str(t).strip() for t in _tickers if str(t).strip()]
    all_symbols += ["^GSPC", "^GDAXI"]
    try:
        raw_hist = yf.download(all_symbols, period="2y", interval="1d", group_by='ticker', progress=False, actions=True)
    except: raw_hist = pd.DataFrame()
    for t in all_symbols:
        try:
            cp, hist = 0, pd.Series()
            if not raw_hist.empty:
                t_df = raw_hist[t].dropna(subset=['Close']) if len(all_symbols) > 1 else raw_hist.dropna(subset=['Close'])
                if not t_df.empty:
                    cp = t_df['Close'].iloc[-1]
                    hist = t_df['Close']
            data[t] = {"price": cp, "history": hist}
        except: data[t] = {"price": 0, "history": pd.Series()}
    return data

# --- 2. STYLY ---
st.markdown("""
<style>
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 8px; }
    .portfolio-table td { padding: 7px; border-bottom: 1px solid #ddd; }
    .num { text-align: right; font-family: monospace; }
    .pos { color: #2e7d32; font-weight: bold; }
    .neg { color: #d32f2f; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    m_data = load_market_data(df_raw["Ticker"].unique())
    earn_data = get_earnings_data(df_raw["Ticker"].unique())
    fx = get_fx_rates()

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
    target_days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[st.sidebar.selectbox("Období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)]

    processed = []
    total_val = 0
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        info = m_data.get(t, {"price": 0, "history": pd.Series()})
        val = float(str(r['Ks']).replace(',','.')) * info["price"] * fx.get(str(r["Měna"]).strip(), 1.0)
        total_val += val
        processed.append({**r, "TC": info["price"], "Val": val, "History": info["history"], **earn_data.get(t, {"earn_dt":"-"})})
    df_p = pd.DataFrame(processed)

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>Cena</th><th>Hodnota</th></tr></thead><tbody>"
        for _, r in df_p.iterrows():
            html += f"<tr><td>{r['Název']}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num'>{format_cz(r['Val'], 0)}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)
    
    elif page == "📈 Výkonnost":
        col1, col2 = st.columns([1, 2])
        with col1:
            idx_t = st.radio("Index:", ["^GSPC", "^GDAXI"], horizontal=True)
            selected = st.multiselect("Výběr:", df_p["Název"].tolist())
        
        idx_h = m_data[idx_t]["history"].tail(target_days)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="Index", line=dict(dash='dash')))
        
        # Srovnání portfolia
        port_h = pd.Series(0.0, index=idx_h.index)
        for _, r in df_p.iterrows():
            if not r["History"].empty:
                s = r["History"].reindex(idx_h.index, method='ffill')
                port_h += (s / s.iloc[0] - 1) * 100 * (r["Val"] / total_val)
        fig.add_trace(go.Scatter(x=idx_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4)))
        
        # Selektivní tituly
        for s in selected:
            h = df_p[df_p["Název"]==s].iloc[0]["History"].tail(target_days)
            if not h.empty: fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=s))
        
        st.plotly_chart(fig, use_container_width=True)
    
    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Název'], values='Val')
        fig.update_layout(height=800)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e: st.error(f"Chyba: {e}")
