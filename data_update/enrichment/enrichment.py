"""
数据补充模块

从 百度百科 / Wikipedia 等外部来源为知识图谱中的共享实体（朝代 / 博物馆 / 艺术家 /
地点 / 文物类型）补充背景信息，并保留来源与补充日期，供后续 Neo4j 图谱写入使用。

默认 百度百科 优先（中文命中率高、不易被墙），Wikipedia 作为兜底。
实体名通常是英文，会先用百度翻译 API 译成中文再查百度百科。

输入：
    data_processing/alignment/nodes_periods.csv
    data_processing/alignment/nodes_museums.csv
    （可选）data_processing/alignment/nodes_types.csv
    （可选）data_processing/alignment/nodes_materials.csv

输出：
    data_update/enrichment/augmented_entities.json
    data_update/enrichment/augmented_entities.csv

字段：
    uri          实体唯一标识（http://kg.bjtu5.org/<kind>/<slug>）
    kind         period / museum / type / material
    name         实体名称（对齐后的标准名）
    description  补充说明
    source       来源站点（Wikipedia / Baidu Baike）
    source_url   原始来源链接
    enrich_date  补充日期 YYYY-MM-DD

用法：
    python3 -m data_update.enrichment.enrichment
    python3 data_update/enrichment/enrichment.py --kinds period museum
    python3 data_update/enrichment/enrichment.py --source baidu      # 仅百度百科
    python3 data_update/enrichment/enrichment.py --source wiki       # 仅维基百科
    python3 data_update/enrichment/enrichment.py --source both       # 百度优先, 维基兜底(默认)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]

# 输入路径优先级：
#   1) data_processing/alignment/neo4j_import/   （中文 + 双语版本，优先）
#   2) data_processing/alignment/                 （旧英文版本，兜底）
_ALIGN_CANDIDATES = [
    ROOT / "data_processing" / "alignment" / "neo4j_import",
    ROOT / "data_processing" / "alignment",
]


def _discover_align_dir() -> Path:
    for d in _ALIGN_CANDIDATES:
        if (d / "nodes_periods.csv").exists():
            return d
    return _ALIGN_CANDIDATES[-1]


ALIGN_DIR = _discover_align_dir()
OUT_DIR = ROOT / "data_update" / "enrichment"

URI_PREFIX = "http://kg.bjtu5.org"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_ZH_REST = "https://zh.wikipedia.org/api/rest_v1/page/summary/{title}"

USER_AGENT = "BUCT-KG-Enrichment/1.0 (course-project; contact: kg@bjtu5.org)"

# 百度百科词条页（解析 meta description 摘要）。openapi 接口已停用，故抓词条页。
BAIKE_ITEM_URL = "https://baike.baidu.com/item/{word}"
BAIDU_TRANSLATE_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"
# 复用清洗模块已配置好的百度翻译密钥
BAIDU_CONFIG_PATH = ROOT / "data_processing" / "cleaning" / "baidu_config.json"
# 浏览器 UA，避免百度百科返回反爬页
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


# ------------------------- 工具 -------------------------

def slugify(text: str) -> str:
    """将名称转化为 URI 中可用的 slug。"""
    text = (text or "").strip().lower()
    text = re.sub(r"[\s/]+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def make_uri(kind: str, name: str) -> str:
    return f"{URI_PREFIX}/{kind}/{slugify(name)}"


def http_get_json(url: str, timeout: int = 8) -> dict | None:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def http_get_text(url: str, timeout: int = 12) -> str | None:
    """抓取 HTML 文本（带浏览器 UA 与 gzip 解码）。"""
    req = Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept-Encoding": "gzip",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                import io
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            return raw.decode("utf-8", "ignore")
    except Exception:
        return None


# 网络可用性探测：连续 N 次 wiki 失败就提前退出，避免 pipeline 卡 30+ 分钟。
_FAIL_STREAK = {"count": 0}
_MAX_FAIL_STREAK = int(os.environ.get("KG_ENRICH_MAX_FAIL", "5"))


def _record_fail():
    _FAIL_STREAK["count"] += 1


def _record_ok():
    _FAIL_STREAK["count"] = 0


def _network_dead() -> bool:
    return _FAIL_STREAK["count"] >= _MAX_FAIL_STREAK


def core_name(name: str) -> str:
    """去掉括号中的年份/限定词，得到可在 Wikipedia 上命中的核心名。

    例如：
        'Qing dynasty (1644-1912)'   -> 'Qing dynasty'
        'Qing dynasty (c. 1975)'     -> 'Qing dynasty'
        'Modern period'              -> 'Modern period'
    """
    s = re.sub(r"\([^)]*\)", "", name).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _query_wiki(title: str) -> tuple[str, str, str] | None:
    encoded = quote(title.replace(" ", "_"))
    data = http_get_json(WIKI_REST.format(title=encoded))
    if data and data.get("extract"):
        url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        _record_ok()
        return data["extract"].strip(), "Wikipedia (en)", url
    data = http_get_json(WIKI_ZH_REST.format(title=encoded))
    if data and data.get("extract"):
        url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        _record_ok()
        return data["extract"].strip(), "Wikipedia (zh)", url
    _record_fail()
    return None


def fetch_wikipedia_summary(
    name: str, cache: dict[str, tuple[str, str, str] | None] | None = None
) -> tuple[str, str, str] | None:
    """先按原名查询，命中即返回；否则回退到去括号的核心名。

    使用可选的 cache 字典，对同一核心名只发起一次网络请求。
    """
    if not name or name.lower() == "unknown":
        return None

    # 1) 原名命中（典型如 "Brooklyn Museum"）
    if cache is not None and name in cache:
        result = cache[name]
    else:
        result = _query_wiki(name)
        if cache is not None:
            cache[name] = result
    if result:
        return result

    # 2) 回退到核心名（典型如 "Qing dynasty"）
    base = core_name(name)
    if not base or base == name:
        return None
    if cache is not None and base in cache:
        return cache[base]
    base_result = _query_wiki(base)
    if cache is not None:
        cache[base] = base_result
    return base_result


# ------------------------- 百度百科 -------------------------

_BAIDU_CFG: dict | None = None
# 已知英文实体名 -> 中文译名的本地映射，命中则免去翻译请求，更稳更准。
_ZH_OVERRIDES = {
    "Qing dynasty": "清朝",
    "Ming dynasty": "明朝",
    "Yuan dynasty": "元朝",
    "Song dynasty": "宋朝",
    "Tang dynasty": "唐朝",
    "Han dynasty": "汉朝",
    "Sui dynasty": "隋朝",
    "Jin dynasty": "晋朝",
    "Zhou dynasty": "周朝",
    "Shang dynasty": "商朝",
    "Qin dynasty": "秦朝",
    "Painting": "绘画",
    "Ceramic": "陶瓷",
    "Bronze": "青铜器",
    "Jade": "玉器",
    "Sculpture": "雕塑",
    "Textile": "纺织品",
    "Calligraphy": "书法",
    "Lacquer": "漆器",
    "Princeton University Art Museum": "普林斯顿大学艺术博物馆",
    "Art Institute of Chicago": "芝加哥艺术博物馆",
    "Brooklyn Museum": "布鲁克林博物馆",
}


def _load_baidu_cfg() -> dict | None:
    """加载百度翻译密钥（复用清洗模块的 baidu_config.json）。"""
    global _BAIDU_CFG
    if _BAIDU_CFG is not None:
        return _BAIDU_CFG or None
    if not BAIDU_CONFIG_PATH.exists():
        _BAIDU_CFG = {}
        return None
    try:
        with BAIDU_CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("app_id") and cfg.get("app_key"):
            _BAIDU_CFG = cfg
            return cfg
    except Exception:
        pass
    _BAIDU_CFG = {}
    return None


def to_chinese(name: str) -> str:
    """把英文实体名转成中文，供百度百科检索。

    优先用本地映射，其次调用百度翻译 API；都失败则原样返回。
    若本身已含中文则直接返回。
    """
    if not name:
        return name
    # 已含中文
    if any("\u4e00" <= c <= "\u9fff" for c in name):
        return name
    base = core_name(name)
    if base in _ZH_OVERRIDES:
        return _ZH_OVERRIDES[base]
    if name in _ZH_OVERRIDES:
        return _ZH_OVERRIDES[name]

    cfg = _load_baidu_cfg()
    if not cfg:
        return base or name
    app_id, app_key = cfg["app_id"], cfg["app_key"]
    salt = str(random.randint(32768, 65536))
    sign = hashlib.md5((app_id + base + salt + app_key).encode()).hexdigest()
    params = (f"?q={quote(base)}&from=en&to=zh&appid={app_id}"
              f"&salt={salt}&sign={sign}")
    data = http_get_json(BAIDU_TRANSLATE_URL + params)
    if data and data.get("trans_result"):
        return data["trans_result"][0].get("dst", base) or base
    return base or name


def _query_baike(word: str) -> tuple[bool, tuple[str, str, str] | None]:
    """抓取百度百科词条页，从 meta description 提取摘要。

    返回 (网络是否可达, 结果)。结果为 (摘要, 来源, url) 或 None（词条无摘要）。
    openapi 接口已停用，改为解析词条页 meta。
    """
    if not word:
        return True, None
    url = BAIKE_ITEM_URL.format(word=quote(word))
    html = http_get_text(url)
    if html is None:
        # 网络层面失败（超时/连接错误），计入断网判定
        return False, None
    m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
    if not m:
        m = re.search(
            r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
    if not m:
        return True, None
    abstract = m.group(1).strip()
    # 过滤百度百科默认的占位/空词条文案
    if not abstract or "百度百科" in abstract and len(abstract) < 25:
        return True, None
    return True, (abstract, "Baidu Baike", url)


def fetch_baike_summary(
    name: str, cache: dict[str, tuple[str, str, str] | None] | None = None
) -> tuple[str, str, str] | None:
    """将实体名译成中文后查询百度百科，带缓存。"""
    if not name or name.lower() == "unknown":
        return None
    zh = to_chinese(name)
    key = f"baike::{zh}"
    if cache is not None and key in cache:
        return cache[key]
    reachable, result = _query_baike(zh)
    # 仅网络不可达才计入断网；词条查不到属正常 miss，不触发 abort
    if reachable:
        _record_ok()
    else:
        _record_fail()
    if cache is not None:
        cache[key] = result
    return result


def fetch_zhwiki_by_chinese(
    name: str, cache: dict[str, tuple[str, str, str] | None] | None = None
) -> tuple[str, str, str] | None:
    """先把实体名译成中文，再查中文维基百科（命中率远高于英文名直查）。"""
    if not name or name.lower() == "unknown":
        return None
    zh = to_chinese(name)
    key = f"zhwiki::{zh}"
    if cache is not None and key in cache:
        return cache[key]
    encoded = quote(zh.replace(" ", "_"))
    data = http_get_json(WIKI_ZH_REST.format(title=encoded))
    result = None
    if data and data.get("extract"):
        url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        result = (data["extract"].strip(), "Wikipedia (zh)", url)
        _record_ok()
    if cache is not None:
        cache[key] = result
    return result


def fetch_summary(
    name: str,
    source: str,
    cache: dict[str, tuple[str, str, str] | None] | None = None,
) -> tuple[str, str, str] | None:
    """按 source 策略补充。

    baidu : 仅百度百科
    wiki  : 中文维基(按中文名) -> 英文/原名维基
    both  : 百度百科 -> 中文维基(按中文名) -> 英文/原名维基（默认）
    """
    if source == "wiki":
        return (fetch_zhwiki_by_chinese(name, cache=cache)
                or fetch_wikipedia_summary(name, cache=cache))
    if source == "baidu":
        return fetch_baike_summary(name, cache=cache)
    # both: 百度优先, 中文维基兜底, 英文维基最后
    return (fetch_baike_summary(name, cache=cache)
            or fetch_zhwiki_by_chinese(name, cache=cache)
            or fetch_wikipedia_summary(name, cache=cache))


# ------------------------- 加载实体 -------------------------

def load_entities(kinds: list[str]) -> list[dict]:
    """从 alignment/nodes_*.csv 读取实体名称。"""
    files = {
        "period": (ALIGN_DIR / "nodes_periods.csv", "name"),
        "museum": (ALIGN_DIR / "nodes_museums.csv", "name"),
        "type": (ALIGN_DIR / "nodes_types.csv", "name"),
        "material": (ALIGN_DIR / "nodes_materials.csv", "name"),
        "artist": (ALIGN_DIR / "nodes_artists.csv", "name"),
        "location": (ALIGN_DIR / "nodes_locations.csv", "name"),
    }
    entities: list[dict] = []
    seen = set()
    # 跳过无意义的占位实体名
    skip_names = {"unknown", "未知", "n/a", "na", "none", "其他", "other"}
    for kind in kinds:
        if kind not in files:
            continue
        path, col = files[kind]
        if not path.exists():
            print(f"[warn] missing {path}, skip kind={kind}")
            continue
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get(col) or "").strip()
                if not name or name.lower() in skip_names:
                    continue
                key = (kind, name)
                if key in seen:
                    continue
                seen.add(key)
                entities.append({"kind": kind, "name": name})
    return entities


# ------------------------- 主流程 -------------------------

def enrich(entities: Iterable[dict], delay: float = 0.4,
           source: str = "both") -> list[dict]:
    today = date.today().isoformat()
    results: list[dict] = []
    cache: dict[str, tuple[str, str, str] | None] = {}
    # 连续 N 次失败时退避重试；连续退避都无法恢复才判定真正断网。
    backoff_sec = float(os.environ.get("KG_ENRICH_BACKOFF", "20"))
    max_backoffs = int(os.environ.get("KG_ENRICH_MAX_BACKOFF", "3"))
    backoff_used = 0
    dead = False
    for ent in entities:
        kind, name = ent["kind"], ent["name"]
        if not dead and _network_dead():
            if backoff_used < max_backoffs:
                backoff_used += 1
                print(f"  [retry] 连续 {_FAIL_STREAK['count']} 次失败, "
                      f"退避 {backoff_sec:.0f}s 后重试 "
                      f"({backoff_used}/{max_backoffs})", flush=True)
                time.sleep(backoff_sec)
                _record_ok()  # 重置失败计数，给后续实体机会
            else:
                print(f"  [abort] 多次退避仍失败, 判定外部源不可达, "
                      f"剩余实体留空。", flush=True)
                dead = True
        info = None if dead else fetch_summary(name, source, cache=cache)
        if not info:
            results.append({
                "uri": make_uri(kind, name),
                "kind": kind,
                "name": name,
                "description": "",
                "source": "",
                "source_url": "",
                "enrich_date": today,
            })
            print(f"  [miss] {kind}: {name}", flush=True)
        else:
            desc, source_site, source_url = info
            backoff_used = 0  # 成功命中后重置退避计数
            results.append({
                "uri": make_uri(kind, name),
                "kind": kind,
                "name": name,
                "description": desc,
                "source": source_site,
                "source_url": source_url,
                "enrich_date": today,
            })
            print(f"  [ok]   {kind}: {name} -> {source_site}", flush=True)
        if not dead:
            time.sleep(delay)
    return results


def write_outputs(records: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "augmented_entities.json"
    csv_path = out_dir / "augmented_entities.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    fieldnames = ["uri", "kind", "name", "description",
                  "source", "source_url", "enrich_date"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    print(f"\nSaved: {json_path}")
    print(f"Saved: {csv_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="知识图谱实体数据补充")
    parser.add_argument(
        "--kinds", nargs="+",
        default=["period", "museum"],
        choices=["period", "museum", "type", "material", "artist", "location"],
        help="要补充的实体种类（默认 period 与 museum）",
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="最多处理多少个实体（0 表示不限制）")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="请求间隔秒数（避免触发限流）")
    parser.add_argument("--source", choices=["baidu", "wiki", "both"],
                        default="both",
                        help="数据来源：baidu=仅百度百科, wiki=仅维基, "
                             "both=百度优先维基兜底（默认）")
    args = parser.parse_args(argv)

    entities = load_entities(args.kinds)
    if args.limit > 0:
        entities = entities[:args.limit]
    print(f"待补充实体总数: {len(entities)}  来源策略: {args.source}")

    if not entities:
        print("没有可补充的实体，退出。")
        return 0

    records = enrich(entities, delay=args.delay, source=args.source)
    write_outputs(records, OUT_DIR)

    ok = sum(1 for r in records if r["description"])
    miss = len(records) - ok
    print(f"\n补充成功 {ok} / 失败 {miss} / 总数 {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
