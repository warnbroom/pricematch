import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time

st.set_page_config(page_title="Genshai Web Pro V37.0", layout="wide")

# --- Hưng chỉ cần 1 dòng kết nối duy nhất (Ví dụ từ Browserless.io) ---
# Đăng ký miễn phí lấy API_KEY để thay vào đây
SBR_WS_ENDPOINT = st.sidebar.text_input("Browserless Token", type="password")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def scrape_logic(page, query, gia_genshai):
    """
    Logic quét Google chuẩn: Barcode > Tên SP
    """
    try:
        url = f"https://www.google.com/search?q=giá+bán+{query}&hl=vi&gl=vn"
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Quét văn bản tầng sâu (Deep Text Scan) để tránh lỗi 0 khối
        full_text = page.evaluate("() => document.body.innerText")
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        
        valid_prices = []
        for m in price_matches:
            p = clean_price(m)
            # Lọc giá rác 150k và giá thùng 300k
            if gia_genshai * 0.4 < p < gia_genshai * 2.0:
                valid_prices.append(p)
        
        if valid_prices:
            best_price = min(valid_prices, key=lambda x: abs(x - gia_genshai))
            return {"Nguồn": "Google Web", "Giá TT": best_price, "Link": url}
    except: return None
    return None

# --- UI ---
st.title("🚀 Genshai Web App V37.0")
st.info("Hệ thống chạy trên Cloud - Tự động vượt rào cản Google.")

with st.form("web_pro_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("KIỂM TRA TRÊN WEB")

if submitted:
    if not SBR_WS_ENDPOINT:
        st.error("Hưng cần nhập Token kết nối ở Sidebar để bắt đầu.")
    else:
        with sync_playwright() as p:
            st.write("🔄 Đang mở trình duyệt đám mây...")
            # KẾT NỐI ĐÁM MÂY: Thay vì launch(), ta dùng connect_over_cdp()
            browser = p.chromium.connect_over_cdp(f"wss://chrome.browserless.io?token={SBR_WS_ENDPOINT}")
            context = browser.new_context()
            page = context.new_page()

            # Thứ tự: Barcode -> Tên
            res = scrape_logic(page, barcode_in, price_in)
            if not res:
                st.write("⚠️ Barcode không khớp, đang quét theo tên...")
                res = scrape_logic(page, name_in, price_in)

            if res:
                st.success("Đã tìm thấy giá thị trường!")
                st.table(pd.DataFrame([res]))
            else:
                st.error("Không tìm thấy kết quả. Có thể cần điều chỉnh lại tên SP.")
            
            browser.close()
