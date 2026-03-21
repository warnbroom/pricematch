import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time

st.set_page_config(page_title="Genshai Web Ultimate V37.2", layout="wide")

# --- KẾT NỐI BROWSERLESS ---
SBR_WS_ENDPOINT = st.sidebar.text_input("Browserless Token", value="2UBSKVhZ0O0zDyk4407ed0", type="password")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def scrape_google_precision(page, query, gia_genshai):
    """
    Sử dụng CSS Selectors để bốc chính xác giá từ các khối kết quả Google.
    """
    try:
        url = f"https://www.google.com/search?q=giá+bán+{query.replace(' ', '+')}&hl=vi&gl=vn"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Chờ các khối giá (Shopping/Search) render xong
        time.sleep(5)

        valid_prices = []

        # CHIẾN THUẬT 1: Tìm trong các thẻ hiển thị giá phổ biến của Google (Shopping/Rich Snippets)
        # Các selector này nhắm thẳng vào các con số có đơn vị tiền tệ
        selectors = [
            "span[style*='color']", ".fG8Fp", ".sh-dlr__list-result", 
            "div[data-p]", ".T8Zfbe", "span:has-text('₫')", "span:has-text('đ')"
        ]
        
        for selector in selectors:
            elements = page.query_selector_all(selector)
            for el in elements:
                txt = el.inner_text()
                if "₫" in txt or "đ" in txt:
                    p = clean_price(txt)
                    # Lọc giá rác (ví dụ 150k mốc Lotte) và giá sỉ
                    if gia_genshai * 0.4 < p < gia_genshai * 1.8:
                        valid_prices.append(p)

        # CHIẾN THUẬT 2: Dự phòng bằng cách quét toàn bộ văn bản nếu CSS Selector thất bại
        if not valid_prices:
            full_text = page.evaluate("() => document.body.innerText")
            matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
            for m in matches:
                p = clean_price(m)
                if gia_genshai * 0.4 < p < gia_genshai * 1.8:
                    valid_prices.append(p)
        
        if valid_prices:
            # Lấy giá sát nhất với giá Genshai để đảm bảo cùng quy cách đóng gói
            best_price = min(valid_prices, key=lambda x: abs(x - gia_genshai))
            return {"Nguồn": "Google Precision", "Giá TT": best_price, "Link": url}
            
    except Exception as e:
        st.error(f"Lỗi: {e}")
    return None

# --- UI ---
st.title("🚀 Genshai Web Ultimate V37.2")

with st.form("ultimate_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("CÀN QUÉT DỮ LIỆU")

if submitted:
    if not SBR_WS_ENDPOINT:
        st.error("Hưng cần Token Browserless để chạy trên Web.")
    else:
        with sync_playwright() as p:
            with st.spinner("🔄 Trình duyệt đám mây đang truy tìm giá..."):
                browser = p.chromium.connect_over_cdp(f"wss://chrome.browserless.io?token={SBR_WS_ENDPOINT}")
                page = browser.new_context().new_page()

                # Ưu tiên Barcode -> Tên
                st.write(f"🔍 Bước 1: Tìm theo Barcode...")
                res = scrape_google_precision(page, barcode_in, price_in)
                
                if not res:
                    st.write(f"⚠️ Bước 2: Tìm theo Tên sản phẩm...")
                    res = scrape_google_precision(page, name_in, price_in)

                if res:
                    diff = res['Giá TT'] - price_in
                    res['Chênh lệch (%)'] = f"{(diff / price_in * 100):+.1f}%"
                    st.success("✅ Đã tìm thấy kết quả khớp!")
                    st.table(pd.DataFrame([res]))
                else:
                    st.error("❌ Google không hiển thị giá phù hợp. Hãy thử rút ngắn tên sản phẩm.")
                
                browser.close()
