#!/usr/bin/env python3
"""Einfacher lokaler Webserver zur LLM-Prozess-Status-Abfrage und Steuerung.

Endpunkte:
  GET  /api/status
  POST /api/start
  POST /api/stop

Konfiguration wird aus config.yaml im gleichen Verzeichnis gelesen.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from subprocess import DEVNULL

import aiohttp
import psutil
import yaml
from aiohttp import web

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
logger = logging.getLogger(__name__)


class LLMManager:
    def __init__(self, config: dict):
        self._config = config
        self._name = config.get("name", "local_llm")
        self._port = int(config.get("manager_port", config.get("port", 8080)))
        self._health_url = config.get("health_url", "")
        self._command = config.get("command", [])
        self._cwd = config.get("cwd", "")
        self._process_match = config.get("process_match", "")
        self._process = None

    def find_process(self):
        """Gibt die laufende LLM-Prozess-Information zurück oder None."""
        for proc in psutil.process_iter(["pid", "cmdline", "name", "status", "cpu_percent", "memory_info"]):
            try:
                info = proc.info
                cmdline = info.get("cmdline") or []
                if info.get("name") == self._process_match or any(
                    self._process_match in part for part in cmdline
                ):
                    return {
                        "pid": info.get("pid"),
                        "status": info.get("status"),
                        "cmdline": " ".join(cmdline),
                        "cpu_percent": info.get("cpu_percent") or 0.0,
                        "memory_mb": (info.get("memory_info") or psutil.Process(proc.pid).memory_info()).rss / 1024 / 1024,
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    async def check_health(self, pid=None):
        """Prüft die API-/Health-URL der LLM, falls konfiguriert."""
        if not self._health_url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self._health_url, timeout=3) as resp:
                    data = await resp.json()
                    data["pid"] = pid
                    return data
        except Exception as exc:
            logger.debug("Health check failed: %s", exc)
            return {"ok": False, "error": str(exc), "pid": pid}

    async def start(self):
        """Startet die LLM mit der konfigurierten Kommandozeile."""
        if self.find_process():
            raise RuntimeError("LLM-Prozess läuft bereits.")
        # Verwende asyncio.create_subprocess_exec für die ersten Argumente + argv[1:]
        if not self._command:
            raise ValueError("Kein Startbefehl in config.yaml konfiguriert.")
        executable = self._command[0]
        args = self._command[1:]
        env = os.environ.copy()
        if self._cwd:
            env["CWD"] = self._cwd
        self._process = await asyncio.create_subprocess_exec(
            executable,
            *args,
            cwd=self._cwd or None,
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        await asyncio.sleep(2)
        return await self.status()

    async def stop(self):
        """Stoppt alle gefundenen LLM-Prozesse."""
        proc = self.find_process()
        if proc:
            pid = proc["pid"]
            for p in psutil.process_iter(["pid", "cmdline"]):
                try:
                    if any(self._process_match in part for part in (p.info.get("cmdline") or [])):
                        p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return await self.status()
        raise RuntimeError("Kein LLM-Prozess gefunden.")

    async def status(self):
        process = self.find_process()
        health = None
        if process and self._health_url:
            health = await self.check_health(process["pid"])
        return {
            "name": self._name,
            "running": process is not None,
            "process": process,
            "health": health,
            "port": self._port,
        }


manager = None


async def handle_status(request):
    return web.json_response(await manager.status())


async def handle_start(request):
    data = await request.json() if request.content_type == "application/json" else {}
    return web.json_response(await manager.start())


async def handle_stop(request):
    return web.json_response(await manager.stop())


def create_app():
    global manager

    if not CONFIG_PATH.exists():
        logger.error("config.yaml nicht gefunden: %s", CONFIG_PATH)
        sys.exit(1)

    with CONFIG_PATH.open() as f:
        config = yaml.safe_load(f) or {}
    manager = LLMManager(config)

    app = web.Application()
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/start", handle_start)
    app.router.add_post("/api/stop", handle_stop)
    app.router.add_get("/", handle_status)
    return app


def main():
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    config = yaml.safe_load(CONFIG_PATH.open()) or {}
    web.run_app(app, host=config.get("host", "0.0.0.0"), port=config.get("port", 8080), handle_signals=True)


if __name__ == "__main__":
    main()
