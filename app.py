import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- 1. FUNKCE ---
def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    return {"CZK": 1.0, "EUR": 25.1, "USD": 23.4, "GBP": 29.8, "DKK": 3.36}

@st.cache_data(ttl=600)
def load_market_data(_tickers):
    data = {}
    all_symbols = [str(t).strip() for t in _tickers if str(t).strip()]
    all_symbols += ["^GSPC", "^GDAXI"]
    try:
        raw_hist = yf.download(all_symbols, period="2y", interval="1d", group_by='ticker', progress=False, actions=True)
    except: raw_hist = pd.DataFrame()
    for t in all_symbols:
        try:
            cp, dv, hist = 0, 0, pd.Series()
            if not raw_hist.empty:
                t_df = raw_hist[t].dropna(subset=['Close']) if len(all_symbols) > 1 else raw_hist.dropna(subset=['Close'])
                if not t_df.empty:
                    cp = t_df['Close'].iloc[-1]
                    hist = t_df['Close'].ffill()
                    # Odstranění časové zóny pro bezpečné porovnávání napříč trhy
                    if hist.index.tz is not None:
                        hist.index = hist.index.tz_localize(None)
                    if 'Dividends' in t_df.columns:
                        dv = t_df[t_df.index >= (datetime.now() - timedelta(days=365))]['Dividends'].sum()
            data[t] = {"price": cp, "div": dv, "history": hist}
        except: data[t] = {"price": 0, "div": 0, "history": pd.Series()}
    return data

# --- 2. LOGIKA ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
try:
    df_raw = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    m_data = load_market_data(df_raw["Ticker"].unique())
    fx = get_fx_rates()

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "⚙️ Ostatní"])
    view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
    
    time_frame = st.sidebar.selectbox("Období:", ["1 den", "1 týden", "1 měsíc", "1 rok", "Od nákupu"], index=0)
    graph_days = 252 if time_frame == "Od nákupu" else {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[time_frame]

    processed = []
    total_val, total_ref = 0, 0
    today = datetime.now().date()

    for _, r in df_raw.iterrows():
        t = str(r["Ticker"]).strip()
        info = m_data.get(t, {"price": 0, "div": 0, "history": pd.Series()})
        rate = fx.get(str(r["Měna"]).strip(), 1.0)
        ks = pd.to_numeric(str(r['Ks']).replace(',','.'), errors='coerce') or 0
        p_std = pd.to_numeric(str(r['Průměrná nákupní cena']).replace(',','.'), errors='coerce') or 0
        p_opt = pd.to_numeric(str(r['Nákupní cena včetně opcí']).replace(',','.'), errors='coerce') or 0
        
        ref_buy = p_std if view_mode == "Standard" else p_opt
        curr_price = info["price"]
        val_czk = ks * curr_price * rate
        hist = info["history"]
        
        if time_frame == "Od nákupu":
            ref_price = ref_buy
        else:
            target_days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[time_frame]
            ref_price = hist.iloc[-(target_days + 1)] if (not hist.empty and len(hist) > target_days) else ref_buy
            
        total_val += val_czk
        total_ref += (ks * ref_price * rate)
        
        div_ks = info["div"]
        
        # Zpracování ručního Earnings sloupce z tabulky
        earn_dt_str = "-"
        days_to = "-"
        
        if 'Earnings' in r and pd.notna(r['Earnings']):
            raw_val = str(r['Earnings']).strip()
            if raw_val and raw_val != "-":
                try:
                    parsed_date = pd.to_datetime(raw_val, dayfirst=True).date()
                    earn_dt_str = parsed_date.strftime('%d.%m.%Y')
                    days_to = (parsed_date - today).days
                except:
                    earn_dt_str = raw_val
        
        processed.append({
            "Název": r['Název'], "KS": ks, "Cena": curr_price, "CZK": val_czk, 
            "Zisk %": ((curr_price - ref_price)/ref_price*100) if ref_price > 0 else 0,
            "Div/ks": div_ks, "Div celkem": ks * div_ks * rate, 
            "Earnings": earn_dt_str, "Dní": days_to, 
            "History": hist, "RefPrice": ref_price,
            "Měna": str(r["Měna"]).strip()
        })
    df_p = pd.DataFrame(processed)

    st.sidebar.divider()
    st.sidebar.metric("Celkem CZK", f"{format_cz(total_val, 0)} CZK")
    diff = total_val - total_ref
    st.sidebar.metric("Změna", f"{format_cz(diff, 0)} CZK", f"{(diff/total_ref*100 if total_ref>0 else 0):.2f} %")

    if page == "💰 Přehled":
        df_show = df_p[["Název", "KS", "Cena", "CZK", "Zisk %", "Div/ks", "Div celkem", "Earnings", "Dní"]].copy()
        df_show = df_show.sort_values("CZK", ascending=False)

        def style_rows(row):
            styles = [''] * len(row)
            orig_row = df_p[df_p['Název'] == row['Název']].iloc[0]
            styles[2] = 'color: #2e7d32; font-weight: bold;' if orig_row['Cena'] >= orig_row['RefPrice'] else 'color: #d32f2f; font-weight: bold;'
            styles[4] = 'color: #2e7d32; font-weight: bold;' if row['Zisk %'] >= 0 else 'color: #d32f2f; font-weight: bold;'
            
            try:
                days = int(row['Dní'])
                if days < 0:
                    styles[8] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center;'
                elif days <= 10:
                    styles[8] = 'background-color: #ffe0b2; color: #e65100; font-weight: bold; text-align: center;'
            except: pass
            return styles

        styled_df = df_show.style.apply(style_rows, axis=1)\
            .format({
                "KS": "{:,.0f}",
                "Cena": lambda x: format_cz(x),
                "CZK": lambda x: format_cz(x, 0),
                "Zisk %": "{:,.2f}%",
                "Div/ks": lambda x: format_cz(x),
                "Div celkem": lambda x: format_cz(x, 0),
                "Dní": lambda x: f"{x}" if isinstance(x, int) else "-"
            })

        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=600)

    elif page == "🖼️ Grafika":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Název'], values='CZK')
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:,.0f} CZK<br>%{percentRoot:.1%}")
        fig.update_layout(height=800)
        st.plotly_chart(fig, use_container_width=True)

    elif page == "📈 Výkonnost":
        idx_t = "^GSPC" if st.radio("Index:", ["S&P 500", "DAX 40"], horizontal=True) == "S&P 500" else "^GDAXI"
        sel = st.multiselect("Srovnání:", df_p["Název"].tolist())
        
        idx_h = m_data[idx_t]["history"].tail(graph_days + 1)
        
        if not idx_h.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=idx_h.index, y=(idx_h/idx_h.iloc[0]-1)*100, name="Index", line=dict(dash='dash')))
            port_h = pd.Series(0.0, index=idx_h.index)
            
            for _, r in df_p.iterrows():
                if not r["History"].empty:
                    h = r["History"].reindex(idx_h.index, method='ffill')
                    if not h.empty and pd.notna(h.iloc[0]) and h.iloc[0] != 0:
                        port_h += (h/h.iloc[0]-1)*100 * (r["CZK"]/total_val)
                        if r["Název"] in sel: 
                            fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=r["Název"]))
            
            fig.add_trace(go.Scatter(x=port_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4)))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Nepodařilo se načíst historii pro vybraný index.")

    elif page == "⚙️ Ostatní":
        # Opravená a vyčištěná mapa barev
        color_map = {
            'CZK': '#29b6f6',
            'EUR': '#0d47a1',
            'USD': '#d32f2f'
        }
        fig = px.sunburst(
            df_p, 
            path=['Měna', 'Název'], 
            values='CZK',
            color='Měna',
            color_discrete_map=color_map
        )
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{percentParent:.1%}",
            insidetextorientation='radial'
        )
        fig.update_layout(height=700)
        st.plotly_chart(fig, use_container_width=True)
        
except Exception as e: st.error(f"Kritická chyba: {e}")
