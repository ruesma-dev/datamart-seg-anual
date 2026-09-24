# tests/test_f107_contrapartidas_cuentas.py
"""
F-107 · Contrapartidas del recurso y catalogo de cuentas analiticas.

Pedido por Juan Romero el 2026-09-23: tras F-101 cuadra los precios de la ficha
contra los partes, pero para reproducir el asiento le faltan (1) la
CONTRAPARTIDA de la ficha del recurso --centro de coste y cuenta analitica que
descargan los partes contra la nomina-- y (2) el CATALOGO de cuentas analiticas
para traducir los identificadores (496869, 496923, 496935...).

Medido en solo lectura contra Sigrid el 2026-09-24 (detalle en
`progress/impl_F-107.md`): la contrapartida es del RECURSO (`res.cenconide`,
`res.caaconide`, informadas en 1.979 de 2.619 recursos), no del tipo de hora;
`caa` tiene 184.234 cuentas, todas `con.tip = 19`, y el codigo solo es unico
dentro de su empresa (14.063 codigos repetidos entre empresas, 0 dentro de una).

Ningun test toca red ni base de datos (convencion del proyecto): se fijan sobre
el TEXTO las decisiones; las cifras contra la base viva son las verificaciones
MANUALES de `progress/current.md`. Helpers copiados de
`tests/test_f102_obra_principal.py`, no importados, por la misma razon que alli.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

RUTA_PERSONAL_SETUP = DIR_SQL / "personal" / "00_setup.sql"
RUTA_RECURSOS = DIR_SQL / "personal" / "01_recursos.sql"
RUTA_CUENTAS = DIR_SQL / "maestro" / "06_cuentas_analiticas.sql"

VISTA = "maestro.cuentas_analiticas"

#: Las dos columnas que gana `personal.recursos`, al final y en este orden.
COLUMNAS_CONTRAPARTIDA = (
    "centro_coste_contrapartida_id",
    "cuenta_analitica_contrapartida_id",
)

#: Las de F-102, que siguen justo delante de las de F-107.
COLUMNAS_F102 = ("empresa_id", "nombre_empresa", "clave_recurso")

#: Lo que publica `maestro.cuentas_analiticas`, en orden.
COLUMNAS_CUENTAS = (
    "cuenta_analitica_id",
    "empresa_id",
    "codigo_cuenta",
    "descripcion_cuenta",
    "cuenta_padre_id",
    "codigo_cuenta_padre",
    "descripcion_cuenta_padre",
    "nivel",
    "centro_coste_id",
    "partida_presupuestaria_id",
    "fecha_baja",
    "es_activa",
)

#: Las tres cuentas del correo de Juan, traducidas en Sigrid el 2026-09-24.
CUENTAS_DEL_CORREO = (
    ("496869", "00000.CIMO02", "JEFE DE OBRA"),
    ("496923", "00000.CICO01", "COMBUSTIBLES-GASOIL"),
    ("496935", "00000.CICO13", "TELEFONO MOVIL"),
)

TOTAL_TABLAS = 70


# ---------------------------------------------------------------------------
# Helpers de texto
# ---------------------------------------------------------------------------


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto EJECUTABLE: sin las lineas `--` de comentario."""
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    """Una sola linea, espacios colapsados: para buscar expresiones SQL."""
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


def _troceado_en_profundidad_cero(texto: str, separador: str) -> list[str]:
    """Trocea por `separador`, ignorando lo que caiga dentro de parentesis."""
    piezas: list[str] = []
    actual: list[str] = []
    profundidad = 0
    i = 0
    while i < len(texto):
        caracter = texto[i]
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        if profundidad == 0 and texto.startswith(separador, i):
            piezas.append("".join(actual))
            actual = []
            i += len(separador)
            continue
        actual.append(caracter)
        i += 1
    piezas.append("".join(actual))
    return piezas


def _sentencia(ruta: Path, vista: str) -> str:
    """El `CREATE OR REPLACE VIEW <vista> AS ...` compacto, hasta su `;`."""
    compacto = _compacto(_sql(ruta))
    marca = f"CREATE OR REPLACE VIEW {vista} AS "
    assert marca in compacto, f"{ruta.name} no crea la vista {vista}"
    resto = compacto[compacto.index(marca) + len(marca):]
    return _troceado_en_profundidad_cero(resto, ";")[0]


def _columnas_en_orden(ruta: Path, vista: str) -> list[str]:
    """Lo que la vista EXPONE, en orden: el SELECT de profundidad cero."""
    cuerpo = " " + _sentencia(ruta, vista)
    seleccion = _troceado_en_profundidad_cero(cuerpo, " SELECT ")[1]
    seleccion = _troceado_en_profundidad_cero(seleccion, " FROM ")[0]
    nombres: list[str] = []
    for pieza in _troceado_en_profundidad_cero(seleccion, ","):
        pieza = pieza.strip()
        if not pieza:
            continue
        if " AS " in pieza:
            nombres.append(pieza.rsplit(" AS ", 1)[1].strip())
        else:
            nombres.append(pieza.rsplit(".", 1)[-1].strip())
    return nombres


def _normalizado(texto: str) -> str:
    """Minusculas y sin tildes: el diccionario se escribe sin ellas."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


@cache
def _yaml(fichero: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / fichero).read_text(encoding="utf-8"))


def _ficha(nombre: str) -> dict:
    esquema, objeto = nombre.split(".")
    objetos = _yaml(f"{esquema}.yaml")["objetos"]
    assert objeto in objetos, f"no hay ficha de {nombre}"
    return objetos[objeto]


def _texto(valor: object) -> str:
    """Todo el texto de una ficha o de un trozo de ella, aplanado."""
    if isinstance(valor, dict):
        return " ".join(_texto(v) for v in valor.values())
    if isinstance(valor, list):
        return " ".join(_texto(v) for v in valor)
    return "" if valor is None else str(valor)


def _relaciones(nombre: str) -> list[dict]:
    return _ficha(nombre).get("relaciones") or []


def _tablas() -> list[dict]:
    return yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))["tables"]


# ===========================================================================
# R1 · `personal.recursos` publica la contrapartida del RECURSO
# ===========================================================================


@pytest.mark.parametrize("columna", COLUMNAS_CONTRAPARTIDA)
def test_f107_r1_la_tabla_existente_gana_la_columna_sin_drop(columna: str) -> None:
    """La nocturna ya creo la tabla: `ADD COLUMN IF NOT EXISTS`, nunca `DROP`
    (se llevaria los GRANT)."""
    compacto = _compacto(_sql(RUTA_PERSONAL_SETUP))
    assert re.search(
        rf"ALTER TABLE personal\.recursos ADD COLUMN IF NOT EXISTS {columna} BIGINT;",
        compacto,
    ), f"personal.recursos gana {columna} BIGINT con ADD COLUMN IF NOT EXISTS (R1)"
    assert "DROP TABLE" not in compacto.upper()


def test_f107_r1_la_tabla_nueva_nace_con_las_dos_al_final() -> None:
    compacto = _compacto(_sql(RUTA_PERSONAL_SETUP))
    ddl = re.search(r"CREATE TABLE IF NOT EXISTS personal\.recursos \((.*?)\);", compacto)
    assert ddl, "falta el CREATE TABLE de personal.recursos"
    columnas = [c.strip().split(" ")[0] for c in _troceado_en_profundidad_cero(
        ddl.group(1), ",")]
    assert columnas[-5:] == list(COLUMNAS_F102 + COLUMNAS_CONTRAPARTIDA), (
        "en una base nueva nacen al final, detras de las de F-102 (R1)"
    )


def test_f107_r1_el_insert_publica_las_dos_al_final() -> None:
    compacto = _compacto(_sql(RUTA_RECURSOS))
    lista = re.search(r"INSERT INTO personal\.recursos \((.*?)\) SELECT", compacto)
    assert lista, "falta el INSERT de personal.recursos"
    columnas = [c.strip() for c in lista.group(1).split(",")]
    assert columnas[-5:] == list(COLUMNAS_F102 + COLUMNAS_CONTRAPARTIDA), "R1"


def test_f107_r1_salen_del_recurso_con_nullif_cero() -> None:
    """Sigrid guarda la ausencia como 0: NULLIF, como el resto del fichero."""
    compacto = _compacto(_sql(RUTA_RECURSOS))
    assert "NULLIF(r.cenconide, 0) AS centro_coste_contrapartida_id" in compacto, "R1"
    assert "NULLIF(r.caaconide, 0) AS cuenta_analitica_contrapartida_id" in compacto, "R1"


def test_f107_r1_no_se_une_nada_nuevo_y_no_se_pierden_filas() -> None:
    """Los dos ids son columnas de `raw.res`: ningun JOIN nuevo, ningun WHERE.
    Una fila por `raw.res`, como antes. El nombre del centro y de la cuenta
    se resuelven en `maestro`, por relacion, no aqui."""
    ejecutable = _compacto(_sql(RUTA_RECURSOS))
    for tabla in ("raw.caa", "raw.cen", "maestro.cuentas_analiticas",
                  "maestro.centros_coste"):
        assert tabla not in ejecutable, f"01_recursos.sql no une {tabla} (R1)"
    joins = re.findall(r"\b(?:LEFT JOIN LATERAL|LEFT JOIN|JOIN) (?:\( )?[\w.]+", ejecutable)
    assert len(joins) == 4, joins  # con, auxrestip, lateral emp, lateral auxemp


def test_f107_r1_la_ficha_documenta_las_dos_al_final() -> None:
    columnas = _ficha("personal.recursos")["columnas"]
    assert list(columnas)[-2:] == list(COLUMNAS_CONTRAPARTIDA), "R1"
    for columna in COLUMNAS_CONTRAPARTIDA:
        assert len(_texto(columnas[columna])) > 120, f"{columna} sin ficha util (R1)"


def test_f107_r1_la_ficha_dice_que_la_contrapartida_es_del_recurso() -> None:
    texto = _normalizado(_texto(_ficha("personal.recursos")))
    assert "contrapartida" in texto
    assert "del recurso" in texto and "no por tipo de hora" in texto, (
        "la ficha explica que la contrapartida es del RECURSO, no de reshor (R1)"
    )
    for cifra in ("1.979", "2.619"):
        assert cifra in texto, f"la ficha no da la cobertura medida «{cifra}» (R1)"


def test_f107_r1_la_ficha_de_tipos_de_hora_no_promete_contrapartida() -> None:
    """`reshor` no tiene contrapartida: su ficha lo dice y remite al recurso."""
    texto = _normalizado(_texto(_ficha("personal.recursos_tipos_hora")))
    assert "contrapartida" in texto and "personal.recursos" in texto, "R1"


@pytest.mark.parametrize(
    ("columna", "destino"),
    [
        ("centro_coste_contrapartida_id", "maestro.centros_coste.centro_coste_id"),
        ("cuenta_analitica_contrapartida_id",
         "maestro.cuentas_analiticas.cuenta_analitica_id"),
    ],
)
def test_f107_r1_las_contrapartidas_tienen_relacion(columna: str, destino: str) -> None:
    relaciones = [r for r in _relaciones("personal.recursos") if r["de"] == columna]
    assert relaciones, f"{columna} sin relacion declarada (R1, R4)"
    assert relaciones[0]["a"] == destino
    assert relaciones[0]["cardinalidad"] == "N:1"


# ===========================================================================
# R2 · se ingiere `caa` y `maestro.cuentas_analiticas` la publica sin filtrar
# ===========================================================================


def test_f107_r2_caa_se_ingiere_entera() -> None:
    entradas = [t for t in _tablas() if t["source_table"] == "caa"]
    assert len(entradas) == 1, "caa declarada una vez (R2)"
    caa = entradas[0]
    assert caa["target_table"] == "caa"
    assert caa["id_column"] == "ide"
    assert caa["incremental_column"] is None, "caa no tiene tiemod (R2)"
    assert caa["where"] is None, "sin filtrar (R2)"
    assert caa["exclude_columns"] == []


def test_f107_r2_el_censo_sube_a_70() -> None:
    from tests.test_f066_ingesta_raw import TOTAL_TABLAS as TOTAL_F066
    from tests.test_f074_ingesta_censo import TOTAL_TABLAS as TOTAL_F074

    assert len(_tablas()) == TOTAL_TABLAS == TOTAL_F066 == TOTAL_F074


def test_f107_r2_la_ficha_de_raw_caa_dice_de_donde_salen_codigo_y_nombre() -> None:
    texto = _texto(_ficha("raw.caa"))
    assert "`con`" in texto and "tip = 19" in texto, "R-SIGRID-CON (R2)"
    assert "184.234" in texto
    assert "maestro.cuentas_analiticas" in texto


def test_f107_r2_las_cabeceras_cuentan_70() -> None:
    raw = (DIR_DICCIONARIO / "raw.yaml").read_text(encoding="utf-8")
    assert re.search(r"[Ss]on 70 tablas", raw)
    glob = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "las 70 tablas" in glob


def test_f107_r2_la_vista_publica_sus_columnas_en_orden() -> None:
    assert _columnas_en_orden(RUTA_CUENTAS, VISTA) == list(COLUMNAS_CUENTAS)


def test_f107_r2_codigo_y_descripcion_salen_de_con() -> None:
    cuerpo = _sentencia(RUTA_CUENTAS, VISTA)
    assert "FROM raw.caa a JOIN raw.con c ON c.ide = a.ide" in cuerpo, "R-SIGRID-CON"
    assert "c.cod AS codigo_cuenta" in cuerpo
    assert "c.res AS descripcion_cuenta" in cuerpo
    assert "c.emp AS empresa_id" in cuerpo


def test_f107_r2_propiedades_de_caa_con_nullif_cero() -> None:
    cuerpo = _sentencia(RUTA_CUENTAS, VISTA)
    for origen, destino in (("padide", "cuenta_padre_id"),
                            ("cenide", "centro_coste_id"),
                            ("prpide", "partida_presupuestaria_id")):
        assert f"NULLIF(a.{origen}, 0) AS {destino}" in cuerpo, f"{destino} (R2)"
    assert "a.niv AS nivel" in cuerpo


def test_f107_r2_la_cuenta_padre_se_nombra_desde_con_con_left_join() -> None:
    """El padre es un grupo `cag` (o, en 4 casos, otra `caa`), y los dos son
    `con`: su codigo y su nombre salen de `raw.con` sin ingerir `cag`. LEFT para
    que las cuentas sin padre (nivel 1) no se pierdan."""
    cuerpo = _sentencia(RUTA_CUENTAS, VISTA)
    assert re.search(r"LEFT JOIN raw\.con (\w+) ON \1\.ide = NULLIF\(a\.padide, 0\)", cuerpo)
    assert "raw.cag" not in cuerpo


def test_f107_r2_baja_como_el_resto_de_maestros() -> None:
    cuerpo = _sentencia(RUTA_CUENTAS, VISTA)
    assert "maestro.fn_fecha(c.fecbaj) AS fecha_baja" in cuerpo
    assert "(c.fecbaj IS NULL OR c.fecbaj = 0) AS es_activa" in cuerpo


def test_f107_r2_sin_filtrar_y_solo_de_raw() -> None:
    cuerpo = _sentencia(RUTA_CUENTAS, VISTA)
    assert " WHERE " not in f" {cuerpo.upper()} ", "se publican todas, bajas incluidas (R2)"
    esquemas = set(re.findall(r"\b(\w+)\.\w+\b", cuerpo)) & {
        "stg", "mart", "cierre", "compras", "personal", "retenciones"}
    assert not esquemas, f"lee solo de raw: {esquemas} (R2)"


def test_f107_r2_el_paso_de_maestros_la_construye_la_ultima() -> None:
    """Ultima a proposito: si `raw.caa` no existe todavia (build a mano antes de
    la primera ingesta), fallan solo las cuentas y las otras seis vistas ya
    estan construidas."""
    from etl_sigrid.application.steps.build_maestros_step import SUB_PASOS

    ultimo = SUB_PASOS[-1]
    assert (ultimo.name, ultimo.sql_file) == ("cuentas_analiticas", "06_cuentas_analiticas.sql")
    assert (ultimo.target_schema, ultimo.target_table) == ("maestro", "cuentas_analiticas")


def test_f107_r2_la_ficha_documenta_todas_las_columnas() -> None:
    ficha = _ficha(VISTA)
    assert list(ficha["columnas"]) == list(COLUMNAS_CUENTAS)
    assert ficha["clave_negocio"] == ["cuenta_analitica_id"]
    assert ficha["paso_etl"] == "build_maestros"
    assert ficha["tipo"] == "vista"


def test_f107_r2_la_ficha_avisa_del_codigo_por_empresa() -> None:
    texto = _texto(_ficha(VISTA))
    assert "R-CODIGO-POR-EMPRESA" in texto
    assert "14.063" in texto and "184.234" in texto
    assert VISTA in _yaml("00_global.yaml")["reglas"][
        [r["codigo"] for r in _yaml("00_global.yaml")["reglas"]].index("R-CODIGO-POR-EMPRESA")
    ]["ambito"], "la regla alcanza al catalogo (R2)"


def test_f107_r2_la_ficha_dice_que_la_partida_esta_vacia() -> None:
    columna = _texto(_ficha(VISTA)["columnas"]["partida_presupuestaria_id"])
    assert "0" in columna and "184.234" in columna, "medido: vacia en todas (R2)"


# ===========================================================================
# R3 · medido que las cuentas de `personal` casan con el catalogo
# ===========================================================================


@pytest.mark.parametrize(("ide", "codigo", "nombre"), CUENTAS_DEL_CORREO)
def test_f107_r3_las_tres_cuentas_del_correo_estan_traducidas(
    ide: str, codigo: str, nombre: str
) -> None:
    texto = _texto(_ficha(VISTA))
    assert ide in texto and codigo in texto and nombre in texto, (
        f"la ficha no traduce {ide} como en el correo de Juan (R3)"
    )


def test_f107_r3_la_ficha_da_el_casamiento_medido() -> None:
    texto = _normalizado(_texto(_ficha(VISTA)))
    for cifra in ("3.199", "1.979", "847"):
        assert cifra in texto, f"la ficha no da el casamiento «{cifra}» (R3)"
    assert "huerfan" in texto


def test_f107_r3_tipos_de_hora_relacionan_con_el_catalogo() -> None:
    relaciones = [r for r in _relaciones("personal.recursos_tipos_hora")
                  if r["de"] == "cuenta_analitica_id"]
    assert relaciones, "falta la relacion de la cuenta del tipo de hora (R3)"
    assert relaciones[0]["a"] == "maestro.cuentas_analiticas.cuenta_analitica_id"
    assert relaciones[0]["cardinalidad"] == "N:1"


def test_f107_r3_el_catalogo_relaciona_con_el_centro_de_coste() -> None:
    relaciones = [r for r in _relaciones(VISTA) if r["de"] == "centro_coste_id"]
    assert relaciones and relaciones[0]["a"] == "maestro.centros_coste.centro_coste_id"


# ===========================================================================
# R4 · diccionario, arquitectura y azure-apps en el mismo trabajo
# ===========================================================================


def test_f107_r4_la_version_sube_a_30() -> None:
    assert int(_yaml("00_global.yaml")["version"]) == 30


def test_f107_r4_la_arquitectura_cuenta_70_tablas_y_caa() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    assert "70 tablas" in texto and "F-107" in texto and "`caa`" in texto


def test_f107_r4_azure_apps_recoge_lo_nuevo() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("maestro.cuentas_analiticas", "centro_coste_contrapartida_id",
                    "cuenta_analitica_contrapartida_id", "70 tablas", "F-107"):
        assert termino in texto, f"azure-apps no dice «{termino}» (R4)"


# ===========================================================================
# R5 · AMPLIACION (decision del humano, 2026-09-24): la cuenta de cada linea
# ===========================================================================
#
# `hmores.caaide` es la cuenta analitica de CARGO de la linea: medido en Sigrid,
# 310.553 de 331.003 lineas, 3.782 cuentas, 0 huerfanas contra `caa`, y en
# 309.182 el prefijo del codigo de la cuenta es el codigo de la obra de la
# linea. Solo 45 lineas llevan la cuenta de contrapartida del recurso.

RUTA_LINEAS = DIR_SQL / "personal" / "02_partes_lineas.sql"


def test_f107_r5_la_tabla_de_lineas_gana_la_cuenta_sin_drop() -> None:
    compacto = _compacto(_sql(RUTA_PERSONAL_SETUP))
    assert re.search(
        r"ALTER TABLE personal\.partes_lineas ADD COLUMN IF NOT EXISTS "
        r"cuenta_analitica_id BIGINT;",
        compacto,
    ), "personal.partes_lineas gana cuenta_analitica_id con ADD COLUMN IF NOT EXISTS (R5)"
    ddl = re.search(r"CREATE TABLE IF NOT EXISTS personal\.partes_lineas \((.*?)\);", compacto)
    assert ddl, "falta el CREATE TABLE de personal.partes_lineas"
    columnas = [c.strip().split(" ")[0] for c in _troceado_en_profundidad_cero(
        ddl.group(1), ",")]
    assert columnas[-1] == "cuenta_analitica_id", "nace al final en una base nueva (R5)"


def test_f107_r5_la_linea_publica_la_cuenta_con_nullif_y_sin_join() -> None:
    compacto = _compacto(_sql(RUTA_LINEAS))
    lista = re.search(r"INSERT INTO personal\.partes_lineas \((.*?)\) SELECT", compacto)
    assert lista, "falta el INSERT de personal.partes_lineas"
    assert [c.strip() for c in lista.group(1).split(",")][-1] == "cuenta_analitica_id"
    assert "NULLIF(l.caaide, 0) AS cuenta_analitica_id FROM raw.hmores l" in compacto, "R5"
    for tabla in ("raw.caa", "maestro.cuentas_analiticas"):
        assert tabla not in compacto, f"02_partes_lineas.sql no une {tabla} (R5)"


def test_f107_r5_la_ficha_documenta_la_cuenta_de_la_linea() -> None:
    ficha = _ficha("personal.partes_lineas")
    assert list(ficha["columnas"])[-1] == "cuenta_analitica_id"
    texto = _normalizado(_texto(ficha["columnas"]["cuenta_analitica_id"]))
    for cifra in ("310.55", "3.782", "0 huerfanas", "cargo", "contrapartida"):
        assert cifra in texto, f"la ficha de la cuenta de la linea no dice «{cifra}» (R5)"


def test_f107_r5_la_cuenta_de_la_linea_relaciona_con_el_catalogo() -> None:
    relaciones = [r for r in _relaciones("personal.partes_lineas")
                  if r["de"] == "cuenta_analitica_id"]
    assert relaciones, "falta la relacion de la cuenta de la linea (R5)"
    assert relaciones[0]["a"] == "maestro.cuentas_analiticas.cuenta_analitica_id"
    assert relaciones[0]["cardinalidad"] == "N:1"


def test_f107_r5_el_criterio_esta_en_la_ficha_de_la_feature() -> None:
    import json

    features = json.loads((RAIZ / "harness" / "features.json").read_text(encoding="utf-8"))
    f107 = next(f for f in features["features"] if f["id"] == "F-107")
    assert any("personal.partes_lineas" in a and "cuenta_analitica_id" in a
               for a in f107["acceptance"]), "el criterio nuevo va en acceptance (R5)"
