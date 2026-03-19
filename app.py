import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time
import os

# 1. CẤU HÌNH GIAO DIỆN (Luôn đặt ở dòng đầu tiên)
st.set_page_config(page_title="Genshai Price Checker", layout="wide")

# Hàm làm sạch giá tiền
def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- LOGIC QUÉT DỮ LIỆU ---

def fetch_data(query, barcode=None):
    """Gộp logic quét từ Lotte và Google"""
    results = []
    
    with sync_playwright() as p:
        # Cấu hình đặc biệt để chạy trên GitHub/Streamlit Cloud
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Bước 1: Quét Lotte Mart (Ưu tiên Barcode)
        search_key = barcode if barcode else query
        try:
            lotte_url = f"https://www.lottemart.vn/vi-nsg/category?q={search_key}"
            page.goto(lotte_url, wait_until="networkidle", timeout=20000)
            content = page.evaluate("() => document.body.innerText")
            
            if "₫" in content or "đ" in content:
                # Tìm giá trong các dòng text
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                for i, line in enumerate(lines):
                    if "₫" in line or "đ" in line:
                        price = clean_price(line)
                        if 1000 < price < 5000000:
                            results.append({"Nguồn": "Lotte Mart", "Giá": price, "Link": lotte_url})
                            break
        except: pass

        # Bước 2: Quét Google Search (Nếu Lotte không có hoặc để so sánh thêm)
        try:
            google_url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
            page.goto(google_url, wait_until="domcontentloaded", timeout=20000)
            
            items = page.query_selector_all("div[class*='g']")
            for item in items[:3]: # Lấy 3 kết quả đầu
                text = item.inner_text()
                link_el = item.query_selector("a")
                link = link_el.get_attribute("href") if link_el else ""
                
                if "genshai.com.vn" in link: continue # Bỏ qua web nhà
                
                if "₫" in text or "đ" in text:
                    price = clean_price(text)
                    if 1000 < price < 10000000:
                        results.append({"Nguồn": "Google", "Giá": price, "Link": link})
                        break
        except: pass

        browser.close()
    return results

# --- GIAO DIỆN NGƯỜI DÙNG ---

st.title("🚀 Hệ Thống So Sánh Giá Genshai (V26.2)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔍 Kiểm tra lẻ", "📁 Xử lý file Excel"])

with tab1:
    with st.form("check_form"):
        col1, col2 = st.columns(2)
        barcode_in = col1.text_input("Mã Barcode")
        name_in = col2.text_input("Tên sản phẩm")
        submitted = st.form_submit_button("Bắt đầu quét")

    if submitted:
        if not barcode_in and not name_in:
            st.warning("Hưng ơi, nhập ít nhất Barcode hoặc Tên nhé!")
        else:
            with st.spinner("Đang lục tìm trên Lotte và Google..."):
                data = fetch_data(name_in, barcode_in)
                if data:
                    st.success(f"Tìm thấy {len(data)} kết quả!")
                    df = pd.DataFrame(data)
                    st.table(df)
                    for res in data:
                        st.caption(f"Chi tiết tại: {res['Link']}")
                else:
                    st.error("Không tìm thấy giá phù hợp. Hưng thử lại với tên khác xem sao.")

with tab2:
    st.info("Tính năng quét file Excel hàng loạt đang được tối ưu hóa cho server GitHub.")
    uploaded_file = st.file_uploader("Tải file .xlsx", type="xlsx")
    if uploaded_file:
        st.success("File đã tải lên thành công. Hệ thống đang sẵn sàng xử lý!")
