"""Command line entry point: ``pejip run|purge|export|delete-all``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pejip.ai.client import AIClient
from pejip.config import Settings, load_config
from pejip.cost import CostGuard, SqliteLedger
from pejip.delivery import make_sns_client, send_digest
from pejip.digest import render
from pejip.logs import configure_logging
from pejip.pipeline import Pipeline
from pejip.profile import CareerProfile, load_profile, load_profile_parameter, make_ssm_client
from pejip.retention import purge_files
from pejip.sources.email_alerts import S3Inbox, make_s3_client
from pejip.sources.http import PoliteClient
from pejip.store import Store

log = logging.getLogger("pejip")


def _load_profile(settings: Settings) -> CareerProfile | None:
    if settings.profile_parameter:
        client = make_ssm_client(settings.aws_region)
        return load_profile_parameter(client, settings.profile_parameter)
    return load_profile(settings.profile_path)


def _unranked_reason(settings: Settings, profile: CareerProfile | None) -> str:
    """Why roles can't be ranked, naming every missing piece at once."""
    missing = []
    if profile is None:
        missing.append(
            f"no career profile is stored yet (SSM parameter {settings.profile_parameter})"
        )
    if not settings.ai_enabled:
        missing.append("Claude access is not set up for this workload yet")
    return " and ".join(missing) or "ranking is not set up"


def _cmd_run(settings: Settings) -> int:
    config = load_config(settings.config_path)
    profile = _load_profile(settings)
    store = Store(settings.database_url)
    ledger = SqliteLedger(settings.ai_ledger_path)
    http = PoliteClient(config.fetch)
    inbox = None
    if settings.inbox_bucket:
        inbox = S3Inbox(make_s3_client(settings.aws_region), settings.inbox_bucket)
    try:
        ai = AIClient(config.ai, CostGuard(ledger)) if settings.ai_enabled else None
        digest = Pipeline(
            config,
            profile,
            store,
            ai,
            http,
            inbox=inbox,
            unranked_reason=_unranked_reason(settings, profile),
        ).run()
    finally:
        http.close()
        ledger.close()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    path = settings.output_dir / f"digest-{digest.generated_at:%Y%m%d-%H%M%S}.md"
    text = render(digest, config.scoring.strong_match_fit)
    path.write_text(text, encoding="utf-8")
    log.info("digest_written", extra={"path": str(path), "status": digest.status})
    try:
        if settings.digest_topic_arn:
            client = make_sns_client(settings.aws_region)
            send_digest(client, settings.digest_topic_arn, digest, text, kept_at=str(path))
            log.info("digest_sent", extra={"status": digest.status})
    finally:
        # Retention holds even when the email fails (policy section 10).
        _purge_output(settings, config.retention_days)
    return 1 if digest.status == "FAILED" else 0


def _cmd_purge(settings: Settings) -> int:
    config = load_config(settings.config_path)
    deleted = Store(settings.database_url).purge_expired(datetime.now(UTC), config.retention_days)
    log.info("purge_finished", extra={"deleted_rows": deleted})
    _purge_output(settings, config.retention_days)
    return 0


def _purge_output(settings: Settings, retention_days: int) -> None:
    """Delete digests and exports past the retention window (policy section 10)."""
    deleted = purge_files(settings.output_dir, datetime.now(UTC), retention_days)
    log.info("output_purged", extra={"deleted_files": deleted})


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging()
    settings = Settings.from_env()
    if args.command == "run":
        try:
            return _cmd_run(settings)
        except Exception:
            # The pejip-app-errors alarm counts ERROR lines; a run that crashes
            # never logs run_finished, so say so before the traceback.
            log.exception("run_crashed")
            raise
    if args.command == "purge":
        return _cmd_purge(settings)
    if args.command == "export":
        return _cmd_export(settings, args.out)
    return _cmd_delete_all(settings, args.yes)
