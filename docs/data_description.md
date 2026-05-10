# 知识图谱子系统 - 数据爬取字段说明与验收文档

## 1. 字段说明表

爬取的数据统一保存为 UTF-8 编码的 CSV 文件，包含以下必填与建议填字段：

| 英文字段名 | 中文说明 | 是否必填 | 数据类型 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `object_id` | 文物唯一标识符 | 必填 | 字符串 | `25247` 或 `obj_25247` |
| `title` | 文物名称 | 必填 | 字符串 | `Tree Peonies in Full Bloom` |
| `period` | 年代/时期 | 必填 | 字符串 | `Qing dynasty (1644–1911)` |
| `type` | 文物类型 | 必填 | 字符串 | `Painting`, `Ceramics`, `Jade` |
| `material` | 材质 | 建议 | 字符串 | `Hanging scroll; ink and colors on silk` |
| `description` | 文物介绍 | 必填 | 字符串 | `This painting depicts...` (已清洗HTML标签) |
| `dimensions` | 尺寸 | 建议 | 字符串 | `116.8 × 59.7 cm (46 × 23 1/2 in.)` |
| `museum` | 所属博物馆 | 必填 | 字符串 | `Art Institute of Chicago` |
| `location` | 博物馆所在地 | 必填 | 字符串 | `Chicago, USA` |
| `detail_url` | 文物详情页URL | 必填 | 字符串 | `https://www.artic.edu/artworks/25247` |
| `image_url` | 图片原始下载链接 | 必填 | 字符串 | `https://www.artic.edu/iiif/2/.../full/full/0/default.jpg` |
| `image_path` | 本地图片存储路径 | 必填 | 字符串 | `images/chicago/obj_25247.jpg` |
| `credit_line` | 版权/来源说明 | 建议 | 字符串 | `Gift of ...` |
| `accession_number` | 藏品编号 | 建议 | 字符串 | `2000.12` |
| `crawl_date` | 爬取日期 | 必填 | 日期 | `2026-05-10` |

---

## 2. 爬取说明

*(本部分将在所有爬虫开发完成后补充完整)*

*   **芝加哥艺术博物馆 (Art Institute of Chicago)**
    *   **接口/难点**：提供官方基于 ElasticSearch 的只读 API。
    *   **解决方案**：采用 `requests` 请求 `https://api.artic.edu/api/v1/artworks/search`，利用 `fields` 参数选取对应字段；查询词限定 `q=Chinese` 并在结果中通过脚本二次校验 `place_of_origin` 或 `title`。
    *   **原图解析**：通过官方提供的 IIIF Image API 拼接规则 `.../full/full/0/default.jpg` 获取最高清晰度的原始图片。
*   **普林斯顿大学艺术博物馆 (Princeton University Art Museum)**
    *   **接口/难点**：待记录。
*   **布鲁克林艺术博物馆 (Brooklyn Museum)**
    *   **接口/难点**：待记录。

---

## 3. 数据统计

*(爬取任务正在后台运行，待所有数据抓取完成后如实回填本节)*

| 博物馆名称 | 爬取记录数 | 图片下载成功率 | 主要字段缺失情况说明 |
| :--- | :--- | :--- | :--- |
| Art Institute of Chicago | (运行中) | - | - |
| Princeton University Art Museum | 0 | - | - |
| Brooklyn Museum | 0 | - | - |
| **汇总** | **-** | **-** |  |

---

## 4. 数据质量自查报告

*(需抽取数据填入此报告以满足验收要求)*

1.  **必填字段完整率检查：**
    *   `object_id`, `title`, `detail_url`, `image_url`, `crawl_date` 均无空值。 (待最终代码运行后检查确认)
2.  **图片有效性验证：**
    *   随机抽查 20 条记录的本地 `image_path`，确保均为独立的高清大图，而非网页缩略图，且文件能正常打开。 (待人工/脚本抽检)
3.  **编码正确性：**
    *   利用 Pandas 读取生成的 `.csv` 文件，确认未出现由于逗号截断或换行符异常导致的格式错乱，且中文字符无乱码问题。
4.  **URL 有效性验证：**
    *   随机抽查 10 条 `detail_url`，测试返回 HTTP HTTP 200，并与博物馆页面相符。