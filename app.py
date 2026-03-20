import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import subprocess
import time

# --- 1. SETUP HỆ THỐNG ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Price Checker V30.1", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. CÁC HÀM LOGIC GỐC ---

def scrape_lotte_v279(page, barcode):
    """Bước 1: Logic Lotte V27.9 (Quét innerText + split dòng)"""
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(2)
        content = page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for line in lines:
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                # Loại bỏ mốc lọc 150k rác để lấy giá sản phẩm
                if 1000 < price < 1000000 and price != 150000:
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_quet_gia(page, search_key, mode):
    """Bước 2 & 3: Logic quet_gia.py (Dùng div.g)"""
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Đúng Selector div.g từ file quet_gia.py
        items = page.query_selector_all("div.g")
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                # Giới hạn giá lẻ để tránh lấy nhầm giá thùng
                if 10000 < price < 200000:
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- 3. ĐIỀU PHỐI THEO TRÌNH TỰ ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # TRÌNH TỰ 1: Lotte theo Barcode (V27.9)
        st.write("🔍 Bước 1: Đang tìm Barcode trên Lotte Mart...")
        final_res = scrape_lotte_v279(page, barcode)
        
        # TRÌNH TỰ 2: Nếu chưa có, tìm Google theo Barcode (quet_gia.py)
        if not final_res:
            st.write("⚠️ Bước 2: Không thấy trên Lotte. Đang tìm Barcode trên Google...")
            final_res = scrape_google_quet_gia(page, barcode, "Google Barcode")
            
        # TRÌNH TỰ 3: Nếu vẫn chưa có, tìm Google theo Tên SP (quet_gia.py)
        if not final_res:
            st.write(f"⚠️ Bước 3: Không thấy Barcode. Đang tìm theo Tên: {name}...")
            final_res = scrape_google_quet_gia(page, name, "Google Tên SP")

        browser.close()

    if final_res and gia_niem_yet > 0:
        diff = final_res['Giá TT'] - gia_niem_yet
        final_res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [final_res] if final_res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Checker V30.1 - Trình tự chuẩn")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("BẮT ĐẦU KIỂM TRA")

if submitted:
    with st.spinner("Đang thực hiện quy trình 3 bước..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.success("Đã tìm thấy giá!")
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả sau cả 3 bước tìm kiếm.")
