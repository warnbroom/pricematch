import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import subprocess
import time
import os
from io import BytesIO

# --- 1. SETUP HỆ THỐNG ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Google Pro V34.3", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TÌM KIẾM GOOGLE VÀ CHỤP MÀN HÌNH ---

def scrape_google_with_screenshot(page, search_key, mode, gia_genshai):
    """
    Tìm kiếm Google (Stealth) và chụp lại màn hình để Hưng kiểm tra.
    """
    try:
        # Sử dụng URL tìm kiếm có các tham số hl=vi và tbm=shop (nếu cần) để ép ra giá
        url = f"https://www.google.com/search?q=giá+bán+{search_key.replace(' ', '+')}&hl=vi&gl=vn"
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Giả lập hành vi người dùng bằng cách di chuyển chuột
        page.mouse.move(100, 100) 
        time.sleep(3) # Chờ Google render Rich Snippets

        # **CHỤP MÀN HÌNH CHÍNH XÁC NHẤT**
        screenshot_bytes = page.screenshot(full_page=False) # Chỉ chụp phần hiển thị ban đầu

        # --- BẮT ĐẦU BÓC TÁCH DỮ LIỆU ---

        # Ưu tiên 1: Quét các khối div.g truyền thống
        items = page.query_selector_all("div.g")
        found_price = None
        for item in items:
            text = item.inner_text()
            if "₫" in text or "đ" in text:
                price = clean_price(text)
                # Filter thông minh dựa trên giá niêm yết (Genshai) để tránh giá thùng/giá rác
                if gia_genshai * 0.4 < price < gia_genshai * 2.0:
                    found_price = price
                    break # Lấy kết quả div.g đầu tiên phù hợp

        # Ưu tiên 2: Quét văn bản toàn trang (Text Scan) - Phương án dự phòng Captcha
        if not found_price:
            full_text = page.evaluate("() => document.body.innerText")
            # Regex tìm các cụm: số + khoảng trắng (tùy chọn) + đ/₫
            matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
            for m in matches:
                p = clean_price(m)
                if gia_genshai * 0.4 < p < gia_genshai * 2.0:
                    found_price = p
                    break # Lấy giá text scan đầu tiên phù hợp

        # Trả về cả dữ liệu và ảnh chụp
        if found_price:
            return {"data": {"Nguồn": f"Google ({mode})", "Giá TT": found_price, "Link": url}, "screenshot": screenshot_bytes}
        else:
            return {"data": None, "screenshot": screenshot_bytes}
            
    except Exception: return {"data": None, "screenshot": None}
    return {"data": None, "screenshot": None}

# --- 3. ĐIỀU PHỐI THEO TRÌNH TỰ CHUẨN (BARCODE > TÊN) ---
def start_process(name, barcode, price_niemyet):
    final_res = None
    final_screenshot = None
    
    with sync_playwright() as p:
        # Cấu hình Stealth tối đa
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox", 
            "--disable-blink-features=AutomationControlled"
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800} # Đặt độ phân giải lớn
        )
        page = context.new_page()

        # BƯỚC 1: TÌM THEO BARCODE
        st.write(f"🔍 Bước 1: Tìm theo Barcode ({barcode})...")
        res1 = scrape_google_with_screenshot(page, barcode, "Barcode", price_niemyet)
        final_res = res1['data']
        final_screenshot = res1['screenshot']
        
        # BƯỚC 2: TÌM THEO TÊN (NẾU BƯỚC 1 THẤT BẠI)
        if not final_res:
            st.write(f"⚠️ Không tìm thấy giá Barcode. Bước 2: Tìm theo Tên ({name})...")
            # Chụp lại màn hình mới khi tìm theo tên
            res2 = scrape_google_with_screenshot(page, name, "Tên SP", price_niemyet)
            final_res = res2['data']
            # Cập nhật ảnh chụp màn hình khi tìm theo tên
            final_screenshot = res2['screenshot'] 

        browser.close()

    if final_res:
        diff = final_res['Giá TT'] - price_niemyet
        final_res['Chênh lệch (%)'] = f"{(diff / price_niemyet * 100):+.1f}%"
        return [final_res], final_screenshot
    return [], final_screenshot

# --- GIAO DIỆN STREAMLIT ---
st.title("🚀 Genshai Google Pro V34.3")

with st.form("google_screenshot_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Mã Barcode", value="8851130050753")
    name_in = c2.text_input("Tên sản phẩm", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá niêm yết (Genshai)", value=81400)
    submitted = st.form_submit_button("BẮT ĐẦU KIỂM TRA GOOGLE")

if submitted:
    with st.spinner("Đang truy vấn Google bằng cơ chế Stealth và chụp lại màn hình..."):
        results, screenshot = start_process(name_in, barcode_in, price_in)
        
        # Luôn hiển thị ảnh chụp màn hình Google
        if screenshot:
            with st.expander("🛠 XEM ẢNH CHỤP MÀN HÌNH GOOGLE", expanded=True):
                # Hiển thị ảnh dưới dạng byte
                st.image(screenshot, caption=f"Hình ảnh thực tế Google đang hiển thị lúc {time.strftime('%H:%M:%S')}", use_column_width=True)
        else:
            st.warning("Playwright chưa chụp được màn hình Google. Hãy thử lại.")

        # Hiển thị kết quả dữ liệu (nếu có)
        if results:
            st.success("Đã tìm thấy giá (Ưu tiên Lotte/Co.op Online)!")
            st.table(pd.DataFrame(results))
        else:
            # Thông báo lỗi từ các ảnh log của bạn
            st.error("Google vẫn đang chặn hoặc không tìm thấy giá phù hợp. Hãy kiểm tra ảnh chụp màn hình phía trên.")
