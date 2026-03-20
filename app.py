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

st.set_page_config(page_title="Genshai Google V34.0", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM GOOGLE ---

def scrape_google_logic(page, search_key, mode, gia_genshai):
    """
    Logic tìm kiếm linh hoạt: Thử Selector trước, nếu thất bại thì quét toàn trang.
    """
    try:
        # Sử dụng tham số hl=vi để ưu tiên kết quả Việt Nam
        url = f"https://www.google.com/search?q=giá+bán+{search_key.replace(' ', '+')}&hl=vi"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(3) 

        # Bước A: Tìm qua các Selector phổ biến (div.g, tF2Cxc...)
        selectors = ["div.g", ".tF2Cxc", ".v7W49e", "div[data-hveid]"]
        for selector in selectors:
            items = page.query_selector_all(selector)
            for item in items:
                text = item.inner_text()
                if "₫" in text or "đ" in text:
                    price = clean_price(text)
                    # Filter thông minh: Chấp nhận giá trong khoảng 30% - 250% giá Genshai
                    if gia_genshai * 0.3 < price < gia_genshai * 2.5:
                        return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": url}

        # Bước B: PHƯƠNG ÁN DỰ PHÒNG (Text Scan) - Nếu Google ẩn khối div.g
        full_text = page.evaluate("() => document.body.innerText")
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        for match in price_matches:
            p = clean_price(match)
            if gia_genshai * 0.3 < p < gia_genshai * 2.5:
                return {"Nguồn": f"Google ({mode} - Scan)", "Giá TT": p, "Link": url}
                
    except Exception: return None
    return None

# --- 3. ĐIỀU PHỐI THEO THỨ TỰ ---
def start_process(name, barcode, price_niemyet):
    final_res = None
    with sync_playwright() as p:
        # Cấu hình Stealth mạnh mẽ để vượt rào cản Google
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        # TRÌNH TỰ 1: TÌM THEO BARCODE
        st.write(f"🔍 Bước 1: Tìm theo Barcode ({barcode})...")
        final_res = scrape_google_logic(page, barcode, "Barcode", price_niemyet)
        
        # TRÌNH TỰ 2: NẾU BƯỚC 1 TRỐNG, TÌM THEO TÊN
        if not final_res:
            st.write(f"⚠️ Không thấy giá theo Barcode. Bước 2: Tìm theo Tên ({name})...")
            final_res = scrape_google_logic(page, name, "Tên SP", price_niemyet)

        browser.close()

    if final_res:
        diff = final_res['Giá TT'] - price_niemyet
        final_res['Chênh lệch (%)'] = f"{(diff / price_niemyet * 100):+.1f}%"
        return [final_res]
    return []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Google V34.0 - Trình tự chuẩn")

with st.form("main_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Mã Barcode", value="8851130050753")
    name_in = c2.text_input("Tên sản phẩm", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("BẮT ĐẦU KIỂM TRA")

if submitted:
    with st.spinner("Đang thực hiện quy trình tìm kiếm 2 giai đoạn trên Google..."):
        results = start_process(name_in, barcode_in, price_in)
        if results:
            st.success("Đã tìm thấy kết quả!")
            st.table(pd.DataFrame(results))
        else:
            st.error("Google vẫn đang chặn hoặc không có kết quả phù hợp. Hưng hãy thử lại sau ít phút.")
