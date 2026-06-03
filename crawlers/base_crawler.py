import time
import random
import requests
from requests.exceptions import RequestException
from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any, Optional

class BaseCrawler(ABC):
    def __init__(self, user_agent: str = None, timeout: int = 10, max_retries: int = 3, min_delay: float = 0.5, max_delay: float = 1.5, proxies: Optional[dict] = None):
        self.session = requests.Session()
        if user_agent:
            self.session.headers.update({"User-Agent": user_agent})
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.proxies = proxies

    def _sleep(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def fetch(self, url: str) -> str:
        """GET 带重试与指数退避。抛出异常由调用者处理。"""
        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                self._sleep()
                resp = self.session.get(url, timeout=self.timeout, proxies=self.proxies)
                if resp.status_code == 429:
                    # 被限速，指数退避并继续重试
                    time.sleep(backoff)
                    backoff *= 2
                    raise RequestException(f"429 Too Many Requests")
                resp.raise_for_status()
                return resp.text
            except RequestException as e:
                if attempt == self.max_retries:
                    raise
                time.sleep(backoff)
                backoff *= 2
        raise RequestException("Unreachable")

    def head(self, url: str) -> requests.Response:
        """HEAD 请求，用于快速检测资源可用性"""
        return self.session.head(url, timeout=self.timeout, proxies=self.proxies)

    @abstractmethod
    def crawl(self) -> Iterable[Dict[str, Any]]:
        """实现具体的爬虫，返回字典列表（每个代表一个条目）"""
        raise NotImplementedError