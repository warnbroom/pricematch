import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess

# --- SETUP HỆ THỐNG ---
def install_playwright():
    try:
        with sync_playwright() as p:
            p.chromium.launch()
    except Exception:
        subprocess.run(["playwright", "install", "chromium"])

install_playwright()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    # Xử lý các trường hợp giá như "60.000" hoặc "60,000"
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

# --- LOGIC QUÉT ---

def scrape_lotte(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=15000)
        if "Không tìm thấy sản phẩm" in page.content():
            return None
        product = page.query_selector(".product-list")
        if product:
            text = product.inner_text()
            if "₫" in text or "đ" in text:
                # Tìm dòng có chứa ký hiệu tiền tệ
                for line in text.split('\n'):
                    if any(c in line for c in ["₫", "đ"]):
                        return {"Nguồn": "Lotte Mart", "Giá TT": clean_price(line), "Link": url}
    except: return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # NÂNG CẤP: Tìm tất cả các kết quả tìm kiếm (thẻ h3 là tiêu đề, sau đó tìm giá quanh đó)
        results = page.query_selector_all("div.g, div[data-hveid]")
        
        for item in results:
            text = item.inner_text()
            # Nếu trong block này có chứa ký hiệu tiền tệ
            if any(c in text for c in ["₫", "đ", "VND"]):
                # Trích xuất các cụm số đứng gần chữ ₫
                price_match = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', text)
                if not price_match:
                    price_match = re.findall(r'[₫đ]\s?(\d{1,3}(?:[\.,]\d{3})+)', text)
                
                if price_match:
                    price = clean_price(price_match[0])
                    if 1000 < price < 10000000:
                        link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else url
                        return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- ĐIỀU PHỐI 3 BƯỚC ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Bước 1: Lotte Barcode
        st.write("🔍 Bước 1: Tìm Barcode trên Lotte Mart...")
        res = scrape_lotte(page, barcode)
        
        # Bước 2: Google Barcode
        if not res:
            st.write("⚠️ Bước 2: Tìm Barcode trên Google...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # Bước 3: Google Tên SP (Quan trọng nhất)
        if not res:
            st.write("⚠️ Bước 3: Tìm theo Tên sản phẩm trên Google...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V26.9)")
with st.form("search_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="78895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA NGAY")

if submitted:
    with st.spinner("Đang thực hiện quy trình 3 bước..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy giá sau 3 bước kiểm tra.")
