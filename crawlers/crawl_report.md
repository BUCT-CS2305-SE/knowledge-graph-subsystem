# 爬取数据报告

> 生成时间: 2026-05-27
> 爬虫目录: `crawlers/`
> 输出目录: `crawlers/data/raw/`

---

## 概览

| 博物馆 | 爬取方式 | 数据条数 | 字段数 | 文件 |
|---|---|---|---|---|
| 普林斯顿大学艺术博物馆 (Princeton) | Playwright + XHR 内部 API | 3,600 条 | 21 | `princeton.jsonl` / `.csv` |
| 芝加哥艺术博物馆 (Chicago) | REST API（免费开放） | 1,000 条 | 23 | `chicago.jsonl` / `.csv` |
| 布鲁克林艺术博物馆 (Brooklyn Museum) | Playwright + APIRequestContext | 720 条 | 27 | `brooklyn_museum.jsonl` / `.csv` |
| 大都会艺术博物馆 (Met) | REST API（免费开放） | 49 条 | 29 | `met_museum.jsonl` / `.csv` |
| 吉美博物馆 (Guimet) | HTML 页面爬取（Drupal） | 9 条 | 17 | `guimet_museum.jsonl` / `.csv` |
| 大英博物馆 (British Museum) | Playwright 浏览器 + ES API | 100 条 | 19 | `british_museum.jsonl` / `.csv` |
| 布鲁克林植物园 (BBG) | HTML 页面爬取 | 2 条 | 18 | `brooklyn_botanic.jsonl` / `.csv` |
| **合计** | | **5,480 条** | | |

**输出格式**: 同时输出 JSONL（每行一条 JSON）和 CSV（表格，可用 Excel/WPS 打开）。

---

## 标准字段说明（15 字段）

所有爬虫统一输出以下 15 个标准字段，额外字段以 `_` 前缀标记：

| 字段名 | 中文说明 | 必填 | 备注 |
|---|---|---|---|
| `object_id` | 文物唯一标识符 | 必填 | 使用博物馆原始 ID |
| `title` | 文物名称 | 必填 | 优先保留英文原名 |
| `period` | 年代/时期 | 必填 | 如 "Tang Dynasty" |
| `type` | 文物类型 | 必填 | 如 Painting、Ceramics |
| `material` | 材质 | 建议填写 | 如 Silk、Bronze |
| `description` | 文物介绍 | 必填 | 原始描述文本 |
| `dimensions` | 尺寸 | 建议填写 | 如 "H. 30 cm × W. 20 cm" |
| `museum` | 所属博物馆 | 必填 | 完整英文名称 |
| `location` | 博物馆所在地 | 必填 | 城市、国家 |
| `detail_url` | 文物详情页 URL | 必填 | 原始页面链接 |
| `image_url` | 图片原始下载链接 | 必填 | 原图地址 |
| `image_path` | 本地图片存储路径 | 必填 | 下载后路径（需 --download-images） |
| `credit_line` | 版权/来源说明 | 建议填写 | 版权声明 |
| `accession_number` | 藏品编号 | 建议填写 | 馆藏编号 |
| `crawl_date` | 爬取日期 | 必填 | 格式：YYYY-MM-DD |

---

## 1. 普林斯顿大学艺术博物馆 — princeton（#5）

**数据来源**: 内部 API `data.artmuseum.princeton.edu/collection/msearch`
**爬取策略**: Playwright 打开主页面鉴权后，通过 XHR 请求内部 API（需 `withCredentials: true`）
**搜索条件**: `q=china&sort=relevance`
**数据量**: 3,600 条（150 页 × 24 条/页）
**总库存**: 58,716 件

### 字段覆盖度

| 标准字段 | 覆盖度 | 说明 |
|---|---|---|
| `object_id` | 3600/3600 (100%) | |
| `title` | 3570/3600 (99%) | |
| `period` | 3402/3600 (94%) | |
| `type` | 0/3600 (0%) | API 未提供独立分类字段 |
| `material` | 3451/3600 (96%) | 映射自 `medium` |
| `description` | 753/3600 (21%) | 仅部分藏品有描述文本 |
| `dimensions` | 0/3600 (0%) | API 未返回尺寸数据 |
| `museum` | 3600/3600 (100%) | |
| `location` | 3600/3600 (100%) | |
| `detail_url` | 3600/3600 (100%) | |
| `image_url` | 3579/3600 (99%) | 映射自 `primaryimage` |
| `image_path` | 0/3600 (0%) | 需 `--download-images` |
| `credit_line` | 0/3600 (0%) | API 未提供版权信息 |
| `accession_number` | 3600/3600 (100%) | 映射自 `objectnumber` |
| `crawl_date` | 3600/3600 (100%) | |

**额外字段**（以 `_` 前缀标记）:

| 字段 | 说明 |
|---|---|
| `_displayculture` | 文化归属（如 Chinese） |
| `_displaydate` | 显示用日期描述 |
| `_displayperiod` | 显示用时期描述 |
| `_objectnumber` | 原始馆藏编号冗余 |
| `_medium_detail` | 材质详细描述 |
| `_image_valid` | 图片 URL 有效性标记 |

### 技术难点

- 直接请求 API 返回 401 未授权，需通过 Playwright 浏览器先加载前端页面获取鉴权 Cookie
- 使用 `XMLHttpRequest` 需设置 `withCredentials = true` 携带认证信息
- `page.goto()` 到藏品搜索页面超时，改用 `wait_until='commit'` 及 `set_content()` 规避

---

## 2. 芝加哥艺术博物馆 — chicago（#10）

**数据来源**: 官方 REST API `api.artic.edu/api/v1/artworks/search`
**爬取策略**: 直接 HTTP 请求（无需 API Key），使用 `fields` 参数获取完整字段
**搜索条件**: `q=china`
**数据量**: 1,000 条（10 页 × 100 条/页）
**总库存**: 约 16,000+ 条结果

### 字段覆盖度

| 标准字段 | 覆盖度 | 说明 |
|---|---|---|
| `object_id` | 1000/1000 (100%) | |
| `title` | 1000/1000 (100%) | |
| `period` | 999/1000 (100%) | 映射自 `date_display` |
| `type` | 0/1000 (0%) | API 中 `classification_display` 作为 `_classification` 保存 |
| `material` | 1000/1000 (100%) | 映射自 `medium_display` |
| `description` | 0/1000 (0%) | API 搜索接口不返回描述文本 |
| `dimensions` | 985/1000 (98%) | |
| `museum` | 1000/1000 (100%) | |
| `location` | 1000/1000 (100%) | |
| `detail_url` | 1000/1000 (100%) | |
| `image_url` | 900/1000 (90%) | 需构造 IIIF URL |
| `image_path` | 0/1000 (0%) | 需 `--download-images` |
| `credit_line` | 1000/1000 (100%) | |
| `accession_number` | 0/1000 (0%) | API 搜索接口未返回 |
| `crawl_date` | 1000/1000 (100%) | |

**额外字段**（以 `_` 前缀标记）:

| 字段 | 说明 |
|---|---|
| `_artist` | 艺术家姓名 |
| `_place_of_origin` | 产地 |
| `_style` | 艺术风格 |
| `_department` | 所属部门 |
| `_technique` | 工艺技法 |
| `_image_id` | IIIF 图片 ID |
| `_classification` | 分类（替代标准 `type`） |
| `_image_valid` | 图片 URL 有效性标记 |

### 技术难点

- API 默认只返回 `id` 和 `title`，需用 `fields` 参数明确指定需要的字段列表
- 图片 URL 需按 IIIF 协议构造：`https://www.artic.edu/iiif/2/{image_id}/full/843,/default.jpg`
- 第 11 页起 API 返回 429/403（速率限制），最多获取 1,000 条。已添加重试和 2.5 秒延迟，但硬限制无法绕过

---

## 3. 布鲁克林艺术博物馆 — brooklyn_museum（#15）

**数据来源**: Sanity CMS API `search.brooklynmuseum.org/api/search`
**爬取策略**: Playwright 打开浏览器后，使用 `page.request.get()`（APIRequestContext）调用 JSON API
**搜索条件**: `type=collectionObject`
**数据量**: 720 条（30 页 × 24 条/页）
**总库存**: 96,299 件

### 字段覆盖度

| 标准字段 | 覆盖度 | 说明 |
|---|---|---|
| `object_id` | 720/720 (100%) | 映射自 `sourceId` |
| `title` | 720/720 (100%) | |
| `period` | 720/720 (100%) | 映射自 `dates` |
| `type` | 720/720 (100%) | 映射自 `classification` |
| `material` | 0/720 (0%) | API 未提供材质字段 |
| `description` | 47/720 (7%) | 仅少部分藏品有描述 |
| `dimensions` | 0/720 (0%) | API 未返回尺寸数据 |
| `museum` | 720/720 (100%) | |
| `location` | 720/720 (100%) | |
| `detail_url` | 720/720 (100%) | 映射自 `url` |
| `image_url` | 569/720 (79%) | 映射自 `imageUrl` |
| `image_path` | 0/720 (0%) | 需 `--download-images` |
| `credit_line` | 0/720 (0%) | API 未提供版权信息 |
| `accession_number` | 720/720 (100%) | 映射自 `accessionNumber` |
| `crawl_date` | 720/720 (100%) | |

**额外字段**（以 `_` 前缀标记）:

| 字段 | 说明 |
|---|---|
| `_source` | 数据来源标记 |
| `_sourceId` | 原始 ID 冗余 |
| `_sourceType` | 来源类型 |
| `_url` | 原始 URL 冗余 |
| `_imageUrl` | 原始图片 URL 冗余 |
| `_accessionNumber` | 原始入藏编号冗余 |
| `_onView` | 是否正在展出 |
| `_classification` | 分类（冗余） |
| `_startYear` | 起始年份 |
| `_dates` | 日期描述 |
| `_endYear` | 结束年份 |
| `_image_valid` | 图片 URL 有效性标记 |

### 技术难点

- 使用 `page.evaluate()` 内 XHR 请求遭遇 CORS 限制，改用 `page.request.get()`（Playwright 的 APIRequestContext）成功获取
- API 返回 JSON 中 `total` 位于 `metadata.total`，`maxPages` 位于 `metadata.maxPages`
- `page.goto()` 到 JSON API 端点超时（Playwright 等待页面加载完成，但 JSON 不是 HTML），使用 APIRequestContext 解决

---

## 4. 大都会艺术博物馆 — met_museum

**数据来源**: [Met Collection API](https://metmuseum.github.io/)（无需 API Key）
**搜索条件**: `q=China&hasImages=true`
**数据量**: 49 条

### 字段覆盖度

| 标准字段 | 覆盖度 | 说明 |
|---|---|---|
| `object_id` | 49/49 (100%) | |
| `title` | 49/49 (100%) | |
| `period` | 18/49 (37%) | |
| `type` | 43/49 (88%) | 映射自 `classification` |
| `material` | 49/49 (100%) | 映射自 `medium` |
| `description` | 0/49 (0%) | API 不提供描述文本 |
| `dimensions` | 49/49 (100%) | |
| `museum` | 49/49 (100%) | |
| `location` | 49/49 (100%) | |
| `detail_url` | 49/49 (100%) | 映射自 `object_url` |
| `image_url` | 46/49 (94%) | |
| `image_path` | 0/49 (0%) | 需 `--download-images` |
| `credit_line` | 49/49 (100%) | |
| `accession_number` | 49/49 (100%) | |
| `crawl_date` | 49/49 (100%) | |

**额外字段**: `_culture`, `_dynasty`, `_reign`, `_artist`, `_artist_bio`, `_artist_nationality`, `_object_date`, `_department`, `_region`, `_country`, `_accession_year`, `_image_small`, `_is_public_domain`, `_image_valid`

---

## 5. 吉美博物馆 — guimet_museum

**数据来源**: 爬取 [China 藏品页](https://www.guimet.fr/en/collections/china) + 详情页
**爬取策略**: BeautifulSoup 解析 Drupal 静态 HTML
**数据量**: 9 条

### 字段覆盖度

| 标准字段 | 覆盖度 | 说明 |
|---|---|---|
| `object_id` | 9/9 (100%) | |
| `title` | 9/9 (100%) | |
| `period` | 8/9 (89%) | |
| `type` | 0/9 (0%) | |
| `material` | 0/9 (0%) | |
| `description` | 9/9 (100%) | |
| `dimensions` | 8/9 (89%) | |
| `museum` | 9/9 (100%) | |
| `location` | 9/9 (100%) | |
| `detail_url` | 8/9 (89%) | |
| `image_url` | 9/9 (100%) | |
| `image_path` | 0/9 (0%) | 需 `--download-images` |
| `credit_line` | 0/9 (0%) | |
| `accession_number` | 0/9 (0%) | |
| `crawl_date` | 9/9 (100%) | |

**额外字段**: `_category`, `_image_valid`

---

## 6. 大英博物馆 — british_museum

**数据来源**: 通过 Playwright 绕过 Cloudflare，拦截内部 `/_search` API
**搜索条件**: `place[]=China`
**数据量**: 100 条

### 字段覆盖度

| 标准字段 | 覆盖度 | 说明 |
|---|---|---|
| `object_id` | 100/100 (100%) | |
| `title` | 100/100 (100%) | |
| `period` | 33/100 (33%) | |
| `type` | 18/100 (18%) | |
| `material` | 0/100 (0%) | |
| `description` | 0/100 (0%) | |
| `dimensions` | 0/100 (0%) | |
| `museum` | 100/100 (100%) | |
| `location` | 100/100 (100%) | |
| `detail_url` | 100/100 (100%) | |
| `image_url` | 37/100 (37%) | |
| `image_path` | 0/100 (0%) | 需 `--download-images` |
| `credit_line` | 0/100 (0%) | |
| `accession_number` | 100/100 (100%) | 映射自 `museum_number` |
| `crawl_date` | 100/100 (100%) | |

**额外字段**: `_culture`, `_findspot`, `_object_name_detail`, `_image_valid`

---

## 数据质量自查

### 必填字段完整率

| 必填字段 | Princeton | Chicago | Brooklyn Museum |
|---|---|---|---|
| `object_id` | 100% | 100% | 100% |
| `title` | 99% | 100% | 100% |
| `detail_url` | 100% | 100% | 100% |
| `image_url` | 99% | 90% | 79% |
| `crawl_date` | 100% | 100% | 100% |

### 图片有效性

图片下载默认关闭（需 `--download-images` 参数）。当前 `image_path` 均为空，`_image_valid` 标记已随每条记录输出。

### 编码正确性

所有 CSV/JSONL 文件以 UTF-8 编码保存，经 Python `csv.DictReader` 读取验证，无中文乱码。

### 数据量验收

- 目标: ≥ 5,000 条
- 实际: **5,480 条**（Princeton 3,600 + Chicago 1,000 + Brooklyn Museum 720 + 其他 160）
- 达标: ✅

---

## 附录：爬取策略总结

| 博物馆 | 反爬机制 | 绕过方式 | 数据接口 |
|---|---|---|---|
| Princeton | 需要浏览器 Cookie 鉴权 | Playwright + XHR withCredentials | REST JSON |
| Chicago | 速率限制（10 页后限流） | 增加延迟、重试（接受 1,000 条限制） | REST JSON |
| Brooklyn Museum | 无直接反爬 | Playwright APIRequestContext | Sanity CMS JSON |
| Met Museum | 无 | 直接 requests | REST JSON |
| Guimet | 无 | BeautifulSoup HTML | Drupal HTML |
| British Museum | Cloudflare | Playwright 浏览器 | 内部 ES `/_search` |
| Brooklyn Botanic | 无 | BeautifulSoup HTML | HTML |