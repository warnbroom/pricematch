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
    # Xử lý các định dạng như 62.900đ hoặc 62,900
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC QUÉT LOTTE (FIX LẤY NHẦM GIÁ BỘ LỌC) ---
def scrape_lotte(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=20000)
        
        # Chờ 2 giây để chắc chắn giá đã load xong
        time.sleep(2)

        # CẢI TIẾN: Chỉ lấy text trong vùng chứa sản phẩm, bỏ qua cột bộ lọc bên trái
        # Selector '.product-list' hoặc '.category-view' giúp loại bỏ con số 150.000 ở bộ lọc
        content = page.evaluate("""() => {
            const productArea = document.querySelector('.product-list, .category-view, #search-result');
            return productArea ? productArea.innerText : document.body.innerText;
        }""")
        
        if "Không tìm thấy sản phẩm" in content:
            return None
            
        if "₫" in content or "đ" in content:
            # Tách các dòng và tìm dòng có chứa giá sản phẩm
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            for line in lines:
                # Nếu dòng chứa '₫' và có số, khả năng cao là giá SP thực tế
                if ("₫" in line or "đ" in line) and any(char.isdigit() for char in line):
                    price = clean_price(line)
                    # Loại bỏ các con số rác quá nhỏ hoặc quá lớn
                    if 1000 < price < 10000000:
                        return {"Nguồn": "Lotte Mart (Chính xác)", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        items = page.query_selector_all("div.g")
        for item in items[:3]:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36")

        # Bước 1: Lotte (Dùng logic khoanh vùng mới)
        st.write("🔍 Đang bóc tách giá từ vùng sản phẩm Lotte...")
        res = scrape_lotte(page, barcode)
        
        # Bước 2 & 3 dự phòng
        if not res:
            res = scrape_google(page, barcode, mode="Barcode")
        if not res:
            clean_name = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
            res = scrape_google(page, clean_name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Genshai Price Checker (V27.8 - Fix Giá)")

with st.form("search_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA LẠI")

if submitted:
    with st.spinner("Đang quét..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả.")
