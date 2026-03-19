import os
import streamlit as st

# MẸO CHO CLOUD: Tự động cài đặt trình duyệt nếu chưa có
if not os.path.exists("/home/adminuser/.cache/ms-playwright"):
    os.system("playwright install chromium")import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time

# 1. CẤU HÌNH GIAO DIỆN
st.set_page_config(page_title="Genshai Price Checker", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- LOGIC QUÉT DỮ LIỆU ---
def fetch_data(query, barcode=None, gia_niem_yet=0):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Bước 1: Quét Lotte Mart
        search_key = barcode if barcode else query
        try:
            lotte_url = f"https://www.lottemart.vn/vi-nsg/category?q={search_key}"
            page.goto(lotte_url, wait_until="networkidle", timeout=15000)
            content = page.evaluate("() => document.body.innerText")
            if "₫" in content or "đ" in content:
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                for i, line in enumerate(lines):
                    if "₫" in line or "đ" in line:
                        price = clean_price(line)
                        if 1000 < price < 10000000:
                            diff = ((price - gia_niem_yet) / gia_niem_yet * 100) if gia_niem_yet > 0 else 0
                            results.append({
                                "Nguồn": "Lotte Mart",
                                "Giá TT": price,
                                "Chênh lệch (%)": f"{diff:+.1f}%",
                                "Link": lotte_url
                            })
                            break
        except: pass

        # Bước 2: Quét Google Search
        try:
            google_url = f"https://www.google.com/search?q=giá+{query.replace(' ', '+')}"
            page.goto(google_url, wait_until="domcontentloaded", timeout=15000)
            items = page.query_selector_all("div[class*='g']")
            for item in items[:2]:
                text = item.inner_text()
                link = item.query_selector("a").get_attribute("href") if item.query_selector("a") else ""
                if "genshai.com.vn" in link: continue
                if "₫" in text or "đ" in text:
                    price = clean_price(text)
                    if 1000 < price < 10000000:
                        diff = ((price - gia_niem_yet) / gia_niem_yet * 100) if gia_niem_yet > 0 else 0
                        results.append({
                            "Nguồn": "Google",
                            "Giá TT": price,
                            "Chênh lệch (%)": f"{diff:+.1f}%",
                            "Link": link
                        })
                        break
        except: pass
        browser.close()
    return results

# --- GIAO DIỆN CHÍNH ---
st.title("🚀 Hệ Thống So Sánh Giá Genshai")
st.markdown("---")

tab1, tab2 = st.tabs(["🔍 Kiểm tra lẻ", "📁 Xử lý file Excel"])

with tab1:
    with st.form("check_form"):
        col1, col2, col3 = st.columns(3)
        barcode_in = col1.text_input("Mã Barcode")
        name_in = col2.text_input("Tên sản phẩm")
        price_in = col3.number_input("Giá niêm yết (Genshai)", min_value=0, step=500)
        submitted = st.form_submit_button("BẮT ĐẦU SO SÁNH")

    if submitted:
        if not (barcode_in or name_in):
            st.error("Vui lòng nhập Barcode hoặc Tên SP!")
        else:
            with st.spinner("Đang lấy giá thị trường..."):
                data = fetch_data(name_in, barcode_in, price_in)
                if data:
                    st.subheader(f"📊 Kết quả so sánh cho: {name_in or barcode_in}")
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Hiển thị tóm tắt thông minh
                    for res in data:
                        p_market = res['Giá TT']
                        if price_in > 0:
                            if p_market < price_in:
                                st.warning(f"⚠️ Giá {res['Nguồn']} đang RẺ HƠN Genshai {price_in - p_market:,.0f}đ")
                            elif p_market > price_in:
                                st.success(f"✅ Giá {res['Nguồn']} đang CAO HƠN Genshai {p_market - price_in:,.0f}đ")
                else:
                    st.error("Không tìm thấy dữ liệu giá trên Lotte/Google.")

with tab2:
    st.info("Hưng tải file Excel có cột 'Barcode', 'Tên' và 'Giá niêm yết' để xử lý hàng loạt.")
    uploaded_file = st.file_uploader("Chọn file .xlsx", type="xlsx")
