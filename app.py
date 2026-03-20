import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time

st.set_page_config(page_title="Genshai Web Pro V37.1", layout="wide")

# --- KẾT NỐI BROWSERLESS ---
SBR_WS_ENDPOINT = st.sidebar.text_input("Browserless Token", value="2UBSKVhZ0O0zDyk4407ed0", type="password")

def clean_price(text):
    if not text: return 0
    # Xử lý các dạng giá như 81.400, 81,400 hoặc 81400đ
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def scrape_google_advanced(page, query, gia_genshai):
    """
    Sử dụng kỹ thuật quét đa tầng để đảm bảo không sót giá trên Google.
    """
    try:
        # Ép Google trả về kết quả tiếng Việt và địa điểm Việt Nam
        url = f"https://www.google.com/search?q=giá+bán+{query.replace(' ', '+')}&hl=vi&gl=vn"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4) # Chờ trình duyệt đám mây render xong nội dung động

        # BƯỚC 1: Quét toàn bộ Text của trang (Cách hiệu quả nhất hiện nay)
        full_text = page.evaluate("() => document.body.innerText")
        
        # Regex tìm giá: Chấp nhận các số có dấu chấm/phẩy ngăn cách và đơn vị đ/₫
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', full_text)
        
        valid_results = []
        for m in price_matches:
            p = clean_price(m)
            # Lọc giá: Tránh nhặt nhầm giá thùng (300k) hoặc giá quá rẻ (10k)
            if gia_genshai * 0.4 < p < gia_genshai * 1.8:
                valid_results.append(p)
        
        if valid_results:
            # Ưu tiên lấy giá gần với giá Genshai nhất (để đúng đơn vị chai/cái)
            best_price = min(valid_results, key=lambda x: abs(x - gia_genshai))
            return {"Nguồn": "Google Search", "Giá TT": best_price, "Link": url}
            
    except Exception as e:
        st.error(f"Lỗi truy cập: {e}")
    return None

# --- UI ---
st.title("🚀 Genshai Web App V37.1")

with st.form("web_pro_v37_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("KIỂM TRA TRÊN WEB")

if submitted:
    if not SBR_WS_ENDPOINT:
        st.error("Hưng vui lòng kiểm tra lại Token Browserless ở Sidebar.")
    else:
        with sync_playwright() as p:
            with st.spinner("🔄 Đang kết nối trình duyệt đám mây và quét giá..."):
                try:
                    # Kết nối tới Browserless với Token của Hưng
                    browser = p.chromium.connect_over_cdp(f"wss://chrome.browserless.io?token={SBR_WS_ENDPOINT}")
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                    page = context.new_page()

                    # TRÌNH TỰ: Barcode trước -> Tên sau
                    st.write(f"🔍 Bước 1: Tìm theo Barcode ({barcode_in})...")
                    res = scrape_google_advanced(page, barcode_in, price_in)
                    
                    if not res:
                        st.write(f"⚠️ Barcode không thấy giá, chuyển sang tìm theo Tên ({name_in})...")
                        res = scrape_google_advanced(page, name_in, price_in)

                    if res:
                        diff = res['Giá TT'] - price_in
                        res['Chênh lệch (%)'] = f"{(diff / price_in * 100):+.1f}%"
                        st.success("✅ Đã tìm thấy giá thị trường phù hợp!")
                        st.table(pd.DataFrame([res]))
                    else:
                        st.warning("❌ Google trả về trang trống hoặc không có giá phù hợp với mốc Genshai.")
                    
                    browser.close()
                except Exception as e:
                    st.error(f"Lỗi kết nối Browserless: {e}")
