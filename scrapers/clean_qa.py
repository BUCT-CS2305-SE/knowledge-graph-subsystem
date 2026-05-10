import os
import re
import pandas as pd

# 配置常量
DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
CLEAN_DATA_DIR = os.path.join(os.path.dirname(__file__), "../data/cleaned")

def init_env():
    if not os.path.exists(CLEAN_DATA_DIR):
        os.makedirs(CLEAN_DATA_DIR)

def standardize_period(period_str):
    """
    统一年代格式 (Rule-based mapping)
    将类似 "Qing dynasty (1644–1911)"、"Ming"统一映射
    """
    if not isinstance(period_str, str) or not period_str:
        return "Unknown"
    
    period_lower = period_str.lower()
    
    if "qing" in period_lower or "ch'ing" in period_lower:
        return "Qing Dynasty (1644-1911)"
    if "ming" in period_lower:
        return "Ming Dynasty (1368-1644)"
    if "yuan" in period_lower:
        return "Yuan Dynasty (1271-1368)"
    if "song" in period_lower or "sung" in period_lower:
        return "Song Dynasty (960-1279)"
    if "tang" in period_lower:
        return "Tang Dynasty (618-907)"
    if "han" in period_lower:
        return "Han Dynasty (202 BC-220 AD)"
    if "shang" in period_lower:
        return "Shang Dynasty (c. 1600-1046 BC)"
    if "zhou" in period_lower or "chou" in period_lower:
        return "Zhou Dynasty (c. 1046-256 BC)"
    if "jin" in period_lower and "western" not in period_lower:
        return "Jin Dynasty (1115-1234)"
    
    # 去除多余空格和特殊字符
    clean_str = re.sub(r'\\s+', ' ', period_str).strip()
    return clean_str

def standardize_type(type_str):
    """
    统一文物类型
    """
    if not isinstance(type_str, str) or not type_str:
        return "Other"
        
    t_lower = type_str.lower()
    if "paint" in t_lower or "scroll" in t_lower:
        return "Painting"
    if "ceramic" in t_lower or "porcelain" in t_lower or "pottery" in t_lower:
        return "Ceramics"
    if "bronze" in t_lower or "metal" in t_lower:
        return "Bronze/Metalwork"
    if "jade" in t_lower:
        return "Jade"
    if "sculpture" in t_lower or "statue" in t_lower or "figure" in t_lower:
        return "Sculpture"
    if "calligraphy" in t_lower:
        return "Calligraphy"
    if "textile" in t_lower or "silk" in t_lower or "garment" in t_lower:
        return "Textiles"
        
    return type_str.title()

def validate_image(image_path_rel):
    """
    检验本地图片是否存在且大小正常（>0）
    由于csv存放相对路径 'images/...'，我们在验证时要转绝对路径
    """
    if not image_path_rel or not isinstance(image_path_rel, str):
        return False
    
    base_proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    abs_path = os.path.join(base_proj_dir, image_path_rel)
    
    if os.path.exists(abs_path) and os.path.getsize(abs_path) > 1024: # > 1KB 视为有效图片
        return True
    return False

def clean_dataset(filename):
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        print(f"Skipping {filename}... File not found.")
        return None
        
    print(f"Processing {filename}...")
    df = pd.read_csv(file_path, encoding='utf-8')
    initial_count = len(df)
    
    # 1. 去重 (按object_id)
    df.drop_duplicates(subset=['object_id'], keep='first', inplace=True)
    
    # 2. 检查必填项 (object_id, title, detail_url, image_url, crawl_date)
    required_cols = ['object_id', 'title', 'detail_url', 'image_url', 'crawl_date']
    for c in required_cols:
        if c in df.columns:
            df.dropna(subset=[c], inplace=True)
            df = df[df[c] != ""]
            
    # 3. 字段标准化
    df['period_clean'] = df['period'].apply(standardize_period)
    df['type_clean'] = df['type'].apply(standardize_type)
    
    # 4. 图片验证
    # 如果图片验证失败，我们可以标记一列 'is_image_valid' = False，或者直接 Drop。
    # 根据需求我们先做记录并过滤掉无效图片的文物
    df['is_image_valid'] = df['image_path'].apply(validate_image)
    df = df[df['is_image_valid'] == True]
    
    # 后处理，覆盖回原字段
    df['period'] = df['period_clean']
    df['type'] = df['type_clean']
    df.drop(columns=['period_clean', 'type_clean', 'is_image_valid'], inplace=True)
    
    final_count = len(df)
    
    # 保存结果
    out_path = os.path.join(CLEAN_DATA_DIR, f"clean_{filename}")
    df.to_csv(out_path, index=False, encoding='utf-8')
    
    print(f"[{filename}] Finished! Initial: {initial_count}, Dropped: {initial_count - final_count}, Cleaned: {final_count}")
    return final_count

def main():
    init_env()
    files_to_clean = ["chicago_museum.csv", "princeton_museum.csv", "brooklyn_museum.csv"]
    
    total_valid = 0
    for f in files_to_clean:
        count = clean_dataset(f)
        if count:
            total_valid += count
            
    print(f"\\nAll Cleaned. Total valid records ready for knowledge graph: {total_valid}")

if __name__ == "__main__":
    main()
