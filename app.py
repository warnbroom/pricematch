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

st.set_page_config(page_title="Genshai Checker V28.9", layout="wide")

def clean_price(text):
    if not text: return 0
    # Xử lý cả dấu chấm và phẩy trong giá tiền
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte_goc(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=20000)
        time.sleep(2)
        content = page.evaluate("() => document.body.innerText")
        if "Không tìm thấy sản phẩm" in content: return None
        
        # Lấy giá lẻ, bỏ qua mốc lọc 150k rác
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for line in lines:
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                if 1000 < price < 150000: 
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_fallback(page, search_key, mode):
    """Quét văn bản toàn trang nếu div.g bị trống"""
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1) # Chờ Google render kết quả
        
        # Lấy toàn bộ văn bản mà mắt người thấy được
        content = page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        log_entries = [f"<b>[Hệ thống]</b> Đang quét {len(lines)} dòng văn bản..."]
        
        for line in lines:
            # Tìm dòng chứa ký hiệu tiền tệ và có số
            if ("₫" in line or "đ" in line) and any(char.isdigit() for char in line):
                price = clean_price(line)
                # Lọc giá lẻ gia vị (1k - 150k)
                if 1000 < price < 150000:
                    log_entries.append(f"✅ Bắt được giá: {price} trong dòng: '{line[:50]}'")
                    st.session_state.google_logs = log_entries
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": url}
        
        st.session_state.google_logs = log_entries
    except Exception as e:
        st.session_state.google_logs = [f"Lỗi: {str(e)}"]
    return None

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    if 'google_logs' not in st.session_state:
        st.session_state.google_logs = []
        
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        # Dùng User Agent thật hơn để tránh bị Google soi
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36")

        # Bước 1: Lotte
        res = scrape_lotte_goc(page, barcode)
        
        # Bước 2 & 3: Google (Dùng cơ chế quét văn bản toàn phần)
        if not res:
            res = scrape_google_fallback(page, barcode, "Barcode")
        if not res:
            res = scrape_google_fallback(page, name, "Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Checker V28.9 - Toàn Diện")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="78895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("KIỂM TRA GIÁ")

if submitted:
    st.session_state.google_logs = []
    with st.spinner("Đang bóc tách dữ liệu Google theo cách mới..."):
        data = start_process(name_in, barcode_in, price_in)
        
        with st.expander("🛠 LOG QUÉT VĂN BẢN (GOOGLE FALLBACK)", expanded=True):
            for log in st.session_state.google_logs:
                st.markdown(log, unsafe_allow_html=True)

        if data:
            st.success("Đã tìm thấy giá thành công!")
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy giá trong văn bản trang Google. Có thể Google đang hiển thị Captcha.")
