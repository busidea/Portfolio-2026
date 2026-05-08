import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Portfolio", layout="wide")

# --- STYLOVÁNÍ A OPRAVENÝ JAVASCRIPT ---
st.markdown("""
<style>
    .block-container { padding-top: 3.5rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
    
    .portfolio-table th { 
        background-color: #343a40; color: white; padding: 10px; 
        text-align: right; cursor: pointer; border: 1px solid #454d55;
        position: sticky; top: 0;
    }
    .portfolio-table th:hover { background-color: #495057; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    
    .portfolio-table td { padding: 5px 10px; border-bottom: 1px solid #dee2e6; line-height: 1.4; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; color: #000; }
    .highlight { font-weight: bold; color: #000; }
    tr:hover { background-color: #f8f9fa; }
</style>

<script>
function sortTable(n) {
  var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.querySelector(".portfolio-table");
  switching = true;
  dir = "asc";
  while (switching) {
    switching = false;
    rows = table.rows;
    for (i = 1; i < (rows.length - 1); i++) {
      shouldSwitch = false;
      x = rows[i].getElementsByTagName("TD")[n];
      y = rows[i+1].getElementsByTagName("TD")[n];
      
      // Vyčištění formátu pro korektní porovnání čísel (odstranění mezer, % a převod čárky na tečku)
      let xVal = x.innerText.replace(/[ %]/g, '').replace(',', '.');
      let yVal = y.innerText.replace(/[ %]/g, '').replace(',', '.');
      
      let xNum = parseFloat(xVal);
      let yNum = parseFloat(yVal);

      if (!isNaN(xNum) && !isNaN(yNum)) {
        if (dir == "asc") { if (xNum > yNum) { shouldSwitch = true; break; } }
        else if (dir == "desc") { if (xNum < yNum) { shouldSwitch = true; break; } }
      } else {
        if (dir == "asc") { if (x.innerText.toLowerCase() > y.innerText.toLowerCase()) { shouldSwitch = true; break; } }
        else if (dir == "desc") { if (x.innerText.toLowerCase() < y.innerText.toLowerCase()) { shouldSwitch = true; break; } }
      }
    }
    if (shouldSwitch) {
      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
      switching = true;
      switchcount ++;
    } else {
      if (switchcount == 0 && dir == "asc") { dir = "desc"; switching = true; }
    }
  }
}
</script>
""", unsafe_allow_html=True)

# --- DATA ---
def get_data():
    data = [
        ["Heidelberg Materials", "HEI.DE", 800, "Stavební", "EUR", 37.45, 28.4, 2.6],
        ["HEIJMANS", "HEIJM.AS", 1162, "Stavební", "EUR", 7.63, 3.77, 0.8],
        ["ČEZ", "CEZ.PR", 750, "Energetika", "CZK", 100, 100, 52.0],
        ["ALPHABET", "GOOGL", 100, "Technologie", "USD", 133.34, 123.25, 0.2],
        ["VIG", "VIG.PR", 500, "Pojišťovnictví", "CZK", 25.59, 24.328, 1.25],
        ["KOMERČNÍ BANKA", "KOMB.PR", 400, "Bankovnictví", "CZK", 657.91, 657.91, 60.0],
        ["MONETA", "MONET.PR", 2500, "Bankovnictví", "CZK", 81.1, 81.1, 9.0],
        ["Siemens Healthineers", "SHL.DE", 600, "Zdravotní", "EUR", 45.67, 38.81, 0.95],
        ["VOLKSWAGEN", "VOW3.DE", 150, "Auto", "EUR", 237, 237, 8.7],
        ["PALANTIR", "PLTR", 100, "Software", "USD", 41, 41, 0.0],
        ["ETF BOTZ", "BOTZ", 400, "AI", "USD", 22.82, 19.75, 0.05],
        ["HPE", "HPE", 500, "IT", "USD", 19.6, 18.046, 0.13],
        ["ETF SPEU", "SPEU", 200, "ETF", "USD", 35.08, 34.57, 0.4],
        ["High Templar", "HTT", 1700, "Fintech", "USD", 6.4, 5.32, 0.0], # Upravený název
        ["BASF", "BAS.DE", 134, "Chemie", "EUR", 30, 30, 3.4],
        ["NOKIA", "NOKIA.HE", 1100, "Telco", "EUR", 4.16, 3.17, 0.13],
        ["META", "META", 10, "Soc. sítě", "USD", 647, 647, 2.0],
        ["GSK", "GSK", 100, "Farmacie", "GBP", 30, 20.22, 0.58],
        ["ETF EPI", "EPI", 100, "Indie", "USD", 37, 28.58, 0.1],
        ["Novo Nordisk", "NOVO-B.CO", 200, "Farmacie", "DKK", 50, 40.83, 9.4],
        ["ETF EWU", "EWU", 100, "UK", "USD", 14.22, 7.855, 0.5],
        ["GRAY TV", "GTN", 600, "Média", "USD", 11.89, 9.19, 0.0],
        ["Pfizer", "PFE", 100, "Farmacie", "USD", 27, 21.43, 1.68],
        ["STMicro", "STMPA.PA", 100, "Polovodiče", "EUR", 35, 23.4, 0.24],
        ["EHANG", "EH", 200, "EVTOL", "USD", 16.5, 14.73, 0.0]
    ]
    return pd.DataFrame(data, columns=["Název", "Ticker", "Ks", "Sektor", "Měna", "Cena_Std", "Cena_Opce", "Divi_Net"])

def format_cz(value, decimals=2):
    if pd.isna(value): return "-"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")

# --- LOGIKA ---
df = get_data()

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

with st.spinner('Aktualizuji data...'):
    curr_prices, hist_data = fetch_data(df["Ticker"].tolist())
    df["TC"] = df["Ticker"].map(lambda x: curr_prices.get(x, 0))
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
    return ((row["TC"] - ref) / ref) * 100 if ref != 0 else 0

df["Zisk_%"] = df.apply(calc_change, axis=1)

fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
df["Hodnota_CZK"] = df.apply(lambda x: x["Ks"] * x["TC"] * fx.get(x["Měna"], 1.0), axis=1)
df["Inv_CZK"] = df.apply(lambda x: x["Ks"] * x[col_price] * fx.get(x["Měna"], 1.0), axis=1)
df["Divi_Celkem_CZK"] = df.apply(lambda x: x["Ks"] * x["Divi_Net"] * fx.get(x["Měna"], 1.0), axis=1)

# Sidebar metriky
st.sidebar.divider()
st.sidebar.metric("Celková hodnota", format_cz(df["Hodnota_CZK"].sum(), 0) + " CZK")
st.sidebar.metric("Roční dividendy (net)", format_cz(df["Divi_Celkem_CZK"].sum(), 0) + " CZK")
st.sidebar.metric("Celkový zisk", format_cz(df["Hodnota_CZK"].sum() - df["Inv_CZK"].sum(), 0) + " CZK")

# --- HTML TABULKA ---
html = "<table class='portfolio-table'><thead><tr>"
html += "<th onclick='sortTable(0)'>Název titulu</th>"
html += "<th onclick='sortTable(1)'>Ticker</th>"
html += "<th onclick='sortTable(2)' class='num'>KS</th>"
html += "<th onclick='sortTable(3)' class='num'>TC</th>"
html += "<th onclick='sortTable(4)' class='num'>Hodnota CZK</th>"
html += "<th onclick='sortTable(5)' class='num'>Zisk %</th>"
html += "<th onclick='sortTable(6)' class='num'>Dividenda</th>"
html += "<th onclick='sortTable(7)' class='num'>Div. celkem CZK</th>"
html += "</tr></thead><tbody>"

for _, r in df.iterrows():
    c_class = "pos" if r["Diff"] >= 0 else "neg"
    z_class = "pos" if r["Zisk_%"] >= 0 else "neg"
    
    html += f"<tr>"
    html += f"<td class='stock-name'>{r['Název']}</td>"
    html += f"<td>{r['Ticker']}</td>"
    html += f"<td class='num highlight'>{format_cz(r['Ks'], 0)}</td>"
    html += f"<td class='num {c_class}'>{format_cz(r['TC'])}</td>"
    html += f"<td class='num highlight'>{format_cz(r['Hodnota_CZK'], 0)}</td>"
    html += f"<td class='num {z_class}'>{format_cz(r['Zisk_%'])} %</td>"
    html += f"<td class='num'>{format_cz(r['Divi_Net'])}</td>"
    html += f"<td class='num'>{format_cz(r['Divi_Celkem_CZK'], 0)}</td>"
    html += "</tr>"

html += "</tbody></table>"

st.write(html, unsafe_allow_html=True)
