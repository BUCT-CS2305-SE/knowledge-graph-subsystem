"""
百度翻译模块
使用百度翻译API将英文翻译成中文
"""
import pandas as pd
import time
import re
import hashlib
import random
import requests
import json
import os


class BaiduTranslator:
    """百度翻译器"""
    
    # 需要翻译的字段列表
    TRANSLATE_FIELDS = [
        'title', 'period', 'type', 'material', 
        'description', 'culture', 'credit_line',
        'standardized_period', 'standardized_type', 'standardized_material'
    ]
    
    def __init__(self, app_id, app_key, delay=1, max_retries=3):
        """
        初始化百度翻译器
        
        Args:
            app_id: 百度翻译API的APP ID
            app_key: 百度翻译API的密钥
            delay: 每次翻译之间的延迟（秒），避免超出QPS限制
            max_retries: 最大重试次数
        """
        self.app_id = app_id
        self.app_key = app_key
        self.delay = delay
        self.max_retries = max_retries
        self.cache = {}
        self.stats = {'total': 0, 'cached': 0, 'failed': 0, 'characters': 0}
        
        # 百度翻译API端点
        self.url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    
    def is_valid_for_translation(self, text):
        """
        判断文本是否值得翻译
        """
        if pd.isna(text) or text == '' or text is None:
            return False
        
        text_str = str(text).strip()
        if not text_str:
            return False
        
        # 跳过纯数字或过短的文本
        if text_str.isdigit() or len(text_str) < 3:
            return False
        
        # 跳过看起来像编号的文本（如 "As.7097", "OA+.3873"）
        if re.match(r'^[A-Za-z0-9\-\_\.\+]+$', text_str) and len(text_str) < 20:
            letter_count = sum(1 for c in text_str if c.isalpha())
            if letter_count < len(text_str) * 0.3:
                return False
        
        # 检查是否已经是中文
        chinese_count = sum(1 for c in text_str if '\u4e00' <= c <= '\u9fff')
        if chinese_count > 0:
            # 如果中文字符占比超过30%，认为已经是中文
            if chinese_count / len(text_str) > 0.3:
                return False
        
        return True
    
    def translate_text(self, text):
        """
        翻译单个文本（使用百度API）
        """
        if not self.is_valid_for_translation(text):
            return text if not pd.isna(text) else ''
        
        text_str = str(text).strip()
        
        # 检查缓存
        if text_str in self.cache:
            self.stats['cached'] += 1
            return self.cache[text_str]
        
        self.stats['total'] += 1
        self.stats['characters'] += len(text_str)
        
        for attempt in range(self.max_retries):
            try:
                # 生成随机数
                salt = str(random.randint(32768, 65536))
                
                # 生成签名
                sign_str = self.app_id + text_str + salt + self.app_key
                sign = hashlib.md5(sign_str.encode()).hexdigest()
                
                # 构建请求参数
                params = {
                    'q': text_str,
                    'from': 'en',
                    'to': 'zh',
                    'appid': self.app_id,
                    'salt': salt,
                    'sign': sign
                }
                
                # 发送请求
                response = requests.get(self.url, params=params, timeout=30)
                result = response.json()
                
                # 检查错误
                if 'error_code' in result:
                    error_msg = result.get('error_msg', 'Unknown error')
                    raise Exception(f"API错误 {result['error_code']}: {error_msg}")
                
                # 提取翻译结果
                if 'trans_result' in result and len(result['trans_result']) > 0:
                    translated = result['trans_result'][0]['dst']
                else:
                    translated = text_str
                
                time.sleep(self.delay)
                
                # 缓存结果
                self.cache[text_str] = translated
                return translated
                
            except Exception as e:
                print(f"  翻译失败 (尝试 {attempt + 1}/{self.max_retries}): {text_str[:50]}... 错误: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * 2)
                else:
                    self.stats['failed'] += 1
                    return text_str
        
        return text_str
    
    def translate_dataframe(self, df, fields=None):
        """
        翻译DataFrame中的指定字段
        """
        if fields is None:
            fields = self.TRANSLATE_FIELDS
        
        df = df.copy()
        
        for field in fields:
            if field not in df.columns:
                continue
            
            # 创建原英文列备份
            en_col_name = f'{field}_original_en'
            if en_col_name not in df.columns:
                df[en_col_name] = df[field].copy()
            
            print(f"  翻译字段: {field} (共 {len(df)} 条)")
            translated_values = []
            total = len(df)
            
            for idx, (_, value) in enumerate(df[field].items()):
                if idx % 20 == 0 and idx > 0:
                    print(f"    进度: {idx}/{total} (成功: {self.stats['total'] - self.stats['failed']}, 缓存: {self.stats['cached']})")
                translated = self.translate_text(value)
                translated_values.append(translated)
            
            df[field] = translated_values
            print(f"    字段 {field} 完成")
        
        return df
    
    def print_stats(self):
        """打印统计信息"""
        success = self.stats['total'] - self.stats['failed']
        print(f"\n翻译统计:")
        print(f"  总翻译次数: {self.stats['total']}")
        print(f"  成功: {success}")
        print(f"  缓存命中: {self.stats['cached']}")
        print(f"  失败: {self.stats['failed']}")
        print(f"  总字符数: {self.stats['characters']}")
        if self.stats['total'] > 0:
            print(f"  成功率: {success / self.stats['total'] * 100:.1f}%")


def translate_csv_file(input_path, output_path=None, fields=None, delay=0.5):
    """
    翻译单个CSV文件
    """
    print(f"\n翻译文件: {input_path}")
    
    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), 'baidu_config.json')
    if not os.path.exists(config_path):
        print("  错误: 未找到百度翻译配置文件 baidu_config.json")
        print("  请创建配置文件，格式: {\"app_id\": \"你的APP_ID\", \"app_key\": \"你的密钥\"}")
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    app_id = config.get('app_id')
    app_key = config.get('app_key')
    
    if not app_id or not app_key:
        print("  错误: 配置文件缺少 app_id 或 app_key")
        return None
    
    # 读取文件
    try:
        df = pd.read_csv(input_path)
        print(f"  记录数: {len(df)}")
        print(f"  字段数: {len(df.columns)}")
    except Exception as e:
        print(f"  读取文件失败: {e}")
        return None
    
    # 确定要翻译的字段
    translator_temp = BaiduTranslator(app_id, app_key, delay)
    fields_to_translate = [f for f in translator_temp.TRANSLATE_FIELDS if f in df.columns]
    
    print(f"  将翻译字段: {fields_to_translate}")
    
    if not fields_to_translate:
        print("  没有需要翻译的字段，跳过")
        return df
    
    # 翻译
    translator = BaiduTranslator(app_id, app_key, delay)
    df = translator.translate_dataframe(df, fields=fields_to_translate)
    
    # 保存
    if output_path is None:
        output_path = input_path
    
    try:
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"  翻译后的文件已保存: {output_path}")
    except Exception as e:
        print(f"  保存文件失败: {e}")
        return None
    
    translator.print_stats()
    return df


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        translate_csv_file(input_file, output_file)
    else:
        print("用法: python baidu_translator.py <输入文件> [输出文件]")