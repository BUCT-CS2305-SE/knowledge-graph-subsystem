# Brooklyn Crawlers — 海外中国流失文物数据爬取

针对海外博物馆中国相关藏品的定向数据爬取，输出结构化的 JSONL / CSV 数据，用于知识图谱构建。

---

## 支持的博物馆

| 博物馆 | 爬虫类 | 方式 | 数据量/批 |
|---|---|---|---|
| 大都会艺术博物馆 (Met) | `MetMuseumCrawler` | 官方 REST API（免费开放） | ~50 条 |
| 吉美博物馆 (Guimet) | `GuimetMuseumCrawler` | BeautifulSoup 爬取 Drupal 页面 | ~10 条 |
| 大英博物馆 (British Museum) | `BritishMuseumCrawler` | Playwright 浏览器绕过 Cloudflare | 100 条/页 |
| 布鲁克林植物园 (BBG) | `BrooklynBotanicCrawler` | HTML 爬取 | 若干 |

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install playwright
playwright install chromium

# 2. 爬取所有博物馆
python -m crawlers.brooklyn.main --museum all

# 3. 爬取单个博物馆
python -m crawlers.brooklyn.main --museum met_museum
python -m crawlers.brooklyn.main --museum guimet_museum
python -m crawlers.brooklyn.main --museum british_museum   # 需要 playwright
python -m crawlers.brooklyn.main --museum brooklyn_botanic

# 4. 可选：下载图片
python -m crawlers.brooklyn.main --museum met_museum --download-images
```

### 输出

```
crawlers/brooklyn/data/raw/
  met_museum.jsonl      # JSON Lines 格式（每行一条 JSON）
  met_museum.csv        # CSV 格式（可直接用 Excel 打开）
  guimet_museum.jsonl
  guimet_museum.csv
  british_museum.jsonl
  british_museum.csv
  brooklyn_botanic.jsonl
  brooklyn_botanic.csv
```

---

## 爬虫说明

### Met Museum（大都会）

- **API**: `https://collectionapi.metmuseum.org/public/collection/v1`
- **搜索**: `GET /search?q=China&hasImages=true`
- **详情**: `GET /objects/{objectID}`
- **无需 API Key**，完全开放
- 每次爬取前 50 条结果
- [官方文档](https://metmuseum.github.io/)

### Guimet Museum（吉美）

- **网站**: Drupal 静态页面
- **策略**: 爬取 `guimet.fr/en/collections/china` 列表页，跟进每条藏品的详情页提取元数据
- **注意**: 目前仅展示 9 件精选藏品，非全量

### British Museum（大英）

- **网站**: 有 Cloudflare 防护，无法直接用 `requests` 访问
- **策略**: 使用 Playwright（Chromium 浏览器）绕过 Cloudflare，拦截内部 `/_search` API
- **注意**: 当前获取的是搜索列表数据（100 条），详情页元数据需额外请求

### Brooklyn Botanic Garden（植物园）

- **说明**: 原项目遗留模块，与"中国流失文物"主题无关
- **爬取**: 植物展示页的图片描述

---

## 项目结构

```
crawlers/brooklyn/
├── README.md           # 本文件
├── crawl_report.md     # 数据爬取报告
├── main.py             # 入口脚本（CLI）
├── config.py           # 配置（博物馆列表、路径等）
├── base_crawler.py     # 爬虫基类（session、重试、限速）
├── spiders.py          # 各博物馆爬虫实现
├── utils.py            # 工具函数（JSONL/CSV 保存、图片下载）
└── data/
    └── raw/            # 输出数据
```

---

## 输出字段一览

| 字段 | Met | Guimet | British Museum |
|---|---|---|---|
| title | ✅ | ✅ | ✅ |
| culture | ✅ | - | ✅ |
| period | ✅ | ✅ | ✅ |
| dynasty | ✅ | - | - |
| medium/material | ✅ | ✅ | ✅ |
| classification | ✅ | ✅ | - |
| dimensions | ✅ | ✅ | - |
| artist | ✅ | - | - |
| image_url | ✅ | ✅ | ✅ |
| object_url | ✅ | ✅ | ✅ |
| findspot | - | - | ✅ |
| museum_number | ✅ | ✅ | ✅ |
| description | - | ✅ | - |

---

## 依赖

- `requests` — HTTP 请求
- `beautifulsoup4` — HTML 解析
- `lxml` — HTML 解析加速
- `playwright` — 浏览器自动化（仅大英博物馆需要）
- `cloudscraper` — Cloudflare 绕过（备用，当前未使用）
