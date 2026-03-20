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

st.set_page_config(page_title="Genshai Price Checker V29.3", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte_phuc_hoi(page, barcode):
    """Khôi phục hoàn toàn logic cũ của Hưng và chỉ chặn số 150.000"""
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(2)
        
        # Logic bóc tách theo dòng nguyên bản
        content = page.evaluate("() => document.body.innerText")
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        for line in lines:
            if "₫" in line or "đ" in line:
                price = clean_price(line)
                # CHỈ LẤY GIÁ NẾU KHÁC 150.000 (Mốc lọc của Lotte)
                if 1000 < price < 1000000 and price != 150000:
                    return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_logic_goc(page, search_key, mode):
    """Bám sát file quet_gia.py: Dùng div.g và in log để kiểm tra"""
    logs = []
    try:
        # Giữ nguyên tên không cắt bỏ theo yêu cầu của Hưng
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Kiểm tra div.g truyền thống
        items = page.query_selector_all("div.g")
        logs.append(f"🔍 Google: Tìm thấy {len(items)} khối div.g")
        
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 200000: # Giới hạn giá lẻ gia vị
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}, logs
        
        # Nếu div.g = 0, thử quét nhanh văn bản (Dự phòng Captcha)
        if not items:
            full_text = page.evaluate("() => document.body.innerText")
            matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
            if matches:
                p = clean_price(matches[0])
                if 1000 < p < 200000:
                    return {"Nguồn": f"Google ({mode} - Text)", "Giá TT": p, "Link": url}, logs

    except Exception as e:
        logs.append(f"❌ Lỗi Google: {str(e)}")
    return None, logs

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    all_logs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Bước 1: Lotte (Logic đã phục hồi)
        st.write("🔍 Đang chạy logic Lotte gốc...")
        final_res = scrape_lotte_phuc_hoi(page, barcode)
        
        # Bước 2: Google Tên SP (Nếu Bước 1 không có)
        if not final_res:
            st.write(f"⚠️ Bước 1 không ra. Tìm Google: {name}...")
            res_google, logs = scrape_google_logic_goc(page, name, "Tên SP")
            all_logs.extend(logs)
            if res_google: final_res = res_google

        browser.close()

    if final_res and gia_niem_yet > 0:
        diff = final_res['Giá TT'] - gia_niem_yet
        final_res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [final_res] if final_res else [], all_logs

# --- UI ---
st.title("🚀 Genshai Checker V29.3 - Phục Hồi Logic")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("KIỂM TRA GIÁ")

if submitted:
    with st.spinner("Đang truy xuất theo đúng logic gốc..."):
        data, logs = start_process(name_in, barcode_in, price_in)
        
        if logs:
            with st.expander("🛠 LOG HỆ THỐNG", expanded=True):
                for log in logs: st.write(log)

        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả. Hưng hãy kiểm tra lại Log để xem Google có trả về khối div.g nào không.")
