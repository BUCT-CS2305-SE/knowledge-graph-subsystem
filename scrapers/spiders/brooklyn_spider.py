import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
from datetime import datetime
import re

# 配置常量
MUSEUM_NAME = "Brooklyn Museum"
LOCATION = "New York, USA"
IMAGE_DIR = os.path.join(os.path.dirname(__file__), "../images/brooklyn")
CSV_PATH = os.path.join(os.path.dirname(__file__), "../data/brooklyn_museum.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

def init_env():
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

def download_image(image_url, object_id):
    if not image_url:
        return ""
    
    file_name = f"obj_{object_id}.jpg"
    file_path = os.path.join(IMAGE_DIR, file_name)
    rel_path = f"images/brooklyn/{file_name}"
    
    if os.path.exists(file_path):
        return rel_path
        
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=20)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            return rel_path
    except Exception as e:
        print(f"Failed to download image {image_url}: {e}")
    return ""

def fetch_brooklyn_data(target_count=1600):
    """
    Brooklyn Museum 爬虫
    使用 HTML 解析，遍历 OpenCollection 搜索页面 (Asian Art / China keyword)
    """
    all_records = []
    base_url = "https://www.brooklynmuseum.org"
    search_url = f"{base_url}/opencollection/search?keyword=Chinese"
    
    print(f"开始抓取 {MUSEUM_NAME} 数据（目标约 {target_count} 条）...")

    page = 1
    while len(all_records) < target_count:
        url = f"{search_url}&offset={(page-1)*30}" # 假设每页30条
        try:
            print(f">>> 请求搜索页: {url}")
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                print(f"页面抓取失败: 状态码 {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 找到列表中的所有具体文物链接（注意：这里采用假设的选择器结构，实际运行时可能需要根据DOM微调）
            item_links = soup.select('.image-card a, .item-card a') 
            
            if not item_links:
                print("未解析到更多文物链接，可能已到最后一页或需调整 CSS 选择器。")
                break
                
            for link in item_links:
                href = link.get('href')
                if not href or '/objects/' not in href:
                    continue
                    
                detail_url = base_url + href if not href.startswith('http') else href
                object_id = href.split('/')[-1]
                
                # 请求详情页获取精准字段
                try:
                    detail_res = requests.get(detail_url, headers=HEADERS, timeout=15)
                    detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
                    
                    # 抓取原图: 博物馆通常有一个高分辨率的查看器或提供下载链接
                    img_tag = detail_soup.select_one('.object-image img')
                    image_url = ""
                    if img_tag and img_tag.get('src'):
                        img_src = img_tag.get('src')
                        # 去除图片URL中的尺寸限制比如 /size2/ 转为 /size4/ (原图) 或者根据网站规则处理
                        image_url = img_src.replace('size2', 'size4') if 'size2' in img_src else img_src
                        if not image_url.startswith('http'):
                            image_url = base_url + image_url
                            
                    # 解析基础字段（示例选择器）
                    title = detail_soup.select_one('h1')
                    title = title.text.strip() if title else ""
                    
                    date_field = detail_soup.find('strong', string=re.compile('DATES', re.I))
                    period = date_field.find_next('span').text.strip() if date_field else ""

                    medium_field = detail_soup.find('strong', string=re.compile('MEDIUM', re.I))
                    material = medium_field.find_next('span').text.strip() if medium_field else ""

                    dim_field = detail_soup.find('strong', string=re.compile('DIMENSIONS', re.I))
                    dimensions = dim_field.find_next('span').text.strip() if dim_field else ""

                    credit_field = detail_soup.find('strong', string=re.compile('CREDIT LINE', re.I))
                    credit_line = credit_field.find_next('span').text.strip() if credit_field else ""

                    acc_field = detail_soup.find('strong', string=re.compile('ACCESSION NUMBER', re.I))
                    accession_number = acc_field.find_next('span').text.strip() if acc_field else ""
                    
                    # 简单归类为 Asian Art
                    artwork_type = "Chinese Art / Asian Art"
                    
                    description_div = detail_soup.select_one('.object-description')
                    description = description_div.text.strip() if description_div else ""
                    
                    image_path = download_image(image_url, object_id) if image_url else ""
                    
                    record = {
                        "object_id": object_id,
                        "title": title,
                        "period": period,
                        "type": artwork_type,
                        "material": material,
                        "description": description,
                        "dimensions": dimensions,
                        "museum": MUSEUM_NAME,
                        "location": LOCATION,
                        "detail_url": detail_url,
                        "image_url": image_url,
                        "image_path": image_path,
                        "credit_line": credit_line,
                        "accession_number": accession_number,
                        "crawl_date": datetime.now().strftime("%Y-%m-%d")
                    }
                    
                    all_records.append(record)
                    print(f"已获取: {len(all_records)} | 当前处理: {object_id} - {title[:20]}")
                    
                    if len(all_records) >= target_count:
                        break
                        
                    time.sleep(1) # 尊重网站速率
                    
                except Exception as ex:
                    print(f"解析详情页 {detail_url} 出错: {ex}")
            
            page += 1
        except Exception as e:
            print(f"页级请求报错: {e}")
            break
            
    return all_records

def main():
    init_env()
    records = fetch_brooklyn_data(target_count=20) # 原型测试20条
    
    if records:
        df = pd.DataFrame(records)
        df.to_csv(CSV_PATH, index=False, encoding='utf-8')
        print(f"抓取完成！共 {len(records)} 条记录，已保存至 {CSV_PATH}")
    else:
        print("未获取到数据记录。")

if __name__ == "__main__":
    main()
