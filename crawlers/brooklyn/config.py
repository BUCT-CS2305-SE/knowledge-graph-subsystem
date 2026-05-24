from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent
# 数据目录
DATA_DIR = ROOT / "data"
# 原始数据目录
RAW_DIR = DATA_DIR / "raw"

# HTTP 头部信息
USER_AGENT = "Mozilla/5.0 (compatible; KG-Crawler/1.0; +https://example.org)"

# 要爬取的博物馆配置（示例）
# id: 用于文件命名与选择；name: 可读名称；start_url: 抓取入口
MUSEUMS = [
    {
        "id": "brooklyn_museum",
        "name": "Brooklyn Museum",
        "start_url": "https://www.brooklynmuseum.org/exhibitions",
    },
    {
        "id": "brooklyn_botanic",
        "name": "Brooklyn Botanic Garden",
        "start_url": "https://www.bbg.org/",
    },
    {
        "id": "british_museum",
        "name": "The British Museum",
        "start_url": "https://www.britishmuseum.org/collection/search?place=China",
    },
    {
        "id": "met_museum",
        "name": "The Metropolitan Museum of Art",
        "start_url": "https://www.metmuseum.org/search-results?search=china",
    },
    {
        "id": "guimet_museum",
        "name": "Musée Guimet",
        "start_url": "https://www.guimet.fr/en/collections/",
    },
]