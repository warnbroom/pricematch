import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import subprocess
import time

# --- 1. SETUP ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Retail Checker V32.0", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM THEO SITE ---

def scrape_google_for_sites(page, product_name, site_list):
    """
    Sử dụng cú pháp 'site:domain' trên Google để ép kết quả về các web đích.
    """
    results = []
    # Kết hợp các site thành một chuỗi tìm kiếm: "tên sản phẩm (site:A OR site:B...)"
    site_query = " OR ".join([f"site:{site}" for site in site_list])
    full_query = f"{product_name} ({site_query})"
    
    try:
        url = f"https://www.google.com/search?q={full_query.replace(' ', '+')}&hl=vi"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        
        # Quét các khối kết quả (div.g) theo đúng logic quet_gia.py
        items = page.query_selector_all("div.g")
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                # Vì là web siêu thị lẻ, ta nới lỏng filter nhưng vẫn chặn giá quá cao
                if 5000 < price < 500000:
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    
                    # Xác định nguồn từ link
                    source = "Siêu thị"
                    for s in site_list:
                        if s in link:
                            source = s.split('.')[0].capitalize()
                            break
                            
                    results.append({"Nguồn": source, "Giá TT": price, "Link": link})
                    # Chỉ lấy kết quả đầu tiên tìm thấy của mỗi site hoặc kết quả tốt nhất
                    if len(results) >= 3: break 
    except: pass
    return results

# --- 3. ĐIỀU PHỐI ---
def start_process(name, gia_niem_yet):
    target_sites = ["bachhoaxanh.com", "cooponline.vn", "kingfoodmart.com", "aeonshop.com"]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        st.write(f"🔍 Đang tìm kiếm '{name}' trên các hệ thống siêu thị...")
        data = scrape_google_for_sites(page, name, target_sites)
        browser.close()

    if data:
        for res in data:
            if gia_niem_yet > 0:
                diff = res['Giá TT'] - gia_niem_yet
                res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
        return data
    return []

# --- UI ---
st.title("🚀 Genshai Retail Checker V32.0")
st.info("Hệ thống quét giá mục tiêu: Bách Hóa Xanh, Co.op Online, Kingfoodmart, Aeon Shop.")

with st.form("retail_form"):
    name_in = st.text_input("Tên sản phẩm đầy đủ", value="Kiwi - Dao Bào Vỏ 217")
    price_in = st.number_input("Giá niêm yết (Genshai)", value=81400)
    submitted = st.form_submit_button("KIỂM TRA GIÁ SIÊU THỊ")

if submitted:
    with st.spinner("Đang truy xuất dữ liệu từ các sàn bán lẻ..."):
        results = start_process(name_in, price_in)
        if results:
            st.success(f"Tìm thấy {len(results)} kết quả phù hợp!")
            st.table(pd.DataFrame(results))
        else:
            st.error("Không tìm thấy giá trên các website mục tiêu. Hãy thử điều chỉnh tên sản phẩm ngắn gọn hơn.")
