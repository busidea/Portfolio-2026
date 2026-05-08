import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Portfolio", layout="wide")

# --- STYLOVÁNÍ (Kompaktní HTML tabulka) ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; }
    
    .portfolio-table { 
        width: 100%; 
        border-collapse: collapse; 
        font-family: 'Segoe UI', sans-serif;
        font-size: 13.5px; 
    }
    
    .portfolio-table th { 
        background-color: #1a1d20 !important; /* Černá hlavička */
        color: white !important;
        padding: 6px 10px; 
        text-align: right; 
        font-weight: bold;
        border: 1px solid #343a40;
    }
    
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    
    .portfolio-table td { 
        padding: 3px 10px; 
        border-bottom: 1px solid #dee2e6;
        line-height: 1.2;
    }
    
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; color: #000; }
    .highlight { font-weight: bold; color: #000; }
    
    tr:hover { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

# --- DATA ---
def get_data():
    data = [
        ["Heidelberg Materials", "HEI.DE", 800, "EUR", 37.45, 28.4, 2.6],
        ["HEIJMANS", "HEIJM.AS", 1162, "EUR", 7.63, 3.77, 0.8],
        ["ČEZ", "CEZ.PR", 750, "CZK", 100, 100, 52.0],
        ["ALPHABET", "GOOGL", 100, "USD", 133.34, 123.25, 0.2],
        ["VIG", "VIG.PR", 500, "CZK", 25.59, 24.328, 1.25],
        ["KOMERČNÍ BANKA", "KOMB.PR", 400, "CZK", 657.91, 657.91, 60.0],
        ["MONETA", "MONET.PR", 2500, "CZK", 81.1, 81.1, 9.0],
        ["Siemens Healthineers", "SHL.DE", 600, "EUR", 45.67, 38.81, 0.95],
        ["VOLKSWAGEN", "VOW3.DE", 150, "EUR", 237, 237, 8.7],
        ["PALANTIR", "PLTR", 100, "USD", 41, 41, 0.0],
        ["ETF BOTZ", "BOTZ", 400, "USD", 22.82, 19.75, 0.05],
        ["HPE", "HPE", 500, "USD", 19.6, 18.046, 0.13],
        ["ETF SPEU", "SPEU", 200, "USD", 35.08, 34.57, 0.4],
        ["High Templar Tech", "HTT", 1700, "USD", 6.4, 5.32, 0.0], # Opravený název
        ["BASF", "BAS.DE", 134, "EUR", 30, 30, 3.4],
        ["NOKIA", "NOKIA.HE", 1100, "EUR", 4.16, 3.17, 0.13],
        ["META", "META", 10, "USD", 647, 647, 2.0],
        ["GSK", "GSK", 100, "GBP", 30, 20.22, 0.58],
        ["ETF EPI", "EPI", 100, "USD", 37, 28.58, 0.1],
        ["Novo Nordisk", "NOVO-B.CO", 200, "DKK", 50, 40.83, 9.4],
        ["ETF EWU", "EWU", 100, "USD", 14.22, 7.855, 0.5],
        ["GRAY TV", "GTN", 600, "USD", 11.89, 9.19, 0.0],
        ["Pfizer", "PFE", 100, "USD", 27, 21.43, 1.68],
        ["STMicro", "STMPA.PA", 100, "EUR", 35, 23.4, 0.24],
        ["EHANG", "EH", 200, "USD", 16.5, 14.73, 0.0]
    ]
    return pd.DataFrame(data, columns=["Název", "Ticker", "KS", "Měna", "Cena_Std", "Cena_Opce", "Dividenda"])

# --- LOGIKA ---
df = get_data()

st.sidebar.title("PORTFOLIO")
view_mode = st.sidebar.radio("Nákupní cena:", ["Standardní", "S opcemi"])
# Nastavení defaultní hodnoty na '1 den'
time_frame = st.sidebar.selectbox("Změna za období:", ["1 den", "1 týden", "1 měsíc", "1 rok", "Od počátku"], index=0)

st.sidebar.divider()
# Nastavení defaultního řazení na Hodnota CZK
sort_by = st.sidebar.selectbox("Seřadit podle:", ["Hodnota CZK", "Zisk %", "Název", "KS", "TC"], index=0)
sort_order = st.sidebar.checkbox("Vzestupně", value=False)

col_price = "Cena_Std" if view_mode == "Standardní" else "Cena_Opce"

@st.cache_data(ttl=600)
def fetch_data(tickers):
    curr, diffs = {}, {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="5d")
            if not h.empty:
                curr[t] = h["Close"].iloc[-1]
                diffs[t] = h["Close"].iloc[-1] - h["Close"].iloc[-2]
            else: curr[t], diffs[t] = 0, 0
        except: curr[t], diffs[t] = 0, 0
    return curr, diffs

with st.spinner('Aktualizuji...'):
    prices, diffs = fetch_data(df["Ticker"].tolist())
    df["TC"] = df["Ticker"].map(prices)
    df["_diff"] = df["Ticker"].map(diffs)

fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
df["Hodnota CZK"] = df.apply(lambda x: x["KS"] * x["TC"] * fx.get(x["Měna"], 1.0), axis=1)
df["Inv_CZK"] = df.apply(lambda x: x["KS"] * x[col_price] * fx.get(x["Měna"], 1.0), axis=1)
df["Zisk %"] = ((df["TC"] - df[col_price]) / df[col_price] * 100)
df["Div. celkem CZK"] = df.apply(lambda x: x["KS"] * x["Dividenda"] * fx.get(x["Měna"], 1.0), axis=1)

# Aplikace řazení
df = df.sort_values(by=sort_by, ascending=sort_order)

def format_cz(value, decimals=2):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")

# --- HTML TABULKA ---
html = "<table class='portfolio-table'><thead><tr>"
html += "<th>Název titulu</th><th>Ticker</th><th>KS</th><th>TC</th><th>Hodnota CZK</th>"
html += "<th>Zisk %</th><th>Dividenda</th><th>Div. celkem CZK</th>"
html += "</tr></thead><tbody>"

for _, r in df.iterrows():
    c_cls = "pos" if r["_diff"] >= 0 else "neg"
    z_cls = "pos" if r["Zisk %"] >= 0 else "neg"
    
    html += f"<tr>"
    html += f"<td class='stock-name'>{r['Název']}</td>"
    html += f"<td>{r['Ticker']}</td>"
    html += f"<td class='num highlight'>{format_cz(r['KS'], 0)}</td>"
    html += f"<td class='num {c_cls}'>{format_cz(r['TC'])}</td>"
    html += f"<td class='num highlight'>{format_cz(r['Hodnota CZK'], 0)}</td>"
    html += f"<td class='num {z_cls}'>{format_cz(r['Zisk %'])} %</td>"
    html += f"<td class='num'>{format_cz(r['Dividenda'])}</td>"
    html += f"<td class='num'>{format_cz(r['Div. celkem CZK'], 0)}</td>"
    html += "</tr>"

html += "</tbody></table>"

st.write(html, unsafe_allow_html=True)

# Sidebar metriky
st.sidebar.divider()
total_val = df["Hodnota CZK"].sum()
st.sidebar.metric("Celková hodnota", format_cz(total_val, 0) + " CZK")
st.sidebar.metric("Roční dividendy", format_cz(df["Div. celkem CZK"].sum(), 0) + " CZK")
st.sidebar.metric("Celkový zisk", format_cz(total_val - df["Inv_CZK"].sum(), 0) + " CZK")
