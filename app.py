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

st.set_page_config(page_title="Genshai Google Pro V31.1", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC GOOGLE NÂNG CAO ---

def scrape_google_stealth(page, search_key, mode):
    """
    Sử dụng Selector đa điểm và quét văn bản sâu để bắt được giá Co.op/Lotte 
    ngay cả khi div.g bị ẩn.
    """
    try:
        # Sử dụng URL tìm kiếm có tham số hl=vi để ưu tiên kết quả Việt Nam
        url = f"https://www.google.com/search?q=giá+bán+{search_key.replace(' ', '+')}&hl=vi"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(3) # Chờ Google render Rich Snippets (giá hiển thị trực tiếp)
        
        # Thử nhiều loại Selector khác nhau vì Google thường đổi class trên Cloud
        selectors = ["div.g", ".tF2Cxc", ".v7W49e", "div[data-hveid]"]
        
        for selector in selectors:
            items = page.query_selector_all(selector)
            if items:
                for item in items:
                    text = item.inner_text()
                    if "₫" in text or "đ" in text:
                        price = clean_price(text)
                        # Bộ lọc giá lẻ gia vị/đồ dùng (10k - 200k)
                        if 10000 < price < 200000:
                            link_elem = item.query_selector("a")
                            link = link_elem.get_attribute("href") if link_elem else url
                            return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}

        # PHƯƠNG ÁN CUỐI: Quét văn bản toàn trang nếu các Selector đều thất bại
        full_text = page.evaluate("() => document.body.innerText")
        # Regex tìm các cụm: số + khoảng trắng (tùy chọn) + đ/₫
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        if price_matches:
            for match in price_matches:
                p = clean_price(match)
                if 10000 < p < 200000:
                    return {"Nguồn": f"Google ({mode} - Text Scan)", "Giá TT": p, "Link": url}
                    
    except Exception: return None
    return None

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    with sync_playwright() as p:
        # Cấu hình Stealth mạnh mẽ để tránh bị Google chặn 0 khối
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox", 
            "--disable-blink-features=AutomationControlled"
        ])
        # Giả lập thiết bị thật với độ phân giải cao
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # BƯỚC 1: Tìm theo Barcode (Ưu tiên tuyệt đối)
        st.write(f"🔍 Đang tìm Barcode {barcode}...")
        final_res = scrape_google_stealth(page, barcode, "Barcode")
        
        # BƯỚC 2: Tìm theo Tên SP (Nếu bước 1 không ra)
        if not final_res:
            st.write(f"⚠️ Đang tìm theo Tên: {name}...")
            final_res = scrape_google_stealth(page, name, "Tên SP")

        browser.close()
