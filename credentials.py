"""
Credential storage and retrieval helpers for the JLCPCB auth plugin.

This module is the single source of truth for credential operations used by
tool handlers, hooks, and dashboard backend routes.
"""

from __future__ import annotations

import ast
import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

USERNAME_KEY = "JLCPCB_USERNAME"
PASSWORD_KEY = "JLCPCB_PASSWORD"


def env_file_path() -> Path:
    override = os.environ.get("HERMES_ENV_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".hermes" / ".env"


def get_credentials() -> tuple[str | None, str | None]:
    username = os.environ.get(USERNAME_KEY, "").strip() or None
    password = os.environ.get(PASSWORD_KEY, "").strip() or None

    if username and password:
        return username, password

    stored = _read_env_values()

    if not username:
        username = stored.get(USERNAME_KEY, "").strip() or None
        if username:
            os.environ[USERNAME_KEY] = username

    if not password:
        password = stored.get(PASSWORD_KEY, "").strip() or None
        if password:
            os.environ[PASSWORD_KEY] = password

    return username, password


def credentials_available() -> bool:
    username, password = get_credentials()
    return bool(username and password)


def username_hint() -> str:
    username, _ = get_credentials()
    if not username:
        return ""
    if len(username) <= 3:
        return "***"
    return username[:3] + "***"


def set_credentials(username: str, password: str) -> None:
    username = username.strip()
    password = password.strip()

    if not username or not password:
        raise ValueError("Username and password are required.")

    _upsert_env_values({
        USERNAME_KEY: username,
        PASSWORD_KEY: password,
    })

    os.environ[USERNAME_KEY] = username
    os.environ[PASSWORD_KEY] = password


def clear_credentials() -> None:
    _upsert_env_values({
        USERNAME_KEY: None,
        PASSWORD_KEY: None,
    })
    os.environ.pop(USERNAME_KEY, None)
    os.environ.pop(PASSWORD_KEY, None)


@contextmanager
def _env_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / ".env.lock"
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_env_values() -> dict[str, str]:
    path = env_file_path()
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for key, value, _raw in _parse_env_lines(path.read_text(encoding="utf-8")):
        if key is not None and value is not None:
            values[key] = value
    return values


def _upsert_env_values(values: dict[str, str | None]) -> None:
    path = env_file_path()

    with _env_file_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        original = path.read_text(encoding="utf-8") if path.exists() else ""
        lines = _parse_env_lines(original)

        seen: set[str] = set()
        updated: list[tuple[str | None, str | None, str | None]] = []

        for key, value, raw in lines:
            if key is None:
                updated.append((None, None, raw))
                continue

            if key in seen:
                continue
            seen.add(key)

            if key in values:
                replacement = values[key]
                if replacement is not None:
                    updated.append((key, replacement, None))
            else:
                updated.append((key, value or "", None))

        for key, value in values.items():
            if key in seen or value is None:
                continue
            updated.append((key, value, None))

        serialised = _serialise_env_lines(updated)
        _atomic_write(path, serialised)


def _parse_env_lines(content: str) -> list[tuple[str | None, str | None, str | None]]:
    parsed: list[tuple[str | None, str | None, str | None]] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            parsed.append((None, None, line))
            continue

        key_part, value_part = line.split("=", 1)
        key = key_part.strip()
        if key.startswith("export "):
            key = key[7:].strip()

        if not key or any(ch.isspace() for ch in key):
            parsed.append((None, None, line))
            continue

        parsed.append((key, _decode_env_value(value_part), None))

    return parsed


def _decode_env_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""

    if value[0] in {"'", '"'} and value[-1] == value[0]:
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, str):
                return parsed
        except Exception:
            return value[1:-1]

    return value


def _encode_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return f'"{escaped}"'


def _serialise_env_lines(lines: list[tuple[str | None, str | None, str | None]]) -> str:
    rendered: list[str] = []

    for key, value, raw in lines:
        if key is None:
            rendered.append(raw or "")
        else:
            rendered.append(f"{key}={_encode_env_value(value or '')}")

    if not rendered:
        return ""
    return "\n".join(rendered).rstrip("\n") + "\n"


def _atomic_write(path: Path, content: str) -> None:
    fd, temp_path = tempfile.mkstemp(prefix=".env.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        path.chmod(0o600)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
