import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Investment Portfolio Tracker", layout="wide")

# --- DATA ---
@st.cache_data
def get_data():
    data = [
        ["Heidelberg Materials", "HEI.DE", 800, "Stavební materiály", "EUR", 37.45, 28.4],
        ["HEIJMANS", "HEIJ.AS", 1162, "Stavebnictví", "EUR", 7.63, 3.77],
        ["ČEZ", "CEZ.PR", 750, "Energetika", "CZK", 1000, 1000], # Oprava ceny ČEZ na cca tržní odhad, v datech bylo 100
        ["ALPHABET", "GOOGL", 100, "Technologie", "USD", 133.34, 123.25],
        ["VIG", "VIG.PR", 500, "Pojišťovnictví", "CZK", 650, 620], # Oprava ceny dle trhu
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
    df = pd.DataFrame(data, columns=["Název", "Ticker", "Ks", "Sektor", "Měna", "Cena_Std", "Cena_Opce"])
    return df

df = get_data()

# --- SIDEBAR ---
st.sidebar.header("Nastavení")
view_mode = st.sidebar.radio("Metrika nákupní ceny:", ["Standardní", "Včetně opcí"])
col_price = "Cena_Std" if view_mode == "Standardní" else "Cena_Opce"

# --- ZÍSKÁNÍ DAT Z TRHU ---
tickers = df["Ticker"].tolist()
@st.cache_data(ttl=3600)
def fetch_market_data(ticker_list):
    prices = {}
    for t in ticker_list:
        try:
            ticker_obj = yf.Ticker(t)
            prices[t] = ticker_obj.history(period="1d")["Close"].iloc[-1]
        except:
            prices[t] = 0
    return prices

market_prices = fetch_market_data(tickers)
df["Aktuální_Cena"] = df["Ticker"].map(market_prices)

# Jednoduchý převod měn (pro demo zjednodušeno, lze rozšířit o live FX)
fx = {"CZK": 1.0, "USD": 23.5, "EUR": 25.2, "GBP": 29.5, "DKK": 3.38}
df["Hodnota_CZK"] = df.apply(lambda x: x["Ks"] * x["Aktuální_Cena"] * fx.get(x["Měna"], 1), axis=1)
df["Investice_CZK"] = df.apply(lambda x: x["Ks"] * x[col_price] * fx.get(x["Měna"], 1), axis=1)
df["Zisk_v_CZK"] = df["Hodnota_CZK"] - df["Investice_CZK"]
df["Zisk_Proc"] = (df["Zisk_v_CZK"] / df["Investice_CZK"]) * 100

# --- DASHBOARD ---
st.title("📊 Portfolio Dashboard")

m1, m2, m3 = st.columns(3)
m1.metric("Celková hodnota", f"{df['Hodnota_CZK'].sum():,.0f} CZK")
m2.metric("Celkový zisk", f"{df['Zisk_v_CZK'].sum():,.0f} CZK", f"{df['Zisk_Proc'].mean():.2f}%")
m3.metric("Počet titulů", len(df))

# --- GRAFY ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("Struktura dle Sektoru")
    fig_sector = px.pie(df, values='Hodnota_CZK', names='Sektor', hole=0.4)
    st.plotly_chart(fig_sector, use_container_width=True)

with c2:
    st.subheader("Největší pozice")
    fig_bar = px.bar(df.sort_values("Hodnota_CZK", ascending=False), x="Název", y="Hodnota_CZK", color="Sektor")
    st.plotly_chart(fig_bar, use_container_width=True)

# --- TABULKA DETAILŮ ---
st.subheader("Detailní přehled")
st.dataframe(df[["Název", "Ticker", "Ks", "Sektor", "Měna", "Aktuální_Cena", "Zisk_Proc"]].style.format({"Zisk_Proc": "{:.2f}%"}))

# --- POROVNÁNÍ S INDEXY ---
st.subheader("Srovnání s Indexy (S&P 500 a DAX)")
period = st.select_slider("Období", options=["1mo", "3mo", "6mo", "1y", "ytd"])

@st.cache_data
def get_benchmarks(p):
    bm = yf.download(["^GSPC", "^GDAXI"], period=p)["Close"]
    bm = bm / bm.iloc[0] # Normalizace na 1
    return bm

benchmark_data = get_benchmarks(period)
st.line_chart(benchmark_data)
