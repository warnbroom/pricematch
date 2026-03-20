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

st.set_page_config(page_title="Genshai Price Checker V29.1", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte_goc(page, barcode):
    """Bám sát logic quet_gia_lotte.py"""
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
                    # Loại bỏ mốc 150k lọc giá của Lotte
                    if 1000 < price < 150000:
                        return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_multi_selector(page, search_key, mode):
    """Thay thế div.g bằng các selector đa điểm để bắt được Co.op Online"""
    logs = []
    try:
        url = f"https://www.google.com/search?q=giá+{search_key.replace(' ', '+')}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        
        # Danh sách các selector thay thế cho div.g (phổ biến hiện nay)
        # .v7W49e, .tF2Cxc, [data-hveid] là các thẻ chứa kết quả tìm kiếm mới của Google
        selectors = ["div.g", ".v7W49e", ".tF2Cxc", "div[data-hveid]", ".X7Ur7b"]
        
        found_items = []
        for selector in selectors:
            items = page.query_selector_all(selector)
            if items:
                logs.append(f"🔍 Selector '{selector}' tìm thấy {len(items)} khối.")
                found_items.extend(items)
        
        if not found_items:
            logs.append("⚠️ Không tìm thấy khối kết quả nào qua Selector. Thử quét toàn trang...")
            full_text = page.evaluate("() => document.body.innerText")
            # Regex bắt giá lẻ (Ví dụ: 60.000₫)
            matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
            for m in matches:
                p = clean_price(m)
                if 1000 < p < 150000:
                    return {"Nguồn": f"Google ({mode} - Toàn trang)", "Giá TT": p, "Link": url}, logs

        # Duyệt qua các khối tìm thấy
        for item in found_items[:10]:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                if 1000 < price < 150000:
                    link_elem = item.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else url
                    return {"Nguồn": f"Google ({mode})", "Giá TT": price, "Link": link}, logs
                    
    except Exception as e:
        logs.append(f"❌ Lỗi Google: {str(e)}")
    return None, logs

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    all_logs = []
    
    with sync_playwright() as p:
        # Tắt chế độ webdriver để Google ít chặn hơn
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        # Bước 1: Lotte
        res_lotte = scrape_lotte_goc(page, barcode)
        if res_lotte: final_res = res_lotte
        
        # Bước 2: Google theo Tên (Hưng ưu tiên bước này)
        if not final_res:
            res_google, logs = scrape_google_multi_selector(page, name, "Tên SP")
            all_logs.extend(logs)
            if res_google: final_res = res_google

        browser.close()

    if final_res and gia_niem_yet > 0:
        diff = final_res['Giá TT'] - gia_niem_yet
        final_res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [final_res] if final_res else [], all_logs

# --- UI ---
st.title("🚀 Genshai Checker V29.1 - Multi-Selector")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=66800)
    submitted = st.form_submit_button("KIỂM TRA GIÁ")

if submitted:
    with st.spinner("Đang thực hiện quét đa điểm..."):
        data, logs = start_process(name_in, barcode_in, price_in)
        
        with st.expander("🛠 NHẬT KÝ QUÉT GOOGLE", expanded=True):
            if logs:
                for log in logs: st.write(log)
            else: st.write("Đã tìm thấy giá ở bước Lotte.")

        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Vẫn không tìm thấy. Google đang ẩn kết quả rất kỹ.")
