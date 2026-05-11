import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- 1. TLAČÍTKO PRO REFRESH CACHE ---
if st.sidebar.button("🔄 Vynutit aktualizaci dat"):
    st.cache_data.clear()
    st.rerun()

# --- 2. DEFINICE FUNKCÍ ---

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
    all_t = list(_tickers) + ["^GSPC", "^GDAXI"]
    
    for t in all_t:
        try:
            tk = yf.Ticker(t)
            # Zkusíme kratší historii pro rychlejší načtení a menší šanci na ban
            h = tk.history(period="1y") 
            
            if h.empty:
                data[t] = {"price": 0, "div": 0, "history": pd.Series(dtype='float64'), "earn_dt": "-", "days_to": "-"}
                continue
            
            info = tk.info
            cp = info.get('currentPrice') or h['Close'].iloc[-1]
            dv = info.get('trailingAnnualDividendRate') or (info.get('dividendYield', 0) * cp) or 0
            
            earn_dt, days_to = "-", "-"
            try:
                cal = tk.calendar
                if cal is not None:
                    # Různé formáty kalendáře
                    e_date = None
                    if isinstance(cal, pd.DataFrame) and not cal.empty: e_date = cal.iloc[0, 0]
                    elif isinstance(cal, dict): e_date = cal.get('Earnings Date', [None])[0]
                    
                    if e_date and hasattr(e_date, 'date'):
                        e_date = e_date.date()
                        if e_date >= today:
                            earn_dt = e_date.strftime('%d.%m.%Y')
                            days_to = (e_date - today).days
            except: pass

            data[t] = {"price": cp, "div": dv, "history": h['Close'], "earn_dt": earn_dt, "days_to": days_to}
        except:
            data[t] = {"price": 0, "div": 0, "history": pd.Series(dtype='float64'), "earn_dt": "-", "days_to": "-"}
    return data

# --- 3. STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main .block-container { padding-top: 0.5rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .portfolio-table th { background-color: #000; color: white; padding: 8px; text-align: right; }
    .portfolio-table td { padding: 6px 8px; border-bottom: 1px solid #dee2e6; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 4. HLAVNÍ LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    fx = get_fx_rates()
    m_data = load_market_data(df_raw["Ticker"].unique())

    # Sidebar nastavení
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "🧠 Strategie", "📈 Výkonnost", "⚙️ Ostatní"])
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    time_frame = st.sidebar.selectbox("Období srovnání:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=1)
    
    days_map = {"1 rok": 250, "1 měsíc": 21, "1 týden": 5, "1 den": 1}
    target_days = days_map[time_frame]

    processed = []
    total_val, total_ref = 0, 0
    
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        m_cur = str(r["Měna"]).strip()
        info = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series(dtype='float64'), "earn_dt": "-", "days_to": "-"})
        rate = fx.get(m_cur, 1.0)
        
        ks = pd.to_numeric(str(r['Ks']).replace(',','.').replace(' ',''), errors='coerce') or 0
        p_std = pd.to_numeric(str(r['Průměrná nákupní cena']).replace(',','.').replace(' ',''), errors='coerce') or 0
        p_opt = pd.to_numeric(str(r['Nákupní cena včetně opcí']).replace(',','.').replace(' ',''), errors='coerce') or 0
        ref_buy = p_std if view_mode == "Standard" else p_opt
        
        hist = info["history"]
        curr_price = info["price"] if info["price"] > 0 else ref_buy
        
        # Bezpečný výpočet referenční ceny pro změnu %
        ref_price = ref_buy
        if not hist.empty and len(hist) > target_days:
            ref_price = hist.iloc[-(target_days + 1)]
        elif not hist.empty:
            ref_price = hist.iloc[0]

        val_czk = ks * curr_price * rate
        total_val += val_czk
        total_ref += (ks * ref_price * rate)

        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"], "Měna": m_cur,
            "Ks": ks, "TC": curr_price, "Hodnota CZK": val_czk,
            "Zisk %": ((curr_price - ref_price) / ref_price * 100) if ref_price > 0 else 0,
            "Div_total": ks * info["div"] * rate, "Earnings": info["earn_dt"], "DaysTo": info["days_to"], 
            "History": hist, "Charakter": r["Charakter"], "Sentiment": r["Sentiment"]
        })
    df_p = pd.DataFrame(processed)

    # Sidebar Metriky
    st.sidebar.divider()
    st.sidebar.metric("Portfolio", f"{format_cz(total_val, 0)} CZK")
    diff_czk = total_val - total_ref
    st.sidebar.metric(f"Změna ({time_frame})", f"{format_cz(diff_czk, 0)} CZK", f"{(diff_czk/total_ref*100 if total_ref>0 else 0):.2f} %")

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th class='num'>KS</th><th class='num'>Cena</th><th class='num'>Hodnota CZK</th><th class='num'>Změna %</th><th>Earnings</th><th>Dní</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            z_c = "pos" if r["Zisk %"] >= 0 else "neg"
            html += f"<tr><td><b>{r['Název']}</b></td><td class='num'>{r['Ks']:.0f}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num'><b>{format_cz(r['Hodnota CZK'], 0)}</b></td><td class='num {z_c}'>{r['Zisk %']:.2f} %</td><td>{r['Earnings']}</td><td>{r['DaysTo']}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "📈 Výkonnost":
        st.subheader("Srovnání vývoje (%)")
        idx_t = "^GSPC" # S&P 500 jako výchozí
        
        # Získání dat indexu s fallbackem
        idx_data = m_data.get(idx_t, {}).get("history", pd.Series(dtype='float64'))
        
        if not idx_data.empty:
            idx_h = idx_data.tail(target_days+1)
            idx_norm = (idx_h / idx_h.iloc[0] - 1) * 100
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=idx_norm.index, y=idx_norm, name="S&P 500", line=dict(color='gray', dash='dash')))
            
            # Výpočet portfolia
            port_h = pd.Series(0.0, index=idx_h.index)
            for _, r in df_p.iterrows():
                if not r["History"].empty:
                    s = r["History"].reindex(idx_h.index, method='ffill')
                    if not s.empty and s.iloc[0] > 0:
                        port_h += (s / s.iloc[0] - 1) * 100 * (r["Hodnota CZK"] / total_val)
            fig.add_trace(go.Scatter(x=idx_h.index, y=port_h, name="Portfolio", line=dict(color='green', width=3)))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Yahoo Finance momentálně neposkytuje data pro indexy. Zkuste tlačítko 'Vynutit aktualizaci' vlevo.")

    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor', 'Název'], values='Hodnota CZK', color='Sektor')
        fig.update_layout(height=800, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    elif page == "🧠 Strategie":
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df_p, x='Charakter', y='Hodnota CZK', color='Název', title="Dle Charakteru").update_layout(showlegend=False, height=700), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df_p, x='Sentiment', y='Hodnota CZK', color='Název', title="Dle Sentimentu").update_layout(showlegend=False, height=700), use_container_width=True)

    elif page == "⚙️ Ostatní":
        df_m = df_p.copy()
        # Oprava expozice
        for t_fix in ['NVO', 'GSK']:
            df_m.loc[df_m['Ticker'].str.contains(t_fix, case=False), 'Měna'] = 'USD'
        st.plotly_chart(px.sunburst(df_m, path=['Měna', 'Název'], values='Hodnota CZK', color='Měna', color_discrete_map={'CZK':'#ADD8E6','EUR':'#00008B','USD':'#FF0000'}).update_layout(height=700), use_container_width=True)

except Exception as e:
    st.error(f"Došlo k neočekávané chybě: {e}")
