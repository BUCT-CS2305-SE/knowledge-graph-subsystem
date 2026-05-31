import pandas as pd
import re

from clean_princeton import (
    standardize_dynasty, standardize_type, standardize_material
)


def clean_guimet(input_path, output_path):
    """清洗吉美博物馆数据"""
    print(f"开始清洗吉美博物馆数据: {input_path}")
    
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
    df['museum'] = 'Musée Guimet'
    df['location'] = 'Paris, France'
    
    # 从 description 中提取材质信息
    for idx, row in df.iterrows():
        desc = str(row.get('description', ''))
        # 尝试从描述中提取材质
        if not row.get('material') or row['material'] == '':
            if 'ceramic' in desc.lower():
                df.loc[idx, 'material'] = 'Ceramic'
            elif 'jade' in desc.lower():
                df.loc[idx, 'material'] = 'Jade'
            elif 'bronze' in desc.lower():
                df.loc[idx, 'material'] = 'Bronze'
            elif 'silk' in desc.lower():
                df.loc[idx, 'material'] = 'Silk'
            elif 'wood' in desc.lower():
                df.loc[idx, 'material'] = 'Wood'
    
    # 从 title 或 period 提取朝代信息
    for idx, row in df.iterrows():
        title = str(row.get('title', ''))
        period_str = str(row.get('period', ''))
        
        if 'Tang' in title or 'Tang' in period_str:
            df.loc[idx, 'standardized_period'] = 'Tang dynasty (618-907)'
        elif 'Qing' in title or 'Qing' in period_str:
            df.loc[idx, 'standardized_period'] = 'Qing dynasty (1644-1912)'
        elif 'Yuan' in title or 'Yuan' in period_str:
            df.loc[idx, 'standardized_period'] = 'Yuan dynasty (1271-1368)'
        elif 'Ming' in title or 'Ming' in period_str:
            df.loc[idx, 'standardized_period'] = 'Ming dynasty (1368-1644)'
        else:
            df.loc[idx, 'standardized_period'] = standardize_dynasty(period_str)
    
    # 标准化类型和材质
    df['standardized_type'] = df['type'].apply(standardize_type)
    df['standardized_material'] = df['material'].apply(standardize_material)
    
    # 文化信息
    df['culture'] = 'Chinese'  # 吉美博物馆的中国收藏
    
    # 检查完整率
    completeness = {}
    for col in ['object_id', 'title', 'detail_url', 'image_url', 'crawl_date']:
        if col in df.columns:
            non_empty = df[col].notna() & (df[col] != '')
            completeness[col] = non_empty.sum() / len(df) * 100
    
    print(f"字段完整率: {completeness}")
    
    # 计算质量分数
    quality_scores = []
    for idx, row in df.iterrows():
        score = 0
        if row.get('title') and row['title'] != '':
            score += 0.2
        if row.get('detail_url') and row['detail_url'] != '':
            score += 0.15
        if row.get('image_url') and row['image_url'] != '':
            score += 0.15
        if row.get('_image_valid') and row['_image_valid'] == 'True':
            score += 0.1
        if row.get('standardized_period') and row['standardized_period'] != 'Unknown':
            score += 0.1
        if row.get('standardized_type') and row['standardized_type'] != 'Unknown':
            score += 0.15
        if row.get('standardized_material') and row['standardized_material'] != 'Unknown':
            score += 0.15
        quality_scores.append(score)
    
    df['data_quality_score'] = quality_scores
    
    # 检测重复
    dup_mask = df.duplicated(subset=['title'], keep=False)
    df['is_duplicate'] = dup_mask
    
    # 重新排列列
    df = df[required_columns + [c for c in df.columns if c not in required_columns]]
    
    df.to_csv(output_path, index=False)
    print(f"清洗后的数据已保存到: {output_path}")
    
    return df, completeness


if __name__ == "__main__":
    input_file = '../guimet_museum.csv'
    output_file = '../clean_guimet.csv'
    
    df, completeness = clean_guimet(input_file, output_file)