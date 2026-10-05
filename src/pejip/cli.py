"""Command line entry point: ``pejip run|connections|purge|export|delete-all``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from pejip.ai.client import AIClient
from pejip.config import (
    SearchConfig,
    Settings,
    load_config,
    parse_private_companies,
    with_private_companies,
)
from pejip.cost import CostGuard, SqliteLedger
from pejip.delivery import make_sns_client, send_digest
from pejip.digest import render
from pejip.logs import configure_logging
from pejip.network.linkedin import ExportError
from pejip.network.loader import load_index, load_index_s3
from pejip.network.matching import YOUR_CALL, NetworkIndex
from pejip.pipeline import Pipeline
from pejip.profile import (
    CareerProfile,
    load_profile,
    load_profile_parameter,
    make_ssm_client,
    read_parameter,
)
from pejip.retention import purge_files
from pejip.sources.email_alerts import S3Inbox, make_s3_client
from pejip.sources.http import PoliteClient
from pejip.store import Store

log = logging.getLogger("pejip")

# What a bad or missing network file raises.
_FILE_ERRORS = (ExportError, OSError, ValidationError, yaml.YAMLError)


def _load_profile(settings: Settings) -> CareerProfile | None:
    if settings.profile_parameter:
        client = make_ssm_client(settings.aws_region)
        return load_profile_parameter(client, settings.profile_parameter)
    return load_profile(settings.profile_path)


def _load_config(settings: Settings) -> tuple[SearchConfig, str | None]:
    """The search configuration with Babu's private companies, and a note if they are missing.

    A malformed company list raises: searching without it would look like a quiet
    day rather than a broken setup.
    """
    config = load_config(settings.config_path)
    if settings.companies_parameter:
        text = read_parameter(make_ssm_client(settings.aws_region), settings.companies_parameter)
        if text is None:
            return config, (
                "Your company list is not stored yet (SSM parameter"
                f" {settings.companies_parameter}), so only the test boards were searched."
            )
    elif settings.companies_path:
        text = settings.companies_path.read_text(encoding="utf-8")
    else:
        return config, None
    return with_private_companies(config, parse_private_companies(text)), None


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
    config, companies_note = _load_config(settings)
    profile = _load_profile(settings)
    store = Store(settings.database_url)
    ledger = SqliteLedger(settings.ai_ledger_path)
    http = PoliteClient(config.fetch)
    network, network_problem = _network(config, settings)
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
            network=network,
            unranked_reason=_unranked_reason(settings, profile),
        ).run()
    finally:
        http.close()
        ledger.close()
    if companies_note:
        digest.notes.append(companies_note)
    if network_problem:
        digest.notes.append(f"Connections were not used this run: {network_problem}.")
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


def _network(config: SearchConfig, settings: Settings) -> tuple[NetworkIndex | None, str | None]:
    """The connections index, or the reason it is unusable; a bad file never stops a run."""
    try:
        if settings.connections_path is not None:
            paths = settings.connections_path, settings.network_decisions_path
            index: NetworkIndex | None = load_index(config, *paths)[1]
        elif settings.network_bucket:
            client = make_s3_client(settings.aws_region)
            index = load_index_s3(client, settings.network_bucket, config)
        else:
            index = None
    except (*_FILE_ERRORS, ClientError, BotoCoreError) as exc:
        # Only the error type is logged: the message can quote the files' contents.
        log.warning("network_unavailable", extra={"error_type": type(exc).__name__})
        return None, _problem(exc)
    return index, None


def _problem(exc: Exception) -> str:
    """A reason for the candidate, naming the file at fault."""
    if isinstance(exc, ExportError):
        return f"the LinkedIn export could not be read ({exc})"
    if isinstance(exc, ValidationError):
        return "the network decisions file has an invalid entry"
    if isinstance(exc, yaml.YAMLError):
        return "the network decisions file is not valid YAML"
    return f"a network file could not be opened ({type(exc).__name__})"


def _cmd_connections(settings: Settings, path: Path) -> int:
    """Check a LinkedIn export before using it: counts and names to review, no people."""
    config, _ = _load_config(settings)
    try:
        preview, index = load_index(config, path, settings.network_decisions_path)
    except _FILE_ERRORS as exc:
        sys.stderr.write(f"Cannot use {path}: {_problem(exc)}\n")
        return 2
    out = [
        f"Rows read: {preview.records_parsed}",
        f"Valid connections: {preview.records_accepted}",
        f"Duplicates merged: {preview.duplicates}",
        f"Rejected: {len(preview.rejected)}",
    ]
    reasons: dict[str, list[int]] = {}
    for row in preview.rejected:
        reasons.setdefault(row.reason, []).append(row.line)
    out += [f"  {reason}: lines {_lines(lines)}" for reason, lines in sorted(reasons.items())]
    out.append("At tracked companies:")
    out += _company_lines(index) or ["  none"]
    out.append("Employer names to review:")
    out += [
        f"  {raw}: {index.held_back[raw]} held back, could be {' or '.join(res.candidates)}"
        for raw, res in sorted(index.unresolved.items())
    ] or ["  none"]
    sys.stdout.write("\n".join(out) + "\n")
    return 0


def _lines(lines: list[int], limit: int = 5) -> str:
    shown = ", ".join(str(n) for n in lines[:limit])
    return shown + (f" and {len(lines) - limit} more" if len(lines) > limit else "")


def _company_lines(index: NetworkIndex) -> list[str]:
    """Per company: connections, and those with no clear level (judged against a VP role)."""
    lines = []
    for company in sorted(index.by_company):
        signal = index.signal(company, "VP")
        unclear = len(signal.by_status(YOUR_CALL))
        lines.append(f"  {company}: {len(signal.matches)} connections, {unclear} unclear titles")
    return lines


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
    conn = sub.add_parser("connections", help="check a LinkedIn Connections export")
    conn.add_argument("file", type=Path)
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
    if args.command == "connections":
        return _cmd_connections(settings, args.file)
    if args.command == "purge":
        return _cmd_purge(settings)
    if args.command == "export":
        return _cmd_export(settings, args.out)
    return _cmd_delete_all(settings, args.yes)
