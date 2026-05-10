import requests
import pandas as pd
import os
import time
from datetime import datetime

# 配置常量
QUERY = "China"
API_URL = "https://api.artic.edu/api/v1/artworks/search"
BASE_DETAIL_URL = "https://www.artic.edu/artworks/"
IMAGE_DIR = os.path.join(os.path.dirname(__file__), "../images/chicago")
CSV_PATH = os.path.join(os.path.dirname(__file__), "../data/chicago_museum.csv")
MUSEUM_NAME = "Art Institute of Chicago"
LOCATION = "Chicago, USA"

# 请求头，包含对API提供者的友好说明
HEADERS = {
    "User-Agent": "KnowledgeGraphAcademicProject/1.0"
}

def init_env():
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
    
def download_image(image_url, object_id):
    if not image_url:
        return ""
    
    file_name = f"obj_{object_id}.jpg"
    file_path = os.path.join(IMAGE_DIR, file_name)
    rel_path = f"images/chicago/{file_name}"
    
    if os.path.exists(file_path):
        return rel_path # 已存在，跳过下载
        
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            return rel_path
    except Exception as e:
        print(f"Failed to download image {image_url}: {e}")
    return ""

def fetch_chicago_data(target_count=2000):
    all_records = []
    page = 1
    limit = 100  # API每页上限一般为100
    
    print(f"开始抓取 {MUSEUM_NAME} 数据（目标抓取约 {target_count} 条）...")
    
    while len(all_records) < target_count:
        # query 参数设置
        params = {
            "q": "Chinese",
            "fields": "id,title,date_display,artwork_type_title,medium_display,description,dimensions,credit_line,main_reference_number,image_id,place_of_origin",
            "limit": limit,
            "page": page
        }

        try:
            response = requests.get(API_URL, params=params, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            
            artworks = data.get("data", [])
            if not artworks:
                print("没有更多数据了，抓取结束。")
                break
                
            for item in artworks:
                # 简单过滤，确保是与中国相关的文物（包含 Chinese 或者 origin 包含 China）
                origin = str(item.get("place_of_origin", "")).lower()
                title = str(item.get("title", "")).lower()
                if "china" not in origin and "chinese" not in origin and "chinese" not in title:
                    continue

                object_id = item.get("id")
                image_id = item.get("image_id")
                
                # IITF Image API：使用 full/full/0/default.jpg 获取原图
                image_url = f"https://www.artic.edu/iiif/2/{image_id}/full/full/0/default.jpg" if image_id else ""
                
                # 下载图片
                image_path = download_image(image_url, object_id)
                
                record = {
                    "object_id": object_id,
                    "title": item.get("title", ""),
                    "period": item.get("date_display", ""),
                    "type": item.get("artwork_type_title", ""),
                    "material": item.get("medium_display", ""),
                    "description": item.get("description", "") or "", 
                    "dimensions": item.get("dimensions", ""),
                    "museum": MUSEUM_NAME,
                    "location": LOCATION,
                    "detail_url": f"{BASE_DETAIL_URL}{object_id}",
                    "image_url": image_url,
                    "image_path": image_path,
                    "credit_line": item.get("credit_line", ""),
                    "accession_number": item.get("main_reference_number", ""),
                    "crawl_date": datetime.now().strftime("%Y-%m-%d")
                }
                # 清理HTML描述标签
                if isinstance(record["description"], str):
                    record["description"] = record["description"].replace("<p>", "").replace("</p>", "").strip()
                
                all_records.append(record)
                print(f"已获取: {len(all_records)} / {target_count} | 当前正在处理: {object_id} - {record['title']}")
                time.sleep(0.5)
                
                if len(all_records) >= target_count:
                    break
                    
            page += 1
            print(f"--- 准备拉取下一页: {page} ---")
            
        except Exception as e:
            print(f"抓取异常: {e}")
            break
            
    return all_records

def main():
    init_env()
    # 为保证3个博物馆加起来达到5000，这里设置每家目标为1700
    records = fetch_chicago_data(target_count=1700)
    
    if records:
        df = pd.DataFrame(records)
        df.to_csv(CSV_PATH, index=False, encoding='utf-8')
        print(f"抓取完成！共 {len(records)} 条记录，已保存至 {CSV_PATH}")
    else:
        print("未抓取到有效记录。")

if __name__ == "__main__":
    main()
