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
        st.error(f"Lỗi cài đặt trình duyệt: {e}")

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

def sanitize_name(name):
    clean = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
    return " ".join(clean.split())

# --- 2. LOGIC QUÉT LOTTE (CÓ CHỌN KHU VỰC) ---

def scrape_lotte(page, barcode):
    try:
        # Bước A: Vào trang chủ để xác nhận khu vực trước
        page.goto("https://www.lottemart.vn/", wait_until="networkidle", timeout=30000)
        
        # Thử đóng popup nếu có
        try:
            page.click(".close-popup", timeout=3000)
        except: pass

        # Bước B: Tìm mã barcode
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Bước C: Cuộn trang để kích hoạt Lazy Load
        page.evaluate("window.scrollTo(0, 500)")
        time.sleep(3) 

        # Kiểm tra nội dung trang
        content = page.content()
        if "Không tìm thấy sản phẩm" in content:
            return None

        # Bước D: Bóc tách giá từ thẻ sản phẩm chuẩn
        # Nhắm vào class .price-amount hoặc .product-price-view
        product_item = page.query_selector(".product-item, .item-inner")
        if product_item:
            # Lấy text chứa ký hiệu ₫
            price_text = product_item.inner_text()
            if "₫" in price_text or "đ" in price_text:
                # Trích xuất con số trước chữ ₫
                price_val = clean_price(price_text.split("₫")[0])
                if price_val > 1000:
                    return {"Nguồn": "Lotte Mart (Barcode)", "Giá TT": price_val, "Link": url}
    except Exception as e:
        print(f"Lotte Debug: {e}")
        return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    """Logic tìm kiếm Google dự phòng"""
    try:
        query = sanitize_name(search_key) if mode == "Tên SP" else search_key
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        results = page.query_selector_all("div.g, div[data-hveid]")
        for item in results:
            text = item.inner_text()
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
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768}
        )
        page = context.new_page()

        # BƯỚC 1: LOTTE
        st.write(f"🔍 Bước 1: Đang thâm nhập Lotte Mart (Mã {barcode})...")
        res = scrape_lotte(page, barcode)
        
        # BƯỚC 2: GOOGLE BARCODE
        if not res:
            st.write("⚠️ Bước 1 không có giá. Đang thử Google Barcode...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # BƯỚC 3: GOOGLE TÊN SP
        if not res:
            st.write(f"⚠️ Bước 2 không ra. Đang tìm tên: {sanitize_name(name)}...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V27.5)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu Lee Kum Kee Thượng Hạng")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA NGAY")

if submitted:
    with st.spinner("Đang thực hiện quy trình 3 bước (Lotte sẽ cần thời gian tải trang)..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Dù đã cố gắng nhưng Lotte Mart vẫn không trả về dữ liệu. Hưng hãy thử lại vào lúc khác hoặc kiểm tra xem website Lotte có đang bảo trì không nhé.")
