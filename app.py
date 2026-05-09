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
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
    .portfolio-table th { background-color: #000; color: white; padding: 6px 10px; text-align: right; border: 1px solid #333; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 4px 10px; border-bottom: 1px solid #dee2e6; line-height: 1.2; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; color: #000; }
</style>
""", unsafe_allow_html=True)

def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    rates = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
    for c, t in {"EUR":"EURCZK=X", "USD":"USDCZK=X", "GBP":"GBPCZK=X", "DKK":"DKKCZK=X"}.items():
        try:
            d = yf.Ticker(t).history(period="1d")
            if not d.empty: rates[c] = d['Close'].iloc[-1]
        except: pass
    return rates

@st.cache_data(ttl=300)
def load_full_data():
    df = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',','.').str.replace(' ',''), errors='coerce').fillna(0)
    
    tickers = df["Ticker"].unique().tolist()
    market_data, historicals = {}, {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="1y")
            market_data[t] = {
                "price": tk.info.get('currentPrice') or (h['Close'].iloc[-1] if not h.empty else 0),
                "div": tk.info.get('trailingAnnualDividendRate') or (tk.info.get('dividendYield', 0) * (tk.info.get('currentPrice', 0))),
                "diff": (h['Close'].iloc[-1] - h['Close'].iloc[-2]) if len(h) > 1 else 0
            }
            historicals[t] = h
        except: market_data[t] = {"price": 0, "div": 0, "diff": 0}
    return df, market_data, historicals

try:
    df_sheet, market_info, historicals = load_full_data()
    fx = get_fx_rates()

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("PŘEJÍT NA:", ["💰 Přehled", "📊 Grafy & Sektory", "🧠 Strategie", "📅 Dividendy"])

    # Příprava základních dat
    processed = []
    for _, r in df_sheet.iterrows():
        t = r["Ticker"]
        m = market_info.get(t, {})
        rate = fx.get(str(r["Měna"]).strip(), 1.0)
        processed.append({
            "Název": "High Templar Tech" if t in ["QD", "HTT"] else r["Název"],
            "Ticker": t, "Sektor": r["Obor (Sektor)"], "Ks": r["Ks"], "TC": m["price"],
            "Hodnota CZK": r["Ks"] * m["price"] * rate,
            "Charakter": r["Charakter"] if "Charakter" in r else "Value",
            "Sentiment": r["Sentiment"] if "Sentiment" in r else "Neutrální",
            "Div celkem CZK": r["Ks"] * m["div"] * rate, "Diff": m["diff"],
            "Standard": r["Průměrná nákupní cena"], "Opce": r["Nákupní cena včetně opcí"],
            "Rate": rate
        })
    df_p = pd.DataFrame(processed)

    if page == "💰 Přehled":
        st.sidebar.divider()
        view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
        time_frame = st.sidebar.selectbox("Období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"], index=4)
        
        col_price = "Standard" if view_mode == "Standard" else "Opce"
        
        # Dynamické výpočty
        total_current = 0
        total_reference = 0
        
        for i, row in df_p.iterrows():
            h = historicals.get(row['Ticker'], pd.DataFrame())
            if time_frame == "1 den" and len(h) > 1: ref_unit = h["Close"].iloc[-2]
            elif time_frame == "1 týden" and len(h) > 5: ref_unit = h["Close"].iloc[-5]
            elif time_frame == "1 měsíc" and len(h) > 21: ref_unit = h["Close"].iloc[-21]
            elif time_frame == "1 rok" and len(h) > 0: ref_unit = h["Close"].iloc[0]
            else: ref_unit = row[col_price]
            
            df_p.at[i, 'Zisk %'] = ((row['TC'] - ref_unit) / ref_unit * 100) if ref_unit != 0 else 0
            total_current += row['Hodnota CZK']
            total_reference += (row['Ks'] * ref_unit * row['Rate'])

        st.sidebar.metric("Celková hodnota", format_cz(total_current, 0) + " CZK")
        st.sidebar.metric(f"Zisk/Ztráta ({time_frame})", format_cz(total_current - total_reference, 0) + " CZK", delta_color="normal")

        html = "<table class='portfolio-table'><thead><tr><th>Název titulu</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th><th class='num'>Zisk %</th><th class='num'>Roční div. CZK</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            z_class = "pos" if r["Zisk %"] >= 0 else "neg"
            c_class = "pos" if r["Diff"] >= 0 else "neg"
            html += f"<tr><td class='stock-name'>{r['Název']}</td><td class='num'>{format_cz(r['Ks'], 0)}</td><td class='num {c_class}'>{format_cz(r['TC'])}</td><td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td><td class='num {z_class}'>{format_cz(r['Zisk %'])} %</td><td class='num'>{format_cz(r['Div celkem CZK'], 0)}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "📊 Grafy & Sektory":
        df_p["Sektor_Label"] = "<b>" + df_p["Sektor"].astype(str) + "</b>"
        # TreeMap s %
        fig_tree = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor_Label', 'Název'], values='Hodnota CZK', color='Sektor')
        fig_tree.update_traces(textinfo="label+percent parent")
        fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=350)
        st.plotly_chart(fig_tree, use_container_width=True)

        # Bar graf s červenou investicí
        df_bar = df_p.copy()
        df_bar["Investice CZK"] = df_bar["Ks"] * df_bar["Standard"] * df_bar["Rate"]
        df_melt = df_bar.melt(id_vars=['Název'], value_vars=['Hodnota CZK', 'Investice CZK'], var_name='Typ', value_name='CZK')
        fig_bar = px.bar(df_melt, x='Název', y='CZK', color='Typ', barmode='group', color_discrete_map={'Hodnota CZK': '#28a745', 'Investice CZK': '#dc3545'})
        fig_bar.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=350, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5))
        st.plotly_chart(fig_bar, use_container_width=True)

    elif page == "🧠 Strategie":
        c1, c2 = st.columns(2)
        with c1:
            fig1 = px.sunburst(df_p, path=['Charakter', 'Název'], values='Hodnota CZK', color='Charakter', color_discrete_sequence=px.colors.qualitative.Pastel)
            fig1.update_layout(title_text="Charakter -> Tituly", margin=dict(t=30, l=0, r=0, b=0))
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            fig2 = px.sunburst(df_p, path=['Sentiment', 'Název'], values='Hodnota CZK', color='Sentiment', color_discrete_sequence=px.colors.qualitative.Safe)
            fig2.update_layout(title_text="Sentiment -> Tituly", margin=dict(t=30, l=0, r=0, b=0))
            st.plotly_chart(fig2, use_container_width=True)

except Exception as e:
    st.error(f"Chyba: {e}")
