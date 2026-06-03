import pandas as pd
import re

# 复用 Princeton 中的标准化函数
from clean_princeton import (
    standardize_dynasty, standardize_type, 
    standardize_material, DYNASTY_MAPPING, 
    TYPE_MAPPING, MATERIAL_MAPPING
)


def standardize_met_period(period_str):
    """标准化 MET 博物馆的时期表达"""
    if pd.isna(period_str) or period_str == '':
        return 'Unknown'
    
    period_str = str(period_str).strip()
    
    # 特殊处理 MET 的格式
    if 'Qing dynasty' in period_str or 'Qing' in period_str:
        return 'Qing dynasty (1644-1912)'
    if 'Ming dynasty' in period_str or 'Ming' in period_str:
        return 'Ming dynasty (1368-1644)'
    if 'Yuan dynasty' in period_str or 'Yuan' in period_str:
        return 'Yuan dynasty (1271-1368)'
    if 'Song dynasty' in period_str or 'Song' in period_str:
        return 'Song dynasty (960-1279)'
    if 'Tang dynasty' in period_str or 'Tang' in period_str:
        return 'Tang dynasty (618-907)'
    if 'Han dynasty' in period_str or 'Han' in period_str:
        return 'Han dynasty (206 BCE-220 CE)'
    if 'Edo period' in period_str:
        return 'Edo period (1603-1868)'
    if 'Kamakura period' in period_str:
        return 'Kamakura period (1185-1333)'
    if 'Meiji period' in period_str or 'Meiji era' in period_str:
        return 'Meiji period (1868-1912)'
    
    return standardize_dynasty(period_str)


def standardize_met_type(type_str):
    """标准化 MET 文物类型"""
    if pd.isna(type_str) or type_str == '':
        return 'Unknown'
    
    type_str = str(type_str).strip()
    
    # MET 特定类型映射
    met_type_mapping = {
        'Handscroll': 'Handscroll',
        'Hanging scroll': 'Hanging scroll',
        'Figure': 'Figure',
        'Bust': 'Bust',
        'Painting': 'Painting',
        'Print': 'Print',
        'Photograph': 'Photograph',
        'Ceramic': 'Ceramic',
        'Porcelain': 'Porcelain',
        'Jade': 'Jade carving',
        'Bronze': 'Bronze',
        'Ivory': 'Ivory carving',
        'Lacquer': 'Lacquerware',
        'Textile': 'Textile',
        'Period room': 'Period room',
        'Tabernacle polyptych': 'Tabernacle polyptych',
        'Reliquary': 'Reliquary',
        'Cross': 'Cross',
        'Plate': 'Plate',
        'Bowl': 'Bowl',
        'Cup': 'Cup',
        'Vase': 'Vase',
        'Jar': 'Jar',
        'Dish': 'Dish',
        'Figure': 'Figure',
    }
    
    for key, value in met_type_mapping.items():
        if key.lower() in type_str.lower():
            return value
    
    return standardize_type(type_str)


def extract_met_culture(row):
    """提取 MET 文化信息"""
    if pd.notna(row.get('_culture')) and row['_culture'] != '':
        return str(row['_culture'])
    
    title = str(row.get('title', ''))
    artist = str(row.get('artist', ''))
    artist_nationality = str(row.get('_artist_nationality', ''))
    
    if 'Chinese' in artist_nationality or 'Chinese' in artist:
        return 'Chinese'
    if 'Japanese' in artist_nationality or 'Japanese' in artist:
        return 'Japanese'
    if 'Korean' in artist_nationality:
        return 'Korean'
    if 'French' in artist_nationality:
        return 'French'
    if 'Italian' in artist_nationality:
        return 'Italian'
    if 'German' in artist_nationality:
        return 'German'
    if 'British' in artist_nationality or 'English' in artist_nationality:
        return 'British'
    if 'American' in artist_nationality:
        return 'American'
    if 'Egyptian' in title:
        return 'Egyptian'
    if 'Greek' in title:
        return 'Greek'
    if 'Roman' in title:
        return 'Roman'
    
    return 'Unknown'


def clean_met(input_path, output_path):
    """清洗 MET 博物馆数据"""
    print(f"开始清洗 MET 数据: {input_path}")
    
    df = pd.read_csv(input_path)
    original_count = len(df)
    print(f"原始记录数: {original_count}")
    
    required_columns = [
        'object_id', 'title', 'period', 'type', 'material',
        'description', 'dimensions', 'museum', 'location',
        'detail_url', 'image_url', 'image_path',
        'credit_line', 'accession_number', 'crawl_date',
        'standardized_period', 'standardized_type', 'standardized_material',
        'culture', 'data_quality_score'
    ]
    
    for col in required_columns:
        if col not in df.columns:
            df[col] = ''
    
    # 设置博物馆信息
    df['museum'] = 'The Metropolitan Museum of Art'
    df['location'] = 'New York, United States'
    
    # 标准化
    df['standardized_period'] = df['period'].apply(standardize_met_period)
    df['standardized_type'] = df['type'].apply(standardize_met_type)
    df['standardized_material'] = df['material'].apply(standardize_material)
    df['culture'] = df.apply(extract_met_culture, axis=1)
    
    # 检查完整率
    completeness = {}
    for col in ['object_id', 'title', 'detail_url', 'image_url', 'crawl_date']:
        if col in df.columns:
            non_empty = df[col].notna() & (df[col] != '')
            completeness[col] = non_empty.sum() / len(df) * 100
    
    print(f"字段完整率: {completeness}")
    
    # 计算质量分数
    quality_weights = {
        'object_id': 0.15,
        'title': 0.15,
        'period': 0.10,
        'type': 0.10,
        'material': 0.10,
        'description': 0.10,
        'dimensions': 0.05,
        'detail_url': 0.05,
        'image_url': 0.10,
        '_image_valid': 0.10,
    }
    
    quality_scores = []
    for idx, row in df.iterrows():
        score = 0
        for col, weight in quality_weights.items():
            val = row.get(col, '')
            if col == '_image_valid':
                if row.get('_image_valid', False):
                    score += weight
            elif pd.notna(val) and val != '':
                score += weight
        quality_scores.append(score)
    
    df['data_quality_score'] = quality_scores
    
    # 检测重复
    dup_mask = df.duplicated(subset=['title', 'accession_number'], keep=False)
    df['is_duplicate'] = dup_mask
    
    # 重新排列列
    df = df[required_columns + [c for c in df.columns if c not in required_columns]]
    
    df.to_csv(output_path, index=False)
    print(f"清洗后的数据已保存到: {output_path}")
    
    return df, completeness


if __name__ == "__main__":
    input_file = '../met_museum.csv'
    output_file = '../clean_met.csv'
    
    df, completeness = clean_met(input_file, output_file)