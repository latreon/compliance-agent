"""Scan-history storage for the web dashboard.

Envelopes are stored as JSON files under the user data directory
(``$XDG_DATA_HOME/compliance-agent/history/<project-key>/``), one directory per
scanned project, newest first, capped so the dashboard cannot grow unbounded.
Storage is per-user and local — nothing ever leaves the machine.
"""

import contextlib
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_ENTRIES = 50
_ENTRY_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{9}$")
_MAX_ID_ATTEMPTS = 1000


def _data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "compliance-agent" / "history"


def project_key(project_path: Path) -> str:
    """Stable directory name for a project (hash of its resolved path)."""
    resolved = str(Path(project_path).resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


def _project_dir(project_path: Path) -> Path:
    return _data_dir() / project_key(project_path)


def _reserve_entry_path(target_dir: Path) -> tuple[str, Path]:
    """Atomically claim a not-yet-used timestamp id.

    Two ``/api/scan`` calls that finish within the same millisecond would
    otherwise compute the same entry id; a bare ``write_text`` from both
    could interleave and corrupt the file (write-write race, no locking).
    ``O_CREAT | O_EXCL`` makes the claim atomic, and the timestamp is bumped
    by a millisecond (the id's actual resolution) on each collision so the
    id shape (and the ``_ENTRY_ID_RE`` contract other code relies on) never
    changes.
    """
    now = datetime.now()
    for _ in range(_MAX_ID_ATTEMPTS):
        candidate = now.strftime("%Y%m%dT%H%M%S%f")[:18]
        path = target_dir / f"{candidate}.json"
        # Re-check right before the actual open — narrows (does not fully
        # close; that would need dir_fd-relative opens throughout) the race
        # window between save()'s earlier is_symlink() check and this call.
        if target_dir.is_symlink():
            raise OSError(f"Refusing to write through symlink: {target_dir}")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            now += timedelta(milliseconds=1)
            continue
        os.close(fd)
        return candidate, path
    raise OSError(f"Could not reserve a unique history entry id under {target_dir}")


def save(project_path: Path, envelope: dict) -> str | None:
    """Persist a scan envelope; returns its entry id (None on failure).

    Best-effort: a read-only home directory must never break a scan.
    """
    target_dir = _project_dir(project_path)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        if target_dir.is_symlink():
            # Refuse to follow a symlink planted at the exact project-key
            # path (e.g. by another local account with write access to this
            # user's data dir) into an attacker-chosen location.
            raise OSError(f"Refusing to write through symlink: {target_dir}")
        entry_id, path = _reserve_entry_path(target_dir)
        path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        _prune(target_dir)
    except OSError as exc:
        logger.warning("Cannot save scan history: %s", exc)
        return None
    return entry_id


def _prune(target_dir: Path) -> None:
    entries = sorted(target_dir.glob("*.json"), reverse=True)
    for stale in entries[MAX_ENTRIES:]:
        # already gone / permissions — pruning is best-effort
        with contextlib.suppress(OSError):
            stale.unlink()


def list_entries(project_path: Path) -> list[dict]:
    """Newest-first summaries of stored scans for a project."""
    target_dir = _project_dir(project_path)
    if not target_dir.is_dir():
        return []
    summaries: list[dict] = []
    for path in sorted(target_dir.glob("*.json"), reverse=True):
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Skipping unreadable history entry %s: %s", path.name, exc)
            continue
        # A syntactically valid JSON value of the wrong shape (`null`, a
        # list, a number — plausible after a disk-full/OOM-kill mid-write,
        # since the write above isn't atomic/fsynced) parses without error,
        # so it isn't caught above; guard the shape explicitly instead of
        # letting a bare .get() raise AttributeError and take down every
        # caller of list_entries (history listing, default diff, default
        # export) over one bad file.
        if not isinstance(envelope, dict):
            logger.warning("Skipping malformed history entry %s: not a JSON object", path.name)
            continue
        result = envelope.get("scan_result")
        if not isinstance(result, dict):
            logger.warning(
                "Skipping malformed history entry %s: missing scan_result", path.name
            )
            continue
        findings = result.get("findings")
        gaps = result.get("gaps")
        summaries.append(
            {
                "id": path.stem,
                "scan_time": result.get("scan_time"),
                "risk_tier": result.get("risk_tier"),
                "findings": len(findings) if isinstance(findings, list) else 0,
                "gaps": len(gaps) if isinstance(gaps, list) else 0,
                "files_scanned": result.get("files_scanned", 0),
            }
        )
    return summaries


def load(project_path: Path, entry_id: str) -> dict | None:
    """Load a stored envelope by id; None when absent or invalid.

    The id is validated against the timestamp shape before touching the
    filesystem, so a crafted id can never traverse outside the history dir.
    """
    if not _ENTRY_ID_RE.match(entry_id):
        return None
    path = _project_dir(project_path) / f"{entry_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
