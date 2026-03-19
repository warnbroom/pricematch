import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess

# 1. CƠ CHẾ TỰ CÀI ĐẶT TRÌNH DUYỆT (Dành riêng cho Streamlit Cloud)
def install_playwright():
    try:
        # Kiểm tra xem trình duyệt đã tồn tại chưa
        with sync_playwright() as p:
            p.chromium.launch()
    except Exception:
        # Nếu chưa có, tiến hành cài đặt cưỡng chế
        st.info("Đang khởi tạo trình duyệt lần đầu (mất khoảng 30s), Hưng vui lòng đợi nhé...")
        subprocess.run(["playwright", "install", "chromium"])

# Gọi hàm cài đặt ngay khi app load
install_playwright()

# 2. CẤU HÌNH GIAO DIỆN
st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- LOGIC QUÉT DỮ LIỆU ---
def fetch_data(query, barcode=None, gia_niem_yet=0):
    results = []
    try:
        with sync_playwright() as p:
            # Cấu hình bypass các lớp chặn của Cloud
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()

            search_key = barcode if barcode else query
            
            # Quét Lotte Mart
            try:
                lotte_url = f"https://www.lottemart.vn/vi-nsg/category?q={search_key}"
                page.goto(lotte_url, wait_until="networkidle", timeout=15000)
                content = page.evaluate("() => document.body.innerText")
                if "₫" in content or "đ" in content:
                    lines = [l.strip() for l in content.split('\n') if l.strip()]
                    for line in lines:
                        if "₫" in line or "đ" in line:
                            price = clean_price(line)
                            if 1000 < price < 10000000:
                                diff = ((price - gia_niem_yet) / gia_niem_yet * 100) if gia_niem_yet > 0 else 0
                                results.append({"Nguồn": "Lotte Mart", "Giá TT": price, "Chênh lệch (%)": f"{diff:+.1f}%", "Link": lotte_url})
                                break
            except: pass

            # Quét Google
            try:
                google_url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
                page.goto(google_url, wait_until="domcontentloaded", timeout=15000)
                items = page.query_selector_all("div[class*='g']")
                for item in items[:2]:
                    text = item.inner_text()
                    link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else ""
                    if "₫" in text or "đ" in text:
                        price = clean_price(text)
                        if 1000 < price < 10000000:
                            diff = ((price - gia_niem_yet) / gia_niem_yet * 100) if gia_niem_yet > 0 else 0
                            results.append({"Nguồn": "Google", "Giá TT": price, "Chênh lệch (%)": f"{diff:+.1f}%", "Link": link})
                            break
            except: pass
            
            browser.close()
    except Exception as e:
        st.error(f"Lỗi khởi động trình duyệt: {str(e)}")
    return results

# --- GIAO DIỆN CHÍNH ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai")
st.markdown("---")

with st.form("check_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode")
    name_in = c2.text_input("Tên sản phẩm")
    price_in = c3.number_input("Giá niêm yết (Genshai)", min_value=0)
    submitted = st.form_submit_button("BẮT ĐẦU SO SÁNH")

if submitted:
    if not (barcode_in or name_in):
        st.warning("Hưng nhập thông tin vào đã nhé!")
    else:
        with st.spinner("Đang quét giá thị trường..."):
            data = fetch_data(name_in, barcode_in, price_in)
            if data:
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.info("Không tìm thấy kết quả phù hợp trên Lotte/Google.")
