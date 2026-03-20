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
    # Xử lý tất cả ký tự không phải số, bao gồm cả các ký hiệu ₫ đặc biệt
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

def sanitize_name(name):
    # Xóa bỏ hoàn toàn phần *12 hoặc các ký tự gây nhiễu để Google tìm chính xác
    clean = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
    # Loại bỏ các từ khóa quá chuyên sâu về quy cách đóng gói nếu cần
    clean = clean.replace('12', '').strip() 
    return " ".join(clean.split())

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte(page, barcode):
    """Quét Lotte với logic lọc giá rác"""
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
                if 1000 < price < 150000: # Lọc mốc 150k
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    """Logic Google cải tiến để bắt đúng giá từ Co.op Online"""
    try:
        query = search_key if mode == "Barcode" else sanitize_name(search_key)
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Tìm trong các thẻ chứa kết quả tìm kiếm
        items = page.query_selector_all("div.g, div[data-hveid]")
        for item in items[:5]: # Kiểm tra 5 kết quả đầu tiên để tăng cơ hội
            text = item.inner_text()
            # Regex mới: Tìm con số có dấu chấm/phẩy đi kèm ký hiệu tiền tệ
            # Ví dụ: 60.000 ₫ hoặc 60,000đ
            match = re.search(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', text)
            if match:
                price = clean_price(match.group(1))
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
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36")

        # 1. Lotte Barcode
        st.write("🔍 Bước 1: Quét Lotte Mart...")
        res = scrape_lotte(page, barcode)
        
        # 2. Google Barcode
        if not res:
            st.write("⚠️ Bước 1 không có. Quét Google Barcode...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # 3. Google Tên SP (Quan trọng cho Co.op)
        if not res:
            st.write(f"⚠️ Bước 2 không ra. Tìm tên sạch: {sanitize_name(name)}...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Genshai Price Checker (V28.1 - Google Fix)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("KIỂM TRA NGAY")

if submitted:
    with st.spinner("Đang truy xuất dữ liệu..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Vẫn không tìm thấy. Có thể Google đang chặn hoặc định dạng giá quá lạ.")
