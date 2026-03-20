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
    # Xử lý mọi ký hiệu tiền tệ đặc biệt như trong hình Co.op Online
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
                if 1000 < price < 150000: # Lọc mốc 150k ở bộ lọc
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    try:
        # GIỮ NGUYÊN TÊN SẢN PHẨM: Không cắt bỏ bất kỳ ký tự nào
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # SỬ DỤNG LOGIC QUÉT TOÀN TRANG (innerText) ĐỂ KHÔNG SÓT KẾT QUẢ
        # Cách này giống hệt logic quet_gia_lotte.py mà Hưng thấy hiệu quả
        content = page.evaluate("() => document.body.innerText")
        
        # Tìm các dòng có chứa giá (số + ₫/đ)
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        for i, line in enumerate(lines):
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                # Chỉ lấy giá trong khoảng hợp lý cho sản phẩm lẻ
                if 1000 < price < 200000:
                    # Cố gắng lấy link từ kết quả gần đó nhất
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": url}
                    
    except: return None
    return None

# --- 3. ĐIỀU PHỐI QUY TRÌNH ---
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
            res = scrape_google(page, barcode, mode="Barcode")
            
        # Bước 3: Google Tên SP (Giữ nguyên tên gốc)
        if not res:
            st.write(f"⚠️ Bước 2 không ra. Tìm chính xác tên: {name}...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Price Checker (V28.3 - Nguyên Tên)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("KIỂM TRA GIÁ")

if submitted:
    with st.spinner("Đang tìm kiếm..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Vẫn không tìm thấy kết quả. Có thể Google đang hạn chế truy cập tự động.")
