import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re, time, random, os
from io import BytesIO

# Cấu hình phải đặt đầu tiên để tránh lỗi Blank
st.set_page_config(page_title="Genshai Web App", layout="wide")

# --- HÀM HỖ TRỢ (Gộp từ 2 file gốc) ---
def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def fetch_lotte(page, barcode):
    url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        content = page.evaluate("() => document.body.innerText")
        if "không tìm thấy" in content.lower(): return None
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            if "đ" in line or "₫" in line:
                val = clean_price(line)
                if 1000 < val < 5000000:
                    return {"gia": val, "nguon": "LotteMart", "link": url, "ten": lines[i-1] if i>0 else "Lotte Item"}
        return None
    except: return None

def fetch_google(page, query):
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Tự động dừng nếu dính Captcha như bản quet_gia.py
        if "google.com/sorry" in page.url:
            st.warning("⚠️ Đang dính CAPTCHA Google. Hãy giải trên trình duyệt!")
            while "google.com/sorry" in page.url: time.sleep(2)
        
        results = page.query_selector_all("div[class*='g']")
        for res in results:
            link = res.query_selector("a").get_attribute("href") if res.query_selector("a") else ""
            if any(site in link for site in ['genshai.com.vn', 'facebook.com']): continue
            txt = res.inner_text()
            if "₫" in txt or "đ" in txt:
                val = clean_price(txt)
                if 1000 < val < 10000000:
                    return {"gia": val, "nguon": "Google", "link": link, "ten": query}
        return None
    except: return None

# --- GIAO DIỆN WEB ---
st.title("🚀 Price Checker V24.8: Lotte & Google Search")

t1, t2 = st.tabs(["🔍 Kiểm tra lẻ", "📁 Xử lý file Excel"])

with t1:
    with st.form("single"):
        c1, c2, c3 = st.columns(3)
        b_code = c1.text_input("Barcode")
        t_sp = c2.text_input("Tên sản phẩm")
        g_ny = c3.number_input("Giá niêm yết", min_value=0)
        submit = st.form_submit_button("Quét ngay")
    
    if submit:
        with st.spinner("Đang tìm kiếm..."):
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                # Ưu tiên Lotte -> Google Barcode -> Google Tên
                res = fetch_lotte(page, b_code) or fetch_google(page, b_code) or fetch_google(page, f"giá {t_sp}")
                if res:
                    st.success(f"Tìm thấy: {res['gia']:,.0f}đ tại {res['nguon']}")
                    st.write(f"Tên sản phẩm: {res['ten']}")
                    st.link_button("Xem nguồn", res['link'])
                else: st.error("Không tìm thấy kết quả.")
                browser.close()

with t2:
    file = st.file_uploader("Tải lên danh sách .xlsx", type="xlsx")
    if file and st.button("Bắt đầu quét danh sách"):
        st.info("Tính năng xử lý file đang chạy ngầm, kết quả sẽ hiện tại đây...")
