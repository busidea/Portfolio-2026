import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import feedparser
from datetime import datetime
from google import genai

# --- NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="Portfolio Tracker 2026", layout="wide")

st.title("📈 Portfolio Tracker 2026")

# --- BOČNÍ PANEL (NAVIGACE A NASTAVENÍ) ---
st.sidebar.header("Navigace")
page = st.sidebar.radio("Přejít na:", ["📊 Přehled portfolia", "📰 Tržní zprávy", "⚙️ Spravovat portfolio"])

# --- INICIALIZACE SESSIONS A STAVU PORTFOLIA ---
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame([
        {"Ticker": "AAPL", "Název": "Apple Inc.", "Kusy": 10, "Nákupní cena ($)": 150.0},
        {"Ticker": "MSFT", "Název": "Microsoft Corp.", "Kusy": 5, "Nákupní cena ($)": 300.0},
        {"Ticker": "CEZ.PR", "Název": "ČEZ a.s.", "Kusy": 100, "Nákupní cena ($)": 850.0}
    ])

df_p = st.session_state.portfolio

# --- FUNKCE PRO NAČÍTÁNÍ ZPRÁV Z INVESTIČNÍHO WEBU (RSS) ---
def get_investicni_web_svodka():
    url = "https://www.investicniweb.cz/rss"
    try:
        feed = feedparser.parse(url)
        svodky = []
        for entry in feed.entries:
            if "Shrnutí" in entry.title or "USA" in entry.title or "akcie" in entry.title.lower():
                svodky.append({
                    "title": entry.title,
                    "summary": entry.summary if hasattr(entry, 'summary') else "",
                    "link": entry.link
                })
                if len(svodky) >= 3:
                    break
        return svodky
    except Exception:
        return []

# ==============================================================================
# STRÁNKA 1: 📊 PŘEHLED PORTFOLIA
# ==============================================================================
if page == "📊 Přehled portfolia":
    st.subheader("Aktuální stav portfolia")
    
    if df_p.empty:
        st.info("Portfolio je prázdné. Přidejte tituly v sekci '⚙️ Spravovat portfolio'.")
    else:
        with st.spinner("Načítám aktuální tržní data..."):
            current_prices = []
            total_values = []
            profit_losses = []
            
            for _, row in df_p.iterrows():
                try:
                    t = yf.Ticker(row["Ticker"])
                    hist = t.history(period="1d")
                    if not hist.empty:
                        c_price = hist["Close"].iloc[-1]
                    else:
                        c_price = row["Nákupní cena ($)"]
                except Exception:
                    c_price = row["Nákupní cena ($)"]
                
                c_price = round(c_price, 2)
                t_value = round(c_price * row["Kusy"], 2)
                p_loss = round((c_price - row["Nákupní cena ($)"]) * row["Kusy"], 2)
                
                current_prices.append(c_price)
                total_values.append(t_value)
                profit_losses.append(p_loss)
            
            df_display = df_p.copy()
            df_display["Aktuální cena ($)"] = current_prices
            df_display["Celková hodnota ($)"] = total_values
            df_display["Zisk/Ztráta ($)"] = profit_losses
            
            col1, col2, col3 = st.columns(3)
            tot_val = sum(total_values)
            tot_invested = sum(df_p["Kusy"] * df_p["Nákupní cena ($)"])
            tot_pnl = tot_val - tot_invested
            
            col1.metric("Celková hodnota", f"${tot_val:,.2f}")
            col2.metric("Celkem investováno", f"${tot_invested:,.2f}")
            col3.metric("Celkový zisk/ztráta", f"${tot_pnl:,.2f}", delta=f"{tot_pnl:,.2f}")
            
            st.dataframe(df_display, use_container_width=True)
            
            # Graf rozložení portfolia
            st.subheader("Rozložení portfolia")
            fig = px.pie(df_display, values="Celková hodnota ($)", names="Název", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# STRÁNKA 2: 📰 TRŽNÍ ZPRÁVY
# ==============================================================================
elif page == "📰 Tržní zprávy":
    st.subheader("📰 Tržní zprávy a svodky")
    
    svodky = get_investicni_web_svodka()
    for svodka in svodky:
        with st.container(border=True):
            st.markdown(f"#### 🌐 {svodka['title']}")
            st.write(svodka['summary'])
            st.markdown(f"[Přečíst celý článek na Investičním webu]({svodka['link']})")
    
    st.divider()

    # --- AI ANALÝZA GEMINI ---
    with st.expander("🤖 Situace na trzích dle AI (Gemini)"):
        if "GEMINI_API_KEY" in st.secrets:
            if st.button("Spustit analýzu aktuálního dění"):
                with st.spinner("Gemini zpracovává tržní přehled..."):
                    try:
                        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        now_str = datetime.now().strftime("%d.%m.%Y v %H:%M")
                        
                        prompt = (
                            f"Dnešní datum a přesný čas je: {now_str}. Tvým úkolem je udělat aktuální a faktické shrnutí dění na akciových trzích. "
                            "Uplatni tato ZÁVAZNÁ pravidla:\n"
                            f"1. NA PRVNÍ ŘÁDEK napiš tučně: 'Analýza vygenerována dne: {now_str}' a uveď, k jakému dni/období data na trzích reálně patří.\n"
                            "2. Buď konkrétní a věcný. Vyhni se vágním frázím o volatilitě a makrodatech. Pokud mluvíš o zprávách, uveď konkrétní událost, jméno firmy nebo report, který vyšel.\n"
                            "3. Uveď reálná čísla nebo přibližný vývoj hlavních indexů (S&P 500, NASDAQ, DAX) za poslední uzavřenou obchodní seanci.\n"
                            "4. Pokud je víkend, výslovně to uveď a shrň uzavření trhů z pátku a klíčové zprávy, které hýbaly uplynulým týdnem.\n"
                            "Odpovídej kompletně v českém jazyce, přehledně, strukturovaně s využitím odrážek a profesionálním tónem."
                        )
                        
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.markdown(response.text)
                    except Exception as ai_err:
                        st.error(f"Při komunikaci s AI došlo k chybě: {ai_err}")
        else:
            st.info("Pro spuštění AI analýzy je nutné v nastavení Streamlit nastavit klíč `GEMINI_API_KEY`.")
    
    st.divider()
    st.subheader("📌 Zprávy k vašim titulům v portfoliu")
    
    all_portfolio_news = []
    
    for _, row_p in df_p.dropna(subset=["Ticker"]).iterrows():
        ticker_symbol = str(row_p["Ticker"]).strip()
        company_name = row_p["Název"]
        
        # --- 1. POKUS: yfinance ---
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            news_list = ticker_obj.news
            
            if news_list and isinstance(news_list, list):
                for item in news_list:
                    title_news, link_news, publisher, timestamp = None, None, "Yahoo Finance", 0
                    
                    if isinstance(item, dict):
                        # Nová struktura yfinance (objekt s klíčem 'content')
                        if "content" in item and isinstance(item["content"], dict):
                            c = item["content"]
                            title_news = c.get("title")
                            link_news = c.get("clickThroughUrl", {}).get("url") if isinstance(c.get("clickThroughUrl"), dict) else c.get("pubUrl")
                            publisher = c.get("provider", {}).get("displayName", "Yahoo Finance") if isinstance(c.get("provider"), dict) else "Yahoo Finance"
                            pub_date = c.get("pubDate")
                            if pub_date:
                                try:
                                    timestamp = int(datetime.fromisoformat(str(pub_date).replace("Z", "+00:00")).timestamp())
                                except:
                                    pass
                        # Stará struktura yfinance
                        else:
                            title_news = item.get("title")
                            link_news = item.get("link")
                            publisher = item.get("publisher", "Yahoo Finance")
                            timestamp = item.get("providerPublishTime", 0)
                    
                    if title_news and link_news:
                        all_portfolio_news.append({
                            "company": company_name,
                            "ticker": ticker_symbol,
                            "title": title_news,
                            "link": link_news,
                            "publisher": publisher,
                            "timestamp": timestamp or 0
                        })
        except Exception:
            pass
        
        # --- 2. FALLBACK: Google News RSS (pokud yfinance nevrátil žádnou zprávu) ---
        if not any(n["ticker"] == ticker_symbol for n in all_portfolio_news):
            try:
                clean_ticker = ticker_symbol.split('.')[0]  # např. CEZ.PR -> CEZ
                rss_url = f"https://news.google.com/rss/search?q={clean_ticker}+{company_name}&hl=en-US&gl=US&ceid=US:en"
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:3]:  # Načte max 3 zprávy z fallbacku
                    pub_ts = 0
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_ts = int(datetime(*entry.published_parsed[:6]).timestamp())
                    
                    all_portfolio_news.append({
                        "company": company_name,
                        "ticker": ticker_symbol,
                        "title": entry.title,
                        "link": entry.link,
                        "publisher": getattr(entry, 'source', {}).get('title', 'Google News'),
                        "timestamp": pub_ts
                    })
            except Exception:
                pass
            
    if all_portfolio_news:
        # Odstranění duplicit podle odkazu
        seen_links = set()
        unique_news = []
        for n in all_portfolio_news:
            if n["link"] not in seen_links:
                seen_links.add(n["link"])
                unique_news.append(n)
        
        # Seřazení od nejnovějších
        unique_news.sort(key=lambda x: x["timestamp"], reverse=True)
        
        for news in unique_news[:50]:
            try:
                if news["timestamp"] > 0:
                    pub_time = datetime.fromtimestamp(news["timestamp"]).strftime('%d.%m.%Y %H:%M')
                else:
                    pub_time = "Nedávno"
            except:
                pub_time = "Nedávno"
                
            st.markdown(f"📌 **{news['company']} ({news['ticker']})** | *{pub_time}* | *Zdroj: {news['publisher']}*")
            st.markdown(f"[{news['title']}]({news['link']})")
    else:
        st.info("Momentálně nebyly nalezeny žádné zprávy pro vaše tituly.")

# ==============================================================================
# STRÁNKA 3: ⚙️ SPRAVOVAT PORTFOLIO
# ==============================================================================
elif page == "⚙️ Spravovat portfolio":
    st.subheader("Správa titulů v portfoliu")
    
    st.dataframe(st.session_state.portfolio, use_container_width=True)
    
    st.divider()
    st.write("### Přidat nový titul")
    
    with st.form("add_ticker_form"):
        new_ticker = st.text_input("Ticker (např. NVDA, TSLA, CEZ.PR):")
        new_name = st.text_input("Název společnosti:")
        new_shares = st.number_input("Počet kusů:", min_value=0.0001, step=1.0)
        new_price = st.number_input("Nákupní cena za kus ($/Kč):", min_value=0.0, step=1.0)
        
        submit_button = st.form_submit_button("Přidat do portfolia")
        
        if submit_button:
            if new_ticker and new_name:
                new_row = pd.DataFrame([{
                    "Ticker": new_ticker.upper().strip(),
                    "Název": new_name.strip(),
                    "Kusy": new_shares,
                    "Nákupní cena ($)": new_price
                }])
                st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
                st.success(f"Titul {new_ticker} byl úspěšně přidán!")
                st.rerun()
            else:
                st.error("Vyplňte prosím Ticker i Název společnosti.")
