import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import subprocess
import time

# --- 1. SETUP ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Debug V34.5", layout="wide")

# --- CẤU HÌNH PROXY (BẮT BUỘC ĐIỀN ĐỂ CHẠY) ---
PROXY_SERVER = st.sidebar.text_input("Proxy Server (http://ip:port)", "")
PROXY_USER = st.sidebar.text_input("Proxy User", "")
PROXY_PASS = st.sidebar.text_input("Proxy Pass", "", type="password")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_google_debug(page, search_key, gia_genshai):
    url = f"https://www.google.com/search?q=giá+bán+{search_key.replace(' ', '+')}&hl=vi"
    screenshot = None
    data = None
    
    try:
        # Cố gắng truy cập
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5) # Chờ Google load Captcha (nếu có)
        
        # ÉP CHỤP MÀN HÌNH TRƯỚC KHI XỬ LÝ DỮ LIỆU
        screenshot = page.screenshot(full_page=False)
        
        # Quét văn bản
        full_text = page.evaluate("() => document.body.innerText")
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        
        for m in price_matches:
            p = clean_price(m)
            if gia_genshai * 0.4 < p < gia_genshai * 2.0:
                data = {"Nguồn": "Google", "Giá TT": p, "Link": url}
                break
    except Exception as e:
        st.error(f"Lỗi kết nối: {str(e)}")
        
    return data, screenshot

# --- 3. GIAO DIỆN ---
st.title("🚀 Genshai Debug V34.5")

with st.form("debug_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Mã Barcode", value="8851130050753")
    name_in = c2.text_input("Tên sản phẩm", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("CHẠY KIỂM TRA & CHỤP ẢNH")

if submitted:
    with sync_playwright() as p:
        proxy = {"server": PROXY_SERVER, "username": PROXY_USER, "password": PROXY_PASS} if PROXY_SERVER else None
        
        # Mở trình duyệt với Proxy
        browser = p.chromium.launch(headless=True, proxy=proxy)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        st.info("🔄 Đang thử tìm theo Barcode...")
        res, ss = scrape_google_debug(page, barcode_in, price_in)
        
        if not res:
            st.info("🔄 Barcode thất bại, đang thử tìm theo Tên...")
            res, ss = scrape_google_debug(page, name_in, price_in)
        
        # HIỂN THỊ ẢNH NGAY LẬP TỨC ĐỂ DEBUG
        if ss:
            st.subheader("🖼 Ảnh chụp thực tế từ Google:")
            st.image(ss, use_column_width=True)
        else:
            st.error("❌ Không thể chụp ảnh màn hình. Proxy có thể đã bị lỗi hoặc sai thông tin đăng nhập.")
            
        if res:
            st.success("✅ Tìm thấy kết quả!")
            st.table(pd.DataFrame([res]))
            
        browser.close()
