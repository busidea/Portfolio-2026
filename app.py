import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 3.5rem; padding-bottom: 0rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    
    /* Vynucené zvýraznění prvního sloupce - Modrá a Tučná */
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { 
        font-weight: bold !important;
        color: #004080 !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def safe_date_diff(earn_date, today):
    if earn_date is None or earn_date == "-":
        return 999
    try:
        # Převedení datetime na date pro korektní odečet dnů
        if isinstance(earn_date, datetime):
            earn_date = earn_date.date()
        elif isinstance(earn_date, str):
            earn_date = pd.to_datetime(earn_date).date()
        return (earn_date - today).days
    except: 
        return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. NAČTENÍ DAT ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300) # Seznam tickerů kontrolujeme každých 5 minut
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except: return pd.DataFrame()

# SPECIÁLNÍ FUNKCE PRO EARNINGS S TÝDENNÍ CACHE (ttl = 7 dní)
@st.cache_data(ttl=604800)
def fetch_earnings_date(ticker_str):
    try:
        tk = yf.Ticker(ticker_str)
        cal = tk.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, list) and len(dates) > 0:
                return dates[0]
            return dates
    except:
        pass
    return "-"

@st.cache_data(ttl=3600) # Hlavní data o cenách a maržích stahujeme každou hodinu
def fetch_all_data(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t in ["-", "nan", "NAN"]: continue
        try:
            tk = yf.Ticker(t); inf = tk.info; hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            # Zde voláme naši týdenní funkci pro Earnings
            earn_dt = fetch_earnings_date(t)

            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie')), 
                "earn": earn_dt,
                "name": inf.get('longName', t)
            })
        except: continue
    return res

df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)
raw_data = fetch_all_data(df_raw_list)

# --- 4. SIDEBAR ---
st.sidebar.markdown("### **📊 Menu**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & RSI"], label_visibility="collapsed")
st.sidebar.divider()

filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)
filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 5. LOGIKA STRÁNEK ---
if stranka == "Scoring Matrix":
    strategie = st.sidebar.selectbox("Strategie:", ["Vlastní", "🛡️ Konzervativní", "⚖️ Vyvážená", "🚀 Růstová"])
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní body", value=False)
    
    h_pe, b_pe = [12, 18, 25, 40, 999], [20, 15, 5, 0, -15]
    h_ps, b_ps = [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10]

    if strategie == "🛡️ Konzervativní":
        h_pe, b_pe = [10, 15, 20, 30, 999], [25, 15, 0, -10, -30]
        h_ps, b_ps = [1.0, 2, 4, 7, 999], [20, 10, 0, -10, -20]
    elif strategie == "🚀 Růstová":
        h_pe, b_pe = [20, 35, 50, 80, 999], [15, 25, 15, 5, -5]
        h_ps, b_ps = [3, 6, 12, 20, 999], [10, 15, 20, 5, -10]

    napovedy = {
        "P/E": "Poměr ceny a zisku.\n• < 15 optimální (levné)\n• 15–25 akceptovatelné\n• > 25 varovné (drahé)",
        "P/S": "Poměr ceny a tržeb.\n• < 2 optimální\n• 2–5 akceptovatelné\n• > 6 riskantní (přehřáté)",
        "P/B": "Cena / Účetní hodnota.\n• < 1.5 skvělé (kryto majetkem)\n• > 4 varovné",
        "P/FCF": "Cena / Volné cashflow.\n• < 15 ideální (generuje hotovost)\n• > 35 drahé",
        "H-Marže": "Hrubá marže.\n• > 50% excelentní (silný produkt)\n• 20%–50% běžný průměr\n• < 20% slabé",
        "Č-Marže": "Čistá marže.\n• > 15% optimální\n• 5%–15% běžné\n• < 5% velmi křehké",
        "ROE": "Návratnost kapitálu.\n• > 15% optimální efektivita\n• < 8% manažersky slabé",
        "Tržby y/y": "Meziroční růst tržeb.\n• > 10% stabilní růst\n• > 25% raketový růst\n• Záporné = úpadek",
        "Zisk y/y": "Meziroční růst zisku.\n• > 10% zdravý růst\n• Záporné hodnoty = varovný pokles ziskovosti",
        "Dluh D/E": "Dluh k vlastnímu kapitálu.\n• < 60% bezpečné\n• 60%–120% akceptovatelné\n• > 120% vysoké riziko",
        "Div. výnos": "Roční dividendový výnos.\n• 2%–5% zdravá dividenda\n• > 8% pozor na neudržitelnost (past na dividendu)",
        "Potenciál": "Cílová cena analytiků vs současná.\n• > 15% trh věří v růst\n• Záporný = očekává se pokles"
    }

    def vytvor_p(nazev, zk, def_h, def_b):
        with st.sidebar.expander(f"📊 {nazev}", expanded=False):
            st.caption(napovedy.get(nazev, ""))
            st.divider()
            d = []
            for i in range(5):
                c1, c2 = st.columns(2)
                h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
                b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
                d.append({"h": h, "b": b})
            return d

    p_pe = vytvor_p("P/E", "pe", h_pe, b_pe)
    p_ps = vytvor_p("P/S", "ps", h_ps, b_ps)
    p_pb = vytvor_p("P/B", "pb", [1, 2.5, 4, 8, 999], [10, 7, 3, 0, -5])
    p_pfcf = vytvor_p("P/FCF", "pfcf", [12, 20, 35, 50, 999], [20, 12, 5, 0, -10])
    p_gm = vytvor_p("H-Marže", "gm", [20, 35, 50, 70, 999], [0, 8, 15, 20, 25])
    p_nm = vytvor_p("Č-Marže", "nm", [10, 20, 30, 45, 999], [0, 10, 18, 22, 30])
    p_roe = vytvor_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
    p_rev = vytvor_p("Tržby y/y", "rev", [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35])
    p_eps = vytvor_p("Zisk y/y", "eps", [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40])
    p_deb = vytvor_p("Dluh D/E", "deb", [40, 80, 120, 200, 999], [20, 10, 0, -15, -40])
    p_div = vytvor_p("Div. výnos", "div", [2, 4, 6, 8, 999], [5, 12, 15, 10, 5])
    p_pot = vytvor_p("Potenciál", "pot", [8, 18, 28, 45, 999], [0, 10, 18, 25, 35])

    st.sidebar.divider()
    w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
    w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
    w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
    w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

    mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    pct_cols = ["Změna", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    m_rows = []

    for item in filtered_data:
        inf = item["inf"]; t = item["t"]; name = item["name"]
        def sg(k, mult=1.0):
            v = inf.get(k); return float(v) * mult if v is not None and str(v) != "None" else 0.0
        
        d_yield = sg("dividendYield")
        if d_yield < 0.2 and d_yield > 0: d_yield *= 100 

        raw_vals = {
            "Cena": sg("currentPrice"), "Změna": ((sg("currentPrice")/sg("previousClose", 1.0))-1)*100 if sg("previousClose") else 0,
            "P/E": sg("trailingPE") or sg("forwardPE"), "P/S": sg("priceToSalesTrailing12Months"), 
            "P/B": sg("priceToBook"), "P/FCF": sg("marketCap")/sg("freeCashflow") if sg("freeCashflow") else 0,
            "H-Marže": sg("grossMargins", 100), "Č-Marže": sg("profitMargins", 100), "ROE": sg("returnOnEquity", 100), 
            "Tržby y/y": sg("revenueGrowth", 100), "Zisk y/y": sg("earningsGrowth", 100), "Dluh D/E": sg("debtToEquity"), 
            "Div. výnos": d_yield, "Potenciál": ((sg("targetMeanPrice")/sg("currentPrice", 1.0))-1)*100 if sg("targetMeanPrice") else 0
        }

        total = 0
        row_p = {"Titul": f"   └ body ({t})", "Type": "Points"}
        p_map = {"P/E":p_pe,"P/S":p_ps,"P/B":p_pb,"P/FCF":p_pfcf,"H-Marže":p_gm,"Č-Marže":p_nm,"ROE":p_roe,"Tržby y/y":p_rev,"Zisk y/y":p_eps,"Dluh D/E":p_deb,"Div. výnos":p_div,"Potenciál":p_pot}
        w_map = {"v":w_val,"p":w_prof,"g":w_growth,"r":w_risk}

        for k in mapping_keys:
            vw = w_map["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
            b = get_b(raw_vals[k], p_map[k]) * vw
            total += b
            row_p[k] = float(int(round(b)))

        row_v = {"Titul": name, "Type": "Value", "Změna": raw_vals["Změna"], "Cena": raw_vals["Cena"], "Score": int(total)}
        for k in mapping_keys:
            row_v[k] = raw_vals[k]
        
        m_rows.append(row_v)
        if zobrazit_body: m_rows.append(row_p)

    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            s = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            for i, col in enumerate(r.index):
                if col in ["Cena", "Změna"]: 
                    s[i] = f"color: {'#1b5e20' if r['Změna']>0 else '#b71c1c'}; font-weight: bold"
                val = r.get(col, 0)
                if col == "P/E" and isinstance(val, (int, float)) and val > 25: s[i] = 'background-color: #ffebee'
                if col == "Dluh D/E" and isinstance(val, (int, float)) and val > 120: s[i] = 'background-color: #ffcdd2'
            return s
        
        nastaveni_sloupcu = {
            "Type": None,
            "Cena": st.column_config.NumberColumn("Cena", format="%.2f"),
            "Změna": st.column_config.NumberColumn("Změna", format="%.1f%%"),
            "Score": st.column_config.NumberColumn("Score", format="%d")
        }
        
        for k in mapping_keys:
            if k in pct_cols:
                nastaveni_sloupcu[k] = st.column_config.NumberColumn(k, format="%.1f%%")
            else:
                nastaveni_sloupcu[k] = st.column_config.NumberColumn(k, format="%.1f")

        st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                    use_container_width=True, hide_index=True, height=750,
                    column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"],
                    column_config=nastaveni_sloupcu)

elif stranka == "Vnitřní hodnota (IV)":
    show_details = st.sidebar.toggle("🔓 Zobrazit detailní metody", value=False)
    with st.sidebar.expander("⚖️ Váhy pilířů", expanded=False):
        w1 = st.slider("Váha P1 (Ziskové)", 0, 100, 33)
        w2 = st.slider("Váha P2 (Cashflow)", 0, 100, 33)
        w3 = st.slider("Váha P3 (Majetek)", 0, 100, 34)
    with st.sidebar.expander("⚙️ Globální parametry", expanded=True):
        g_pct = st.slider("Růst (g) %", 0.0, 10.0, 3.0) / 100
        re_pct = st.slider("Výnosnost (Re) %", 5.0, 15.0, 9.0) / 100
        y_bond = st.number_input("Výnos dluhopisů (Y)", value=4.4)
        target_pe = st.slider("Cílové P/E", 5, 40, 15)
        target_ps = st.slider("Cílové P/S", 0.5, 10.0, 3.0)

    iv_results = []
    for item in filtered_data:
        inf = item["inf"]; price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps')); bvps = safe_float(inf.get('bookValue'))
        fcf = safe_float(inf.get('freeCashflow')); rev = safe_float(inf.get('totalRevenue'))
        shares = safe_float(inf.get('sharesOutstanding')); div = safe_float(inf.get('dividendRate'))

        v_graham = (eps * (8.5 + 2 * (g_pct*100)) * 4.4) / y_bond if eps > 0 else 0
        v_pe = eps * target_pe if eps > 0 else 0
        v_rim = bvps + ((eps - (re_pct * bvps)) / (re_pct - g_pct)) if (bvps > 0 and re_pct > g_pct) else 0
        val_p1 = max(v_graham, v_pe, v_rim)
        v_fcf = ((fcf * (1 + g_pct)) / (re_pct - g_pct)) / shares if (shares > 0 and re_pct > g_pct and fcf > 0) else 0
        v_ddm = (div * (1 + g_pct)) / (re_pct - g_pct) if (div > 0 and re_pct > g_pct) else 0
        val_p2 = max(v_fcf, v_ddm)
        v_ps = (rev / shares) * target_ps if (shares > 0 and rev > 0) else 0
        v_nav = bvps if bvps > 0 else 0
        val_p3 = max(v_ps, v_nav)

        ws = [w1, w2, w3]; vals = [val_p1, val_p2, val_p3]
        weighted_sum = sum(v * w for v, w in zip(vals, ws) if v > 0)
        active_weights = sum(w for v, w in zip(vals, ws) if v > 0)
        fair_price = weighted_sum / active_weights if active_weights > 0 else 0
        upside = ((fair_price / price) - 1) * 100 if price > 0 else 0

        row = {"Titul": item["name"], "Cena": price, "P1: Zisk": int(val_p1), "P2: CF": int(val_p2), "P3: Tržby": int(val_p3), "Férová cena": int(fair_price), "Potenciál_num": upside, "Potenciál %": f"{upside:.1f}%"}
        if show_details: row.update({"› Graham": int(v_graham), "› P/E": int(v_pe), "› RIM": int(v_rim), "› FCF": int(v_fcf), "› DDM": int(v_ddm), "› P/S": int(v_ps), "› NAV": int(v_nav)})
        iv_results.append(row)

    df_iv = pd.DataFrame(iv_results)
    if not df_iv.empty:
        def apply_all_styles(row):
            styles = [''] * len(row)
            up = row["Potenciál_num"]
            bg = 'background-color: #d4edda' if up > 0 else ('background-color: #f8d7da' if up < 0 else '')
            tc = 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold'
            for i, col in enumerate(row.index):
                if col in ["Titul", "Potenciál %"]: styles[i] = bg
                if col == "Cena": styles[i] = tc
            return styles
        st.dataframe(df_iv.style.apply(apply_all_styles, axis=1).format({"Cena": "{:.2f}"}), 
                    use_container_width=True, hide_index=True, height=850,
                    column_config={"Potenciál_num": None})

else:
    with st.expander("ℹ️ Legenda k RSI a Doporučení analytiků", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 📈 Doporučení analytiků")
            st.caption("**Zdroj:** Konsenzus bank z Wall Street (Yahoo Finance), horizont 6-12 měsíců.")
            st.markdown("""
            - **Strong Buy / Buy (Zelená):** Silný fundament, analytici očekávají překonání trhu.
            - **Hold:** Férové ocenění, neutrální výhled.
            - **Underperform / Sell (Červená):** Očekávané zhoršení výsledků nebo nadhodnocení.
            """)
        with c2:
            st.markdown("### 📊 Indikátor RSI (Momentum)")
            st.caption("**Zdroj:** Matematický výpočet za posledních 14 dní (rychlost pohybu ceny).")
            st.markdown("""
            - **RSI > 65 (Překoupeno / Červená):** Trh propadl euforii, akcie je krátkodobě drahá, hrozí korekce.
            - **RSI < 35 (Přeprodáno / Zelená):** Na trhu je panika/výprodej, akcie je v technické 'slevě'.
            - **35 až 65:** Neutrální zóna.
            """)

    c_rows, today = [], date.today()
    for item in filtered_data:
        inf = item["inf"]; earn_val = item["earn"]
        days_to = safe_date_diff(earn_val, today)
        
        # Formátování zobrazení datumu pro tabulku
        fmt_earn = "-"
        if isinstance(earn_val, (datetime, date)):
            fmt_earn = earn_val.strftime('%d.%m.%Y')
        elif str(earn_val) != "-":
            fmt_earn = str(earn_val)

        ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
        c_rows.append({
            "Titul": item["name"], "Ticker": item["t"], "Earnings": fmt_earn, "Dní do": days_to,
            "Dividenda": f"{safe_float(inf.get('dividendRate')):.2f} {inf.get('currency', 'USD')}", "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", 
            "Doporučení": inf.get('recommendationKey', '-').replace('_', ' ').title(), "RSI": int(item['rsi']), "_rsi": item["rsi"]
        })
    df_c = pd.DataFrame(c_rows)
    if not df_c.empty:
        def style_calendar(r):
            s = [''] * len(r)
            d_idx = r.index.get_loc("Dní do")
            
            # Pokud se nepovedlo datum stáhnout (999), nebudeme políčko barvit
            if r["Dní do"] == 999:
                pass
            elif r["Dní do"] < 0: 
                s[d_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            elif r["Dní do"] < 14: 
                s[d_idx] = 'background-color: #fff9c4; color: #f57f17; font-weight: bold'
            
            rec = str(r["Doporučení"]).lower(); rec_idx = r.index.get_loc("Doporučení")
            if "buy" in rec: s[rec_idx] = 'background-color: #e8f5e9; color: #1b5e20; font-weight: bold'
            elif "sell" in rec: s[rec_idx] = 'background-color: #ffebee; color: #b71c1c'
            
            rsi_idx = r.index.get_loc("RSI")
            if r["_rsi"] < 35: s[rsi_idx] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold'
            elif r["_rsi"] > 65: s[rsi_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            return s
            
        st.dataframe(df_c.style.apply(style_calendar, axis=1), 
                    use_container_width=True, hide_index=True, height=850,
                    column_config={"_rsi": None, "Dní do": st.column_config.NumberColumn("Dní do", format="%d")})
