import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Live Portfolio", layout="wide")

# --- KONFIGURACE PROPOJENÍ ---
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
    .ticker-sub { color: gray; font-size: 11px; font-weight: normal; }
    tr:hover { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

def format_cz(value, decimals=2):
    try:
        if pd.isna(value): return "0"
        return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

# --- AUTOMATICKÉ KURZY ---
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

# --- NAČÍTÁNÍ DAT (MOZEK APLIKACE) ---
@st.cache_data(ttl=300)
def load_all_data():
    df = pd.read_csv(SHEET_URL)
    df = df.dropna(subset=['Ticker'])
    
    # Očištění číselných hodnot z Google Sheetu
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce').fillna(0)

    tickers = df["Ticker"].unique().tolist()
    market_data = {}
    historicals = {}
    
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            # Získáme cenu a dividendu
            price = tk.info.get('currentPrice')
            div = tk.info.get('trailingAnnualDividendRate') or (tk.info.get('dividendYield', 0) * (price or 0))
            h = tk.history(period="5d") # Stačí nám pár dní pro denní změnu
            
            market_data[t] = {
                "price": price or (h['Close'].iloc[-1] if not h.empty else 0),
                "div": div or 0.0,
                "diff": (h['Close'].iloc[-1] - h['Close'].iloc[-2]) if len(h) > 1 else 0,
                "last_close": h['Close'].iloc[-2] if len(h) > 1 else price
            }
            historicals[t] = h
        except:
            market_data[t] = {"price": 0, "div": 0, "diff": 0, "last_close": 0}
            
    return df, market_data

# --- VÝPOČTY A ZOBRAZENÍ ---
try:
    df_sheet, market_info = load_all_data()
    fx = get_fx_rates()

    # Sidebar ovladače
    st.sidebar.title("OVLÁDACÍ PANEL")
    view_mode = st.sidebar.radio("Nákupní cena:", ["Standardní", "S opcemi"])
    sort_col = st.sidebar.selectbox("Seřadit podle:", ["Název", "Hodnota CZK", "Zisk %"], index=1)
    
    col_price_key = "Průměrná nákupní cena" if view_mode == "Standardní" else "Nákupní cena včetně opcí"
    
    processed_rows = []
    for _, r in df_sheet.iterrows():
        t = r["Ticker"]
        m = market_info.get(t, {})
        
        # Logika pro High Templar Tech
        display_name = "High Templar Tech" if t in ["QD", "HTT"] else r["Název"]
        
        curr = str(r["Měna"]).strip() if pd.notna(r["Měna"]) else "USD"
        rate = fx.get(curr, 1.0)
        
        val_czk = r["Ks"] * m["price"] * rate
        inv_czk = r["Ks"] * r[col_price_key] * rate
        zisk_pc = ((m["price"] - r[col_price_key]) / r[col_price_key] * 100) if r[col_price_key] != 0 else 0
        
        processed_rows.append({
            "Název": display_name,
            "Ticker": t,
            "Ks": r["Ks"],
            "TC": m["price"],
            "Hodnota CZK": val_czk,
            "Zisk %": zisk_pc,
            "Dividenda": m["div"],
            "Div celkem CZK": r["Ks"] * m["div"] * rate,
            "Diff": m["diff"],
            "Investice": inv_czk
        })

    df_final = pd.DataFrame(processed_rows).sort_values(sort_col, ascending=False)

    # Horní metriky v Sidebaru
    total_val = df_final["Hodnota CZK"].sum()
    total_inv = df_final["Investice"].sum()
    st.sidebar.divider()
    st.sidebar.metric("Celková hodnota", format_cz(total_val, 0) + " CZK")
    st.sidebar.metric("Celkový zisk/ztráta", format_cz(total_val - total_inv, 0) + " CZK")
    st.sidebar.write(f"Aktuální kurzy: USD {fx['USD']:.2f} | EUR {fx['EUR']:.2f}")

    # Vykreslení hlavní tabulky
    html = "<table class='portfolio-table'><thead><tr>"
    html += "<th>Název titulu</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th>"
    html += "<th class='num'>Zisk %</th><th class='num'>Dividenda (ks)</th><th class='num'>Roční div. CZK</th>"
    html += "</tr></thead><tbody>"

    for _, r in df_final.iterrows():
        z_class = "pos" if r["Zisk %"] >= 0 else "neg"
        c_class = "pos" if r["Diff"] >= 0 else "neg"
        
        html += f"<tr>"
        html += f"<td class='stock-name'>{r['Název']}<br><span class='ticker-sub'>{r['Ticker']}</span></td>"
        html += f"<td class='num'>{format_cz(r['Ks'], 0)}</td>"
        html += f"<td class='num {c_class}'>{format_cz(r['TC'])}</td>"
        html += f"<td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td>"
        html += f"<td class='num {z_class}'>{format_cz(r['Zisk %'])} %</td>"
        html += f"<td class='num'>{format_cz(r['Dividenda'])}</td>"
        html += f"<td class='num'>{format_cz(r['Div celkem CZK'], 0)}</td>"
        html += "</tr>"

    html += "</tbody></table>"
    st.write(html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Došlo k chybě při zpracování tabulky: {e}")
