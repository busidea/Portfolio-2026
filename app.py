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
    for t in list(_tickers):
        symbol = str(t)
        if not symbol.startswith("^"):
            try:
                tk = yf.Ticker(symbol)
                cal = tk.calendar
                e_date = None
                if isinstance(cal, pd.DataFrame) and not cal.empty: e_date = cal.iloc[0, 0]
                elif isinstance(cal, dict): e_date = cal.get('Earnings Date', [None])[0]
                
                if e_date and hasattr(e_date, 'date'):
                    e_date = e_date.date()
                    if e_date >= today:
                        earnings_info[symbol] = {"date": e_date.strftime('%d.%m.%Y'), "days": (e_date - today).days}
                        continue
            except: pass
        earnings_info[symbol] = {"date": "-", "days": "-"}
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
            cp, dv = 0, 0
            if not raw_hist.empty:
                t_df = raw_hist[t].dropna(subset=['Close']) if len(all_symbols) > 1 else raw_hist.dropna(subset=['Close'])
                if not t_df.empty:
                    cp = t_df['Close'].iloc[-1]
                    if 'Dividends' in t_df.columns:
                        dv = t_df[t_df.index >= (datetime.now() - timedelta(days=365))]['Dividends'].sum()
            data[t] = {"price": cp, "div": dv}
        except: data[t] = {"price": 0, "div": 0}
    return data

# --- 2. STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 8px 10px; text-align: right; }
    .portfolio-table td { padding: 7px 10px; border-bottom: 1px solid #eee; }
    .ticker-name { font-weight: 700; }
    .num { text-align: right; font-family: 'Courier New', monospace; }
    .warn-cell { background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIKA A STRÁNKY ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    tickers = df_raw["Ticker"].unique()
    m_data = load_market_data(tickers)
    earn_data = get_earnings_data(tickers)
    fx = get_fx_rates()

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
    
    processed = []
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        info = m_data.get(t, {"price": 0, "div": 0})
        earn = earn_data.get(t, {"date": "-", "days": "-"})
        val_czk = float(str(r['Ks']).replace(',','.')) * info["price"] * fx.get(str(r["Měna"]).strip(), 1.0)
        processed.append({**r, **info, **earn, "Hodnota CZK": val_czk})
    df_p = pd.DataFrame(processed)

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>KS</th><th>Cena</th><th>Earnings</th><th>Dní</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            e_style = " class='warn-cell'" if (isinstance(r['days'], int) and r['days'] <= 14) else ""
            html += f"<tr><td><span class='ticker-name'>{r['Název']}</span></td><td class='num'>{r['Ks']}</td><td class='num'>{format_cz(r['price'])}</td><td>{r['date']}</td><td{e_style}>{r['days']}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)
    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=['Obor (Sektor)', 'Název'], values='Hodnota CZK')
        st.plotly_chart(fig, use_container_width=True)
    elif page == "📈 Výkonnost":
        st.subheader("Analýza výkonnosti")
        st.info("Sekce výkonnosti je připravena.")
    elif page == "⚙️ Ostatní":
        st.subheader("Rozložení dle měn")
        fig = px.sunburst(df_p, path=['Měna', 'Název'], values='Hodnota CZK', color='Měna')
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Chyba: {e}")
