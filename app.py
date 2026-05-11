import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- 1. MINIMALISTICKÝ STAHOVAČ ---
@st.cache_data(ttl=300)
def get_live_data(tickers):
    # Stáhneme vše najednou jedním požadavkem - mnohem efektivnější a Yahoo to má raději
    data = yf.download(list(tickers), period="5d", interval="1d", group_by='ticker', progress=False)
    return data

# --- 2. FORMÁTOVÁNÍ ---
def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

# --- 3. LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    tickers = df_raw["Ticker"].unique()
    
    # Stáhneme tržní data
    market_raw = get_live_data(tickers)
    fx = {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

    processed = []
    total_val = 0
    
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        m_cur = str(r["Měna"]).strip()
        rate = fx.get(m_cur, 1.0)
        
        ks = pd.to_numeric(str(r['Ks']).replace(',','.').replace(' ',''), errors='coerce') or 0
        p_buy = pd.to_numeric(str(r['Průměrná nákupní cena']).replace(',','.').replace(' ',''), errors='coerce') or 0
        
        # Extrakce ceny z hromadného downloadu
        try:
            # Pokud je víc tickerů, yf.download vrací MultiIndex
            if len(tickers) > 1:
                current_price = market_raw[t]['Close'].iloc[-1]
            else:
                current_price = market_raw['Close'].iloc[-1]
        except:
            current_price = p_buy # Fallback pouze pokud fakt nic nepřijde
            
        val_czk = ks * current_price * rate
        total_val += val_czk

        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"],
            "Ks": ks, "Tržní cena": current_price, "Nákupka": p_buy,
            "Hodnota CZK": val_czk,
            "Změna %": ((current_price - p_buy) / p_buy * 100) if p_buy > 0 else 0,
            "Měna": m_cur
        })
    
    df_p = pd.DataFrame(processed)

    # --- JEDNODUCHÝ DISPLAY ---
    st.title("💰 Moje Portfolio")
    st.metric("Celková hodnota", f"{format_cz(total_val, 0)} CZK")
    
    tab1, tab2 = st.tabs(["Tabulka", "Grafy"])
    
    with tab1:
        st.dataframe(
            df_p[["Název", "Ticker", "Ks", "Nákupka", "Tržní cena", "Změna %", "Hodnota CZK"]].sort_values("Hodnota CZK", ascending=False),
            column_config={
                "Změna %": st.column_config.NumberColumn(format="%.2f %%"),
                "Hodnota CZK": st.column_config.NumberColumn(format="%.0f"),
                "Tržní cena": st.column_config.NumberColumn(format="%.2f"),
                "Nákupka": st.column_config.NumberColumn(format="%.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

    with tab2:
        fig = px.pie(df_p, values='Hodnota CZK', names='Sektor', title="Rozložení podle sektorů")
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Chyba: {e}")
