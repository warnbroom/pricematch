import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess
import time

# --- 1. SETUP HỆ THỐNG (STREAMLIT CLOUD) ---
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

def sanitize_name(name):
    # Loại bỏ ký tự đặc biệt để Google tìm kiếm chuẩn hơn
    clean = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
    return " ".join(clean.split())

# --- 2. LOGIC BÓC TÁCH DỮ LIỆU ---

def scrape_lotte(page, barcode):
    """Tìm Barcode trên Lotte Mart với logic chống lấy nhầm giá bộ lọc"""
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(3) 

        content = page.evaluate("() => document.body.innerText")
        if "Không tìm thấy sản phẩm" in content:
            return None

        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for line in lines:
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                # Chỉ lấy giá thực tế (thường < 150k), bỏ qua mốc lọc 150.000
                if 1000 < price < 150000:
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    """Logic tìm kiếm từ file quet_gia.py"""
    try:
        query = search_key if mode == "Barcode" else sanitize_name(search_key)
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Quét các khối kết quả tìm kiếm
        items = page.query_selector_all("div.g")
        for item in items[:3]: # Kiểm tra 3 kết quả đầu tiên
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- 3. ĐIỀU PHỐI QUY TRÌNH ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36")

        # BƯỚC 1: Lotte Barcode
        st.write("🔍 Bước 1: Đang quét trực tiếp trên Lotte Mart...")
        res = scrape_lotte(page, barcode)
        
        # BƯỚC 2: Google Barcode
        if not res:
            st.write("⚠️ Bước 1 không có. Đang tìm Barcode trên Google...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # BƯỚC 3: Google Tên SP
        if not res:
            st.write(f"⚠️ Bước 2 không ra. Đang tìm theo tên: {sanitize_name(name)}...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V28.0)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("BẮT ĐẦU SO SÁNH")

if submitted:
    with st.spinner("Đang thực hiện quy trình tìm kiếm 3 bước..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.success("Đã tìm thấy dữ liệu giá!")
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả phù hợp trên cả Lotte và Google.")
