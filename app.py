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

# --- 2. LOGIC QUÉT LOTTE (CHIẾN THUẬT TÀNG HÌNH) ---

def scrape_lotte(page, barcode):
    try:
        # Lotte đôi khi cần tìm chính xác chuỗi barcode
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        
        # Truy cập với timeout dài hơn
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # GIẢ LẬP NGƯỜI DÙNG: Cuộn trang nhẹ để kích hoạt load giá
        page.mouse.wheel(0, 500)
        time.sleep(2) # Chờ 2 giây để script của Lotte chạy
        
        # Chờ đợi một trong hai: Giá tiền xuất hiện HOẶC thông báo không thấy
        try:
            page.wait_for_selector(".product-item .price, text=₫", timeout=8000)
        except:
            if "Không tìm thấy sản phẩm" in page.content():
                return None

        # Bóc tách dữ liệu từ sản phẩm đầu tiên
        product = page.query_selector(".product-item")
        if product:
            price_elem = product.query_selector(".price, .product-price")
            if price_elem:
                price_text = price_elem.inner_text()
                return {
                    "Nguồn": "Lotte Mart (Barcode)", 
                    "Giá TT": clean_price(price_text), 
                    "Link": url
                }
    except Exception as e:
        st.warning(f"Lotte chưa phản hồi (Thử lại bước 2-3)...")
        return None
    return None

def scrape_google(page, search_key, mode="Barcode"):
    try:
        query = sanitize_name(search_key) if mode == "Tên SP" else search_key
        url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Tìm giá từ kết quả tìm kiếm Google
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

# --- 3. ĐIỀU PHỐI (VỚI CẤU HÌNH TÀNG HÌNH) ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        # Launch với các tham số ẩn danh chuyên sâu
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox", 
            "--disable-blink-features=AutomationControlled", # Ẩn dấu hiệu robot
            "--disable-infobars"
        ])
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # BƯỚC 1: LOTTE BARCODE
        st.write(f"🔍 Đang thử vượt rào Lotte Mart cho mã {barcode}...")
        res = scrape_lotte(page, barcode)
        
        # BƯỚC 2: GOOGLE BARCODE
        if not res:
            st.write("⚠️ Lotte chặn hoặc không thấy. Đang tìm Google Barcode...")
            res = scrape_google(page, barcode, mode="Barcode")
            
        # BƯỚC 3: GOOGLE TÊN SP
        if not res:
            st.write(f"⚠️ Đang tìm Google theo tên: {sanitize_name(name)}...")
            res = scrape_google(page, name, mode="Tên SP")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai (V27.4)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu Lee Kum Kee Thượng Hạng")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA NGAY")

if submitted:
    with st.spinner("Đang chạy quy trình tàng hình 3 bước..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Cả 3 bước đều thất bại. Có thể website đối thủ đã thay đổi cấu trúc hoàn toàn.")
