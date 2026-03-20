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

st.set_page_config(page_title="Genshai Checker V29.2", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM ---

def scrape_lotte_chuan(page, barcode):
    """Logic Lotte cải tiến: Loại bỏ mốc giá lọc 150k"""
    try:
        url = f"https://www.lottemart.vn/vi-nsg/category?q={barcode}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        time.sleep(3) # Đợi load sản phẩm
        
        content = page.evaluate("() => document.body.innerText")
        if "₫" in content or "đ" in content:
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            for line in lines:
                if "₫" in line or "đ" in line:
                    price = clean_price(line)
                    # QUAN TRỌNG: Loại bỏ mốc giá 150.000 rác để lấy giá thật
                    if 1000 < price < 1000000 and price != 150000:
                        return {"Nguồn": "Lotte Mart", "Giá TT": price, "Link": url}
    except: return None
    return None

def scrape_google_stealth(page, search_key, mode):
    """Sử dụng cơ chế giả lập sâu để tránh bị chặn 0 khối"""
    logs = []
    try:
        # Thay đổi URL tìm kiếm để trông tự nhiên hơn
        url = f"https://www.google.com/search?q=giá+bán+{search_key.replace(' ', '+')}&hl=vi"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        
        # Thử lấy tất cả các liên kết có chứa giá (thay vì dùng div.g bị chặn)
        content = page.evaluate("() => document.body.innerText")
        
        # Tìm kiếm giá lẻ trong văn bản (Ưu tiên các mốc giá hợp lý)
        matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', content)
        if matches:
            for m in matches:
                p = clean_price(m)
                # Lọc giá: Tránh lấy nhầm giá thùng nếu đang tìm chai lẻ
                if 1000 < p < 150000:
                    logs.append(f"✅ Đã bắt được giá lẻ từ văn bản: {p}₫")
                    return {"Nguồn": f"Google ({mode})", "Giá TT": p, "Link": url}, logs
        else:
            logs.append("⚠️ Vẫn không thấy ký hiệu giá trong văn bản trang.")
            
    except Exception as e:
        logs.append(f"❌ Lỗi: {str(e)}")
    return None, logs

# --- 3. ĐIỀU PHỐI ---
def start_process(name, barcode, gia_niem_yet):
    final_res = None
    all_logs = []
    
    with sync_playwright() as p:
        # Sử dụng các tham số vượt rào cản (Stealth)
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox", 
            "--disable-blink-features=AutomationControlled",
            "--use-fake-ui-for-media-stream"
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # Bước 1: Lotte (Đã fix mốc 150k)
        st.write("🔍 Đang kiểm tra Lotte Mart...")
        res_lotte = scrape_lotte_chuan(page, barcode)
        if res_lotte: final_res = res_lotte
        
        # Bước 2: Google (Dùng chế độ Stealth)
        if not final_res:
            st.write(f"⚠️ Đang tìm trên Google cho: {name}...")
            res_google, logs = scrape_google_stealth(page, name, "Tên SP")
            all_logs.extend(logs)
            if res_google: final_res = res_google

        browser.close()

    if final_res and gia_niem_yet > 0:
        diff = final_res['Giá TT'] - gia_niem_yet
        final_res['Chênh lệch (%)'] = f"{(diff / gia_niem_yet * 100):+.1f}%"
    
    return [final_res] if final_res else [], all_logs

# --- GIAO DIỆN ---
st.title("🚀 Genshai Checker V29.2 - Fix Lotte & Google")

with st.form("main_form"):
    c1, c2, c3 = st.columns(3)
    barcode_in = c1.text_input("Mã Barcode", value="0078895153767")
    name_in = c2.text_input("Tên sản phẩm", value="Hắc xì dầu thượng hạng LKK 500ml*12")
    price_in = c3.number_input("Giá niêm yết", value=66800)
    submitted = st.form_submit_button("BẮT ĐẦU SO SÁNH")

if submitted:
    with st.spinner("Đang xử lý dữ liệu chuẩn..."):
        data, logs = start_process(name_in, barcode_in, price_in)
        
        if logs:
            with st.expander("🛠 NHẬT KÝ HỆ THỐNG", expanded=True):
                for log in logs: st.write(log)

        if data:
            st.table(pd.DataFrame(data))
        else:
            st.error("Không tìm thấy kết quả phù hợp. Google có thể đang yêu cầu xác minh danh tính.")
