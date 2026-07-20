"""Konstanten für die lokale LLM-Status-Integration."""

from __future__ import annotations

DOMAIN = "llm_status"
MANUFACTURER = "HACSLLM"
PLATFORMS = ["sensor"]
DEFAULT_SCAN_INTERVAL = 60

SERVICE_START = "start_llm"
SERVICE_STOP = "stop_llm"
SERVICE_SHUTDOWN = "shutdown_pc"

SERVICE_ACTIONS = {
    SERVICE_START: "start",
    SERVICE_STOP: "stop",
    SERVICE_SHUTDOWN: "system_shutdown",
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

ATTR_ENCODE_TOTAL = "encode_total"
ATTR_DECODE_TOTAL = "decode_total"
ATTR_ENCODE_TPS = "encode_tps"
ATTR_DECODE_TPS = "decode_tps"

DESCRIPTION_MAP = {
    SERVICE_START: {
        "name": "LLM starten",
        "description": "Startet den konfigurierten lokalen LLM-Prozess.",
    },
    SERVICE_STOP: {
        "name": "LLM stoppen",
        "description": "Stoppt den laufenden lokalen LLM-Prozess.",
    },
    SERVICE_SHUTDOWN: {
        "name": "PC herunterfahren",
        "description": "Fährt den PC herunter, auf dem der LLM Server läuft.",
    },
}
