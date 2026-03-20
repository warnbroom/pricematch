import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess

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
    # Lấy chính xác các cụm số
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

def sanitize_name(name):
    """Làm sạch tên để Google tìm kiếm tốt nhất"""
    clean = re.sub(r'[\*xX\(\)\[\]]', ' ', name)
    return " ".join(clean.split())

# --- 2. LOGIC QUÉT LOTTE (NÂNG CẤP ĐỘ NHẠY) ---

def scrape_lotte(page, barcode):
    try:
        # Giữ nguyên mã barcode có số 0 hoặc không để tìm kiếm
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        
        # Bước 1: Truy cập và chờ đợi mạng rỗi
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Bước 2: ÉP BUỘC CHỜ - Đợi cho đến khi text có ký hiệu '₫' xuất hiện
        # Điều này đảm bảo JavaScript đã chạy xong và hiện giá tiền
        page.wait_for_selector("text=₫", timeout=10000)
        
        # Kiểm tra nếu trang báo không tìm thấy
        if "Không tìm thấy sản phẩm" in page.content():
            return None
            
        # Bước 3: Quét vùng chứa sản phẩm đầu tiên
        # Selector mới linh hoạt hơn cho giao diện Lotte
        product_card = page.query_selector(".product-item, [class*='product-list'], .item")
        if product_card:
            card_text = product_card.inner_text()
            if "₫" in card_text or "đ" in card_text:
                # Tìm dòng chứa giá tiền
                lines = [l.strip() for l in card_text.split('\n') if "₫" in l or "đ" in l]
                if lines:
                    return {
                        "Nguồn": "Lotte Mart (Barcode)", 
                        "Giá TT": clean_price(lines[0]), 
                        "Link": url
                    }
    except Exception as e:
        # In lỗi ra console để debug nếu cần
        print(f"Lotte Error: {e}")
        return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    """Logic tìm kiếm Google tối ưu"""
    try:
        query = sanitize_name(search_key) if mode == "Tên SP" else search_key
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        results = page.query_selector_all("div.g, div[data-hveid], .v7W49e")
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

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        # Giả lập màn hình máy tính để Lotte hiện đầy đủ giao diện
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # BƯỚC 1: LOTTE BARCODE (Ưu tiên tuyệt đối)
        st.write(f"🔍 Đang quét Lotte Mart với mã: {barcode}...")
        res = scrape_lotte(page, barcode)
        
        # BƯỚC 2: GOOGLE BARCODE
        if not res:
            st.write("⚠️ Bước 1 không ra kết quả. Đang thử Google Barcode...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # BƯỚC 3: GOOGLE TÊN SP
        if not res:
            st.write(f"⚠️ Đang thử tìm theo tên: {sanitize_name(name)}...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- GIAO DIỆN ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V27.3)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu Lee Kum Kee Thượng Hạng")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("BẮT ĐẦU KIỂM TRA")

if submitted:
    with st.spinner("Đang thực hiện quy trình 3 bước chuyên sâu..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.error("Không tìm thấy kết quả sau 3 bước. Hưng hãy kiểm tra lại barcode trên web Lotte có đang bị thay đổi không nhé.")
