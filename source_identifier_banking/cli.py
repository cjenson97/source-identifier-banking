import argparse
import json
import os
from pathlib import Path
import structlog

logger = structlog.get_logger()


def _cmd_discover(args: argparse.Namespace) -> None:
    """Run the discovery pipeline."""
    from source_identifier_banking.discovery import DiscoveryRunner

    artifacts_dir = Path(args.output).parent
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runner = DiscoveryRunner(
        search_config_path=args.config,
        existing_sources_path=args.existing,
    )
    candidates = runner.run()

    candidates = candidates[: args.max_candidates]

    output_path = Path(args.output)
    with open(output_path, "w") as fh:
        json.dump(candidates, fh, indent=2)
    logger.info("discover_wrote_candidates", path=str(output_path), count=len(candidates))

    decisions_path = Path("artifacts/decisions.csv")
    if not decisions_path.exists():
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        with open(decisions_path, "w") as fh:
            fh.write("candidate_id,decision,notes\n")
        logger.info("discover_wrote_decisions_template", path=str(decisions_path))

    logger.info(
        "discover_summary",
        total=len(candidates),
        add=sum(1 for c in candidates if c["recommended_action"] == "add"),
        watchlist=sum(1 for c in candidates if c["recommended_action"] == "watchlist"),
        reject=sum(1 for c in candidates if c["recommended_action"] == "reject"),
    )


def _cmd_import_sources(args: argparse.Namespace) -> None:
    """Import sources from an Excel file into existing_sources.yaml."""
    from source_identifier_banking.excel_importer import import_sources

    added = import_sources(
        file_path=args.file,
        existing_path=args.existing,
        sheet=args.sheet,
        replace=args.replace,
    )
    logger.info("import_sources_complete", added=added, output=args.existing)


def _cmd_serve(args: argparse.Namespace) -> None:
    """Start the local HTTP server."""
    from source_identifier_banking.server import run_server

    run_server(host=args.host, port=args.port, candidates_file=args.candidates)


def _cmd_apply_decisions(args: argparse.Namespace) -> None:
    """Apply human decisions to candidate sources."""
    from source_identifier_banking.decisions import apply_decisions

    apply_decisions(
        decisions_file=args.decisions,
        candidates_file=args.candidates,
        approved_file=args.approved,
        rejected_file=args.rejected,
    )


def main() -> None:
    """Entry point for the source-identifier-banking CLI."""
    parser = argparse.ArgumentParser(
        prog="source-identifier-banking",
        description="Financial Services horizon scanning source discovery tool.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Run source discovery pipeline.")
    discover_parser.add_argument(
        "--config", default="config/search_config.yaml", help="Path to search config YAML."
    )
    discover_parser.add_argument(
        "--existing", default="config/existing_sources.yaml", help="Path to existing sources YAML."
    )
    discover_parser.add_argument(
        "--output", default="artifacts/candidate_sources.json", help="Output JSON path."
    )
    discover_parser.add_argument(
        "--max-candidates", type=int, default=50, help="Maximum candidates to output."
    )

    import_parser = subparsers.add_parser(
        "import-sources", help="Import existing sources from an Excel (.xlsx) file."
    )
    import_parser.add_argument(
        "--file", required=True, help="Path to the .xlsx file to import."
    )
    import_parser.add_argument(
        "--sheet", default=None, help="Sheet name to read (default: first sheet)."
    )
    import_parser.add_argument(
        "--existing",
        default="config/existing_sources.yaml",
        help="Path to existing_sources.yaml to update.",
    )
    import_parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace all existing entries instead of merging.",
    )

    apply_parser = subparsers.add_parser("apply-decisions", help="Apply human decisions to candidates.")
    apply_parser.add_argument(
        "--decisions", default="artifacts/decisions.csv", help="Path to decisions CSV."
    )
    apply_parser.add_argument(
        "--candidates", default="artifacts/candidate_sources.json", help="Path to candidates JSON."
    )
    apply_parser.add_argument(
        "--approved", default="config/approved_sources.yaml", help="Path to write approved YAML."
    )
    apply_parser.add_argument(
        "--rejected", default="config/rejected_sources.yaml", help="Path to write rejected YAML."
    )

    serve_parser = subparsers.add_parser(
        "serve", help="Start a local HTTP server to browse candidate sources."
    )
    serve_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)."
    )
    serve_parser.add_argument(
        "--port", type=int, default=8000, help="Port to listen on (default: 8000)."
    )
    serve_parser.add_argument(
        "--candidates",
        default="artifacts/candidate_sources.json",
        help="Path to candidates JSON file to serve.",
    )

    args = parser.parse_args()

    if args.command == "discover":
        _cmd_discover(args)
    elif args.command == "import-sources":
        _cmd_import_sources(args)
    elif args.command == "apply-decisions":
        _cmd_apply_decisions(args)
    elif args.command == "serve":
        _cmd_serve(args)
