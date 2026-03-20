import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import subprocess
import time

# --- 1. SETUP HỆ THỐNG ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Google Pro V34.2", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM GOOGLE (CẤP ĐỘ CAO) ---

def scrape_google_pure(page, search_key, mode, gia_genshai):
    """
    Sử dụng kỹ thuật giả lập hành vi người dùng thật để tránh bị Google chặn 0 khối.
    """
    try:
        # URL với các tham số hl=vi và tbm=shop (nếu cần) để ép ra giá
        url = f"https://www.google.com/search?q=giá+bán+{search_key.replace(' ', '+')}&hl=vi&gl=vn"
        
        # Di chuyển chuột giả lập trước khi load để đánh lừa bot detection
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.mouse.move(100, 100) 
        time.sleep(2)

        # CHIẾN THUẬT 1: Quét các khối div.g truyền thống
        items = page.query_selector_all("div.g")
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                # Bộ lọc thông minh dựa trên giá niêm yết để tránh giá thùng 300k
                if gia_genshai * 0.4 < price < gia_genshai * 2.0:
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": url}

        # CHIẾN THUẬT 2: Quét toàn bộ Text trang (Dự phòng khi Google ẩn thẻ)
        # Regex tìm giá tiền Việt Nam chuẩn
        full_text = page.evaluate("() => document.body.innerText")
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        
        valid_prices = []
        for m in price_matches:
            p = clean_price(m)
            if gia_genshai * 0.4 < p < gia_genshai * 2.0:
                valid_prices.append(p)
        
        if valid_prices:
            # Lấy giá sát nhất với giá Genshai để đảm bảo cùng đơn vị bán lẻ
            best_price = min(valid_prices, key=lambda x: abs(x - gia_genshai))
            return {"Nguồn": f"Google ({mode} - Scan)", "Giá TT": best_price, "Link": url}
            
    except Exception: return None
    return None

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, price_niemyet):
    final_res = None
    with sync_playwright() as p:
        # Cấu hình Stealth tối đa
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox", 
            "--disable-blink-features=AutomationControlled",
            "--use-fake-ui-for-media-stream"
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        # BƯỚC 1: TÌM THEO BARCODE
        st.write(f"🔍 Bước 1: Tìm theo Barcode ({barcode})...")
        final_res = scrape_google_pure(page, barcode, "Barcode", price_niemyet)
        
        # BƯỚC 2: TÌM THEO TÊN (NẾU BƯỚC 1 THẤT BẠI)
        if not final_res:
            st.write(f"⚠️ Không tìm thấy giá Barcode. Bước 2: Tìm theo Tên ({name})...")
            final_res = scrape_google_pure(page, name, "Tên SP", price_niemyet)

        browser.close()

    if final_res:
        diff = final_res['Giá TT'] - price_niemyet
        final_res['Chênh lệch (%)'] = f"{(diff / price_niemyet * 100):+.1f}%"
        return [final_res]
    return []

# --- UI ---
st.title("🚀 Genshai Google Pro V34.2")

with st.form("google_pure_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Mã Barcode", value="8851130050753")
    name_in = c2.text_input("Tên sản phẩm", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("KIỂM TRA GOOGLE")

if submitted:
    with st.spinner("Đang truy vấn Google bằng cơ chế Stealth..."):
        results = start_process(name_in, barcode_in, price_in)
        if results:
            st.table(pd.DataFrame(results))
        else:
            # Thông báo lỗi từ các ảnh log của bạn
            st.error("Google vẫn đang chặn hoặc không tìm thấy giá phù hợp. Hãy thử rút ngắn tên sản phẩm.")
