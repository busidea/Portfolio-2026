import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- KONFIGURACE ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main .block-container { padding-top: 2.5rem !important; padding-bottom: 1rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
    .portfolio-table th { background-color: #000; color: white; padding: 8px; text-align: right; position: sticky; top: 0; z-index: 10; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 5px 8px; border-bottom: 1px solid #dee2e6; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    rates = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
    for c, t in {"EUR":"EURCZK=X", "USD":"USDCZK=X"}.items():
        try:
            d = yf.Ticker(t).history(period="1d")
            if not d.empty: rates[c] = d['Close'].iloc[-1]
        except: pass
    return rates

@st.cache_data(ttl=300)
def load_data_and_indices(tickers):
    market_data, historicals = {}, {}
    # Přidáme indexy pro srovnání
    all_tickers = tickers + ["^GSPC", "^GDAXI"] 
    for t in all_tickers:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="1y")
            if not h.empty:
                market_data[t] = {"price": h['Close'].iloc[-1], "diff": (h['Close'].iloc[-1] - h['Close'].iloc[-2]) if len(h)>1 else 0}
                historicals[t] = h
        except: pass
    return market_data, historicals

try:
    df_sheet = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',','.').str.replace(' ',''), errors='coerce').fillna(0)
    
    fx = get_fx_rates()
    market_info, historicals = load_data_and_indices(df_sheet["Ticker"].unique().tolist())

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("PŘEJÍT NA:", ["💰 Přehled", "📊 Grafy & Sektory", "🧠 Strategie", "📈 Výkonnost"])

    # Příprava dat
    processed = []
    for _, r in df_sheet.iterrows():
        t, m_cur = r["Ticker"], r["Měna"]
        m = market_info.get(t, {"price": 0, "diff": 0})
        rate = fx.get(str(m_cur).strip(), 1.0)
        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"], "Měna": m_cur,
            "Ks": r["Ks"], "TC": m["price"], "Hodnota CZK": r["Ks"] * m["price"] * rate,
            "Charakter": r["Charakter"], "Sentiment": r["Sentiment"],
            "Diff": m["diff"], "Standard": r["Průměrná nákupní cena"], "Opce": r["Nákupní cena včetně opcí"],
            "Rate": rate, "Investice CZK": r["Ks"] * r["Průměrná nákupní cena"] * rate
        })
    df_p = pd.DataFrame(processed)

    # --- SIDEBAR OVLÁDÁNÍ ---
    st.sidebar.divider()
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    time_frame = st.sidebar.selectbox("Období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"], index=4)
    col_price = "Standard" if view_mode == "Standard" else "Opce"

    # Výpočty výkonnosti
    total_val, total_ref = 0, 0
    for i, row in df_p.iterrows():
        h = historicals.get(row['Ticker'], pd.DataFrame())
        if time_frame == "1 den" and len(h)>1: ref_u = h["Close"].iloc[-2]
        elif time_frame == "1 týden" and len(h)>5: ref_u = h["Close"].iloc[-5]
        elif time_frame == "1 měsíc" and len(h)>21: ref_u = h["Close"].iloc[-21]
        elif time_frame == "1 rok" and len(h)>0: ref_u = h["Close"].iloc[0]
        else: ref_u = row[col_price]
        df_p.at[i, 'Zisk %'] = ((row['TC'] - ref_u) / ref_u * 100) if ref_u != 0 else 0
        total_val += row['Hodnota CZK']; total_ref += (row['Ks'] * ref_u * row['Rate'])

    port_perf = ((total_val - total_ref) / total_ref * 100) if total_ref != 0 else 0
    st.sidebar.metric("Celková hodnota", format_cz(total_val, 0) + " CZK")
    st.sidebar.metric(f"Změna ({time_frame})", format_cz(total_val - total_ref, 0) + " CZK", f"{port_perf:.2f} %")

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název titulu</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th><th class='num'>Zisk %</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            z_c, c_c = ("pos" if r["Zisk %"] >= 0 else "neg"), ("pos" if r["Diff"] >= 0 else "neg")
            html += f"<tr><td class='stock-name'>{r['Název']}</td><td class='num'>{format_cz(r['Ks'], 0)}</td><td class='num {c_c}'>{format_cz(r['TC'])}</td><td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td><td class='num {z_c}'>{format_cz(r['Zisk %'])} %</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "📊 Grafy & Sektory":
        c1, c2 = st.columns([2, 1])
        with c1:
            fig_tree = px.treemap(df_p, path=[px.Constant("Sektory"), 'Sektor', 'Název'], values='Hodnota CZK', color='Sektor')
            fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=450)
            st.plotly_chart(fig_tree, use_container_width=True)
        with c2:
            fig_curr = px.sunburst(df_p, path=['Měna', 'Název'], values='Hodnota CZK', color='Měna', title="Rozdělení dle měn")
            fig_curr.update_layout(margin=dict(t=30, l=0, r=0, b=0), height=450)
            st.plotly_chart(fig_curr, use_container_width=True)

    elif page == "🧠 Strategie":
        c1, c2 = st.columns(2)
        for col, field, title in zip([c1, c2], ['Charakter', 'Sentiment'], ["Dle Charakteru", "Dle Sentimentu"]):
            with col:
                fig = px.bar(df_p, x=field, y='Hodnota CZK', color='Název', title=title, barmode='stack', text='Název')
                fig.update_layout(showlegend=False, height=500)
                st.plotly_chart(fig, use_container_width=True)

    elif page == "📈 Výkonnost":
        # 1. Srovnání Investice vs Hodnota (přesunuto sem)
        df_melt = df_p.melt(id_vars=['Název'], value_vars=['Hodnota CZK', 'Investice CZK'], var_name='Typ', value_name='CZK')
        fig_bar = px.bar(df_melt, x='Název', y='CZK', color='Typ', barmode='group', color_discrete_map={'Hodnota CZK':'#28a745','Investice CZK':'#dc3545'})
        fig_bar.update_layout(title="Srovnání: Pořízení vs Současnost", legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig_bar, use_container_width=True)

        # 2. Srovnání s Indexy
        st.divider()
        st.subheader(f"Benchmark: Portfolio vs Indexy ({time_frame})")
        
        def get_idx_perf(ticker):
            h = historicals.get(ticker, pd.DataFrame())
            if h.empty: return 0
            curr = h['Close'].iloc[-1]
            if time_frame == "1 den" and len(h)>1: ref = h['Close'].iloc[-2]
            elif time_frame == "1 týden" and len(h)>5: ref = h['Close'].iloc[-5]
            elif time_frame == "1 měsíc" and len(h)>21: ref = h['Close'].iloc[-21]
            elif time_frame == "1 rok": ref = h['Close'].iloc[0]
            else: ref = h['Close'].iloc[0] # Pro "Od počátku" bereme u indexů začátek roku
            return ((curr - ref) / ref * 100)

        bench_data = {
            "Subjekt": ["Moje Portfolio", "S&P 500 (USA)", "DAX 40 (GER)"],
            "Výkon v %": [port_perf, get_idx_perf("^GSPC"), get_idx_perf("^GDAXI")]
        }
        fig_bench = px.bar(bench_data, x='Subjekt', y='Výkon v %', color='Subjekt', text_auto='.2f')
        fig_bench.update_layout(showlegend=False)
        st.plotly_chart(fig_bench, use_container_width=True)

except Exception as e:
    st.error(f"Chyba: {e}")
