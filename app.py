import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- STYLY ---
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

# --- FUNKCE ---
def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=600)
def get_full_data(_tickers):
    fx = {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}
    data = {}
    all_sym = list(set(_tickers + ["^GSPC", "^GDAXI"]))
    raw = yf.download(all_sym, period="2y", interval="1d", group_by='ticker', progress=False)
    
    today = datetime.now().date()
    for t in all_sym:
        hist = raw[t]['Close'].ffill().dropna() if t in raw else pd.Series()
        div = raw[t]['Dividends'].sum() if 'Dividends' in raw[t].columns else 0
        
        # Earnings
        earn_dt, days_to = "-", "-"
        if not t.startswith("^"):
            try:
                tk = yf.Ticker(t)
                cal = tk.calendar
                e_date = cal.iloc[0, 0] if isinstance(cal, pd.DataFrame) else None
                if e_date and hasattr(e_date, 'date'):
                    e_date = e_date.date()
                    if e_date >= today:
                        earn_dt = e_date.strftime('%d.%m.%Y')
                        days_to = (e_date - today).days
            except: pass
        
        data[t] = {"price": hist.iloc[-1] if not hist.empty else 0, "history": hist, "div": div, "earn_dt": earn_dt, "days_to": days_to}
    return data, fx

# --- LOGIKA ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA/export?format=csv"
df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
m_data, fx = get_full_data(df_raw["Ticker"].unique().tolist())

# Sidebar
page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
target_days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[st.sidebar.selectbox("Období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)]

processed = []
total_val = 0
for _, r in df_raw.iterrows():
    t = str(r["Ticker"]).strip()
    m = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series()})
    rate = fx.get(str(r["Měna"]).strip(), 1.0)
    ks = float(str(r['Ks']).replace(',','.'))
    ref_b = float(str(r['Průměrná nákupní cena']).replace(',','.'))
    
    val_czk = ks * m["price"] * rate
    total_val += val_czk
    
    processed.append({**r, "TC": m["price"], "Val": val_czk, "Zisk%": ((m["price"]-ref_b)/ref_b*100), 
                      "Div": m["div"]*ks*rate, "Earn": m["earn_dt"], "Days": m["days_to"], "History": m["history"]})
df_p = pd.DataFrame(processed)

# --- STRÁNKY ---
if page == "💰 Přehled":
    html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>Cena</th><th>CZK</th><th>Zisk %</th><th>Div</th><th>Earnings</th><th>Dní</th></tr></thead><tbody>"
    for _, r in df_p.iterrows():
        z_cls = "pos" if r["Zisk%"] >= 0 else "neg"
        w_cls = "warn" if str(r["Days"]).isdigit() and int(r["Days"]) <= 14 else ""
        html += f"<tr><td>{r['Název']}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num'>{format_cz(r['Val'], 0)}</td><td class='num {z_cls}'>{r['Zisk%']:.2f}%</td><td class='num'>{format_cz(r['Div'], 0)}</td><td>{r['Earn']}</td><td class='{w_cls}'>{r['Days']}</td></tr>"
    st.write(html + "</tbody></table>", unsafe_allow_html=True)

elif page == "🖼️ Grafika":
    fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Obor (Sektor)', 'Název'], values='Val')
    fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:,.0f} CZK<br>%{percentRoot:.1%}")
    st.plotly_chart(fig, use_container_width=True)

elif page == "📈 Výkonnost":
    # (Ponechána funkční verze)
    idx_t = st.radio("Index:", ["^GSPC", "^GDAXI"], horizontal=True)
    fig = go.Figure()
    idx_h = m_data[idx_t]["history"].tail(target_days)
    fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="Index", line=dict(dash='dash')))
    port_h = pd.Series(0.0, index=idx_h.index)
    for _, r in df_p.iterrows():
        h = r["History"].reindex(idx_h.index, method='ffill')
        if not h.empty: port_h += (h/h.iloc[0]-1)*100 * (r["Val"]/total_val)
    fig.add_trace(go.Scatter(x=port_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4)))
    st.plotly_chart(fig, use_container_width=True)
