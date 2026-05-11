import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Investiční Portál", layout="wide")

@st.cache_data(ttl=300)
def get_live_data(_tickers): # To podtržítko je klíčové
    t_list = list(_tickers)
    return yf.download(t_list, period="5d", interval="1d", group_by='ticker', progress=False)

def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    unique_tickers = df_raw["Ticker"].unique()
    
    # Stažení dat
    market_raw = get_live_data(unique_tickers)
    fx = {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

    processed = []
    total_val = 0
    
    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        m_cur = str(r["Měna"]).strip()
        rate = fx.get(m_cur, 1.0)
        
        ks = pd.to_numeric(str(r['Ks']).replace(',','.').replace(' ',''), errors='coerce') or 0
        p_buy = pd.to_numeric(str(r['Průměrná nákupní cena']).replace(',','.').replace(' ',''), errors='coerce') or 0
        
        # Bezpečné vytažení ceny z MultiIndexu
        try:
            if len(unique_tickers) > 1:
                current_price = market_raw[t]['Close'].iloc[-1]
            else:
                current_price = market_raw['Close'].iloc[-1]
        except:
            current_price = p_buy
            
        val_czk = ks * current_price * rate
        total_val += val_czk

        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"],
            "Ks": ks, "Cena": current_price, "Nákupka": p_buy,
            "Hodnota CZK": val_czk,
            "Zisk %": ((current_price - p_buy) / p_buy * 100) if p_buy > 0 else 0
        })
    
    df_p = pd.DataFrame(processed)

    st.title("💰 Moje Portfolio (Live Check)")
    st.metric("Celková hodnota", f"{format_cz(total_val, 0)} CZK")
    
    st.dataframe(
        df_p.sort_values("Hodnota CZK", ascending=False),
        column_config={
            "Zisk %": st.column_config.NumberColumn(format="%.2f %%"),
            "Hodnota CZK": st.column_config.NumberColumn(format="%.0f CZK"),
            "Cena": st.column_config.NumberColumn(format="%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"Chyba: {e}")
