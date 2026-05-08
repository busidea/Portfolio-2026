import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Live Portfolio", layout="wide")

# --- KONFIGURACE ODKAZU ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- STYLOVÁNÍ ---
st.markdown("""
<style>
    .block-container { padding-top: 4rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 15px; }
    .portfolio-table th { 
        background-color: #000000 !important; color: white !important; 
        padding: 12px 10px; text-align: right; border: 1px solid #333; font-weight: bold;
    }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 8px 10px; border-bottom: 1px solid #dee2e6; line-height: 1.4; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; color: #000; }
    .highlight { font-weight: bold; color: #000; }
    tr:hover { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

def format_cz(value, decimals=2):
    try:
        if pd.isna(value): return "0"
        return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except:
        return "0"

# --- NAČÍTÁNÍ DAT ---
@st.cache_data(ttl=300)
def load_full_data():
    # 1. Načtení Google Tabulky
    df = pd.read_csv(SHEET_URL)
    df = df.dropna(subset=['Ticker'])
    
    # Převedení číselných sloupců na skutečná čísla (odstraní chybu s násobením)
    num_cols = ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce').fillna(0)

    tickers = df["Ticker"].unique().tolist()
    market_results = {}
    historicals = {}
    
    # 2. Načtení dat z Yahoo Finance
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info
            h = tk.history(period="1y")
            
            # Automatická dividenda
            div = info.get('trailingAnnualDividendRate') or (info.get('dividendYield', 0) * info.get('currentPrice', 0))
            
            market_results[t] = {
                "price": info.get('currentPrice') or (h['Close'].iloc[-1] if not h.empty else 0),
                "div": div or 0.0,
                "currency_market": info.get('currency', 'USD'),
                "diff": (h['Close'].iloc[-1] - h['Close'].iloc[-2]) if len(h) > 1 else 0
            }
            historicals[t] = h
        except:
            market_results[t] = {"price": 0, "div": 0, "currency_market": "USD", "diff": 0}
            
    return df, market_results, historicals

# --- SPUŠTĚNÍ ---
try:
    df_sheet, market_info, historicals = load_full_data()

    # SIDEBAR
    st.sidebar.title("PORTFOLIO")
    view_mode = st.sidebar.radio("Nákupní cena:", ["Standardní", "S opcemi"])
    time_frame = st.sidebar.selectbox("Změna za období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"], index=4)
    sort_col_ui = st.sidebar.selectbox("Seřadit podle:", ["Název", "Hodnota CZK", "Zisk %", "Ks", "TC"], index=1)
    sort_asc = st.sidebar.checkbox("Vzestupně", value=False)

    col_price_name = "Průměrná nákupní cena" if view_mode == "Standardní" else "Nákupní cena včetně opcí"

    fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
    
    rows = []
    for _, r in df_sheet.iterrows():
        t = r["Ticker"]
        m = market_info.get(t, {})
        h = historicals.get(t, pd.DataFrame())
        
        # Oprava názvů a dat
        name = "High Templar Tech" if t == "HTT" else r["Název"]
        current_price = float(m.get("price", 0))
        buy_price = float(r[col_price_name])
        ks = float(r["Ks"])
        
        # Měna z tabulky (sloupec "Měna")
        currency = str(r["Měna"]).strip() if pd.notna(r["Měna"]) else m.get("currency_market", "USD")
        rate = fx.get(currency, 1.0)
        
        # Výpočet změny %
        if time_frame == "1 den" and len(h) > 1: ref = h["Close"].iloc[-2]
        elif time_frame == "1 týden" and len(h) > 5: ref = h["Close"].iloc[-5]
        elif time_frame == "1 měsíc" and len(h) > 21: ref = h["Close"].iloc[-21]
        elif time_frame == "1 rok" and len(h) > 0: ref = h["Close"].iloc[0]
        else: ref = buy_price
        
        zisk_pc = ((current_price - ref) / ref * 100) if ref != 0 else 0
        
        rows.append({
            "Název": name,
            "Ticker": t,
            "Ks": ks,
            "TC": current_price,
            "Hodnota CZK": ks * current_price * rate,
            "Zisk %": zisk_pc,
            "Dividenda": m.get("div", 0),
            "Div celkem CZK": ks * m.get("div", 0) * rate,
            "Diff": m.get("diff", 0),
            "Inv_CZK": ks * buy_price * rate
        })

    df_final = pd.DataFrame(rows)
    df_final = df_final.sort_values(by=sort_col_ui, ascending=sort_asc)

    # METRIKY
    st.sidebar.divider()
    total_val = df_final["Hodnota CZK"].sum()
    st.sidebar.metric("Celková hodnota", format_cz(total_val, 0) + " CZK")
    st.sidebar.metric("Odhad dividend (rok)", format_cz(df_final["Div celkem CZK"].sum(), 0) + " CZK")
    st.sidebar.metric("Celkový zisk", format_cz(total_val - df_final["Inv_CZK"].sum(), 0) + " CZK")

    # TABULKA
    html = "<table class='portfolio-table'><thead><tr>"
    html += "<th>Název titulu</th><th>Ticker</th><th class='num'>KS</th><th class='num'>TC</th><th class='num'>Hodnota CZK</th>"
    html += "<th class='num'>Zisk %</th><th class='num'>Dividenda</th><th class='num'>Div. celkem CZK</th>"
    html += "</tr></thead><tbody>"

    for _, r in df_final.iterrows():
        c_class = "pos" if r["Diff"] >= 0 else "neg"
        z_class = "pos" if r["Zisk %"] >= 0 else "neg"
        
        html += f"<tr>"
        html += f"<td class='stock-name'>{r['Název']}</td>"
        html += f"<td>{r['Ticker']}</td>"
        html += f"<td class='num highlight'>{format_cz(r['Ks'], 0)}</td>"
        html += f"<td class='num {c_class}'>{format_cz(r['TC'])}</td>"
        html += f"<td class='num highlight'>{format_cz(r['Hodnota CZK'], 0)}</td>"
        html += f"<td class='num {z_class}'>{format_cz(r['Zisk %'])} %</td>"
        html += f"<td class='num'>{format_cz(r['Dividenda'])}</td>"
        html += f"<td class='num'>{format_cz(r['Div celkem CZK'], 0)}</td>"
        html += "</tr>"

    html += "</tbody></table>"
    st.write(html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Chyba: {e}")
    st.write("Debug info - sloupce v tabulce:", df_sheet.columns.tolist() if 'df_sheet' in locals() else "Tabulka nenačtena")
