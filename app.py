import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Live Portfolio", layout="wide")

# --- KONFIGURACE ODKAZU ---
# Vaše tabulka převedená na přímý export dat
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
        return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except:
        return "0"

# --- NAČÍTÁNÍ DAT Z GOOGLE SHEETS ---
@st.cache_data(ttl=300) # Data z tabulky se osvěží každých 5 minut
def load_sheet_data():
    df_sheet = pd.read_csv(SHEET_URL)
    # Vyčištění dat (odstranění prázdných řádků)
    df_sheet = df_sheet.dropna(subset=['Ticker'])
    return df_sheet

# --- NAČÍTÁNÍ DAT Z BURZY ---
@st.cache_data(ttl=600)
def fetch_market_data(tickers):
    results = {}
    hist_data = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            # Aktuální cena a info
            info = tk.info
            h = tk.history(period="1y")
            
            # Automatická dividenda (zkusíme několik zdrojů v info)
            div = info.get('trailingAnnualDividendRate')
            if div is None:
                yield_pc = info.get('dividendYield')
                if yield_pc:
                    div = info.get('currentPrice', 0) * yield_pc
                else:
                    div = 0.0
            
            results[t] = {
                "shortName": info.get('shortName', t),
                "price": info.get('currentPrice') or (h['Close'].iloc[-1] if not h.empty else 0),
                "div": div or 0.0,
                "currency": info.get('currency', 'USD'),
                "diff": (h['Close'].iloc[-1] - h['Close'].iloc[-2]) if len(h) > 1 else 0
            }
            hist_data[t] = h
        except:
            results[t] = {"shortName": t, "price": 0, "div": 0, "currency": "USD", "diff": 0}
    return results, hist_data

# --- HLAVNÍ LOGIKA ---
try:
    df_base = load_sheet_data()
    tickers = df_base["Ticker"].unique().tolist()
    
    with st.spinner('Stahuji data z burzy a Google tabulky...'):
        market_info, historicals = fetch_market_data(tickers)

    # Propojení dat
    df_base["Název"] = df_base["Ticker"].map(lambda x: market_info[x]["shortName"])
    df_base["TC"] = df_base["Ticker"].map(lambda x: market_info[x]["price"])
    df_base["Měna"] = df_base["Ticker"].map(lambda x: market_info[x]["currency"])
    df_base["Divi_Auto"] = df_base["Ticker"].map(lambda x: market_info[x]["div"])
    df_base["Diff"] = df_base["Ticker"].map(lambda x: market_info[x]["diff"])

    # Sidebar ovladače
    st.sidebar.title("PORTFOLIO")
    view_mode = st.sidebar.radio("Nákupní cena:", ["Standardní", "S opcemi"])
    time_frame = st.sidebar.selectbox("Změna za období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"], index=4)
    sort_col = st.sidebar.selectbox("Seřadit podle:", ["Název", "Hodnota_CZK", "Zisk_%", "Ks", "TC"], index=1)
    sort_asc = st.sidebar.checkbox("Vzestupně", value=False)

    col_price = "Cena_Std" if view_mode == "Standardní" else "Cena_Opce"

    # Výpočty
    fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
    
    def calc_zisk(row):
        t = row["Ticker"]
        if t not in historicals or historicals[t].empty: return 0.0
        h = historicals[t]["Close"]
        if time_frame == "1 den": ref = h.iloc[-2] if len(h)>1 else h.iloc[-1]
        elif time_frame == "1 týden": ref = h.iloc[-5] if len(h)>5 else h.iloc[0]
        elif time_frame == "1 měsíc": ref = h.iloc[-21] if len(h)>21 else h.iloc[0]
        elif time_frame == "1 rok": ref = h.iloc[0]
        else: ref = row[col_price]
        return ((row["TC"] - ref) / ref) * 100 if ref != 0 else 0

    df_base["Zisk_%"] = df_base.apply(calc_zisk, axis=1)
    df_base["Hodnota_CZK"] = df_base.apply(lambda x: x["Ks"] * x["TC"] * fx.get(x["Měna"], 1.0), axis=1)
    df_base["Inv_CZK"] = df_base.apply(lambda x: x["Ks"] * x[col_price] * fx.get(x["Měna"], 1.0), axis=1)
    df_base["Divi_Celkem_CZK"] = df_base.apply(lambda x: x["Ks"] * x["Divi_Auto"] * fx.get(x["Měna"], 1.0), axis=1)

    # Seřazení
    df_final = df_base.sort_values(by=sort_col, ascending=sort_asc)

    # Sidebar metriky
    st.sidebar.divider()
    st.sidebar.metric("Celková hodnota", format_cz(df_final["Hodnota_CZK"].sum(), 0) + " CZK")
    st.sidebar.metric("Odhad dividend (rok)", format_cz(df_final["Divi_Celkem_CZK"].sum(), 0) + " CZK")
    st.sidebar.metric("Celkový zisk", format_cz(df_final["Hodnota_CZK"].sum() - df_final["Inv_CZK"].sum(), 0) + " CZK")

    # --- HTML VÝSTUP ---
    html = "<table class='portfolio-table'><thead><tr>"
    html += "<th>Název titulu</th><th>Ticker</th><th class='num'>KS</th><th class='num'>TC</th><th class='num'>Hodnota CZK</th>"
    html += "<th class='num'>Zisk %</th><th class='num'>Dividenda</th><th class='num'>Div. celkem CZK</th>"
    html += "</tr></thead><tbody>"

    for _, r in df_final.iterrows():
        c_class = "pos" if r["Diff"] >= 0 else "neg"
        z_class = "pos" if r["Zisk_%"] >= 0 else "neg"
        
        html += f"<tr>"
        html += f"<td class='stock-name'>{r['Název']}</td>"
        html += f"<td>{r['Ticker']}</td>"
        html += f"<td class='num highlight'>{format_cz(r['Ks'], 0)}</td>"
        html += f"<td class='num {c_class}'>{format_cz(r['TC'])}</td>"
        html += f"<td class='num highlight'>{format_cz(r['Hodnota_CZK'], 0)}</td>"
        html += f"<td class='num {z_class}'>{format_cz(r['Zisk_%'])} %</td>"
        html += f"<td class='num'>{format_cz(r['Divi_Auto'])}</td>"
        html += f"<td class='num'>{format_cz(r['Divi_Celkem_CZK'], 0)}</td>"
        html += "</tr>"

    html += "</tbody></table>"
    st.write(html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Chyba při načítání dat: {e}")
    st.info("Zkontrolujte, zda má tabulka sloupce: Ticker, Ks, Cena_Std, Cena_Opce")
