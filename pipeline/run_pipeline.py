import sys
import os
import json
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'pipeline.log')),
        logging.StreamHandler(sys.stdout)
    ]
)

# 避免目录引用问题，确保当前为模块根路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(PROJECT_ROOT)

# 导入我们的各个处理模块
try:
    # 模拟导入各阶段的启动函数 
    # 实际应用中需要确保各个 py 文件的 main() 函数可被直接调用或重构为类
    from scrapers.spiders import chicago_spider
    from scrapers.spiders import princeton_spider
    from scrapers.spiders import brooklyn_spider
    from scrapers import clean_qa
    from scrapers import augmentation
    from db import mysql_builder
    from db import neo4j_builder
except ImportError as e:
    logging.warning(f"Note: Import adjustments might be needed based on pythonpath. {e}")

SYNC_STATE_FILE = os.path.join(os.path.dirname(__file__), 'sync_state.json')

def load_sync_state():
    """加载上次同步的时间戳和记录"""
    if os.path.exists(SYNC_STATE_FILE):
        with open(SYNC_STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_run": "2000-01-01", "total_records": 0}

def save_sync_state(records_added):
    """保存最新的同步状态"""
    state = {
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": records_added
    }
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(state, f)
    logging.info(f"State saved. Last run updated to: {state['last_run']}")

def run_scrapers_incremental(last_run_date):
    """
    执行增量爬虫
    (注意：实际上爬虫内部需修改抓取逻辑过滤只抓取 last_updated > last_run_date 的记录。
    这里示意执行流程调用)
    """
    logging.info(f"Starting incremental scraping for records after {last_run_date}...")
    
    # 理论上的增量爬虫执行逻辑
    # chicago_spider.fetch_chicago_data(incremental_since=last_run_date)
    # princeton_spider.fetch_princeton_data(incremental_since=last_run_date)
    # brooklyn_spider.fetch_brooklyn_data(incremental_since=last_run_date)
    
    # 暂以命令行示例触发
    os.system(f"cd {PROJECT_ROOT}/scrapers && python spiders/chicago_spider.py")
    os.system(f"cd {PROJECT_ROOT}/scrapers && python spiders/princeton_spider.py")
    os.system(f"cd {PROJECT_ROOT}/scrapers && python spiders/brooklyn_spider.py")

def build_pipeline():
    logging.info("=== Knowledge Graph Build Pipeline Started ===")
    
    state = load_sync_state()
    last_run = state.get("last_run", "2000-01-01")
    
    try:
        # Step 1: Incremental Scraping
        logging.info("--> Step 1: Running Scrapers")
        run_scrapers_incremental(last_run)
        
        # Step 2: Clean & QA
        logging.info("--> Step 2: Quality Assurance & Cleaning")
        os.system(f"cd {PROJECT_ROOT}/scrapers && python clean_qa.py")
        
        # Step 3: Entity Alignment
        logging.info("--> Step 3: Entity Alignment & Augmentation")
        os.system(f"cd {PROJECT_ROOT}/scrapers && python augmentation.py")
        
        # Step 4: Storage Load
        logging.info("--> Step 4: Synchronizing to MySQL and Neo4j")
        os.system(f"cd {PROJECT_ROOT}/db && python mysql_builder.py")
        os.system(f"cd {PROJECT_ROOT}/db && python neo4j_builder.py")
        
        # 统计数量 (假设每次完成记录日志表)
        # 这里记录状态防止重新拉取
        save_sync_state(state.get("total_records", 0) + 1)
        logging.info("=== Pipeline Completed Successfully ===")
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")

if __name__ == "__main__":
    # 该文件可以通过 cron job 或 airflow 定期调度执行
    build_pipeline()
