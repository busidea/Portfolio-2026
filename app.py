import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Portfolio", layout="wide")

# CSS pro stylování tabulky a odstranění indexů
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .stDataFrame td { font-weight: 500; }
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

# --- FUNKCE PRO HISTORICKÁ DATA ---
@st.cache_data(ttl=3600)
def fetch_portfolio_data(tickers):
    hist_prices = {}
    current_prices = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="1y")
            if not h.empty:
                hist_prices[t] = h
                current_prices[t] = h["Close"].iloc[-1]
            else:
                current_prices[t] = 0.0
        except:
            current_prices[t] = 0.0
    return current_prices, hist_prices

# --- LOGIKA ---
df = get_data()

# SIDEBAR
st.sidebar.title("PORTFOLIO")
view_mode = st.sidebar.radio("Nákupní cena:", ["Standardní", "S opcemi"])
time_frame = st.sidebar.selectbox("Změna za období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"])
col_price = "Cena_Std" if view_mode == "Standardní" else "Cena_Opce"

with st.spinner('Načítám...'):
    curr_prices, hist_data = fetch_portfolio_data(df["Ticker"].tolist())
    df["Aktuální_Cena"] = df["Ticker"].map(curr_prices)

# Výpočet historické změny
def calc_change(row):
    t = row["Ticker"]
    if t not in hist_data or hist_data[t].empty: return 0.0
    h = hist_data[t]["Close"]
    
    if time_frame == "1 den": ref_price = h.iloc[-2] if len(h)>1 else h.iloc[-1]
    elif time_frame == "1 týden": ref_price = h.iloc[-5] if len(h)>5 else h.iloc[0]
    elif time_frame == "1 měsíc": ref_price = h.iloc[-21] if len(h)>21 else h.iloc[0]
    elif time_frame == "1 rok": ref_price = h.iloc[0]
    else: ref_price = row[col_price] # Od počátku
    
    return ((row["Aktuální_Cena"] - ref_price) / ref_price) * 100 if ref_price != 0 else 0

df["Zisk_%"] = df.apply(calc_change, axis=1)

# Měny (fixní pro stabilitu)
fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
df["Hodnota_CZK"] = df.apply(lambda x: x["Ks"] * x["Aktuální_Cena"] * fx.get(x["Měna"], 1.0), axis=1)
df["Investice_CZK"] = df.apply(lambda x: x["Ks"] * x[col_price] * fx.get(x["Měna"], 1.0), axis=1)

# Metriky do Sidebar
st.sidebar.divider()
total_val = df["Hodnota_CZK"].sum()
total_profit = total_val - df["Investice_CZK"].sum()
st.sidebar.metric("Celková hodnota", f"{total_val:,.0f} CZK".replace(",", " "))
st.sidebar.metric("Celkový zisk", f"{total_profit:,.0f} CZK".replace(",", " "), f"{(total_profit/df['Investice_CZK'].sum()*100):.2f}%")

# --- HLAVNÍ TABULKA ---
# Formátování pro zobrazení
disp_df = df[["Název", "Ticker", "Ks", "Aktuální_Cena", "Zisk_%", "Hodnota_CZK"]].copy()

# Úprava názvů na tučné pro Markdown (použijeme st.dataframe s column_config)
st.dataframe(
    disp_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Název": st.column_config.TextColumn("Název", help="Tučně v seznamu", width="medium"),
        "Ks": st.column_config.NumberColumn("Kusy", format="%d"),
        "Aktuální_Cena": st.column_config.NumberColumn("Cena", format="%.2f"),
        "Zisk_%": st.column_config.NumberColumn(f"Zisk ({time_frame})", format="%.2f %%"),
        "Hodnota_CZK": st.column_config.NumberColumn("Hodnota CZK", format="%d")
    }
)
