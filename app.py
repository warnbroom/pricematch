import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import subprocess
import time
import urllib.parse

# --- 1. SETUP ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Proxy Pro V34.4", layout="wide")

# --- CẤU HÌNH PROXY (Hưng thay thông số của bên cung cấp vào đây) ---
# Nếu Hưng chưa có Proxy, có thể mua tại các bên như Webshare, Tinproxy, ProxyNo1...
PROXY_SERVER = "http://your-proxy-address:port" 
PROXY_USER = "your-username"
PROXY_PASS = "your-password"

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM GOOGLE VỚI PROXY ---

def scrape_google_proxy(page, search_key, mode, gia_genshai):
    try:
        url = f"https://www.google.com/search?q=giá+bán+{search_key.replace(' ', '+')}&hl=vi&gl=vn"
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Chụp màn hình để kiểm tra xem IP Proxy có bị Google chặn không
        screenshot = page.screenshot(full_page=False)

        # Đọc dữ liệu văn bản tầng sâu (Deep Text Scan)
        full_text = page.evaluate("() => document.body.innerText")
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        
        valid_prices = []
        for m in price_matches:
            p = clean_price(m)
            # Filter theo giá niêm yết để tránh giá thùng 300k
            if gia_genshai * 0.4 < p < gia_genshai * 2.0:
                valid_prices.append(p)
        
        if valid_prices:
            best_price = min(valid_prices, key=lambda x: abs(x - gia_genshai))
            return {"data": {"Nguồn": f"Google ({mode})", "Giá TT": best_price, "Link": url}, "screenshot": screenshot}
            
        return {"data": None, "screenshot": screenshot}
    except:
        return {"data": None, "screenshot": None}

# --- 3. ĐIỀU PHỐI VỚI PROXY ---
def start_process(name, barcode, price_niemyet, use_proxy):
    final_res = None
    final_screenshot = None
    
    with sync_playwright() as p:
        # Cấu hình Proxy vào trình duyệt
        proxy_config = {
            "server": PROXY_SERVER,
            "username": PROXY_USER,
            "password": PROXY_PASS
        } if use_proxy else None

        browser = p.chromium.launch(
            headless=True, 
            proxy=proxy_config, # Kích hoạt Proxy tại đây
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        # Thực hiện tìm kiếm theo trình tự Barcode > Tên
        st.write("🔍 Đang truy vấn qua Proxy...")
        res = scrape_google_proxy(page, barcode, "Barcode", price_niemyet)
        
        if not res['data']:
            st.write("⚠️ Barcode không ra kết quả, đang thử tìm theo Tên...")
            res = scrape_google_proxy(page, name, "Tên SP", price_niemyet)
            
        final_res = res['data']
        final_screenshot = res['screenshot']
        browser.close()

    return final_res, final_screenshot

# --- UI ---
st.title("🚀 Genshai Proxy Checker V34.4")

with st.sidebar:
    st.header("Cài đặt kết nối")
    use_p = st.toggle("Sử dụng Proxy dân cư", value=False)
    st.info("Bật Proxy để tránh lỗi reCAPTCHA khi có nhiều người dùng cùng quét.")

with st.form("main_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Mã Barcode", value="8851130050753")
    name_in = c2.text_input("Tên sản phẩm", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("KIỂM TRA HỆ THỐNG")

if submitted:
    res, ss = start_process(name_in, barcode_in, price_in, use_p)
    
    if ss:
        with st.expander("📷 KIỂM TRA TRẠNG THÁI GOOGLE", expanded=True):
            st.image(ss)
            
    if res:
        diff = res['Giá TT'] - price_in
        res['Chênh lệch (%)'] = f"{(diff / price_in * 100):+.1f}%"
        st.table(pd.DataFrame([res]))
    else:
        st.error("Không tìm thấy kết quả phù hợp. Kiểm tra lại ảnh chụp màn hình để xem có bị Captcha không.")
