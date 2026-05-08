import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Portfolio 2026", layout="wide")

# --- KONFIGURACE DAT ---
@st.cache_data(ttl=3600)
def get_portfolio_base():
    # Název, Ticker, Ks, Sektor, Měna, Cena_Std, Cena_Opce
    data = [
        ["Heidelberg Materials", "HEI.DE", 800, "Stavební materiály", "EUR", 37.45, 28.4],
        ["HEIJMANS", "HEIJ.AS", 1162, "Stavebnictví", "EUR", 7.63, 3.77],
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

# --- LIVE KURZY MĚN ---
@st.cache_data(ttl=3600)
def get_fx_rates():
    rates = {"CZK": 1.0}
    for m in ["EUR", "USD", "GBP", "DKK"]:
        try:
            pair = f"{m}CZK=X"
            data = yf.download(pair, period="1d", interval="1m", progress=False)
            rates[m] = data["Close"].iloc[-1]
        except:
            # Záložní fixní kurzy pro případ výpadku Yahoo
            backup = {"EUR": 25.3, "USD": 23.6, "GBP": 29.8, "DKK": 3.4}
            rates[m] = backup[m]
    return rates

# --- LIVE CENY AKCIÍ ---
def fetch_prices(tickers):
    data = yf.download(tickers, period="1d", progress=False)["Close"]
    # Pokud je stažen jen jeden ticker, yfinance vrátí Series místo DataFrame
    if len(tickers) == 1:
        return {tickers[0]: data.iloc[-1]}
    return {t: data[t].iloc[-1] for t in tickers}

# --- APLIKACE ---
df = get_portfolio_base()
fx = get_fx_rates()

st.title("📈 Moje Portfolio 2026")

view_mode = st.sidebar.radio("Metrika nákupní ceny:", ["Standardní", "Včetně opcí"])
col_price = "Cena_Std" if view_mode == "Standardní" else "Cena_Opce"

# Načtení cen
with st.spinner('Stahuji aktuální data z burz...'):
    prices = fetch_prices(df["Ticker"].tolist())
    df["Aktuální_Cena"] = df["Ticker"].map(prices)

# Výpočty
df["Hodnota_v_Měně"] = df["Ks"] * df["Aktuální_Cena"]
df["Hodnota_CZK"] = df.apply(lambda x: x["Hodnota_v_Měně"] * fx.get(x["Měna"], 1), axis=1)
df["Investice_CZK"] = df.apply(lambda x: x["Ks"] * x[col_price] * fx.get(x["Měna"], 1), axis=1)
df["Zisk_CZK"] = df["Hodnota_CZK"] - df["Investice_CZK"]
df["Zisk_Proc"] = (df["Zisk_CZK"] / df["Investice_CZK"]) * 100

# Horní metriky
m1, m2, m3, m4 = st.columns(4)
m1.metric("Celková hodnota", f"{df['Hodnota_CZK'].sum():,.0f} CZK")
total_profit = df['Zisk_CZK'].sum()
total_profit_perc = (total_profit / df['Investice_CZK'].sum()) * 100
m2.metric("Celkový zisk/ztráta", f"{total_profit:,.0f} CZK", f"{total_profit_perc:.2f}%")
m3.metric("Nejvýnosnější titul", df.loc[df['Zisk_Proc'].idxmax()]['Název'], f"{df['Zisk_Proc'].max():.1f}%")
m4.metric("Dnešní kurz EUR", f"{fx['EUR']:.2f} CZK")

# Grafy
c1, c2 = st.columns(2)
with c1:
    fig_pie = px.pie(df, values='Hodnota_CZK', names='Sektor', title="Rozložení dle sektorů", hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)
with c2:
    fig_profit = px.bar(df.sort_values("Zisk_CZK"), x="Zisk_CZK", y="Název", orientation='h',
                         title="Zisk / Ztráta v CZK dle titulů",
                         color="Zisk_CZK", color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_profit, use_container_width=True)

# Tabulka
st.subheader("Detailní přehled pozic")
def color_profit(val):
    color = 'green' if val > 0 else 'red'
    return f'color: {color}'

st.dataframe(df[["Název", "Sektor", "Ks", "Měna", "Aktuální_Cena", "Zisk_Proc", "Hodnota_CZK"]]
             .style.format({"Zisk_Proc": "{:.2f}%", "Hodnota_CZK": "{:,.0f} CZK", "Aktuální_Cena": "{:,.2f}"})
             .applymap(color_profit, subset=['Zisk_Proc']))

# Benchmarky
st.divider()
st.subheader("Srovnání s hlavními indexy (relativní vývoj)")
bench_choice = st.multiselect("Vyber indexy:", ["^GSPC", "^GDAXI", "PX.PR"], default=["^GSPC", "^GDAXI"])
if bench_choice:
    b_data = yf.download(bench_choice, period="1y")["Close"]
    b_data_norm = b_data / b_data.iloc[0] * 100
    st.line_chart(b_data_norm)
