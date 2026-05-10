import pandas as pd
import os
import pymysql
from sqlalchemy import create_engine

# MySQL 数据库配置 (根据本地环境替换 password 和 user)
DB_USER = "root"
DB_PASS = "se_jk2305"
DB_HOST = "127.0.0.1"
DB_PORT = "3306"
DB_NAME = "knowledge_graph_db"

DATA_DIR = os.path.join(os.path.dirname(__file__), "../scrapers/data/cleaned")

def init_mysql_db():
    """初始化 MySQL 数据库以及表结构"""
    # 先连接 MySQL Server 创建 Database
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, port=int(DB_PORT))
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    conn.commit()
    cursor.close()
    conn.close()

def import_to_mysql():
    """将清洗后的文物全量详细数据写入关系型数据库，用于结构化检索和业务支撑"""
    print("Connecting to MySQL...")
    engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4")
    
    # 建立业务系统的一些额外默认表 (如用户表)
    with engine.connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50), email VARCHAR(50), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} does not exist. Please run scraping and cleaning first.")
        return

    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
    
    for file in csv_files:
        file_path = os.path.join(DATA_DIR, file)
        print(f"Importing {file} to MySQL table 'artifacts'...")
        df = pd.read_csv(file_path)
        
        # 写入 MySQL (存在则附加)
        df.to_sql(name='artifacts', con=engine, if_exists='append', index=False)
        print(f"Successfully imported {len(df)} records from {file}")

def main():
    try:
        init_mysql_db()
        import_to_mysql()
        print("MySQL database initialization and load complete.")
    except Exception as e:
        print(f"Error connecting or writing to MySQL: {e}")
        print("Please ensure MySQL is running locally and credentials match the script.")

if __name__ == "__main__":
    main()
