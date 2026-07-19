"""Konstanten für die lokale LLM-Status-Integration."""

from __future__ import annotations

DOMAIN = "llm_status"
MANUFACTURER = "HACSLLM"
PLATFORMS = ["sensor"]
DEFAULT_SCAN_INTERVAL = 60

SERVICE_START = "start_llm"
SERVICE_STOP = "stop_llm"

SERVICE_ACTIONS = {
    SERVICE_START: "start",
    SERVICE_STOP: "stop",
}

ATTR_NAME = "name"
ATTR_IS_RUNNING = "is_running"
ATTR_PID = "pid"
ATTR_PROCESS_CMDLINE = "process_cmdline"
ATTR_PROCESS_CPU = "process_cpu_percent"
ATTR_MEMORY_MB = "memory_mb"
ATTR_PORT = "port"
ATTR_HEALTH_OK = "health_ok"
ATTR_HEALTH_ERROR = "health_error"
ATTR_HEALTH_URL = "health_url"
ATTR_MANAGED_BY = "managed_by"

DESCRIPTION_MAP = {
    SERVICE_START: {
        "name": "LLM starten",
        "description": "Startet den konfigurierten lokalen LLM-Prozess.",
    },
    SERVICE_STOP: {
        "name": "LLM stoppen",
        "description": "Stoppt den laufenden lokalen LLM-Prozess.",
    },
}
