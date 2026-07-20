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
import sys
from pathlib import Path

import aiohttp
import psutil
import yaml
from aiohttp import ClientTimeout, web

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
        self._managed_process = None
        self._last_metrics = {}
        self._last_metrics_time = 0

    async def fetch_metrics(self):
        if not self._health_url:
            return None
        
        try:
            timeout = ClientTimeout(total=2)
            slots_url = self._config.get("slots_url", f"http://127.0.0.1:{self._config.get('llm_port', 11434)}/slots")
            
            # Initialize tracking structures if not present
            if not hasattr(self, '_slot_totals'):
                self._slot_totals = {}
                self._global_prompt_total = 0
                self._global_decoded_total = 0
                self._last_metrics_time = 0
                self._last_metrics_totals = {"encode": 0, "decode": 0}

            async with aiohttp.ClientSession() as session:
                async with session.get(slots_url, timeout=timeout) as resp:
                    if resp.status == 200:
                        slots_data = await resp.json()
                        
                        current_time = time.time()
                        metrics_data = {"encode_total": 0, "decode_total": 0, "encode_tps": 0.0, "decode_tps": 0.0}
                        
                        for slot in slots_data:
                            slot_id = slot.get("id", 0)
                            
                            # Parse prompt tokens
                            current_prompt = slot.get("n_prompt_tokens_processed")
                            if current_prompt is None:
                                current_prompt = 0
                                
                            # Parse decoded tokens
                            current_decoded = 0
                            next_token_info = slot.get("next_token")
                            if next_token_info and isinstance(next_token_info, list) and len(next_token_info) > 0:
                                current_decoded = next_token_info[0].get("n_decoded", 0)
                            
                            if slot_id not in self._slot_totals:
                                self._slot_totals[slot_id] = {"prompt": 0, "decoded": 0}
                                
                            last_prompt = self._slot_totals[slot_id]["prompt"]
                            last_decoded = self._slot_totals[slot_id]["decoded"]
                            
                            delta_prompt = current_prompt - last_prompt
                            if delta_prompt < 0:
                                delta_prompt = current_prompt
                                
                            delta_decoded = current_decoded - last_decoded
                            if delta_decoded < 0:
                                delta_decoded = current_decoded
                                
                            self._global_prompt_total += delta_prompt
                            self._global_decoded_total += delta_decoded
                            
                            self._slot_totals[slot_id]["prompt"] = current_prompt
                            self._slot_totals[slot_id]["decoded"] = current_decoded
                        
                        metrics_data["encode_total"] = self._global_prompt_total
                        metrics_data["decode_total"] = self._global_decoded_total
                        
                        time_delta = current_time - self._last_metrics_time
                        if self._last_metrics_time > 0 and time_delta > 0:
                            metrics_data["encode_tps"] = round((self._global_prompt_total - self._last_metrics_totals["encode"]) / time_delta, 1)
                            metrics_data["decode_tps"] = round((self._global_decoded_total - self._last_metrics_totals["decode"]) / time_delta, 1)
                            
                            if metrics_data["encode_tps"] < 0:
                                metrics_data["encode_tps"] = 0.0
                            if metrics_data["decode_tps"] < 0:
                                metrics_data["decode_tps"] = 0.0
                                
                        self._last_metrics_time = current_time
                        self._last_metrics_totals["encode"] = self._global_prompt_total
                        self._last_metrics_totals["decode"] = self._global_decoded_total
                        return metrics_data
        except Exception as e:
            logger.error("Fehler beim Abrufen der Slot-Metriken: %s", e)
        return None

    def find_process(self):
        """Gibt die laufende LLM-Prozess-Information fuer RAM/CPU zurueck oder None."""
        target = None
        for proc in psutil.process_iter(["pid", "cmdline", "name", "status"]):
            try:
                info = proc.info
                cmdline = info.get("cmdline") or []
                if info.get("name") == self._process_match or any(
                    self._process_match in part for part in cmdline
                ):
                    target = proc
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not target:
            return None

        try:
            mem = target.memory_info()
            cpu = target.cpu_percent(interval=0.1)
            return {
                "pid": target.pid,
                "status": target.status(),
                "cmdline": " ".join(target.cmdline()),
                "cpu_percent": cpu,
                "memory_mb": round(mem.rss / 1024 / 1024, 2),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def is_managed_running(self):
        if not self._managed_process:
            return False
        return self._managed_process.returncode is None

    async def check_health(self, pid=None):
        """Prueft die API-/Health-URL der LLM, falls konfiguriert."""
        if not self._health_url:
            return None
        try:
            timeout = ClientTimeout(total=3)
            async with aiohttp.ClientSession() as session:
                async with session.get(self._health_url, timeout=timeout) as resp:
                    data = await resp.json()
                    data["pid"] = pid
                    return data
        except Exception as exc:
            logger.debug("Health check failed: %s", exc)
            return {"status": "error", "error": str(exc), "pid": pid}

    async def drain_pipe(self, pipe, log_level=logging.INFO):
        """Verhindert Blockaden durch volle Subprocess-Pipes."""
        while True:
            line = await pipe.readline()
            if line:
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                logger.log(log_level, text)
            else:
                break

    async def wait_for_health(self, timeout=120):
        """Wartet, bis der LLM-Server antwortet."""
        if not self._health_url or not self._managed_process:
            return None

        start = asyncio.get_event_loop().time()
        while True:
            if self._managed_process.returncode is not None:
                raise RuntimeError(f"LLM-Prozess mit PID {self._managed_process.pid} wurde beendet.")
            try:
                timeout_val = ClientTimeout(total=1)
                async with aiohttp.ClientSession() as session:
                    async with session.get(self._health_url, timeout=timeout_val) as resp:
                        data = await resp.json()
                        data["pid"] = self._managed_process.pid
                        return data
            except Exception:
                pass

            if asyncio.get_event_loop().time() - start > timeout:
                raise TimeoutError(f"Health-Check unter {self._health_url} dauerte zu lang.")
            await asyncio.sleep(0.5)
        return None

    async def start(self):
        """Startet den konfigurierten LLM-Prozess."""
        if self.is_managed_running() or self.find_process() is not None:
            raise RuntimeError("LLM-Prozess laeuft bereits.")
        command = self._command if isinstance(self._command, list) else [str(self._command)]
        env = os.environ.copy()
        args = []
        for item in command:
            item = str(item).strip()
            if "=" in item and not item.startswith("-"):
                key, _, value = item.partition("=")
                env[key.strip()] = value.strip()
            else:
                args.append(item)
        if not args:
            raise ValueError("Kein Startbefehl in config.yaml konfiguriert.")
        cwd = self._cwd if isinstance(self._cwd, str) and self._cwd else None
        self._managed_process = await asyncio.create_subprocess_exec(
            args[0],
            *args[1:],
            cwd=cwd or None,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        logger.info("LLM-Prozess gestartet: %s PID=%s", args[0], self._managed_process.pid)

        async def drain():
            while self._managed_process and self._managed_process.returncode is None:
                await self.drain_pipe(self._managed_process.stdout, logging.INFO)
                await self.drain_pipe(self._managed_process.stderr, logging.WARNING)
                await asyncio.sleep(0.2)

        asyncio.create_task(drain())
        await self.wait_for_health(timeout=120)
        return await self.status()

    async def stop(self):
        """Stoppt den gestarteten LLM-Prozess."""
        # 1. Beende den vom Skript gestarteten Prozess
        if self._managed_process and self.is_managed_running():
            try:
                self._managed_process.terminate()
                await asyncio.wait_for(self._managed_process.wait(), timeout=10)
            except Exception:
                self._managed_process.kill()
            self._managed_process = None

        # 2. Beende manuell gestartete Prozesse
        found = self.find_process()
        if found:
            try:
                proc = psutil.Process(found["pid"])
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    proc.kill()
            except psutil.NoSuchProcess:
                pass
                
        return await self.status()

    async def status(self):
        managed_running = self.is_managed_running()
        process = None
        
        if managed_running and self._managed_process:
            process = {
                "pid": self._managed_process.pid,
                "status": "managed_running",
                "managed": True,
                "cpu_percent": 0,
                "memory_mb": 0,
            }
            try:
                psutil_proc = psutil.Process(self._managed_process.pid)
                process["cpu_percent"] = psutil_proc.cpu_percent(interval=0.1)
                process["memory_mb"] = round(psutil_proc.memory_info().rss / 1024 / 1024, 2)
            except Exception:
                pass
        else:
            found = self.find_process()
            if found:
                process = found
                process["managed"] = False

        is_running = process is not None
        health = None
        metrics_data = {"encode_total": 0, "decode_total": 0, "encode_tps": 0.0, "decode_tps": 0.0}

        if process and self._health_url:
            health = await self.check_health(process["pid"])
            metrics_result = await self.fetch_metrics()
            if metrics_result:
                metrics_data = metrics_result

        return {
            "name": self._name,
            "running": is_running,
            "process": process,
            "health": health,
            "metrics": metrics_data,
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


async def handle_shutdown(request):
    logger.info("System shutdown requested via API")
    async def do_shutdown():
        await asyncio.sleep(1)
        os.system("sudo shutdown -h now")
    asyncio.create_task(do_shutdown())
    return web.json_response({"status": "shutting_down"})


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
    app.router.add_post("/api/system_shutdown", handle_shutdown)
    app.router.add_get("/", handle_status)
    return app


def main():
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    config = yaml.safe_load(CONFIG_PATH.open()) or {}
    web.run_app(app, host=config.get("host", "0.0.0.0"), port=config.get("port", 8080), handle_signals=True)


if __name__ == "__main__":
    main()
