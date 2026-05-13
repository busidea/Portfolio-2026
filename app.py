import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- FUNKCE ---
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
            cp, dv, hist = 0, 0, pd.Series()
            if not raw_hist.empty:
                t_df = raw_hist[t].dropna(subset=['Close']) if len(all_symbols) > 1 else raw_hist.dropna(subset=['Close'])
                if not t_df.empty:
                    cp = t_df['Close'].iloc[-1]
                    hist = t_df['Close']
                    if 'Dividends' in t_df.columns:
                        dv = t_df[t_df.index >= (datetime.now() - timedelta(days=365))]['Dividends'].sum()
            data[t] = {"price": cp, "div": dv, "history": hist}
        except: data[t] = {"price": 0, "div": 0, "history": pd.Series()}
    return data

# --- STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 8px; text-align: right; }
    .portfolio-table td { padding: 7px; border-bottom: 1px solid #eee; }
    .num { text-align: right; font-family: monospace; }
    .pos-text { color: #2e7d32; font-weight: bold; }
    .neg-text { color: #d32f2f; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    m_data = load_market_data(df_raw["Ticker"].unique())
    earn_data = get_earnings_data(df_raw["Ticker"].unique())
    fx = get_fx_rates()

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    time_frame = st.sidebar.selectbox("Období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)
    target_days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[time_frame]

    processed = []
    total_val, total_ref = 0, 0
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        info = m_data.get(t, {"price": 0, "history": pd.Series()})
        rate = fx.get(str(r["Měna"]).strip(), 1.0)
        ks = float(str(r['Ks']).replace(',','.'))
        ref_buy = float(str(r['Průměrná nákupní cena' if view_mode == "Standard" else 'Nákupní cena včetně opcí']).replace(',','.'))
        hist = info["history"]
        ref_price = hist.iloc[-(target_days + 1)] if (not hist.empty and len(hist) > target_days) else ref_buy
        curr_price = info["price"] if info["price"] > 0 else ref_buy
        val_czk = ks * curr_price * rate
        total_val += val_czk
        total_ref += (ks * ref_price * rate)
        processed.append({**r, "TC": curr_price, "Hodnota CZK": val_czk, "Zisk %": ((curr_price - ref_price) / ref_price * 100), "History": hist, **earn_data.get(t, {"earn_dt":"-", "days_to":"-"})})
    df_p = pd.DataFrame(processed)

    st.sidebar.divider()
    st.sidebar.metric("Celkem", f"{format_cz(total_val, 0)} CZK")
    diff = total_val - total_ref
    st.sidebar.metric(f"Změna", f"{format_cz(diff, 0)} CZK", f"{(diff/total_ref*100):.2f} %")

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>Cena</th><th>CZK</th><th>Zisk %</th></tr></thead><tbody>"
        for _, r in df_p.iterrows():
            cls = "pos-text" if r["Zisk %"] >= 0 else "neg-text"
            html += f"<tr><td>{r['Název']}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num'>{format_cz(r['Hodnota CZK'], 0)}</td><td class='num {cls}'>{r['Zisk %']:.2f} %</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)
    
    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Název'], values='Hodnota CZK')
        fig.update_layout(height=800) # ROZTAŽENÍ
        st.plotly_chart(fig, use_container_width=True)

    elif page == "📈 Výkonnost":
        idx_t = st.radio("Index:", ["^GSPC", "^GDAXI"], horizontal=True)
        idx_h = m_data[idx_t]["history"].tail(target_days)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="Index"))
        for _, r in df_p.iterrows():
            h = r["History"].tail(target_days)
            if not h.empty: fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=r["Název"]))
        st.plotly_chart(fig, use_container_width=True)

    elif page == "⚙️ Ostatní":
        st.plotly_chart(px.sunburst(df_p, path=['Měna', 'Název'], values='Hodnota CZK'), use_container_width=True)
except Exception as e: st.error(f"Chyba: {e}")
