"""Crawlers for museum collections — each returns structured item dicts."""

import json
import re
from typing import Iterable, Dict, Any, Optional
from bs4 import BeautifulSoup
import requests

from .base_crawler import BaseCrawler

MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


# ── Met Museum (REST API, no key needed) ──────────────────────────────

class MetMuseumCrawler(BaseCrawler):
    """大都会博物馆 — 官方开放 REST API，搜索中国相关藏品"""

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)
        self._session = requests.Session()

    def _search(self, query: str = "China", has_images: bool = True) -> list[int]:
        params = {"q": query}
        if has_images:
            params["hasImages"] = "true"
        resp = self._session.get(f"{MET_API_BASE}/search", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("objectIDs", []) or []

    def _get_object(self, oid: int) -> dict:
        resp = self._session.get(f"{MET_API_BASE}/objects/{oid}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def crawl(self) -> Iterable[Dict[str, Any]]:
        all_ids = self._search("China", has_images=True)
        for oid in all_ids[:50]:
            try:
                obj = self._get_object(oid)
            except Exception:
                continue
            if not obj or not obj.get("title"):
                continue
            yield {
                "title": obj.get("title"),
                "object_name": obj.get("objectName"),
                "culture": obj.get("culture"),
                "period": obj.get("period"),
                "dynasty": obj.get("dynasty"),
                "reign": obj.get("reign"),
                "object_date": obj.get("objectDate"),
                "medium": obj.get("medium"),
                "classification": obj.get("classification"),
                "department": obj.get("department"),
                "dimensions": obj.get("dimensions"),
                "credit_line": obj.get("creditLine"),
                "country": obj.get("country"),
                "region": obj.get("region"),
                "artist": obj.get("artistDisplayName"),
                "artist_bio": obj.get("artistDisplayBio"),
                "artist_nationality": obj.get("artistNationality"),
                "image_url": obj.get("primaryImage"),
                "image_small": obj.get("primaryImageSmall"),
                "object_url": obj.get("objectURL"),
                "accession_number": obj.get("accessionNumber"),
                "accession_year": obj.get("accessionYear"),
                "is_public_domain": obj.get("isPublicDomain"),
                "source": "met_museum",
            }


# ── Guimet Museum (Drupal HTML scraping) ─────────────────────────────

class GuimetMuseumCrawler(BaseCrawler):
    """吉美博物馆 — 爬取 Drupal 静态页面"""

    BASE = "https://www.guimet.fr"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)
        self.start_url = start_url

    def _abs(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{self.BASE}{url}"
        return url

    def _parse_detail(self, url: str) -> dict:
        try:
            html = self.fetch(url)
        except Exception:
            return {}
        soup = BeautifulSoup(html, "html.parser")
        meta = {}

        for sel in (".field--name-field-teaser",):
            el = soup.select_one(sel)
            if el:
                meta["description"] = el.get_text(strip=True)

        period = soup.select_one(".field--name-field-text-period")
        if period:
            meta["period"] = period.get_text(strip=True)

        info = soup.select_one(".info-table")
        if info:
            for cell in info.find_all("div", class_="cell"):
                label = cell.select_one(".field__label")
                val = cell.select_one(".field__item")
                if label and val:
                    key = (
                        label.get_text(strip=True)
                        .lower().replace(" ", "_").replace("é", "e")
                    )
                    meta[key] = val.get_text(strip=True)

        full = soup.select_one(
            ".field--name-field-image img, div.field--type-image img"
        )
        if full:
            meta["image_url"] = self._abs(full.get("src", ""))

        return meta

    def crawl(self) -> Iterable[Dict[str, Any]]:
        html = self.fetch(f"{self.BASE}/en/collections/china")
        soup = BeautifulSoup(html, "html.parser")

        for card in soup.select(".node--type-art-work"):
            title_el = card.select_one(".field--name-title, h2, h3")
            title = title_el.get_text(strip=True) if title_el else ""

            cat_el = card.select_one(".field--name-field-object-type")
            category = cat_el.get_text(strip=True) if cat_el else ""

            link_el = card.select_one("a[href*='/our-collections/']")
            detail_url = self._abs(link_el["href"]) if link_el else None

            thumb_el = card.select_one("img")
            thumb = self._abs(thumb_el.get("src", "")) if thumb_el else ""

            item = {
                "title": title,
                "category": category,
                "detail_url": detail_url,
                "image_url": thumb,
                "source": "guimet_museum",
            }
            if detail_url:
                detail = self._parse_detail(detail_url)
                if detail.get("image_url"):
                    item["image_url"] = detail["image_url"]
                item.update(detail)

            if title:
                yield item


# ── Brooklyn Botanic Garden (HTML scraping) ──────────────────────────

class BrooklynBotanicCrawler(BaseCrawler):
    """布鲁克林植物园 — 爬取植物名录"""

    BASE = "https://www.bbg.org"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)

    def _abs(self, url: str) -> str:
        return f"{self.BASE}{url}" if url.startswith("/") else url

    def crawl(self) -> Iterable[Dict[str, Any]]:
        pages = [
            "/collections/cherry_stages",
            "/bloom",
            "/collections/cherries",
        ]
        for path in pages:
            url = self._abs(path)
            try:
                html = self.fetch(url)
            except Exception:
                continue
            soup = BeautifulSoup(html, "html.parser")
            title_el = soup.select_one("h1")
            collection = title_el.get_text(strip=True) if title_el else path.strip("/")

            seen = set()
            for img in soup.find_all("img"):
                src = img.get("src") or ""
                alt = img.get("alt", "").strip()
                if not src or "/logo" in src or "svg" in src:
                    continue
                abs_src = self._abs(src)
                if abs_src in seen:
                    continue
                seen.add(abs_src)
                if len(alt) > 3:
                    yield {
                        "title": alt,
                        "plant_name": alt.split(",")[0].strip() if "," in alt else alt,
                        "collection": collection,
                        "category": "plant",
                        "url": url,
                        "image_url": abs_src,
                        "source": "brooklyn_botanic",
                    }


# ── British Museum (Playwright-browser required) ──────────────────────

class BritishMuseumCrawler(BaseCrawler):
    """大英博物馆 — 通过 Playwright 浏览器绕过 Cloudflare"""

    BASE = "https://www.britishmuseum.org"
    MEDIA_BASE = "https://media.britishmuseum.org"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)

    def _clean_html(self, raw: str) -> str:
        """Strip HTML tags from brief-field values."""
        return re.sub(r"<[^>]+>", "", raw).strip()

    def _extract_ident(self, identifiers: list, id_type: str) -> str:
        for item in identifiers:
            if isinstance(item, dict) and item.get("type") == id_type:
                return item.get("value", "")
        return ""

    def crawl(self) -> Iterable[Dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("pip install playwright && playwright install chromium")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-GB",
            )
            page = ctx.new_page()
            api_data = {}

            def capture(response):
                if "_search" in response.url and response.status == 200:
                    try:
                        api_data["body"] = response.json()
                    except Exception:
                        pass

            page.on("response", capture)
            page.goto(
                f"{self.BASE}/collection/search?place=China&page=0",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(8000)

            if "body" not in api_data:
                browser.close()
                raise RuntimeError("British Museum API blocked by Cloudflare")

            hits = api_data["body"].get("hits", {}).get("hits", [])

            for hit in hits:
                src = hit.get("_source", {})
                brief_str = src.get("@template", {}).get("brief", "{}")
                try:
                    brief = json.loads(brief_str)
                except (json.JSONDecodeError, TypeError):
                    brief = {}

                # object type
                obj_types = brief.get("Object Type") or brief.get("object_type") or []
                object_type = ""
                if isinstance(obj_types, list):
                    for t in obj_types:
                        if isinstance(t, dict):
                            val = self._clean_html(t.get("value", ""))
                            if val:
                                object_type = val
                elif isinstance(obj_types, str):
                    object_type = self._clean_html(obj_types)

                # title / name
                names = src.get("name", [])
                object_name = ""
                titles = []
                for n in names:
                    if isinstance(n, dict) and n.get("type") == "object name":
                        v = n.get("value", "")
                        if v:
                            titles.append(v)
                object_name = " / ".join(titles) if titles else object_type

                # production date
                prod_date = ""
                pd = brief.get("Production date") or brief.get("production_date") or ""
                if isinstance(pd, list):
                    vals = []
                    for v in pd:
                        if isinstance(v, dict):
                            vals.append(self._clean_html(v.get("value", "")))
                    prod_date = "; ".join(vals)
                else:
                    prod_date = self._clean_html(str(pd))

                # findspot / place
                findspot_raw = brief.get("Findspot") or brief.get("findspot") or {}
                findspot = ""
                if isinstance(findspot_raw, dict):
                    findspot = self._clean_html(findspot_raw.get("value", ""))

                # culture / ethnicity
                culture_raw = brief.get("Culture/period") or brief.get("culture") or ""
                culture = ""
                if isinstance(culture_raw, list):
                    vals = [self._clean_html(c.get("value", "")) for c in culture_raw if isinstance(c, dict)]
                    culture = "; ".join(vals)
                else:
                    culture = self._clean_html(str(culture_raw))

                # material
                material_raw = brief.get("Material") or brief.get("material") or ""
                material = ""
                if isinstance(material_raw, list):
                    vals = [self._clean_html(m.get("value", "")) for m in material_raw if isinstance(m, dict)]
                    material = "; ".join(vals)
                else:
                    material = self._clean_html(str(material_raw))

                # museum number
                museum_no = self._clean_html(str(brief.get("Museum number") or brief.get("museum_number") or ""))

                # image
                identifiers = src.get("identifier", [])
                img_url = ""
                if src.get("multimedia"):
                    loc = (
                        src["multimedia"][0]
                        .get("@processed", {})
                        .get("large", {})
                        .get("location", "")
                    )
                    if loc:
                        img_url = f"{self.MEDIA_BASE}/{loc}"

                uid = self._extract_ident(identifiers, "unique object id")
                reg_num = self._extract_ident(identifiers, "registration number")
                object_url = f"{self.BASE}/collection/object/{uid}" if uid else ""

                yield {
                    "title": object_name,
                    "object_type": object_type,
                    "culture": culture,
                    "period": prod_date,
                    "material": material,
                    "findspot": findspot,
                    "object_name": object_name,
                    "museum_number": museum_no or reg_num,
                    "image_url": img_url,
                    "object_url": object_url,
                    "source": "british_museum",
                }

            browser.close()
