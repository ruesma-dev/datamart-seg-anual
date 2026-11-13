# tests/test_f070_modelo_y_esfuerzo.py
"""F-070 · R14–R21: modelo `claude-opus-5-5` y esfuerzo por rol y carril.

Los agentes y `leader.md` son `arnes_puro`: llegan sin preguntar. El
`.claude/settings.json` es `adaptado`: un proyecto que conserve el suyo ve un
único rojo con lo que aceptar, y sus dependientes se saltan (patrón F-059 R34).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
AGENTES = RAIZ / ".claude" / "agents"
LEADER = AGENTES / "leader.md"
SETTINGS = RAIZ / ".claude" / "settings.json"

MODELO = "claude-opus-5-5"
ALIAS = ("inherit", "opus", "sonnet", "haiku", "fable")
# El esfuerzo del frontmatter es el del carril `estandar` (R15).
ESFUERZO_POR_AGENTE = {
    "leader": "high",
    "spec-author": "high",
    "implementer": "medium",
    "reviewer": "high",
    "qa-e2e": "medium",
}
CARRILES = ("express", "documental", "estandar", "critico")
# R16: rol → esfuerzo por carril; «—» es que el rol no actúa en ese carril.
TABLA_ESPERADA = {
    "líder (sesión)": ("high", "high", "high", "high"),
    "spec-author": ("—", "high", "high", "high"),
    "implementer": ("low", "low", "medium", "high"),
    "reviewer principal": ("medium", "medium", "high", "xhigh"),
    "reviewer de evidencias": ("—", "—", "medium", "medium"),
    "qa-e2e": ("—", "—", "medium", "medium"),
}


def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _plano(texto: str) -> str:
    return " ".join(texto.split())


def _frontmatter(ruta: Path) -> dict[str, str]:
    bloque = _crudo(ruta).split("---", 2)[1]
    campos = {}
    for linea in bloque.strip().splitlines():
        clave, _, valor = linea.partition(":")
        campos[clave.strip()] = valor.strip()
    return campos


def _seccion(texto: str, titulo: str) -> str:
    inicio = texto.index(titulo)
    fin = texto.find("\n## ", inicio + len(titulo))
    return texto[inicio:] if fin == -1 else texto[inicio:fin]


def _seccion_modelo() -> str:
    return _seccion(_crudo(LEADER), "## Modelo y esfuerzo")


def _tabla_modelo() -> dict[str, list[str]]:
    filas = {}
    for linea in _seccion_modelo().splitlines():
        if not linea.startswith("|") or set(linea) <= set("|-: "):
            continue
        celdas = [c.strip().replace("`", "") for c in linea.strip().strip("|").split("|")]
        filas[celdas[0]] = celdas[1:]
    return filas


# --- R14–R15: frontmatter de los cinco agentes ------------------------------------


def test_f070_r14_los_cinco_agentes_declaran_el_id_completo() -> None:
    agentes = sorted(p.stem for p in AGENTES.glob("*.md"))

    assert agentes == sorted(ESFUERZO_POR_AGENTE)
    for nombre in agentes:
        modelo = _frontmatter(AGENTES / f"{nombre}.md").get("model")
        assert modelo == MODELO, (nombre, modelo)
        assert modelo not in ALIAS


@pytest.mark.parametrize("agente,esfuerzo", sorted(ESFUERZO_POR_AGENTE.items()))
def test_f070_r15_el_frontmatter_lleva_el_esfuerzo_de_estandar(agente: str, esfuerzo: str) -> None:
    assert _frontmatter(AGENTES / f"{agente}.md").get("effort") == esfuerzo


# --- R16–R18 y R20: la tabla «Modelo y esfuerzo» de leader.md ----------------------


def test_f070_r16_la_tabla_rol_por_carril_con_su_motivo() -> None:
    tabla = _tabla_modelo()
    cabecera = tabla.pop("Rol")

    assert cabecera[:4] == list(CARRILES) and cabecera[4] == "Motivo"
    assert sorted(tabla) == sorted(TABLA_ESPERADA)
    for rol, esperado in TABLA_ESPERADA.items():
        assert tuple(tabla[rol][:4]) == esperado, rol
        assert len(tabla[rol][4]) > 15, f"la fila {rol} no trae motivo"


def test_f070_r16_los_frontmatter_coinciden_con_la_columna_estandar() -> None:
    tabla = _tabla_modelo()
    columna = CARRILES.index("estandar")

    assert tabla["líder (sesión)"][columna] == ESFUERZO_POR_AGENTE["leader"]
    for agente in ("spec-author", "implementer", "qa-e2e"):
        assert tabla[agente][columna] == ESFUERZO_POR_AGENTE[agente], agente
    assert tabla["reviewer principal"][columna] == ESFUERZO_POR_AGENTE["reviewer"]


def test_f070_r17_el_lider_pasa_effort_y_nunca_model_ni_fork() -> None:
    seccion = _plano(_seccion_modelo())

    assert "parámetro `effort` de la herramienta Agent" in seccion
    assert "sin editar ningún fichero" in seccion
    assert "**nunca** el parámetro `model`" in seccion and "solo admite alias" in seccion
    assert "**nunca** como `fork`" in seccion and "ignora `effort`" in seccion
    assert "v2.1.292" in seccion


def test_f070_r18_nadie_usa_max() -> None:
    for ruta in AGENTES.glob("*.md"):
        assert _frontmatter(ruta).get("effort") != "max", ruta.name
    for rol, celdas in _tabla_modelo().items():
        assert "max" not in celdas[:4], rol
    assert json.loads(_crudo(SETTINGS)).get("effortLevel") != "max"


def test_f070_r20_el_lider_avisa_de_la_variable_de_entorno() -> None:
    seccion = _plano(_seccion_modelo())

    assert "`CLAUDE_CODE_EFFORT_LEVEL`" in seccion
    assert "pisa el frontmatter y el parámetro" in seccion


# --- R21: cada agente dice su esfuerzo en una línea ----------------------------------


@pytest.mark.parametrize("agente", sorted(a for a in ESFUERZO_POR_AGENTE if a != "leader"))
def test_f070_r21_cada_subagente_dice_su_esfuerzo(agente: str) -> None:
    lineas = [li for li in _crudo(AGENTES / f"{agente}.md").splitlines()
              if li.startswith("**Esfuerzo por defecto:")]

    assert len(lineas) == 1, agente
    assert f"`{ESFUERZO_POR_AGENTE[agente]}`" in lineas[0]
    assert "el líder lo sube o lo baja al lanzarte" in lineas[0]
    assert "«Modelo y esfuerzo» de `leader.md`" in lineas[0]


def test_f070_r21_el_lider_dice_el_esfuerzo_de_su_sesion() -> None:
    lineas = [li for li in _crudo(LEADER).splitlines() if li.startswith("**Esfuerzo por defecto:")]

    assert len(lineas) == 1
    assert "`high`" in lineas[0] and "`effortLevel`" in lineas[0]


# --- R19–R20: .claude/settings.json (adaptado) ---------------------------------------

_INSTRUCCION_SETTINGS = (
    ".claude/settings.json no trae lo de F-070 (modelo y esfuerzo de la sesión): al "
    "actualizar el arnés, acepta las claves `model` y `effortLevel` del diff de "
    ".claude/settings.json"
)


def _motivo_settings_viejo(texto: str) -> str | None:
    """El rojo de R30 si este settings.json es de antes de F-070; o None."""
    try:
        datos = json.loads(texto)
    except ValueError:
        return _INSTRUCCION_SETTINGS
    if not isinstance(datos, dict):
        return _INSTRUCCION_SETTINGS
    nuevo = "model" in datos and "effortLevel" in datos
    return None if nuevo else _INSTRUCCION_SETTINGS


_MOTIVO = _motivo_settings_viejo(_crudo(SETTINGS))
settings_de_f070 = pytest.mark.skipif(_MOTIVO is not None, reason=_MOTIVO or "")


def test_f070_r30_el_settings_instalado_trae_model_y_effortlevel() -> None:
    motivo = _motivo_settings_viejo(_crudo(SETTINGS))

    assert motivo is None, motivo


@settings_de_f070
def test_f070_r19_settings_fija_modelo_y_esfuerzo_de_la_sesion() -> None:
    datos = json.loads(_crudo(SETTINGS))

    assert datos["model"] == MODELO
    assert datos["effortLevel"] == "high"
    assert "effortLevel" in datos["$adaptar"]
    assert "CLAUDE_CODE_EFFORT_LEVEL" in datos["$adaptar"]


@settings_de_f070
def test_f070_r20_settings_no_define_la_variable_de_esfuerzo() -> None:
    datos = json.loads(_crudo(SETTINGS))

    assert "CLAUDE_CODE_EFFORT_LEVEL" not in datos.get("env", {})


@settings_de_f070
def test_f070_r30_un_settings_viejo_da_el_motivo_con_instrucciones() -> None:
    datos = json.loads(_crudo(SETTINGS))
    sin_model = {k: v for k, v in datos.items() if k != "model"}
    sin_esfuerzo = {k: v for k, v in datos.items() if k != "effortLevel"}

    for viejo in (json.dumps(sin_model), json.dumps(sin_esfuerzo), "", "[]"):
        assert _motivo_settings_viejo(viejo) == _INSTRUCCION_SETTINGS
    assert "acepta las claves `model` y `effortLevel` del diff de .claude/settings.json" in (
        _INSTRUCCION_SETTINGS)


def test_f070_r30_los_dependientes_de_settings_llevan_la_marca_y_el_rojo_no() -> None:
    dependientes = [f for n, f in globals().items()
                    if n.startswith(("test_f070_r19_", "test_f070_r20_settings_",
                                     "test_f070_r30_un_settings_")) and callable(f)]

    assert len(dependientes) == 3
    for funcion in dependientes:
        assert settings_de_f070.mark in getattr(funcion, "pytestmark", []), funcion.__name__
    rojo = test_f070_r30_el_settings_instalado_trae_model_y_effortlevel
    assert settings_de_f070.mark not in getattr(rojo, "pytestmark", [])
