import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_CACHED_BUILD_INFO: Optional[Dict[str, Any]] = None


def clear_build_info_cache() -> None:
    """Clear in-memory cache of build info (primarily for testing)."""
    global _CACHED_BUILD_INFO
    _CACHED_BUILD_INFO = None


def _read_file_stripped(path: Path) -> Optional[str]:
    """Safely read text from a file if it exists and is readable."""
    try:
        if path.is_file():
            content = path.read_text(encoding="utf-8").strip()
            return content if content else None
    except Exception as exc:
        logger.debug("Failed to read build file %s: %s", path, exc)
    return None


def _get_git_output(args: list[str], cwd: Path) -> Optional[str]:
    """Safely execute a git command and return stripped stdout."""
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            out = res.stdout.strip()
            return out if out else None
    except Exception as exc:
        logger.debug("Git command execution failed: %s", exc)
    return None


def get_build_info() -> Dict[str, Any]:
    """
    Resolve build compilation metadata with startup in-memory caching.
    Inspects:
    1. Explicit environment variables or settings (APP_BUILD_TIME, APP_BUILD_COMMIT, APP_VERSION, APP_ENV)
    2. Container-baked files (/app/build_date.txt, /app/build_commit.txt or project root)
    3. Local Git repository inspection (git log, git rev-parse)
    4. Fallback defaults for local development
    """
    global _CACHED_BUILD_INFO
    if _CACHED_BUILD_INFO is not None:
        return _CACHED_BUILD_INFO

    base_dir = getattr(settings, "BASE_DIR", Path.cwd())
    if not isinstance(base_dir, Path):
        base_dir = Path(base_dir)

    # 1. Resolve Build Time
    build_time = (
        os.getenv("APP_BUILD_TIME", "")
        or os.getenv("BUILD_TIME", "")
        or getattr(settings, "APP_BUILD_TIME", "")
    ).strip()

    is_docker = False
    if not build_time:
        for candidate in [Path("/app/build_date.txt"), base_dir / "build_date.txt"]:
            file_time = _read_file_stripped(candidate)
            if file_time:
                build_time = file_time
                is_docker = True
                break

    # 2. Resolve Commit Hash
    commit_raw = (
        os.getenv("APP_BUILD_COMMIT", "")
        or os.getenv("BUILD_COMMIT", "")
        or getattr(settings, "APP_BUILD_COMMIT", "")
    ).strip()
    commit_short = commit_raw[:7] if commit_raw else ""

    if not commit_short:
        for candidate in [Path("/app/build_commit.txt"), base_dir / "build_commit.txt"]:
            file_commit = _read_file_stripped(candidate)
            if file_commit:
                commit_short = file_commit[:7]
                is_docker = True
                break

    # 3. Local Git fallback if not in Docker and metadata not yet found
    git_dir = base_dir / ".git"
    if (not build_time or not commit_short) and git_dir.exists():
        if not build_time:
            git_date = _get_git_output(
                ["log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M UTC"],
                cwd=base_dir,
            )
            if git_date:
                build_time = git_date
        if not commit_short:
            git_sha = _get_git_output(["rev-parse", "--short", "HEAD"], cwd=base_dir)
            if git_sha:
                commit_short = git_sha[:7]

    commit_short = commit_short if commit_short else None

    # Check container indicators
    if (
        os.path.exists("/.dockerenv")
        or os.getenv("DOCKER_CONTAINER")
        or Path("/app/build_date.txt").exists()
    ):
        is_docker = True

    # 4. Resolve Version
    version = (
        os.getenv("APP_VERSION", "")
        or getattr(settings, "APP_VERSION", "")
        or "1.0.0"
    ).strip()

    # 5. Resolve Environment
    env_str = (
        os.getenv("APP_ENV", "")
        or getattr(settings, "APP_ENV", "")
    ).strip().lower()

    if not env_str:
        is_debug = getattr(settings, "DEBUG", True)
        if not is_debug and is_docker:
            env_str = "production"
        elif not is_debug:
            env_str = "staging"
        else:
            env_str = "development"

    if env_str in ("prod", "production"):
        environment = "production"
        environment_badge = "PROD"
        badge_css = "bg-emerald-100 text-emerald-800 border border-emerald-300"
    elif env_str in ("stage", "staging"):
        environment = "staging"
        environment_badge = "STAGING"
        badge_css = "bg-amber-100 text-amber-800 border border-amber-300"
    else:
        environment = "development"
        environment_badge = "DEV"
        badge_css = "bg-slate-100 text-slate-700 border border-slate-300"

    # Default build_time display if still unresolved
    if not build_time:
        build_time = "Local Dev"

    # Formatted display string
    if commit_short:
        formatted_display = f"{build_time} ({commit_short})"
    else:
        formatted_display = build_time

    info = {
        "build_time": build_time,
        "commit_short": commit_short,
        "version": version,
        "is_docker": is_docker,
        "environment": environment,
        "environment_badge": environment_badge,
        "badge_css": badge_css,
        "formatted_display": formatted_display,
    }

    _CACHED_BUILD_INFO = info
    return info
