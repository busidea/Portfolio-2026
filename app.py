import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px  # Knihovna pro hezké grafy

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- KONFIGURACE ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- STYLOVÁNÍ ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; } /* Schováme výchozí menu */
    .block-container { padding-top: 2rem; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .portfolio-table th { background-color: #000; color: white; padding: 8px; text-align: right; }
    .portfolio-table td { padding: 5px 10px; border-bottom: 1px solid #eee; }
    .num { text-align: right; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- FUNKCE PRO DATA ---
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
def load_data():
    df = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',','.').str.replace(' ',''), errors='coerce').fillna(0)
    
    market_info = {}
    for t in df["Ticker"].unique():
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            cp = inf.get('currentPrice', 0)
            market_info[t] = {
                "price": cp,
                "div": inf.get('trailingAnnualDividendRate', 0),
                "name": inf.get('longName', t)
            }
        except: market_info[t] = {"price":0, "div":0, "name":t}
    return df, market_info

# --- NAVIGACE V SIDEBARU ---
st.sidebar.title("💎 PORTFÓLIO")
page = st.sidebar.radio("PŘEJÍT NA:", ["💰 Přehled", "📊 Grafy & Sektory", "📅 Dividendy", "🚀 Vývoj"])

try:
    df_sheet, market_info = load_data()
    fx = get_fx_rates()

    # Příprava dat pro obě stránky
    processed = []
    for _, r in df_sheet.iterrows():
        t = r["Ticker"]
        m = market_info.get(t, {})
        rate = fx.get(r["Měna"], 1.0)
        
        # Výpočty
        val_czk = r["Ks"] * m["price"] * rate
        name = "High Templar Tech" if t in ["QD", "HTT"] else r["Název"]
        
        processed.append({
            "Název": name,
            "Sektor": r["Obor (Sektor)"] if "Obor (Sektor)" in r else "Neuvedeno",
            "Ks": r["Ks"],
            "TC": m["price"],
            "Hodnota CZK": val_czk,
            "Zisk %": ((m["price"] - r["Průměrná nákupní cena"]) / r["Průměrná nákupní cena"] * 100) if r["Průměrná nákupní cena"] != 0 else 0,
            "Div_CZK": r["Ks"] * m["div"] * rate
        })
    df_p = pd.DataFrame(processed)

    # --- STRÁNKA: PŘEHLED ---
    if page == "💰 Přehled":
        st.subheader("Aktuální stav portfolia")
        # Zde by byla tvá tabulka (zkráceno pro ukázku)
        st.table(df_p[["Název", "Ks", "Hodnota CZK", "Zisk %"]].style.format({"Hodnota CZK": "{:,.0f} CZK", "Zisk %": "{:.2f} %"}))

    # --- STRÁNKA: GRAFY ---
    elif page == "📊 Grafy & Sektory":
        st.subheader("Analýza rozložení")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### Sektory")
            fig_sec = px.pie(df_p, values='Hodnota CZK', names='Sektor', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_sec, use_container_width=True)
            
        with col2:
            st.write("### Největší pozice")
            fig_pos = px.bar(df_p.sort_values("Hodnota CZK", ascending=False).head(10), x='Název', y='Hodnota CZK', color='Název')
            st.plotly_chart(fig_pos, use_container_width=True)

    else:
        st.info(f"Stránka '{page}' je ve výstavbě. Zde budeme rozvíjet tvůj další 'list' z tabulky.")

except Exception as e:
    st.error(f"Chyba: {e}")
