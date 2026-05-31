"""
数据补充模块

从 Wikipedia 等外部来源为知识图谱中的共享实体（朝代 / 博物馆 / 艺术家 / 地点 /
文物类型）补充背景信息，并保留来源与补充日期，供后续 Neo4j 图谱写入使用。

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
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
ALIGN_DIR = ROOT / "data_processing" / "alignment"
OUT_DIR = ROOT / "data_update" / "enrichment"

URI_PREFIX = "http://kg.bjtu5.org"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_ZH_REST = "https://zh.wikipedia.org/api/rest_v1/page/summary/{title}"

USER_AGENT = "BUCT-KG-Enrichment/1.0 (course-project; contact: kg@bjtu5.org)"


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
        return data["extract"].strip(), "Wikipedia (en)", url
    data = http_get_json(WIKI_ZH_REST.format(title=encoded))
    if data and data.get("extract"):
        url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        return data["extract"].strip(), "Wikipedia (zh)", url
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


# ------------------------- 加载实体 -------------------------

def load_entities(kinds: list[str]) -> list[dict]:
    """从 alignment/nodes_*.csv 读取实体名称。"""
    files = {
        "period": (ALIGN_DIR / "nodes_periods.csv", "name"),
        "museum": (ALIGN_DIR / "nodes_museums.csv", "name"),
        "type": (ALIGN_DIR / "nodes_types.csv", "name"),
        "material": (ALIGN_DIR / "nodes_materials.csv", "name"),
    }
    entities: list[dict] = []
    seen = set()
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
                if not name or name.lower() == "unknown":
                    continue
                key = (kind, name)
                if key in seen:
                    continue
                seen.add(key)
                entities.append({"kind": kind, "name": name})
    return entities


# ------------------------- 主流程 -------------------------

def enrich(entities: Iterable[dict], delay: float = 0.4) -> list[dict]:
    today = date.today().isoformat()
    results: list[dict] = []
    cache: dict[str, tuple[str, str, str] | None] = {}
    for ent in entities:
        kind, name = ent["kind"], ent["name"]
        # 命中缓存的回退路径（base name）就不再额外 sleep
        already_cached = (name in cache) or (core_name(name) in cache)
        info = fetch_wikipedia_summary(name, cache=cache)
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
            print(f"  [miss] {kind}: {name}")
        else:
            desc, source, source_url = info
            results.append({
                "uri": make_uri(kind, name),
                "kind": kind,
                "name": name,
                "description": desc,
                "source": source,
                "source_url": source_url,
                "enrich_date": today,
            })
            print(f"  [ok]   {kind}: {name} -> {source}")
        if not already_cached:
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
        choices=["period", "museum", "type", "material"],
        help="要补充的实体种类（默认 period 与 museum）",
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="最多处理多少个实体（0 表示不限制）")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="请求间隔秒数（避免触发限流）")
    args = parser.parse_args(argv)

    entities = load_entities(args.kinds)
    if args.limit > 0:
        entities = entities[:args.limit]
    print(f"待补充实体总数: {len(entities)}")

    if not entities:
        print("没有可补充的实体，退出。")
        return 0

    records = enrich(entities, delay=args.delay)
    write_outputs(records, OUT_DIR)

    ok = sum(1 for r in records if r["description"])
    miss = len(records) - ok
    print(f"\n补充成功 {ok} / 失败 {miss} / 总数 {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
