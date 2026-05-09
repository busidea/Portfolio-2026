import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- 1. DEFINICE FUNKCÍ ---

def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    return {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

@st.cache_data(ttl=600)
def load_market_data(_tickers):
    data = {}
    today = datetime.now().date()
    ticker_list = list(_tickers)
    all_t = ticker_list + ["^GSPC", "^GDAXI"]
    
    # Progress bar pro uživatele
    progress_text = "Stahuji tržní data..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, t in enumerate(all_t):
        my_bar.progress((i + 1) / len(all_t), text=f"Stahuji: {t}")
        try:
            tk = yf.Ticker(t)
            # Zkusíme stáhnout historii za 2 roky (pro benchmark)
            h = tk.history(period="2y")
            
            if h.empty:
                data[t] = {"price": 0, "div": 0, "history": pd.Series(), "earn_dt": "-", "days_to": "-"}
                continue
            
            # Cena: Prioritně z 'currentPrice', jinak poslední z historie
            info = tk.info
            cp = info.get('currentPrice')
            if cp is None or cp == 0:
                cp = h['Close'].iloc[-1]
            
            # Dividenda
            dv = info.get('trailingAnnualDividendRate') or (info.get('dividendYield', 0) * cp) or 0
            
            # Earnings
            earn_dt, days_to = "-", "-"
            try:
                cal = tk.calendar
                if cal is not None and not cal.empty:
                    # Různé verze yfinance vrací kalendář různě
                    if isinstance(cal, pd.DataFrame):
                        e_date = cal.iloc[0, 0].date()
                    else:
                        e_date = cal.get('Earnings Date', [None])[0].date()
                    
                    if e_date >= today:
                        earn_dt = e_date.strftime('%d.%m.%Y')
                        days_to = (e_date - today).days
            except: pass

            data[t] = {"price": cp, "div": dv, "history": h['Close'], "earn_dt": earn_dt, "days_to": days_to}
        except Exception as e:
            data[t] = {"price": 0, "div": 0, "history": pd.Series(), "earn_dt": "-", "days_to": "-"}
            
    my_bar.empty()
    return data

# --- 2. STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main .block-container { padding-top: 2rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
    .portfolio-table th { background-color: #000; color: white; padding: 8px; text-align: right; position: sticky; top: 0; z-index: 10; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 6px 8px; border-bottom: 1px solid #dee2e6; line-height: 1.2; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .warn { background-color: #ffcccc; color: #cc0000 !important; font-weight: bold; text-align: center !important; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOADING ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL)
    # Čištění: Ticker nesmí být prázdný a musí to být string
    df_raw = df_raw.dropna(subset=['Ticker'])
    df_raw['Ticker'] = df_raw['Ticker'].astype(str).str.strip()
    
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        df_raw[col] = pd.to_numeric(df_raw[col].astype(str).str.replace(',','.').str.replace(' ',''), errors='coerce').fillna(0)
    
    fx = get_fx_rates()
    m_data = load_market_data(df_raw["Ticker"].unique())

    # --- 4. SIDEBAR ---
    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "🧠 Strategie", "📈 Výkonnost", "⚙️ Ostatní"])
    st.sidebar.divider()
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    time_frame = st.sidebar.selectbox("Srovnávací období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)
    
    days_map = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}
    target_days = days_map[time_frame]

    processed = []
    total_val, total_ref = 0, 0
    
    for _, r in df_raw.iterrows():
        t = r["Ticker"]
        m_cur = str(r["Měna"]).strip()
        info = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series(), "earn_dt": "-", "days_to": "-"})
        rate = fx.get(m_cur, 1.0)
        
        col_price = "Průměrná nákupní cena" if view_mode == "Standard" else "Nákupní cena včetně opcí"
        
        hist = info["history"]
        # Pokud máme historii, získáme cenu z minulosti, jinak nákupní cenu
        if len(hist) > target_days:
            ref_u = hist.iloc[-(target_days + 1)]
        else:
            ref_u = r[col_price]

        # Pokud Yahoo nevrátilo cenu (0), použijeme nákupní cenu, aby tabulka nebyla prázdná
        current_price = info["price"] if info["price"] > 0 else r[col_price]
        
        c_val_czk = r["Ks"] * current_price * rate
        r_val_czk = r["Ks"] * ref_u * rate
        total_val += c_val_czk
        total_ref += r_val_czk

        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"], "Měna": m_cur,
            "Ks": r["Ks"], "TC": current_price, "Hodnota CZK": c_val_czk,
            "Zisk %": ((current_price - ref_u) / ref_u * 100) if ref_u > 0 else 0,
            "Charakter": r["Charakter"], "Sentiment": r["Sentiment"],
            "Div_ks": info["div"], "Div_total": r["Ks"] * info["div"] * rate,
            "Earnings": info["earn_dt"], "DaysTo": info["days_to"], 
            "History": info["history"], "Rate": rate
        })
    df_p = pd.DataFrame(processed)

    # Sidebar Metriky
    st.sidebar.metric("Hodnota portfolia", f"{format_cz(total_val, 0)} CZK")
    diff_czk = total_val - total_ref
    diff_per = (diff_czk / total_ref * 100) if total_ref > 0 else 0
    st.sidebar.metric(f"Změna ({time_frame})", f"{format_cz(diff_czk, 0)} CZK", f"{diff_per:.2f} %")

    # --- 5. STRÁNKY (Zkráceno pro přehlednost, kód zůstává stejný jako dříve) ---
    if page == "💰 Přehled":
        st.write("### Aktuální pozice")
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th><th class='num'>Změna %</th><th class='num'>Div/ks</th><th class='num'>Div celkem</th><th>Earnings</th><th>Dní do</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            z_c = "pos" if r["Zisk %"] >= 0 else "neg"
            warn_style = " class='warn'" if (isinstance(r['DaysTo'], int) and r['DaysTo'] <= 7) else ""
            html += f"<tr><td><b>{r['Název']}</b></td><td class='num'>{r['Ks']:.0f}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num'><b>{format_cz(r['Hodnota CZK'], 0)}</b></td><td class='num {z_c}'>{r['Zisk %']:.2f} %</td><td class='num'>{format_cz(r['Div_ks'])}</td><td class='num'>{format_cz(r['Div_total'], 0)}</td><td>{r['Earnings']}</td><td{warn_style}>{r['DaysTo']}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)
    
    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor', 'Název'], values='Hodnota CZK', color='Sektor')
        fig.update_traces(textinfo="label+percent entry")
        st.plotly_chart(fig, use_container_width=True)

    elif page == "📈 Výkonnost":
        st.subheader("Benchmark: Srovnání vývoje (%)")
        idx_t = "^GSPC" if st.radio("Index:", ["S&P 500", "DAX 40"], horizontal=True) == "S&P 500" else "^GDAXI"
        if idx_t in m_data and not m_data[idx_t]["history"].empty:
            idx_h = m_data[idx_t]["history"].tail(target_days+1)
            idx_norm = (idx_h / idx_h.iloc[0] - 1) * 100
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=idx_norm.index, y=idx_norm, name="Index", line=dict(color='gray', dash='dash')))
            
            # Výpočet portfolia
            port_h = pd.Series(0.0, index=idx_h.index)
            for _, r in df_p.iterrows():
                if not r["History"].empty:
                    s = r["History"].reindex(idx_h.index, method='ffill')
                    if not s.empty and s.iloc[0] > 0:
                        port_h += (s / s.iloc[0] - 1) * 100 * (r["Hodnota CZK"] / total_val)
            fig.add_trace(go.Scatter(x=idx_h.index, y=port_h, name="Portfolio", line=dict(color='green', width=3)))
            st.plotly_chart(fig, use_container_width=True)

    elif page == "⚙️ Ostatní":
        df_m = df_p.copy()
        df_m.loc[df_m['Ticker'].isin(['GSK', 'NVO', 'VOW3.DE']), 'Měna'] = 'USD' # Jen příklad, uprav dle potřeby
        fig = px.sunburst(df_m, path=['Měna', 'Název'], values='Hodnota CZK', color='Měna',
                          color_discrete_map={'CZK': '#ADD8E6', 'EUR': '#00008B', 'USD': '#FF0000'})
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Kritická chyba: {e}")
