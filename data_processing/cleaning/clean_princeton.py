import pandas as pd
import numpy as np
import re
import os
from datetime import datetime
import json

# 朝代标准化映射
DYNASTY_MAPPING = {
    # 清代
    'Qing': 'Qing dynasty (1644-1912)',
    'Qing dynasty': 'Qing dynasty (1644-1912)',
    'Qing dynasty, 1644–1911': 'Qing dynasty (1644-1912)',
    'Qing dynasty (1644–1911)': 'Qing dynasty (1644-1912)',
    'late Qing dynasty': 'Qing dynasty (1644-1912)',
    
    # 明代
    'Ming': 'Ming dynasty (1368-1644)',
    'Ming dynasty': 'Ming dynasty (1368-1644)',
    'Ming dynasty (1368–1644)': 'Ming dynasty (1368-1644)',
    
    # 元代
    'Yuan': 'Yuan dynasty (1271-1368)',
    'Yuan dynasty': 'Yuan dynasty (1271-1368)',
    
    # 宋代
    'Song': 'Song dynasty (960-1279)',
    'Song dynasty': 'Song dynasty (960-1279)',
    'Northern Song': 'Northern Song dynasty (960-1127)',
    'Southern Song': 'Southern Song dynasty (1127-1279)',
    
    # 唐代
    'Tang': 'Tang dynasty (618-907)',
    'Tang dynasty': 'Tang dynasty (618-907)',
    
    # 汉代
    'Han': 'Han dynasty (206 BCE-220 CE)',
    'Western Han': 'Western Han dynasty (206 BCE-9 CE)',
    'Eastern Han': 'Eastern Han dynasty (25-220 CE)',
    
    # 其他朝代
    'Ming or Qing': 'Ming or Qing dynasty',
    'Ming/Qing': 'Ming or Qing dynasty',
    'Shang': 'Shang dynasty (c. 1600-1046 BCE)',
    'Western Zhou': 'Western Zhou dynasty (1046-771 BCE)',
    'Eastern Zhou': 'Eastern Zhou dynasty (770-256 BCE)',
    'Warring States': 'Warring States period (475-221 BCE)',
    'Spring and Autumn': 'Spring and Autumn period (770-476 BCE)',
    'Northern Wei': 'Northern Wei dynasty (386-534)',
    'Sui': 'Sui dynasty (581-618)',
    'Five Dynasties': 'Five Dynasties period (907-960)',
    'Liao': 'Liao dynasty (907-1125)',
    'Jin': 'Jin dynasty (1115-1234)',
    'Yuan or Ming': 'Yuan or Ming dynasty',
    'Yuan/Ming': 'Yuan or Ming dynasty',
    
    # 日本时期
    'Edo': 'Edo period (1603-1868)',
    'Edo period': 'Edo period (1603-1868)',
    'Kamakura': 'Kamakura period (1185-1333)',
    'Muromachi': 'Muromachi period (1336-1573)',
    'Meiji': 'Meiji period (1868-1912)',
    'Shōwa': 'Shōwa period (1926-1989)',
    
    # 罗马时期
    'Roman Imperial': 'Roman Imperial period (27 BCE-476 CE)',
    'Roman': 'Roman period',
    
    # 希腊时期
    'Greek': 'Greek period',
    'Archaic Period': 'Archaic Greek period (c. 800-480 BCE)',
    'Classical Period': 'Classical Greek period (480-323 BCE)',
    'Hellenistic': 'Hellenistic period (323-31 BCE)',
    
    # 其他
    'Neolithic': 'Neolithic period',
    'Bronze Age': 'Bronze Age',
}

# 文物类型标准化映射
TYPE_MAPPING = {
    # 绘画类
    'painting': 'Painting',
    'drawing': 'Drawing',
    'watercolor': 'Watercolor',
    'oil painting': 'Oil painting',
    'handscroll': 'Handscroll',
    'hanging scroll': 'Hanging scroll',
    'scroll': 'Scroll',
    'print': 'Print',
    'woodblock print': 'Woodblock print',
    'lithograph': 'Lithograph',
    'etching': 'Etching',
    'engraving': 'Engraving',
    'woodcut': 'Woodcut',
    'screenprint': 'Screenprint',
    'monotype': 'Monotype',
    
    # 陶瓷类
    'ceramic': 'Ceramic',
    'porcelain': 'Porcelain',
    'pottery': 'Pottery',
    'stoneware': 'Stoneware',
    'earthenware': 'Earthenware',
    'celadon': 'Celadon',
    'qingbai': 'Qingbai ware',
    
    # 雕塑类
    'sculpture': 'Sculpture',
    'figure': 'Figure',
    'statuette': 'Statuette',
    'bust': 'Bust',
    'relief': 'Relief',
    'stela': 'Stela',
    
    # 摄影类
    'photograph': 'Photograph',
    'gelatin silver print': 'Gelatin silver print',
    'albumen print': 'Albumen print',
    'platinum print': 'Platinum print',
    'cyanotype': 'Cyanotype',
    'chromogenic print': 'Chromogenic print',
    'inkjet print': 'Inkjet print',
    
    # 器物类
    'vessel': 'Vessel',
    'jar': 'Jar',
    'bowl': 'Bowl',
    'cup': 'Cup',
    'plate': 'Plate',
    'dish': 'Dish',
    'vase': 'Vase',
    'bottle': 'Bottle',
    'ewer': 'Ewer',
    'amphora': 'Amphora',
    'kylix': 'Kylix',
    'pyxis': 'Pyxis',
    
    # 纺织品
    'textile': 'Textile',
    'robe': 'Robe',
    'garment': 'Garment',
    
    # 媒体艺术
    'video': 'Video',
    'digital video': 'Digital video',
    'film': 'Film',
    'media': 'Media art',
    
    # 其他
    'jade': 'Jade carving',
    'bronze': 'Bronze',
    'ivory': 'Ivory carving',
    'lacquer': 'Lacquerware',
    'mask': 'Mask',
}

# 材质标准化映射
MATERIAL_MAPPING = {
    'ceramic': 'Ceramic',
    'porcelain': 'Porcelain',
    'stoneware': 'Stoneware',
    'earthenware': 'Earthenware',
    'pottery': 'Pottery',
    'clay': 'Clay',
    'terracotta': 'Terracotta',
    
    'wood': 'Wood',
    'jade': 'Jade',
    'jadeite': 'Jadeite',
    'nephrite': 'Nephrite',
    'bronze': 'Bronze',
    'copper': 'Copper',
    'gold': 'Gold',
    'silver': 'Silver',
    'brass': 'Brass',
    'iron': 'Iron',
    'stone': 'Stone',
    'marble': 'Marble',
    'limestone': 'Limestone',
    'granite': 'Granite',
    
    'silk': 'Silk',
    'cotton': 'Cotton',
    'linen': 'Linen',
    'wool': 'Wool',
    'textile': 'Textile',
    
    'oil on canvas': 'Oil on canvas',
    'oil on panel': 'Oil on panel',
    'oil on wood': 'Oil on wood',
    'ink on paper': 'Ink on paper',
    'watercolor': 'Watercolor',
    'gouache': 'Gouache',
    'pastel': 'Pastel',
    'tempera': 'Tempera',
    'fresco': 'Fresco',
    
    'glass': 'Glass',
    'ivory': 'Ivory',
    'bone': 'Bone',
    'shell': 'Shell',
    'bead': 'Bead',
    
    'photographic paper': 'Photographic paper',
    'gelatin silver': 'Gelatin silver',
    'albumen': 'Albumen',
}


def standardize_dynasty(dynasty_str):
    """标准化朝代/时期表达"""
    if pd.isna(dynasty_str) or dynasty_str == '':
        return 'Unknown'
    
    dynasty_str = str(dynasty_str).strip()
    
    # 直接映射
    for key, value in DYNASTY_MAPPING.items():
        if key.lower() in dynasty_str.lower():
            return value
    
    # 处理年份范围
    year_match = re.search(r'(\d{3,4})\s*[–\-]\s*(\d{3,4})', dynasty_str)
    if year_match:
        start = int(year_match.group(1))
        end = int(year_match.group(2))
        if start > 1000 and end > 1000:
            if start >= 1644:
                return f'Qing dynasty ({start}-{end})'
            elif start >= 1368:
                return f'Ming dynasty ({start}-{end})'
            elif start >= 1271:
                return f'Yuan dynasty ({start}-{end})'
            elif start >= 960:
                return f'Song dynasty ({start}-{end})'
            elif start >= 618:
                return f'Tang dynasty ({start}-{end})'
    
    # 提取公元年份
    ce_match = re.search(r'(\d{3,4})\s*CE', dynasty_str)
    if ce_match:
        return f'c. {ce_match.group(1)} CE'
    
    bce_match = re.search(r'(\d{3,4})\s*BCE', dynasty_str)
    if bce_match:
        return f'c. {bce_match.group(1)} BCE'
    
    return dynasty_str[:100] if len(dynasty_str) > 100 else dynasty_str


def standardize_type(type_str):
    """标准化文物类型"""
    if pd.isna(type_str) or type_str == '':
        return 'Unknown'
    
    type_str = str(type_str).strip()
    
    for key, value in TYPE_MAPPING.items():
        if key.lower() in type_str.lower():
            return value
    
    # 处理特殊格式
    if 'hanging scroll' in type_str.lower():
        return 'Hanging scroll'
    if 'handscroll' in type_str.lower():
        return 'Handscroll'
    if 'print' in type_str.lower():
        return 'Print'
    
    return type_str[:100] if len(type_str) > 100 else type_str


def standardize_material(material_str):
    """标准化材质"""
    if pd.isna(material_str) or material_str == '':
        return 'Unknown'
    
    material_str = str(material_str).strip()
    
    # 按长度排序，优先匹配长关键词
    sorted_keys = sorted(MATERIAL_MAPPING.keys(), key=len, reverse=True)
    
    for key in sorted_keys:
        if key.lower() in material_str.lower():
            return MATERIAL_MAPPING[key]
    
    return material_str[:100] if len(material_str) > 100 else material_str


def extract_culture(row):
    """提取文化信息"""
    # 优先使用 _displayculture 列
    if pd.notna(row.get('_displayculture')) and row['_displayculture'] != '':
        return str(row['_displayculture'])
    
    # 从 title 或 description 中提取
    title = str(row.get('title', ''))
    desc = str(row.get('description', ''))
    
    cultures = ['Chinese', 'Japanese', 'Korean', 'Greek', 'Roman', 
                'Egyptian', 'Indian', 'Persian', 'Maya', 'Inca']
    
    for culture in cultures:
        if culture.lower() in title.lower() or culture.lower() in desc.lower():
            return culture
    
    return 'Unknown'


def clean_princeton(input_path, output_path):
    """清洗 Princeton 博物馆数据"""
    print(f"开始清洗 Princeton 数据: {input_path}")
    
    # 读取数据
    df = pd.read_csv(input_path)
    
    # 记录原始行数
    original_count = len(df)
    print(f"原始记录数: {original_count}")
    
    # 1. 补齐缺失列，保持字段顺序一致
    required_columns = [
        'object_id', 'title', 'period', 'type', 'material', 
        'description', 'dimensions', 'museum', 'location', 
        'detail_url', 'image_url', 'image_path', 
        'credit_line', 'accession_number', 'crawl_date',
        'standardized_period', 'standardized_type', 'standardized_material',
        'culture', 'data_quality_score'
    ]
    
    # 确保所有列存在
    for col in required_columns:
        if col not in df.columns:
            df[col] = ''
    
    # 2. 标准化年代表达
    df['standardized_period'] = df['period'].apply(standardize_dynasty)
    
    # 对于空白的 period，尝试从其他字段提取
    mask = (df['standardized_period'] == 'Unknown') & (df['period'].isna())
    for idx in df[mask].index:
        title = str(df.loc[idx, 'title'])
        desc = str(df.loc[idx, 'description'])
        if 'Qing' in title or 'Qing' in desc:
            df.loc[idx, 'standardized_period'] = 'Qing dynasty (1644-1912)'
        elif 'Ming' in title or 'Ming' in desc:
            df.loc[idx, 'standardized_period'] = 'Ming dynasty (1368-1644)'
        elif 'Tang' in title or 'Tang' in desc:
            df.loc[idx, 'standardized_period'] = 'Tang dynasty (618-907)'
        elif 'Song' in title or 'Song' in desc:
            df.loc[idx, 'standardized_period'] = 'Song dynasty (960-1279)'
    
    # 3. 标准化文物类型
    df['standardized_type'] = df['type'].apply(standardize_type)
    
    # 4. 标准化材质
    df['standardized_material'] = df['material'].apply(standardize_material)
    
    # 5. 提取文化信息
    df['culture'] = df.apply(extract_culture, axis=1)
    
    # 6. 检查完整率
    completeness = {}
    for col in ['object_id', 'title', 'detail_url', 'image_url', 'crawl_date']:
        if col in df.columns:
            non_empty = df[col].notna() & (df[col] != '')
            completeness[col] = non_empty.sum() / len(df) * 100
    
    print(f"字段完整率: {completeness}")
    
    # 7. 校验图片
    df['image_valid'] = False
    for idx, row in df.iterrows():
        img_path = row.get('image_path', '')
        if pd.notna(img_path) and img_path != '':
            # 检查是否为完整路径
            if img_path.startswith('/') or img_path.startswith('http'):
                df.loc[idx, 'image_valid'] = True
            else:
                # 构建完整路径检查（这里简化处理）
                full_path = os.path.join(os.path.dirname(input_path), '..', 'images', img_path)
                if os.path.exists(full_path):
                    file_size = os.path.getsize(full_path)
                    df.loc[idx, 'image_valid'] = file_size > 1000
    
    # 8. 计算数据质量分数
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
        'image_valid': 0.10,
    }
    
    quality_scores = []
    for idx, row in df.iterrows():
        score = 0
        for col, weight in quality_weights.items():
            if col == 'image_valid':
                if row.get('image_valid', False):
                    score += weight
            else:
                val = row.get(col, '')
                if pd.notna(val) and val != '':
                    score += weight
        quality_scores.append(score)
    
    df['data_quality_score'] = quality_scores
    
    # 9. 识别重复记录
    dup_mask = df.duplicated(subset=['title', 'accession_number'], keep=False)
    duplicate_records = df[dup_mask].copy()
    print(f"发现的重复记录数: {len(duplicate_records)}")
    
    # 标记重复
    df['is_duplicate'] = dup_mask
    
    # 10. 重新排列列顺序
    df = df[required_columns + [c for c in df.columns if c not in required_columns]]
    
    # 11. 保存清洗后的数据
    df.to_csv(output_path, index=False)
    print(f"清洗后的数据已保存到: {output_path}")
    
    return df, completeness, duplicate_records


def generate_quality_report(all_results, output_path):
    """生成质量报告"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'datasets': {},
        'summary': {
            'total_records': 0,
            'avg_quality_score': 0,
            'total_duplicates': 0
        }
    }
    
    total_records = 0
    total_score = 0
    total_duplicates = 0
    
    for dataset_name, result in all_results.items():
        df = result['df']
        completeness = result['completeness']
        duplicates = result['duplicates']
        
        dataset_report = {
            'record_count': len(df),
            'completeness': completeness,
            'duplicate_count': len(duplicates),
            'avg_quality_score': df['data_quality_score'].mean(),
            'period_distribution': df['standardized_period'].value_counts().head(10).to_dict(),
            'type_distribution': df['standardized_type'].value_counts().head(10).to_dict(),
            'material_distribution': df['standardized_material'].value_counts().head(10).to_dict(),
            'culture_distribution': df['culture'].value_counts().head(10).to_dict()
        }
        
        report['datasets'][dataset_name] = dataset_report
        
        total_records += len(df)
        total_score += df['data_quality_score'].sum()
        total_duplicates += len(duplicates)
    
    if total_records > 0:
        report['summary']['total_records'] = total_records
        report['summary']['avg_quality_score'] = total_score / total_records
        report['summary']['total_duplicates'] = total_duplicates
    
    # 保存 JSON 报告
    json_path = output_path.replace('.md', '.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 生成 Markdown 报告
    md_content = generate_markdown_report(report)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"质量报告已保存到: {output_path} 和 {json_path}")
    
    return report


def generate_markdown_report(report):
    """生成 Markdown 格式的质量报告"""
    md = "# Data Quality Report\n\n"
    md += f"**Report Generated:** {report['timestamp']}\n\n"
    
    md += "## Summary\n\n"
    md += f"- **Total Records Across All Datasets:** {report['summary']['total_records']}\n"
    md += f"- **Average Quality Score:** {report['summary']['avg_quality_score']:.2%}\n"
    md += f"- **Total Duplicates Found:** {report['summary']['total_duplicates']}\n\n"
    
    for dataset_name, dataset_report in report['datasets'].items():
        md += f"## Dataset: {dataset_name}\n\n"
        md += f"### Basic Statistics\n"
        md += f"- Records: {dataset_report['record_count']}\n"
        md += f"- Average Quality Score: {dataset_report['avg_quality_score']:.2%}\n"
        md += f"- Duplicates Found: {dataset_report['duplicate_count']}\n\n"
        
        md += "### Field Completeness\n"
        md += "| Field | Completeness |\n"
        md += "|-------|--------------|\n"
        for field, completeness in dataset_report['completeness'].items():
            md += f"| {field} | {completeness:.1f}% |\n"
        md += "\n"
        
        md += "### Top Periods (Standardized)\n"
        md += "| Period | Count |\n"
        md += "|--------|-------|\n"
        for period, count in list(dataset_report['period_distribution'].items())[:10]:
            md += f"| {period} | {count} |\n"
        md += "\n"
        
        md += "### Top Types (Standardized)\n"
        md += "| Type | Count |\n"
        md += "|------|-------|\n"
        for type_name, count in list(dataset_report['type_distribution'].items())[:10]:
            md += f"| {type_name} | {count} |\n"
        md += "\n"
        
        md += "### Top Materials (Standardized)\n"
        md += "| Material | Count |\n"
        md += "|----------|-------|\n"
        for material, count in list(dataset_report['material_distribution'].items())[:10]:
            md += f"| {material} | {count} |\n"
        md += "\n"
        
        md += "### Cultures\n"
        md += "| Culture | Count |\n"
        md += "|---------|-------|\n"
        for culture, count in list(dataset_report['culture_distribution'].items())[:10]:
            md += f"| {culture} | {count} |\n"
        md += "\n"
        md += "---\n\n"
    
    return md


if __name__ == "__main__":
    # 处理 Princeton 数据
    input_file = '../princeton.csv'
    output_file = '../clean_princeton.csv'
    
    df, completeness, duplicates = clean_princeton(input_file, output_file)
    
    # 生成报告
    all_results = {
        'princeton': {
            'df': df,
            'completeness': completeness,
            'duplicates': duplicates
        }
    }
    
    generate_quality_report(all_results, '../../data_quality_report.md')