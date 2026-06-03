import pandas as pd
import re

from clean_princeton import (
    standardize_dynasty, standardize_type, standardize_material
)


def clean_british_museum(input_path, output_path):
    """清洗大英博物馆数据"""
    print(f"开始清洗大英博物馆数据: {input_path}")
    
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
    df['museum'] = 'British Museum'
    df['location'] = 'London, United Kingdom'
    
    # 从 _culture 或 _findspot 提取文化信息
    df['culture'] = 'Unknown'
    for idx, row in df.iterrows():
        culture = str(row.get('_culture', ''))
        findspot = str(row.get('_findspot', ''))
        
        if 'Chinese' in culture or 'Chinese' in findspot:
            df.loc[idx, 'culture'] = 'Chinese'
        elif 'Japanese' in culture or 'Japanese' in findspot:
            df.loc[idx, 'culture'] = 'Japanese'
        elif 'Tibet' in findspot:
            df.loc[idx, 'culture'] = 'Tibetan'
        elif 'Egypt' in findspot:
            df.loc[idx, 'culture'] = 'Egyptian'
    
    # 标准化时期
    df['standardized_period'] = df['period'].apply(standardize_dynasty)
    
    # 从 object_name_detail 提取类型
    for idx, row in df.iterrows():
        obj_name = str(row.get('_object_name_detail', ''))
        if obj_name and obj_name != '':
            df.loc[idx, 'standardized_type'] = standardize_type(obj_name)
        else:
            df.loc[idx, 'standardized_type'] = standardize_type(row.get('type', ''))
    
    # 标准化材质
    df['standardized_material'] = df['material'].apply(standardize_material)
    
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
        if row.get('object_id') and row['object_id'] != '':
            score += 0.15
        if row.get('title') and row['title'] != '':
            score += 0.15
        if row.get('detail_url') and row['detail_url'] != '':
            score += 0.10
        if row.get('image_url') and row['image_url'] != '':
            score += 0.10
        if row.get('_image_valid') and row['_image_valid'] == 'True':
            score += 0.10
        if row.get('standardized_period') and row['standardized_period'] != 'Unknown':
            score += 0.10
        if row.get('standardized_type') and row['standardized_type'] != 'Unknown':
            score += 0.15
        if row.get('standardized_material') and row['standardized_material'] != 'Unknown':
            score += 0.15
        quality_scores.append(score)
    
    df['data_quality_score'] = quality_scores
    
    # 检测重复
    dup_mask = df.duplicated(subset=['object_id'], keep=False)
    df['is_duplicate'] = dup_mask
    
    # 重新排列列
    df = df[required_columns + [c for c in df.columns if c not in required_columns]]
    
    df.to_csv(output_path, index=False)
    print(f"清洗后的数据已保存到: {output_path}")
    
    return df, completeness


if __name__ == "__main__":
    input_file = '../british_museum.csv'
    output_file = '../clean_british_museum.csv'
    
    df, completeness = clean_british_museum(input_file, output_file)