from typing import Iterable, Dict, Any
from bs4 import BeautifulSoup

from .base_crawler import BaseCrawler


class BrooklynMuseumCrawler(BaseCrawler):
    """示例：对 Brooklyn Museum 的 exhibitions 页面做简单解析，提取展览标题与链接。
    改为抓取文物列表时同时提取图片、年代、类型等字段（尽量通用的选择器示例）。"""

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)
        self.start_url = start_url

    def _abs_url(self, href: str) -> str:
        if href.startswith("/"):
            return "https://www.brooklynmuseum.org" + href
        return href

    def crawl(self) -> Iterable[Dict[str, Any]]:
        html = self.fetch(self.start_url)
        soup = BeautifulSoup(html, "html.parser")
        items = []
        # 根据常见结构尝试提取条目
        for card in soup.select(".exhibition-card, .object-card, .item, li.album-item"):
            title_el = card.select_one(".title, h3, h2, a")
            title = title_el.get_text(strip=True) if title_el else None

            img_el = card.select_one("img")
            img_src = img_el.get("data-src") or img_el.get("src") if img_el else None
            if img_src and img_src.startswith("/"):
                img_src = self._abs_url(img_src)

            link_el = card.select_one("a")
            href = link_el.get("href") if link_el else None
            if href:
                href = self._abs_url(href)

            # 年代/材质/类型 在列表页可能没有，保留详情页 URL 供后续抓取
            items.append({
                "title": title,
                "url": href,
                "image_url": img_src,
                "source": "brooklyn_museum",
            })

        return items


class BrooklynBotanicCrawler(BaseCrawler):
    """占位符：示例如何处理需要更多步骤（会场、活动列表等）。"""

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)
        self.start_url = start_url

    def _abs_url(self, href: str) -> str:
        if href.startswith("/"):
            return "https://www.bbg.org" + href
        return href

    def crawl(self) -> Iterable[Dict[str, Any]]:
        html = self.fetch(self.start_url)
        soup = BeautifulSoup(html, "html.parser")
        items = []
        # 简单示例：提取主页上的 headline 链接
        for a in soup.select("a"):
            title = a.get_text(strip=True)
            href = a.get("href")
            if href and title and len(title) > 5:
                href = self._abs_url(href)
                items.append({"title": title, "url": href, "image_url": None, "source": "brooklyn_botanic"})
        return items