from pathlib import Path
import argparse

from .config import MUSEUMS, RAW_DIR, USER_AGENT
from .spiders import (
    MetMuseumCrawler,
    GuimetMuseumCrawler,
    BrooklynBotanicCrawler,
    BritishMuseumCrawler,
)
from .utils import save_jsonl, save_csv, check_image_url, download_image

CRAWLERS = {
    "met_museum": MetMuseumCrawler,
    "guimet_museum": GuimetMuseumCrawler,
    "brooklyn_botanic": BrooklynBotanicCrawler,
    "british_museum": BritishMuseumCrawler,
}


def run_crawler(museum_id: str, out_dir: Path, download_images: bool = False):
    config = next((m for m in MUSEUMS if m["id"] == museum_id), None)
    if not config:
        raise SystemExit(f"Unknown museum id: {museum_id}")

    crawler_cls = CRAWLERS.get(museum_id)
    if not crawler_cls:
        raise SystemExit(f"No crawler implemented for: {museum_id}")

    print(f"Starting crawler: {config['name']} ({museum_id})")
    crawler = crawler_cls(start_url=config.get("start_url"), user_agent=USER_AGENT)
    items = list(crawler.crawl())
    print(f"  Got {len(items)} items")

    # 可选：对每条记录执行图片有效性检测与下载
    images_dir = out_dir / "images" / museum_id
    for i, it in enumerate(items):
        img = it.get("image_url")
        if img:
            valid = check_image_url(img)
            it["image_valid"] = valid
            it["image_local"] = None
            if download_images and valid:
                ext = Path(img).suffix.split("?")[0] or ".jpg"
                local_path = images_dir / f"{museum_id}_{i}{ext}"
                ok = download_image(img, local_path)
                it["image_local"] = str(local_path) if ok else None
        else:
            it["image_valid"] = False
            it["image_local"] = None

    out_path_jsonl = out_dir / f"{museum_id}.jsonl"
    out_path_csv = out_dir / f"{museum_id}.csv"
    save_jsonl(items, out_path_jsonl)
    # 动态推断 CSV 列名（此时 items 已有 image_valid/image_local）
    fieldnames = list(items[0].keys()) if items else []
    save_csv(items, out_path_csv, fieldnames=fieldnames)

    print(f"  Saved to {out_path_jsonl} and {out_path_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Brooklyn museum crawlers — 中国流失文物数据爬取"
    )
    parser.add_argument("--museum", default="all",
                        help="museum id to crawl (or 'all')")
    parser.add_argument("--download-images", action="store_true",
                        help="download original images")
    args = parser.parse_args()

    out_dir = Path(RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    to_run = [args.museum] if args.museum != "all" else list(CRAWLERS.keys())
    for mid in to_run:
        try:
            run_crawler(mid, out_dir, download_images=args.download_images)
        except Exception as e:
            print(f"Error crawling {mid}: {e}")
