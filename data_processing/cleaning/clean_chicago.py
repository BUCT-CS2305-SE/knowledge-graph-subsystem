import pandas as pd
import re

from clean_princeton import (
    standardize_dynasty, standardize_type, 
    standardize_material, DYNASTY_MAPPING
)


def standardize_chicago_period(period_str):
    """标准化芝加哥艺术学院的时期表达"""
    if pd.isna(period_str) or period_str == '':
        return 'Unknown'
    
    period_str = str(period_str).strip()
    
    # 芝加哥艺术学院特定格式
    if 'Qing dynasty' in period_str:
        return 'Qing dynasty (1644-1912)'
    if 'Ming dynasty' in period_str or 'Ming' in period_str:
        return 'Ming dynasty (1368-1644)'
    if 'Yuan dynasty' in period_str:
        return 'Yuan dynasty (1271-1368)'
    if 'Song dynasty' in period_str:
        return 'Song dynasty (960-1279)'
    if 'Tang dynasty' in period_str:
        return 'Tang dynasty (618-907)'
    if 'Han dynasty' in period_str:
        return 'Han dynasty (206 BCE-220 CE)'
    if 'Shang dynasty' in period_str:
        return 'Shang dynasty (c. 1600-1046 BCE)'
    if 'Edo period' in period_str:
        return 'Edo period (1603-1868)'
    if 'Kamakura period' in period_str:
        return 'Kamakura period (1185-1333)'
    
    return standardize_dynasty(period_str)


def standardize_chicago_type(type_str):
    """标准化芝加哥文物类型"""
    if pd.isna(type_str) or type_str == '':
        return 'Unknown'
    
    type_str = str(type_str).strip()
    
    chicago_type_mapping = {
        'Hanging scroll': 'Hanging scroll',
        'Handscroll': 'Handscroll',
        'Album leaf': 'Album leaf',
        'Print': 'Print',
        'Photograph': 'Photograph',
        'Gelatin silver print': 'Gelatin silver print',
        'Chromogenic print': 'Chromogenic print',
        'Woodblock print': 'Woodblock print',
        'Etching': 'Etching',
        'Lithograph': 'Lithograph',
        'Drypoint': 'Drypoint',
        'Monotype': 'Monotype',
        'Painting': 'Painting',
        'Oil on canvas': 'Oil painting',
        'Watercolor': 'Watercolor',
        'Ceramic': 'Ceramic',
        'Porcelain': 'Porcelain',
        'Jade': 'Jade carving',
        'Bronze': 'Bronze',
        'Figure': 'Figure',
        'Vase': 'Vase',
        'Jar': 'Jar',
        'Bowl': 'Bowl',
        'Plate': 'Plate',
        'Sculpture': 'Sculpture',
        'Textile': 'Textile',
        'Costume': 'Costume',
    }
    
    for key, value in chicago_type_mapping.items():
        if key.lower() in type_str.lower():
            return value
    
    return standardize_type(type_str)


def extract_chicago_culture(row):
    """提取文化信息"""
    if pd.notna(row.get('_place_of_origin')) and row['_place_of_origin'] != '':
        origin = str(row['_place_of_origin'])
        if 'China' in origin:
            return 'Chinese'
        if 'Japan' in origin:
            return 'Japanese'
        if 'Korea' in origin:
            return 'Korean'
    
    if pd.notna(row.get('_style')) and row['_style'] != '':
        style = str(row['_style'])
        if 'Chinese' in style:
            return 'Chinese'
        if 'Japanese' in style:
            return 'Japanese'
    
    title = str(row.get('title', ''))
    if 'Chinese' in title:
        return 'Chinese'
    if 'Japanese' in title:
        return 'Japanese'
    
    return 'Unknown'


def clean_chicago(input_path, output_path):
    """清洗芝加哥艺术学院数据"""
    print(f"开始清洗芝加哥数据: {input_path}")
    
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
    df['museum'] = 'Art Institute of Chicago'
    df['location'] = 'Chicago, United States'
    
    # 标准化
    df['standardized_period'] = df['period'].apply(standardize_chicago_period)
    df['standardized_type'] = df['type'].apply(standardize_chicago_type)
    df['standardized_material'] = df['material'].apply(standardize_material)
    df['culture'] = df.apply(extract_chicago_culture, axis=1)
    
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
    input_file = '../chicago.csv'
    output_file = '../clean_chicago.csv'
    
    df, completeness = clean_chicago(input_file, output_file)