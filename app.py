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
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 8px; }
    .portfolio-table td { padding: 7px; border-bottom: 1px solid #ddd; }
    .num { text-align: right; font-family: monospace; }
    .pos { color: #2e7d32; font-weight: bold; }
    .neg { color: #d32f2f; font-weight: bold; }
    .warn { background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    m_data = load_market_data(df_raw["Ticker"].unique())
    earn_data = get_earnings_data(df_raw["Ticker"].unique())
    fx = {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    time_frame = st.sidebar.selectbox("Období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)
    target_days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[time_frame]

    processed = []
    total_val, total_ref = 0, 0
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        info = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series()})
        ks = float(str(r['Ks']).replace(',','.'))
        tc = info["price"]
        ref_buy = float(str(r['Průměrná nákupní cena' if view_mode == "Standard" else 'Nákupní cena včetně opcí']).replace(',','.'))
        ref_price = info["history"].iloc[-(target_days + 1)] if (not info["history"].empty and len(info["history"]) > target_days) else ref_buy
        
        rate = fx.get(str(r["Měna"]).strip(), 1.0)
        val = ks * tc * rate
        div_total = info["div"] * ks * rate
        total_val += val
        total_ref += ks * ref_price * rate
        
        processed.append({**r, "TC": tc, "Ref": ref_price, "Val": val, "Zisk%": ((tc - ref_price)/ref_price*100), "DivTotal": div_total, "History": info["history"], **earn_data.get(t, {"earn_dt":"-", "days_to":"-"})})
    
    df_p = pd.DataFrame(processed)

    st.sidebar.divider()
    st.sidebar.metric("Celkem CZK", f"{format_cz(total_val, 0)} CZK")
    diff = total_val - total_ref
    st.sidebar.metric(f"Změna", f"{format_cz(diff, 0)} CZK", f"{(diff/total_ref*100 if total_ref>0 else 0):.2f} %")

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>KS</th><th>Cena</th><th>CZK</th><th>Zisk %</th><th>Div</th><th>Earnings</th><th>Dní</th></tr></thead><tbody>"
        for _, r in df_p.iterrows():
            tc_cls = "pos" if r["TC"] >= r["Ref"] else "neg"
            z_cls = "pos" if r["Zisk%"] >= 0 else "neg"
            w_cls = "warn" if str(r["days_to"]).isdigit() and int(r["days_to"]) <= 14 else ""
            html += f"<tr><td>{r['Název']}</td><td class='num'>{r['Ks']:.0f}</td><td class='num {tc_cls}'>{format_cz(r['TC'])}</td><td class='num'>{format_cz(r['Val'], 0)}</td><td class='num {z_cls}'>{r['Zisk%']:.2f}%</td><td class='num'>{format_cz(r['DivTotal'], 0)}</td><td style='text-align:center'>{r['earn_dt']}</td><td class='{w_cls}'>{r['days_to']}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)
    
    elif page == "📈 Výkonnost":
        # ... (zůstává funkční verze)
        sel = st.multiselect("Srovnání:", df_p["Název"].tolist())
        idx_h = m_data["^GSPC"]["history"].tail(target_days)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="S&P 500", line=dict(dash='dash')))
        port_h = pd.Series(0.0, index=idx_h.index)
        for _, r in df_p.iterrows():
            h = r["History"].tail(target_days)
            if not h.empty:
                port_h += (h/h.iloc[0]-1)*100 * (r["Val"]/total_val)
                if r["Název"] in sel: fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=r["Název"]))
        fig.add_trace(go.Scatter(x=port_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4)))
        st.plotly_chart(fig, use_container_width=True)
        
    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Obor (Sektor)', 'Název'], values='Val', color='Obor (Sektor)')
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:,.0f} CZK<br>%{percentRoot:.1%}")
        fig.update_layout(height=800)
        st.plotly_chart(fig, use_container_width=True)
except Exception as e: st.error(f"Chyba: {e}")
