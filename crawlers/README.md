# Crawlers — 海外中国流失文物数据爬取

针对海外博物馆中国相关藏品的定向数据爬取，输出结构化 JSONL / CSV 数据，用于知识图谱构建。

> 子系统统一目录已扁平化：本目录就是 `crawlers` 包；7 个博物馆爬虫共用 `base_crawler.py` / `spiders.py` / `utils.py`。

---

## 支持的博物馆

| 博物馆 | id | 爬虫类 | 方式 | 抓取量 |
|---|---|---|---|---|
| 普林斯顿大学艺术博物馆 | `princeton` | `PrincetonMuseumCrawler` | Playwright + XHR 内部 API | 3,600 |
| 芝加哥艺术博物馆 | `chicago` | `ArtInstituteChicagoCrawler` | 官方 REST API | 1,000 |
| 布鲁克林艺术博物馆 | `brooklyn_museum` | `BrooklynArtMuseumCrawler` | Playwright + APIRequestContext | 720 |
| 大都会艺术博物馆 | `met_museum` | `MetMuseumCrawler` | 官方 REST API | 49 |
| 吉美博物馆 | `guimet_museum` | `GuimetMuseumCrawler` | BeautifulSoup | 9 |
| 大英博物馆 | `british_museum` | `BritishMuseumCrawler` | Playwright 绕过 Cloudflare | 100/页 |
| 布鲁克林植物园 | `brooklyn_botanic` | `BrooklynBotanicCrawler` | HTML | 2 |
| **合计** | | | | **5,480** |

5 团需要的是 `princeton` / `chicago` / `brooklyn_museum`。

---

## 快速开始

```bash
pip install -r ../requirements.txt
pip install playwright && playwright install chromium

# 抓取所有
python -m crawlers.main --museum all

# 抓取单馆
python -m crawlers.main --museum princeton
python -m crawlers.main --museum chicago
python -m crawlers.main --museum brooklyn_museum

# 同时下载图片原图
python -m crawlers.main --museum princeton --download-images
```

### 输出目录

```
crawlers/data/raw/
  princeton.jsonl / princeton.csv
  chicago.jsonl   / chicago.csv
  brooklyn_museum.jsonl / brooklyn_museum.csv
  met_museum.jsonl      / met_museum.csv
  guimet_museum.jsonl   / guimet_museum.csv
  british_museum.jsonl  / british_museum.csv
  brooklyn_botanic.jsonl / brooklyn_botanic.csv
  images/                                   # --download-images 时输出
```

---

## 标准输出字段（15 列，与 docs/project_specification.md 7.1 节一致）

| 字段名 | 中文说明 | 必填 |
|---|---|---|
| `object_id` | 文物唯一标识符 | 必填 |
| `title` | 文物名称 | 必填 |
| `period` | 年代/时期 | 必填 |
| `type` | 文物类型 | 必填 |
| `material` | 材质 | 建议 |
| `description` | 文物介绍 | 必填 |
| `dimensions` | 尺寸 | 建议 |
| `museum` | 所属博物馆 | 必填 |
| `location` | 博物馆所在地 | 必填 |
| `detail_url` | 详情页 URL | 必填 |
| `image_url` | 原图 URL | 必填 |
| `image_path` | 本地图片相对路径 | 必填 |
| `credit_line` | 版权/来源说明 | 建议 |
| `accession_number` | 藏品编号 | 建议 |
| `crawl_date` | 爬取日期 YYYY-MM-DD | 必填 |

额外字段以 `_` 前缀标记（例如 `_image_valid`, `_classification`），下游清洗 / 入库会忽略。

---

## 模块说明

| 文件 | 作用 |
|---|---|
| [base_crawler.py](./base_crawler.py) | 抽象基类：session、超时、重试、限速、429 退避 |
| [spiders.py](./spiders.py) | 7 个博物馆爬虫的具体实现 |
| [config.py](./config.py) | 博物馆列表 + 输出目录 + UA |
| [utils.py](./utils.py) | JSONL / CSV 写入 + 图片下载 / HEAD 校验 |
| [main.py](./main.py) | CLI 入口（`python -m crawlers.main`） |
| [crawl_report.md](./crawl_report.md) | 爬取报告（覆盖度 / 数据质量自查） |

---

## 各爬虫要点

### Princeton — 内部 API 鉴权
- 数据源：`data.artmuseum.princeton.edu/collection/msearch`
- 直接请求 401，必须先用 Playwright 打开主页拿 Cookie，再 `withCredentials: true` XHR

### Chicago — 官方开放 API
- `https://api.artic.edu/api/v1/artworks/search?q=china`
- 无需 Key；图片走 IIIF：`https://www.artic.edu/iiif/2/{image_id}/full/843,/default.jpg`
- 10 页 / 1,000 条之后会被速率限制

### Brooklyn Museum — Sanity CMS
- `search.brooklynmuseum.org/api/search`
- Playwright 打开浏览器后用 `page.request.get()` 调 JSON API

### Met — 官方开放 API
- `https://collectionapi.metmuseum.org/public/collection/v1`
- 无需 Key

### Guimet — Drupal 静态页面
- BeautifulSoup 解析详情页（仅展示 9 件精选）

### British Museum — Cloudflare
- 必须 Playwright 浏览器拦截 `/_search` 内部 API

### Brooklyn Botanic Garden — 遗留模块
- 与"中国流失文物"主题无关，保留兼容

---

## 依赖

| 库 | 用途 |
|---|---|
| `requests` | HTTP |
| `beautifulsoup4` / `lxml` | HTML 解析 |
| `playwright` | Princeton / Brooklyn Museum / British Museum 必需 |
