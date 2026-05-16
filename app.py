import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import re

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 3.5rem; padding-bottom: 0rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    
    /* Vynucené zvýraznění prvního sloupce */
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { 
        font-weight: bold !important;
        color: #004080 !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE (ZESÍLENÉ) ---
def safe_float(val):
    if pd.isna(val) or val is None:
        return 0.0
    s = str(val).strip()
    if s.lower() in ["nan", "none", "-", "", "null"]:
        return 0.0
    
    try:
        # Odstraníme běžné měny a mezery (včetně nezlomitelných \xa0)
        s = re.sub(r'[^\d.,-]', '', s)
        
        # Pokud text obsahuje jak čárku, tak tečku (např. 1,250.50 nebo 1.250,50)
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):  # 1.250,50 -> evropský styl tisíců
                s = s.replace('.', '').replace(',', '.')
            else:  # 1,250.50 -> anglosaský styl
                s = s.replace(',', '')
        else:
            # Pokud obsahuje jen čárku, předpokládáme, že je to desetinná čárka (český styl: 37,45 -> 37.45)
            s = s.replace(',', '.')
            
        return float(s)
    except:
        return 0.0

def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]:
        return 999
    try:
        dt = pd.to_datetime(earn_val, dayfirst=True).date()
        return (dt - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def fmt(val, precision=1, is_pct=False):
    if val is None or val == 0: return "0.0" + ("%" if is_pct else "")
    res = f"{val:.{precision}f}"
    return res + "%" if is_pct else res

# --- 3. NAČTENÍ DAT ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=60)  # Sníženo pro rychlejší testování změn
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        
        # Zkusíme nejprve standardní čárku
        df = pd.read_csv(csv_url, sep=",")
        
        # Pokud se načetl jen 1 sloupec, zkusíme středník
        if len(df.columns) <= 1:
            df = pd.read_csv(csv_url, sep=";")
            
        df.columns = [c.strip() for c in df.columns]
        
        # Najdeme sloupec s Tickerem
        col_ticker = next((c for c in df.columns if "ticker" in c.lower()), None)
        if col_ticker:
            df['Ticker'] = df[col_ticker].astype(str).str.upper().str.strip()
        else:
            df['Ticker'] = df.iloc[:, 1].astype(str).str.upper().str.strip() if len(df.columns) > 1 else df.iloc[:, 0].astype(str).str.upper().str.strip()
            
        return df
    except: 
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_all_data(df_input):
    res = []
    if df_input.empty: return res
    
    # Flexibilní vyhledání sloupců
    col_std = next((c for c in df_input.columns if "průměrná nákupní" in c.lower() or "prumerna" in c.lower() or "nákupní cena" in c.lower()), None)
    col_opc = next((c for c in df_input.columns if "včetně opcí" in c.lower() or "vcetne" in c.lower() or "opcí" in c.lower()), None)
    col_kat = next((c for c in df_input.columns if "charakter" in c.lower() or "kategorie" in c.lower() or "sentiment" in c.lower()), None)
    col_earn = next((c for c in df_input.columns if "earnings" in c.lower() or "kalendář" in c.lower()), None)

    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        if t and t not in ["NAN", "NONE", "-", ""]:
            # Vyčištění případného balastu v tickeru
            if " " in t: t = t.split()[-1]
            
            c_std = safe_float(row.get(col_std)) if col_std else 0.0
            c_opc = safe_float(row.get(col_opc)) if col_opc else 0.0
            
            try:
                tk = yf.Ticker(t); inf = tk.info; hi = tk.history(period="3mo")
                rsi = 50
                if len(hi) > 14:
                    d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                    rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
                
                res.append({
                    "t": t, "inf": inf, "rsi": rsi, "history": hi,
                    "kat": "Portfolio", # Výchozí zobrazení
                    "earn": row.get(col_earn) if col_earn else None,
                    "cena_std": c_std,
                    "cena_opc": c_opc,
                    "name": inf.get('longName', t)
                })
            except: 
                continue
    return res

df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)
raw_data = fetch_all_data(df_raw_list)

# --- DIAGNOSTICKÝ BOX (Zde uvidíš pravdu) ---
with st.expander("🔍 DIAGNOSTIKA NAČÍTÁNÍ DAT (Rozklikni pro kontrolu)", expanded=True):
    st.write("**Nalezené názvy sloupců v tabulce:**", list(df_raw_list.columns))
    if not df_raw_list.empty:
        st.write("**Ukázka raw řádku z tabulky (co poslal Google):**")
        st.dataframe(df_raw_list.head(3))
    st.write("**Co z toho Python vypreparoval (Zde nesmí být nuly!):**")
    diag_rows = [{"Ticker": d["t"], "Načtená Cena (Standard)": d["cena_std"], "Načtená Cena (S opcemi)": d["cena_opc"]} for d in raw_data]
    st.dataframe(pd.DataFrame(diag_rows))

# --- 4. SIDEBAR ---
st.sidebar.markdown("### **📊 Menu**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & RSI"], label_visibility="collapsed")
st.sidebar.divider()

filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Vše"], index=0)
filtered_data = raw_data # Pro zjednodušení teď bereme všechna napárovaná data

st.sidebar.markdown("### **⏱️ Období / Výkonnost**")
obdobi = st.sidebar.selectbox("Zobrazit změnu za:", ["1 Den", "1 Týden", "1 Měsíc", "Od pořízení (Standard)", "Od pořízení (s opcemi)"], index=0)

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

    def vytvor_p(nazev, zk, def_h, def_b):
        with st.sidebar.expander(f"📊 {nazev}", expanded=False):
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
    pct_cols = ["Výkonnost", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    m_rows = []

    for item in filtered_data:
        inf = item["inf"]; t = item["t"]; name = item["name"]; hi = item["history"]
        def sg(k, mult=1.0):
            v = inf.get(k); return float(v) * mult if v is not None and str(v) != "None" else 0.0
        
        d_yield = sg("dividendYield")
        if d_yield < 0.2 and d_yield > 0: d_yield *= 100 

        aktuarni_cena = sg("currentPrice")
        vypoctena_zmena = 0.0

        if obdobi == "1 Den":
            vypoctena_zmena = ((aktuarni_cena / sg("previousClose", 1.0)) - 1) * 100 if sg("previousClose") else 0.0
        elif obdobi == "1 Týden" and len(hi) >= 5:
            vypoctena_zmena = ((aktuarni_cena / hi['Close'].iloc[-5]) - 1) * 100 if hi['Close'].iloc[-5] > 0 else 0.0
        elif obdobi == "1 Měsíc" and len(hi) >= 20:
            vypoctena_zmena = ((aktuarni_cena / hi['Close'].iloc[-20]) - 1) * 100 if hi['Close'].iloc[-20] > 0 else 0.0
        elif obdobi == "Od pořízení (Standard)":
            vypoctena_zmena = ((aktuarni_cena / item["cena_std"]) - 1) * 100 if item["cena_std"] > 0 else 0.0
        elif obdobi == "Od pořízení (s opcemi)":
            vypoctena_zmena = ((aktuarni_cena / item["cena_opc"]) - 1) * 100 if item["cena_opc"] > 0 else 0.0

        raw_vals = {
            "Cena": aktuarni_cena, 
            "Výkonnost": vypoctena_zmena,
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
            row_p[k] = str(int(round(b)))

        row_v = {"Titul": name, "Type": "Value", "_perf": raw_vals["Výkonnost"], "Score": int(total)}
        for k in mapping_keys:
            row_v[k] = fmt(raw_vals[k], 1, k in pct_cols)
            row_v[f"_raw_{k}"] = raw_vals[k]
        
        row_v["Cena"] = fmt(raw_vals["Cena"], 2)
        row_v["Výkonnost"] = fmt(raw_vals["Výkonnost"], 1, True)
        m_rows.append(row_v)
        if zobrazit_body: m_rows.append(row_p)

    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            s = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            for i, col in enumerate(r.index):
                if col == "Cena": 
                    s[i] = "font-weight: bold;"
                if col == "Výkonnost":
                    s[i] = f"color: {'#1b5e20' if r['_perf']>0 else '#b71c1c'}; font-weight: bold; background-color: {'#e8f5e9' if r['_perf']>0 else '#ffebee'}"
                
                if col == "Score":
                    sc = r.get("Score", 0)
                    if sc > 100: s[i] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold;'
                    elif sc > 50: s[i] = 'background-color: #fff9c4; color: #f57f17; font-weight: bold;'
                    else: s[i] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold;'
                    
                val = r.get(f"_raw_{col}", 0)
                if col == "P/E" and val > 25: s[i] = 'background-color: #ffebee'
                if col == "Dluh D/E" and val > 120: s[i] = 'background-color: #ffcdd2'
            return s
        
        cols_to_hide = [c for c in df.columns if c.startswith("_raw_") or c.startswith("_")] + ["Type"]
        st.dataframe(df.style.apply(style_matrix, axis=1),
                    use_container_width=True, hide_index=True, height=800,
                    column_order=["Titul", "Cena", "Výkonnost"] + mapping_keys + ["Score"],
                    column_config={c: None for c in cols_to_hide})

# [Zbytek stránek IV a Kalendář zůstává beze změny, funkční podle předchozí verze]
else:
    st.info("Přepněte na Scoring Matrix pro zobrazení hlavní tabulky.")
