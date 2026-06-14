"""
一键执行「数据补充 + 增量扫描」（本地运行）。

适用场景：
    数据已爬取、清洗、对齐完成后，在本地跑这一个脚本即可完成
        1. 数据补充 enrichment（默认 百度百科优先，Wikipedia 兜底）
        2. 增量扫描 incremental scan（基于已有 raw CSV 产出 delta）
    跑完后会打印「需要上传到服务器的文件清单」，照着传即可。

CLI：
    python3 pipeline/run_update.py
    python3 pipeline/run_update.py --source baidu          # 仅百度百科
    python3 pipeline/run_update.py --kinds period museum type material
    python3 pipeline/run_update.py --skip-incremental      # 只补充
    python3 pipeline/run_update.py --skip-enrichment       # 只增量
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "pipeline" / "update.log"

MUSEUMS = ["chicago", "princeton", "brooklyn_museum"]

# 跑完后需要上传到服务器的产物（相对仓库根）
UPLOAD_FILES = [
    "data_update/enrichment/augmented_entities.json",
    "data_update/enrichment/augmented_entities.csv",
    "data_update/incremental/sync_state.json",
    "data_update/incremental/delta/chicago_delta.csv",
    "data_update/incremental/delta/princeton_delta.csv",
    "data_update/incremental/delta/brooklyn_museum_delta.csv",
]


def run_step(name: str, cmd: list[str], log) -> bool:
    print(f"\n=== [update] step: {name} ===")
    print("    cmd:", " ".join(cmd))
    log.write(f"\n=== {datetime.now().isoformat()} step={name} ===\n")
    log.write("cmd: " + " ".join(cmd) + "\n")
    log.flush()
    try:
        result = subprocess.run(
            cmd, cwd=str(ROOT), check=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        log.write(result.stdout or "")
        log.flush()
        if result.stdout:
            tail = result.stdout if len(result.stdout) < 4000 else \
                "...\n" + result.stdout[-4000:]
            print(tail)
        return result.returncode == 0
    except Exception as exc:
        log.write(f"EXCEPTION: {exc}\n")
        print(f"    EXCEPTION: {exc}")
        return False


def print_upload_list() -> None:
    print("\n" + "=" * 56)
    print("需要上传到服务器的文件（相对仓库根目录）：")
    print("=" * 56)
    for rel in UPLOAD_FILES:
        p = ROOT / rel
        flag = "OK " if p.exists() else "-- "  # -- 表示本次未生成（可能跳过该步骤）
        print(f"  [{flag}] {rel}")
    print("\n上传后在服务器执行入库即可：")
    print("  python3 db/mysql_builder.py")
    print("  python3 db/neo4j_builder.py")
    print("=" * 56)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一键执行 数据补充 + 增量扫描")
    parser.add_argument("--source", choices=["baidu", "wiki", "both"],
                        default="both",
                        help="补充来源：baidu=仅百度百科, wiki=仅维基, "
                             "both=百度优先维基兜底（默认）")
    parser.add_argument("--kinds", nargs="+",
                        default=["period", "museum"],
                        choices=["period", "museum", "type", "material"],
                        help="补充的实体种类（默认 period museum）")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="补充请求间隔秒数")
    parser.add_argument("--museums", nargs="+", default=MUSEUMS,
                        help="增量扫描的博物馆 id")
    parser.add_argument("--skip-enrichment", action="store_true")
    parser.add_argument("--skip-incremental", action="store_true")
    args = parser.parse_args(argv)

    py = sys.executable
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    ok_all = True
    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(f"\n############ update run @ "
                  f"{datetime.now().isoformat()} ############\n")

        if not args.skip_enrichment:
            started = time.time()
            ok = run_step("enrichment", [
                py, "data_update/enrichment/enrichment.py",
                "--source", args.source,
                "--kinds", *args.kinds,
                "--delay", str(args.delay),
            ], log)
            print(f"    -> {'成功' if ok else '失败'} "
                  f"({time.time() - started:.1f}s)")
            ok_all = ok_all and ok

        if not args.skip_incremental:
            started = time.time()
            ok = run_step("incremental", [
                py, "data_update/incremental/incremental.py", "scan",
                "--museums", *args.museums,
            ], log)
            print(f"    -> {'成功' if ok else '失败'} "
                  f"({time.time() - started:.1f}s)")
            ok_all = ok_all and ok

    print_upload_list()
    print(f"\n[update] 日志 -> {LOG_PATH}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
