"""
独立图片下载器：读取 data_processing/alignment/by_dataset/clean_*.csv
里的 image_url 直接下载，不走完整爬虫流程。

用法：
    python3 scripts/download_images.py                  # 下全部
    python3 scripts/download_images.py --museum princeton  # 只下一个馆
    python3 scripts/download_images.py --limit 10       # 每馆限量（调试用）
    python3 scripts/download_images.py --workers 8      # 并发数

输出：
    crawlers/data/raw/images/<museum_id>/<object_id>.jpg
"""
import argparse
import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "data_processing" / "alignment" / "by_dataset"
OUT_ROOT = ROOT / "crawlers" / "data" / "raw" / "images"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

CSV_TO_MUSEUM = {
    "clean_british_museum.csv":   "british_museum",
    "clean_brooklyn_botanic.csv": "brooklyn_botanic",
    "clean_brooklyn_museum.csv":  "brooklyn_museum",
    "clean_chicago.csv":          "chicago",
    "clean_guimet.csv":           "guimet_museum",
    "clean_met.csv":              "met_museum",
    "clean_princeton.csv":        "princeton",
}


def safe_name(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", str(s or "").strip())


def normalize_url(url: str) -> str:
    """对 IIIF Image API base URL 自动补全为真图 URL。"""
    u = url.strip()
    low = u.lower()
    # 已经是真图：保持原样
    if low.endswith((".jpg", ".jpeg", ".png", ".webp", "/default.jpg")):
        return u
    # IIIF Image API：包含 /iiif/ 且不带 /full/ 等参数
    if "/iiif/" in low and "/full/" not in low:
        return u.rstrip("/") + "/full/max/0/default.jpg"
    return u


def download(url: str, out_path: Path, timeout: int = 30, debug: bool = False) -> str:
    """返回 'ok' / 'skip' / 'fail:原因'。"""
    if out_path.exists() and out_path.stat().st_size > 0:
        return "skip"
    headers = {
        "User-Agent": UA,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Referer": "https://www.google.com/",
    }
    real_url = normalize_url(url)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(real_url, timeout=timeout, headers=headers, stream=True,
                         allow_redirects=True)
        if r.status_code != 200:
            if debug:
                print(f"  [debug] {r.status_code} {real_url}", flush=True)
            return f"fail:HTTP{r.status_code}"
        ct = (r.headers.get("Content-Type") or "").lower()
        # 如果还是 json/html/xml：再尝试一种 IIIF 兼容写法 /full/full/0/default.jpg
        if ("html" in ct or "json" in ct or "xml" in ct):
            r.close()
            if "/iiif/" in real_url.lower() and "/full/max/" in real_url:
                alt_url = real_url.replace("/full/max/", "/full/full/")
                r = requests.get(alt_url, timeout=timeout, headers=headers,
                                 stream=True, allow_redirects=True)
                ct = (r.headers.get("Content-Type") or "").lower()
                if r.status_code != 200 or "html" in ct or "json" in ct:
                    if debug:
                        print(f"  [debug] retry bad CT={ct} {alt_url}", flush=True)
                    return f"fail:CT={ct[:30]}"
            else:
                if debug:
                    print(f"  [debug] bad CT={ct} {real_url}", flush=True)
                return f"fail:CT={ct[:30]}"
        size = 0
        with out_path.open("wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
        if size < 512:  # 太小肯定不是真图
            out_path.unlink(missing_ok=True)
            return f"fail:size={size}"
        return "ok"
    except requests.exceptions.Timeout:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        if debug:
            print(f"  [debug] timeout {real_url}", flush=True)
        return "fail:timeout"
    except Exception as e:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        if debug:
            print(f"  [debug] {type(e).__name__}: {e} {real_url}", flush=True)
        return f"fail:{type(e).__name__}"


def process_csv(csv_path: Path, museum_id: str, limit: int, workers: int,
                debug: bool = False):
    out_dir = OUT_ROOT / museum_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            url = (r.get("image_url") or "").strip()
            oid = (r.get("object_id") or "").strip()
            if not url or not oid:
                continue
            ext = ".jpg"
            for cand in (".jpg", ".jpeg", ".png", ".webp"):
                if cand in url.lower():
                    ext = cand
                    break
            out_path = out_dir / f"{safe_name(oid)}{ext}"
            rows.append((url, out_path))
            if limit and len(rows) >= limit:
                break

    if not rows:
        print(f"[{museum_id}] no rows with image_url, skip")
        return 0, 0, 0, 0

    print(f"[{museum_id}] downloading {len(rows)} images -> {out_dir}")
    ok = skip = fail = 0
    fail_reasons = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(download, url, p, 30, debug): (url, p) for url, p in rows}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            if res == "ok":
                ok += 1
            elif res == "skip":
                skip += 1
            else:
                fail += 1
                fail_reasons[res] = fail_reasons.get(res, 0) + 1
            if i % 50 == 0 or i == len(rows):
                print(f"  [{museum_id}] {i}/{len(rows)} ok={ok} skip={skip} fail={fail}",
                      flush=True)
    dt = time.time() - t0
    print(f"[{museum_id}] DONE ok={ok} skip={skip} fail={fail} elapsed={dt:.1f}s")
    if fail_reasons:
        top = sorted(fail_reasons.items(), key=lambda x: -x[1])[:5]
        print(f"[{museum_id}] top fail reasons: {top}")
    return len(rows), ok, skip, fail


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--museum", default="all",
                   choices=["all"] + list(CSV_TO_MUSEUM.values()))
    p.add_argument("--limit", type=int, default=0,
                   help="每馆限量（0 = 不限）")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--debug", action="store_true",
                   help="打印每个失败请求的详细原因")
    args = p.parse_args()

    if not CSV_DIR.exists():
        print(f"[ERROR] CSV dir not found: {CSV_DIR}", file=sys.stderr)
        sys.exit(1)

    targets = []
    for csv_name, mid in CSV_TO_MUSEUM.items():
        if args.museum != "all" and args.museum != mid:
            continue
        f = CSV_DIR / csv_name
        if not f.exists():
            print(f"[WARN] missing: {f}")
            continue
        targets.append((f, mid))

    if not targets:
        print("[ERROR] no targets")
        sys.exit(1)

    total = total_ok = total_skip = total_fail = 0
    for f, mid in targets:
        n, ok, skip, fail = process_csv(f, mid, args.limit, args.workers, args.debug)
        total += n; total_ok += ok; total_skip += skip; total_fail += fail

    print()
    print(f"[ALL] total={total} ok={total_ok} skip={total_skip} fail={total_fail}")
    print(f"[ALL] images saved under: {OUT_ROOT}")


if __name__ == "__main__":
    main()