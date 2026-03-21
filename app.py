import streamlit as st
import pandas as pd
import requests
import re

st.set_page_config(page_title="Genshai API Pro V38.1", layout="wide")

# --- CẤU HÌNH SIDEBAR ---
with st.sidebar:
    st.header("Cài đặt API")
    api_key = st.text_input("Google API Key", value="AlzaSyB8smn4fvYfs39EUznk...", type="password")
    cx_id = st.text_input("Search Engine ID (CX)", value="61025d0bba9a249bf")

def clean_price(text):
    if not text: return 0
    # Xử lý các định dạng giá: 81.400, 81400, 81.400đ
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

def get_google_api_price(query, gia_genshai):
    url = "https://www.googleapis.com/customsearch/v1"
    # Thêm tham số 'cr=countryVN' để ép tìm kết quả tại VN
    params = {
        "key": api_key,
        "cx": cx_id,
        "q": f"giá bán \"{query}\"", # Để trong ngoặc kép để tìm chính xác
        "cr": "countryVN",
        "hl": "vi"
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "items" not in data:
            return None

        found_prices = []
        for item in data["items"]:
            # Quét cả Tiêu đề và Snippet
            text = item.get("title", "") + " " + item.get("snippet", "")
            # Tìm các con số có chữ đ hoặc ₫ đi kèm
            matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', text)
            
            for m in matches:
                p = clean_price(m)
                # Biên độ lọc: 50% - 150% giá Genshai để tránh nhặt nhầm giá sỉ/giá thùng
                if gia_genshai * 0.5 < p < gia_genshai * 1.5:
                    found_prices.append({
                        "Nguồn": item.get("displayLink"),
                        "Giá TT": p,
                        "Link": item.get("link")
                    })
        
        if found_prices:
            # Ưu tiên giá gần nhất với giá Genshai
            return min(found_prices, key=lambda x: abs(x["Giá TT"] - gia_genshai))
    except:
        return None
    return None

# --- UI ---
st.title("🚀 Genshai API Pro V38.1")

with st.form("search_form"):
    c1, c2, c3 = st.columns([1, 2, 1])
    barcode_in = c1.text_input("Barcode", value="8851130050753")
    name_in = c2.text_input("Tên SP", value="Kiwi - Dao Bào Vỏ 217")
    price_in = c3.number_input("Giá Genshai", value=81400)
    submitted = st.form_submit_button("TRA CỨU NGAY")

if submitted:
    if not api_key or not cx_id:
        st.error("Vui lòng điền đủ thông tin API ở Sidebar.")
    else:
        with st.spinner("🔄 Đang truy xuất dữ liệu từ Google API..."):
            # Thứ tự: Barcode ưu tiên hơn
            res = get_google_api_price(barcode_in, price_in)
            
            if not res:
                st.info("⚠️ Barcode không ra kết quả, đang thử tìm theo Tên...")
                # Rút gọn tên nếu quá dài để tăng tỉ lệ khớp
                short_name = " ".join(name_in.split()[:5]) 
                res = get_google_api_price(short_name, price_in)

            if res:
                st.success("✅ Đã tìm thấy giá thị trường!")
                st.table(pd.DataFrame([res]))
            else:
                st.error("❌ Không tìm thấy giá phù hợp. Mẹo: Hãy vào trang cài đặt CX và bật 'Search the entire web'.")
