import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- KONFIGURACE ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- STYLY (Maximální huštění) ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .main .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
    .portfolio-table th { background-color: #000; color: white; padding: 4px 6px; text-align: right; position: sticky; top: 0; z-index: 10; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 2px 6px; border-bottom: 1px solid #eee; line-height: 1.1; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    return {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}

@st.cache_data(ttl=600)
def load_full_market_data(tickers):
    data = {}
    for t in tickers + ["^GSPC", "^GDAXI"]:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="1y")
            cal = tk.calendar
            next_earn = cal.get('Earnings Date', [None])[0] if isinstance(cal, dict) else None
            data[t] = {
                "price": h['Close'].iloc[-1],
                "div": tk.info.get('trailingAnnualDividendRate', 0) or 0,
                "history": h['Close'],
                "earnings": next_earn.strftime('%d.%m.%Y') if next_earn else "-"
            }
        except: data[t] = {"price": 0, "div": 0, "history": pd.Series(), "earnings": "-"}
    return data

try:
    df_sheet = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',','.').str.replace(' ',''), errors='coerce').fillna(0)
    
    fx = get_fx_rates()
    m_data = load_full_market_data(df_sheet["Ticker"].unique().tolist())

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika portfolia", "🧠 Strategie", "📈 Výkonnost", "⚙️ Ostatní"])

    processed = []
    for _, r in df_sheet.iterrows():
        t, m_cur = r["Ticker"], str(r["Měna"]).strip()
        info = m_data.get(t, {})
        rate = fx.get(m_cur, 1.0)
        val_czk = r["Ks"] * info["price"] * rate
        processed.append({
            "Název": r["Název"], "Ticker": t, "Sektor": r["Obor (Sektor)"], "Měna": m_cur,
            "Ks": r["Ks"], "TC": info["price"], "Hodnota CZK": val_czk,
            "Charakter": r["Charakter"], "Sentiment": r["Sentiment"],
            "Div_ks": info["div"], "Div_total": r["Ks"] * info["div"] * rate,
            "Earnings": info["earnings"], "Standard": r["Průměrná nákupní cena"], "Rate": rate,
            "History": info["history"]
        })
    df_p = pd.DataFrame(processed)

    # --- GLOBÁLNÍ FILTR OBDOBÍ ---
    st.sidebar.divider()
    time_frame = st.sidebar.selectbox("Srovnávací období:", ["1 rok", "1 měsíc", "1 týden", "1 den"], index=0)
    days = {"1 rok": 252, "1 měsíc": 21, "1 týden": 5, "1 den": 1}[time_frame]

    if page == "💰 Přehled":
        html = "<table class='portfolio-table'><thead><tr><th>Název</th><th class='num'>KS</th><th class='num'>Cena</th><th class='num'>Hodnota CZK</th><th class='num'>Zisk %</th><th class='num'>Div/ks</th><th class='num'>Div celkem</th><th>Earnings</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            ref = r["History"].iloc[-days] if len(r["History"]) > days else r["Standard"]
            zisk = ((r["TC"] - ref) / ref * 100) if ref > 0 else 0
            z_c = "pos" if zisk >= 0 else "neg"
            html += f"<tr><td class='stock-name'>{r['Název']}</td><td class='num'>{r['Ks']:.0f}</td><td class='num'>{format_cz(r['TC'])}</td><td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td><td class='num {z_c}'>{zisk:.2f} %</td><td class='num'>{format_cz(r['Div_ks'])}</td><td class='num'>{format_cz(r['Div_total'], 0)}</td><td>{r['Earnings']}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "🖼️ Grafika portfolia":
        fig = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor', 'Název'], values='Hodnota CZK', color='Sektor')
        fig.update_traces(textinfo="label+percent entry", textfont_size=14)
        fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=700)
        st.plotly_chart(fig, use_container_width=True)

    elif page == "🧠 Strategie":
        for field in ['Charakter', 'Sentiment']:
            fig = px.bar(df_p, x=field, y='Hodnota CZK', color='Název', barmode='stack', text='Název')
            fig.update_layout(showlegend=False, height=450, title=f"Rozložení: {field}")
            st.plotly_chart(fig, use_container_width=True)

    elif page == "📈 Výkonnost":
        st.subheader("Benchmark: Srovnání vývoje (%)")
        target = st.selectbox("Co srovnat s indexem?", ["Celé Portfolio"] + df_p["Název"].tolist())
        index_choice = st.radio("Srovnávací index:", ["S&P 500 (USA)", "DAX 40 (GER)"], horizontal=True)
        idx_ticker = "^GSPC" if "S&P" in index_choice else "^GDAXI"
        
        # Výpočet procentuálních řad
        idx_h = m_data[idx_ticker]["history"].tail(days)
        idx_norm = (idx_h / idx_h.iloc[0] - 1) * 100
        
        if target == "Celé Portfolio":
            # Zjednodušená simulace portfolia (vážený průměr historií)
            port_h = pd.Series(0, index=idx_h.index)
            for _, r in df_p.iterrows():
                if not r["History"].empty:
                    s = r["History"].tail(days).reindex(idx_h.index, method='ffill')
                    port_h += (s / s.iloc[0] - 1) * 100 * (r["Hodnota CZK"] / df_p["Hodnota CZK"].sum())
            y_data = port_h
        else:
            row = df_p[df_p["Název"] == target].iloc[0]
            s = row["History"].tail(days).reindex(idx_h.index, method='ffill')
            y_data = (s / s.iloc[0] - 1) * 100

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=idx_h.index, y=idx_norm, name=index_choice, line=dict(color='gray', dash='dash')))
        fig.add_trace(go.Scatter(x=idx_h.index, y=y_data, name=target, line=dict(color='green', width=3)))
        fig.update_layout(height=500, yaxis_suffix=" %", margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)
        
        # Srovnání pořízení vs současnost
        st.divider()
        df_p["Investice CZK"] = df_p["Ks"] * df_p["Standard"] * df_p["Rate"]
        df_melt = df_p.melt(id_vars=['Název'], value_vars=['Hodnota CZK', 'Investice CZK'], var_name='Typ', value_name='CZK')
        fig_bar = px.bar(df_melt, x='Název', y='CZK', color='Typ', barmode='group', color_discrete_map={'Hodnota CZK':'#28a745','Investice CZK':'#dc3545'})
        fig_bar.update_layout(height=400, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig_bar, use_container_width=True)

    elif page == "⚙️ Ostatní":
        st.subheader("Měnová expozice")
        df_curr = df_p.copy()
        # Speciální pravidlo pro VW (pokud obsahuje 'VOLKSWAGEN' v názvu nebo 'VOW3' v tickeru)
        df_curr.loc[df_curr['Název'].str.contains('VOLKSWAGEN', case=False), 'Měna'] = 'CZK'
        
        fig = px.sunburst(df_curr, path=['Měna', 'Název'], values='Hodnota CZK', color='Měna')
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Chyba: {e}")
