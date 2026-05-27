import json
from pathlib import Path
from typing import Iterable, Dict, Any
import csv
import requests

def ensure_dir(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def save_jsonl(items: Iterable[Dict[str, Any]], out_path: Path):
    ensure_dir(out_path)
    with out_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def save_csv(items: Iterable[Dict[str, Any]], out_path: Path, fieldnames=None):
    ensure_dir(out_path)
    items = list(items)
    if not fieldnames:
        # 从第一项推断列顺序
        fieldnames = list(items[0].keys()) if items else []
    with out_path.open("w", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for it in items:
            writer.writerow({k: (v if v is not None else "") for k, v in it.items()})


def download_image(url: str, out_path: Path, timeout: int = 10) -> bool:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in resp.iter_content(1024 * 8):
                f.write(chunk)
        return True
    except Exception:
        return False


def check_image_url(url: str, timeout: int = 6) -> bool:
    try:
        resp = requests.head(url, timeout=timeout)
        return resp.status_code == 200 and 'image' in resp.headers.get('Content-Type','')
    except Exception:
        return False