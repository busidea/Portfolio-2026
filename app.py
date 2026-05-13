import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

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
    [data-testid="stSidebarNav"] { display: none; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 10px; text-align: right; }
    .portfolio-table td { padding: 8px; border-bottom: 1px solid #ddd; }
    .num { text-align: right; font-family: monospace; }
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
    total_val = 0
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        info = m_data.get(t, {"price": 0, "history": pd.Series()})
        earn = earn_data.get(t, {"date": "-", "days": "-"})
        val_czk = float(str(r['Ks']).replace(',','.')) * info["price"] * fx.get(str(r["Měna"]).strip(), 1.0)
        total_val += val_czk
        processed.append({**r, **info, **earn, "Hodnota CZK": val_czk})
    df_p = pd.DataFrame(processed)

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th>KS</th><th>Cena</th><th>Earnings</th><th>Dní</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            e_style = " class='warn-cell'" if (isinstance(r['days'], int) and r['days'] <= 14) else ""
            html += f"<tr><td>{r['Název']}</td><td class='num'>{r['Ks']}</td><td class='num'>{format_cz(r['price'])}</td><td>{r['date']}</td><td{e_style}>{r['days']}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)
    
    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=['Obor (Sektor)', 'Název'], values='Hodnota CZK')
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:,.0f} CZK<br>%{percentParent:.1%}")
        st.plotly_chart(fig, use_container_width=True)
    
    elif page == "📈 Výkonnost":
        st.subheader("Analýza výkonnosti")
        selected = st.multiselect("Vyberte tituly:", df_p["Název"].tolist())
        # Zpětná implementace výkonnosti
        idx_h = m_data["^GSPC"]["history"].tail(21)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="S&P 500"))
        for title in selected:
            h = df_p[df_p["Název"]==title].iloc[0]["history"].tail(21)
            fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=title))
        st.plotly_chart(fig, use_container_width=True)
    
    elif page == "⚙️ Ostatní":
        st.subheader("Rozložení měn")
        st.plotly_chart(px.sunburst(df_p, path=['Měna', 'Název'], values='Hodnota CZK'))

except Exception as e:
    st.error(f"Chyba: {e}")
