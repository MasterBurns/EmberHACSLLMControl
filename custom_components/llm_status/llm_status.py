"""Dienstprogramm-Funktionen für den lokalen LLM-Status."""

from __future__ import annotations


def is_running(status: dict) -> bool:
    """Gibt an, ob der LLM-Prozess läuft."""
    return bool(status.get("process"))


def pid(status: dict) -> int | None:
    """Gibt die PID des LLM-Prozesses zurück."""
    return (status.get("process") or {}).get("pid")


def health_ok(status: dict) -> bool:
    """Gibt an, ob der Gesundheitsstatus positiv ist."""
    health = status.get("health") or {}
    return health.get("ok", False)
