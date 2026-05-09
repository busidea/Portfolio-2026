import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- 1. DEFINICE FUNKCÍ (Musí být jako první!) ---

def format_cz(value, decimals=2):
    try:
        return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except:
        return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    # Fixní kurzy pro stabilitu, lze přepnout na live přes yfinance
    return {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

@st.cache_data(ttl=300)
def load_market_data(tickers):
    data = {}
    all_t = list(tickers) + ["^GSPC", "^GDAXI"]
    for t in all_t:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="1y")
            if h.empty: continue
            
            info = tk.info
            cp = info.get('currentPrice') or h['Close'].iloc[-1]
            dv = info.get('trailingAnnualDividendRate') or (info.get('dividendYield', 0) * cp) or 0
            
            earn = "-"
            if 'earningsTimestamp' in info and info['earningsTimestamp']:
                earn = pd.to_datetime(info['earningsTimestamp'], unit='s').strftime('%d.%m.%Y')
            elif tk.calendar is not None and hasattr(tk.calendar, 'iloc') and not tk.calendar.empty:
                earn = tk.calendar.iloc[0,0].strftime('%d.%m.%Y')

            data[t] = {"price": cp, "div": dv, "history": h['Close'], "earnings": earn}
        except:
            data[t] = {"price": 0, "div": 0, "history": pd.Series(), "earnings": "-"}
    return data

# --- 2. STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main .block-container { padding-top: 2.5rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
    .portfolio-table th { background-color: #000; color: white; padding: 8px; text-align: right; position: sticky; top: 0; z-index: 10; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 6px 8px; border-bottom: 1px solid #dee2e6; line-height: 1.2; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOADING ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        df_raw[col] = pd.to_numeric(df_raw[col].astype(str).str.replace(',','.').str.replace(' ',''), errors='coerce').fillna(0)
    
    fx = get_fx_rates()
    m_data = load_market_data(df_raw["Ticker"].unique())

    # --- 4. SIDEBAR ---
    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "🧠 Strategie", "📈 Výkonnost", "⚙️ Ostatní"])
    st.sidebar.divider()
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    time_frame = st.sidebar.selectbox("Srovnávací období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=3)
    
    days_map = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}
    days = days_map[time_frame]

    processed = []
    total_val, total_ref = 0, 0
    
    for _, r in df_raw.iterrows():
        t, m_cur = r["Ticker"], str(r["Měna"]).strip()
        info = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series(), "earnings": "-"})
        rate = fx.get(m_cur, 1.0)
        
        col_price = "Průměrná nákupní cena" if view_mode == "Standard" else "Nákupní cena včetně opcí"
        ref_u = info["history"].iloc[-days-1] if len(info["history"]) > days else r[col_price]
        
        c_val_czk = r["Ks"] * info["price"] * rate
        r_val_czk = r["Ks"] * ref_u * rate
        
        total_val += c_val_czk
        total_ref += r_val_czk

        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"], "Měna": m_cur,
            "Ks": r["Ks"], "TC": info["price"], "Hodnota CZK": c_val_czk,
            "Zisk %": ((info["price"] - ref_u) / ref_u * 100) if ref_u > 0 else 0,
            "Charakter": r["Charakter"], "Sentiment": r["Sentiment"],
            "Div_ks": info["div"], "Div_total": r["Ks"] * info["div"] * rate,
            "Earnings": info["earnings"], "History": info["history"], "Rate": rate
        })
    df_p = pd.DataFrame(processed)

    # Sidebar Metriky
    st.sidebar.metric("Hodnota portfolia", f"{format_cz(total_val, 0)} CZK")
    diff_czk = total_val - total_ref
    diff_per = (diff_czk / total_ref * 100) if total_ref > 0 else 0
    st.sidebar.metric(f"Změna ({time_frame})", f"{format_cz(diff_czk, 0)} CZK", f"{diff_per:.2f} %")

    # --- 5. STRÁNKY ---

    if page == "💰 Přehled":
        st.write("### Aktuální pozice")
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th><th class='num'>Změna %</th><th class='num'>Div/ks</th><th class='num'>Div celkem</th><th>Earnings</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            z_c = "pos" if r["Zisk %"] >= 0 else "neg"
            html += f"<tr><td class='stock-name'>{r['Název']}</td><td class='num'>{r['Ks']:.0f}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td><td class='num {z_c}'>{r['Zisk %']:.2f} %</td><td class='num'>{format_cz(r['Div_ks'])}</td><td class='num'>{format_cz(r['Div_total'], 0)}</td><td>{r['Earnings']}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor', 'Název'], values='Hodnota CZK', color='Sektor')
        fig.update_traces(textinfo="label+percent entry")
        fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=650)
        st.plotly_chart(fig, use_container_width=True)

    elif page == "🧠 Strategie":
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.bar(df_p, x='Charakter', y='Hodnota CZK', color='Název', barmode='stack', text='Název', title="Dle Charakteru")
            fig1.update_layout(showlegend=False, height=700)
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            fig2 = px.bar(df_p, x='Sentiment', y='Hodnota CZK', color='Název', barmode='stack', text='Název', title="Dle Sentimentu")
            fig2.update_layout(showlegend=False, height=700)
            st.plotly_chart(fig2, use_container_width=True)

    elif page == "📈 Výkonnost":
        st.subheader("Benchmark: Srovnání vývoje (%)")
        col1, col2 = st.columns([1, 3])
        with col1:
            index_choice = st.radio("Index:", ["S&P 500", "DAX 40"])
            target = st.selectbox("Srovnat s:", ["Celé Portfolio"] + df_p["Název"].tolist())
        
        idx_t = "^GSPC" if index_choice == "S&P 500" else "^GDAXI"
        idx_h = m_data[idx_t]["history"].tail(days+1)
        idx_norm = (idx_h / idx_h.iloc[0] - 1) * 100
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=idx_norm.index, y=idx_norm, name=index_choice, line=dict(color='gray', dash='dash')))
        
        if target == "Celé Portfolio":
            port_h = pd.Series(0.0, index=idx_h.index)
            for _, r in df_p.iterrows():
                if not r["History"].empty:
                    s = r["History"].tail(days+1).reindex(idx_h.index, method='ffill')
                    port_h += (s / s.iloc[0] - 1) * 100 * (r["Hodnota CZK"] / total_val)
            fig.add_trace(go.Scatter(x=idx_h.index, y=port_h, name="Portfolio", line=dict(color='green', width=3)))
        else:
            hist = df_p[df_p["Název"]==target].iloc[0]["History"].tail(days+1).reindex(idx_h.index, method='ffill')
            y_data = (hist / hist.iloc[0] - 1) * 100
            fig.add_trace(go.Scatter(x=idx_h.index, y=y_data, name=target, line=dict(color='blue', width=3)))
        
        fig.update_layout(height=500, margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)

    elif page == "⚙️ Ostatní":
        st.subheader("Měnová expozice")
        df_m = df_p.copy()
        # Korekce měn
        df_m.loc[df_m['Ticker'].isin(['GSK', 'NVO']), 'Měna'] = 'USD'
        df_m.loc[df_m['Název'].str.contains('Volkswagen', case=False), 'Měna'] = 'CZK'
        
        fig = px.sunburst(df_m, path=['Měna', 'Název'], values='Hodnota CZK', 
                          color='Měna',
                          color_discrete_map={'CZK': '#ADD8E6', 'EUR': '#00008B', 'USD': '#FF0000'})
        fig.update_layout(height=650)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Chyba v aplikaci: {e}")
