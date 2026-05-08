import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Portfolio", layout="wide")

# --- STYLOVÁNÍ ---
st.markdown("""
<style>
    /* O něco větší horní okraj, aby hlavička nebyla oříznutá */
    .block-container { padding-top: 3.5rem !important; padding-bottom: 0rem !important; }
    
    /* Vylepšení vzhledu tabulky */
    [data-testid="stDataFrame"] {
        border: 1px solid #e6e9ef;
        border-radius: 4px;
    }
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
                diffs[t] = h["Close"].iloc[-1] - h["Close"].iloc[-2]
            else: curr[t], diffs[t] = 0, 0
        except: curr[t], diffs[t] = 0, 0
    return curr, diffs

with st.spinner('Aktualizuji data...'):
    prices, diffs = fetch_data(df["Ticker"].tolist())
    df["TC"] = df["Ticker"].map(prices)
    df["_diff"] = df["Ticker"].map(diffs)

fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
df["Hodnota CZK"] = df.apply(lambda x: x["KS"] * x["TC"] * fx.get(x["Měna"], 1.0), axis=1)
df["Inv_CZK"] = df.apply(lambda x: x["KS"] * x[col_price] * fx.get(x["Měna"], 1.0), axis=1)
df["Zisk %"] = ((df["TC"] - df[col_price]) / df[col_price] * 100)
df["Div. celkem CZK"] = df.apply(lambda x: x["KS"] * x["Dividenda"] * fx.get(x["Měna"], 1.0), axis=1)

# Seřazení a výběr sloupců
final_df = df[["Název", "Ticker", "KS", "TC", "Hodnota CZK", "Zisk %", "Dividenda", "Div. celkem CZK", "_diff"]].copy()

# --- STYLIZACE ---
def apply_styles(styler):
    # Barva Zisku
    styler.map(lambda v: f'color: {"#28a745" if v > 0 else "#dc3545"}; font-weight: bold', subset=['Zisk %'])
    # Barva TC podle schovaného _diff
    styler.apply(lambda row: [f'color: {"#28a745" if row["_diff"] >= 0 else "#dc3545"}; font-weight: bold' if i == 3 else '' for i, v in enumerate(row)], axis=1)
    # Tučné názvy, KS a Hodnoty
    styler.map(lambda v: 'font-weight: bold', subset=['KS', 'Hodnota CZK', 'Název'])
    # Formátování čísel
    styler.format({
        'KS': '{:,.0f}', 'TC': '{:,.2f}', 'Hodnota CZK': '{:,.0f}',
        'Zisk %': '{:,.2f} %', 'Dividenda': '{:,.2f}', 'Div. celkem CZK': '{:,.0f}'
    }, decimal=',', thousands=' ')
    return styler

# --- ZOBRAZENÍ TABULKY ---
# Použití column_config k absolutnímu skrytí _diff a úpravě šířek
st.dataframe(
    apply_styles(final_df.style),
    use_container_width=True,
    height=910, # Zvýšeno tak, aby 25 řádků bylo vidět bez scrollování
    hide_index=True,
    column_config={
        "_diff": None, # Toto sloupec totálně vymaže ze zobrazení
        "Název": st.column_config.TextColumn(width="medium"),
        "Ticker": st.column_config.TextColumn(width="small"),
        "KS": st.column_config.NumberColumn(width="small"),
        "TC": st.column_config.NumberColumn(width="small"),
        "Hodnota CZK": st.column_config.NumberColumn(width="medium"),
        "Zisk %": st.column_config.NumberColumn(width="small"),
        "Dividenda": st.column_config.NumberColumn(width="small"),
        "Div. celkem CZK": st.column_config.NumberColumn(width="medium"),
    }
)

# Sidebar metriky
st.sidebar.divider()
total_val = final_df["Hodnota CZK"].sum()
st.sidebar.metric("Celková hodnota", f"{total_val:,.0f} CZK".replace(",", " "))
st.sidebar.metric("Roční dividendy", f"{final_df['Div. celkem CZK'].sum():,.0f} CZK".replace(",", " "))
st.sidebar.metric("Celkový zisk", f"{(total_val - df['Inv_CZK'].sum()):,.0f} CZK".replace(",", " "))
