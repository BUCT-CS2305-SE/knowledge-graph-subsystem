import requests
import os
import time
import pymysql
import re
from datetime import datetime

# =====================
# API配置
# =====================
API_URL = "https://api.artic.edu/api/v1/artworks/search"
BASE_DETAIL_URL = "https://www.artic.edu/artworks/"
MUSEUM_NAME = "Art Institute of Chicago"
LOCATION = "Chicago, USA"

HEADERS = {
    "User-Agent": "KnowledgeGraphAcademicProject/1.0"
}

# =====================
# MySQL配置（root版本）
# =====================
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "se_jk2305",
    "database": "knowledge_graph_db",
    "charset": "utf8mb4",
    "autocommit": False
}

# =====================
# 图片目录
# =====================
IMAGE_DIR = os.path.join(os.path.dirname(__file__), "../images/chicago")

# MVP: do not download images, use default placeholder in API
ENABLE_IMAGE_DOWNLOAD = False


# =====================
# 初始化环境
# =====================
def init_env():
    os.makedirs(IMAGE_DIR, exist_ok=True)


def get_conn():
    return pymysql.connect(**MYSQL_CONFIG)


def init_mysql_table():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS artifacts (
        object_id BIGINT PRIMARY KEY,
        title TEXT,
        period TEXT,
        type TEXT,
        material TEXT,
        description TEXT,
        dimensions TEXT,
        museum TEXT,
        location TEXT,
        detail_url TEXT,
        image_url TEXT,
        image_path TEXT,
        credit_line TEXT,
        accession_number TEXT,
        crawl_date DATE
    )
    """)

    conn.commit()
    conn.close()


# =====================
# 图片下载
# =====================
def download_image(image_url, object_id):
    if not ENABLE_IMAGE_DOWNLOAD:
        return ""
    if not image_url:
        return ""

    file_name = f"obj_{object_id}.jpg"
    file_path = os.path.join(IMAGE_DIR, file_name)

    if os.path.exists(file_path):
        return f"images/chicago/{file_name}"

    try:
        r = requests.get(image_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(r.content)
            return f"images/chicago/{file_name}"
    except Exception:
        pass

    return ""


# =====================
# 清洗与标准化
# =====================
def standardize_period(period_str):
    if not isinstance(period_str, str) or not period_str.strip():
        return "Unknown"

    period_lower = period_str.lower()
    if "qing" in period_lower or "ch'ing" in period_lower:
        return "Qing Dynasty (1644-1911)"
    if "ming" in period_lower:
        return "Ming Dynasty (1368-1644)"
    if "yuan" in period_lower:
        return "Yuan Dynasty (1271-1368)"
    if "song" in period_lower or "sung" in period_lower:
        return "Song Dynasty (960-1279)"
    if "tang" in period_lower:
        return "Tang Dynasty (618-907)"
    if "han" in period_lower:
        return "Han Dynasty (202 BC-220 AD)"
    if "shang" in period_lower:
        return "Shang Dynasty (c. 1600-1046 BC)"
    if "zhou" in period_lower or "chou" in period_lower:
        return "Zhou Dynasty (c. 1046-256 BC)"
    if "jin" in period_lower and "western" not in period_lower:
        return "Jin Dynasty (1115-1234)"

    return re.sub(r"\s+", " ", period_str).strip()


def standardize_type(type_str):
    if not isinstance(type_str, str) or not type_str.strip():
        return "Other"

    t_lower = type_str.lower()
    if "paint" in t_lower or "scroll" in t_lower:
        return "Painting"
    if "ceramic" in t_lower or "porcelain" in t_lower or "pottery" in t_lower:
        return "Ceramics"
    if "bronze" in t_lower or "metal" in t_lower:
        return "Bronze/Metalwork"
    if "jade" in t_lower:
        return "Jade"
    if "sculpture" in t_lower or "statue" in t_lower or "figure" in t_lower:
        return "Sculpture"
    if "calligraphy" in t_lower:
        return "Calligraphy"
    if "textile" in t_lower or "silk" in t_lower or "garment" in t_lower:
        return "Textiles"

    return type_str.title()


def clean_text(value):
    if not isinstance(value, str):
        return ""
    text = value.replace("<p>", "").replace("</p>", "")
    return re.sub(r"\s+", " ", text).strip()


# =====================
# 爬虫
# =====================
def fetch_data(limit_count=50):
    records = []
    page = 1

    print("Starting crawl...")

    while len(records) < limit_count:

        params = {
            "q": "Chinese",
            "fields": "id,title,date_display,artwork_type_title,medium_display,description,dimensions,credit_line,main_reference_number,image_id,place_of_origin",
            "limit": 100,
            "page": page
        }

        try:
            res = requests.get(API_URL, params=params, headers=HEADERS)
            data = res.json()

            items = data.get("data", [])
            if not items:
                break

            for item in items:

                origin = str(item.get("place_of_origin", "")).lower()
                title = str(item.get("title", "")).lower()

                if "china" not in origin and "chinese" not in title:
                    continue

                object_id = item.get("id")
                image_id = item.get("image_id")

                image_url = (
                    f"https://www.artic.edu/iiif/2/{image_id}/full/full/0/default.jpg"
                    if image_id else ""
                )

                image_path = download_image(image_url, object_id)

                record = (
                    object_id,
                    item.get("title", ""),
                    standardize_period(item.get("date_display", "")),
                    standardize_type(item.get("artwork_type_title", "")),
                    item.get("medium_display", "") or "",
                    clean_text(item.get("description") or ""),
                    item.get("dimensions", ""),
                    MUSEUM_NAME,
                    LOCATION,
                    f"{BASE_DETAIL_URL}{object_id}",
                    image_url,
                    image_path,
                    item.get("credit_line", ""),
                    item.get("main_reference_number", ""),
                    datetime.now().strftime("%Y-%m-%d")
                )

                records.append(record)

                print(f"{len(records)}/{limit_count} - {object_id}")

                time.sleep(0.2)

                if len(records) >= limit_count:
                    break

            page += 1

        except Exception as e:
            print("crawl error:", e)
            break

    return records


# =====================
# 写入 MySQL（root版）
# =====================
def insert_mysql(records):
    conn = get_conn()
    cursor = conn.cursor()

    sql = """
    INSERT INTO artifacts (
        object_id, title, period, type, material,
        description, dimensions, museum, location,
        detail_url, image_url, image_path,
        credit_line, accession_number, crawl_date
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        title=VALUES(title),
        description=VALUES(description),
        image_path=VALUES(image_path)
    """

    try:
        cursor.executemany(sql, records)
        conn.commit()
        print(f"MySQL insert success: {len(records)} records")

    except Exception as e:
        conn.rollback()
        print("MySQL insert error:", e)

    finally:
        conn.close()


# =====================
# main
# =====================
def main():
    init_env()
    init_mysql_table()

    records = fetch_data(20)

    if records:
        insert_mysql(records)
    else:
        print("No data fetched")


if __name__ == "__main__":
    main()