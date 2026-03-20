import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess

# --- 1. SETUP MÔI TRƯỜNG ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    # Logic tách số nguyên bản
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC GỐC TỪ FILE QUET_GIA.PY ---
def scrape_google_logic_goc(page, search_key, mode):
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # SỬ DỤNG ĐÚNG SELECTOR TRONG FILE QUET_GIA.PY
        items = page.query_selector_all("div.g")
        
        for item in items:
            text = item.inner_text()
            # Kiểm tra ký hiệu tiền tệ như code gốc
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                # Filter giá hợp lý để tránh lấy nhầm năm hoặc số lượng
                if 1000 < price < 10000000:
                    # Lấy link từ thẻ a bên trong div.g
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except:
        return None
    return None

# --- 3. ĐIỀU PHỐI 3 BƯỚC THEO Ý HƯNG ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # BƯỚC 1: Lotte Barcode (Dùng logic evaluate body gốc của Hưng)
        st.write("🔍 Bước 1: Quét Lotte (Barcode)...")
        url_lotte = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        try:
            page.goto(url_lotte, wait_until="networkidle", timeout=20000)
            content = page.evaluate("() => document.body.innerText")
            if "₫" in content or "đ" in content:
                # Tìm dòng giá đầu tiên trong danh sách (loại bỏ mốc 150k rác)
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                for line in lines:
                    if ("₫" in line or "đ" in line) and clean_price(line) != 150000:
                        p_val = clean_price(line)
                        if 1000 < p_val < 1000000:
                            res = {"Nguồn": "Lotte Mart", "Giá TT": p_val, "Link": url_lotte}
                            break
        except: pass

        # BƯỚC 2: Google Barcode (Dùng logic div.g)
        if not res:
            st.write("⚠️ Bước 2: Quét Google (Barcode)...")
            res = scrape_google_logic_goc(page, barcode, "Barcode")

        # BƯỚC 3: Google Tên sản phẩm (Dùng logic div.g)
        if not res:
            st.write(f"⚠️ Bước 3: Quét Google (Tên SP)...")
            res = scrape_google_logic_goc(page, name, "Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Hệ Thống Kiểm Giá (Bám Sát Logic Gốc)")

with st.form("search_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA")

if submitted:
    with st.spinner("Đang chạy đúng logic file quet_gia.py..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả với logic hiện tại.")
