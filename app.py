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
    all_symbols = [str(t).strip() for t in _tickers if str(t).strip()]
    all_symbols += ["^GSPC", "^GDAXI"]
    
    # Hromadný download historie
    try:
        raw_hist = yf.download(all_symbols, period="2y", interval="1d", group_by='ticker', progress=False)
    except:
        raw_hist = pd.DataFrame()

    for t in all_symbols:
        try:
            cp, dv, hist = 0, 0, pd.Series()
            earn_dt, days_to = "-", "-"
            
            # 1. Získání ceny a historie
            if not raw_hist.empty:
                try:
                    h_df = raw_hist[t].dropna(subset=['Close']) if len(all_symbols) > 1 else raw_hist.dropna(subset=['Close'])
                    if not h_df.empty:
                        cp = h_df['Close'].iloc[-1]
                        hist = h_df['Close']
                except: pass

            if cp == 0:
                tk_obj = yf.Ticker(t)
                cp = tk_obj.fast_info.get('last_price', 0)

            # 2. Získání Dividend a Earnings (vyžaduje Ticker objekt)
            if not t.startswith("^"):
                tk = yf.Ticker(t)
                # Zkusíme vytáhnout dividendu (trailingAnnualDividendRate je nejjistější)
                try:
                    inf = tk.info
                    dv = inf.get('trailingAnnualDividendRate') or inf.get('dividendRate') or 0
                except: dv = 0
                
                # Earnings
                try:
                    cal = tk.calendar
                    if cal is not None and not (isinstance(cal, list) and len(cal) == 0):
                        e_date = None
                        if isinstance(cal, pd.DataFrame) and not cal.empty: e_date = cal.iloc[0, 0]
                        elif isinstance(cal, dict): e_date = cal.get('Earnings Date', [None])[0]
                        
                        if e_date and hasattr(e_date, 'date'):
                            e_date = e_date.date()
                            if e_date >= today:
                                earn_dt = e_date.strftime('%d.%m.%Y')
                                days_to = (e_date - today).days
                except: pass

            data[t] = {"price": cp, "div": dv, "history": hist, "earn_dt": earn_dt, "days_to": days_to}
        except:
            data[t] = {"price": 0, "div": 0, "history": pd.Series(), "earn_dt": "-", "days_to": "-"}
    return data

# --- 2. STYLY (Vylepšená vizualizace) ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main .block-container { padding-top: 0.5rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
    .portfolio-table th { background-color: #1e1e1e; color: #ffffff; padding: 10px; text-align: right; position: sticky; top: 0; }
    .portfolio-table th:first-child { text-align: left; }
    .portfolio-table td { padding: 8px; border-bottom: 1px solid #eee; }
    .ticker-name { color: #1565C0; font-weight: 800; font-size: 14px; } /* Vylepšený název */
    .num { text-align: right; font-family: 'Roboto Mono', monospace; }
    .pos-row { background-color: #f8fff9; } /* Velmi jemný zelený nádech pro ziskové */
    .neg-row { background-color: #fffaf9; } /* Velmi jemný červený nádech pro ztrátové */
    .pos-text { color: #2e7d32; font-weight: bold; }
    .neg-text { color: #d32f2f; font-weight: bold; }
    .warn-cell { background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOADING ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    fx = get_fx_rates()
    m_data = load_market_data(df_raw["Ticker"].unique())

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
        info = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series(), "earn_dt": "-", "days_to": "-"})
        rate = fx.get(m_cur, 1.0)
        
        ks = pd.to_numeric(str(r['Ks']).replace(',','.').replace(' ',''), errors='coerce') or 0
        ref_buy = pd.to_numeric(str(r['Průměrná nákupní cena']).replace(',','.').replace(' ',''), errors='coerce') if view_mode == "Standard" else pd.to_numeric(str(r['Nákupní cena včetně opcí']).replace(',','.').replace(' ',''), errors='coerce')
        
        hist = info["history"]
        ref_price = ref_buy
        if not hist.empty:
            ref_price = hist.iloc[-(target_days + 1)] if len(hist) > target_days else hist.iloc[0]
        
        curr_price = info["price"] if info["price"] > 0 else ref_buy
        val_czk = ks * curr_price * rate
        total_val += val_czk
        total_ref += (ks * ref_price * rate)

        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"], "Měna": m_cur,
            "Ks": ks, "TC": curr_price, "Hodnota CZK": val_czk,
            "Zisk %": ((curr_price - ref_price) / ref_price * 100) if ref_price > 0 else 0,
            "Charakter": r["Charakter"], "Sentiment": r["Sentiment"],
            "Div_ks": info["div"], "Div_total": ks * info["div"] * rate,
            "Earnings": info["earn_dt"], "DaysTo": info["days_to"], "History": hist
        })
    df_p = pd.DataFrame(processed)

    st.sidebar.divider()
    st.sidebar.metric("Portfolio", f"{format_cz(total_val, 0)} CZK")
    diff_czk = total_val - total_ref
    st.sidebar.metric(f"Změna ({time_frame})", f"{format_cz(diff_czk, 0)} CZK", f"{(diff_czk/total_ref*100 if total_ref>0 else 0):.2f} %")

    # --- STRÁNKY ---
    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th class='num'>KS</th><th class='num'>Cena</th><th class='num'>Hodnota CZK</th><th class='num'>Změna %</th><th class='num'>Div/ks</th><th class='num'>Div celkem</th><th>Earnings</th><th>Dní do</th></tr></thead><tbody>"
        
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            row_class = "pos-row" if r["Zisk %"] >= 0 else "neg-row"
            text_class = "pos-text" if r["Zisk %"] >= 0 else "neg-text"
            warn_class = " class='warn-cell'" if (isinstance(r['DaysTo'], int) and r['DaysTo'] <= 7) else ""
            
            html += f"""<tr class='{row_class}'>
                <td><span class='ticker-name'>{r['Název']}</span><br><small style='color:gray'>{r['Ticker']}</small></td>
                <td class='num'>{r['Ks']:.0f}</td>
                <td class='num'>{format_cz(r['TC'])}</td>
                <td class='num'><b>{format_cz(r['Hodnota CZK'], 0)}</b></td>
                <td class='num {text_class}'>{r['Zisk %']:.2f} %</td>
                <td class='num'>{format_cz(r['Div_ks'])}</td>
                <td class='num'>{format_cz(r['Div_total'], 0)}</td>
                <td style='text-align:center'>{r['Earnings']}</td>
                <td{warn_class}>{r['DaysTo']}</td>
            </tr>"""
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor', 'Název'], values='Hodnota CZK', color='Sektor')
        fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=800)
        st.plotly_chart(fig, use_container_width=True)

    elif page == "🧠 Strategie":
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df_p, x='Charakter', y='Hodnota CZK', color='Název', title="Dle Charakteru").update_layout(showlegend=False, height=750), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df_p, x='Sentiment', y='Hodnota CZK', color='Název', title="Dle Sentimentu").update_layout(showlegend=False, height=750), use_container_width=True)

    elif page == "📈 Výkonnost":
        st.subheader("Benchmark")
        idx_t = "^GSPC" if st.radio("Index:", ["S&P 500", "DAX 40"], horizontal=True) == "S&P 500" else "^GDAXI"
        if idx_t in m_data and not m_data[idx_t]["history"].empty:
            idx_h = m_data[idx_t]["history"].tail(target_days+1)
            idx_norm = (idx_h / idx_h.iloc[0] - 1) * 100
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=idx_norm.index, y=idx_norm, name="Index", line=dict(color='gray', dash='dash')))
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
        for t_fix in ['NVO', 'GSK']:
            df_m.loc[df_m['Ticker'].str.contains(t_fix, case=False, na=False), 'Měna'] = 'USD'
        st.plotly_chart(px.sunburst(df_m, path=['Měna', 'Název'], values='Hodnota CZK', color='Měna', color_discrete_map={'CZK':'#ADD8E6','EUR':'#00008B','USD':'#FF0000'}).update_layout(height=700), use_container_width=True)

except Exception as e:
    st.error(f"Kritická chyba: {e}")
