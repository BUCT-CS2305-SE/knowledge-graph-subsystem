import os
import time
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://artmuseum.princeton.edu"
SAVE_DIR = "images/princeton"
os.makedirs(SAVE_DIR, exist_ok=True)

all_data = []
visited = set()

def download_image(url, path):
    if not url:
        return
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
            print("图片下载:", path)
    except Exception as e:
        print("图片下载失败:", e)

def parse_detail(page, url):
    if url in visited:
        return
    visited.add(url)
    page.goto(url, timeout=60000)
    page.wait_for_timeout(1500)
    soup = BeautifulSoup(page.content(), "lxml")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    object_id = url.rstrip("/").split("/")[-1]

    period = type_ = material = accession_number = description = dimensions = ""

    info_table = soup.find("dl")
    if info_table:
        dt_list = info_table.find_all("dt")
        dd_list = info_table.find_all("dd")
        for dt, dd in zip(dt_list, dd_list):
            key = dt.get_text(strip=True).lower()
            val = dd.get_text(" ", strip=True)
            if "date" in key or "dynasty" in key:
                period = val
            elif "classification" in key or "type" in key:
                type_ = val
            elif "medium" in key or "material" in key:
                material = val
            elif "dimensions" in key:
                dimensions = val
            elif "accession" in key:
                accession_number = val

    desc_div = soup.find("div", class_="object__description")
    if desc_div:
        description = desc_div.get_text(" ", strip=True)

    image_url = ""
    img_tag = soup.find("img", class_="object__image")
    if img_tag:
        src = img_tag.get("src")
        if src:
            image_url = urljoin(BASE_URL, src)

    image_path = f"{SAVE_DIR}/obj_{object_id}.jpg"
    if image_url:
        download_image(image_url, image_path)

    all_data.append({
        "object_id": object_id,
        "title": title,
        "period": period,
        "type": type_,
        "material": material,
        "description": description,
        "dimensions": dimensions,
        "museum": "Princeton University Art Museum",
        "location": "Princeton, USA",
        "detail_url": url,
        "image_url": image_url,
        "image_path": image_path,
        "credit_line": "",
        "accession_number": accession_number,
        "crawl_date": datetime.now().strftime("%Y-%m-%d")
    })
    print("保存成功:", title)

def crawl():
    page_size = 20
    from_index = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        while True:
            url = (
                f"{BASE_URL}/art/collections/search?"
                f"query=chinese&mainSearch=chinese&title=0"
                f"&artist_name=0&sort=relevance&from={from_index}"
            )
            print(f"抓取分页: from={from_index}")
            page.goto(url, timeout=60000)
            page.wait_for_timeout(2000)

            soup = BeautifulSoup(page.content(), "lxml")
            links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/collections/objects/" in href:
                    links.add(urljoin(BASE_URL, href))

            if not links:
                print("没有更多搜索结果，爬取结束")
                break

            print("本页详情数量:", len(links))
            for link in links:
                try:
                    parse_detail(page, link)
                    time.sleep(0.5)
                except Exception as e:
                    print("详情页失败:", e)

            from_index += page_size

        browser.close()

    # 保存 CSV
    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(all_data)
    df.drop_duplicates(subset=["object_id"], inplace=True)
    csv_path = "data/princeton_museum_chinese.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print("爬取完成，总条数:", len(df))
    print("CSV 文件:", csv_path)

if __name__ == "__main__":
    crawl()
