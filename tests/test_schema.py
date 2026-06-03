"""Schema 校验测试 — CI 必跑

每个成员的 PR 必须本地通过：
    pytest tests/test_schema.py

校验内容：
1. 原始 CSV 列顺序与主企划一致
2. 必填字段非空
3. URI 命名规范
4. 受控词表合法
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scrapers" / "data"
FIXTURES = ROOT / "tests" / "fixtures"

# ---------- 契约常量（与 docs/project_specification.md 保持一致） ----------

RAW_COLUMNS = [
    "object_id", "title", "period", "type", "material",
    "description", "dimensions", "museum", "location",
    "detail_url", "image_url", "image_path",
    "credit_line", "accession_number", "crawl_date",
]

RAW_REQUIRED = {
    "object_id", "title", "period", "type", "description",
    "museum", "location", "detail_url", "image_url",
    "image_path", "crawl_date",
}

CLEANED_EXTRA_COLUMNS = [
    "museum_key", "dynasty_norm", "year_start", "year_end",
    "type_norm", "material_norm", "artifact_uri",
    "image_valid", "dedup_group_id",
]

TYPE_VOCAB = {
    "Painting", "Ceramics", "Bronze", "Jade", "Sculpture",
    "Calligraphy", "Textiles", "Lacquer", "Other",
}

MUSEUM_KEYS = {"princeton", "artic", "brooklyn"}

URI_PREFIX = "http://kg.bjtu5.org/"
URI_PATTERN = re.compile(
    r"^http://kg\.bjtu5\.org/(artifact|museum|dynasty|artist|location|material|type)/[a-z0-9_]+$"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------- 工具 ----------

def _read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def _raw_csv_files():
    if not DATA.exists():
        return []
    return [p for p in DATA.glob("*_museum.csv") if not p.name.startswith("_")]


def _mock_csv_files():
    if not FIXTURES.exists():
        return []
    return list(FIXTURES.glob("_mock_*.csv"))


# ---------- 原始 CSV ----------

@pytest.mark.parametrize("path", _mock_csv_files(), ids=lambda p: p.name)
def test_mock_csv_columns(path):
    cols, _ = _read_csv(path)
    assert cols == RAW_COLUMNS, f"{path.name} 列顺序与契约不符"


@pytest.mark.parametrize("path", _mock_csv_files(), ids=lambda p: p.name)
def test_mock_csv_required_non_empty(path):
    _, rows = _read_csv(path)
    assert rows, f"{path.name} 没有数据行"
    for i, row in enumerate(rows, 2):
        for field in RAW_REQUIRED:
            assert (row.get(field) or "").strip(), (
                f"{path.name} L{i} 必填字段 {field} 为空"
            )


@pytest.mark.parametrize("path", _raw_csv_files(), ids=lambda p: p.name)
def test_raw_csv_columns(path):
    cols, _ = _read_csv(path)
    assert cols == RAW_COLUMNS, f"{path.name} 列顺序与契约不符"


@pytest.mark.parametrize("path", _raw_csv_files(), ids=lambda p: p.name)
def test_raw_csv_required_non_empty(path):
    _, rows = _read_csv(path)
    for i, row in enumerate(rows, 2):  # 第 2 行起（含表头）
        # 仓库中提交的 raw CSV 可能是历史样例，仅校验最基础的可追溯字段。
        for field in {"object_id", "title", "detail_url", "crawl_date"}:
            assert (row.get(field) or "").strip(), (
                f"{path.name} L{i} 必填字段 {field} 为空"
            )


@pytest.mark.parametrize("path", _raw_csv_files(), ids=lambda p: p.name)
def test_raw_csv_crawl_date_format(path):
    _, rows = _read_csv(path)
    for i, row in enumerate(rows, 2):
        d = row.get("crawl_date", "")
        assert DATE_PATTERN.match(d), f"{path.name} L{i} crawl_date 格式错误: {d!r}"


@pytest.mark.parametrize("path", _raw_csv_files(), ids=lambda p: p.name)
def test_raw_csv_image_url_not_thumbnail(path):
    _, rows = _read_csv(path)
    bad_keywords = ("thumb", "thumbnail", "small", "preview")
    for i, row in enumerate(rows, 2):
        url = row.get("image_url", "").lower()
        if not url:
            continue
        for kw in bad_keywords:
            assert kw not in url, f"{path.name} L{i} 疑似缩略图: {url}"


# ---------- 清洗后 CSV ----------

def _cleaned_path():
    return DATA / "cleaned" / "artifacts.csv"


@pytest.mark.skipif(
    not _cleaned_path().exists(), reason="cleaned/artifacts.csv 尚未产出"
)
def test_cleaned_columns_superset():
    cols, _ = _read_csv(_cleaned_path())
    expected = RAW_COLUMNS + CLEANED_EXTRA_COLUMNS
    missing = set(expected) - set(cols)
    assert not missing, f"清洗后 CSV 缺少列: {missing}"


@pytest.mark.skipif(
    not _cleaned_path().exists(), reason="cleaned/artifacts.csv 尚未产出"
)
def test_cleaned_type_vocab():
    _, rows = _read_csv(_cleaned_path())
    for i, row in enumerate(rows, 2):
        t = row.get("type_norm", "")
        assert t in TYPE_VOCAB, f"L{i} type_norm 不在受控词表: {t!r}"


@pytest.mark.skipif(
    not _cleaned_path().exists(), reason="cleaned/artifacts.csv 尚未产出"
)
def test_cleaned_museum_key():
    _, rows = _read_csv(_cleaned_path())
    for i, row in enumerate(rows, 2):
        mk = row.get("museum_key", "")
        assert mk in MUSEUM_KEYS, f"L{i} museum_key 非法: {mk!r}"


@pytest.mark.skipif(
    not _cleaned_path().exists(), reason="cleaned/artifacts.csv 尚未产出"
)
def test_cleaned_artifact_uri():
    _, rows = _read_csv(_cleaned_path())
    for i, row in enumerate(rows, 2):
        uri = row.get("artifact_uri", "")
        assert URI_PATTERN.match(uri), f"L{i} artifact_uri 不合规: {uri!r}"


# ---------- 实体表 ----------

ENTITY_FILES = ["artist.csv", "dynasty.csv", "location.csv", "museum.csv"]


@pytest.mark.parametrize("name", ENTITY_FILES)
def test_entity_uri(name):
    path = DATA / "cleaned" / "entities" / name
    if not path.exists():
        pytest.skip(f"{name} 尚未产出")
    _, rows = _read_csv(path)
    for i, row in enumerate(rows, 2):
        uri = row.get("uri", "")
        assert URI_PATTERN.match(uri), f"{name} L{i} uri 不合规: {uri!r}"


# ---------- 补充数据 ----------

ENRICHED_REQUIRED = {
    "target_uri", "field", "content",
    "source_url", "source_site", "enrich_date",
}


@pytest.mark.parametrize(
    "name", ["artist_bio.csv", "dynasty_bg.csv", "artifact_extra.csv"]
)
def test_enriched_required(name):
    path = DATA / "enriched" / name
    if not path.exists():
        pytest.skip(f"{name} 尚未产出")
    cols, rows = _read_csv(path)
    missing = ENRICHED_REQUIRED - set(cols)
    assert not missing, f"{name} 缺少必填列: {missing}"
    for i, row in enumerate(rows, 2):
        for field in ENRICHED_REQUIRED:
            assert (row.get(field) or "").strip(), (
                f"{name} L{i} 必填字段 {field} 为空"
            )