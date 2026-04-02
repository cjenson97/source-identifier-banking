"""Import existing sources from an Excel (.xlsx) file into existing_sources.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import structlog
import yaml

logger = structlog.get_logger()

# Column names (lower-cased) that are accepted as the primary URL/domain column.
_URL_COLUMN_ALIASES = {"url", "link", "homepage", "domain", "website"}

# Mapping from our canonical field names to accepted lower-cased column aliases.
_OPTIONAL_COLUMN_ALIASES: dict[str, set[str]] = {
    "name": {"name", "source_name", "source name", "title"},
    "jurisdiction": {"jurisdiction", "region", "country"},
    "source_type": {"source_type", "type", "source type", "category"},
    "feed_url": {"feed_url", "feed", "rss", "rss_url", "rss url"},
}


def _detect_column(headers: list[str], aliases: set[str]) -> Optional[str]:
    """Return the first header (original case) whose lower-case form is in *aliases*."""
    for h in headers:
        if h.strip().lower() in aliases:
            return h
    return None


def _extract_domain(value: str) -> str:
    """Extract the hostname from a URL or return the value if it looks like a bare domain."""
    from source_identifier_banking.url_utils import extract_domain, normalize_domain

    value = value.strip()
    if not value:
        return ""
    # If no scheme present, treat as a bare domain.
    if "://" not in value:
        return normalize_domain(value)
    return extract_domain(value)


def read_excel_sources(file_path: str, sheet: Optional[str] = None) -> list[dict]:
    """
    Read source records from an Excel file.

    Args:
        file_path: Path to the .xlsx file.
        sheet: Sheet name or 0-based index (default: first sheet).

    Returns:
        List of source dicts with keys: domain, name, jurisdiction, source_type, feed_url.

    Raises:
        ValueError: If no recognisable URL/domain column is found.
        FileNotFoundError: If the file does not exist.
    """
    import openpyxl  # imported here so the rest of the package works without openpyxl installed

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    if sheet is None:
        ws = wb.worksheets[0]
    elif isinstance(sheet, int):
        ws = wb.worksheets[sheet]
    else:
        ws = wb[sheet]

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        logger.warning("excel_importer_empty_sheet", file=file_path)
        return []

    headers: list[str] = [str(h) if h is not None else "" for h in rows[0]]

    url_col = _detect_column(headers, _URL_COLUMN_ALIASES)
    if url_col is None:
        raise ValueError(
            f"No URL/domain column found in {file_path}. "
            f"Expected one of: {sorted(_URL_COLUMN_ALIASES)}"
        )

    optional_cols: dict[str, Optional[str]] = {
        field: _detect_column(headers, aliases)
        for field, aliases in _OPTIONAL_COLUMN_ALIASES.items()
    }

    url_idx = headers.index(url_col)
    optional_indices: dict[str, Optional[int]] = {
        field: headers.index(col) if col is not None else None
        for field, col in optional_cols.items()
    }

    sources: list[dict] = []
    for row in rows[1:]:
        raw_url = row[url_idx] if url_idx < len(row) else None
        if not raw_url:
            continue

        domain = _extract_domain(str(raw_url))
        if not domain:
            continue

        def _get(field: str) -> str:
            idx = optional_indices.get(field)
            if idx is None or idx >= len(row) or row[idx] is None:
                return ""
            return str(row[idx]).strip()

        sources.append({
            "name": _get("name") or domain,
            "domain": domain,
            "feed_url": _get("feed_url") or None,
            "jurisdiction": _get("jurisdiction") or "Unknown",
            "source_type": _get("source_type") or "unknown",
        })

    logger.info("excel_importer_read", file=file_path, rows=len(sources))
    return sources


def import_sources(
    file_path: str,
    existing_path: str,
    sheet: Optional[str] = None,
    replace: bool = False,
) -> int:
    """
    Read sources from *file_path* and write/merge them into *existing_path*.

    Args:
        file_path: Path to the .xlsx file.
        existing_path: Path to the existing_sources.yaml to update.
        sheet: Sheet name or index (default: first sheet).
        replace: If True, overwrite existing entries; if False, merge and deduplicate by domain.

    Returns:
        Number of new sources added.
    """
    new_sources = read_excel_sources(file_path, sheet=sheet)

    p = Path(existing_path)
    if replace or not p.exists():
        existing_data: dict = {}
    else:
        with open(p) as fh:
            existing_data = yaml.safe_load(fh) or {}

    existing_sources: list[dict] = existing_data.get("sources", [])

    if not replace:
        existing_domains: set[str] = {s.get("domain", "") for s in existing_sources}
        added = [s for s in new_sources if s["domain"] not in existing_domains]
    else:
        added = new_sources

    existing_sources.extend(added)
    existing_data["sources"] = existing_sources

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as fh:
        yaml.dump(existing_data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(
        "excel_importer_done",
        added=len(added),
        total=len(existing_sources),
        output=str(p),
    )
    return len(added)
