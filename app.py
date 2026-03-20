import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess
import time

# --- 1. SETUP ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    # Giữ lại số từ các định dạng giá phức tạp
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(2)
        content = page.evaluate("() => document.body.innerText")
        if "Không tìm thấy sản phẩm" in content: return None

        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for line in lines:
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                if 1000 < price < 150000: # Lọc giá rác
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_smart(page, search_key, mode="Tên SP"):
    """Logic quét toàn trang kết hợp Regex mạnh để bắt giá từ Co.op Online"""
    try:
        # Thay thế các ký tự đặc biệt như * bằng khoảng trắng để Google không bị 'loạn'
        query = search_key.replace('*', ' ').replace('x', ' ').replace('X', ' ')
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Lấy toàn bộ text để tránh sót các thẻ HTML lạ của Google
        content = page.evaluate("() => document.body.innerText")
        
        # REGEX MỚI: Tìm con số có định dạng giá (60.000) đứng cạnh ₫/đ
        # Ưu tiên bắt các cụm như '60.000 ₫' hoặc '60.000đ'
        matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', content)
        
        if matches:
            for m in matches:
                price = clean_price(m)
                # Kiểm tra giá lẻ (thường dưới 100k cho gia vị) để loại bỏ giá thùng
                if 1000 < price < 150000:
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": url}
    except: return None
    return None

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36")

        # Bước 1: Lotte Barcode
        st.write("🔍 Bước 1: Quét Lotte Mart...")
        res = scrape_lotte(page, barcode)
        
        # Bước 2: Google Barcode
        if not res:
            st.write("⚠️ Bước 1 không có. Quét Google Barcode...")
            res = scrape_google_smart(page, barcode, mode="Barcode")
            
        # Bước 3: Google Tên SP (Xử lý thông minh ký tự đặc biệt)
        if not res:
            st.write(f"⚠️ Bước 2 không ra. Đang tìm theo tên: {name}...")
            res = scrape_google_smart(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Genshai Price Checker (V28.4 - Google Smart)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("KIỂM TRA GIÁ")

if submitted:
    with st.spinner("Đang truy xuất dữ liệu..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Vẫn không tìm thấy. Có thể Google đang chặn hoặc định dạng giá quá lạ.")
