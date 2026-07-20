"""Consistent SQLite backup, retention, scheduled backup, and safe restore."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from config import APP_TZINFO, BACKUP_DIR, BACKUP_HOUR, BACKUP_RETENTION_DAYS, DB_PATH

logger = logging.getLogger(__name__)


def _backup_root() -> Path:
    root = Path(BACKUP_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_backup(reason: str = "scheduled", db_path: str | None = None) -> Path:
    """Create an online SQLite backup and a small provenance manifest."""
    source_path = Path(db_path or DB_PATH).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Database tidak ditemukan: {source_path}")

    timestamp = datetime.now(APP_TZINFO).strftime("%Y-%m-%d_%H%M%S_%f_%z")
    safe_reason = "".join(c if c.isalnum() or c in "-_" else "-" for c in reason)[:40]
    destination = _backup_root() / f"ekraf_{timestamp}_{safe_reason}.db"

    source = sqlite3.connect(str(source_path), timeout=30)
    target = sqlite3.connect(str(destination), timeout=30)
    try:
        source.backup(target)
        check = target.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"Integritas backup gagal: {check}")
    finally:
        target.close()
        source.close()

    manifest = {
        "created_at": datetime.now(APP_TZINFO).isoformat(timespec="seconds"),
        "reason": reason,
        "source": str(source_path),
        "backup": destination.name,
        "size_bytes": destination.stat().st_size,
    }
    destination.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    prune_backups()
    logger.info("Backup database selesai: %s (%s)", destination, reason)
    return destination


def list_backups() -> list[Path]:
    return sorted(_backup_root().glob("ekraf_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def prune_backups(retention_days: int | None = None) -> int:
    days = retention_days if retention_days is not None else BACKUP_RETENTION_DAYS
    cutoff = datetime.now().timestamp() - days * 86400
    removed = 0
    for path in list_backups():
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            path.with_suffix(".json").unlink(missing_ok=True)
            removed += 1
    return removed


def backup_if_due() -> Path | None:
    latest = next(iter(list_backups()), None)
    if latest:
        age = datetime.now().timestamp() - latest.stat().st_mtime
        if age < 20 * 3600:
            return None
    return create_backup("scheduled")


def restore_backup(backup_name: str, *, confirm: str, db_path: str | None = None) -> Path:
    """Restore a verified backup; always creates a pre-restore safety backup."""
    if confirm != "RESTORE":
        raise ValueError("Konfirmasi restore tidak valid. Gunakan RESTORE.")

    root = _backup_root()
    source_path = (root / Path(backup_name).name).resolve()
    if source_path.parent != root or not source_path.exists() or source_path.suffix != ".db":
        raise FileNotFoundError("File backup tidak ditemukan atau berada di luar BACKUP_DIR.")

    source_check = sqlite3.connect(str(source_path))
    try:
        check = source_check.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"Backup rusak: {check}")
    finally:
        source_check.close()

    target_path = Path(db_path or DB_PATH).resolve()
    pre_restore = create_backup("pre-restore", str(target_path))
    source = sqlite3.connect(str(source_path), timeout=30)
    target = sqlite3.connect(str(target_path), timeout=30)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    log_entry = {
        "restored_at": datetime.now(APP_TZINFO).isoformat(timespec="seconds"),
        "restored_from": source_path.name,
        "pre_restore_backup": pre_restore.name,
    }
    restore_log = root / "restore-history.jsonl"
    with restore_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    logger.warning("Database dipulihkan dari %s", source_path)
    return pre_restore


def start_backup_scheduler(app) -> BackgroundScheduler | None:
    """Start one daily backup job for the current application process."""
    if not app.config.get("AUTO_BACKUP_ENABLED", True) or app.config.get("TESTING"):
        return None
    scheduler = BackgroundScheduler(timezone=APP_TZINFO)
    scheduler.add_job(
        backup_if_due,
        trigger="cron",
        hour=BACKUP_HOUR,
        minute=0,
        id="daily-sqlite-backup",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.start()
    app.extensions["backup_scheduler"] = scheduler
    return scheduler
