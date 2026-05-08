import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Portfolio 2026", layout="wide")
# --- DATA --- (Aktualizovaný ticker pro Heijmans)
def get_data():
    data = [
        ["Heidelberg Materials", "HEI.DE", 800, "Stavební materiály", "EUR", 37.45, 28.4],
        ["HEIJMANS", "HEIJM.AS", 1162, "Stavebnictví", "EUR", 7.63, 3.77], # Změněno na HEIJM.AS
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

# --- FUNKCE PRO CENY --- (Robustnější verze)
def fetch_prices(tickers):
    prices = {}
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            # Zkusíme nejdřív fast_info (rychlé a stabilní)
            price = ticker_obj.fast_info['last_price']
            
            # Pokud fast_info selže nebo vrátí nesmysl, zkusíme historii
            if price is None or price == 0 or pd.isna(price):
                d = ticker_obj.history(period="1d")
                if not d.empty:
                    price = d["Close"].iloc[-1]
                else:
                    price = 0.0
            prices[t] = price
        except Exception as e:
            prices[t] = 0.0
    return prices
# --- HLAVNÍ LOGIKA ---
st.title("📈 Moje Portfolio 2026")

df = get_data()
view_mode = st.sidebar.radio("Metrika nákupní ceny:", ["Standardní", "Včetně opcí"])
col_price = "Cena_Std" if view_mode == "Standardní" else "Cena_Opce"

with st.spinner('Aktualizuji data...'):
    current_prices = fetch_prices(df["Ticker"].tolist())
    df["Aktuální_Cena"] = df["Ticker"].map(current_prices).astype(float)

# Fixní kurzy (dočasně pro stabilitu, než vyřešíme chybu s FX)
fx = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}

# Výpočty (bezpečnější syntaxe pro Pandas)
df["Hodnota_CZK"] = df.apply(lambda x: float(x["Ks"]) * float(x["Aktuální_Cena"]) * fx.get(x["Měna"], 1.0), axis=1)
df["Investice_CZK"] = df.apply(lambda x: float(x["Ks"]) * float(x[col_price]) * fx.get(x["Měna"], 1.0), axis=1)
df["Zisk_CZK"] = df["Hodnota_CZK"] - df["Investice_CZK"]
df.loc[:, "Zisk_Proc"] = (df["Zisk_CZK"] / df["Investice_CZK"]) * 100

# --- DASHBOARD ---
m1, m2 = st.columns(2)
total_val = df["Hodnota_CZK"].sum()
total_inv = df["Investice_CZK"].sum()
total_profit = total_val - total_inv
total_perc = (total_profit / total_inv) * 100 if total_inv != 0 else 0

m1.metric("Celková hodnota portfolia", f"{total_val:,.0f} CZK")
m2.metric("Celkový zisk / ztráta", f"{total_profit:,.0f} CZK", f"{total_perc:.2f}%")

st.divider()

c1, c2 = st.columns(2)
with c1:
    fig_pie = px.pie(df, values='Hodnota_CZK', names='Sektor', title="Sektorové rozložení")
    st.plotly_chart(fig_pie, use_container_width=True)
with c2:
    fig_bar = px.bar(df.sort_values("Zisk_CZK"), x="Zisk_CZK", y="Název", orientation='h', 
                     title="Zisk v CZK", color="Zisk_CZK", color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar, use_container_width=True)

st.subheader("Detailní tabulka")
st.dataframe(df[["Název", "Ticker", "Ks", "Aktuální_Cena", "Zisk_Proc", "Hodnota_CZK"]].style.format({
    "Zisk_Proc": "{:.2f}%", 
    "Hodnota_CZK": "{:,.0f}",
    "Aktuální_Cena": "{:.2f}"
}))
