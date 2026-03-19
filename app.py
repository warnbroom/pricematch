import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess

# --- CÀI ĐẶT HỆ THỐNG CHO CLOUD ---
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
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- LOGIC QUÉT DỮ LIỆU ---

def scrape_lotte(page, barcode):
    """Bước 1: Tìm barcode trên Lotte"""
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=15000)
        content = page.evaluate("() => document.body.innerText")
        
        if "Không tìm thấy sản phẩm" in content:
            return None
            
        product_list = page.query_selector(".product-list")
        if product_list:
            text = product_list.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    return {"Nguồn": "Lotte Mart (Barcode)", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    """Bước 2 & 3: Tìm trên Google"""
    try:
        url = f"https://www.google.com/search?q=giá+{search_key}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        items = page.query_selector_all("div[class*='g']")
        for item in items[:3]:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else ""
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except: return None
    return None

# --- ĐIỀU PHỐI THEO THỨ TỰ 1 -> 2 -> 3 ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # 1. Tìm Barcode trên Lotte
        st.write("🔍 Đang tìm Barcode trên Lotte Mart...")
        res = scrape_lotte(page, barcode)
        
        # 2. Nếu thất bại, tìm Barcode trên Google
        if not res:
            st.write("⚠️ Lotte không có mã này. Đang thử tìm Barcode trên Google...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # 3. Nếu vẫn thất bại, tìm Tên sản phẩm trên Google
        if not res:
            st.write("⚠️ Google không thấy giá qua Barcode. Đang tìm theo Tên sản phẩm...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = ((res['Giá TT'] - gia_niem_yet) / gia_niem_yet * 100)
        res['Chênh lệch (%)'] = f"{diff:+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V26.8)")

with st.form("search_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode")
    name_in = c2.text_input("Tên sản phẩm")
    price_in = c3.number_input("Giá niêm yết", min_value=0)
    submitted = st.form_submit_button("KIỂM TRA THEO THỨ TỰ")

if submitted:
    if not (barcode_in and name_in):
        st.error("Hưng cần nhập cả Barcode và Tên để thực hiện đủ 3 bước nhé!")
    else:
        with st.spinner("Đang chạy quy trình so sánh..."):
            final_results = start_process(name_in, barcode_in, price_in)
            if final_results:
                st.dataframe(pd.DataFrame(final_results), use_container_width=True)
            else:
                st.error("Cả 3 bước đều không tìm thấy giá phù hợp.")
