"""
全流程调度脚本：把数据采集 → 清洗 → 对齐 → 补充 → 入库串联起来。

执行顺序（按 docs/project_specification.md 第 13 节）：
    1. 三家爬虫（可选；缺失也不会导致后续失败）
    2. data_processing/cleaning/run_all_clean.py
    3. data_processing/alignment/entity_alignment.py
    4. data_update/enrichment/enrichment.py
    5. data_update/incremental/incremental.py scan
    6. db/mysql_builder.py
    7. db/neo4j_builder.py
    8. 写入 pipeline/sync_state.json

CLI：
    python3 pipeline/run_pipeline.py
    python3 pipeline/run_pipeline.py --skip-crawl --skip-enrichment
    python3 pipeline/run_pipeline.py --only mysql neo4j

任一步骤非零退出会终止后续步骤。状态写入 pipeline/sync_state.json。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_LOG = ROOT / "pipeline" / "pipeline.log"
STATE_PATH = ROOT / "pipeline" / "sync_state.json"


# 步骤定义：name → (相对仓库根的命令, 是否必需)
def build_steps(args) -> list[tuple[str, list[str], bool]]:
    py = sys.executable
    steps: list[tuple[str, list[str], bool]] = []

    # 爬虫统一入口在 crawlers/main.py（使用相对导入，必须 -m 调用）
    if not args.skip_crawl and (ROOT / "crawlers/main.py").exists():
        for name, museum_id in [
            ("crawl_chicago",         "chicago"),
            ("crawl_princeton",       "princeton"),
            ("crawl_brooklyn_museum", "brooklyn_museum"),
        ]:
            steps.append((
                name,
                [py, "-m", "crawlers.main", "--museum", museum_id],
                False,
            ))

    if not args.skip_clean and (ROOT / "data_processing/cleaning/run_all_clean.py").exists():
        steps.append(("cleaning", [py, "data_processing/cleaning/run_all_clean.py"], True))

    if not args.skip_align and (ROOT / "data_processing/alignment/entity_alignment.py").exists():
        steps.append(("alignment", [py, "data_processing/alignment/entity_alignment.py"], True))

    if not args.skip_enrichment and (ROOT / "data_update/enrichment/enrichment.py").exists():
        steps.append(("enrichment", [py, "data_update/enrichment/enrichment.py"], False))

    if not args.skip_incremental and (ROOT / "data_update/incremental/incremental.py").exists():
        steps.append((
            "incremental",
            [py, "data_update/incremental/incremental.py", "scan",
             "--museums", "chicago", "princeton", "brooklyn_museum"],
            False,
        ))

    if not args.skip_mysql and (ROOT / "db/mysql_builder.py").exists():
        steps.append(("mysql_build", [py, "db/mysql_builder.py"], True))

    if not args.skip_neo4j and (ROOT / "db/neo4j_builder.py").exists():
        steps.append(("neo4j_build", [py, "db/neo4j_builder.py"], True))

    # pHash 索引（以图搜图，必需在 mysql_build 之后）
    if not args.skip_phash and (ROOT / "db/phash_indexer.py").exists():
        steps.append(("phash_index", [py, "db/phash_indexer.py"], False))

    # CLIP + FAISS 语义索引（可选；未安装 torch 时该步骤会失败但不阻塞）
    if args.with_clip and (ROOT / "db/clip_indexer.py").exists():
        steps.append(("clip_index", [py, "db/clip_indexer.py"], False))

    if args.only:
        steps = [s for s in steps if s[0] in set(args.only)]

    return steps


def run_step(name: str, cmd: list[str], log) -> tuple[bool, float]:
    started = time.time()
    print(f"\n=== [pipeline] step: {name} ===")
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
        # 同时回显到控制台（截断超长输出）
        if result.stdout:
            tail = result.stdout if len(result.stdout) < 4000 else \
                "...\n" + result.stdout[-4000:]
            print(tail)
        ok = result.returncode == 0
    except Exception as exc:  # 极端异常
        log.write(f"EXCEPTION: {exc}\n")
        ok = False
    return ok, time.time() - started


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="知识图谱构建全流程")
    parser.add_argument("--skip-crawl", action="store_true")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-align", action="store_true")
    parser.add_argument("--skip-enrichment", action="store_true")
    parser.add_argument("--skip-incremental", action="store_true")
    parser.add_argument("--skip-mysql", action="store_true")
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--skip-phash", action="store_true")
    parser.add_argument("--with-clip", action="store_true",
                        help="额外执行 CLIP+FAISS 离线索引（需先 pip install torch faiss-cpu transformers）")
    parser.add_argument("--only", nargs="*",
                        help="仅执行给定步骤名（与 skip-* 互斥）")
    args = parser.parse_args(argv)

    PIPELINE_LOG.parent.mkdir(parents=True, exist_ok=True)
    state = load_state()
    history = state.get("history", [])

    run_id = datetime.now().isoformat(timespec="seconds")
    run_record = {"run_id": run_id, "steps": []}

    with PIPELINE_LOG.open("a", encoding="utf-8") as log:
        log.write(f"\n############ pipeline run @ {run_id} ############\n")
        steps = build_steps(args)
        if not steps:
            print("[pipeline] no steps to run.")
            return 0

        for name, cmd, required in steps:
            ok, elapsed = run_step(name, cmd, log)
            run_record["steps"].append({
                "name": name, "ok": ok, "elapsed_sec": round(elapsed, 2),
            })
            if not ok and required:
                print(f"[pipeline] step '{name}' failed; abort subsequent steps.")
                run_record["aborted_at"] = name
                break
            if not ok:
                print(f"[pipeline] step '{name}' failed (non-required), continue.")

    # 写状态
    state["last_run"] = run_id
    history.append(run_record)
    state["history"] = history[-50:]
    save_state(state)
    print(f"\n[pipeline] state saved -> {STATE_PATH}")
    print(f"[pipeline] log -> {PIPELINE_LOG}")

    failed_required = [s for s in run_record["steps"] if not s["ok"]]
    return 0 if not failed_required else 1


if __name__ == "__main__":
    sys.exit(main())
