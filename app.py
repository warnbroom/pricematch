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

st.set_page_config(page_title="Genshai Google Checker V31.0", layout="wide")

def clean_price(text):
    if not text: return 0
    # Xử lý các định dạng như 60.000đ, 60,000...
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM GOOGLE (QUET_GIA.PY) ---

def scrape_google_logic_chuan(page, search_key, mode):
    """Bám sát logic div.g và bóc tách dữ liệu từ file quet_gia.py"""
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2) # Chờ kết quả hiển thị ổn định
        
        # Selector div.g là cốt lõi của quet_gia.py
        items = page.query_selector_all("div.g")
        
        for item in items:
            text = item.inner_text()
            # Kiểm tra sự tồn tại của ký hiệu tiền tệ
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                
                # BỘ LỌC GIÁ LẺ (Tránh lấy nhầm giá combo/thùng)
                # Dựa trên dữ liệu Hưng cung cấp, giá lẻ thường < 120.000
                if 10000 < price < 120000:
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}
    except Exception as e:
        return None
    return None

# --- 3. ĐIỀU PHỐI QUY TRÌNH ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    with sync_playwright() as p:
        # Sử dụng các tham số giúp tránh bị Google chặn (Stealth)
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        # BƯỚC 1: Tìm Barcode trên Google
        st.write(f"🔍 Bước 1: Đang tìm Barcode ({barcode}) trên Google...")
        final_res = scrape_google_logic_chuan(page, barcode, "Barcode")
        
        # BƯỚC 2: Nếu Bước 1 thất bại, tìm theo Tên trên Google
        if not final_res:
            st.write(f"⚠️ Không thấy Barcode. Bước 2: Tìm theo Tên trên Google...")
            # Giữ nguyên tên đầy đủ theo yêu cầu của Hưng
            final_res = scrape_google_logic_chuan(page, name, "Tên SP")

        browser.close()

    if final_res and gia_niem_yet > 0:
        diff = final_res['Giá TT'] - gia_niem_yet
        final_res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [final_res] if final_res else []

# --- GIAO DIỆN ---
st.title("🚀 Genshai Google Checker V31.0")
st.info("Hệ thống tập trung tối ưu logic tìm kiếm Google Search.")

with st.form("google_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("KIỂM TRA GOOGLE")

if submitted:
    with st.spinner("Đang thực hiện quy trình tìm kiếm 2 giai đoạn..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.success("Đã tìm thấy giá!")
            st.table(pd.DataFrame(data))
        else:
            # Thông báo khi Google chặn hoặc không tìm thấy khối div.g phù hợp
            st.error("Không tìm thấy kết quả phù hợp trong khối div.g trên Google.")
