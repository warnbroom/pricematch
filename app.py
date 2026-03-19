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

# --- LOGIC 1: LOTTE MART (CẬP NHẬT CHỐNG NHẦM GIÁ) ---
def logic_lotte(page, search_key):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={search_key}"
        page.goto(url, wait_until="networkidle", timeout=15000)
        
        # KIỂM TRA 1: Nếu thấy dòng chữ báo không tìm thấy thì thoát luôn
        no_result = page.query_selector("text='Không tìm thấy sản phẩm'")
        if no_result:
            return None
            
        # KIỂM TRA 2: Chỉ bóc tách giá từ các thẻ sản phẩm thực (class chứa 'product-item')
        # Điều này giúp loại bỏ các giá từ banner quảng cáo hoặc sản phẩm gợi ý ngoài danh sách
        product_list = page.query_selector(".product-list")
        if product_list:
            content = product_list.inner_text()
            if "₫" in content or "đ" in content:
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                for line in lines:
                    if "₫" in line or "đ" in line:
                        price = clean_price(line)
                        if 1000 < price < 10000000:
                            return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except:
        return None
    return None

# --- LOGIC 2: GOOGLE SEARCH ---
def logic_google(page, query):
    try:
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        items = page.query_selector_all("div[class*='g']")
        for item in items[:3]:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 10000000:
                    link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else ""
                    return {"Nguồn": "Google Search", "Giá TT": price, "Link": link}
    except:
        return None
    return None

# --- ĐIỀU PHỐI ---
def start_scraping(name, barcode, gia_niem_yet):
    results = []
    search_key = barcode if barcode else name
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        # Bước 1: Quét Lotte Mart
        lotte_res = logic_lotte(page, search_key)
        
        if lotte_res:
            results.append(lotte_res)
        else:
            # Bước 2: Nếu Lotte không có, quét Google
            google_res = logic_google(page, name if name else barcode)
            if google_res:
                results.append(google_res)

        browser.close()
    
    if results and gia_niem_yet > 0:
        for r in results:
            diff = ((r['Giá TT'] - gia_niem_yet) / gia_niem_yet * 100)
            r['Chênh lệch (%)'] = f"{diff:+.1f}%"
            
    return results

# --- GIAO DIỆN ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode")
    name_in = c2.text_input("Tên sản phẩm")
    price_in = c3.number_input("Giá niêm yết", min_value=0)
    submitted = st.form_submit_button("KIỂM TRA GIÁ")

if submitted:
    if not (barcode_in or name_in):
        st.warning("Vui lòng nhập thông tin!")
    else:
        with st.spinner("Đang thực hiện logic quét (Lotte -> Google)..."):
            final_data = start_scraping(name_in, barcode_in, price_in)
            if final_data:
                st.write("### Kết quả tìm thấy:")
                st.dataframe(pd.DataFrame(final_data), use_container_width=True)
            else:
                st.error("Không tìm thấy kết quả phù hợp trên cả Lotte và Google.")
