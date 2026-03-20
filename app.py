import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess
import time

# --- 1. SETUP HỆ THỐNG ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC GỐC TỪ FILE QUET_GIA_LOTTE.PY ---
def scrape_lotte_goc(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=20000)
        time.sleep(2) # Đợi load giá
        
        # ĐÂY LÀ LOGIC HƯNG ĐANG DÙNG HIỆU QUẢ
        content = page.evaluate("() => document.body.innerText")
        
        if "Không tìm thấy sản phẩm" in content:
            return None
            
        if "₫" in content or "đ" in content:
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            for line in lines:
                if "₫" in line or "đ" in line:
                    price = clean_price(line)
                    # Loại bỏ mốc lọc 150.000 và các số rác
                    if 1000 < price < 150000: 
                        return {"Nguồn": "Lotte Mart (Gốc)", "Giá TT": price, "Link": url}
    except: return None
    return None

# --- 3. LOGIC GỐC TỪ FILE QUET_GIA.PY ---
def scrape_google_goc(page, search_key, mode):
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # TUÂN THỦ ĐÚNG div.g VÀ inner_text()
        items = page.query_selector_all("div.g")
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- 4. ĐIỀU PHỐI 3 BƯỚC ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # BƯỚC 1: Lotte (Dùng quet_gia_lotte.py)
        st.write("🔍 Bước 1: Quét Lotte Mart (Logic Gốc)...")
        res = scrape_lotte_goc(page, barcode)
        
        # BƯỚC 2: Google Barcode (Dùng quet_gia.py)
        if not res:
            st.write("⚠️ Bước 1 không ra. Quét Google Barcode...")
            res = scrape_google_goc(page, barcode, "Barcode")
            
        # BƯỚC 3: Google Tên sản phẩm (Dùng quet_gia.py)
        if not res:
            st.write(f"⚠️ Bước 2 không ra. Quét Google Tên SP: {name}...")
            res = scrape_google_goc(page, name, "Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Price Checker (V28.7 - Combo Gốc)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA")

if submitted:
    with st.spinner("Đang chạy quy trình 3 bước chuẩn..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.success("Đã lấy được dữ liệu!")
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả.")
