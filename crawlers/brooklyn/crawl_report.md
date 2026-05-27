# 爬取数据报告

> 生成时间: 2026-05-27
> 爬虫目录: `crawlers/brooklyn/`
> 输出目录: `crawlers/brooklyn/data/raw/`

---

## 概览

| 博物馆 | 爬取方式 | 数据条数 | 字段数 | 文件 |
|---|---|---|---|---|
| 大都会艺术博物馆 (Met) | REST API（免费开放） | 49 条 | 26 个 | `met_museum.jsonl` / `.csv` |
| 吉美博物馆 (Guimet) | HTML 页面爬取（Drupal） | 9 条 | 11 个 | `guimet_museum.jsonl` / `.csv` |
| 大英博物馆 (British Museum) | Playwright 浏览器 + ES API | 100 条 | 13 个 | `british_museum.jsonl` / `.csv` |
| 布鲁克林植物园 (BBG) | HTML 页面爬取 | 2 条 | 9 个 | `brooklyn_botanic.jsonl` / `.csv` |

**输出格式**: 同时输出 JSONL（每行一条 JSON）和 CSV（表格，可用 Excel/WPS 打开）。

---

## 1. 大都会艺术博物馆 — met_museum

**数据来源**: [Met Collection API](https://metmuseum.github.io/)（无需 API Key）
**搜索条件**: `q=China&hasImages=true`

### 字段说明

| 字段 | 覆盖度 | 说明 |
|---|---|---|
| `title` | 49/49 | 藏品名称 |
| `object_name` | 49/49 | 物件类型（Print, Figure, Bowl...） |
| `culture` | 23/49 | 文化归属（China, Chinese...） |
| `period` | 18/49 | 时期描述（Yuan dynasty, Qing dynasty...） |
| `dynasty` | 2/49 | 朝代（独立字段，较少填充） |
| `reign` | 2/49 | 皇帝年号 |
| `object_date` | 47/49 | 年代描述（dated 1282, 15th century...） |
| `medium` | 49/49 | 材质/工艺 |
| `classification` | 43/49 | 分类（Sculpture, Ceramics, Prints...） |
| `department` | 49/49 | 所属部门（Asian Art, Islamic Art...） |
| `dimensions` | 49/49 | 尺寸 |
| `credit_line` | 49/49 | 来源/捐赠信息 |
| `artist` | 29/49 | 艺术家姓名 |
| `artist_bio` | 25/49 | 艺术家生平 |
| `artist_nationality` | 24/49 | 艺术家国籍 |
| `image_url` | 46/49 | 高清图片链接 |
| `image_small` | 46/49 | 缩略图链接 |
| `object_url` | 49/49 | 官网详情页链接 |
| `accession_number` | 49/49 | 入藏编号 |
| `is_public_domain` | 46/49 | 是否公有领域 |
| `source` | 49/49 | 数据来源标记 |

### 样例数据

```
Title: Bodhisattva Avalokiteshvara (Guanyin)
Object Name: Figure
Culture: China
Period: Yuan dynasty (1271–1368)
Object Date: dated 1282
Medium: Wood (willow) with traces of pigment; single woodblock construction
Classification: Sculpture
Department: Asian Art
Dimensions: 39 1/4 in. (99.7 cm)
Image: https://images.metmuseum.org/CRDImages/as/original/DP223478.jpg
```

---

## 2. 吉美博物馆 — guimet_museum

**数据来源**: 爬取 [China 藏品页](https://www.guimet.fr/en/collections/china) + 详情页
**爬取策略**: BeautifulSoup 解析 Drupal 静态 HTML

### 字段说明

| 字段 | 覆盖度 | 说明 |
|---|---|---|
| `title` | 9/9 | 藏品名称 |
| `detail_url` | 8/9 | 藏品详情页链接 |
| `image_url` | 9/9 | 图片链接 |
| `description` | 8/9 | 英文描述 |
| `period` | 8/9 | 年代/时期 |
| `dimensions` | 8/9 | 尺寸 |
| `region_ou_domaine` | 8/9 | 所属区域（China） |
| `type_d_objet` | 部分 | 物件类型（Bowl, Figure...） |
| `materiaux` | 部分 | 材质 |
| `numero_d_inventaire` | 部分 | 馆藏编号 |
| `acquisition` | 部分 | 来源/入藏方式 |

### 样例数据

```
Title: Jade Bowl, known as "Mazarin Bowl"
Description: This outstanding piece, archaising and mannerist, is a testimony of Ming sculpture.
Period: 16th century
Dimensions: 4.7 x 13 cm
Region: China
Image: https://www.guimet.fr/sites/default/files/styles/width_1220px/public/2023-10/mr204-2.jpg
```

```
Title: Screen with twelve leaves and a hundred birds
Period: Dated 1725, Qing Dynasty, Reign of Yongzheng (1722-1735)
Dimensions: H. 263 x L. 725 cm
```

---

## 3. 大英博物馆 — british_museum

**数据来源**: 通过 Playwright（Chromium 浏览器）绕过 Cloudflare，拦截内部 `/_search` API
**搜索条件**: `place[]=China`

### 字段说明

| 字段 | 覆盖度 | 说明 |
|---|---|---|
| `title` | 100/100 | 物件名称分类 |
| `object_name` | 100/100 | 物件名称 |
| `object_type` | 18/100 | 物件类型 |
| `period` | 33/100 | 生产年代 |
| `material` | 部分 | 材质（需详情页，待完善） |
| `findspot` | 88/100 | 出土地/发现地 |
| `museum_number` | 100/100 | 馆藏编号 |
| `image_url` | 37/100 | 图片链接（约 1/3 有图） |
| `object_url` | 100/100 | 详情页链接 |

### 样例数据

```
Title: abacus
Object Name: abacus
Findspot: Found/Acquired: China
Museum Number: As.3593
Image: https://media.britishmuseum.org/Repository/Documents/2014_11/8_16/...large_01381495_001.jpg
```

```
Title: figure / trident / 'khar-gsil
Period: 1801-2000
Findspot: Found/Acquired: Tibet
Museum Number: 1948,0716.30
```

> ⚠️ 注意: 大英博物馆当前仅获取到搜索列表数据（100 条/页），详情页的完整元数据（材质、文化、具体描述）需进一步爬取每个详情页，但这需要额外的 Playwright 请求。

---

## 4. 布鲁克林植物园 — brooklyn_botanic

**数据来源**: 爬取植物展示页的图片描述
**说明**: 本数据与"中国流失文物"主题无关，属于原项目遗留模块

### 字段

| 字段 | 说明 |
|---|---|
| `title` | 图片描述文本 |
| `plant_name` | 植物名（提取自描述） |
| `collection` | 所属合集 |
| `image_url` | 图片链接 |

---

## 数据使用

### 查看 CSV 数据
```bash
# 直接用 Excel/WPS 打开 crawlers/brooklyn/data/raw/*.csv
# 或用 Python
venv/Scripts/python -c "
import csv, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('crawlers/brooklyn/data/raw/met_museum.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        print(row['title'], '|', row.get('period', ''), '|', row.get('culture', ''))
"
```

### 查看 JSONL 数据
```bash
venv/Scripts/python -c "
import json
with open('crawlers/brooklyn/data/raw/met_museum.jsonl', encoding='utf-8') as f:
    for line in f:
        item = json.loads(line)
        print(item['title'], '-', item.get('period', ''))
"
```
