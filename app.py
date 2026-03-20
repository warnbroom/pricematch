import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import subprocess
import time

# --- 1. SETUP ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte(page, barcode):
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(2)
        content = page.evaluate("() => document.body.innerText")
        if "Không tìm thấy sản phẩm" in content: return None
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for line in lines:
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                if 1000 < price < 150000:
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_real(page, search_key, mode="Tên SP"):
    """Giả lập hành động gõ phím để Google không chặn"""
    try:
        # Bước A: Vào Google.com trước
        page.goto("https://www.google.com", wait_until="networkidle")
        
        # Bước B: Tìm ô tìm kiếm và gõ tên (delay giữa các phím)
        search_box = page.locator("textarea[name='q'], input[name='q']").first
        search_box.fill(f"giá {search_key}")
        page.keyboard.press("Enter")
        
        # Bước C: Đợi kết quả load
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Bước D: Quét toàn bộ nội dung tìm kiếm
        content = page.evaluate("() => document.body.innerText")
        
        # Tìm giá kèm ký hiệu ₫ hoặc đ
        matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', content)
        if matches:
            for m in matches:
                price = clean_price(m)
                # Giới hạn giá lẻ gia vị
                if 1000 < price < 150000:
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": page.url}
    except Exception as e:
        print(f"Google Error: {e}")
        return None
    return None

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    res = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        # 1. Lotte Barcode
        st.write("🔍 Đang quét Lotte Mart...")
        res = scrape_lotte(page, barcode)
        
        # 2. Google (Dùng cơ chế gõ phím thật)
        if not res:
            st.write(f"⚠️ Đang tìm kiếm Google cho: {name}...")
            res = scrape_google_real(page, name, mode="Tên SP")
            
        # 3. Google Barcode (Dự phòng cuối)
        if not res:
            st.write(f"⚠️ Quét barcode trên Google...")
            res = scrape_google_real(page, barcode, mode="Barcode")

        browser.close()

    if res and gia_niem_yet > 0:
        diff = res['Giá TT'] - gia_niem_yet
        res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [res] if res else []

# --- UI ---
st.title("🚀 Genshai Price Checker (V28.5 - Real Human Search)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("BẮT ĐẦU KIỂM TRA")

if submitted:
    with st.spinner("Đang giả lập người dùng tìm kiếm trên Google..."):
        data = start_process(name_in, barcode_in, price_in)
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Dù đã giả lập người dùng nhưng vẫn không thấy giá. Hưng hãy thử đổi sang mạng khác hoặc kiểm tra tên SP có bị sai chính tả không nhé.")
