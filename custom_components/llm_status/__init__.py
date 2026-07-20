"""Local LLM Status integration für Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, HomeAssistantError
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, PLATFORMS, SERVICE_START, SERVICE_STOP, SERVICE_SHUTDOWN
from .coordinator import LLMCoordinator

logger = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Richte die Domain und Services ein."""

    def find_coordinator() -> LLMCoordinator:
        """Finde den Coordinator des ersten llm_status Config-Entries."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("Kein Local LLM Status Eintrag konfiguriert.")
        return hass.data[DOMAIN].get(entries[0].entry_id)

    async def service_start(call) -> None:
        """Startet den konfigurierten LLM-Prozess."""
        coordinator = find_coordinator()
        await coordinator.async_call_service(SERVICE_START)

    async def service_stop(call) -> None:
        """Stoppt den laufenden LLM-Prozess."""
        coordinator = find_coordinator()
        await coordinator.async_call_service(SERVICE_STOP)

    async def service_shutdown(call) -> None:
        """Fährt den PC herunter."""
        coordinator = find_coordinator()
        await coordinator.async_call_service(SERVICE_SHUTDOWN)

    for key, handler in {
        SERVICE_START: service_start,
        SERVICE_STOP: service_stop,
        SERVICE_SHUTDOWN: service_shutdown,
    }.items():
        hass.services.async_register(DOMAIN, key, handler)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stellt das Config-Entry ein."""
    url = entry.data.get("url")
    if not url:
        raise ValueError("Fehlende URL im Konfigurations-Eintrag.")

    scan_interval = entry.options.get("scan_interval", entry.data.get("scan_interval", 60))

    coordinator = LLMCoordinator(
        hass,
        url,
        entry.title,
        scan_interval,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt das Config-Entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Läd das Config-Entry neu, wenn Optionen geändert wurden."""
    await hass.config_entries.async_reload(entry.entry_id)
