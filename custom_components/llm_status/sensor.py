"""Sensoren für den lokalen LLM-Status."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform, entity_registry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import llm_status
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
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    SERVICE_START,
    SERVICE_STOP,
)
from .coordinator import LLMCoordinator

logger = logging.getLogger(__name__)


@dataclass
class LLMStatusSensorDescription(SensorEntityDescription):
    icon: str | None = None
    value_key: str | None = None


SENSORS: tuple[LLMStatusSensorDescription, ...] = (
    LLMStatusSensorDescription(
        key="llm_running",
        name="Status",
        icon="mdi:robot",
        unit_of_measurement="bool",
        device_class=None,
    ),
    LLMStatusSensorDescription(
        key="llm_pid",
        name="Prozess-ID",
        icon="mdi:alpha-p-circle",
        device_class=None,
    ),
    LLMStatusSensorDescription(
        key="llm_cpu",
        name="CPU-Auslastung",
        icon="mdi:cpu-32",
        unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    LLMStatusSensorDescription(
        key="llm_memory_mb",
        name="Arbeitsspeicher",
        icon="mdi:memory",
        unit_of_measurement="MB",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    LLMStatusSensorDescription(
        key="llm_health",
        name="Gesundheitsstatus",
        icon="mdi:heart-pulse",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Richte Sensoren basierend auf dem Konfigurations-Eintrag ein."""
    coordinator: LLMCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LLMStatusSensor(coordinator, config_entry.entry_id, description)
        for description in SENSORS
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START,
        {},
        "async_start",
    )
    platform.async_register_entity_service(
        SERVICE_STOP,
        {},
        "async_stop",
    )


class LLMStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor für den lokalen LLM-Status."""

    entity_description: LLMStatusSensorDescription

    def __init__(
        self,
        coordinator: LLMCoordinator,
        entry_id: str,
        description: LLMStatusSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._entry_id = entry_id
        self.entity_description = description

        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_should_poll = False

    @property
    def available(self) -> bool:
        return self._coordinator.available and super().available

    @property
    def native_value(self) -> Any:
        attrs = self._coordinator.get_status_attrs()
        key = self.entity_description.key
        if key == "llm_running":
            return attrs.get(ATTR_IS_RUNNING)
        if key == "llm_pid":
            return attrs.get(ATTR_PID)
        if key == "llm_cpu":
            return attrs.get(ATTR_PROCESS_CPU)
        if key == "llm_memory_mb":
            return attrs.get(ATTR_MEMORY_MB)
        if key == "llm_health":
            return "healthy" if attrs.get(ATTR_HEALTH_OK) else "error"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self._coordinator.get_status_attrs()
        if self.entity_description.key == "llm_running":
            return attrs
        return {
            ATTR_MANAGED_BY: DOMAIN,
            ATTR_HEALTH_URL: attrs.get(ATTR_HEALTH_URL),
        }

    async def async_start(self) -> None:
        await self._coordinator.async_call_service(SERVICE_START)
        await self._coordinator.async_request_refresh()

    async def async_stop(self) -> None:
        await self._coordinator.async_call_service(SERVICE_STOP)
        await self._coordinator.async_request_refresh()
