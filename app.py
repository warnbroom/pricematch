import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess

# --- 1. KHẮC PHỤC LỖI EXECUTABLE TRÊN STREAMLIT CLOUD ---
@st.cache_resource
def install_browser():
    try:
        # Lệnh ép cài đặt chromium vào đúng thư mục hệ thống của app
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Lỗi cài đặt trình duyệt: {e}")

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    # Lấy chính xác các cụm số có phân cách bởi dấu chấm/phẩy
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

def sanitize_name(name):
    """Xử lý tên SP để Google không bị 'ngáo' bởi dấu *"""
    # Biến '500ml*12' thành '500ml 12' để Google tìm được Co.op Online
    clean = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
    return " ".join(clean.split())

# --- 2. LOGIC QUÉT DỮ LIỆU ---

def scrape_lotte(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=15000)
        # Chặn lấy nhầm giá gợi ý 150k
        if "Không tìm thấy sản phẩm" in page.content():
            return None
        product_list = page.query_selector(".product-list")
        if product_list:
            text = product_list.inner_text()
            if "₫" in text or "đ" in text:
                return {"Nguồn": "Lotte Mart", "Giá TT": clean_price(text), "Link": url}
    except: return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    try:
        query = sanitize_name(search_key) if mode == "Tên SP" else search_key
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Quét rộng để tìm giá từ Rich Snippets (như Co.op Online)
        results = page.query_selector_all("div.g, div[data-hveid], .v7W49e")
        for item in results:
            text = item.inner_text()
            # Regex bắt đúng định dạng 60.000đ
            match = re.search(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', text)
            if match:
                price = clean_price(match.group(1))
                if 1000 < price < 10000000:
                    link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- 3. ĐIỀU PHỐI 3 BƯỚC ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        # Launch với các cờ chống lỗi môi trường cloud
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")

        # Bước 1: Lotte Barcode
        st.write("🔍 Bước 1: Tìm Barcode trên Lotte Mart...")
        res = scrape_lotte(page, barcode)
        
        # Bước 2: Google Barcode
        if not res:
            st.write("⚠️ Bước 2: Tìm Barcode trên Google...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # Bước 3: Google Tên SP (Đã xóa dấu *)
        if not res:
            st.write(f"⚠️ Bước 3: Tìm theo Tên sạch: '{sanitize_name(name)}'...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V27.1)")

with st.form("search_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="78895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA LẠI")

if submitted:
    with st.spinner("Đang chạy quy trình 3 bước..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Vẫn không tìm thấy. Hưng kiểm tra lại mạng hoặc tên SP nhé.")
