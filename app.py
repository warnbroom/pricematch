import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import re
import subprocess
import time
import urllib.parse

# --- 1. SETUP ---
@st.cache_resource
def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception: pass

install_browser()

st.set_page_config(page_title="Genshai Direct Search V33.0", layout="wide")

def clean_price(text):
    if not text: return 0
    digits = re.sub(r'\D', '', str(text))
    return int(digits) if digits else 0

# --- 2. LOGIC TRUY CẬP TRỰC TIẾP ---

def scrape_direct_retailers(page, product_name, gia_genshai):
    # Định dạng URL tìm kiếm dựa trên thông tin Hưng cung cấp
    encoded_name = urllib.parse.quote(product_name)
    sites = [
        {"name": "Bách Hóa Xanh", "url": f"https://www.bachhoaxanh.com/tim-kiem?key={encoded_name}"},
        {"name": "Co.op Online", "url": f"https://cooponline.vn/search?router=productListing&query={encoded_name}"},
        {"name": "Kingfoodmart", "url": f"https://kingfoodmart.com/search?keyword={encoded_name}"},
        {"name": "AeonEshop", "url": f"https://aeoneshop.com/products/search/{encoded_name}"}
    ]
    
    results = []
    
    for site in sites:
        try:
            st.write(f"🔄 Đang kiểm tra: {site['name']}...")
            page.goto(site['url'], wait_until="networkidle", timeout=20000)
            time.sleep(3) # Chờ trang load sản phẩm

            # Quét toàn bộ văn bản trang để tìm giá (Text Scan) vì mỗi trang có class khác nhau
            content = page.evaluate("() => document.body.innerText")
            
            # Tìm tất cả các cụm số có ký hiệu đ hoặc ₫
            price_matches = re.findall(r'(\d{1,3}(?:[\.,]\d{3})+)\s?[₫đ]', content)
            
            valid_prices = []
            for match in price_matches:
                p = clean_price(match)
                # Filter thông minh dựa trên giá Genshai
                if gia_genshai * 0.3 < p < gia_genshai * 2.5:
                    valid_prices.append(p)
            
            if valid_prices:
                # Chọn giá xuất hiện nhiều nhất hoặc nhỏ nhất (thường là giá lẻ)
                best_price = min(valid_prices)
                results.append({
                    "Nguồn": site['name'],
                    "Giá TT": best_price,
                    "Link": site['url']
                })
        except Exception as e:
            continue
            
    return results

# --- 3. ĐIỀU PHỐI ---
def start_process(name, price_niemyet):
    with sync_playwright() as p:
        browser = p.
