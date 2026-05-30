import pandas as pd

def clean_brooklyn_botanic(input_path, output_path):
    """清洗布鲁克林植物园数据"""
    print(f"开始清洗布鲁克林植物园数据: {input_path}")
    
    df = pd.read_csv(input_path)
    original_count = len(df)
    print(f"原始记录数: {original_count}")
    
    # 植物园数据是植物记录，不是文物
    # 这里主要做格式标准化
    
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
    df['museum'] = 'Brooklyn Botanic Garden'
    df['location'] = 'Brooklyn, New York, United States'
    
    # 植物园数据特殊处理
    df['standardized_type'] = 'Plant'
    df['standardized_material'] = 'Living plant'
    df['standardized_period'] = 'Living collection'
    df['culture'] = 'Botanical'
    
    # 从 _plant_name 和 _collection 构建标题（如果为空）
    for idx, row in df.iterrows():
        if pd.isna(row['title']) or row['title'] == '':
            plant = row.get('_plant_name', '')
            collection = row.get('_collection', '')
            if plant and collection:
                df.loc[idx, 'title'] = f"{plant} at {collection}"
            elif plant:
                df.loc[idx, 'title'] = plant
    
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
        score = 0.3  # 基础分
        if row.get('title') and row['title'] != '':
            score += 0.2
        if row.get('detail_url') and row['detail_url'] != '':
            score += 0.15
        if row.get('image_url') and row['image_url'] != '':
            score += 0.15
        if row.get('_image_valid') and row['_image_valid'] == 'True':
            score += 0.2
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
    input_file = '../brooklyn_botanic.csv'
    output_file = '../clean_brooklyn_botanic.csv'
    
    df, completeness = clean_brooklyn_botanic(input_file, output_file)