"""Command line entry point: ``pejip run|digest|connections|purge|export|delete-all``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from pejip.accounts import open_store
from pejip.ai.client import AIClient
from pejip.companies import load_search_config
from pejip.config import SearchConfig, Settings, account_ids, load_config
from pejip.cost import CostGuard, SqliteLedger
from pejip.delivery import make_sns_client, send_digest
from pejip.digest import Digest, render
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
)
from pejip.retention import delete_files, purge_files
from pejip.sources.email_alerts import S3Inbox, make_s3_client
from pejip.sources.http import PoliteClient

log = logging.getLogger("pejip")

# What a bad or missing network file raises.
_FILE_ERRORS = (ExportError, OSError, ValidationError, yaml.YAMLError)


def _load_profile(settings: Settings) -> CareerProfile | None:
    if settings.profile_parameter:
        client = make_ssm_client(settings.aws_region)
        return load_profile_parameter(client, settings.profile_parameter)
    return load_profile(settings.profile_path)


def _load_config(settings: Settings) -> tuple[SearchConfig, str | None]:
    return load_search_config(settings, make_ssm_client)


ROUTINE_PENDING = "the ranking routine has not analysed it yet"
# Each digest goes out two hours after its search; a latest run older than this
# means that search never finished. Monday's first digest follows Monday's
# first search, so weekends don't trip it.
STALE_RUN_HOURS = 4


def _unranked_reason(settings: Settings, profile: CareerProfile | None) -> str:
    """Why roles can't be ranked, naming every missing piece at once."""
    missing = []
    if profile is None:
        missing.append(
            f"no career profile is stored yet (SSM parameter {settings.profile_parameter})"
        )
    if settings.ranker == "routine":
        if profile is not None:
            missing.append(ROUTINE_PENDING)
    elif not settings.ai_enabled:
        missing.append("Claude access is not set up for this workload yet")
    return " and ".join(missing) or "ranking is not set up"


def _ai_client(settings: Settings, config: SearchConfig, ledger: SqliteLedger) -> AIClient | None:
    # The routine does the model step itself, so the run never calls the API then.
    if settings.ranker == "routine" or not settings.ai_enabled:
        return None
    return AIClient(config.ai, CostGuard(ledger))


def _cmd_run(settings: Settings) -> int:
    config, companies_note = _load_config(settings)
    profile = _load_profile(settings)
    store = open_store(settings)
    ledger = SqliteLedger(settings.ai_ledger_path)
    http = PoliteClient(config.fetch)
    network, network_problem = _network(config, settings)
    inbox = None
    if settings.inbox_bucket:
        inbox = S3Inbox(
            make_s3_client(settings.aws_region), settings.inbox_bucket, settings.inbox_prefix
        )
    try:
        digest = Pipeline(
            config,
            profile,
            store,
            _ai_client(settings, config, ledger),
            http,
            inbox=inbox,
            network=network,
            unranked_reason=_unranked_reason(settings, profile),
            routine=settings.ranker == "routine",
        ).run()
    finally:
        http.close()
        ledger.close()
    if companies_note:
        digest.notes.append(companies_note)
    if network_problem:
        digest.notes.append(f"Connections were not used this run: {network_problem}.")
    if settings.ranker == "routine":
        # `pejip digest` emails it once the routine has analysed the new roles.
        log.info("digest_deferred", extra={"status": digest.status})
        _purge_output(settings, config.retention_days)
    else:
        _deliver(settings, config, digest)
    return 1 if digest.status == "FAILED" else 0


def _cmd_digest(settings: Settings) -> int:
    """Score the latest run's roles with the analyses stored since, and email the digest."""
    config, companies_note = _load_config(settings)
    store = open_store(settings)
    run = store.latest_run()
    if run is None:
        log.error("digest_without_run")
        return 1
    profile = _load_profile(settings)
    network, network_problem = _network(config, settings)
    pipeline = Pipeline(
        config,
        profile,
        store,
        None,
        PoliteClient(config.fetch),
        network=network,
        unranked_reason=_unranked_reason(settings, profile),
        routine=settings.ranker == "routine",
    )
    try:
        digest = pipeline.digest_from(run)
    finally:
        pipeline.http.close()
    if companies_note:
        digest.notes.append(companies_note)
    if network_problem:
        digest.notes.append(f"Connections were not used this run: {network_problem}.")
    waiting = any(item.recommendation is None for item in digest.items)
    age = datetime.now(UTC) - run["started_at"]
    if age > timedelta(hours=STALE_RUN_HOURS):
        # The pejip-app-errors alarm emails Babu about this ERROR line.
        log.error("digest_run_stale", extra={"run_id": run["id"]})
        digest.notes.append(
            f"No search has finished since {run['started_at']:%Y-%m-%d %H:%M} UTC, so this "
            "digest repeats that search's roles. Check why the latest search failed."
        )
    elif profile is not None and waiting and not store.analyses_since(run["started_at"], "routine"):
        # The pejip-app-errors alarm emails Babu about this ERROR line.
        log.error("routine_results_missing", extra={"run_id": run["id"]})
        digest.notes.append(
            "The ranking routine did not report after this morning's search, so new and "
            "changed roles are unranked. They will be offered to it again tomorrow."
        )
    _deliver(settings, config, digest)
    return 1 if digest.status == "FAILED" else 0


def _deliver(settings: Settings, config: SearchConfig, digest: Digest) -> None:
    """Write the digest, email it when a topic is set, and purge old digests."""
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


def _network(config: SearchConfig, settings: Settings) -> tuple[NetworkIndex | None, str | None]:
    """The connections index, or the reason it is unusable; a bad file never stops a run."""
    try:
        if settings.connections_path is not None:
            paths = settings.connections_path, settings.network_decisions_path
            index: NetworkIndex | None = load_index(config, *paths)[1]
        elif settings.network_bucket:
            client = make_s3_client(settings.aws_region)
            index = load_index_s3(client, settings.network_bucket, config, settings.network_prefix)
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
    deleted = open_store(settings).purge_expired(datetime.now(UTC), config.retention_days)
    log.info("purge_finished", extra={"deleted_rows": deleted})
    _purge_output(settings, config.retention_days)
    return 0


def _purge_output(settings: Settings, retention_days: int) -> None:
    """Delete digests and exports past the retention window (policy section 10)."""
    deleted = purge_files(settings.output_dir, datetime.now(UTC), retention_days)
    log.info("output_purged", extra={"deleted_files": deleted})


def _cmd_export(settings: Settings, out: Path) -> int:
    out.write_text(open_store(settings).export_all(), encoding="utf-8")
    log.info("export_written", extra={"path": str(out)})
    return 0


def _cmd_delete_all(settings: Settings, confirmed: bool) -> int:
    if not confirmed:
        sys.stderr.write("Refusing to delete without --yes.\n")
        return 2
    open_store(settings).delete_all()
    deleted = delete_files(settings.output_dir)
    log.info("all_data_deleted", extra={"account": settings.account, "deleted_files": deleted})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pejip", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run one search and write the digest")
    sub.add_parser("digest", help="email the latest run's digest, ranked again")
    conn = sub.add_parser("connections", help="check a LinkedIn Connections export")
    conn.add_argument("file", type=Path)
    sub.add_parser("purge", help="delete data past the retention window")
    export = sub.add_parser("export", help="export all stored data as JSON")
    export.add_argument("out", type=Path)
    delete = sub.add_parser("delete-all", help="delete all stored data and digests")
    delete.add_argument("--yes", action="store_true", help="confirm deletion")
    for command in (export, delete):
        command.add_argument(
            "--account", help="the account to act on (default: PEJIP_ACCOUNT, else Babu's)"
        )
    return parser


# The scheduled commands, run once per account (design doc 0016).
_SCHEDULED: dict[str, Callable[[Settings], int]] = {
    "run": _cmd_run,
    "digest": _cmd_digest,
    "purge": _cmd_purge,
}


def _for_each_account(command: str) -> int:
    """Run a scheduled command for every account; one account's crash spares the rest.

    The pejip-app-errors alarm counts ERROR lines, and a run that crashes never
    logs run_finished, so each crash is logged at once (with the account id,
    never its email). The first crash is raised again once every account has
    had its turn, so the task still fails with its traceback.
    """
    worst, crashes = 0, list[Exception]()
    for account in account_ids(os.environ):
        try:
            worst = max(worst, _SCHEDULED[command](Settings.from_env(account=account)))
        except Exception as exc:  # noqa: BLE001 - one account must not stop the rest; re-raised below
            _log_crash(command, account)
            crashes.append(exc)
    if crashes:
        raise crashes[0]
    return worst


def _log_crash(command: str, account: str) -> None:
    if command == "run":
        log.exception("run_crashed", extra={"account": account})
    elif command == "digest":
        # As for run_crashed: a digest that never arrives must still alarm.
        log.exception("digest_crashed", extra={"account": account})
    else:
        log.exception("purge_crashed", extra={"account": account})


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging()
    if args.command in _SCHEDULED:
        return _for_each_account(args.command)
    settings = Settings.from_env(account=getattr(args, "account", None))
    if args.command == "connections":
        return _cmd_connections(settings, args.file)
    if args.command == "export":
        return _cmd_export(settings, args.out)
    return _cmd_delete_all(settings, args.yes)
