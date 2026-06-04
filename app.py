import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import feedparser  # Knihovna pro čtení RSS kanálů
import urllib.request # Pomocná knihovna pro simulaci prohlížeče

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
                    if hist.index.tz is not None:
                        hist.index = hist.index.tz_localize(None)
                    if 'Dividends' in t_df.columns:
                        dv = t_df[t_df.index >= (datetime.now() - timedelta(days=365))]['Dividends'].sum()
            data[t] = {"price": cp, "div": dv, "history": hist}
        except: data[t] = {"price": 0, "div": 0, "history": pd.Series()}
    return data

# Funkce pro stahování denního shrnutí trhu z Investičního webu
@st.cache_data(ttl=3600)
def get_investicni_web_svodka():
    try:
        req = urllib.request.Request(
            "https://www.investicniweb.cz/rss/all.xml", 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            html_content = response.read()
        
        feed = feedparser.parse(html_content)
        svodky = []
        
        for entry in feed.entries:
            title_lower = entry.title.lower()
            if "shrnutí obchodování v usa" in title_lower or "usa" in title_lower and "akcie" in title_lower:
                summary_clean = entry.summary.split('<')[0] if '<' in entry.summary else entry.summary
                
                # Zjednodušení názvu na přání uživatele
                display_title = "Shrnutí obchodování v USA"
                if " - " in entry.title:
                    # Pokud obsahuje datum (např. "Shrnutí obchodování v USA - 5. 6."), zachováme ho
                    display_title = f"Shrnutí obchodování v USA ({entry.title.split(' - ')[-1]})"

                svodky.append({
                    "title": display_title,
                    "summary": summary_clean.strip(),
                    "link": entry.link
                })
            if len(svodky) >= 3:
                break
                
        if svodky:
            return svodky
    except:
        pass
    return [{
        "title": "Shrnutí obchodování v USA", 
        "summary": "Odkaz přímo na kompletní výpis denních shrnutí amerických trhů.", 
        "link": "https://www.investicniweb.cz/tema/shrnuti-obchodovani-v-usa"
    }]

# --- 2. LOGIKA & NAČÍTÁNÍ DAT ---
SHEET_ID = "1LBQNzIofAltQvixIyWgBCutwYNZNSHv740hyaMICWkA"

URL_PORTFOLIO = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid=0"
URL_UKOLY = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid=937653419"

try:
    df_raw = pd.read_csv(URL_PORTFOLIO).dropna(subset=['Ticker'])
    tickers_list = df_raw["Ticker"].unique()
    m_data = load_market_data(tickers_list)
    fx = get_fx_rates()

    try: df_ukoly_raw = pd.read_csv(URL_UKOLY)
    except: df_ukoly_raw = pd.DataFrame(columns=["Úkol", "Termín"])

    st.sidebar.title("💎 MENU")
    page = st.sidebar.radio("NAVIGACE:", ["💰 Přehled", "🖼️ Grafika", "📈 Výkonnost", "📋 Úkoly a Poznámky", "📰 Tržní zprávy", "⚙️ Ostatní"])
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
        curr_price = info["price"] if pd.notna(info["price"]) else 0
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
        
        earn_dt_str = "-"
        days_to = "-"
        if 'Earnings' in r and pd.notna(r['Earnings']):
            raw_val = str(r['Earnings']).strip()
            if raw_val and raw_val != "-":
                try:
                    parsed_date = pd.to_datetime(raw_val, dayfirst=True).date()
                    earn_dt_str = parsed_date.strftime('%d.%m.%Y')
                    days_to = (parsed_date - today).days
                except: earn_dt_str = raw_val
        
        poznamka_val = str(r['Poznámka']).strip() if 'Poznámka' in r and pd.notna(r['Poznámka']) else "-"

        processed.append({
            "Ticker": t, "Název": r['Název'], "KS": ks, "Cena": curr_price, "CZK": val_czk, 
            "Zisk %": ((curr_price - ref_price)/ref_price*100) if ref_price > 0 else 0,
            "Div/ks": div_ks, "Div celkem": ks * div_ks * rate, 
            "Earnings": earn_dt_str, "Dní": days_to, 
            "Poznámka": poznamka_val,
            "History": hist, "RefPrice": ref_price,
            "Měna": str(r["Měna"]).strip()
        })
    df_p = pd.DataFrame(processed)

    st.sidebar.divider()
    st.sidebar.metric("Celkem CZK", f"{format_cz(total_val, 0)} CZK")
    diff = total_val - total_ref
    st.sidebar.metric("Změna", f"{format_cz(diff, 0)} CZK", f"{(diff/total_ref*100 if total_ref>0 else 0):.2f} %")

    # --- STRÁNKY ---
    if page == "💰 Přehled":
        df_show = df_p[["Název", "KS", "Cena", "CZK", "Zisk %", "Div/ks", "Div celkem", "Earnings", "Dní", "Poznámka"]].copy()
        df_show["CZK"] = df_show["CZK"].fillna(0)
        df_show = df_show.sort_values("CZK", ascending=False)

        def style_rows(row):
            styles = [''] * len(row)
            try:
                orig_match = df_p[df_p['Název'] == row['Název']]
                if not orig_match.empty:
                    orig_row = orig_match.iloc[0]
                    styles[2] = 'color: #2e7d32; font-weight: bold;' if orig_row['Cena'] >= orig_row['RefPrice'] else 'color: #d32f2f; font-weight: bold;'
            except: pass
            styles[4] = 'color: #2e7d32; font-weight: bold;' if row['Zisk %'] >= 0 else 'color: #d32f2f; font-weight: bold;'
            try:
                days = int(row['Dní'])
                if days < 0: styles[8] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center;'
                elif days <= 10: styles[8] = 'background-color: #ffe0b2; color: #e65100; font-weight: bold; text-align: center;'
            except: pass
            return styles

        styled_df = df_show.style.apply(style_rows, axis=1)\
            .format({
                "KS": "{:,.0f}", "Cena": lambda x: format_cz(x), "CZK": lambda x: format_cz(x, 0),
                "Zisk %": "{:,.2f}%", "Div/ks": lambda x: format_cz(x), "Div celkem": lambda x: format_cz(x, 0),
                "Dní": lambda x: f"{x}" if isinstance(x, int) else "-"
            })
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height="content")

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
                        if r["Název"] in sel: fig.add_trace(go.Scatter(x=h.index, y=(h/h.iloc[0]-1)*100, name=r["Název"]))
            fig.add_trace(go.Scatter(x=port_h.index, y=port_h, name="MOJE PORTFOLIO", line=dict(width=4)))
            st.plotly_chart(fig, use_container_width=True)
        else: st.warning("Nepodařilo se načíst historii pro vybraný index.")

    elif page == "📋 Úkoly a Poznámky":
        st.title("📋 Úkoly a Poznámky")
        st.subheader("📌 Obecné úkoly (s odpočtem termínu)")
        
        if not df_ukoly_raw.empty:
            if "Úkol" not in df_ukoly_raw.columns and len(df_ukoly_raw.columns) > 0:
                df_ukoly_raw.rename(columns={df_ukoly_raw.columns[0]: "Úkol"}, inplace=True)
            if len(df_ukoly_raw.columns) > 1 and "Termín" not in df_ukoly_raw.columns:
                df_ukoly_raw.rename(columns={df_ukoly_raw.columns[1]: "Termín"}, inplace=True)

            df_ukoly = df_ukoly_raw.dropna(subset=["Úkol"]).copy()
            processed_ukoly = []
            for _, row_u in df_ukoly.iterrows():
                u_text = str(row_u["Úkol"]).strip()
                u_date_str = "-"
                u_days_to = "-"
                if "Termín" in df_ukoly.columns and pd.notna(row_u["Termín"]):
                    raw_date = str(row_u["Termín"]).strip()
                    if raw_date and raw_date != "-":
                        try:
                            parsed_u_date = pd.to_datetime(raw_date, dayfirst=True).date()
                            u_date_str = parsed_u_date.strftime('%d.%m.%Y')
                            u_days_to = (parsed_u_date - today).days
                        except: u_date_str = raw_date
                processed_ukoly.append({"Úkol": u_text, "Termín": u_date_str, "Dní do termínu": u_days_to})
            
            df_ukoly_final = pd.DataFrame(processed_ukoly)
            df_ukoly_final["sort_key"] = df_ukoly_final["Dní do termínu"].apply(lambda x: x if isinstance(x, int) else 999999)
            df_ukoly_final = df_ukoly_final.sort_values("sort_key").drop(columns=["sort_key"])

            def style_ukoly_rows(row):
                styles = [''] * len(row)
                try:
                    days = int(row['Dní do termínu'])
                    if days < 0: styles[2] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold; text-align: center;'
                    elif days <= 7: styles[2] = 'background-color: #ffe0b2; color: #e65100; font-weight: bold; text-align: center;'
                    else: styles[2] = 'background-color: #e8f5e9; color: #2e7d32; text-align: center;'
                except: styles[2] = 'text-align: center;'
                return styles

            st.dataframe(df_ukoly_final.style.apply(style_ukoly_rows, axis=1).format({"Dní do termínu": lambda x: f"{x}" if isinstance(x, int) else "-"}), use_container_width=True, hide_index=True)
        else: st.info("V tabulce úkolů nemáte žádné záznamy.")
            
        st.divider()
        st.subheader("🔍 Poznámky ke konkrétním titulům")
        df_notes_only = df_p[df_p["Poznámka"] != "-"][["Název", "Poznámka"]].copy()
        if not df_notes_only.empty: st.dataframe(df_notes_only, use_container_width=True, hide_index=True)
        else: st.info("Nemáte žádné specifické poznámky u akcií v prvním listu.")

    elif page == "📰 Tržní zprávy":
        # --- SEKCE A: DENNÍ SHRNOTÍ TRHU (Investiční web) ---
        svodky = get_investicni_web_svodka()
        
        for svodka in svodky:
            with st.container(border=True):
                st.markdown(f"#### 🌐 {svodka['title']}")
                st.write(svodka['summary'])
                st.markdown(f"[Přečíst celý článek na Investičním webu]({svodka['link']})")
        
        st.divider()
        
        # --- SEKCE B: ZPRÁVY KE SPOLEČNOSTEM V PORTFOLIU (Yahoo Finance) ---
        st.subheader("🎯 Zprávy ke společnostem ve vašem portfoliu")
        st.caption("Filtrováno automaticky podle tickerů, které reálně vlastníte. Zobrazují se maximálně 3 nejnovější zprávy pro každý titul.")
        
        found_any_news = False
        
        for _, row_p in df_p.dropna(subset=["Ticker"]).iterrows():
            ticker_symbol = row_p["Ticker"]
            company_name = row_p["Název"]
            
            try:
                ticker_obj = yf.Ticker(ticker_symbol)
                news_list = ticker_obj.news
                
                if news_list:
                    printed_for_this_ticker = 0 
                    
                    for item in news_list:
                        title_news = item.get("title")
                        link_news = item.get("link")
                        
                        if not title_news and "content" in item:
                            title_news = item["content"].get("title")
                            link_news = item["content"].get("clickThroughUrl", {}).get("url") or item["content"].get("pubUrl")
                        
                        if not title_news or not link_news:
                            continue
                            
                        found_any_news = True
                        printed_for_this_ticker += 1
                        
                        publisher = item.get("publisher") or item.get("content", {}).get("provider", {}).get("displayName") or "Yahoo Finance"
                        
                        try:
                            raw_time = item.get("providerPublishTime") or item.get("content", {}).get("pubDate")
                            pub_time = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00")).strftime('%d.%m.%Y %H:%M') if "T" in str(raw_time) else datetime.fromtimestamp(int(raw_time)).strftime('%d.%m.%Y %H:%M')
                        except:
                            pub_time = "Aktuální"
                        
                        st.markdown(f"**📌 {company_name} ({ticker_symbol})** | *{pub_time}* | Zdroj: {publisher}")
                        st.markdown(f"[{title_news}]({link_news})")
                        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
                        
                        if printed_for_this_ticker >= 3:
                            break
            except:
                pass
                
        if not found_any_news:
            st.info("Momentálně nebyly nalezeny žádné zprávy pro vaše tituly.")

    elif page == "⚙️ Ostatní":
        color_map = {'CZK': '#29b6f6', 'EUR': '#0d47a1', 'USD': '#d32f2f'}
        fig = px.sunburst(df_p, path=['Měna', 'Název'], values='CZK', color='Měna', color_discrete_map=color_map)
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{percentParent:.1%}", insidetextorientation='radial')
        fig.update_layout(height=700)
        st.plotly_chart(fig, use_container_width=True)
        
except Exception as e: st.error(f"Kritická chyba: {e}")
