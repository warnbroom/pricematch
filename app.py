import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time

st.set_page_config(page_title="Genshai Web Ultimate V37.2", layout="wide")

# --- KẾT NỐI BROWSERLESS ---
# Tôi vẫn giữ Token của Hưng để bạn test nhanh
SBR_WS_ENDPOINT = st.sidebar.text_input("Browserless Token", value="2UBSKVhZ0O0zDyk4407ed0", type="password")

def clean_price(text):
    if not text: return 0
    # Xử lý mọi ký tự lạ, chỉ giữ lại số
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def scrape_google_ultimate(page, query, gia_genshai):
    """
    Chiến thuật quét 'Lưới điện': Không bỏ sót bất kỳ con số nào trên trang.
    """
    try:
        url = f"https://www.google.com/search?q=giá+bán+{query.replace(' ', '+')}&hl=vi&gl=vn"
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Cuộn nhẹ trang để kích hoạt các phần nội dung ẩn (lazy load)
        page.mouse.wheel(0, 500)
        time.sleep(3)

        # LẤY DỮ LIỆU TỪ 3 NGUỒN KHÁC NHAU ĐỂ ĐỐI CHIẾU
        # 1. Toàn bộ text trang
        full_text = page.evaluate("() => document.body.innerText")
        # 2. Toàn bộ các đường link (có thể chứa giá trong tiêu đề)
        all_links = page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.innerText).join(' ') ")
        # 3. Các thẻ meta (mô tả ẩn)
        meta_desc = page.evaluate("() => Array.from(document.querySelectorAll('span')).map(s => s.innerText).join(' ') ")

        combined_content = full_text + " " + all_links + " " + meta_desc
        
        # Regex tìm giá thông minh: 81.400, 81.400đ, 81,400...
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', combined_content)
        
        valid_prices = []
        for m in price_matches:
            p = clean_price(m)
            # Giữ bộ lọc an toàn để tránh giá thùng 300k
            if gia_genshai * 0.4 < p < gia_genshai * 2.0:
                valid_prices.append(p)
        
        if valid_prices:
            # Lấy giá phổ biến nhất hoặc giá gần với Genshai nhất
            best_price = min(valid_prices, key=lambda x: abs(x - gia_genshai))
            return {"Nguồn": "Google Ultimate", "Giá TT": best_price, "Link": url}
            
    except Exception as e:
        st.error(f"Lỗi: {e}")
    return None

# --- UI ---
st.title("🚀 Genshai Web Ultimate V37.2")
st.markdown("---")

with st.form("ultimate_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("BẮT ĐẦU CÀN QUÉT")

if submitted:
    with sync_playwright() as p:
        with st.spinner("🔄 Đang dùng trình duyệt đám mây càn quét Google..."):
            browser = p.chromium.connect_over_cdp(f"wss://chrome.browserless.io?token={SBR_WS_ENDPOINT}")
            page = browser.new_context().new_page()

            # Thử Barcode trước
            st.write(f"🔍 Đang tìm theo Barcode...")
            res = scrape_google_ultimate(page, barcode_in, price_in)
            
            if not res:
                st.write(f"🔍 Barcode không ra, đang tìm theo Tên...")
                res = scrape_google_ultimate(page, name_in, price_in)

            if res:
                diff = res['Giá TT'] - price_in
                res['Chênh lệch (%)'] = f"{(diff / price_in * 100):+.1f}%"
                st.success("✅ Đã tìm thấy giá thị trường!")
                st.table(pd.DataFrame([res]))
            else:
                st.error("❌ Vẫn không tìm thấy giá. Hãy thử nhập tên sản phẩm ngắn gọn hơn (Ví dụ: 'Dao bào vỏ 217').")
            
            browser.close()
