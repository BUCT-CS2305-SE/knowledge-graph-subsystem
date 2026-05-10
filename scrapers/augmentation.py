import urllib.parse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import json
import time

# 配置常量
BAIDU_BAIKE_URL = "https://baike.baidu.com/item/"
DATA_DIR = os.path.join(os.path.dirname(__file__), "../data/cleaned")
AUGMENTED_DATA_FILE = os.path.join(os.path.dirname(__file__), "../data/augmented_entities.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_baike_summary(keyword):
    """
    通过百度百科爬取朝代/艺术家等实体的摘要补充信息
    """
    if not keyword or pd.isna(keyword) or keyword == "Unknown":
        return ""
        
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"{BAIDU_BAIKE_URL}{encoded_keyword}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        # 百度百科如果存在该词条，通常返回 200。
        # 如果重定向或者没有，通常有特定标识，但抓取 summary div 最稳妥
        if response.status_code == 200:
            response.encoding = 'utf-8' # 防止中文乱码
            soup = BeautifulSoup(response.text, 'html.parser')
            # 摘要通常在一个特定的 class 里: lemma-summary 或者 J-summary
            summary_div = soup.find('div', class_='lemma-summary')
            if summary_div:
                text = summary_div.get_text(separator=' ', strip=True)
                # 清理类似 [1] [2] 这种角标
                import re
                text = re.sub(r'\[\d+\]', '', text)
                return text
                
    except Exception as e:
        print(f"Failed to fetch Baike for {keyword}: {e}")
        
    return ""

def align_and_augment_entities():
    """
    针对当前爬取到的数据池，抽取出独立的实体（如朝代），去重并请求外部百科数据进行补充
    """
    print("开始实体对齐与数据补充任务...")
    
    unique_periods = set()
    # 读取所有的 clean 数据集合并朝代实体
    for file in os.listdir(DATA_DIR):
        if file.endswith(".csv"):
            file_path = os.path.join(DATA_DIR, file)
            df = pd.read_csv(file_path)
            if 'period' in df.columns:
                for p in df['period'].unique():
                    unique_periods.add(p)
                    
    # 如果没数据造一些伪数据用于原型演示
    if not unique_periods:
        unique_periods = {"唐朝", "清朝", "明朝", "Song Dynasty"}
        
    print(f"找到 {len(unique_periods)} 个待补充的朝代/时期实体。")
    
    augmented_data = {}
    
    for period in unique_periods:
        # 有些是英文，可以做个简单的映射机制以提高百度百科命中率
        search_keyword = period
        if "Qing" in period:
            search_keyword = "清朝"
        elif "Ming" in period:
            search_keyword = "明朝"
        elif "Song" in period or "Sung" in period:
            search_keyword = "宋朝"
        elif "Tang" in period:
            search_keyword = "唐朝"
        elif "Han" in period:
            search_keyword = "汉朝"
            
        print(f"正在补充实体信息: {period} (搜索词: {search_keyword})...")
        summary = fetch_baike_summary(search_keyword)
        
        augmented_data[period] = {
            "uri": f"http://knowledge-graph.system/entity/period/{urllib.parse.quote(period)}",
            "name": period,
            "description": summary,
            "source": "Baidu Baike" if summary else "None",
            "fetch_date": time.strftime("%Y-%m-%d")
        }
        
        time.sleep(1) # 控制请求频率防封
        
    # 保存对齐增强后的实体到 JSON
    with open(AUGMENTED_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(augmented_data, f, ensure_ascii=False, indent=4)
        
    print(f"实体补充完成。结果保存在 {AUGMENTED_DATA_FILE}")

def main():
    align_and_augment_entities()

if __name__ == "__main__":
    main()
