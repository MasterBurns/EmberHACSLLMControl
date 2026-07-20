#!/bin/bash

# 20 Sekunden warten (z. B. auf das Netzwerk)
sleep 20

# In das Server-Verzeichnis wechseln
cd /home/masterburns/Dokumente/HACSLLM/server

# Prüfen, ob die virtuelle Umgebung (.venv) bereits existiert
if [ ! -d ".venv" ]; then
    echo "Erstelle virtuelle Umgebung und installiere Abhängigkeiten..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

# Server starten
echo "Starte den LLM-Server..."
.venv/bin/python llm_manager_server.py
