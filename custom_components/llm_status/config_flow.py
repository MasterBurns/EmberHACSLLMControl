"""Config Flow für Local LLM Status."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

USER_FORM_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Local LLM"): str,
        vol.Required("url", default="http://127.0.0.1:8080/api/status"): str,
        vol.Optional("model"): str,
        vol.Optional("version"): str,
        vol.Optional("scan_interval", default=60): vol.All(vol.Coerce(int), vol.Range(min=10)),
    }
)

logger = logging.getLogger(__name__)


class LLMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Leitet den Benutzer durch die Einrichtung von Local LLM Status."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return await self._validate_and_create(user_input)
        return self.async_show_form(step_id="user", data_schema=USER_FORM_SCHEMA)

    async def _validate_and_create(self, user_input: dict[str, Any]) -> FlowResult:
        url = user_input.get("url")
        if not await self._check_url(url):
            return self.async_show_form(
                step_id="user",
                data_schema=USER_FORM_SCHEMA,
                errors={"base": "cannot_connect"},
            )
        return self.async_create_entry(
            title=user_input.get("name", DOMAIN),
            data={
                "url": url,
                "model": user_input.get("model"),
                "version": user_input.get("version"),
                "scan_interval": user_input.get("scan_interval"),
            },
        )

    async def _check_url(self, url: str) -> bool:
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=10) as resp:
                logger.info("Antwort von %s: %s", url, resp.status)
                try:
                    data = await resp.json()
                    logger.info("JSON erhalten: %s", data)
                except Exception:
                    text = await resp.text()
                    logger.warning("Kein JSON von %s: %s", url, text[:200])
                    raise
                return resp.status == 200
        except Exception as exc:
            logger.error("URL-Prüfung fehlgeschlagen für %s: %s", url, exc)
            return False
