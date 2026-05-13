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

# --- TÝDENNÍ CACHE PRO EARNINGS (Oprava chyby s hashováním přes _tickers) ---
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

# --- 2. STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main .block-container { padding-top: 0.5rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 8px 10px; text-align: right; position: sticky; top: 0; }
    .portfolio-table th:first-child { text-align: left; }
    .portfolio-table td { padding: 7px 10px; border-bottom: 1px solid #eee; line-height: 1.2; }
    .ticker-name { font-weight: 700; color: #000; font-size: 14px; }
    .num { text-align: right; font-family: 'Roboto Mono', monospace; }
    .pos-text { color: #2e7d32; font-weight: bold; }
    .neg-text { color: #d32f2f; font-weight: bold; }
    .warn-cell { background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center; border-radius: 4px; padding: 1px 4px; }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIKA NAČTENÍ ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    tickers = df_raw["Ticker"].unique()
    m_data = load_market_data(tickers)
    earn_data = get_earnings_data(tickers)
    fx = get_fx_rates()

    # --- SIDEBAR ---
    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "🧠 Strategie", "📈 Výkonnost", "⚙️ Ostatní"])
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    time_frame = st.sidebar.selectbox("Období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)
    days_map = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}
    target_days = days_map[time_frame]

    processed = []
    total_val, total_ref = 0, 0
    
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        m_cur = str(r["Měna"]).strip()
        info = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series()})
        earn = earn_data.get(t, {"earn_dt": "-", "days_to": "-"})
        rate = fx.get(m_cur, 1.0)
        
        ks = pd.to_numeric(str(r['Ks']).replace(',','.').replace(' ',''), errors='coerce') or 0
        p_std = pd.to_numeric(str(r['Průměrná nákupní cena']).replace(',','.').replace(' ',''), errors='coerce') or 0
        p_opt = pd.to_numeric(str(r['Nákupní cena včetně opcí']).replace(',','.').replace(' ',''), errors='coerce') or 0
        ref_buy = p_std if view_mode == "Standard" else p_opt
        
        hist = info["history"]
        ref_price = hist.iloc[-(target_days + 1)] if (not hist.empty and len(hist) > target_days) else ref_buy
        curr_price = info["price"] if info["price"] > 0 else ref_buy
        val_czk = ks * curr_price * rate
        total_val += val_czk
        total_ref += (ks * ref_price * rate)

        processed.append({**r, "TC": curr_price, "RefPrice": ref_price, "Hodnota CZK": val_czk,
            "Zisk %": ((curr_price - ref_price) / ref_price * 100) if ref_price > 0 else 0,
            "Div_ks": info["div"], "Div_total": ks * info["div"] * rate,
            **earn, "History": hist})
    df_p = pd.DataFrame(processed)

    # --- STRÁNKY ---
    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th><th class='num'>Změna %</th><th class='num'>Div/ks</th><th class='num'>Div celkem</th><th>Earnings</th><th>Dní</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            tc_class = "pos-text" if r["TC"] >= r["RefPrice"] else "neg-text"
            pct_class = "pos-text" if r["Zisk %"] >= 0 else "neg-text"
            e_style = " class='warn-cell'" if (isinstance(r['days_to'], int) and r['days_to'] <= 14) else ""
            html += f"""<tr><td><span class='ticker-name'>{r['Název']}</span></td><td class='num'>{r['Ks']:.0f}</td><td class='num {tc_class}'>{format_cz(r['TC'])}</td><td class='num'><b>{format_cz(r['Hodnota CZK'], 0)}</b></td><td class='num {pct_class}'>{r['Zisk %']:.2f} %</td><td class='num'>{format_cz(r['Div_ks'])}</td><td class='num'>{format_cz(r['Div_total'], 0)}</td><td style='text-align:center'>{r['earn_dt']}</td><td{e_style}>{r['days_to']}</td></tr>"""
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Obor (Sektor)', 'Název'], values='Hodnota CZK', color='Obor (Sektor)')
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:,.0f} CZK<br>%{percentParent:.1%}", textfont=dict(size=15))
        fig.update_layout(margin=dict(t=30, l=10, r=10, b=10), height=800)
        st.plotly_chart(fig, use_container_width=True)

    elif page == "📈 Výkonnost":
        st.subheader("📊 Analýza výkonnosti")
        col_idx, col_stock = st.columns([1, 2])
        with col_idx: idx_t = "^GSPC" if st.radio("Index:", ["S&P 500", "DAX 40"], horizontal=True) == "S&P 500" else "^GDAXI"
        with col_stock: selected_stocks = st.multiselect("🔍 Vyberte konkrétní akcie:", options=df_p["Název"].tolist())
        if idx_t in m_data and not m_data[idx_t]["history"].empty:
            idx_h = m_data[idx_t]["history"].tail(target_days+1)
            idx_norm = (idx_h / idx_h.iloc[0] - 1) * 100
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=idx_norm.index, y=idx_norm, name=f"Index {idx_t}", line=dict(color='gray', dash='dash')))
            port_h = pd.Series(0.0, index=idx_h.index)
            for _, r in df_p.iterrows():
                if not r["History"].empty:
                    s = r["History"].reindex(idx_h.index, method='ffill')
                    if not s.empty and s.iloc[0] > 0: port_h += (s / s.iloc[0] - 1) * 100 * (r["Hodnota CZK"] / total_val)
            fig.add_trace(go.Scatter(x=idx_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(color='#2ecc71', width=4)))
            for s_name in selected_stocks:
                stock_data = df_p[df_p["Název"] == s_name].iloc[0]
                if not stock_data["History"].empty:
                    s_h = stock_data["History"].reindex(idx_h.index, method='ffill')
                    fig.add_trace(go.Scatter(x=s_h.index, y=(s_h/s_h.iloc[0]-1)*100, name=s_name))
            fig.update_layout(title="Relativní výkonnost v čase (%)", height=600, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

    elif page == "🧠 Strategie":
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df_p, x='Charakter', y='Hodnota CZK', color='Název', title="Dle Charakteru").update_layout(showlegend=False, height=700), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df_p, x='Sentiment', y='Hodnota CZK', color='Název', title="Dle Sentimentu").update_layout(showlegend=False, height=700), use_container_width=True)

    elif page == "⚙️ Ostatní":
        st.subheader("📊 Rozložení portfolia dle měn")
        fig = px.sunburst(df_p, path=['Měna', 'Název'], values='Hodnota CZK', color='Měna')
        st.plotly_chart(fig, use_container_width=True)

except Exception as e: st.error(f"Kritická chyba: {e}")
