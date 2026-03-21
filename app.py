import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time
import io

st.set_page_config(page_title="Genshai Visual Pro V37.4", layout="wide")

# --- QUẢN LÝ KẾT NỐI ---
SBR_WS_ENDPOINT = st.sidebar.text_input("Browserless Token", value="2UBSKVhZ0O0zDyk4407ed0", type="password")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def scrape_with_screenshot(page, query, gia_genshai):
    """
    Quét giá kèm theo chụp ảnh màn hình để debug.
    """
    screenshot_data = None
    result_data = None
    
    try:
        url = f"https://www.google.com/search?q=giá+bán+{query.replace(' ', '+')}&hl=vi&gl=vn"
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(5) # Chờ render nội dung

        # CHỤP ẢNH MÀN HÌNH NGAY LẬP TỨC
        screenshot_data = page.screenshot(full_page=False)

        # Logic quét giá
        content = page.evaluate("() => document.body.innerText")
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', content)
        
        valid_prices = []
        for m in price_matches:
            p = clean_price(m)
            if gia_genshai * 0.5 < p < gia_genshai * 1.5:
                valid_prices.append(p)
        
        if valid_prices:
            best_price = min(valid_prices, key=lambda x: abs(x - gia_genshai))
            result_data = {"Nguồn": "Google", "Giá TT": best_price, "Link": url}
            
    except Exception as e:
        st.error(f"Lỗi khi quét: {e}")
        
    return result_data, screenshot_data

# --- GIAO DIỆN ---
st.title("🚀 Genshai Visual Pro V37.4")

with st.form("visual_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("KIỂM TRA & CHỤP ẢNH")

if submitted:
    if not SBR_WS_ENDPOINT:
        st.error("Vui lòng nhập Token Browserless.")
    else:
        with sync_playwright() as p:
            try:
                with st.spinner("🔗 Đang kết nối trình duyệt đám mây..."):
                    endpoint = f"wss://chrome.browserless.io?token={SBR_WS_ENDPOINT.strip()}"
                    browser = p.chromium.connect_over_cdp(endpoint)
                    page = browser.new_context().new_page()

                    st.write(f"🔍 Đang truy vấn dữ liệu...")
                    # Thử tìm theo Barcode trước
                    res, ss = scrape_with_screenshot(page, barcode_in, price_in)
                    
                    if not res:
                        st.write(f"⚠️ Thử lại với tên sản phẩm...")
                        res, ss = scrape_with_screenshot(page, name_in, price_in)

                    # HIỂN THỊ SCREENSHOT
                    if ss:
                        with st.expander("📷 XEM ẢNH CHỤP MÀN HÌNH GOOGLE", expanded=True):
                            st.image(ss, caption="Kết quả thực tế từ trình duyệt đám mây")
                    
                    if res:
                        st.success("✅ Đã tìm thấy giá!")
                        st.table(pd.DataFrame([res]))
                    else:
                        st.warning("❌ Không tìm thấy giá phù hợp trong ảnh trên.")
                    
                    browser.close()
            except Exception as e:
                st.error(f"Lỗi hệ thống: {str(e)}")
