"""Config Flow für Local LLM Status."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return LLMOptionsFlowHandler(config_entry)

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


class LLMOptionsFlowHandler(config_entries.OptionsFlow):
    """Behandelt die Optionen für Local LLM Status."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialisierung."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage die Optionen."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            "scan_interval", self.config_entry.data.get("scan_interval", 60)
        )

        options_schema = vol.Schema(
            {
                vol.Required("scan_interval", default=current_interval): vol.All(vol.Coerce(int), vol.Range(min=5)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
