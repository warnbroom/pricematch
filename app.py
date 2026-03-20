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

st.set_page_config(page_title="Genshai Price Checker V29.0", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte_goc(page, barcode):
    """Logic Lotte gốc của Hưng"""
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=20000)
        time.sleep(2)
        content = page.evaluate("() => document.body.innerText")
        if "₫" in content or "đ" in content:
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            for line in lines:
                if "₫" in line or "đ" in line:
                    price = clean_price(line)
                    if 1000 < price < 150000: # Lọc giá rác
                        return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_with_trace(page, search_key, mode):
    """Bám sát div.g nhưng thêm cơ chế bóc tách văn bản dự phòng"""
    debug_logs = []
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1) # Chờ Google ổn định
        
        # Bước A: Thử dùng div.g (Logic quet_gia.py)
        items = page.query_selector_all("div.g")
        debug_logs.append(f"🔍 Tìm thấy {len(items)} khối div.g")
        
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 150000:
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": url}, debug_logs
        
        # Bước B: Nếu div.g thất bại, dùng logic quét văn bản (Dự phòng cho Captcha/Layout mới)
        debug_logs.append("⚠️ Không thấy giá trong div.g. Đang quét văn bản toàn trang...")
        full_text = page.evaluate("() => document.body.innerText")
        
        # Tìm các dòng chứa số và ký hiệu tiền tệ (giống logic Lotte)
        matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        if matches:
            for m in matches:
                price = clean_price(m)
                if 1000 < price < 150000:
                    debug_logs.append(f"✅ Tìm thấy giá trong văn bản: {price}₫")
                    return {"Nguồn": f"Google ({mode} - Văn bản)", "Giá TT": price, "Link": url}, debug_logs
                    
    except Exception as e:
        debug_logs.append(f"❌ Lỗi: {str(e)}")
        
    return None, debug_logs

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    all_debug = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # 1. Lotte Barcode
        res_lotte = scrape_lotte_goc(page, barcode)
        if res_lotte: final_res = res_lotte
        
        # 2. Google Tên SP (Hưng muốn bám sát tìm theo tên)
        if not final_res:
            res_google, logs = scrape_google_with_trace(page, name, "Tên SP")
            all_debug.extend(logs)
            if res_google: final_res = res_google

        browser.close()

    if final_res and gia_niem_yet > 0:
        diff = final_res['Giá TT'] - gia_niem_yet
        final_res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [final_res] if final_res else [], all_debug

# --- UI ---
st.title("🚀 Hệ Thống Kiểm Giá Toàn Diện (V29.0)")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("BẮT ĐẦU KIỂM TRA")

if submitted:
    with st.spinner("Đang truy xuất dữ liệu..."):
        data, logs = start_process(name_in, barcode_in, price_in)
        
        with st.expander("🛠 NHẬT KÝ XỬ LÝ DỮ LIỆU", expanded=True):
            for log in logs:
                st.write(log)
        
        if data:
            st.success("Đã tìm thấy giá!")
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả. Google có thể đang chặn truy cập tự động.")
