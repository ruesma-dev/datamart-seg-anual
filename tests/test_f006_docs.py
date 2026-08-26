# tests/test_f006_docs.py
"""
Los tres documentos que F-006 tiene que dejar escritos (T28, T35, T36).

Un documento no se «verifica leyéndolo»: se verifica igual que el código, con
una guarda que falle cuando alguien lo borre o lo deje a medias. Esta feature ya
tiene cinco rechazos por copias que sobrevivieron en el campo de al lado, así
que aquí no se comprueba solo que la frase esté: **se comprueba contra la fuente
que gobierna** siempre que exista una.

- **T28** · `docs/CONVENTIONS.md` exige actualizar la ficha del diccionario en
  el mismo trabajo que el objeto. Los comandos que la regla cite tienen que
  existir de verdad en `main.py`.
- **T35** · `docs/runbook_postgres_azure.md` documenta el firewall: la regla
  única del puesto y la IP de salida del entorno del MCP. Ningún comando de
  firewall del runbook puede usar `--rule-name`, que **no existe** en la CLI y
  ya costó media hora el 2026-08-19.
- **T36** · `docs/ARCHITECTURE.md` describe la capa semántica, y **las tablas
  del contrato se derivan del DDL**, no se enumeran a mano: el día que el
  contrato gane una tabla, este test lo dice.

Las comparaciones de prosa pasan por `tests._texto.contiene`: el Markdown está
ajustado a 79 columnas y una frase partida en dos líneas no la encuentra un
`in` a pelo (pasadas 8, 10, 13 y 15 de esta feature).
"""

from __future__ import annotations

import pathlib
import re

import pytest

from tests._texto import contiene

RAIZ = pathlib.Path(__file__).resolve().parents[1]

CONVENCIONES = RAIZ / "docs" / "CONVENTIONS.md"
RUNBOOK = RAIZ / "docs" / "runbook_postgres_azure.md"
ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"

MAIN = RAIZ / "main.py"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DDL_CONTRATO = (
    RAIZ
    / "etl_sigrid"
    / "infrastructure"
    / "postgres"
    / "sql"
    / "ddl"
    / "01_diccionario.sql"
)
STEP_PUBLICAR = (
    RAIZ / "etl_sigrid" / "application" / "steps" / "publicar_diccionario_step.py"
)


def _texto(ruta: pathlib.Path) -> str:
    return ruta.read_text(encoding="utf-8")


#: Un encabezado Markdown de verdad: almohadillas y **un espacio**. Un
#: `# 1) La IP de ahora mismo` dentro de un bloque ```bash no lo es, y tomarlo
#: por encabezado parte la sección justo antes de lo que se quiere comprobar.
_ENCABEZADO = re.compile(r"^(#{1,6})\s")


def _encabezados(texto: str):
    """`(nº de línea, nivel, línea)` de cada encabezado, **fuera** de los fences."""
    dentro_de_codigo = False
    for numero, linea in enumerate(texto.splitlines()):
        if linea.lstrip().startswith("```"):
            dentro_de_codigo = not dentro_de_codigo
            continue
        if dentro_de_codigo:
            continue
        marca = _ENCABEZADO.match(linea)
        if marca:
            yield numero, len(marca.group(1)), linea


def _seccion(texto: str, titulo: str) -> str:
    """El bloque que arranca en el encabezado que contiene `titulo`.

    Termina en el siguiente encabezado del MISMO nivel o de uno superior, para
    que una aserción sobre una sección no se cuele por lo que dice otra.
    """
    lineas = texto.splitlines()
    cabeceras = list(_encabezados(texto))
    arranque = next(((n, nivel) for n, nivel, l in cabeceras if titulo in l), None)
    if arranque is None:
        return ""
    inicio, nivel = arranque
    for numero, otro_nivel, _ in cabeceras:
        if numero > inicio and otro_nivel <= nivel:
            return "\n".join(lineas[inicio:numero])
    return "\n".join(lineas[inicio:])


# ---------------------------------------------------------------------------
# T28 · la regla vive donde la busca quien escribe SQL nuevo
# ---------------------------------------------------------------------------


def test_f006_t28_convenciones_exigen_la_ficha_en_el_mismo_trabajo() -> None:
    """La regla existe, y con sus tres piezas.

    Que la regla esté en `CLAUDE.md` y en la puerta de `init.sh` no basta: quien
    añade una vista SQL abre `docs/CONVENTIONS.md`, que es el documento
    normativo contra el que valida el reviewer.
    """
    texto = _texto(CONVENCIONES)
    assert contiene(texto, "config/diccionario"), (
        "las convenciones no nombran el directorio del diccionario semántico"
    )
    faltan = [
        pieza
        for pieza in (
            "en el mismo trabajo",  # cuándo
            "pendiente",  # la salida honesta si no se puede hacer ahora
        )
        if not contiene(texto, pieza)
    ]
    assert not faltan, f"la regla del diccionario no dice: {faltan}"


def test_f006_t28_convenciones_citan_comandos_que_existen() -> None:
    """Ningún `python main.py <cmd>` de las convenciones puede ser inventado.

    Derivado de `main.py`: los comandos se leen de los `@cli.command("…")`, no
    de una lista escrita a mano que envejezca en silencio.
    """
    registrados = set(re.findall(r'@cli\.command\(\s*"([a-z0-9-]+)"', _texto(MAIN)))
    assert len(registrados) >= 10, (
        f"solo se han derivado {len(registrados)} comandos de main.py: revisar el criterio"
    )
    citados = set(re.findall(r"python main\.py ([a-z0-9-]+)", _texto(CONVENCIONES)))
    assert citados, "las convenciones no citan ni un comando del diccionario"
    inventados = sorted(citados - registrados)
    assert not inventados, f"comandos citados que no existen en main.py: {inventados}"


# ---------------------------------------------------------------------------
# T35 · firewall (R35–R37)
# ---------------------------------------------------------------------------


def test_f006_t35_firewall_la_regla_del_puesto_es_unica_y_se_reescribe() -> None:
    """D11: la IP del puesto rota por CGNAT y perseguirla con reglas nuevas no sirve."""
    texto = _texto(RUNBOOK)
    faltan = [
        pieza
        for pieza in (
            "datamart-puesto-pgris",  # el nombre exacto, sin fecha
            "se reescribe",  # qué se hace con ella
            "no se crean reglas nuevas",  # qué NO se hace
            "CGNAT",  # por qué rota
        )
        if not contiene(texto, pieza)
    ]
    assert not faltan, f"el runbook no fija la regla única del puesto: {faltan}"


def test_f006_t35_firewall_el_entorno_del_mcp_documentado() -> None:
    """R35–R37: IP de salida estática, sin VNet, sobre un recurso ajeno."""
    texto = _texto(RUNBOOK)
    faltan = [
        pieza
        for pieza in (
            "properties.staticIp",  # de dónde sale la IP
            "sin integración de red virtual",  # la decisión que la hace estática
            "rg-albaranes-dev",  # el recurso es de otro proyecto
            "cualquier recurso de Azure",  # la regla de la que NO se depende
        )
        if not contiene(texto, pieza)
    ]
    assert not faltan, f"el runbook no documenta el firewall del MCP: {faltan}"


def test_f006_t35_firewall_el_servidor_compartido_esta_advertido() -> None:
    """`psql-albaranes-rs9k2` lo comparten `albaranes` y `partes` en producción."""
    seccion = _seccion(_texto(RUNBOOK), "Firewall")
    assert seccion, "no hay sección de firewall en el runbook"
    faltan = [
        pieza
        for pieza in ("albaranes", "partes", "no se tocan las ajenas")
        if not contiene(seccion, pieza)
    ]
    assert not faltan, (
        f"la sección de firewall no advierte del servidor compartido: {faltan}"
    )


def test_f006_t35_firewall_ningun_comando_usa_rule_name() -> None:
    """El parámetro que no existe, derivado del propio texto del runbook.

    `--rule-name` devuelve «unrecognized arguments»: en `create`, `update` y
    `delete` el servidor va en `--server-name`/`-s` y la regla en `--name`/`-n`.
    """
    lineas = [
        (numero, linea)
        for numero, linea in enumerate(_texto(RUNBOOK).splitlines(), start=1)
        if re.search(r"firewall-rule (create|update|delete)", linea)
    ]
    assert len(lineas) >= 2, (
        f"solo {len(lineas)} comandos de firewall en el runbook: el barrido no ve nada"
    )
    malos = [
        f"{RUNBOOK.name}:{numero}"
        for numero, linea in lineas
        if "--rule-name" in linea or not re.search(r"--server-name|\s-s\s", linea)
    ]
    assert not malos, f"comandos de firewall que no ejecutarían: {malos}"


def test_f006_t35_firewall_enlaza_infra_readme_en_vez_de_copiarlo() -> None:
    """Los nombres de parámetro se enlazan, no se duplican (design §12)."""
    texto = _texto(RUNBOOK)
    assert contiene(texto, "infra/README.md"), (
        "el runbook no enlaza `infra/README.md`, donde viven los parámetros"
    )
    assert (RAIZ / "infra" / "README.md").exists(), "el fichero enlazado no existe"


# ---------------------------------------------------------------------------
# T36 · la capa semántica en la arquitectura
# ---------------------------------------------------------------------------

TITULO_SEMANTICA = "El datamart se explica solo"


def test_f006_t36_arquitectura_describe_la_capa_semantica() -> None:
    """Fuente, paso, contrato y consumidor: las cuatro piezas."""
    seccion = _seccion(_texto(ARQUITECTURA), TITULO_SEMANTICA)
    assert seccion, f"no hay sección «{TITULO_SEMANTICA}» en docs/ARCHITECTURE.md"
    faltan = [
        pieza
        for pieza in (
            "config/diccionario/",  # la fuente
            "publicar_diccionario",  # el paso
            "run-all",  # dónde corre
            "mcp-bbdd",  # quién lo consume
            "mcp_sigrid_dm_ro",  # con qué rol
        )
        if not contiene(seccion, pieza)
    ]
    assert not faltan, f"la sección de la capa semántica no dice: {faltan}"


def test_f006_t36_arquitectura_nombra_el_contrato_derivado_del_ddl() -> None:
    """Las tablas del contrato se leen del DDL, no de una lista a mano.

    Si mañana el contrato gana una quinta tabla y nadie toca la arquitectura,
    este test lo dice. Es la lección de la 17ª pasada: una tabla de estado
    copiada sin contrastar miente en cuanto el árbol se mueve.
    """
    ddl = _texto(DDL_CONTRATO)
    objetos = set(
        re.findall(r"CREATE TABLE IF NOT EXISTS _meta\.(\w+)", ddl)
    ) | set(re.findall(r"CREATE OR REPLACE VIEW _meta\.(\w+)", ddl))
    assert len(objetos) == 5, (
        f"el contrato de `_meta` ya no son cuatro tablas y una vista, son {sorted(objetos)}"
    )
    seccion = _seccion(_texto(ARQUITECTURA), TITULO_SEMANTICA)
    faltan = sorted(o for o in objetos if f"_meta.{o}" not in seccion)
    assert not faltan, f"la arquitectura no nombra objetos del contrato: {faltan}"


def test_f006_t36_arquitectura_nombra_el_paso_como_lo_llama_el_codigo() -> None:
    """El nombre del paso sale de la clase, no de la memoria de quien escribe."""
    nombre = re.search(
        r"def name\(self\) -> str:\s*\n\s*return \"([a-z_]+)\"", _texto(STEP_PUBLICAR)
    )
    assert nombre, "no se ha podido derivar el nombre del paso de su clase"
    seccion = _seccion(_texto(ARQUITECTURA), TITULO_SEMANTICA)
    assert nombre.group(1) in seccion, (
        f"la arquitectura no llama al paso `{nombre.group(1)}`, que es como se llama"
    )
    assert "PublicarDiccionarioStep(" in _texto(MAIN), (
        "el paso ya no se compone en main.py: la arquitectura estaría mintiendo"
    )


def test_f006_t36_arquitectura_enlaza_azure_apps_sin_duplicarlo() -> None:
    """`CLAUDE.md` lo manda: el documento del ecosistema se enlaza, no se copia."""
    seccion = _seccion(_texto(ARQUITECTURA), TITULO_SEMANTICA)
    assert contiene(seccion, "azure-apps/datamart_seg_anual.md"), (
        "la sección no enlaza el documento del ecosistema"
    )


@pytest.mark.parametrize("ruta", [CONVENCIONES, RUNBOOK, ARQUITECTURA])
def test_f006_docs_control_los_documentos_existen(ruta: pathlib.Path) -> None:
    """Control: sin esto, un `read_text` fallando se leería como otra cosa."""
    assert ruta.exists(), f"falta {ruta}"
