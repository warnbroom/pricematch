import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time

st.set_page_config(page_title="Genshai Web Final V37.3", layout="wide")

# --- QUẢN LÝ KẾT NỐI ---
SBR_WS_ENDPOINT = st.sidebar.text_input("Browserless Token", value="2UBSKVhZ0O0zDyk4407ed0", type="password")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def scrape_google_failsafe(page, query, gia_genshai):
    try:
        # Sử dụng tham số tbm=shop để ép Google vào trang mua sắm (ít Captcha hơn)
        url = f"https://www.google.com/search?q=giá+bán+{query.replace(' ', '+')}&hl=vi&gl=vn"
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(5)

        # Lấy toàn bộ text và lọc giá
        content = page.evaluate("() => document.body.innerText")
        price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', content)
        
        valid_prices = []
        for m in price_matches:
            p = clean_price(m)
            if gia_genshai * 0.5 < p < gia_genshai * 1.5:
                valid_prices.append(p)
        
        if valid_prices:
            best_price = min(valid_prices, key=lambda x: abs(x - gia_genshai))
            return {"Nguồn": "Google Search", "Giá TT": best_price, "Link": url}
    except Exception as e:
        st.warning(f"⚠️ Lỗi khi đọc trang: {str(e)}")
    return None

# --- GIAO DIỆN CHÍNH ---
st.title("🚀 Genshai Web Final V37.3")

with st.form("final_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("KIỂM TRA NGAY")

if submitted:
    if not SBR_WS_ENDPOINT:
        st.error("Hưng hãy nhập Token Browserless để bắt đầu.")
    else:
        with sync_playwright() as p:
            try:
                # ÉP BUỘC XỬ LÝ LỖI KẾT NỐI
                with st.spinner("🔗 Đang thiết lập kết nối an toàn với trình duyệt đám mây..."):
                    endpoint = f"wss://chrome.browserless.io?token={SBR_WS_ENDPOINT.strip()}"
                    browser = p.chromium.connect_over_cdp(endpoint)
                    context = browser.new_context()
                    page = context.new_page()

                    # Bước 1: Thử tìm theo Barcode
                    st.write(f"🔍 Bước 1: Truy vấn Barcode {barcode_in}...")
                    res = scrape_google_failsafe(page, barcode_in, price_in)
                    
                    if not res:
                        # Bước 2: Thử tìm theo Tên
                        st.write(f"⚠️ Không thấy giá qua Barcode, đang thử tìm theo Tên...")
                        res = scrape_google_failsafe(page, name_in, price_in)

                    if res:
                        diff = res['Giá TT'] - price_in
                        res['Chênh lệch (%)'] = f"{(diff / price_in * 100):+.1f}%"
                        st.success("✅ Thành công! Đã tìm thấy giá thị trường.")
                        st.table(pd.DataFrame([res]))
                    else:
                        st.error("❌ Không tìm thấy giá phù hợp. Hãy thử rút ngắn tên sản phẩm.")
                    
                    browser.close()
            except Exception as connect_error:
                # Báo lỗi cụ thể nếu Token sai hoặc hết hạn
                st.error(f"❌ Lỗi kết nối Browserless: {str(connect_error)}")
                st.info("💡 Mẹo: Kiểm tra xem Token có bị thừa dấu cách không, hoặc thử đăng ký một Token mới tại browserless.io.")
