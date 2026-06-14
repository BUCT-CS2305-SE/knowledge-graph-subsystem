"""
实体对齐模块
对朝代、博物馆、类型、材质、艺术家、地点进行标准化对齐，
并为每个实体生成唯一标识符 URI（满足跨数据源去重与可追溯要求）。
"""

import pandas as pd
import json
import os
import re


# 知识图谱 URI 命名空间（用于实体唯一标识，避免图中重复节点）
URI_BASE = "http://buct-kg.org/resource"

# 视为"无效/未知"的取值，提取艺术家、地点时跳过
_INVALID_VALUES = {
    '', 'unknown', 'none', 'nan', 'n/a', 'na', 'null',
    'unidentified', 'not applicable',
}


def make_uri(kind: str, name) -> str:
    """根据实体类别与名称生成稳定 URI。

    同名实体在所有数据源中会映射到同一 URI，从而实现跨源去重。
    """
    if pd.isna(name) or str(name).strip() == '':
        return ''
    slug = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]+', '_', str(name).strip()).strip('_')
    if not slug:
        return ''
    return f"{URI_BASE}/{kind}/{slug}"


def _is_invalid(value) -> bool:
    if pd.isna(value):
        return True
    s = str(value).strip()
    if s.lower() in _INVALID_VALUES:
        return True
    # "Artist unknown ..."、"Maker unidentified" 等
    if re.search(r'unknown|unidentified|佚名|不详|无款', s, re.IGNORECASE):
        return True
    return False


class ArtistEntityAligner:
    """艺术家实体对齐器：从各馆不同列名中提取并清洗艺术家名。"""

    # 候选列（按优先级），覆盖 met / chicago 等不同字段命名
    CANDIDATE_COLUMNS = [
        '_artist', 'artist', '_artist_name', '_maker', '_attribution',
    ]

    @classmethod
    def extract(cls, row) -> str:
        for col in cls.CANDIDATE_COLUMNS:
            v = row.get(col) if hasattr(row, 'get') else None
            if v is not None and not _is_invalid(v):
                # 仅取首行（部分馆把生平塞在同一字段，用换行分隔）
                name = str(v).strip().splitlines()[0].strip()
                if name and not _is_invalid(name):
                    return name[:200]
        return ''


class LocationEntityAligner:
    """地点实体对齐器：提取文物产地/来源地。"""

    # 候选列（按优先级）：产地 > 国家/地区 > 文化
    CANDIDATE_COLUMNS = [
        '_place_of_origin', '_country', '_region',
        '_displayculture', '_culture', 'culture',
    ]

    @classmethod
    def extract(cls, row) -> str:
        for col in cls.CANDIDATE_COLUMNS:
            v = row.get(col) if hasattr(row, 'get') else None
            if v is not None and not _is_invalid(v):
                name = str(v).strip().splitlines()[0].strip()
                if name and not _is_invalid(name):
                    return name[:150]
        return ''


class MuseumEntityAligner:
    """博物馆实体对齐器"""
    
    # 博物馆标准名称映射
    MUSEUM_MAPPING = {
        'Princeton University Art Museum': 'Princeton University Art Museum',
        'princeton': 'Princeton University Art Museum',
        'Princeton': 'Princeton University Art Museum',
        'Metropolitan Museum of Art': 'Metropolitan Museum of Art',
        'the metropolitan museum of art': 'Metropolitan Museum of Art',
        'MET': 'Metropolitan Museum of Art',
        'met': 'Metropolitan Museum of Art',
        'Art Institute of Chicago': 'Art Institute of Chicago',
        'art institute of chicago': 'Art Institute of Chicago',
        'Chicago': 'Art Institute of Chicago',
        'Brooklyn Museum': 'Brooklyn Museum',
        'brooklyn museum': 'Brooklyn Museum',
        'Brooklyn Botanic Garden': 'Brooklyn Botanic Garden',
        'brooklyn botanic garden': 'Brooklyn Botanic Garden',
        'Musée Guimet': 'Musée Guimet',
        'guimet': 'Musée Guimet',
        'British Museum': 'British Museum',
        'british museum': 'British Museum',
    }
    
    # 博物馆位置映射
    MUSEUM_LOCATION = {
        'Princeton University Art Museum': 'Princeton, United States',
        'Metropolitan Museum of Art': 'New York, United States',
        'Art Institute of Chicago': 'Chicago, United States',
        'Brooklyn Museum': 'Brooklyn, New York, United States',
        'Brooklyn Botanic Garden': 'Brooklyn, New York, United States',
        'Musée Guimet': 'Paris, France',
        'British Museum': 'London, United Kingdom',
    }
    
    @classmethod
    def align(cls, museum_name):
        """对齐博物馆名称"""
        if pd.isna(museum_name) or museum_name == '':
            return 'Unknown'
        
        museum_str = str(museum_name).strip()
        for key, value in cls.MUSEUM_MAPPING.items():
            if key.lower() in museum_str.lower():
                return value
        
        return museum_str[:100] if len(museum_str) > 100 else museum_str
    
    @classmethod
    def get_location(cls, museum_name):
        """获取博物馆位置"""
        aligned = cls.align(museum_name)
        return cls.MUSEUM_LOCATION.get(aligned, 'Unknown')


class PeriodEntityAligner:
    """朝代/时期实体对齐器"""
    
    # 标准时期分级
    PERIOD_HIERARCHY = {
        # 中国朝代
        'Qing dynasty (1644-1912)': {'level': 1, 'era': 'Imperial China'},
        'Ming dynasty (1368-1644)': {'level': 1, 'era': 'Imperial China'},
        'Yuan dynasty (1271-1368)': {'level': 1, 'era': 'Imperial China'},
        'Song dynasty (960-1279)': {'level': 1, 'era': 'Imperial China'},
        'Tang dynasty (618-907)': {'level': 1, 'era': 'Imperial China'},
        'Han dynasty (206 BCE-220 CE)': {'level': 1, 'era': 'Imperial China'},
        'Shang dynasty (c. 1600-1046 BCE)': {'level': 1, 'era': 'Ancient China'},
        'Zhou dynasty (1046-256 BCE)': {'level': 1, 'era': 'Ancient China'},
        
        # 日本时期
        'Edo period (1603-1868)': {'level': 1, 'era': 'Early Modern Japan'},
        'Kamakura period (1185-1333)': {'level': 1, 'era': 'Medieval Japan'},
        'Meiji period (1868-1912)': {'level': 1, 'era': 'Modern Japan'},
        
        # 西方时期
        'Roman Imperial period (27 BCE-476 CE)': {'level': 1, 'era': 'Roman Empire'},
        'Greek period': {'level': 1, 'era': 'Ancient Greece'},
        'Hellenistic period (323-31 BCE)': {'level': 1, 'era': 'Hellenistic'},
        
        # 现代
        'Modern period': {'level': 1, 'era': 'Modern'},
    }
    
    # 时期别名映射
    PERIOD_ALIASES = {
        'Qing': 'Qing dynasty (1644-1912)',
        'Ming': 'Ming dynasty (1368-1644)',
        'Yuan': 'Yuan dynasty (1271-1368)',
        'Song': 'Song dynasty (960-1279)',
        'Tang': 'Tang dynasty (618-907)',
        'Han': 'Han dynasty (206 BCE-220 CE)',
        'Shang': 'Shang dynasty (c. 1600-1046 BCE)',
        'Edo': 'Edo period (1603-1868)',
        'Kamakura': 'Kamakura period (1185-1333)',
        'Meiji': 'Meiji period (1868-1912)',
    }
    
    @classmethod
    def align(cls, period_str):
        """对齐时期名称"""
        if pd.isna(period_str) or period_str == '':
            return 'Unknown'
        
        period_str = str(period_str).strip()
        
        # 检查别名
        for alias, standard in cls.PERIOD_ALIASES.items():
            if alias in period_str:
                return standard
        
        # 检查标准名称
        for standard in cls.PERIOD_HIERARCHY.keys():
            if standard.lower() in period_str.lower():
                return standard
        
        # 尝试提取年份
        import re
        year_match = re.search(r'(\d{3,4})', period_str)
        if year_match:
            year = int(year_match.group(1))
            if year >= 1644:
                return f'Qing dynasty (c. {year})'
            elif year >= 1368:
                return f'Ming dynasty (c. {year})'
            elif year >= 1271:
                return f'Yuan dynasty (c. {year})'
            elif year >= 960:
                return f'Song dynasty (c. {year})'
            elif year >= 618:
                return f'Tang dynasty (c. {year})'
        
        return period_str[:100] if len(period_str) > 100 else period_str
    
    @classmethod
    def get_era(cls, period_str):
        """获取时期所属的大时代"""
        aligned = cls.align(period_str)
        if aligned in cls.PERIOD_HIERARCHY:
            return cls.PERIOD_HIERARCHY[aligned]['era']
        return 'Unknown'


class TypeEntityAligner:
    """文物类型实体对齐器"""
    
    # 类型层次结构
    TYPE_HIERARCHY = {
        # 绘画类
        'Painting': {'category': 'Fine Art', 'subcategory': 'Painting'},
        'Handscroll': {'category': 'Fine Art', 'subcategory': 'Scroll Painting'},
        'Hanging scroll': {'category': 'Fine Art', 'subcategory': 'Scroll Painting'},
        'Album leaf': {'category': 'Fine Art', 'subcategory': 'Album Painting'},
        
        # 版画类
        'Print': {'category': 'Fine Art', 'subcategory': 'Print'},
        'Woodblock print': {'category': 'Fine Art', 'subcategory': 'Woodblock Print'},
        'Lithograph': {'category': 'Fine Art', 'subcategory': 'Lithograph'},
        'Etching': {'category': 'Fine Art', 'subcategory': 'Etching'},
        'Engraving': {'category': 'Fine Art', 'subcategory': 'Engraving'},
        
        # 摄影类
        'Photograph': {'category': 'Photography', 'subcategory': 'Photograph'},
        'Gelatin silver print': {'category': 'Photography', 'subcategory': 'Gelatin Silver'},
        'Albumen print': {'category': 'Photography', 'subcategory': 'Albumen'},
        
        # 陶瓷类
        'Ceramic': {'category': 'Ceramics', 'subcategory': 'Ceramic'},
        'Porcelain': {'category': 'Ceramics', 'subcategory': 'Porcelain'},
        'Pottery': {'category': 'Ceramics', 'subcategory': 'Pottery'},
        'Stoneware': {'category': 'Ceramics', 'subcategory': 'Stoneware'},
        'Earthenware': {'category': 'Ceramics', 'subcategory': 'Earthenware'},
        
        # 雕塑类
        'Sculpture': {'category': 'Sculpture', 'subcategory': 'Sculpture'},
        'Figure': {'category': 'Sculpture', 'subcategory': 'Figure'},
        'Bust': {'category': 'Sculpture', 'subcategory': 'Bust'},
        'Relief': {'category': 'Sculpture', 'subcategory': 'Relief'},
        
        # 器物类
        'Vessel': {'category': 'Decorative Arts', 'subcategory': 'Vessel'},
        'Vase': {'category': 'Decorative Arts', 'subcategory': 'Vase'},
        'Jar': {'category': 'Decorative Arts', 'subcategory': 'Jar'},
        'Bowl': {'category': 'Decorative Arts', 'subcategory': 'Bowl'},
        'Plate': {'category': 'Decorative Arts', 'subcategory': 'Plate'},
        
        # 纺织品
        'Textile': {'category': 'Textiles', 'subcategory': 'Textile'},
        'Robe': {'category': 'Textiles', 'subcategory': 'Garment'},
        'Costume': {'category': 'Textiles', 'subcategory': 'Costume'},
        
        # 媒体艺术
        'Video': {'category': 'Media Art', 'subcategory': 'Video'},
        'Digital video': {'category': 'Media Art', 'subcategory': 'Digital Video'},
        'Media art': {'category': 'Media Art', 'subcategory': 'Media Art'},
        
        # 其他
        'Jade carving': {'category': 'Decorative Arts', 'subcategory': 'Jade Carving'},
        'Bronze': {'category': 'Decorative Arts', 'subcategory': 'Bronze'},
        'Lacquerware': {'category': 'Decorative Arts', 'subcategory': 'Lacquerware'},
    }
    
    @classmethod
    def align(cls, type_str):
        """对齐类型名称"""
        if pd.isna(type_str) or type_str == '':
            return 'Unknown'
        
        type_str = str(type_str).strip()
        
        # 检查标准名称
        for standard in cls.TYPE_HIERARCHY.keys():
            if standard.lower() == type_str.lower():
                return standard
        
        # 模糊匹配
        for standard in cls.TYPE_HIERARCHY.keys():
            if standard.lower() in type_str.lower():
                return standard
        
        # 通用分类
        if any(x in type_str.lower() for x in ['paint', 'ink', 'watercolor', 'scroll']):
            return 'Painting'
        if any(x in type_str.lower() for x in ['photograph', 'print', 'gelatin', 'albumen']):
            return 'Photograph'
        if any(x in type_str.lower() for x in ['ceramic', 'porcelain', 'pottery', 'stoneware']):
            return 'Ceramic'
        if any(x in type_str.lower() for x in ['bronze', 'jade', 'ivory', 'lacquer']):
            return 'Decorative object'
        
        return type_str[:100] if len(type_str) > 100 else type_str
    
    @classmethod
    def get_category(cls, type_str):
        """获取类型的分类"""
        aligned = cls.align(type_str)
        if aligned in cls.TYPE_HIERARCHY:
            return cls.TYPE_HIERARCHY[aligned]['category']
        return 'Unknown'
    
    @classmethod
    def get_subcategory(cls, type_str):
        """获取类型的子分类"""
        aligned = cls.align(type_str)
        if aligned in cls.TYPE_HIERARCHY:
            return cls.TYPE_HIERARCHY[aligned]['subcategory']
        return 'Unknown'


class MaterialEntityAligner:
    """材质实体对齐器"""
    
    # 材质分类
    MATERIAL_CATEGORIES = {
        'Ceramic': ['Ceramic', 'Porcelain', 'Stoneware', 'Earthenware', 'Pottery', 'Clay', 'Terracotta'],
        'Wood': ['Wood', 'Bamboo'],
        'Jade/Stone': ['Jade', 'Jadeite', 'Nephrite', 'Stone', 'Marble', 'Limestone', 'Granite', 'Crystal'],
        'Metal': ['Bronze', 'Gold', 'Silver', 'Brass', 'Copper', 'Iron', 'Gilt', 'Patinated'],
        'Textile': ['Silk', 'Cotton', 'Linen', 'Wool', 'Textile'],
        'Painting Material': ['Oil', 'Ink', 'Watercolor', 'Gouache', 'Pastel', 'Tempera', 'Acrylic'],
        'Paper/Canvas': ['Paper', 'Canvas', 'Cardboard', 'Linen canvas'],
        'Glass': ['Glass', 'Enamel'],
        'Organic': ['Ivory', 'Bone', 'Shell', 'Bead', 'Feather', 'Hair'],
        'Photographic': ['Gelatin', 'Albumen', 'Photographic paper', 'Chromogenic'],
        'Unknown': ['Unknown', '']
    }
    
    @classmethod
    def align(cls, material_str):
        """对齐材质名称"""
        if pd.isna(material_str) or material_str == '':
            return 'Unknown'
        
        material_str = str(material_str).strip()
        
        # 首先检查是否已经是标准名称
        for category, items in cls.MATERIAL_CATEGORIES.items():
            if material_str in items:
                return material_str
        
        # 模糊匹配
        for category, items in cls.MATERIAL_CATEGORIES.items():
            for item in items:
                if item.lower() in material_str.lower():
                    return item
        
        # 默认返回原字符串（截断）
        return material_str[:100] if len(material_str) > 100 else material_str
    
    @classmethod
    def get_category(cls, material_str):
        """获取材质的分类"""
        aligned = cls.align(material_str)
        
        for category, items in cls.MATERIAL_CATEGORIES.items():
            if aligned in items:
                return category
        
        return 'Unknown'


def align_all_datasets(cleaned_dir, output_dir):
    """对所有清洗后的数据集进行实体对齐"""
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 收集所有数据
    all_data = []
    
    # 检查 cleaned 目录是否存在
    if not os.path.exists(cleaned_dir):
        print(f"错误: cleaned 目录不存在: {cleaned_dir}")
        print("请先运行清洗脚本生成 cleaned 目录中的文件")
        return None
    
    # 找到 cleaned 目录下的所有清洗文件
    files_found = []
    for file_name in os.listdir(cleaned_dir):
        if file_name.startswith('clean_') and file_name.endswith('.csv'):
            file_path = os.path.join(cleaned_dir, file_name)
            files_found.append(file_name)
            print(f"读取文件: {file_path}")
            try:
                df = pd.read_csv(file_path)
                all_data.append(df)
                print(f"  - 成功读取 {len(df)} 条记录")
            except Exception as e:
                print(f"  - 读取失败: {e}")
    
    if not all_data:
        print(f"\n错误: 在 {cleaned_dir} 目录中未找到任何清洗后的CSV文件")
        print(f"找到的文件: {files_found}")
        print("\n请确保:")
        print(f"1. 清洗脚本已成功运行")
        print(f"2. cleaned 目录 ({cleaned_dir}) 中有 clean_*.csv 文件")
        print(f"3. 当前目录结构: alignment 和 cleaning 文件夹在同一级")
        print(f"\n当前脚本所在目录: {os.path.dirname(os.path.abspath(__file__))}")
        return None
    
    # 合并所有数据
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 添加对齐后的列
    combined_df['aligned_museum'] = combined_df['museum'].apply(MuseumEntityAligner.align)
    combined_df['museum_location'] = combined_df['museum'].apply(MuseumEntityAligner.get_location)
    combined_df['aligned_period'] = combined_df['standardized_period'].apply(PeriodEntityAligner.align)
    combined_df['period_era'] = combined_df['standardized_period'].apply(PeriodEntityAligner.get_era)
    combined_df['aligned_type'] = combined_df['standardized_type'].apply(TypeEntityAligner.align)
    combined_df['type_category'] = combined_df['standardized_type'].apply(TypeEntityAligner.get_category)
    combined_df['type_subcategory'] = combined_df['standardized_type'].apply(TypeEntityAligner.get_subcategory)
    combined_df['aligned_material'] = combined_df['standardized_material'].apply(MaterialEntityAligner.align)
    combined_df['material_category'] = combined_df['standardized_material'].apply(MaterialEntityAligner.get_category)
    # 艺术家 / 地点（从各馆差异化列名中提取）
    combined_df['aligned_artist'] = combined_df.apply(ArtistEntityAligner.extract, axis=1)
    combined_df['aligned_location'] = combined_df.apply(LocationEntityAligner.extract, axis=1)

    # 为每类实体生成唯一标识符 URI（跨数据源去重 + 可追溯）
    combined_df['artwork_uri'] = combined_df['object_id'].apply(lambda v: make_uri('artifact', v))
    combined_df['museum_uri'] = combined_df['aligned_museum'].apply(lambda v: make_uri('museum', v))
    combined_df['period_uri'] = combined_df['aligned_period'].apply(lambda v: make_uri('period', v))
    combined_df['type_uri'] = combined_df['aligned_type'].apply(lambda v: make_uri('type', v))
    combined_df['material_uri'] = combined_df['aligned_material'].apply(lambda v: make_uri('material', v))
    combined_df['artist_uri'] = combined_df['aligned_artist'].apply(lambda v: make_uri('artist', v))
    combined_df['location_uri'] = combined_df['aligned_location'].apply(lambda v: make_uri('location', v))
    
    # 保存对齐后的数据
    combined_output = os.path.join(output_dir, 'aligned_combined.csv')
    combined_df.to_csv(combined_output, index=False)
    print(f"\n实体对齐完成，数据保存到: {combined_output}")
    print(f"总记录数: {len(combined_df)}")
    
    # 输出统计信息
    print("\n=== 实体对齐统计 ===\n")
    
    print("博物馆分布:")
    print(combined_df['aligned_museum'].value_counts().head(10))
    print("\n")
    
    print("时期分布:")
    print(combined_df['aligned_period'].value_counts().head(10))
    print("\n")
    
    print("时期时代分布:")
    print(combined_df['period_era'].value_counts())
    print("\n")
    
    print("类型分布:")
    print(combined_df['aligned_type'].value_counts().head(10))
    print("\n")
    
    print("类型分类分布:")
    print(combined_df['type_category'].value_counts())
    print("\n")
    
    print("材质分类分布:")
    print(combined_df['material_category'].value_counts())
    
    # 保存各数据集的对齐版本
    aligned_datasets_dir = os.path.join(output_dir, 'by_dataset')
    os.makedirs(aligned_datasets_dir, exist_ok=True)
    
    for file_name in os.listdir(cleaned_dir):
        if file_name.startswith('clean_') and file_name.endswith('.csv'):
            file_path = os.path.join(cleaned_dir, file_name)
            try:
                df = pd.read_csv(file_path)
                
                # 添加对齐列
                df['aligned_museum'] = df['museum'].apply(MuseumEntityAligner.align)
                df['aligned_period'] = df['standardized_period'].apply(PeriodEntityAligner.align)
                df['aligned_type'] = df['standardized_type'].apply(TypeEntityAligner.align)
                df['aligned_material'] = df['standardized_material'].apply(MaterialEntityAligner.align)
                
                output_file = os.path.join(aligned_datasets_dir, file_name)
                df.to_csv(output_file, index=False)
            except Exception as e:
                print(f"处理 {file_name} 时出错: {e}")
    
    print(f"\n各数据集的对齐版本已保存到: {aligned_datasets_dir}")
    
    return combined_df


def create_neo4j_import_files(combined_df, output_dir):
    """创建 Neo4j 导入文件"""
    
    # 创建节点文件目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 文物节点
    artworks_df = combined_df[['object_id', 'artwork_uri', 'title', 'description', 'dimensions',
                               'accession_number', 'detail_url', 'image_url',
                               'aligned_period', 'aligned_type', 'aligned_material',
                               'aligned_artist', 'aligned_location',
                               'data_quality_score']].drop_duplicates(subset=['object_id'])
    artworks_df = artworks_df.rename(columns={'artwork_uri': 'uri'})
    artworks_df.to_csv(os.path.join(output_dir, 'nodes_artworks.csv'), index=False)
    print(f"文物节点: {len(artworks_df)} 条")
    
    # 2. 博物馆节点
    museums_df = combined_df[['aligned_museum', 'museum_uri', 'museum_location']].drop_duplicates(subset=['aligned_museum'])
    museums_df = museums_df.rename(columns={'aligned_museum': 'name', 'museum_uri': 'uri', 'museum_location': 'location'})
    museums_df.to_csv(os.path.join(output_dir, 'nodes_museums.csv'), index=False)
    print(f"博物馆节点: {len(museums_df)} 条")
    
    # 3. 时期节点
    periods_df = combined_df[['aligned_period', 'period_uri', 'period_era']].drop_duplicates(subset=['aligned_period'])
    periods_df = periods_df.rename(columns={'aligned_period': 'name', 'period_uri': 'uri', 'period_era': 'era'})
    periods_df.to_csv(os.path.join(output_dir, 'nodes_periods.csv'), index=False)
    print(f"时期节点: {len(periods_df)} 条")
    
    # 4. 类型节点
    types_df = combined_df[['aligned_type', 'type_uri', 'type_category', 'type_subcategory']].drop_duplicates(subset=['aligned_type'])
    types_df = types_df.rename(columns={'aligned_type': 'name', 'type_uri': 'uri', 'type_category': 'category', 'type_subcategory': 'subcategory'})
    types_df.to_csv(os.path.join(output_dir, 'nodes_types.csv'), index=False)
    print(f"类型节点: {len(types_df)} 条")
    
    # 5. 材质节点
    materials_df = combined_df[['aligned_material', 'material_uri', 'material_category']].drop_duplicates(subset=['aligned_material'])
    materials_df = materials_df.rename(columns={'aligned_material': 'name', 'material_uri': 'uri', 'material_category': 'category'})
    materials_df.to_csv(os.path.join(output_dir, 'nodes_materials.csv'), index=False)
    print(f"材质节点: {len(materials_df)} 条")

    # 6. 艺术家节点（过滤空值）
    artists_src = combined_df[combined_df['aligned_artist'].astype(bool) & (combined_df['aligned_artist'] != '')]
    artists_df = artists_src[['aligned_artist', 'artist_uri']].drop_duplicates(subset=['aligned_artist'])
    artists_df = artists_df.rename(columns={'aligned_artist': 'name', 'artist_uri': 'uri'})
    artists_df.to_csv(os.path.join(output_dir, 'nodes_artists.csv'), index=False)
    print(f"艺术家节点: {len(artists_df)} 条")

    # 7. 地点节点（过滤空值）
    loc_src = combined_df[combined_df['aligned_location'].astype(bool) & (combined_df['aligned_location'] != '')]
    locations_df = loc_src[['aligned_location', 'location_uri']].drop_duplicates(subset=['aligned_location'])
    locations_df = locations_df.rename(columns={'aligned_location': 'name', 'location_uri': 'uri'})
    locations_df.to_csv(os.path.join(output_dir, 'nodes_locations.csv'), index=False)
    print(f"地点节点: {len(locations_df)} 条")

    # 8. 关系文件: 文物-博物馆
    artwork_museum_df = combined_df[['object_id', 'aligned_museum']].drop_duplicates()
    artwork_museum_df.to_csv(os.path.join(output_dir, 'relationships_artwork_museum.csv'), index=False)
    print(f"文物-博物馆关系: {len(artwork_museum_df)} 条")
    
    # 9. 关系文件: 文物-时期
    artwork_period_df = combined_df[['object_id', 'aligned_period']].drop_duplicates()
    artwork_period_df.to_csv(os.path.join(output_dir, 'relationships_artwork_period.csv'), index=False)
    print(f"文物-时期关系: {len(artwork_period_df)} 条")
    
    # 10. 关系文件: 文物-类型
    artwork_type_df = combined_df[['object_id', 'aligned_type']].drop_duplicates()
    artwork_type_df.to_csv(os.path.join(output_dir, 'relationships_artwork_type.csv'), index=False)
    print(f"文物-类型关系: {len(artwork_type_df)} 条")
    
    # 11. 关系文件: 文物-材质
    artwork_material_df = combined_df[['object_id', 'aligned_material']].drop_duplicates()
    artwork_material_df.to_csv(os.path.join(output_dir, 'relationships_artwork_material.csv'), index=False)
    print(f"文物-材质关系: {len(artwork_material_df)} 条")

    # 12. 关系文件: 文物-艺术家（创作于）
    artwork_artist_df = artists_src[['object_id', 'aligned_artist']].drop_duplicates()
    artwork_artist_df.to_csv(os.path.join(output_dir, 'relationships_artwork_artist.csv'), index=False)
    print(f"文物-艺术家关系: {len(artwork_artist_df)} 条")

    # 13. 关系文件: 文物-地点（出土/产自）
    artwork_location_df = loc_src[['object_id', 'aligned_location']].drop_duplicates()
    artwork_location_df.to_csv(os.path.join(output_dir, 'relationships_artwork_location.csv'), index=False)
    print(f"文物-地点关系: {len(artwork_location_df)} 条")
    
    print(f"\nNeo4j 导入文件已保存到: {output_dir}")


if __name__ == "__main__":
    # 获取当前脚本所在目录
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 清洗后的数据目录: ../cleaning/cleaned
    # 因为 alignment 和 cleaning 在同一级目录下
    CLEANED_DIR = os.path.join(CURRENT_DIR, '..', 'cleaning', 'cleaned')
    
    # 对齐后的输出目录: alignment/ 本身
    # （与 db/neo4j_builder.py、db/mysql_builder.py 的读取路径保持一致）
    ALIGNED_DIR = CURRENT_DIR

    # Neo4j 导入文件目录: alignment/neo4j_import
    NEO4J_DIR = os.path.join(ALIGNED_DIR, 'neo4j_import')
    
    print("=" * 60)
    print("实体对齐脚本")
    print("=" * 60)
    print(f"当前脚本目录: {CURRENT_DIR}")
    print(f"Cleaned 目录: {CLEANED_DIR}")
    print(f"Aligned 输出目录: {ALIGNED_DIR}")
    print(f"Neo4j 导入目录: {NEO4J_DIR}")
    print("=" * 60)
    print()
    
    # 检查 cleaned 目录是否存在
    if not os.path.exists(CLEANED_DIR):
        print(f"错误: cleaned 目录不存在!")
        print(f"请先运行 cleaning/run_all_clean.py 生成清洗后的文件")
        print(f"期望的目录路径: {CLEANED_DIR}")
        exit(1)
    
    # 列出 cleaned 目录中的文件
    print(f"cleaned 目录中的文件:")
    if os.path.exists(CLEANED_DIR):
        for f in os.listdir(CLEANED_DIR):
            if f.endswith('.csv'):
                print(f"  - {f}")
    print()
    
    # 执行实体对齐
    combined_df = align_all_datasets(CLEANED_DIR, ALIGNED_DIR)
    
    if combined_df is not None:
        # 创建 Neo4j 导入文件
        create_neo4j_import_files(combined_df, NEO4J_DIR)
        print("\n实体对齐完成!")
    else:
        print("\n实体对齐失败，请检查 cleaned 目录中的文件")