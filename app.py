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
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte_goc(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=20000)
        time.sleep(2)
        content = page.evaluate("() => document.body.innerText")
        if "Không tìm thấy sản phẩm" in content: return None
        if "₫" in content or "đ" in content:
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            for line in lines:
                if "₫" in line or "đ" in line:
                    price = clean_price(line)
                    if 1000 < price < 150000: 
                        return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_with_log(page, search_key, mode):
    """Bám sát div.g và in log chi tiết"""
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Lấy tất cả div.g theo logic gốc của Hưng
        items = page.query_selector_all("div.g")
        
        log_entries = []
        log_entries.append(f"<b>[Hệ thống]</b> Đã tìm thấy {len(items)} khối kết quả (div.g)")
        
        for i, item in enumerate(items[:5]): # Log 5 kết quả đầu
            text = item.inner_text().replace('\n', ' ')
            log_entries.append(f"<b>[Kết quả {i+1}]</b>: {text[:150]}...")
            
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    st.session_state.google_logs = log_entries # Lưu log vào session
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
        
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
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Bước 1 & 2
        res = scrape_lotte_goc(page, barcode)
        if not res:
            res = scrape_google_with_log(page, barcode, "Barcode")
            
        # Bước 3: Tìm theo tên
        if not res:
            res = scrape_google_with_log(page, name, "Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Checker V28.8 - Debug Mode")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA")

if submitted:
    # Reset log
    st.session_state.google_logs = []
    
    with st.spinner("Đang truy xuất dữ liệu..."):
        data = start_process(name_in, barcode_in, price_in)
        
        # Hiển thị Log Debug
        with st.expander("🛠 XEM LOG XỬ LÝ DỮ LIỆU GOOGLE", expanded=True):
            if st.session_state.google_logs:
                for log in st.session_state.google_logs:
                    st.markdown(log, unsafe_allow_html=True)
            else:
                st.write("Không có dữ liệu log.")

        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy giá trong các khối div.g.")
