import csv
import json
from pathlib import Path
import yaml
import structlog

logger = structlog.get_logger()


def load_decisions(decisions_file: str) -> list[dict]:
    """
    Load decisions from a CSV file.

    Args:
        decisions_file: Path to the decisions CSV file.

    Returns:
        List of dicts with keys: candidate_id, decision, notes.
    """
    path = Path(decisions_file)
    if not path.exists():
        return []
    decisions = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("candidate_id"):
                decisions.append({
                    "candidate_id": row["candidate_id"],
                    "decision": row.get("decision", "").strip().lower(),
                    "notes": row.get("notes", ""),
                })
    return decisions


def apply_decisions(
    decisions_file: str,
    candidates_file: str,
    approved_file: str,
    rejected_file: str,
) -> None:
    """
    Apply human decisions from a CSV to candidates and write to YAML output files.

    Args:
        decisions_file: Path to decisions CSV.
        candidates_file: Path to candidates JSON.
        approved_file: Path to write approved sources YAML.
        rejected_file: Path to write rejected sources YAML.
    """
    decisions = load_decisions(decisions_file)
    if not decisions:
        logger.info("apply_decisions_no_decisions")
        return

    with open(candidates_file) as fh:
        candidates: list[dict] = json.load(fh)

    candidate_map = {c["candidate_id"]: c for c in candidates}

    approved = []
    rejected = []

    for decision in decisions:
        cid = decision["candidate_id"]
        candidate = candidate_map.get(cid)
        if not candidate:
            logger.warning("apply_decisions_candidate_not_found", candidate_id=cid)
            continue

        record = {
            "name": candidate.get("source_name", ""),
            "domain": _extract_domain_simple(candidate.get("homepage_url", "")),
            "homepage_url": candidate.get("homepage_url", ""),
            "feed_url": candidate.get("feed_url"),
            "jurisdiction": candidate.get("jurisdiction", "Unknown"),
            "source_type": candidate.get("source_type", "unknown"),
            "notes": decision.get("notes", ""),
        }

        if decision["decision"] == "add":
            approved.append(record)
            logger.info("apply_decisions_approved", name=record["name"])
        elif decision["decision"] == "reject":
            rejected.append(record)
            logger.info("apply_decisions_rejected", name=record["name"])

    _append_yaml(approved_file, approved)
    _append_yaml(rejected_file, rejected)
    logger.info("apply_decisions_done", approved=len(approved), rejected=len(rejected))


def _append_yaml(path: str, records: list[dict]) -> None:
    """Append records to a YAML file under a 'sources' key."""
    if not records:
        return
    p = Path(path)
    existing: dict = {}
    if p.exists():
        with open(p) as fh:
            existing = yaml.safe_load(fh) or {}
    sources = existing.get("sources", [])
    sources.extend(records)
    existing["sources"] = sources
    with open(p, "w") as fh:
        yaml.dump(existing, fh, default_flow_style=False, allow_unicode=True)


def _extract_domain_simple(url: str) -> str:
    """Extract domain from URL using a deferred import of url_utils."""
    from source_identifier_banking.url_utils import extract_domain
    return extract_domain(url)
