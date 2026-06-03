# 知识图谱构建子系统

编写程序从海外博物馆网站爬取中国文物信息，经数据清洗、建模与存储，构建结构化的海外文物知识图谱，为知识服务、问答及可视化功能提供数据基础。主要包括以下功能：

**（1）数据爬取**

爬取至少3家指定海外博物馆的全部中国文物信息（博物馆列表见附录），爬取内容至少包括：文物名称、文物图片（原图）、年代、类型、材质、介绍文本、文物详情页URL。数据按规定格式保存（具体格式见附录），以UTF-8编码输出为CSV文件，并提交字段说明文档。

技术要求：需处理反爬机制；图片需解析原始地址下载，不得仅保存缩略图；爬取完成后需统计各博物馆文物数量并核验数据完整性。

**（2）数据清洗与质量控制**

对爬取的原始数据进行清洗处理，主要包括：

字段标准化：统一年代格式（如"公元前206年"统一表示方式）、文物类型分类等；

去重处理：识别并合并同一文物的重复记录；

图片有效性验证：检测图片链接是否可正常访问，过滤无效图片。

**（3）数据建模**

将清洗后的数据转化为三元组形式（主体-谓词-客体），建议参考CIDOC-CRM文化遗产领域本体标准进行建模。至少需要定义以下实体类型和关系：

实体类型：文物（Artifact）、博物馆（Museum）、朝代（Dynasty）、艺术家（Artist）、地点（Location）等；

关系类型：收藏于、创作于、属于朝代、材质为、类型为等。

**（4）数据补充**

针对基础数据中存在的信息缺失，从外部来源进行定向补充：

从百度百科、维基百科等爬取信息，例如书画作家生平、朝代背景、文物介绍等信息；

补充数据须与原始数据建立关联，并标注来源与补充日期。

**（5）实体对齐与去重**

不同博物馆可能收藏同一艺术家的作品或记录相同的历史实体，需进行跨数据源的实体对齐：

对艺术家、朝代、地点等共享实体进行识别与合并；

建立实体唯一标识符（URI），避免知识图谱中出现重复节点；

对齐结果须可追溯，保留原始来源信息。

**（6）数据存储**

建立双层存储架构，分别满足图查询和业务查询需求：

图数据库（Neo4j 或 Virtuoso）：存储全部三元组，支持图查询、关系遍历与SPARQL检索；可选发布为链接开放数据（LOD）；

关系型数据库（MySQL 或其他）：存储文物详细数据、用户数据及系统业务数据，支持高效的结构化查询。

**（7）数据更新与增量爬取**

为保持知识图谱的时效性，系统应支持定期数据更新：

支持增量爬取，仅爬取上次爬取后新增或更新的文物记录，避免全量重复下载；

记录每次爬取的时间、数量与变更详情；

对更新的实体数据自动触发三元组重建与图数据库同步。

# 补充要求和资料

**一、知识图谱构建相关**

**（1）CIDOC-CRM 文化遗产领域本体标准**

CIDOC-CRM 是文化遗产领域信息整合的理论与实践工具，已被国际标准化组织采纳为 ISO 21127:2023 标准，是文化遗产信息受控交换的国际标准。该标准在中国也有等效采标版本 GB/T 37965-2019《信息与文献 文化遗产信息交换参考本体》，可在中国标准查询系统中获取。

官方文档：

<https://cidoc-crm.org/html/cidoc_crm_v7.1.1_with_translations.html>

官网主页：<https://cidoc-crm.org/>

维基百科介绍：

<https://en.wikipedia.org/wiki/CIDOC_Conceptual_Reference_Model>

**（2）知识图谱建模工具**

①Protégé（斯坦福大学，免费开源，推荐）

Protégé 是斯坦福大学开发的免费开源本体编辑器，被全球研究人员、组织和政府机构广泛用于构建和管理本体。提供本地桌面版（Protégé Desktop）和在线协作版（WebProtégé）两种形式，完整支持 W3C 的 OWL 2 标准。 Protégé适合在建模阶段设计和可视化文物知识图谱的类、属性和关系结构，是学术界最常用的本体开发工具。

官网：https://protege.stanford.edu/

GitHub：https://github.com/protegeproject/protege

适用场景：本体设计、OWL/RDF 结构可视化、一致性验证

② RMLMapper / Morph-KGC（数据到RDF映射，推荐）

RMLMapper 是 RML（RDF Mapping Language）规范的参考实现，支持将 CSV、JSON、XML、关系型数据库等多种格式的数据转化为高质量的链接数据（RDF）。Morph-KGC 是一个更强大的 RML 引擎，支持大规模数据，可从命令行运行或作为 Python 库调用。 Fairplus对于本课程设计而言，可直接用 RML 规则将爬取的 CSV 格式文物数据映射为三元组，无需手动编写转换代码。

RMLMapper GitHub：https://github.com/RMLio/rmlmapper-java

Morph-KGC GitHub：https://github.com/morph-kgc/morph-kgc

YARRRML（RML 的可读性更强的语法）：https://rml.io/yarrrml/

适用场景：将爬取的 CSV/JSON 文物数据批量转化为 RDF 三元组

③ RDFLib（Python 库，轻量推荐）

纯 Python 实现的 RDF 处理库，支持三元组的读写、SPARQL 查询、格式转换等操作，无需额外安装数据库或图形界面，适合在代码中直接操作和生成三元组数据。

官方文档：https://rdflib.readthedocs.io/en/stable/

GitHub：https://github.com/RDFLib/rdflib

适用场景：编程方式生成和操作三元组，与 Python 爬虫代码无缝集成

④ Karma

USC ISI 开发的半自动数据建模工具，支持将结构化数据映射到本体。

项目地址：<https://github.com/usc-isi-i2/Web-Karma>

说明：网络中文资料较少，建议直接参考项目 Wiki 文档

**（3）Neo4j 图数据库**

Neo4j 支持从非结构化数据构建知识图谱的完整流水线，包括数据加载、文本分块、实体与关系抽取、知识图谱写入与实体解析等组件，并可与大语言模型集成构建 GraphRAG 应用。 [Neo4j](https://neo4j.com/developer/genai-ecosystem/importing-graph-from-unstructured-data/)

官方文档：<https://neo4j.com/docs/>

知识图谱构建指南：

<https://neo4j.com/developer/genai-ecosystem/importing-graph-from-unstructured-data/>

GitHub 仓库：<https://github.com/neo4j/neo4j>

**（4）Virtuoso 开源图数据库**

支持 SPARQL 查询与链接开放数据（LOD）发布，适合大规模三元组存储。

GitHub 仓库：<https://github.com/openlink/virtuoso-opensource>

官方网站：<https://virtuoso.openlinksw.com/>

**（5）LangChain 知识图谱与 RAG 开发框架**

LangChain 提供了完整的检索增强生成（RAG）支持，可将外部知识库与大语言模型结合，解决模型知识截止和幻觉问题，建议用于知识问答子系统的开发。

官方文档：<https://docs.langchain.com/>

RAG 入门指南：<https://www.langchain.com/retrieval>

**二、数据爬取相关**

**（6）Scrapy 网络爬虫框架**

Python 生态中最主流的爬虫框架，支持异步爬取、中间件扩展与数据管道，适合大规模博物馆数据爬取。

官方文档：<https://docs.scrapy.org/en/latest/>

GitHub 仓库：<https://github.com/scrapy/scrapy>

**（7）Selenium / Playwright 动态页面爬取**

部分博物馆网站采用 JavaScript 动态渲染，需使用浏览器自动化工具爬取。

Selenium 官方文档：<https://www.selenium.dev/documentation/>

Playwright 官方文档：<https://playwright.dev/python/docs/intro>

**（8）Pandas 数据处理库**

用于 CSV 格式数据的读写、清洗与字段处理，避免编码格式错误。

官方文档：<https://pandas.pydata.org/docs/>

**五、参考博物馆与平台**

**（14）克利夫兰艺术博物馆**（含高级搜索与 Open Access API）

搜索界面：<https://www.clevelandart.org/art/collection/search>

Open Access 数据集：<https://openaccess-api.clevelandart.org/>

**（15）大都会艺术博物馆 Open Access API**

提供约 48 万件文物的结构化数据，支持 JSON 格式直接调用，可作为爬取数据的补充来源。

API 文档：<https://metmuseum.github.io/>

**（16）全历史知识图谱平台**

国内优秀的历史人文知识图谱可视化案例，可参考其关系图谱与时间轴的交互设计。

网站：<https://www.allhistory.com/>

**（17）故宫博物院 App**

国内博物馆移动端 App 的优秀参考案例，可参考掌上博物馆的功能设计与交互方式。

官网：<https://www.dpm.org.cn/Creative.html#app>

# 数据爬取格式及要求

**（1）数据格式要求**

所有爬取数据须遵循以下格式规范：

编码格式：统一使用 UTF-8 编码保存，避免中文乱码；

文件格式：保存为 CSV 格式，建议使用 Python 的 csv 或 pandas 库进行读写，防止出现分隔符冲突、换行符异常等格式错误；

文件命名：按博物馆命名，例如 cleveland\_museum.csv、metropolitan\_museum.csv；

图片存储：图片文件按博物馆分文件夹存放，文件名与 CSV 中的文物 ID 一一对应，例如 images/cleveland/obj\_12345.jpg；

各组须自行验证导出的 CSV 文件可在 Excel 或 pandas 中正常打开，确认无乱码、无格式错误后方可提交。

**（2）数据字段要求**

每条文物记录至少包含以下字段（部分字段如博物馆网站未提供可标注为空）：

| **字段名（英文）** | **中文说明** | **是否必填** | **备注** |
| --- | --- | --- | --- |
| object\_id | 文物唯一标识符 | 必填 | 使用博物馆原始ID或自行生成 |
| title | 文物名称 | 必填 | 优先保留英文原名，有中文译名则补充 |
| period | 年代/时期 | 必填 | 如"Tang Dynasty"或"618–907 AD" |
| type | 文物类型 | 必填 | 如 Painting、Ceramics、Bronze 等 |
| material | 材质 | 建议填写 | 如 Silk、Bronze、Jade 等 |
| description | 文物介绍 | 必填 | 爬取网站提供的原始描述文本 |
| dimensions | 尺寸 | 建议填写 | 如"H. 30 cm × W. 20 cm" |
| museum | 所属博物馆 | 必填 | 填写博物馆完整英文名称 |
| location | 博物馆所在地 | 必填 | 城市、国家 |
| detail\_url | 文物详情页URL | 必填 | 文物在博物馆网站上的原始页面链接 |
| image\_url | 图片原始下载链接 | 必填 | 须为原图地址，而非缩略图 |
| image\_path | 本地图片存储路径 | 必填 | 图片下载后的相对路径 |
| credit\_line | 版权/来源说明 | 建议填写 | 博物馆提供的版权声明 |
| accession\_number | 藏品编号 | 建议填写 | 博物馆馆藏编号 |
| crawl\_date | 爬取日期 | 必填 | 格式：YYYY-MM-DD |

注意事项：

图片爬取须注意解析原图地址，部分网站（如大都会博物馆）需要通过API获取高清原图链接，不可仅保存页面展示的缩略图；

对于缺失字段，用空字符串填充，不可省略该列；

文物介绍若为英文，建议同时保留原文，后续可通过翻译API补充中文描述。

**（3）数据量要求**

每组须爬取指定的3家博物馆，筛选其中的中国文物；

最终提交数据总量不少于5000件文物的有效记录（含图片）。

**（4）数据质量验收标准**

提交前须自行检查以下内容，并在说明文档中附上检查结果：

必填字段完整率：object\_id、title、detail\_url、image\_url、crawl\_date 五个必填字段不得有空值；

图片有效性：随机抽查20条记录，验证图片文件可正常打开，且为原图而非缩略图；

编码正确性：读取 CSV 后打印前5行，确认中文字符无乱码；

URL 有效性：随机抽查10条 detail\_url，验证链接可正常访问。

**（5）说明文档要求**

每组须提交一份数据说明文档（Markdown 或 Word 格式），内容包括：

字段说明表：列出所有字段的英文名、中文含义、数据类型与示例值，例如：

| **英文字段名** | **中文说明** | **数据类型** | **示例** |
| --- | --- | --- | --- |
| period | 文物年代 | 字符串 | Tang Dynasty |
| crawl\_date | 爬取日期 | 日期 | 2024-03-15 |

爬取说明：说明各博物馆爬取时遇到的技术难点及解决方案，如反爬处理方式、原图地址解析方法等

数据统计：各博物馆爬取记录数、图片下载成功率、字段缺失情况统计

数据质量自查报告：按照第（4）条验收标准的自查结果

# 数据爬取网站

每团需爬取3家海外博物馆。为平衡各组爬取数量，请按照下表爬取。如需调换，需要两组组长同意后，上报助教老师

表1 网站分配

|  |  |  |  |
| --- | --- | --- | --- |
| **团号** | **爬取博物馆序号（对应见下表）** | | |
| 5团 | 5 | 10 | 15 |

表2 海外博物馆名称、网址和中国文物数量

|  |  |  |
| --- | --- | --- |
| **序号** | **博物馆名** | **网址** |
| 1 | 克利夫兰 | <https://www.clevelandart.org/art/collection/search> |
| 2 | 大都会 | <https://www.metmuseum.org/art/collection> |
| 3 | 史密斯 | <https://www.si.edu/openaccess> |
| 4 | 弗利尔美术馆 | [https://www.freersackler.si.edu/collections/ https://asia.si.edu/collection-area/chinese-art/](https://www.freersackler.si.edu/collections/) |
| 5 | 普林斯顿大学艺术博物馆 | <https://artmuseum.princeton.edu/search/collections> |
| 6 | 纳尔逊-阿特金斯艺术博物馆 | <https://art.nelson-atkins.org/collections> |
| 7 | 旧金山亚洲艺术博物馆 | <http://searchcollection.asianart.org/view/objects/asimages/23140?t:state:flow=925e5439-97d7-4a9b-9733-62cdb565a1d9> |
| 8 | 波士顿美术馆 | <https://www.mfa.org/collections/search> |
| 9 | 明尼阿波利斯艺术博物馆 | <https://collections.artsmia.org/> |
| 10 | 芝加哥艺术博物馆 | <https://www.artic.edu/collection?place_ids=China> |
| 11 | 宾夕法尼亚大学考古与人类学博物馆 | <https://www.penn.museum/> |
| 12 | 费城艺术博物馆 | <https://www.philamuseum.org/collections/search.html> |
| 13 | 哈佛大学 | <https://harvardartmuseums.org/collections?q=chinese> |
| 14 | 美国自然历史博物馆 | <https://anthro.amnh.org/collections> |
| 15 | 布鲁克林艺术博物馆 | <https://www.brooklynmuseum.org/opencollection/collections> |

注：**国外博物馆**一般可在博物馆网站文物搜索栏中使用“chinese”，“china”等关键字进行筛选，还可在网站上提供的location等字段进行筛选，以得到中国文物。