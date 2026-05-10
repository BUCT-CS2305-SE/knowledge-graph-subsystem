import requests
import pandas as pd
import os
import time
from datetime import datetime

# 配置常量
MUSEUM_NAME = "Princeton University Art Museum"
LOCATION = "Princeton, USA"
IMAGE_DIR = os.path.join(os.path.dirname(__file__), "../images/princeton")
CSV_PATH = os.path.join(os.path.dirname(__file__), "../data/princeton_museum.csv")

HEADERS = {
    "User-Agent": "KnowledgeGraphAcademicProject/1.0",
    "Accept": "application/json"
}

def init_env():
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

def download_image(image_url, object_id):
    if not image_url:
        return ""
    
    file_name = f"obj_{object_id}.jpg"
    file_path = os.path.join(IMAGE_DIR, file_name)
    rel_path = f"images/princeton/{file_name}"
    
    if os.path.exists(file_path):
        return rel_path
        
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            return rel_path
    except Exception as e:
        print(f"Failed to download image {image_url}: {e}")
    return ""

def fetch_princeton_data(target_count=1700):
    """
    Princeton Art Museum API 抓取函数.
    Princeton 公开了基于 Elasticsearch 的 API: https://data.artmuseum.princeton.edu/search
    通过该 API 我们能够拉取到需要的 JSON 对象。
    """
    all_records = []
    
    # Princeton Museum API endpoint (基于 GraphQL/Elasticsearch)
    # 此 API 是其前端调用的检索接口
    search_url = "https://data.artmuseum.princeton.edu/search"
    
    base_detail_url = "https://artmuseum.princeton.edu/collections/objects/"
    
    print(f"开始抓取 {MUSEUM_NAME} 数据（目标约 {target_count} 条）...")

    # 简化的参数，主要以国家/产地/关键字筛选 Chinese 艺术品
    # 具体通过 payload 获取数据
    payload = {
        "size": 100,
        "from": 0,
        "q": "china OR chinese"
    }

    try:
        response = requests.get("https://data.artmuseum.princeton.edu/objects/search", params=payload, headers=HEADERS)
        
        # 如果 API 可用则执行 JSON 解析，否则这里做一个 Fallback 说明
        # 注意: 实际情况中 Princeton 可能有一定防护措施或改过 API 地址，这里使用已知的数据源地址做结构化原型
        if response.status_code == 200:
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits:
                source = hit.get("_source", {})
                object_id = source.get("objectid", hit.get("_id"))
                
                # 获取原图像
                images = source.get("images", [])
                image_url = ""
                if images:
                    # 尝试拼接高清图片地址 (Princeton 通常使用 IIIF 或直接媒体库地址)
                    # 例如: https://data.artmuseum.princeton.edu/media/.../full/!800,800/0/default.jpg
                    base_img = images[0].get("base_uri", "")
                    if base_img:
                        image_url = f"{base_img}/full/full/0/default.jpg"

                image_path = download_image(image_url, object_id) if image_url else ""

                record = {
                    "object_id": object_id,
                    "title": source.get("title", ""),
                    "period": source.get("displaydate", ""),
                    "type": source.get("objecttype", ""),
                    "material": source.get("medium", ""),
                    "description": source.get("description", "") or "",
                    "dimensions": source.get("dimensions", ""),
                    "museum": MUSEUM_NAME,
                    "location": LOCATION,
                    "detail_url": f"{base_detail_url}{object_id}",
                    "image_url": image_url,
                    "image_path": image_path,
                    "credit_line": source.get("creditline", ""),
                    "accession_number": source.get("objectnumber", ""),
                    "crawl_date": datetime.now().strftime("%Y-%m-%d")
                }
                
                all_records.append(record)
                print(f"已获取: {len(all_records)} | 当前处理: {object_id} - {record['title']}")
                time.sleep(0.5)
                
                if len(all_records) >= target_count:
                    break
        else:
            print(f"API 获取失败, 状态码: {response.status_code}。可能需要使用 Playwright 深度渲染 DOM 来提取。")

    except Exception as e:
        print(f"获取/解析数据发生异常: {e}")

    return all_records

def main():
    init_env()
    records = fetch_princeton_data(target_count=20) # 原型测试拉取 20 条
    if records:
        df = pd.DataFrame(records)
        df.to_csv(CSV_PATH, index=False, encoding='utf-8')
        print(f"抓取完成！共 {len(records)} 条记录，已保存至 {CSV_PATH}")
    else:
        print("未获取到数据记录。")

if __name__ == "__main__":
    main()
