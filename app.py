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
    except Exception as e:
        st.error(f"Lỗi cài đặt: {e}")

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

def sanitize_name(name):
    # Loại bỏ dấu * để Google tìm thấy Co.op
    clean = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
    return " ".join(clean.split())

# --- 2. LOGIC QUÉT LOTTE (DÙNG XPATH SIÊU NHẠY) ---

def scrape_lotte(page, barcode):
    try:
        # Sử dụng đúng URL tìm kiếm
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Đợi 3 giây để JavaScript của Lotte đổ dữ liệu vào trang
        time.sleep(3)
        
        # Kiểm tra nếu trang báo rỗng
        if "Không tìm thấy sản phẩm" in page.content():
            return None

        # DÙNG XPATH: Tìm thẻ chứa ký hiệu ₫ gần nhất với khu vực sản phẩm
        # Đây là cách tìm "mù" nhưng cực kỳ hiệu quả khi class thay đổi
        price_element = page.xpath("//*[contains(text(), '₫')]").first
        if price_element:
            price_text = price_element.inner_text()
            return {
                "Nguồn": "Lotte Mart (Barcode)", 
                "Giá TT": clean_price(price_text), 
                "Link": url
            }
    except Exception as e:
        print(f"Lotte Debug: {e}")
    return None

def scrape_google(page, search_key, mode="Barcode"):
    try:
        query = sanitize_name(search_key) if mode == "Tên SP" else search_key
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Quét vùng kết quả tìm kiếm
        results = page.query_selector_all("div.g, div[data-hveid]")
        for item in results:
            text = item.inner_text()
            # Bắt giá 60.000đ
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
        # Chế độ giả lập người dùng thật
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # BƯỚC 1: LOTTE
        st.write("🔍 Đang quét Lotte Mart bằng cơ chế XPath...")
        res = scrape_lotte(page, barcode)
        
        # BƯỚC 2: GOOGLE BARCODE
        if not res:
            st.write("⚠️ Lotte không phản hồi giá. Chuyển sang Google Barcode...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # BƯỚC 3: GOOGLE TÊN SP (Dành cho Co.op Online)
        if not res:
            st.write(f"⚠️ Đang tìm theo tên sạch: {sanitize_name(name)}...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V27.6)")

with st.form("search_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu Lee Kum Kee Thượng Hạng")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA NGAY")

if submitted:
    with st.spinner("Hệ thống đang thâm nhập dữ liệu Lotte..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Dù đã dùng XPath nhưng Lotte vẫn không nhả dữ liệu. Hưng kiểm tra lại mạng nhé.")
