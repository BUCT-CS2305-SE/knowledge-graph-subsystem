"""
运行所有清洗脚本
"""

import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clean_princeton import clean_princeton, generate_quality_report
from clean_met import clean_met
from clean_chicago import clean_chicago
from clean_brooklyn_museum import clean_brooklyn_museum
from clean_brooklyn_botanic import clean_brooklyn_botanic
from clean_guimet import clean_guimet
from clean_british_museum import clean_british_museum

# 获取当前脚本所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 输入文件目录: cleaning/wait_to_clean
INPUT_DIR = os.path.join(CURRENT_DIR, 'wait_to_clean')

# 输出文件目录: cleaning/cleaned
OUTPUT_DIR = os.path.join(CURRENT_DIR, 'cleaned')

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)

FILES = {
    'princeton': {
        'input': os.path.join(INPUT_DIR, 'princeton.csv'),
        'output': os.path.join(OUTPUT_DIR, 'clean_princeton.csv'),
        'clean_func': clean_princeton
    },
    'met': {
        'input': os.path.join(INPUT_DIR, 'met_museum.csv'),
        'output': os.path.join(OUTPUT_DIR, 'clean_met.csv'),
        'clean_func': clean_met
    },
    'chicago': {
        'input': os.path.join(INPUT_DIR, 'chicago.csv'),
        'output': os.path.join(OUTPUT_DIR, 'clean_chicago.csv'),
        'clean_func': clean_chicago
    },
    'brooklyn_museum': {
        'input': os.path.join(INPUT_DIR, 'brooklyn_museum.csv'),
        'output': os.path.join(OUTPUT_DIR, 'clean_brooklyn_museum.csv'),
        'clean_func': clean_brooklyn_museum
    },
    'brooklyn_botanic': {
        'input': os.path.join(INPUT_DIR, 'brooklyn_botanic.csv'),
        'output': os.path.join(OUTPUT_DIR, 'clean_brooklyn_botanic.csv'),
        'clean_func': clean_brooklyn_botanic
    },
    'guimet': {
        'input': os.path.join(INPUT_DIR, 'guimet_museum.csv'),
        'output': os.path.join(OUTPUT_DIR, 'clean_guimet.csv'),
        'clean_func': clean_guimet
    },
    'british_museum': {
        'input': os.path.join(INPUT_DIR, 'british_museum.csv'),
        'output': os.path.join(OUTPUT_DIR, 'clean_british_museum.csv'),
        'clean_func': clean_british_museum
    }
}


def main():
    all_results = {}
    
    # 检查输入目录是否存在
    if not os.path.exists(INPUT_DIR):
        print(f"错误: 输入目录不存在 {INPUT_DIR}")
        print(f"请创建目录并将CSV文件放入: {INPUT_DIR}")
        return
    
    # 列出可用的输入文件
    available_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.csv')]
    print(f"在 {INPUT_DIR} 中找到的CSV文件: {available_files}")
    
    for name, config in FILES.items():
        input_file = config['input']
        output_file = config['output']
        
        if not os.path.exists(input_file):
            print(f"警告: 文件不存在 {input_file}, 跳过")
            continue
        
        try:
            print(f"\n处理 {name}...")
            df, completeness = config['clean_func'](input_file, output_file)
            all_results[name] = {
                'df': df,
                'completeness': completeness,
                'duplicates': df[df['is_duplicate']] if 'is_duplicate' in df.columns else pd.DataFrame()
            }
            print(f"成功处理 {name}: {len(df)} 条记录")
        except Exception as e:
            print(f"处理 {name} 时出错: {e}")
    
    # 生成综合质量报告 - 放在 cleaned 目录
    report_path = os.path.join(OUTPUT_DIR, 'data_quality_report.md')
    json_report_path = os.path.join(OUTPUT_DIR, 'quality_report.json')
    generate_quality_report(all_results, report_path)
    print(f"\n综合质量报告已生成: {report_path}")
    print(f"JSON报告已生成: {json_report_path}")


if __name__ == "__main__":
    main()