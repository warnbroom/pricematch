import streamlit as st
import pandas as pd
import requests
import re

st.set_page_config(page_title="Genshai Smart Search V39.0", layout="wide")

# --- CẤU HÌNH SIDEBAR ---
with st.sidebar:
    st.header("Cài đặt SerpApi")
    # Hưng dán Key lấy từ serpapi.com vào đây
    SERP_API_KEY = st.text_input("Nhập SerpApi Key", type="password")
    st.info("Mẹo: Đăng ký tại serpapi.com để lấy Key miễn phí.")

def clean_price(text):
    if not text: return 0
    # Xử lý các định dạng giá: 81.400, 81400, 81.400đ...
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def get_price_serpapi(query, gia_genshai):
    """
    Sử dụng SerpApi để lấy kết quả Google thực tế.
    """
    url = "https://serpapi.com/search"
    params = {
        "engine": "google",
        "q": f"giá bán {query}",
        "location": "Vietnam",
        "hl": "vi",
        "gl": "vn",
        "api_key": SERP_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # SerpApi trả về kết quả trong mục 'organic_results'
        results = data.get("organic_results", [])
        valid_prices = []

        for res in results:
            # Quét giá trong cả Tiêu đề và Snippet
            title = res.get("title", "")
            snippet = res.get("snippet", "")
            combined_text = title + " " + snippet
            
            # Tìm các con số có ký hiệu tiền tệ
            matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', combined_text)
            
            for m in matches:
                p = clean_price(m)
                # Lọc giá trong khoảng 60% - 140% giá Genshai
                if gia_genshai * 0.6 < p < gia_genshai * 1.4:
                    valid_prices.append({
                        "Giá TT": p,
                        "Nguồn": res.get("displayed_link"),
                        "Link": res.get("link")
                    })
        
        if valid_prices:
            # Chọn giá sát nhất với giá mục tiêu của Genshai
            return min(valid_prices, key=lambda x: abs(x["Giá TT"] - gia_genshai))
            
    except Exception as e:
        st.error(f"Lỗi kết nối SerpApi: {e}")
    return None

# --- GIAO DIỆN CHÍNH ---
st.title("🚀 Genshai Smart Search V39.0")
st.markdown("---")

with st.form("search_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên sản phẩm", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("KIỂM TRA GIÁ THỊ TRƯỜNG")

if submitted:
    if not SERP_API_KEY:
        st.warning("Hưng ơi, bạn cần nhập SerpApi Key ở thanh bên trái!")
    else:
        with st.spinner("🔄 Đang lấy dữ liệu trực tiếp từ Google..."):
            # Lần 1: Tìm theo Barcode (Độ chính xác cao nhất)
            res = get_price_serpapi(barcode_in, price_in)
            
            if not res:
                st.info("🔍 Barcode không khớp, đang tìm theo tên sản phẩm...")
                res = get_price_serpapi(name_in, price_in)
                
            if not res:
                st.info("🔍 Thử tìm kiếm mở rộng...")
                # Rút gọn tên để tăng khả năng tìm thấy
                short_name = " ".join(name_in.split()[:4])
                res = get_price_serpapi(short_name, price_in)

            if res:
                st.success("✅ Đã tìm thấy giá phù hợp!")
                # Tính chênh lệch
                diff = res['Giá TT'] - price_in
                res['Chênh lệch'] = f"{diff:+,.0f}đ ({(diff/price_in*100):+.1f}%)"
                st.table(pd.DataFrame([res]))
            else:
                st.error("❌ Không tìm thấy giá phù hợp trên Google.")
