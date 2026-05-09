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
    .block-container { padding-top: 2rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
    .portfolio-table th { background-color: #000; color: white; padding: 8px 10px; text-align: right; }
    .portfolio-table td { padding: 5px 10px; border-bottom: 1px solid #dee2e6; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- POMOCNÉ FUNKCE ---
def format_cz(value, decimals=2):
    try:
        return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
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

# --- DATA ---
try:
    df_sheet, market_info, historicals = load_full_data()
    fx = get_fx_rates()

    # SIDEBAR
    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("PŘEJÍT NA:", ["💰 Přehled", "📊 Grafy & Sektory", "🧠 Moje Strategie", "📅 Dividendy"])

    # Společná příprava dat pro grafy
    processed = []
    for _, r in df_sheet.iterrows():
        t = r["Ticker"]
        m = market_info.get(t, {})
        rate = fx.get(str(r["Měna"]).strip(), 1.0)
        
        val_czk = r["Ks"] * m["price"] * rate
        # Použijeme standardní nákupní cenu pro srovnání
        inv_czk = r["Ks"] * r["Průměrná nákupní cena"] * rate
        
        processed.append({
            "Název": "High Templar Tech" if t in ["QD", "HTT"] else r["Název"],
            "Ticker": t,
            "Sektor": r["Obor (Sektor)"],
            "Ks": r["Ks"],
            "TC": m["price"],
            "Hodnota CZK": val_czk,
            "Investice CZK": inv_czk,
            "Charakter": r["Charakter"] if "Charakter" in r else "Neuvedeno",
            "Sentiment": r["Sentiment"] if "Sentiment" in r else "Neuvedeno",
            "Dividenda": m["div"],
            "Div celkem CZK": r["Ks"] * m["div"] * rate,
            "Diff": m["diff"],
            "Nákupní cena": r["Průměrná nákupní cena"],
            "Nákupní cena opce": r["Nákupní cena včetně opcí"]
        })
    df_p = pd.DataFrame(processed)

    # --- STRÁNKA: PŘEHLED ---
    if page == "💰 Přehled":
        st.sidebar.divider()
        view_mode = st.sidebar.radio("Cena:", ["Standardní", "S opcemi"])
        time_frame = st.sidebar.selectbox("Změna:", ["Od počátku", "1 rok", "1 den"], index=2)
        
        col_price_key = "Nákupní cena" if view_mode == "Standardní" else "Nákupní cena opce"
        
        # Výpočet zisku pro tabulku
        for i, row in df_p.iterrows():
            h = historicals.get(row['Ticker'], pd.DataFrame())
            if time_frame == "1 den" and len(h) > 1: ref = h["Close"].iloc[-2]
            else: ref = row[col_price_key]
            df_p.at[i, 'Zisk %'] = ((row['TC'] - ref) / ref * 100) if ref != 0 else 0

        total_val = df_p["Hodnota CZK"].sum()
        total_inv = (df_p["Ks"] * df_p[col_price_key] * df_p["Ticker"].apply(lambda x: fx.get(df_sheet[df_sheet['Ticker']==x]['Měna'].values[0],1))).sum()
        
        st.sidebar.metric("Celková hodnota", format_cz(total_val, 0) + " CZK")
        st.sidebar.metric("Zisk/Ztráta", format_cz(total_val - total_inv, 0) + " CZK")

        html = "<table class='portfolio-table'><thead><tr><th>Název titulu</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th><th class='num'>Zisk %</th><th class='num'>Roční div. CZK</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            z_class = "pos" if r["Zisk %"] >= 0 else "neg"
            html += f"<tr><td class='stock-name'>{r['Název']}</td><td class='num'>{format_cz(r['Ks'], 0)}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td><td class='num {z_class}'>{format_cz(r['Zisk %'])} %</td><td class='num'>{format_cz(r['Div celkem CZK'], 0)}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    # --- STRÁNKA: GRAFY ---
    elif page == "📊 Grafy & Sektory":
        st.subheader("Vizuální mapa a srovnání hodnoty")
        
        # TreeMap s tučným zvýrazněním v hierarchii
        df_p["Sektor_Label"] = "<b>" + df_p["Sektor"].astype(str) + "</b>"
        fig_tree = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor_Label', 'Název'], values='Hodnota CZK', color='Sektor')
        st.plotly_chart(fig_tree, use_container_width=True)

        st.divider()
        st.subheader("Srovnání: Tržní hodnota vs. Investice (CZK)")
        # Sloupcový graf srovnání
        df_bar = df_p.melt(id_vars=['Název'], value_vars=['Hodnota CZK', 'Investice CZK'], var_name='Typ', value_name='Částka')
        fig_bar = px.bar(df_bar, x='Název', y='Částka', color='Typ', barmode='group', color_discrete_map={'Hodnota CZK': '#28a745', 'Investice CZK': '#6c757d'})
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- STRÁNKA: STRATEGIE ---
    elif page == "🧠 Moje Strategie":
        st.subheader("Charakter a Sentiment portfolia")
        c1, c2 = st.columns(2)
        
        with c1:
            st.write("### Charakter titulů")
            fig_char = px.pie(df_p, values='Hodnota CZK', names='Charakter', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_char, use_container_width=True)
            
        with c2:
            st.write("### Můj Sentiment")
            fig_sent = px.pie(df_p, values='Hodnota CZK', names='Sentiment', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_sent, use_container_width=True)

except Exception as e:
    st.error(f"Chyba při zpracování: {e}")
