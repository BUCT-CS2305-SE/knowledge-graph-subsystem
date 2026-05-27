# Brooklyn Crawlers — 海外中国流失文物数据爬取

针对海外博物馆中国相关藏品的定向数据爬取，输出结构化的 JSONL / CSV 数据，用于知识图谱构建。

---

## 支持的博物馆

| 博物馆 | 爬虫类 | 方式 | 本次爬取量 |
|---|---|---|---|
| 普林斯顿大学艺术博物馆 (Princeton) | `PrincetonMuseumCrawler` | Playwright + XHR 内部 API | 3,600 条 |
| 芝加哥艺术博物馆 (Chicago) | `ArtInstituteChicagoCrawler` | 官方 REST API（免费开放） | 1,000 条 |
| 布鲁克林艺术博物馆 (Brooklyn Museum) | `BrooklynArtMuseumCrawler` | Playwright + APIRequestContext | 720 条 |
| 大都会艺术博物馆 (Met) | `MetMuseumCrawler` | 官方 REST API（免费开放） | 49 条 |
| 吉美博物馆 (Guimet) | `GuimetMuseumCrawler` | BeautifulSoup 爬取 Drupal 页面 | 9 条 |
| 大英博物馆 (British Museum) | `BritishMuseumCrawler` | Playwright 浏览器绕过 Cloudflare | 100 条/页 |
| 布鲁克林植物园 (BBG) | `BrooklynBotanicCrawler` | HTML 爬取 | 2 条 |
| **合计** | | | **5,480 条** |

---

## 快速开始

```bash
pip install -r requirements.txt
pip install playwright
playwright install chromium

python -m crawlers.brooklyn.main --museum all

python -m crawlers.brooklyn.main --museum princeton
python -m crawlers.brooklyn.main --museum chicago
python -m crawlers.brooklyn.main --museum brooklyn_museum
python -m crawlers.brooklyn.main --museum met_museum
python -m crawlers.brooklyn.main --museum guimet_museum
python -m crawlers.brooklyn.main --museum british_museum  
python -m crawlers.brooklyn.main --museum brooklyn_botanic

python -m crawlers.brooklyn.main --museum princeton --download-images
```

### 输出目录

```
crawlers/brooklyn/data/raw/
  princeton.jsonl / princeton.csv       # 普林斯顿大学艺术博物馆
  chicago.jsonl / chicago.csv           # 芝加哥艺术博物馆
  brooklyn_museum.jsonl / .csv          # 布鲁克林艺术博物馆
  met_museum.jsonl / met_museum.csv     # 大都会艺术博物馆
  guimet_museum.jsonl / guimet_museum.csv
  british_museum.jsonl / british_museum.csv
  brooklyn_botanic.jsonl / .csv         # 布鲁克林植物园（遗留）
  images/                               # 下载的原图（需 --download-images）
```

---

## 标准输出字段（15 字段）

所有爬虫统一输出以下字段，额外字段以 `_` 前缀标记：

| 字段名 | 中文说明 | 必填 |
|---|---|---|
| `object_id` | 文物唯一标识符 | 必填 |
| `title` | 文物名称 | 必填 |
| `period` | 年代/时期 | 必填 |
| `type` | 文物类型 | 必填 |
| `material` | 材质 | 建议填写 |
| `description` | 文物介绍 | 必填 |
| `dimensions` | 尺寸 | 建议填写 |
| `museum` | 所属博物馆 | 必填 |
| `location` | 博物馆所在地 | 必填 |
| `detail_url` | 文物详情页 URL | 必填 |
| `image_url` | 图片原始下载链接 | 必填 |
| `image_path` | 本地图片存储路径 | 必填 |
| `credit_line` | 版权/来源说明 | 建议填写 |
| `accession_number` | 藏品编号 | 建议填写 |
| `crawl_date` | 爬取日期 | 必填 |

---

## 爬虫说明

### Princeton University Art Museum（普林斯顿大学艺术博物馆）

- **数据源**: 内部 API `data.artmuseum.princeton.edu/collection/msearch`
- **策略**: Playwright 打开主页面鉴权后，通过 XHR 请求内部 API（`withCredentials: true`）
- **分页**: `from` 参数偏移，每页 24 条
- **注意**: 直接请求 API 返回 401，必须通过浏览器获取 Cookie

### Art Institute of Chicago（芝加哥艺术博物馆）

- **API**: `https://api.artic.edu/api/v1/artworks/search?q=china`
- **策略**: 直接 HTTP 请求（无需 API Key），`fields` 参数指定字段
- **图片**: IIIF 协议 `https://www.artic.edu/iiif/2/{image_id}/full/843,/default.jpg`
- **限制**: API 在 10 页（1,000 条）后速率限制，无法绕过

### Brooklyn Museum（布鲁克林艺术博物馆）

- **数据源**: Sanity CMS API `search.brooklynmuseum.org/api/search`
- **策略**: Playwright 打开浏览器后，使用 `page.request.get()` 调用 JSON API
- **分页**: `page` 参数，每页 24 条
- **库存**: 约 96,299 件藏品

### Met Museum（大都会）

- **API**: `https://collectionapi.metmuseum.org/public/collection/v1`
- **搜索**: `GET /search?q=China&hasImages=true` → `GET /objects/{objectID}`
- **无需 API Key**，完全开放
- [官方文档](https://metmuseum.github.io/)

### Guimet Museum（吉美）

- **网站**: Drupal 静态页面
- **策略**: 爬取详情页提取元数据
- **注意**: 目前仅展示 9 件精选藏品，非全量

### British Museum（大英）

- **网站**: 有 Cloudflare 防护，无法直接用 `requests` 访问
- **策略**: Playwright 浏览器绕过 Cloudflare，拦截内部 `/_search` API
- **注意**: 当前获取搜索列表数据（100 条），详情元数据需额外请求

### Brooklyn Botanic Garden（植物园）

- **说明**: 原项目遗留模块，与"中国流失文物"主题无关

---

## 项目结构

```
crawlers/brooklyn/
├── README.md           # 本文件
├── crawl_report.md     # 数据爬取报告（字段覆盖度、质量自查）
├── request.md          # 需求规格说明（字段规范、数据量要求）
├── main.py             # 入口脚本（CLI）
├── config.py           # 配置（博物馆列表、路径等）
├── base_crawler.py     # 爬虫基类（session、重试、限速）
├── spiders.py          # 各博物馆爬虫实现（7 个爬虫）
├── utils.py            # 工具函数（JSONL/CSV 保存、图片下载）
└── data/
    └── raw/            # 输出数据
```

---

## 依赖

- `requests` — HTTP 请求
- `beautifulsoup4` — HTML 解析
- `lxml` — HTML 解析加速
- `playwright` — 浏览器自动化（Princeton、Brooklyn Museum、British Museum 需要）
