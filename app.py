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

st.set_page_config(page_title="Genshai Price Checker V30.2", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TỪNG BƯỚC ---

def scrape_lotte_v279_fixed(page, barcode):
    """
    ƯU TIÊN 1: Lotte Mart (Logic V27.9 cải tiến)
    Sửa lỗi lấy nhầm giá combo 300k bằng cách thu hẹp khoảng giá lẻ.
    """
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(2)
        
        content = page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        for line in lines:
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                # BỘ LỌC CHIẾN THUẬT:
                # 1. Bỏ qua 150.000 (mốc lọc rác của Lotte)
                # 2. Chỉ lấy giá > 10k và < 120k để chắc chắn là chai lẻ, không phải combo/thùng
                if 10000 < price < 120000 and price != 150000:
                    return {"Nguồn": "Lotte Mart (Chai lẻ)", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_quet_gia(page, search_key, mode):
    """
    ƯU TIÊN 2 & 3: Google (Logic quet_gia.py chuẩn)
    """
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        items = page.query_selector_all("div.g")
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                # Áp dụng bộ lọc giá lẻ tương tự để bắt đúng giá Co.op Online
                if 10000 < price < 120000:
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- 3. ĐIỀU PHỐI THEO TRÌNH TỰ CHUẨN ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # BƯỚC 1: Lotte Barcode
        st.write("🔍 Bước 1: Quét Lotte Mart (Lọc giá lẻ)...")
        final_res = scrape_lotte_v279_fixed(page, barcode)
        
        # BƯỚC 2: Google Barcode
        if not final_res:
            st.write("⚠️ Bước 2: Tìm Barcode trên Google...")
            final_res = scrape_google_quet_gia(page, barcode, "Barcode")
            
        # BƯỚC 3: Google Tên SP
        if not final_res:
            st.write(f"⚠️ Bước 3: Tìm theo Tên trên Google: {name}...")
            final_res = scrape_google_quet_gia(page, name, "Tên SP")

        browser.close()

    if final_res and gia_niem_yet > 0:
        diff = final_res['Giá TT'] - gia_niem_yet
        final_res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [final_res] if final_res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Checker V30.2 - Final Logic")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("KIỂM TRA NGAY")

if submitted:
    with st.spinner("Đang thực hiện quy trình lọc giá chuẩn..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.success("Đã tìm thấy giá chai lẻ!")
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy giá trong khoảng 10k - 120k.")
