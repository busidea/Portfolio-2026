import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Portfolio", layout="wide")

# --- KOMPAKTNÍ STYLOVÁNÍ (CSS) ---
st.markdown("""
<style>
    /* Posun celého obsahu co nejvýše */
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    
    /* Definice tabulky - extrémně kompaktní */
    .portfolio-table { 
        width: 100%; 
        border-collapse: collapse; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 14px; /* O něco menší písmo pro úsporu místa */
    }
    .portfolio-table th { 
        background-color: #f8f9fb; 
        padding: 4px 10px; 
        text-align: left; 
        border-bottom: 2px solid #333;
        font-weight: bold;
    }
    .portfolio-table td { 
        padding: 2px 10px; /* Minimální vertikální padding */
        border-bottom: 1px solid #eee;
        line-height: 1.2;
    }
    
    /* Zarovnání čísel doprava */
    .num { text-align: right; }
    
    /* Barvy a tučnost */
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; color: #1f77b4; text-align: left; }
    
    /* Zúžení postranního panelu pro více místa na tabulku */
    [data-testid="stSidebar"] { width: 250px !important; }
</style>
""", unsafe_allow_html=True)

# --- DATA ---
def get_data():
    data = [
        ["Heidelberg Materials", "HEI.DE", 800, "Stavební materiály", "EUR", 37.45, 28.4],
        ["HEIJMANS", "HEIJM.AS", 1162, "Stavebnictví", "EUR", 7.63, 3.77],
        ["ČEZ", "CEZ.PR", 750, "Energetika", "CZK", 100, 100],
        ["ALPHABET", "GOOGL", 100, "Technologie", "USD", 133.34, 123.25],
        ["VIG", "VIG.PR", 500, "Pojišťovnictví", "CZK", 25.59, 24.328],
        ["KOMERČNÍ BANKA", "KOMB.PR", 400, "Bankovnictví", "CZK", 657.91, 657.91],
        ["MONETA", "MONET.PR", 2500, "Bankovnictví", "CZK", 81.1, 81.1],
        ["Siemens Healthineers", "SHL.DE", 600, "Zdravotní technika", "EUR", 45.67, 38.81],
        ["VOLKSWAGEN", "VOW3.DE", 150, "Auto", "EUR", 237, 237],
        ["PALANTIR", "PLTR", 100, "Software / AI", "USD", 41, 41],
        ["ETF BOTZ", "BOTZ", 400, "AI / Robotika", "USD", 22.82, 19.75],
        ["HPE", "HPE", 500, "IT Infra", "USD", 19.6, 18.046],
        ["ETF SPEU", "SPEU", 200, "ETF Evropa", "USD", 35.08, 34.57],
        ["QUDIAN", "QD", 1700, "Fintech", "USD", 6.4, 5.32],
        ["BASF", "BAS.DE", 134, "Chemie", "EUR", 30, 30],
        ["NOKIA", "NOKIA.HE", 1100, "Telekomunikace", "EUR", 4.16, 3.17],
        ["META", "META", 10, "Sociální sítě", "USD", 647, 647],
        ["GSK", "GSK", 100, "Farmacie", "GBP", 30, 20.22],
        ["ETF EPI", "EPI", 100, "ETF Indie", "USD", 37, 28.58],
        ["Novo Nordisk", "NOVO-B.CO", 200, "Farmacie", "DKK", 50, 40.83],
        ["ETF EWU", "EWU", 100, "ETF UK", "USD", 14.22, 7.855],
        ["GRAY TV", "GTN", 600, "Média", "USD", 11.89, 9.19],
        ["Pfizer", "PFE", 100, "Farmacie", "USD", 27, 21.43],
        ["STMicro", "STMPA.PA", 100, "Polovodiče", "EUR", 35, 23.4],
        ["EHANG", "EH", 200, "EVTOL", "USD", 16.5, 14.73]
    ]
    return pd.DataFrame(data, columns=["Název", "Ticker", "Ks", "Sektor", "Měna", "Cena_Std", "Cena_Opce"])

def format_cz(value, decimals=2):
    if pd.isna(value): return "-"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" ", " ")

# --- LOGIKA DATA ---
df = get_data()

# SIDEBAR
st.sidebar.title("PORTFOLIO")
view_mode = st.sidebar.radio("Nákupní cena:", ["Standardní", "S opcemi"])
time_frame = st.sidebar.selectbox("Změna za období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"])
col_price = "Cena_Std" if view_mode == "Standardní" else "Cena_Opce"

@st.cache_data(ttl=600)
def fetch_data(tickers):
    curr, hist = {}, {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="1y")
            if not h.empty:
                hist[t] = h
                curr[t] = h["Close"].iloc[-1]
                prev = h["Close"].iloc[-2] if len(h) > 1 else h["Close"].iloc[-1]
                curr[t + "_diff"] = curr[t] - prev
            else: curr[t], curr[t + "_diff"] = 0.0, 0.0
        except: curr[t], curr[t + "_diff"] = 0.0, 0.0
    return curr, hist

with st.spinner('Načítám...'):
    curr_prices, hist_data = fetch_data(df["Ticker"].tolist())
    df["Aktuální_Cena"] = df["Ticker"].map(lambda x: curr_prices.get(x, 0))
    df["Diff"] = df["Ticker"].map(lambda x: curr_prices.get(x + "_diff", 0))

def calc_change(row):
    t = row["Ticker"]
    if t not in hist_data: return 0.0
    h = hist_data[t]["Close"]
    if time_frame == "1 den": ref = h.iloc[-2] if len(h)>1 else h.iloc[-1]
    elif time_frame == "1 týden": ref = h.iloc[-5] if len(h)>5 else h.iloc[0]
    elif time_frame == "1 měsíc": ref = h.iloc[-21] if len(h)>21 else h.iloc[0]
    elif time_frame == "1 rok": ref = h.iloc[0]
    else: ref = row[col_price]
    return ((row["Aktuální_Cena"] - ref) / ref) * 100 if ref != 0 else 0

df["Zisk_%"] = df.apply(calc_change, axis=1)

# Měny a celky
fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
df["Hodnota_CZK"] = df.apply(lambda x: x["Ks"] * x["Aktuální_Cena"] * fx.get(x["Měna"], 1.0), axis=1)
df["Inv_CZK"] = df.apply(lambda x: x["Ks"] * x[col_price] * fx.get(x["Měna"], 1.0), axis=1)

# Sidebar metriky
st.sidebar.divider()
total_val = df["Hodnota_CZK"].sum()
st.sidebar.metric("Celková hodnota", format_cz(total_val, 0) + " CZK")
prof = total_val - df["Inv_CZK"].sum()
prof_p = (prof / df["Inv_CZK"].sum() * 100) if df["Inv_CZK"].sum() != 0 else 0
st.sidebar.metric("Celkový zisk", format_cz(prof, 0) + " CZK", f"{prof_p:.2f} %")

# --- VÝSTUPNÍ HTML TABULKA ---
html = "<table class='portfolio-table'><thead><tr>"
html += "<th>Název</th><th class='num'>Ticker</th><th class='num'>Kusy</th><th class='num'>Cena</th><th class='num'>Zisk %</th><th class='num'>Hodnota CZK</th>"
html += "</tr></thead><tbody>"

for _, r in df.iterrows():
    c_class = "pos" if r["Diff"] >= 0 else "neg"
    z_class = "pos" if r["Zisk_%"] >= 0 else "neg"
    
    html += f"<tr>"
    html += f"<td class='stock-name'>{r['Název']}</td>"
    html += f"<td class='num'>{r['Ticker']}</td>"
    html += f"<td class='num'>{format_cz(r['Ks'], 0)}</td>"
    html += f"<td class='num {c_class}'>{format_cz(r['Aktuální_Cena'])}</td>"
    html += f"<td class='num {z_class}'>{format_cz(r['Zisk_%'])} %</td>"
    html += f"<td class='num'>{format_cz(r['Hodnota_CZK'], 0)}</td>"
    html += f"</tr>"

html += "</tbody></table>"

st.write(html, unsafe_allow_html=True)
