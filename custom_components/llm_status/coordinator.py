"""Datenkoordinator für lokale LLM-Status-Abfragen."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_HEALTH_ERROR,
    ATTR_HEALTH_OK,
    ATTR_HEALTH_URL,
    ATTR_IS_RUNNING,
    ATTR_MANAGED_BY,
    ATTR_MEMORY_MB,
    ATTR_NAME,
    ATTR_PID,
    ATTR_PORT,
    ATTR_PROCESS_CMDLINE,
    ATTR_PROCESS_CPU,
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_ACTIONS,
)

logger = logging.getLogger(__name__)


class LLMCoordinator(DataUpdateCoordinator):
    """Koordinator für den Status eines lokalen LLM-Manager-Servers."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_url: str,
        name: str = DOMAIN,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api_url = api_url
        self.scan_interval = scan_interval
        self._health_url = api_url.replace("/api/status", "/health", 1)
        self._api_prefix = api_url.rsplit("/api/status", 1)[0] if "/api/status" in api_url else api_url.rsplit("/status", 1)[0]

    @property
    def health_url(self) -> str:
        return self._health_url

    async def _async_update_data(self) -> dict[str, Any]:
        """Holt den aktuellen LLM-Status von der API."""
        logger.debug("Aktualisiere Status von %s", self.api_url)
        try:
            async with async_get_clientsession(self.hass).get(self.api_url, timeout=10) as resp:
                data = await resp.json()
        except Exception as exc:
            raise UpdateFailed(f"Fehler beim Abrufen des LLM-Status: {exc}") from exc
        await self.update_status(data)
        return data

    async def update_status(self, data: dict[str, Any]) -> None:
        """Aktualisiert gespeicherte Werte."""
        self.data = data

    async def async_call_service(self, service: str) -> dict[str, Any]:
        """Führt einen Start-/Stop-Befehl über die API aus."""
        action = SERVICE_ACTIONS.get(service, service)
        url = f"{self._api_prefix}/api/{action}"
        logger.info("%s auf %s", service, url)
        async with async_get_clientsession(self.hass).post(url, timeout=10) as resp:
            resp.raise_for_status()
            data = await resp.json()
        await self.update_status(data)
        self.async_request_refresh()
        return data

    def _process_attrs(self, data: dict[str, Any]) -> dict[str, Any]:
        """Zubereitung der Sensorenattribute."""
        process = data.get("process") or {}
        health = data.get("health") or {}
        attrs = {
            ATTR_NAME: data.get(ATTR_NAME, DOMAIN),
            ATTR_MANAGED_BY: DOMAIN,
            ATTR_HEALTH_URL: self.health_url,
        }
        if process:
            attrs[ATTR_IS_RUNNING] = True
            attrs[ATTR_PID] = process.get("pid")
            attrs[ATTR_PROCESS_CMDLINE] = process.get("cmdline")
            attrs[ATTR_PROCESS_CPU] = process.get("cpu_percent")
            attrs[ATTR_MEMORY_MB] = round(process.get("memory_mb", 0), 2)
        else:
            attrs[ATTR_IS_RUNNING] = False
            attrs[ATTR_PID] = None
            attrs[ATTR_PROCESS_CMDLINE] = None
            attrs[ATTR_PROCESS_CPU] = None
            attrs[ATTR_MEMORY_MB] = None
        attrs[ATTR_PORT] = data.get("port")
        if health:
            attrs[ATTR_HEALTH_OK] = health.get("status") == "ok"
            attrs[ATTR_HEALTH_ERROR] = health.get("error")
        return attrs

    def get_status_attrs(self) -> dict[str, Any]:
        """Aktuelle Sensorenattribute."""
        data = self.data or {}
        return self._process_attrs(data)

    def is_running(self) -> bool:
        data = self.data or {}
        return bool(data.get("process"))

    def current_pid(self) -> int | None:
        data = self.data or {}
        return (data.get("process") or {}).get("pid")

    def current_model(self) -> str | None:
        data = self.data or {}
        return data.get("name") or DOMAIN

    @property
    def available(self) -> bool:
        return self.last_update_success
