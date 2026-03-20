import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess

# --- SETUP HỆ THỐNG CHO STREAMLIT CLOUD ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception:
        pass

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- BƯỚC 1: LOGIC TỪ FILE QUET_GIA_LOTTE.PY CỦA HƯNG ---
def scrape_lotte(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=20000)
        
        # SỬ DỤNG ĐÚNG LOGIC CỦA HƯNG
        content = page.evaluate("() => document.body.innerText")
        
        # Kiểm tra nếu trang báo không tìm thấy (để tránh lấy nhầm giá gợi ý)
        if "Không tìm thấy sản phẩm" in content:
            return None
            
        if "₫" in content or "đ" in content:
            # Tách dòng và tìm dòng chứa giá như code gốc của Hưng
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            for line in lines:
                if "₫" in line or "đ" in line:
                    price = clean_price(line)
                    if 1000 < price < 10000000:
                        return {"Nguồn": "Lotte Mart (Gốc)", "Giá TT": price, "Link": url}
    except:
        return None
    return None

# --- BƯỚC 2 & 3: LOGIC GOOGLE (QUET_GIA.PY) ---
def scrape_google(page, search_key, mode="Barcode"):
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Quét div.g như logic quet_gia.py
        items = page.query_selector_all("div.g")
        for item in items[:3]:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except:
        return None
    return None

# --- ĐIỀU PHỐI 3 BƯỚC ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36")

        # 1. Lotte Barcode (Dùng code Hưng)
        st.write("🔍 Đang chạy logic Lotte gốc...")
        res = scrape_lotte(page, barcode)
        
        # 2. Google Barcode
        if not res:
            st.write("⚠️ Lotte không ra, tìm Google Barcode...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # 3. Google Tên SP (Tối ưu dấu * để ra Co.op Online)
        if not res:
            clean_name = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
            st.write(f"⚠️ Đang tìm Google theo tên: {clean_name}...")
            res = scrape_google(page, clean_name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Price Checker (V27.7 - Logic Gốc)")

with st.form("search_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA GIÁ")

if submitted:
    with st.spinner("Đang chạy..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả.")
