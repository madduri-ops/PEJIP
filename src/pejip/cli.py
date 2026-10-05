"""Command line entry point: ``pejip run|purge|export|delete-all|eval``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pejip.ai.client import AIClient
from pejip.config import Settings, load_config
from pejip.digest import render
from pejip.golden_eval import EvalPaths, run_eval
from pejip.logs import configure_logging
from pejip.pipeline import Pipeline
from pejip.profile import load_profile
from pejip.sources.http import PoliteClient
from pejip.store import Store

log = logging.getLogger("pejip")


def _cmd_run(settings: Settings) -> int:
    config = load_config(settings.config_path)
    profile = load_profile(settings.profile_path)
    store = Store(settings.database_url)
    http = PoliteClient(config.fetch)
    try:
        pipeline = Pipeline(config, profile, store, AIClient(config.ai, store), http)
        digest = pipeline.run()
    finally:
        http.close()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    path = settings.output_dir / f"digest-{digest.generated_at:%Y%m%d-%H%M%S}.md"
    path.write_text(render(digest, config.scoring.strong_match_fit), encoding="utf-8")
    log.info("digest_written", extra={"path": str(path), "status": digest.status})
    return 1 if digest.status == "FAILED" else 0


def _cmd_purge(settings: Settings) -> int:
    config = load_config(settings.config_path)
    deleted = Store(settings.database_url).purge_expired(datetime.now(UTC), config.retention_days)
    log.info("purge_finished", extra={"deleted_rows": deleted})
    return 0


def _cmd_export(settings: Settings, out: Path) -> int:
    out.write_text(Store(settings.database_url).export_all(), encoding="utf-8")
    log.info("export_written", extra={"path": str(out)})
    return 0


def _cmd_delete_all(settings: Settings, confirmed: bool) -> int:
    if not confirmed:
        sys.stderr.write("Refusing to delete without --yes.\n")
        return 2
    Store(settings.database_url).delete_all()
    log.info("all_data_deleted")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pejip", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run one search and write the digest")
    sub.add_parser("purge", help="delete data past the retention window")
    export = sub.add_parser("export", help="export all stored data as JSON")
    export.add_argument("out", type=Path)
    delete = sub.add_parser("delete-all", help="delete all stored data")
    delete.add_argument("--yes", action="store_true", help="confirm deletion")
    evaluate = sub.add_parser("eval", help="score the golden evaluation set")
    evaluate.add_argument("--live", action="store_true", help="call the model instead of replaying")
    evaluate.add_argument("--cases", type=Path, default=Path("evals/golden.yaml"))
    evaluate.add_argument("--baseline", type=Path, default=Path("evals/baseline.json"))
    evaluate.add_argument("--profile", type=Path, default=Path("examples/profile.example.yaml"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging()
    settings = Settings.from_env()
    if args.command == "run":
        return _cmd_run(settings)
    if args.command == "purge":
        return _cmd_purge(settings)
    if args.command == "export":
        return _cmd_export(settings, args.out)
    if args.command == "delete-all":
        return _cmd_delete_all(settings, args.yes)
    paths = EvalPaths(settings.config_path, args.cases, args.baseline, args.profile)
    return run_eval(paths, live=args.live)
