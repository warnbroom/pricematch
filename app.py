import streamlit as st
import pandas as pd
import requests
import re

st.set_page_config(page_title="Genshai API Pro V38.0", layout="wide")

# --- CẤU HÌNH GOOGLE API ---
# Hưng dán 2 mã vừa lấy vào đây hoặc nhập ở Sidebar
API_KEY = st.sidebar.text_input("AIzaSyB8smn4fvYfs39EUznKtrVIoq33eUfrbxo", type="password")
SEARCH_ENGINE_ID = st.sidebar.text_input("<script async src="https://cse.google.com/cse.js?cx=61025d0bba9a249bf">
</script>
<div class="gcse-search"></div>")

def clean_price(text):
    if not text: return 0
    # Xử lý cả định dạng giá trong snippet (VD: 81.400đ, Giá: 85.000...)
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def get_price_from_api(query, gia_genshai):
    """
    Sử dụng Google Custom Search API để lấy kết quả.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": f"giá bán {query}",
        "gl": "vn", # Giới hạn kết quả tại Việt Nam
        "hl": "vi"  # Ngôn ngữ tiếng Việt
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "items" not in data:
            return None

        valid_prices = []
        for item in data["items"]:
            # API trả về Tiêu đề và Đoạn mô tả (Snippet)
            text_to_scan = item.get("title", "") + " " + item.get("snippet", "")
            
            # Tìm giá tiền trong văn bản
            price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', text_to_scan)
            
            for m in price_matches:
                p = clean_price(m)
                # Lọc giá theo ngưỡng Genshai
                if gia_genshai * 0.5 < p < gia_genshai * 1.5:
                    valid_prices.append({"Giá TT": p, "Nguồn": item.get("displayLink"), "Link": item.get("link")})
        
        if valid_prices:
            # Chọn kết quả có giá sát với Genshai nhất
            best_match = min(valid_prices, key=lambda x: abs(x["Giá TT"] - gia_genshai))
            return best_match

    except Exception as e:
        st.error(f"Lỗi kết nối API: {e}")
    return None

# --- GIAO DIỆN ---
st.title("🚀 Genshai API Pro V38.0")
st.info("Hệ thống sử dụng Google API chính chủ - Không Captcha, không lỗi trình duyệt.")

with st.form("api_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("TRA CỨU NGAY")

if submitted:
    if not API_KEY or not SEARCH_ENGINE_ID:
        st.error("Hưng cần nhập đủ API Key và Search Engine ID ở Sidebar.")
    else:
        with st.spinner("🔄 Đang truy vấn dữ liệu từ Google Cloud..."):
            # Thứ tự ưu tiên: Barcode -> Tên
            res = get_price_from_api(barcode_in, price_in)
            
            if not res:
                st.write("⚠️ Barcode không thấy giá, đang thử tìm theo Tên...")
                res = get_price_from_api(name_in, price_in)

            if res:
                diff = res['Giá TT'] - price_in
                res['Chênh lệch (%)'] = f"{(diff / price_in * 100):+.1f}%"
                st.success("✅ Đã tìm thấy giá thị trường!")
                st.table(pd.DataFrame([res]))
            else:
                st.error("❌ Không tìm thấy giá phù hợp. Hãy thử kiểm tra lại tên sản phẩm.")
