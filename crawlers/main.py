import sys
import re
from pathlib import Path
import argparse

from .config import MUSEUMS, RAW_DIR, USER_AGENT
from .spiders import (
    MetMuseumCrawler,
    GuimetMuseumCrawler,
    BrooklynBotanicCrawler,
    BritishMuseumCrawler,
    ArtInstituteChicagoCrawler,
    PrincetonMuseumCrawler,
    BrooklynArtMuseumCrawler,
)
from .utils import save_jsonl, save_csv, check_image_url, download_image

CRAWLERS = {
    "met_museum": MetMuseumCrawler,
    "guimet_museum": GuimetMuseumCrawler,
    "brooklyn_botanic": BrooklynBotanicCrawler,
    "british_museum": BritishMuseumCrawler,
    "chicago": ArtInstituteChicagoCrawler,
    "princeton": PrincetonMuseumCrawler,
    "brooklyn_museum": BrooklynArtMuseumCrawler,
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

    # Image validation & download — standardise image_path field
    images_dir = out_dir / "images" / museum_id
    for it in items:
        img = it.get("image_url", "")
        if img:
            if download_images:
                valid = check_image_url(img)
                it["_image_valid"] = valid
                if valid:
                    safe_oid = re.sub(r'[<>:"/\\|?*]', "_", str(it.get("object_id", "")))
                    if not safe_oid:
                        safe_oid = hashlib_md5(img.encode()).hexdigest()[:12]
                    ext = Path(img).suffix.split("?")[0] or ".jpg"
                    local_path = images_dir / f"{safe_oid}{ext}"
                    ok = download_image(img, local_path)
                    it["image_path"] = str(local_path) if ok else ""
                else:
                    it["image_path"] = ""
            else:
                it["_image_valid"] = ""
                it["image_path"] = ""
        else:
            it["_image_valid"] = False
            it["image_path"] = ""

    out_path_jsonl = out_dir / f"{museum_id}.jsonl"
    out_path_csv = out_dir / f"{museum_id}.csv"
    save_jsonl(items, out_path_jsonl)

    # CSV: standard 15 fields first, then extra (_-prefixed) fields
    std_fields = [
        "object_id", "title", "period", "type", "material", "description",
        "dimensions", "museum", "location", "detail_url", "image_url",
        "image_path", "credit_line", "accession_number", "crawl_date",
    ]
    if items:
        extra_fields = [k for k in items[0] if k not in std_fields]
        fieldnames = std_fields + extra_fields
    else:
        fieldnames = std_fields
    save_csv(items, out_path_csv, fieldnames=fieldnames)

    print(f"  Saved to {out_path_jsonl} and {out_path_csv}")


def hashlib_md5(data: bytes) -> str:
    import hashlib
    return hashlib.md5(data).hexdigest()


if __name__ == "__main__":
    # Ensure UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Brooklyn museum crawlers — 海外中国流失文物数据爬取"
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
