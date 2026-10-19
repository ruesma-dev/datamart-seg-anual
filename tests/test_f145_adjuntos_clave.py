# tests/test_f145_adjuntos_clave.py
"""
F-145 · La ficha de los adjuntos dice cómo los abre hoy `mcp-bbdd` (su F-025).

Desde la F-025 de `mcp-bbdd` (desplegada y verificada, revisión `--0000021`,
imagen `r20261018-1730`), `abrir_adjunto` pide el fichero a `sigrid-api` por la
PAREJA de la fila del índice, `key: {"emp": empresa_repositorio, "cod":
cod_repositorio}`, sin `id_column` ni `id_value`; si no hay fichero con esa
pareja (400 `ValueError`) o la fila no trae empresa, lo pide UNA vez más con la
empresa 1 y avisa al modelo; el 409 de `sigrid-api` es `ORIGEN_AMBIGUO`, y el
código que rechazaba los `cod` repetidos desaparece.

Quien lee la ficha es una IA: si la ficha le dice `id_column: cod`, pedirá así el
fichero y pensará que un `cod` basta. Aquí se fija que ninguna ficha lo vuelve a
decir, que la nueva forma está escrita y que `empresa_repositorio` sigue siendo
ENTERA en el SQL: `mcp-bbdd` solo la usa si le llega como entero (contrato
nuevo), y renombrarla o cambiarle el tipo rompe `abrir_adjunto`.

Sin red ni BBDD.
"""

from __future__ import annotations

import re
import subprocess
from functools import cache
from pathlib import Path

import pytest
import yaml

from tests._texto import contiene, normalizado

RAIZ = Path(__file__).resolve().parents[1]
DICC = RAIZ / "config" / "diccionario"
GLOBAL = DICC / "00_global.yaml"
SQL_ADJUNTOS = (
    RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
    / "14_documento_adjuntos.sql"
)
DOMINIO = RAIZ / "etl_sigrid" / "domain" / "documento_adjuntos.py"
ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

VERSION_F145 = 57

#: Lo que ya no es verdad desde la F-025 de `mcp-bbdd`: la petición por
#: `id_column: cod` (en cualquiera de sus formas escritas) y el código de error
#: que rechazaba los `cod` con más de una empresa.
CADUCADO: tuple[re.Pattern[str], ...] = (
    re.compile(r"id_column`?\s*:?\s*`?\s*\"?cod\b"),
    re.compile(r"ADJUNTO_AMBIGUO"),
)


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_almohadillas(texto: str) -> str:
    """Las líneas de comentario YAML sin su `#`, para leer la prosa entera."""
    return "\n".join(re.sub(r"^\s*#", "", linea) for linea in texto.splitlines())


def caducados_en(texto: str) -> list[str]:
    """Los patrones caducados que aparecen en `texto`, ignorando el ajuste."""
    plano = normalizado(_sin_almohadillas(texto))
    return [p.pattern for p in CADUCADO if p.search(plano)]


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load(_texto(DICC / nombre))


def _adjuntos() -> dict:
    return _yaml("compras.yaml")["objetos"]["documento_adjuntos"]


def _columna(nombre: str) -> str:
    return _adjuntos()["columnas"][nombre]["significado"]


# ===========================================================================
# 1 · Nada vuelve a decir `id_column: cod` ni el código retirado
# ===========================================================================


@pytest.mark.parametrize("fichero", sorted(p.name for p in DICC.glob("*.yaml")))
def test_f145_ninguna_ficha_dice_lo_caducado(fichero: str) -> None:
    hallados = caducados_en(_texto(DICC / fichero))
    assert not hallados, (
        f"{fichero} aún dice {hallados}: desde la F-025 de `mcp-bbdd` el fichero se "
        "pide por la pareja (`empresa_repositorio`, `cod_repositorio`)"
    )


@pytest.mark.parametrize(
    "ruta", [SQL_ADJUNTOS, DOMINIO, ARQUITECTURA], ids=lambda r: r.name
)
def test_f145_ni_el_sql_ni_el_dominio_ni_la_arquitectura(ruta: Path) -> None:
    hallados = caducados_en(_texto(ruta))
    assert not hallados, f"{ruta.name} aún dice {hallados} (F-145)"


def test_f145_ni_azure_apps() -> None:
    if not AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    hallados = caducados_en(_texto(AZURE_APPS))
    assert not hallados, f"azure-apps/datamart_seg_anual.md aún dice {hallados} (F-145)"


@pytest.mark.parametrize(
    "texto",
    [
        "(`database: ruesma_rep`, `table: gra`, `id_column:\n      cod`, `id_value`",
        "en `documents/read` con `id_column: cod`. DATO",
        "`POST /api/documents/read` (`id_column` `cod`).",
        "# el 409 ya no es\n# ADJUNTO_AMBIGUO",
    ],
)
def test_f145_sabotaje_el_barrido_ve_las_formas_que_habia(texto: str) -> None:
    """Las cuatro formas en que estaba escrito, envueltas como estaban."""
    assert caducados_en(texto), f"el barrido no ve lo caducado en {texto!r}"


def test_f145_control_el_barrido_no_salta_con_lo_vigente() -> None:
    vigente = (
        '`key: {"emp": empresa_repositorio, "cod": cod_repositorio}`, sin '
        "`id_column` ni `id_value`; el 409 es `ORIGEN_AMBIGUO`; `id_column: ide`"
    )
    assert caducados_en(vigente) == []


# ===========================================================================
# 2 · La ficha dice cómo se abre hoy
# ===========================================================================


def test_f145_la_ficha_dice_la_pareja_el_respaldo_y_el_409() -> None:
    descripcion = _adjuntos()["descripcion"]
    for dato in (
        'key: {"emp": empresa_repositorio, "cod": cod_repositorio}',
        "sin `id_column` ni `id_value`",
        "F-025",
        "400",
        "`ValueError`",
        "empresa 1",
        "UNA vez",
        "puede no ser el original",
        "respaldo=empresa_defecto",
        "409",
        "`ORIGEN_AMBIGUO`",
        "`abrir_adjunto(adjunto_id)`",
        'filename_columns: ["cod"]',
        "blob_column: ima",
    ):
        assert contiene(descripcion, dato), f"la ficha no dice «{dato}» (F-145)"


def test_f145_la_columna_cod_repositorio_dice_la_pareja() -> None:
    significado = _columna("cod_repositorio")
    for dato in ("`empresa_repositorio`", "`key`", "pareja", "DATO PERSONAL"):
        assert contiene(significado, dato), f"`cod_repositorio` no dice «{dato}»"
    assert "id_value" not in significado, "ya no hay `id_value`: es la `key`"


def test_f145_la_columna_empresa_repositorio_dice_el_contrato() -> None:
    significado = _columna("empresa_repositorio")
    for dato in ("ENTERO", "`abrir_adjunto`", "`SIN_BINARIO`", "empresa 1", "nula"):
        assert contiene(significado, dato), f"`empresa_repositorio` no dice «{dato}»"


def test_f145_el_comment_de_la_tabla_dice_la_pareja() -> None:
    comment = _texto(SQL_ADJUNTOS).split("COMMENT ON TABLE compras.documento_adjuntos IS", 1)[1]
    assert "pareja (empresa_repositorio, cod_repositorio)" in comment, (
        "el COMMENT de la tabla aún dice que se pide solo con cod_repositorio (F-145)"
    )


# ===========================================================================
# 3 · `empresa_repositorio` es ENTERA en el SQL (contrato con `mcp-bbdd`)
# ===========================================================================


def _sin_comentarios_sql(texto: str) -> str:
    return re.sub(r"\s+", " ", "\n".join(
        re.sub(r"--.*$", "", linea) for linea in texto.splitlines()
    )).strip()


def problemas_empresa_entera(sql: str) -> list[str]:
    """Lo que en `sql` haría que `empresa_repositorio` no llegue ENTERA y tal cual.

    `raw.gra.emp` es entero (`int` en Sigrid, `INTEGER` en `raw`): mientras la
    columna salga de `g.emp` sin conversión ni función, y pase al SELECT final
    sin tocar, `mcp-bbdd` la recibe como entero. Cualquier `::`, `CAST`,
    función o renombrado lo rompe.
    """
    plano = _sin_comentarios_sql(sql)
    problemas: list[str] = []
    definiciones = re.findall(r"([^,()]*(?:\([^()]*\))?[^,()]*) AS empresa_repositorio\b", plano)
    definiciones = [d.strip() for d in definiciones]
    if definiciones != ["g.emp"]:
        problemas.append(f"`empresa_repositorio` sale de {definiciones}, no de `g.emp` tal cual")
    if re.search(r"\bg\.emp\s*::", plano) or re.search(r"CAST\s*\(\s*g\.emp\b", plano, re.I):
        problemas.append("`g.emp` lleva una conversión de tipo")
    usos = re.findall(r"b\.empresa_repositorio\b(\s*::\s*\w+)?", plano)
    if usos != [""]:
        problemas.append(f"el SELECT final no pasa `b.empresa_repositorio` tal cual: {usos}")
    if re.search(r"empresa_repositorio\s*::", plano):
        problemas.append("`empresa_repositorio` lleva una conversión de tipo")
    return problemas


def test_f145_empresa_repositorio_es_entera_en_el_sql() -> None:
    problemas = problemas_empresa_entera(_texto(SQL_ADJUNTOS))
    assert not problemas, (
        f"{problemas}: `mcp-bbdd` usa `empresa_repositorio` solo si llega como ENTERO; "
        "renombrarla o cambiarle el tipo rompe `abrir_adjunto` (SIN_BINARIO). "
        "Contrato en azure-apps/datamart_seg_anual.md: avisa a su dueño"
    )


@pytest.mark.parametrize(
    ("de", "a"),
    [
        ("g.emp AS empresa_repositorio", "g.emp::TEXT AS empresa_repositorio"),
        ("g.emp AS empresa_repositorio", "CAST(g.emp AS VARCHAR) AS empresa_repositorio"),
        ("g.emp AS empresa_repositorio", "NULLIF(BTRIM(g.emp::text), '') AS empresa_repositorio"),
        ("g.emp AS empresa_repositorio", "g.emp AS empresa"),
        ("b.empresa_repositorio,", "b.empresa_repositorio::TEXT,"),
        ("b.empresa_repositorio,", "b.empresa_repositorio::TEXT AS empresa_repositorio,"),
    ],
)
def test_f145_sabotaje_la_guarda_ve_cada_forma_de_romperlo(de: str, a: str) -> None:
    original = _sin_comentarios_sql(_texto(SQL_ADJUNTOS))
    assert de in original, f"el SQL ya no lleva «{de}»: rehacer el sabotaje"
    assert problemas_empresa_entera(original.replace(de, a, 1)), f"no ve «{a}»"


def test_f145_la_columna_de_raw_que_alimenta_la_empresa_se_ingiere() -> None:
    """Si `emp` se excluyera en la ingesta, el SQL no compilaría o llegaría nula."""
    from etl_sigrid.domain.documento_adjuntos import COLUMNAS_EXCLUIDAS_GRA

    assert "emp" not in COLUMNAS_EXCLUIDAS_GRA


# ===========================================================================
# 4 · azure-apps: H5 y el contrato del entero
# ===========================================================================


def test_f145_azure_apps_dice_la_pareja_y_el_contrato() -> None:
    if not AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = _texto(AZURE_APPS)
    h5 = texto[texto.index("- **H5.**"): texto.index("- **H6.**")]
    for dato in ('"emp": empresa_repositorio', '"cod": cod_repositorio', "empresa 1",
                 "respaldo=empresa_defecto", "`ORIGEN_AMBIGUO`", "F-025",
                 'filename_columns: ["cod"]'):
        assert contiene(h5, dato), f"H5 no dice «{dato}» (F-145)"
    for dato in ("`empresa_repositorio` es ENTERO", "`SIN_BINARIO`",
                 "rompe `abrir_adjunto`"):
        assert contiene(texto, dato), f"azure-apps no escribe el contrato «{dato}» (F-145)"


# ===========================================================================
# 5 · La versión del diccionario: 57, robusta al merge
# ===========================================================================


def _global_de_main() -> str | None:
    try:
        r = subprocess.run(
            ["git", "show", "main:config/diccionario/00_global.yaml"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def test_f145_version_la_siguiente_a_la_de_main() -> None:
    """Antes del merge, la de `main` + 1; después, `main` YA lleva la entrada de
    F-145 y basta con no bajar de ella (lección de F-141/F-144, resuelta así en
    la R31 de F-128)."""
    texto_main = _global_de_main()
    if texto_main is None:
        pytest.skip("sin git o sin rama main: no se puede comparar")
    version_main = int(yaml.safe_load(texto_main)["version"])
    actual = int(_yaml("00_global.yaml")["version"])
    if "(F-145, " in texto_main:
        assert actual >= version_main
    else:
        assert actual >= version_main + 1


def test_f145_historia_de_versiones() -> None:
    assert int(_yaml("00_global.yaml")["version"]) >= VERSION_F145
    assert f"# version {VERSION_F145} (F-145, " in _texto(GLOBAL)
