# tests/test_f015_protocolos.py
"""F-015 · Protocolos de los agentes y línea base sobre código real (R8, R9, R18).

Análisis textual, como hizo F-003 con los `.ps1`: lo que se verifica es que el
protocolo escrito EXIGE la evidencia, no que un agente concreto la haya dado.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
IMPLEMENTER = RAIZ / ".claude" / "agents" / "implementer.md"


def texto_de(ruta: Path) -> str:
    """Texto en minúsculas y con los espacios colapsados.

    Así el análisis textual no depende de dónde parta las líneas el Markdown.
    """
    return re.sub(r"\s+", " ", ruta.read_text(encoding="utf-8").lower())


# --- R8: fase RED con salida real -------------------------------------------


def test_f015_r8_implementer_exige_fase_red_con_salida_real() -> None:
    protocolo = texto_de(IMPLEMENTER)

    assert "fase red" in protocolo
    # Qué hay que demostrar: que el test fallaba ANTES de existir el código.
    assert "antes" in protocolo
    assert "fallaba" in protocolo or "falla" in protocolo
    # Y con qué se demuestra: la salida real pegada en el informe.
    assert "salida real" in protocolo
    assert "progress/impl_f-xxx.md" in protocolo
    # La defensa que justifica la regla, escrita para que nadie la relaje.
    assert "a posteriori" in protocolo


def test_f015_r8_la_fase_red_se_exige_para_los_requisitos_centrales() -> None:
    protocolo = texto_de(IMPLEMENTER)

    assert "requisitos centrales" in protocolo
    # Y se dice explícitamente qué NO vale como evidencia.
    assert "no vale" in protocolo


# --- R9: sección «Evidencias» con números reales ----------------------------


def test_f015_r9_implementer_exige_seccion_evidencias_con_numeros() -> None:
    protocolo = texto_de(IMPLEMENTER)

    assert "evidencias" in protocolo
    # Los cuatro números, comparables entre features.
    assert re.search(r"tests? ejecutados", protocolo)
    assert "cobertura de las líneas cambiadas" in protocolo
    assert "supervivientes" in protocolo
    assert "tiempo" in protocolo
    # Números reales, no impresiones.
    assert "debería funcionar" in protocolo or "numeros reales" in protocolo
