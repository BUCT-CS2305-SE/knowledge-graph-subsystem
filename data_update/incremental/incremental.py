"""
增量爬取模块（成员 D 任务）

目标：
    1. 维护 sync_state.json，记录每次爬取运行的时间、各馆数量与变更详情。
    2. 提供基于 (museum, object_id) 与内容 hash 的弱增量过滤工具，
       让爬虫脚本仅写入新增或更新过的记录，避免全量重复下载。
    3. 与本仓库已有的爬虫输出 CSV 配合使用：
           crawlers/data/raw/<museum>.csv

主要 API：
    - IncrementalState : 加载 / 写回 sync_state.json
    - filter_new_items(items, museum_id, state)
        过滤掉 (museum_id, object_id, content_hash) 已经记录过的条目
    - run(museum_ids, since=...) : 命令行入口

CLI：
    python3 data_update/incremental/incremental.py status
    python3 data_update/incremental/incremental.py scan \
        --museums chicago princeton brooklyn_museum
    python3 data_update/incremental/incremental.py reset \
        --museum chicago
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "crawlers" / "data" / "raw"
STATE_PATH = Path(__file__).resolve().parent / "sync_state.json"

# 与 docs/project_specification.md 第 7.1 节保持一致的 15 列
STD_FIELDS = [
    "object_id", "title", "period", "type", "material",
    "description", "dimensions", "museum", "location",
    "detail_url", "image_url", "image_path",
    "credit_line", "accession_number", "crawl_date",
]

# 用于计算内容 hash 的字段（更新检测）
HASH_FIELDS = [
    "title", "period", "type", "material", "description",
    "dimensions", "detail_url", "image_url", "credit_line",
    "accession_number",
]


# ------------------------- 状态对象 -------------------------

@dataclass
class MuseumState:
    last_run: str = ""              # ISO 时间
    total_records: int = 0          # 累计已知记录数
    seen: dict[str, str] = field(default_factory=dict)  # object_id -> content_hash

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunRecord:
    run_at: str
    museum: str
    target_count: int = 0
    raw_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    steps: list[str] = field(default_factory=list)


class IncrementalState:
    """对 sync_state.json 的轻量封装。"""

    def __init__(self, path: Path = STATE_PATH):
        self.path = path
        self.museums: dict[str, MuseumState] = {}
        self.history: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        for mid, payload in (data.get("museums") or {}).items():
            self.museums[mid] = MuseumState(
                last_run=payload.get("last_run", ""),
                total_records=int(payload.get("total_records", 0) or 0),
                seen=dict(payload.get("seen") or {}),
            )
        self.history = list(data.get("history") or [])

    def save(self) -> None:
        payload = {
            "museums": {mid: ms.to_dict() for mid, ms in self.museums.items()},
            "history": self.history[-50:],   # 仅保留最近 50 次运行
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 便捷访问
    def get(self, museum_id: str) -> MuseumState:
        return self.museums.setdefault(museum_id, MuseumState())

    def reset(self, museum_id: str) -> None:
        self.museums.pop(museum_id, None)

    def append_run(self, record: RunRecord) -> None:
        self.history.append(asdict(record))


# ------------------------- 内容 hash -------------------------

def content_hash(item: dict) -> str:
    parts = "\u0001".join(str(item.get(f, "") or "") for f in HASH_FIELDS)
    return hashlib.md5(parts.encode("utf-8")).hexdigest()


# ------------------------- 过滤工具 -------------------------

def filter_new_items(
    items: Iterable[dict],
    museum_id: str,
    state: IncrementalState,
    since: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """根据已记录的 seen 表区分新增 / 更新 / 跳过。

    返回 (new_items, updated_items, skipped_items)；同时直接更新 state 中
    对应博物馆的 seen 表，但不会写盘。
    """
    ms = state.get(museum_id)
    new_items: list[dict] = []
    updated_items: list[dict] = []
    skipped_items: list[dict] = []

    since_dt = _parse_date(since) if since else None

    for it in items:
        oid = str(it.get("object_id") or "").strip()
        if not oid:
            continue
        if since_dt:
            crawl_dt = _parse_date(it.get("crawl_date"))
            if crawl_dt and crawl_dt < since_dt:
                skipped_items.append(it)
                continue
        h = content_hash(it)
        prev = ms.seen.get(oid)
        if prev is None:
            new_items.append(it)
            ms.seen[oid] = h
        elif prev != h:
            updated_items.append(it)
            ms.seen[oid] = h
        else:
            skipped_items.append(it)

    ms.total_records = len(ms.seen)
    ms.last_run = datetime.now().isoformat(timespec="seconds")
    return new_items, updated_items, skipped_items


def _parse_date(value) -> date | None:
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ------------------------- CSV 读写辅助 -------------------------

def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_delta_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = STD_FIELDS + [
        k for k in rows[0].keys() if k not in STD_FIELDS
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (r.get(k) or "") for k in fieldnames})


# ------------------------- 命令行子命令 -------------------------

def cmd_status(args, state: IncrementalState) -> int:
    if not state.museums:
        print("(empty) sync_state.json 尚未记录任何博物馆。")
        return 0
    print(f"State file: {state.path}")
    for mid, ms in state.museums.items():
        print(f"  {mid:20s}  total={ms.total_records:<6d}  last_run={ms.last_run}")
    if state.history:
        print("\nRecent runs:")
        for h in state.history[-5:]:
            print(f"  - {h.get('run_at')}  {h.get('museum')}  "
                  f"new={h.get('new_count')}  upd={h.get('updated_count')}  "
                  f"skip={h.get('skipped_count')}")
    return 0


def cmd_scan(args, state: IncrementalState) -> int:
    """扫描已有 raw CSV，按增量逻辑更新状态并输出 delta。"""
    out_dir = Path(args.out_dir) if args.out_dir else \
        Path(__file__).resolve().parent / "delta"
    out_dir.mkdir(parents=True, exist_ok=True)

    for museum in args.museums:
        csv_path = RAW_DIR / f"{museum}.csv"
        if not csv_path.exists():
            print(f"[skip] {museum}: {csv_path} 不存在")
            continue

        rows = read_csv(csv_path)
        new_items, updated, skipped = filter_new_items(
            rows, museum, state, since=args.since
        )
        record = RunRecord(
            run_at=datetime.now().isoformat(timespec="seconds"),
            museum=museum,
            target_count=args.target_count or 0,
            raw_count=len(rows),
            new_count=len(new_items),
            updated_count=len(updated),
            skipped_count=len(skipped),
            steps=["read_csv", "filter_new_items", "write_delta"],
        )
        state.append_run(record)

        delta_path = out_dir / f"{museum}_delta.csv"
        write_delta_csv(delta_path, new_items + updated)

        print(f"[{museum}] raw={len(rows)} new={len(new_items)} "
              f"updated={len(updated)} skipped={len(skipped)}  -> {delta_path}")

    state.save()
    print(f"\nState saved: {state.path}")
    return 0


def cmd_reset(args, state: IncrementalState) -> int:
    if args.museum == "all":
        state.museums.clear()
        state.history.clear()
        print("已清空所有博物馆状态。")
    else:
        state.reset(args.museum)
        print(f"已重置 {args.museum} 的状态。")
    state.save()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="增量爬取与同步状态管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="打印当前同步状态")

    p_scan = sub.add_parser("scan", help="扫描已有 raw CSV 并产出增量")
    p_scan.add_argument("--museums", nargs="+",
                        default=["chicago", "princeton", "brooklyn_museum"],
                        help="待扫描博物馆 id（与 raw/<id>.csv 对应）")
    p_scan.add_argument("--since", default=None,
                        help="仅处理 crawl_date >= 该日期 (YYYY-MM-DD)")
    p_scan.add_argument("--target-count", type=int, default=0,
                        help="本轮目标记录数（仅记录在历史中）")
    p_scan.add_argument("--out-dir", default=None,
                        help="增量 CSV 输出目录，默认 incremental/delta")

    p_reset = sub.add_parser("reset", help="重置某馆或全部状态")
    p_reset.add_argument("--museum", default="all",
                         help="博物馆 id 或 all（默认 all）")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    state = IncrementalState()

    handlers = {
        "status": cmd_status,
        "scan": cmd_scan,
        "reset": cmd_reset,
    }
    return handlers[args.cmd](args, state)


if __name__ == "__main__":
    sys.exit(main())
