import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- KONFIGURACE ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- KOMPLETNÍ STYLOVÁNÍ (ZRESTAUROVÁNO) ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .block-container { padding-top: 2rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
    .portfolio-table th { 
        background-color: #000000 !important; color: white !important; 
        padding: 8px 10px; text-align: right; border: 1px solid #333; font-weight: bold;
    }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 5px 10px; border-bottom: 1px solid #dee2e6; line-height: 1.2; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; color: #000; }
    tr:hover { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

def format_cz(value, decimals=2):
    try:
        if pd.isna(value): return "0"
        return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

# --- DATA & KURZY ---
@st.cache_data(ttl=3600)
def get_fx_rates():
    rates = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
    pairs = {"EUR": "EURCZK=X", "USD": "USDCZK=X", "GBP": "GBPCZK=X", "DKK": "DKKCZK=X"}
    for currency, ticker in pairs.items():
        try:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty: rates[currency] = data['Close'].iloc[-1]
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

# --- HLAVNÍ LOGIKA ---
try:
    df_sheet, market_info, historicals = load_full_data()
    fx = get_fx_rates()

    # SIDEBAR NAVIGACE
    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("PŘEJÍT NA:", ["💰 Přehled", "📊 Grafy & Sektory", "📅 Dividendy", "🚀 Vývoj"])
    
    # --- STRÁNKA: PŘEHLED (ZRESTAUROVANÁ) ---
    if page == "💰 Přehled":
        st.sidebar.divider()
        st.sidebar.subheader("NASTAVENÍ TABULKY")
        view_mode = st.sidebar.radio("Cena:", ["Standardní", "S opcemi"])
        time_frame = st.sidebar.selectbox("Změna za období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"], index=4)
        sort_col = st.sidebar.selectbox("Seřadit podle:", ["Název", "Hodnota CZK", "Zisk %"], index=1)
        
        col_price_key = "Průměrná nákupní cena" if view_mode == "Standardní" else "Nákupní cena včetně opcí"
        
        processed_rows = []
        for _, r in df_sheet.iterrows():
            t = r["Ticker"]
            m = market_info.get(t, {})
            h = historicals.get(t, pd.DataFrame())
            rate = fx.get(str(r["Měna"]).strip(), 1.0)
            
            # Výpočet reference pro zisk
            if time_frame == "1 den" and len(h) > 1: ref = h["Close"].iloc[-2]
            elif time_frame == "1 týden" and len(h) > 5: ref = h["Close"].iloc[-5]
            elif time_frame == "1 měsíc" and len(h) > 21: ref = h["Close"].iloc[-21]
            elif time_frame == "1 rok" and len(h) > 0: ref = h["Close"].iloc[0]
            else: ref = r[col_price_key]
            
            zisk_pc = ((m["price"] - ref) / ref * 100) if ref != 0 else 0
            
            processed_rows.append({
                "Název": "High Templar Tech" if t in ["QD", "HTT"] else r["Název"],
                "Sektor": r["Obor (Sektor)"],
                "Ks": r["Ks"],
                "TC": m["price"],
                "Hodnota CZK": r["Ks"] * m["price"] * rate,
                "Zisk %": zisk_pc,
                "Dividenda": m["div"],
                "Div celkem CZK": r["Ks"] * m["div"] * rate,
                "Diff": m["diff"],
                "Investice": r["Ks"] * r[col_price_key] * rate
            })

        df_final = pd.DataFrame(processed_rows).sort_values(sort_col, ascending=False)

        # Celkové metriky
        total_val = df_final["Hodnota CZK"].sum()
        st.sidebar.divider()
        st.sidebar.metric("Celková hodnota", format_cz(total_val, 0) + " CZK")
        st.sidebar.metric("Zisk/Ztráta", format_cz(total_val - df_final["Investice"].sum(), 0) + " CZK")
        
        # Samotná tabulka
        html = "<table class='portfolio-table'><thead><tr>"
        html += "<th>Název titulu</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th>"
        html += "<th class='num'>Zisk %</th><th class='num'>Dividenda (ks)</th><th class='num'>Roční div. CZK</th>"
        html += "</tr></thead><tbody>"

        for _, r in df_final.iterrows():
            z_class = "pos" if r["Zisk %"] >= 0 else "neg"
            c_class = "pos" if r["Diff"] >= 0 else "neg"
            html += f"<tr><td class='stock-name'>{r['Název']}</td><td class='num'>{format_cz(r['Ks'], 0)}</td>"
            html += f"<td class='num {c_class}'>{format_cz(r['TC'])}</td>"
            html += f"<td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td>"
            html += f"<td class='num {z_class}'>{format_cz(r['Zisk %'])} %</td>"
            html += f"<td class='num'>{format_cz(r['Dividenda'])}</td>"
            html += f"<td class='num'>{format_cz(r['Div celkem CZK'], 0)}</td></tr>"
        html += "</tbody></table>"
        st.write(html, unsafe_allow_html=True)

    # --- OSTATNÍ STRÁNKY (ZATÍM JEDNODUCHÉ) ---
        elif page == "📊 Grafy & Sektory":
        st.subheader("Vizuální mapa portfolia")
        
        # Příprava dat
        rows_g = []
        for _, r in df_sheet.iterrows():
            rate = fx.get(str(r["Měna"]).strip(), 1.0)
            rows_g.append({
                "Název": "High Templar Tech" if r["Ticker"] in ["QD", "HTT"] else r["Název"],
                "Sektor": r["Obor (Sektor)"],
                "Hodnota CZK": r["Ks"] * market_info.get(r["Ticker"], {"price":0})["price"] * rate
            })
        df_g = pd.DataFrame(rows_g)

        # TreeMap - tohle je ta pecka
        fig_tree = px.treemap(
            df_g, 
            path=[px.Constant("Portfolio"), 'Sektor', 'Název'], # Hierarchie: Vše -> Sektor -> Akcie
            values='Hodnota CZK',
            color='Sektor',
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        
        fig_tree.update_layout(margin=dict(t=30, l=10, r=10, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)
        
        st.info("💡 Tip: Na čtverce v grafu můžeš klikat – graf se 'ponoří' hlouběji do daného sektoru.")
        st.subheader("Rozložení portfolia")
        # Rychlá příprava dat pro graf
        rows_g = []
        for _, r in df_sheet.iterrows():
            rate = fx.get(str(r["Měna"]).strip(), 1.0)
            rows_g.append({"Sektor": r["Obor (Sektor)"], "Hodnota CZK": r["Ks"] * market_info.get(r["Ticker"], {"price":0})["price"] * rate})
        df_g = pd.DataFrame(rows_g)
        
        fig = px.pie(df_g, values='Hodnota CZK', names='Sektor', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info(f"Stránka {page} je připravena pro tvé další nápady.")

except Exception as e:
    st.error(f"Chyba: {e}")
