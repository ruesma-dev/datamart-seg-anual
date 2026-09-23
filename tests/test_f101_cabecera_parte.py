# tests/test_f101_cabecera_parte.py
"""
F-101 · HOTFIX de F-057: la cabecera del parte, el codigo y el texto en cada
linea, y los tipos de hora con los precios de la ficha del recurso (R29).

Ningun test toca red ni base de datos: los objetos se construyen contra un
PostgreSQL compartido con `albaranes` y `partes` en produccion. Lo que se fija
aqui son las decisiones que la spec tomo MIDIENDO contra Sigrid vivo el
2026-09-22/23, de modo que un refactor que se lleve cualquiera por delante
rompa la suite y no la nocturna. Las cifras contra la base viva son las
verificaciones MANUALES M1-M10 de `specs/F-101-cabecera-del-parte/tasks.md`.

Mismo patron y mismos helpers que `tests/test_f057_personal.py`, COPIADOS y no
importados: si alguien borra aquel fichero, estos guardas siguen en pie (R14).

Tres familias:

1. **El SQL**, sobre su texto: DDL, `03_partes.sql`, `04_recursos_tipos_hora.sql`
   y lo que cambia en `02_partes_lineas.sql`.
2. **La propagacion**: el step, el inventario de `check-declarados`, la ingesta
   de `hmores.tex` y el documento de `azure-apps`.
3. **La ficha del diccionario**, con las cifras que la hacen util: sin ellas el
   agente del MCP comete la trampa que la ficha existe para evitar.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_PERSONAL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "personal"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

RUTA_SETUP = DIR_PERSONAL / "00_setup.sql"
RUTA_RECURSOS = DIR_PERSONAL / "01_recursos.sql"
RUTA_LINEAS = DIR_PERSONAL / "02_partes_lineas.sql"
RUTA_CABECERA = DIR_PERSONAL / "03_partes.sql"
RUTA_TIPOS_HORA = DIR_PERSONAL / "04_recursos_tipos_hora.sql"
RUTA_VISTAS = DIR_PERSONAL / "05_views.sql"

#: Los seis ficheros del step, EN ORDEN (D-7: el numero es el orden).
FICHEROS_PERSONAL = [
    "00_setup.sql",
    "01_recursos.sql",
    "02_partes_lineas.sql",
    "03_partes.sql",
    "04_recursos_tipos_hora.sql",
    "05_views.sql",
]

COLUMNAS_PARTES = (
    "parte_id", "codigo_parte", "descripcion", "fecha", "anio", "mes",
    "obra_cabecera_id", "centro_coste_cabecera_id", "estado_id", "estado",
    "activo", "fecha_baja", "fecha_modificacion", "num_lineas",
    "lineas_en_otra_obra", "_built_at",
)

COLUMNAS_TIPOS_HORA = (
    "reshor_id", "recurso_id", "tipo_hora_id", "codigo_tipo_hora", "tipo_hora",
    "unidad", "precio_coste", "precio_venta", "cantidad_defecto",
    "cuenta_analitica_id", "es_por_defecto", "orden", "tipo_hora_de_baja",
    "_built_at",
)


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


def _ddl_de(tabla: str) -> str:
    """El cuerpo del `CREATE TABLE` de `personal.<tabla>`, compacto."""
    encontrado = re.search(
        rf"CREATE TABLE IF NOT EXISTS personal\.{tabla} \((.*?)\);",
        _compacto(_sql(RUTA_SETUP)),
    )
    assert encontrado, f"falta el CREATE TABLE de personal.{tabla}"
    return encontrado.group(1)


def _plano(texto: str) -> str:
    """Minusculas y sin tildes: para buscar palabras en la prosa de una ficha."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def _case_medide(ruta: Path) -> str:
    encontrado = re.search(
        r"CASE \w+\.medide\b.*?END::VARCHAR\(12\) AS unidad", _compacto(_sql(ruta))
    )
    assert encontrado, f"{ruta.name}: falta el CASE de la unidad sobre `medide`"
    return encontrado.group(0)


# ===========================================================================
# A · personal.partes — la cabecera (R1-R12)
# ===========================================================================


def test_f101_r1_ddl_partes() -> None:
    """Una TABLA con las 16 columnas del diseno y `parte_id` de clave primaria."""
    ddl = _ddl_de("partes")

    for columna in COLUMNAS_PARTES:
        assert re.search(rf"(?:^|, )\s*{columna}\s+[A-Z]", ddl), (
            f"personal.partes debe declarar la columna {columna} (R1)"
        )
    assert re.search(r"(?:^|, )\s*parte_id BIGINT PRIMARY KEY", ddl)


def test_f101_r1_ddl_partes_indices() -> None:
    compacto = _compacto(_sql(RUTA_SETUP))

    for indice in (
        r"\(obra_cabecera_id, anio, mes\)", r"\(codigo_parte\)", r"\(estado_id\)",
    ):
        assert re.search(
            rf"CREATE INDEX IF NOT EXISTS \w+ ON personal\.partes {indice}", compacto
        ), f"falta el indice {indice} de personal.partes (R1)"
    assert not re.search(r"CREATE UNIQUE INDEX[^;]*codigo_parte", compacto), (
        "el codigo del parte NO es unico: 569 codigos repetidos (R3)"
    )


def test_f101_r1_partes_una_fila_por_parte() -> None:
    """Grano `raw.hmo` = `raw.con` con `tip = 35` (R-SIGRID-CON), 6.886 filas."""
    compacto = _compacto(_sql(RUTA_CABECERA))

    assert "TRUNCATE TABLE personal.partes;" in compacto
    assert "INSERT INTO personal.partes (" in compacto
    assert re.search(r"FROM raw\.hmo h JOIN raw\.con c ON c\.ide = h\.ide", compacto), (
        "la cabecera es `raw.hmo` y su codigo, fecha y estado salen de `raw.con` (R1)"
    )
    assert re.search(r"\bh\.ide\s+AS parte_id\b", compacto)


def test_f101_r2_codigo_parte_desde_con_cod() -> None:
    assert re.search(r"\bc\.cod\s+AS codigo_parte\b", _compacto(_sql(RUTA_CABECERA)))


def test_f101_r4_descripcion_desde_con_res_y_no_tex() -> None:
    """`con.res` en 6.883 de 6.886; `con.tex` solo en 3 partes (660 bytes)."""
    assert re.search(r"\bc\.res\s+AS descripcion\b", _compacto(_sql(RUTA_CABECERA)))
    assert not re.search(r"\btex\b", _sin_comentarios(_sql(RUTA_CABECERA))), (
        "la descripcion del parte es `con.res`, no `con.tex` (R4)"
    )


def test_f101_r5_fecha_anio_y_mes() -> None:
    compacto = _compacto(_sql(RUTA_CABECERA))

    assert re.search(r"personal\.fn_fecha\(c\.fec\)\s+AS fecha\b", compacto)
    assert re.search(r"\bh\.ano\s+AS anio\b", compacto)
    assert re.search(r"\bh\.mes\s+AS mes\b", compacto)


def test_f101_r6_obra_y_centro_de_cabecera_con_sufijo() -> None:
    """D-1: la de la LINEA imputa, la de CABECERA audita. Nunca `obra_id`."""
    compacto = _compacto(_sql(RUTA_CABECERA))

    assert re.search(r"NULLIF\(h\.obride, 0\)\s+AS obra_cabecera_id\b", compacto)
    assert re.search(r"NULLIF\(h\.cenide, 0\)\s+AS centro_coste_cabecera_id\b", compacto)
    for prohibida in ("obra_id", "centro_coste_id"):
        assert not re.search(rf"\bAS {prohibida}\b", compacto), (
            f"`{prohibida}` a secas se confunde con la de la linea (R6, D-1)"
        )
        assert not re.search(rf"(?:^|, )\s*{prohibida}\s+[A-Z]", _ddl_de("partes")), (
            f"personal.partes no puede declarar `{prohibida}` (R6, D-1)"
        )


def test_f101_r7_estado_traducido_contra_conest_tipo_35() -> None:
    """1 REG «En registro», 3 CER «Cerrado», 10 IMP «Imputado»: filtrando TIPO."""
    compacto = _compacto(_sql(RUTA_CABECERA))

    assert re.search(r"\bc\.est\s+AS estado_id\b", compacto)
    lateral = re.search(
        r"LEFT JOIN LATERAL \( SELECT ce\.res FROM raw\.conest ce "
        r"WHERE ce\.tip = 35 AND ce\.est = c\.est ORDER BY ce\.ide LIMIT 1 \) es ON TRUE",
        compacto,
    )
    assert lateral, "el estado se traduce con el LATERAL de maestro/01_obras.sql (R7)"
    assert re.search(r"\bes\.res\s+AS estado\b", compacto)


def test_f101_r8_activo_con_el_vocabulario_de_recursos_y_sin_filtrar() -> None:
    """Mismo `activo` y `fecha_baja` que `personal.recursos`; 218 de baja."""
    cabecera = _compacto(_sql(RUTA_CABECERA))
    recursos = _compacto(_sql(RUTA_RECURSOS))

    for expresion in (
        r"\(COALESCE\(c\.fecbaj, 0\) = 0\)\s+AS activo\b",
        r"personal\.fn_fecha\(c\.fecbaj\)\s+AS fecha_baja\b",
    ):
        assert re.search(expresion, recursos), "cambio el vocabulario de recursos"
        assert re.search(expresion, cabecera), f"{expresion} no esta en la cabecera (R8)"
    assert not re.search(r"\bWHERE\b[^;]*\bfecbaj\b", _sin_comentarios(_sql(RUTA_CABECERA))), (
        "la baja se MARCA, no se filtra (R8)"
    )


def test_f101_r9_fecha_modificacion_con_fecha_serie_local() -> None:
    """`con.tiemod` es fecha serie, epoca 1899-12-30 verificada por dos vias."""
    setup = _compacto(_sql(RUTA_SETUP))

    assert re.search(
        r"CREATE OR REPLACE FUNCTION personal\.fn_fecha_serie\(d DOUBLE PRECISION\) "
        r"RETURNS DATE",
        setup,
    )
    assert "DATE '1899-12-30'" in setup
    assert re.search(
        r"personal\.fn_fecha_serie\(c\.tiemod\)\s+AS fecha_modificacion\b",
        _compacto(_sql(RUTA_CABECERA)),
    )
    for ajena in ("stg.", "compras.", "maestro.", "retenciones."):
        cuerpo = setup.split("personal.fn_fecha_serie", 1)[1].split("$$;", 1)[0]
        assert ajena not in cuerpo, "la funcion es local al esquema (R9)"


def test_f101_r10_recuento_de_lineas_en_otra_obra() -> None:
    """615 lineas en 14 partes: se cuenta contra `raw.hmores`, no contra
    `personal.partes_lineas`, para no depender del orden de los ficheros (D-2)."""
    compacto = _compacto(_sql(RUTA_CABECERA))

    assert re.search(
        r"LEFT JOIN LATERAL \( SELECT COUNT\(\*\) AS n, COUNT\(\*\) FILTER \( "
        r"WHERE NULLIF\(l\.obride, 0\) IS NOT NULL AND NULLIF\(h\.obride, 0\) IS NOT NULL "
        r"AND l\.obride <> h\.obride \) AS d FROM raw\.hmores l WHERE l\.hmoide = h\.ide \) "
        r"ln ON TRUE",
        compacto,
    ), "falta el LATERAL del recuento de lineas (R10)"
    assert re.search(r"COALESCE\(ln\.n, 0\)\s+AS num_lineas\b", compacto)
    assert re.search(r"COALESCE\(ln\.d, 0\)\s+AS lineas_en_otra_obra\b", compacto)
    assert "personal.partes_lineas" not in compacto


def test_f101_r11_no_publica_las_columnas_a_cero() -> None:
    """`feccie`, `cla` y `caaide` valen 0 en las 6.886; `reside` esta en 6."""
    ejecutable = _sin_comentarios(_sql(RUTA_CABECERA))

    for muerta in ("feccie", "cla", "caaide", "reside"):
        assert not re.search(rf"\b{muerta}\b", ejecutable), (
            f"`hmo.{muerta}` no aporta nada: no se publica (R11)"
        )


def test_f101_r12_el_usuario_creador_no_se_publica() -> None:
    """Vive en `dbo.log` (8,47 M filas, no ingerida): es F-105."""
    for prohibida in ("usuario", "creador", "usuario_alta"):
        assert not re.search(rf"\b{prohibida}\w*\s+[A-Z]", _ddl_de("partes"))
    ficha = _ficha_de("partes")
    assert "dbo.log" in ficha.descripcion and "F-105" in ficha.descripcion, (
        "la ficha tiene que decir DONDE esta el usuario y POR QUE no se trae (R12)"
    )


# ===========================================================================
# B · personal.partes_lineas — el codigo y el texto en la linea (R13-R16)
# ===========================================================================


def test_f101_r13_codigo_parte_en_la_linea() -> None:
    """Por `raw.con` sobre `hmoide`: 0 de 330.941 lineas sin cabecera."""
    compacto = _compacto(_sql(RUTA_LINEAS))

    assert re.search(r"LEFT JOIN raw\.con c ON c\.ide = l\.hmoide", compacto)
    assert re.search(r"\bc\.cod\s+AS codigo_parte\b", compacto)
    assert re.search(r"(?:^|, )\s*codigo_parte VARCHAR\(24\)", _ddl_de("partes_lineas"))


def test_f101_r13_codigo_parte_llega_a_una_tabla_que_ya_existe() -> None:
    """`CREATE TABLE IF NOT EXISTS` no anade columnas a la tabla que la nocturna
    del 23 ya creo: sin el `ALTER`, el INSERT revienta la primera noche."""
    assert re.search(
        r"ALTER TABLE personal\.partes_lineas ADD COLUMN IF NOT EXISTS "
        r"codigo_parte VARCHAR\(24\)",
        _compacto(_sql(RUTA_SETUP)),
    )


def test_f101_r14_el_veto_de_f057_sigue_en_pie() -> None:
    """Relanzado aqui para que borrar `test_f057_personal.py` no lo apague."""
    compacto = _compacto(_sql(RUTA_LINEAS))

    assert not re.search(r"\braw\.hmo\b", _sin_comentarios(_sql(RUTA_LINEAS))), (
        "la cabecera `raw.hmo` no participa en las lineas: 615 la contradicen (R14)"
    )
    assert re.search(r"NULLIF\(\w+\.obride, 0\)\s+AS obra_id", compacto)
    assert "obra_cabecera_id" not in compacto, "la obra de cabecera no baja a la linea"


def test_f101_r15_hmores_tex_se_ingiere_con_sus_cifras() -> None:
    """D-3 aprobada: +284.080 B sobre 101 MB, +0,27 %."""
    tablas = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))["tables"]
    hmores = next(t for t in tablas if t["source_table"] == "hmores")

    assert "tex" not in (hmores["exclude_columns"] or []), (
        "`hmores.tex` entra desde F-101 (D-3) (R15)"
    )
    crudo = FICHERO_TABLAS.read_text(encoding="utf-8")
    bloque = crudo.split("source_table: hmores", 1)[1].split("- source_table:", 1)[0]
    for cifra in ("13.390", "284.080", "0,27"):
        assert cifra in bloque, f"el comentario de `hmores` tiene que citar {cifra} (R15)"


def test_f101_r16_texto_linea_publicado() -> None:
    compacto = _compacto(_sql(RUTA_LINEAS))

    assert re.search(r"NULLIF\(l\.tex, ''\)\s+AS texto_linea\b", compacto)
    assert re.search(r"(?:^|, )\s*texto_linea TEXT", _ddl_de("partes_lineas"))
    assert re.search(
        r"ALTER TABLE personal\.partes_lineas ADD COLUMN IF NOT EXISTS texto_linea TEXT",
        _compacto(_sql(RUTA_SETUP)),
    )


def test_f101_r16_ficha_texto_linea_avisa_de_nombres_de_persona() -> None:
    texto = _plano(_columna("partes_lineas", "texto_linea").significado)

    assert "texto libre" in texto
    assert "nombres de persona" in texto, "el texto puede llevar nombres (R16)"


# ===========================================================================
# C · personal.recursos_tipos_hora — los precios de la ficha (R17-R25)
# ===========================================================================


def test_f101_r17_ddl_tipos_hora() -> None:
    ddl = _ddl_de("recursos_tipos_hora")

    for columna in COLUMNAS_TIPOS_HORA:
        assert re.search(rf"(?:^|, )\s*{columna}\s+[A-Z]", ddl), (
            f"personal.recursos_tipos_hora debe declarar la columna {columna} (R17)"
        )
    assert re.search(r"(?:^|, )\s*reshor_id BIGINT PRIMARY KEY", ddl)
    compacto = _compacto(_sql(RUTA_SETUP))
    for indice in (r"\(recurso_id\)", r"\(tipo_hora_id\)"):
        assert re.search(
            rf"CREATE INDEX IF NOT EXISTS \w+ ON personal\.recursos_tipos_hora {indice}",
            compacto,
        ), f"falta el indice {indice} de personal.recursos_tipos_hora (R17)"


def test_f101_r17_tipos_hora_una_fila_por_reshor() -> None:
    compacto = _compacto(_sql(RUTA_TIPOS_HORA))

    assert "TRUNCATE TABLE personal.recursos_tipos_hora;" in compacto
    assert "INSERT INTO personal.recursos_tipos_hora (" in compacto
    assert re.search(r"FROM raw\.reshor rh\b", compacto)
    assert re.search(r"\brh\.ide\s+AS reshor_id\b", compacto)
    assert re.search(r"NULLIF\(rh\.reside, 0\)\s+AS recurso_id\b", compacto)
    assert re.search(r"NULLIF\(rh\.horide, 0\)\s+AS tipo_hora_id\b", compacto)
    cuerpo = compacto.split("FROM raw.reshor", 1)[1]
    assert " WHERE " not in cuerpo.upper(), "no se filtra ninguna fila de `reshor` (R17)"


def test_f101_r18_tipos_hora_la_clave_es_reshor_id_y_no_el_par() -> None:
    """17 pares repetidos; uno (recurso 947513, tipo 27) con dos precios (D-4)."""
    ficha = _ficha_de("recursos_tipos_hora")

    assert ficha.clave_negocio == ("reshor_id",)
    texto = ficha.descripcion + ficha.grano
    assert "17" in texto and "947513" in texto, "la ficha dice POR QUE no es el par (R18)"


def test_f101_r19_tipos_hora_unidad_con_el_mismo_case_que_las_lineas() -> None:
    """Dos traducciones que divergen son peor que una sola equivocada."""
    assert _case_medide(RUTA_TIPOS_HORA) == _case_medide(RUTA_LINEAS), (
        "el CASE de `medide` tiene que ser IDENTICO en las lineas y en la ficha (R19)"
    )
    compacto = _compacto(_sql(RUTA_TIPOS_HORA))
    assert re.search(r"\bh\.res\s+AS tipo_hora\b", compacto)
    assert re.search(r"\bh\.cod\s+AS codigo_tipo_hora\b", compacto)
    assert not re.search(r"\bext\b", _sin_comentarios(_sql(RUTA_TIPOS_HORA))), (
        "`auxhor.ext` esta a 0 en el catalogo: no clasifica (R19)"
    )


def test_f101_r20_tipos_hora_left_join_al_catalogo() -> None:
    """3 filas apuntan a un tipo de hora que no esta en `auxhor`."""
    compacto = _compacto(_sql(RUTA_TIPOS_HORA))

    assert re.search(r"LEFT JOIN raw\.auxhor h ON h\.ide = rh\.horide", compacto)
    assert not re.search(r"(?<!LEFT) JOIN raw\.auxhor", compacto), (
        "con JOIN a secas las 3 filas sin catalogo desaparecen sin ruido (R20)"
    )


def test_f101_r21_tipos_hora_precios_y_cantidades() -> None:
    compacto = _compacto(_sql(RUTA_TIPOS_HORA))

    for origen, destino in (
        ("pre", "precio_coste"), ("preven", "precio_venta"),
        ("candef", "cantidad_defecto"),
    ):
        assert re.search(rf"COALESCE\(rh\.{origen}, 0\)::NUMERIC\(18,4\)\s+AS {destino}\b",
                         compacto), f"{destino} sale de `reshor.{origen}` (R21)"
    assert re.search(r"NULLIF\(rh\.caaide, 0\)\s+AS cuenta_analitica_id\b", compacto)
    assert re.search(r"\brh\.pos\s+AS orden\b", compacto)
    assert re.search(r"\(h\.fecbaj <> 0\)\s+AS tipo_hora_de_baja\b", compacto)


def test_f101_r21_ficha_avisa_de_que_precio_venta_casi_no_esta() -> None:
    texto = _columna("recursos_tipos_hora", "precio_venta").significado

    assert re.search(r"\b3 de (?:las )?8\.9\d\d\b", texto), (
        "`preven` esta informado en 3 filas: la ficha lo dice con la cifra (R21, D-9)"
    )


def test_f101_r22_no_publica_prenom_ni_columnas_a_cero() -> None:
    """`prenom` por decision del humano; `cuaide` y `proide` valen 0."""
    for ruta in (RUTA_TIPOS_HORA, RUTA_SETUP):
        ejecutable = _sin_comentarios(_sql(ruta))
        for vetada in ("prenom", "cuaide", "proide"):
            assert not re.search(rf"\b{vetada}\b", ejecutable), (
                f"{ruta.name}: `reshor.{vetada}` no se publica (R22)"
            )
    nombres = {c.nombre for c in _ficha_de("recursos_tipos_hora").columnas}
    assert not {"precio_nomina", "prenom"} & nombres


def test_f101_r23_es_por_defecto_desde_res_horide() -> None:
    compacto = _compacto(_sql(RUTA_TIPOS_HORA))

    assert re.search(r"LEFT JOIN raw\.res r ON r\.ide = rh\.reside", compacto)
    assert re.search(
        r"COALESCE\(NULLIF\(r\.horide, 0\) = rh\.horide, FALSE\)\s+AS es_por_defecto\b",
        compacto,
    ), "`es_por_defecto` compara `res.horide` con el tipo de la fila (R23, D-8 A)"
    texto = _plano(_columna("recursos_tipos_hora", "es_por_defecto").significado)
    assert "4 recursos" in texto, "los 4 recursos sin fila de su defecto (R23)"


def test_f101_r24_ficha_declara_que_no_hay_historico_de_precios() -> None:
    texto = _plano(_ficha_de("recursos_tipos_hora").descripcion)

    assert "historico" in texto and "hoy" in texto, (
        "`reshor` no tiene fechas ni `tiemod`: son los precios de HOY (R24, D-5)"
    )


def test_f101_r25_ficha_cuantifica_el_desfase_con_las_lineas() -> None:
    """La pregunta de Juan (el caso Jaime Rabadan), con su cifra."""
    texto = _ficha_de("recursos_tipos_hora").descripcion

    for cifra in ("156.819", "279.034", "56,2"):
        assert cifra in texto, f"la ficha tiene que citar {cifra} (R25)"


# ===========================================================================
# D · Propagacion e integridad (R26-R30)
# ===========================================================================


def test_f101_r26_step_seis_sub_pasos_en_orden() -> None:
    from etl_sigrid.application.steps import build_personal_step

    subs = build_personal_step.SUB_PASOS
    assert [s.sql_file for s in subs] == FICHEROS_PERSONAL
    assert [s.name for s in subs] == [
        "setup", "recursos", "partes_lineas", "partes", "recursos_tipos_hora", "views",
    ]
    por_nombre = {s.name: s for s in subs}
    for nombre in ("partes", "recursos_tipos_hora"):
        assert por_nombre[nombre].target_schema == "personal"
        assert por_nombre[nombre].target_table == nombre, f"{nombre} cuenta sus filas"
    assert por_nombre["views"].target_table is None
    for sub in subs:
        assert (DIR_PERSONAL / sub.sql_file).exists(), f"{sub.sql_file} no existe"


def test_f101_r26_step_encadena_los_seis_y_cuenta_cuatro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from etl_sigrid.application.steps import build_personal_step
    from etl_sigrid.application.steps.build_personal_step import BuildPersonalStep
    from etl_sigrid.domain.entities import StepStatus

    class _PgFalso:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []
            self.contados: list[tuple[str, str]] = []

        def execute_sql_file(self, path: Path) -> None:
            self.ejecutados.append(path.name)

        def count_rows(self, schema: str, table: str) -> int:
            self.contados.append((schema, table))
            return 3

    pg = _PgFalso()
    monkeypatch.setattr(build_personal_step, "build_postgres_client", lambda _s: pg)

    resultado = BuildPersonalStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS_PERSONAL
    assert pg.contados == [
        ("personal", "recursos"), ("personal", "partes_lineas"),
        ("personal", "partes"), ("personal", "recursos_tipos_hora"),
    ]
    assert resultado.rows_processed == 12


def test_f101_r26_personal_sigue_sin_dependientes() -> None:
    """Un fallo de `build_personal` no puede tumbar la nocturna."""
    import main

    ajustes = SimpleNamespace(postgres=SimpleNamespace(
        readonly_role="mcp_sigrid_dm_ro", set_role="sigrid_dm_etl",
        consumption_schema_list=["mart"],
    ))
    for paso in main.build_pipeline_steps(ajustes):
        assert "build_personal" not in paso.depends_on, paso.name


def test_f101_r27_check_declarados_ve_los_objetos_nuevos() -> None:
    from etl_sigrid.infrastructure.inventario_repositorio import (
        inventario_del_repositorio,
    )

    nombres = {o.nombre: o.tipo for o in inventario_del_repositorio()}

    assert nombres.get("personal.partes") == "tabla"
    assert nombres.get("personal.recursos_tipos_hora") == "tabla"
    assert nombres.get("personal.fn_fecha_serie") == "funcion"
    assert nombres.get("personal.v_pbi_horas_obra_mes") == "vista", "05_views.sql"


def test_f101_r27_sin_pendientes_nuevos() -> None:
    """`config/objetos_pendientes.yaml` es un trinquete: sigue vacio."""
    pendientes = yaml.safe_load(
        (RAIZ / "config" / "objetos_pendientes.yaml").read_text(encoding="utf-8")
    )
    assert not ((pendientes or {}).get("pendientes") or []), "no se aplaza nada (R27)"


@cache
def _diccionario():
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _ficha_de(objeto: str):
    fichas = {f.objeto: f for f in _diccionario().fichas if f.esquema == "personal"}
    assert objeto in fichas, f"falta la ficha de personal.{objeto} (R28)"
    return fichas[objeto]


def _columna(objeto: str, columna: str):
    columnas = {c.nombre: c for c in _ficha_de(objeto).columnas}
    assert columna in columnas, f"la ficha de personal.{objeto} no documenta {columna}"
    return columnas[columna]


@pytest.mark.parametrize(
    ("objeto", "tipo", "clave"),
    [
        ("partes", "tabla", ("parte_id",)),
        ("recursos_tipos_hora", "tabla", ("reshor_id",)),
        ("fn_fecha_serie", "funcion", ()),
    ],
)
def test_f101_r28_ficha_de_cada_objeto_nuevo(objeto: str, tipo: str, clave: tuple) -> None:
    ficha = _ficha_de(objeto)

    assert ficha.tipo == tipo
    assert ficha.paso_etl == "build_personal"
    assert ficha.refresco == "nocturno"
    assert ficha.clave_negocio == clave


@pytest.mark.parametrize(
    ("objeto", "columnas"),
    [
        ("partes", COLUMNAS_PARTES),
        ("recursos_tipos_hora", COLUMNAS_TIPOS_HORA),
        ("partes_lineas", ("codigo_parte", "texto_linea")),
    ],
)
def test_f101_r28_ficha_documenta_cada_columna(objeto: str, columnas: tuple) -> None:
    """Una columna publicada sin significado es una columna que el MCP adivina."""
    documentadas = {c.nombre for c in _ficha_de(objeto).columnas}

    assert set(columnas) <= documentadas, sorted(set(columnas) - documentadas)
    if objeto != "partes_lineas":
        assert documentadas == set(columnas), "la ficha documenta columnas que no existen"


def test_f101_r28_ficha_relaciones_declaradas() -> None:
    """`check-relaciones` se alimenta de aqui: lo que hay que escribir es el YAML."""
    partes = {r.de: (r.a, r.cardinalidad) for r in _ficha_de("partes").relaciones}
    assert partes.get("obra_cabecera_id") == ("maestro.obras.obra_id", "N:1")
    assert partes.get("centro_coste_cabecera_id") == (
        "maestro.centros_coste.centro_coste_id", "N:1",
    )
    assert partes.get("parte_id") == ("personal.partes_lineas.parte_id", "1:N")

    lineas = {r.de: r.a for r in _ficha_de("partes_lineas").relaciones}
    assert lineas.get("parte_id") == "personal.partes.parte_id"

    tipos = {r.de: r.a for r in _ficha_de("recursos_tipos_hora").relaciones}
    assert tipos.get("recurso_id") == "personal.recursos.recurso_id"


def test_f101_r3_ficha_codigo_parte_no_es_clave() -> None:
    """569 codigos repetidos que afectan a 1.197 partes: la clave es `parte_id`."""
    texto = _columna("partes", "codigo_parte").significado

    assert "569" in texto and "1.197" in texto and "parte_id" in texto


def test_f101_r5_ficha_declara_anio_y_mes_fuera_de_rango() -> None:
    assert "27" in _columna("partes", "anio").significado
    assert re.search(r"\b2\b", _columna("partes", "mes").significado)


def test_f101_r6_ficha_dice_quien_imputa_y_quien_audita() -> None:
    texto = _plano(_columna("partes", "obra_cabecera_id").significado)

    assert "audit" in texto and "imputa" in texto, "patron F-093 en la ficha (R6)"


def test_f101_r9_ficha_de_la_fecha_serie_con_la_epoca_verificada() -> None:
    texto = _ficha_de("fn_fecha_serie").descripcion

    assert "1899-12-30" in texto and "46287" in texto


def test_f101_r10_ficha_cita_la_discrepancia() -> None:
    texto = _columna("partes", "lineas_en_otra_obra").significado

    assert "615" in texto and "14" in texto


def test_f101_r28_diccionario_sigue_validando() -> None:
    import main
    from etl_sigrid.domain.diccionario import validar

    ajustes = SimpleNamespace(postgres=SimpleNamespace(
        readonly_role="mcp_sigrid_dm_ro", set_role="sigrid_dm_etl",
        consumption_schema_list=["mart"],
    ))
    pasos = tuple(p.name for p in main.build_pipeline_steps(ajustes))
    errores = validar(_diccionario(), pasos)

    assert errores == [], "\n".join(f"{e.objeto}: {e.detalle}" for e in errores[:10])


def test_f101_r28_version_sube() -> None:
    """`personal.yaml` 1 -> 2; `00_global.yaml` 27 -> 28 (ya estaba en 27)."""
    personal = yaml.safe_load((DIR_DICCIONARIO / "personal.yaml").read_text(encoding="utf-8"))
    assert int(personal["version"]) == 2
    assert int(_diccionario().version) >= 28


def test_f101_r29_cada_requisito_tiene_su_test() -> None:
    """Trazabilidad: un `test_f101_rN_*` por cada requisito R1-R30."""
    nombres = [n for n in dir(sys.modules[__name__]) if n.startswith("test_f101_r")]
    cubiertos = {int(m.group(1)) for n in nombres if (m := re.match(r"test_f101_r(\d+)_", n))}

    assert set(range(1, 31)) <= cubiertos, sorted(set(range(1, 31)) - cubiertos)


def test_f101_r30_azure_apps_lista_los_objetos_nuevos() -> None:
    """El documento del proyecto en `azure-apps/` pasa de 3 a 5 objetos."""
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")

    for objeto in ("personal.partes`", "personal.recursos_tipos_hora`"):
        assert objeto in texto, f"`{objeto} no esta en azure-apps (R30)"
