import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Portfolio", layout="wide")

# --- KOMPAKTNÍ STYLOVÁNÍ ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; }
    
    .portfolio-table { 
        width: 100%; 
        border-collapse: collapse; 
        font-family: 'Segoe UI', sans-serif;
        font-size: 13px; /* Mírně menší písmo pro úsporu místa */
    }
    
    .portfolio-table th { 
        background-color: #212529; /* Velmi tmavě šedá/černá */
        color: #ffffff;
        padding: 8px 10px; 
        text-align: right; 
        font-weight: 600;
        cursor: pointer;
        border: 1px solid #343a40;
        position: sticky;
        top: 0;
    }
    
    .portfolio-table th:hover { background-color: #343a40; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    
    .portfolio-table td { 
        padding: 3px 10px; /* Kompaktní řádky */
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
        ["High Templar", "HTT", 1700, "USD", 6.4, 5.32, 0.0],
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
time_frame = st.sidebar.selectbox("Změna za období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"])
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
                diffs[t] = h["Close"].iloc[-1] - h["Close"].iloc[-2] if len(h) > 1 else 0
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

def format_cz(value, decimals=2):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")

# --- HTML TABULKA S INLINE JAVASCRIPTEM ---
# JavaScript je vložen přímo do HTML komponenty, aby fungovalo řazení
html_code = f"""
<div id="portfolio-container">
<table class="portfolio-table" id="pTable">
    <thead>
        <tr>
            <th onclick="sortT(0)">Název titulu</th>
            <th onclick="sortT(1)">Ticker</th>
            <th onclick="sortT(2)">KS</th>
            <th onclick="sortT(3)">TC</th>
            <th onclick="sortT(4)">Hodnota CZK</th>
            <th onclick="sortT(5)">Zisk %</th>
            <th onclick="sortT(6)">Dividenda</th>
            <th onclick="sortT(7)">Div. celkem CZK</th>
        </tr>
    </thead>
    <tbody>
"""

for _, r in df.iterrows():
    c_cls = "pos" if r["_diff"] >= 0 else "neg"
    z_cls = "pos" if r["Zisk %"] >= 0 else "neg"
    
    html_code += f"<tr>"
    html_code += f"<td class='stock-name'>{r['Název']}</td>"
    html_code += f"<td>{r['Ticker']}</td>"
    html_code += f"<td class='num highlight'>{format_cz(r['KS'], 0)}</td>"
    html_code += f"<td class='num {c_cls}'>{format_cz(r['TC'])}</td>"
    html_code += f"<td class='num highlight'>{format_cz(r['Hodnota CZK'], 0)}</td>"
    html_code += f"<td class='num {z_cls}'>{format_cz(r['Zisk %'])} %</td>"
    html_code += f"<td class='num'>{format_cz(r['Dividenda'])}</td>"
    html_code += f"<td class='num'>{format_cz(r['Div. celkem CZK'], 0)}</td>"
    html_code += "</tr>"

html_code += """
    </tbody>
</table>
</div>

<script>
function sortT(n) {
  var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.getElementById("pTable");
  switching = true;
  dir = "asc";
  while (switching) {
    switching = false;
    rows = table.rows;
    for (i = 1; i < (rows.length - 1); i++) {
      shouldSwitch = false;
      x = rows[i].getElementsByTagName("TD")[n];
      y = rows[i+1].getElementsByTagName("TD")[n];
      let xV = x.innerText.replace(/[ %]/g, '').replace(',', '.');
      let yV = y.innerText.replace(/[ %]/g, '').replace(',', '.');
      let xN = parseFloat(xV);
      let yN = parseFloat(yV);
      if (!isNaN(xN) && !isNaN(yN)) {
        if (dir == "asc") { if (xN > yN) { shouldSwitch = true; break; } }
        else { if (xN < yN) { shouldSwitch = true; break; } }
      } else {
        if (dir == "asc") { if (x.innerText.toLowerCase() > y.innerText.toLowerCase()) { shouldSwitch = true; break; } }
        else { if (x.innerText.toLowerCase() < y.innerText.toLowerCase()) { shouldSwitch = true; break; } }
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
"""

# Zobrazení přes components.html zajistí, že JavaScript poběží v izolovaném, ale funkčním okně
import streamlit.components.v1 as components
components.html(html_code, height=650, scrolling=False)

# Sidebar sumář
st.sidebar.divider()
st.sidebar.metric("Celková hodnota", format_cz(df["Hodnota CZK"].sum(), 0) + " CZK")
st.sidebar.metric("Roční dividendy", format_cz(df["Div. celkem CZK"].sum(), 0) + " CZK")
st.sidebar.metric("Celkový zisk", format_cz(df["Hodnota CZK"].sum() - df["Inv_CZK"].sum(), 0) + " CZK")
