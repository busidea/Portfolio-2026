import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Investiční Portál", layout="wide")

# --- KONFIGURACE ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- STYLY ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    /* Přidání odsazení shora, aby nemizela hlavička */
    .main .block-container { padding-top: 4rem !important; padding-bottom: 2rem !important; }
    .portfolio-table { width: 100%; border-collapse: collapse; font-family: 'Segoe UI', sans-serif; font-size: 14px; margin-top: 10px; }
    .portfolio-table th { background-color: #000; color: white; padding: 10px; text-align: right; border: 1px solid #333; position: sticky; top: 0; }
    .portfolio-table th:first-child, .portfolio-table td:first-child { text-align: left !important; }
    .portfolio-table td { padding: 6px 10px; border-bottom: 1px solid #dee2e6; line-height: 1.3; }
    .num { text-align: right !important; }
    .pos { color: #28a745; font-weight: bold; }
    .neg { color: #dc3545; font-weight: bold; }
    .stock-name { font-weight: bold; color: #000; }
</style>
""", unsafe_allow_html=True)

def format_cz(value, decimals=2):
    try: return f"{float(value):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" " , " ")
    except: return "0"

@st.cache_data(ttl=3600)
def get_fx_rates():
    rates = {"CZK": 1.0, "EUR": 25.2, "USD": 23.5, "GBP": 29.5, "DKK": 3.38}
    for c, t in {"EUR":"EURCZK=X", "USD":"USDCZK=X", "GBP":"GBPCZK=X", "DKK":"DKKCZK=X"}.items():
        try:
            d = yf.Ticker(t).history(period="1d")
            if not d.empty: rates[c] = d['Close'].iloc[-1]
        except: pass
    return rates

@st.cache_data(ttl=300)
def load_full_data():
    df = pd.read_csv(SHEET_URL).dropna(subset=['Ticker'])
    for col in ['Ks', 'Průměrná nákupní cena', 'Nákupní cena včetně opcí']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',','.').str.replace(' ',''), errors='coerce').fillna(0)
    
    tickers = df["Ticker"].unique().tolist()
    market_data, historicals = {}, {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="1y")
            inf = tk.info
            cp = inf.get('currentPrice') or (h['Close'].iloc[-1] if not h.empty else 0)
            dv = inf.get('trailingAnnualDividendRate') or (inf.get('dividendYield', 0) * cp)
            market_data[t] = {"price": cp, "div": dv or 0.0, "diff": (h['Close'].iloc[-1] - h['Close'].iloc[-2]) if len(h) > 1 else 0}
            historicals[t] = h
        except: market_data[t] = {"price": 0, "div": 0, "diff": 0}
    return df, market_data, historicals

try:
    df_sheet, market_info, historicals = load_full_data()
    fx = get_fx_rates()

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("PŘEJÍT NA:", ["💰 Přehled", "📊 Grafy & Sektory", "🧠 Strategie", "📅 Dividendy"])

    # Příprava dat
    processed = []
    for _, r in df_sheet.iterrows():
        t = r["Ticker"]
        m = market_info.get(t, {})
        rate = fx.get(str(r["Měna"]).strip(), 1.0)
        processed.append({
            "Název": "High Templar Tech" if t in ["QD", "HTT"] else r["Název"],
            "Ticker": t, "Sektor": r["Obor (Sektor)"], "Ks": r["Ks"], "TC": m["price"],
            "Hodnota CZK": r["Ks"] * m["price"] * rate,
            "Charakter": r["Charakter"] if pd.notna(r["Charakter"]) else "Neuvedeno",
            "Sentiment": r["Sentiment"] if pd.notna(r["Sentiment"]) else "Neuvedeno",
            "Div_ks": m["div"],
            "Div celkem CZK": r["Ks"] * m["div"] * rate, 
            "Diff": m["diff"],
            "Standard": r["Průměrná nákupní cena"], "Opce": r["Nákupní cena včetně opcí"],
            "Rate": rate
        })
    df_p = pd.DataFrame(processed)

    if page == "💰 Přehled":
        st.sidebar.divider()
        view_mode = st.sidebar.radio("Cena:", ["Standard", "Opce"])
        time_frame = st.sidebar.selectbox("Období:", ["Od počátku", "1 rok", "1 měsíc", "1 týden", "1 den"], index=4)
        col_price = "Standard" if view_mode == "Standard" else "Opce"
        
        total_current = 0
        total_ref = 0
        for i, row in df_p.iterrows():
            h = historicals.get(row['Ticker'], pd.DataFrame())
            if time_frame == "1 den" and len(h) > 1: ref_u = h["Close"].iloc[-2]
            elif time_frame == "1 týden" and len(h) > 5: ref_u = h["Close"].iloc[-5]
            elif time_frame == "1 měsíc" and len(h) > 21: ref_u = h["Close"].iloc[-21]
            elif time_frame == "1 rok" and len(h) > 0: ref_u = h["Close"].iloc[0]
            else: ref_u = row[col_price]
            
            df_p.at[i, 'Zisk %'] = ((row['TC'] - ref_u) / ref_u * 100) if ref_u != 0 else 0
            total_current += row['Hodnota CZK']
            total_ref += (row['Ks'] * ref_u * row['Rate'])

        st.sidebar.metric("Celková hodnota", format_cz(total_current, 0) + " CZK")
        st.sidebar.metric(f"Změna ({time_frame})", format_cz(total_current - total_ref, 0) + " CZK")

        html = "<table class='portfolio-table'><thead><tr><th>Název titulu</th><th class='num'>KS</th><th class='num'>Tržní cena</th><th class='num'>Hodnota CZK</th><th class='num'>Zisk %</th><th class='num'>Div/ks</th><th class='num'>Roční div. CZK</th></tr></thead><tbody>"
        for _, r in df_p.sort_values("Hodnota CZK", ascending=False).iterrows():
            z_c = "pos" if r["Zisk %"] >= 0 else "neg"
            c_c = "pos" if r["Diff"] >= 0 else "neg"
            html += f"<tr><td class='stock-name'>{r['Název']}</td><td class='num'>{format_cz(r['Ks'], 0)}</td><td class='num {c_c}'>{format_cz(r['TC'])}</td><td class='num' style='font-weight:bold;'>{format_cz(r['Hodnota CZK'], 0)}</td><td class='num {z_c}'>{format_cz(r['Zisk %'])} %</td><td class='num'>{format_cz(r['Div_ks'])}</td><td class='num'>{format_cz(r['Div celkem CZK'], 0)}</td></tr>"
        st.write(html + "</tbody></table>", unsafe_allow_html=True)

    elif page == "📊 Grafy & Sektory":
        # Přidání paddingu shora pro graf
        st.write("<br>", unsafe_allow_html=True)
        df_p["Sektor_Label"] = "<b>" + df_p["Sektor"].astype(str) + "</b>"
        fig_tree = px.treemap(df_p, path=[px.Constant("Portfolio"), 'Sektor_Label', 'Název'], values='Hodnota CZK', color='Sektor')
        fig_tree.update_traces(textinfo="label+percent entry", hovertemplate='<b>%{label}</b><br>Hodnota: %{value:,.0f} CZK')
        fig_tree.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=400)
        st.plotly_chart(fig_tree, use_container_width=True)

        df_bar = df_p.copy()
        df_bar["Investice CZK"] = df_bar["Ks"] * df_bar["Standard"] * df_bar["Rate"]
        df_melt = df_bar.melt(id_vars=['Název'], value_vars=['Hodnota CZK', 'Investice CZK'], var_name='Typ', value_name='CZK')
        fig_bar = px.bar(df_melt, x='Název', y='CZK', color='Typ', barmode='group', color_discrete_map={'Hodnota CZK': '#28a745', 'Investice CZK': '#dc3545'})
        fig_bar.update_layout(margin=dict(t=40, l=10, r=10, b=10), height=350, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig_bar, use_container_width=True)

    elif page == "🧠 Strategie":
        st.write("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            # Skládaný sloupec pro Charakter
            fig1 = px.bar(df_p, x='Charakter', y='Hodnota CZK', color='Název', title="Skladba podle Charakteru", barmode='stack', text='Název')
            fig1.update_layout(showlegend=False, height=500, margin=dict(t=50, b=10))
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            # Skládaný sloupec pro Sentiment
            fig2 = px.bar(df_p, x='Sentiment', y='Hodnota CZK', color='Název', title="Skladba podle Sentimentu", barmode='stack', text='Název')
            fig2.update_layout(showlegend=False, height=500, margin=dict(t=50, b=10))
            st.plotly_chart(fig2, use_container_width=True)

except Exception as e:
    st.error(f"Chyba: {e}")
