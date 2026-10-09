# tests/test_f067_sql.py
"""
F-067 · El SQL del contrato, del código 2 y de la fecha de Delphi, sobre su TEXTO.

`sql/compras/*.sql` y `sql/descompuestos/06_views.sql` construyen objetos en un
Postgres **compartido con producción**, así que aquí no se ejecutan: se leen.
Mismo criterio que `tests/test_f084_sql.py` y `tests/test_f038_sql.py`.

LO QUE ESTE FICHERO DEFIENDE:

1. **Los literales del SQL son los del dominio**: la época de Delphi de
   `compras.fn_sigrid_tiempo` es `EPOCA_DELPHI` (`domain/fecha_delphi.py`).
2. **Las columnas nuevas van AL FINAL** de tablas que ya consumen Power BI y el
   MCP, y las de siempre no se mueven.

La FOTO DIARIA de estados (`11_historial_estados.sql`, R1-R8) la RETIRÓ F-132
(Fase B, decisión del humano del 2026-10-09), y con ella sus tests; lo que la
sustituye lo fija `tests/test_f132_retirada.py`.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain.fecha_delphi import EPOCA_DELPHI

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
)
RUTA_SETUP = DIRECTORIO_SQL / "compras" / "00_setup.sql"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


def _funcion(texto: str, nombre: str) -> str:
    """La definición compactada de una función, de su `CREATE` a su `$$;`."""
    ejecutable = _sin_comentarios(texto)
    marca = f"CREATE OR REPLACE FUNCTION {nombre}("
    assert marca in ejecutable, f"`{nombre}` no está definida"
    inicio = ejecutable.index(marca)
    fin = ejecutable.index("$$;", ejecutable.index("AS $$", inicio))
    return re.sub(r"\s+", " ", ejecutable[inicio:fin])


# ===========================================================================
# R14 · `compras.fn_sigrid_tiempo`: la fecha de Delphi de `con.tiemod`
# ===========================================================================


def test_f067_r14_tiempo_la_funcion_esta_definida_una_vez() -> None:
    ejecutable = _sin_comentarios(_texto(RUTA_SETUP))
    assert ejecutable.count("CREATE OR REPLACE FUNCTION compras.fn_sigrid_tiempo(") == 1


def test_f067_r14_tiempo_firma_double_a_timestamp_e_inmutable() -> None:
    cuerpo = _funcion(_texto(RUTA_SETUP), "compras.fn_sigrid_tiempo")
    assert "fn_sigrid_tiempo(v DOUBLE PRECISION) RETURNS TIMESTAMP" in cuerpo
    assert "IMMUTABLE" in cuerpo


def test_f067_r14_tiempo_la_epoca_del_sql_es_la_del_dominio() -> None:
    """La de Delphi (1899-12-30), no la de SQL Server (1900-01-01): esa da dos
    días de más, medido con la fila modificada el 2026-10-05."""
    cuerpo = _funcion(_texto(RUTA_SETUP), "compras.fn_sigrid_tiempo")
    epocas = re.findall(r"TIMESTAMP '(\d{4}-\d{2}-\d{2})'", cuerpo)
    assert epocas == [EPOCA_DELPHI.isoformat()]


def test_f067_r14_tiempo_cero_y_negativo_son_nulo_y_la_hora_es_decimal() -> None:
    cuerpo = _funcion(_texto(RUTA_SETUP), "compras.fn_sigrid_tiempo")
    assert "CASE WHEN v > 0 THEN" in cuerpo, "el 0 de Sigrid es NULL, no 1899-12-30"
    assert "ELSE" not in cuerpo, "fuera del CASE tiene que salir NULL"
    assert "+ v * INTERVAL '1 day' END" in cuerpo, (
        "la parte decimal es la hora: multiplicar por un día la conserva"
    )


# ===========================================================================
# R1-R11 · la foto diaria y su vista: RETIRADAS por F-132
# ===========================================================================
#
# La vista `compras.v_estado_documentos` la crea desde F-132
# `13_estado_documentos.sql` a partir de `rac` (tests en
# `tests/test_f132_sql.py`), y la foto (`11_historial_estados.sql`) ya no
# existe: la retiró la Fase B de F-132 (`tests/test_f132_retirada.py`).


# ===========================================================================
# R12-R14 · `compras.contratos`: condiciones y última modificación, AL FINAL
# ===========================================================================

RUTA_DOCUMENTOS = DIRECTORIO_SQL / "compras" / "01_documentos.sql"

#: Las quince de siempre (doce de antes + las tres de F-084), en su orden.
COLUMNAS_CONTRATO_DE_SIEMPRE = (
    "contrato_id", "codigo_contrato", "serie", "descripcion", "fecha", "obra_id",
    "codigo_obra", "nombre_obra", "proveedor_id", "proveedor_nombre",
    "proveedor_cif", "comparativo_id", "estado_id", "estado_codigo", "estado",
)
#: Las cinco de F-067, DETRÁS y en este orden (design §5).
COLUMNAS_CONTRATO_NUEVAS = (
    "forma_pago_id",
    "forma_pago",
    "retencion_garantia_porcentaje",
    "retencion_garantia_concepto",
    "fecha_ultima_modificacion",
)


def _bloque(nombre: str) -> str:
    """El texto ejecutable compactado del bloque que construye `nombre`."""
    texto = _texto(RUTA_DOCUMENTOS)
    inicio = texto.index(f"DROP TABLE IF EXISTS {nombre} CASCADE")
    fin = texto.index(f"ALTER TABLE {nombre} ADD PRIMARY KEY", inicio)
    return _compacto(texto[inicio:fin])


def _alias_del_select(bloque: str, desde: str) -> list[str]:
    """Los `AS <alias>` de la proyección, hasta el `FROM` externo."""
    return re.findall(r"\bAS ([a-z_0-9]+)\b", bloque[: bloque.index(desde)])


def test_f067_r12_contratos_las_nuevas_van_al_final_y_las_de_siempre_no_se_mueven() -> None:
    alias = _alias_del_select(_bloque("compras.contratos"), " FROM raw.ctr c ")
    assert tuple(alias) == COLUMNAS_CONTRATO_DE_SIEMPRE + COLUMNAS_CONTRATO_NUEVAS, alias


def test_f067_r12_contratos_la_forma_de_pago_del_contrato() -> None:
    bloque = _bloque("compras.contratos")
    assert "NULLIF(c.pagide, 0) AS forma_pago_id" in bloque
    assert "pag.res AS forma_pago" in bloque
    assert "LEFT JOIN raw.auxpag pag ON pag.ide = NULLIF(c.pagide, 0)" in bloque, (
        "de `raw.auxpag` y no de `compras.formas_pago`, que se construye en 04 "
        "(después); LEFT para no perder contratos sin forma de pago"
    )


def _lateral_retencion(bloque: str) -> str:
    inicio = bloque.index("LEFT JOIN LATERAL ( SELECT")
    return bloque[inicio : bloque.index(") ret ON TRUE", inicio) + len(") ret ON TRUE")]


def test_f067_r13_contratos_la_retencion_es_el_concepto_ret_de_menor_pos() -> None:
    lateral = _lateral_retencion(_bloque("compras.contratos"))
    assert "FROM raw.ctrrec r JOIN raw.con x ON x.ide = r.recide" in lateral
    assert "AND r.docide = c.ide" in lateral
    assert "AND x.cod LIKE 'RET%'" in lateral
    assert lateral.endswith("ORDER BY r.pos, r.ide LIMIT 1 ) ret ON TRUE"), (
        "el LIMIT 1 es la guarda de grano (un contrato tiene dos); sin ORDER BY "
        "elegiría una al azar"
    )


def test_f067_r13_contratos_el_porcentaje_va_en_tanto_por_cien() -> None:
    lateral = _lateral_retencion(_bloque("compras.contratos"))
    assert "ROUND((r.valpor * 100)::NUMERIC, 4) AS porcentaje" in lateral
    assert "x.res AS concepto" in lateral
    bloque = _bloque("compras.contratos")
    assert "ret.porcentaje AS retencion_garantia_porcentaje" in bloque
    assert "ret.concepto AS retencion_garantia_concepto" in bloque


def test_f067_r13_contratos_el_lateral_del_estado_sigue_siendo_el_primero() -> None:
    """`test_f084_sql.py` lee el PRIMER `LEFT JOIN LATERAL` como el del estado."""
    bloque = _bloque("compras.contratos")
    assert bloque.index("LEFT JOIN LATERAL compras.fn_estado_documento(44, con.est)") < (
        bloque.index("LEFT JOIN LATERAL ( SELECT")
    )


def test_f067_r14_contratos_la_ultima_modificacion_es_tiemod_con_su_funcion() -> None:
    assert (
        "compras.fn_sigrid_tiempo(con.tiemod) AS fecha_ultima_modificacion"
        in _bloque("compras.contratos")
    )


# ===========================================================================
# R17-R18 · el código 2 y la necesidad en las tres tablas de líneas (D3)
# ===========================================================================

#: Las columnas de siempre de cada tabla de líneas, EN ORDEN.
LINEAS_DE_SIEMPRE = {
    "compras.contrato_lineas": (
        "linea_id", "contrato_id", "producto_id", "descripcion", "unidad_medida",
        "partida_id", "centro_coste_id", "cantidad", "precio", "importe",
        "cuota_iva", "cantidad_servida",
    ),
    "compras.albaran_lineas": (
        "linea_id", "albaran_id", "obra_id", "partida_id", "producto_id",
        "descripcion", "unidad_medida", "centro_coste_id", "cantidad", "precio",
        "importe", "cuota_iva", "cantidad_facturada", "contrato_linea_id",
        "contrato_id_linea", "importe_pendiente_facturar",
    ),
    "compras.factura_lineas": (
        "linea_id", "factura_id", "obra_id", "partida_id", "producto_id",
        "descripcion", "unidad_medida", "centro_coste_id", "cantidad", "precio",
        "importe", "cuota_iva", "albaran_linea_id", "albaran_id",
        "contrato_linea_id", "contrato_id_directo",
    ),
}
FROM_DE_LINEAS = {
    "compras.contrato_lineas": " FROM raw.ctrpro l ",
    "compras.albaran_lineas": " FROM raw.dcapro l ",
    "compras.factura_lineas": " FROM raw.dcfpro l ",
}
COLUMNAS_CODIGO_2 = ("codigo_alternativo", "necesidad_id", "necesidad_linea_id")
#: El FROM de cada tabla de líneas, tal cual: ni un JOIN que multiplique ni un
#: filtro que quite filas.
UNIVERSO_DE_LINEAS = {
    "compras.contrato_lineas": (
        "FROM raw.ctrpro l WHERE EXISTS (SELECT 1 FROM raw.ctr c WHERE c.ide = l.docide);"
    ),
    "compras.albaran_lineas": (
        "FROM raw.dcapro l WHERE EXISTS (SELECT 1 FROM raw.dca a WHERE a.ide = l.docide);"
    ),
    "compras.factura_lineas": (
        "FROM raw.dcfpro l WHERE EXISTS (SELECT 1 FROM raw.dcf f WHERE f.ide = l.docide);"
    ),
}


@pytest.mark.parametrize("tabla", sorted(LINEAS_DE_SIEMPRE))
def test_f067_r17_lineas_las_tres_nuevas_al_final(tabla: str) -> None:
    alias = _alias_del_select(_bloque(tabla), FROM_DE_LINEAS[tabla])
    assert tuple(alias) == LINEAS_DE_SIEMPRE[tabla] + COLUMNAS_CODIGO_2, alias


@pytest.mark.parametrize("tabla", sorted(LINEAS_DE_SIEMPRE))
def test_f067_r17_lineas_vacio_y_cero_son_nulo(tabla: str) -> None:
    bloque = _bloque(tabla)
    assert "NULLIF(btrim(l.cod2), '') AS codigo_alternativo" in bloque
    assert "NULLIF(l.dncide, 0) AS necesidad_id" in bloque
    assert "NULLIF(l.dncproide, 0) AS necesidad_linea_id" in bloque


@pytest.mark.parametrize("tabla", sorted(LINEAS_DE_SIEMPRE))
def test_f067_r18_lineas_el_universo_no_cambia(tabla: str) -> None:
    """Columnas nuevas, ni una fila más ni menos: el `WHERE EXISTS` de siempre."""
    bloque = _bloque(tabla)
    desde_el_from = bloque[bloque.index(FROM_DE_LINEAS[tabla]) :]
    assert desde_el_from.strip() == UNIVERSO_DE_LINEAS[tabla], desde_el_from


def test_f067_r17_albaran_lineas_indice_por_la_linea_de_necesidad() -> None:
    assert (
        "CREATE INDEX idx_com_alblin_ncl ON compras.albaran_lineas (necesidad_linea_id);"
        in _compacto(_texto(RUTA_DOCUMENTOS))
    )


# ===========================================================================
# R19 · `compras.necesidades`: el documento de necesidades (DPC) de la obra
# ===========================================================================

RUTA_NECESIDADES = DIRECTORIO_SQL / "compras" / "10_necesidades.sql"
COLUMNAS_NECESIDADES = (
    "necesidad_id",
    "codigo_necesidad",
    "nombre",
    "fecha_alta",
    "obra_id",
    "codigo_obra",
    "nombre_obra",
    "es_la_de_la_obra",
    "n_lineas",
)


def _necesidades() -> str:
    return _compacto(_texto(RUTA_NECESIDADES)).strip()


def test_f067_r19_necesidades_se_reconstruye_como_el_resto_de_compras() -> None:
    texto = _necesidades()
    assert texto.startswith(
        "DROP TABLE IF EXISTS compras.necesidades CASCADE; "
        "CREATE TABLE compras.necesidades AS SELECT "
    ), texto[:120]
    assert "ALTER TABLE compras.necesidades ADD PRIMARY KEY (necesidad_id);" in texto


def test_f067_r19_necesidades_columnas_en_orden() -> None:
    alias = _alias_del_select(_necesidades(), " FROM raw.dnc d ")
    assert tuple(alias) == COLUMNAS_NECESIDADES, alias


def test_f067_r19_necesidades_una_fila_por_dnc_con_su_concepto() -> None:
    texto = _necesidades()
    assert "d.ide AS necesidad_id" in texto
    assert " FROM raw.dnc d JOIN raw.con c ON c.ide = d.ide " in texto
    assert "c.cod AS codigo_necesidad" in texto and "c.res AS nombre" in texto
    assert "compras.fn_sigrid_date(c.fec) AS fecha_alta" in texto


def test_f067_r19_necesidades_obra_y_si_es_la_de_la_obra() -> None:
    texto = _necesidades()
    assert "NULLIF(d.obride, 0) AS obra_id" in texto
    assert "LEFT JOIN raw.con obr_con ON obr_con.ide = NULLIF(d.obride, 0)" in texto
    assert "LEFT JOIN raw.obr o ON o.ide = NULLIF(d.obride, 0)" in texto
    assert "COALESCE(o.dncide = d.ide, FALSE) AS es_la_de_la_obra" in texto


def test_f067_r19_necesidades_cuenta_sus_lineas_sin_multiplicar() -> None:
    texto = _necesidades()
    assert "COALESCE(nl.n, 0) AS n_lineas" in texto
    assert (
        "LEFT JOIN ( SELECT p.dncide, count(*) AS n FROM raw.dncpro p "
        "GROUP BY p.dncide ) nl ON nl.dncide = d.ide" in texto
    ), "agregado ANTES de unir: un JOIN a las líneas multiplicaría la cabecera"


def test_f067_r24_necesidades_no_publica_el_estado() -> None:
    """Los 277 están «En curso»: un estado que no informa no se publica."""
    assert "est" not in _alias_del_select(_necesidades(), " FROM raw.dnc d ")
    assert "con.est" not in _necesidades() and "c.est" not in _necesidades()


# ===========================================================================
# R20-R21 · `necesidad_id` en las dos vistas de planificación de `descompuestos`
# ===========================================================================

RUTA_VISTAS_DES = DIRECTORIO_SQL / "descompuestos" / "06_views.sql"
SUBCONSULTA_NECESIDAD = (
    "(SELECT NULLIF(n.dncide, 0) FROM raw.dncpro n WHERE n.ide = lineas.dncpro_id) "
    "AS necesidad_id"
)
VISTAS_CON_NECESIDAD = {
    "v_pbi_planif_jo": "PLANIF_JO",
    "v_pbi_master_planif_jo": "MASTER_PLANIF_JO",
}


def _vista_des(vista: str) -> str:
    texto = _compacto(_texto(RUTA_VISTAS_DES))
    inicio = texto.index(f"CREATE OR REPLACE VIEW descompuestos.{vista} AS SELECT ")
    return texto[inicio : texto.index(";", inicio)]


@pytest.mark.parametrize(("vista", "origen"), sorted(VISTAS_CON_NECESIDAD.items()))
def test_f067_r20_descompuestos_necesidad_id_al_final_por_subconsulta(
    vista: str, origen: str
) -> None:
    """Subconsulta escalar por la PK de `raw.dncpro`, y NO un JOIN: el `FROM
    descompuestos.lineas WHERE origen = ...` de la vista no cambia (R24 de
    F-097). Lee `raw` y no `compras.necesidades`: el `DROP ... CASCADE`
    nocturno de `compras` se llevaría la vista por delante."""
    cuerpo = _vista_des(vista)
    assert cuerpo.endswith(
        f"factor, {SUBCONSULTA_NECESIDAD} FROM descompuestos.lineas WHERE origen = '{origen}'"
    ), cuerpo[-300:]
    assert "compras." not in cuerpo


@pytest.mark.parametrize("vista", ["v_pbi_estudio", "v_pbi_master_estudio"])
def test_f067_r20_descompuestos_las_vistas_de_estudios_no_cambian(vista: str) -> None:
    """ESTUDIO y MASTER_ESTUDIO no tienen línea de necesidad (`dncpro_id`)."""
    assert "necesidad_id" not in _vista_des(vista)


def test_f067_r21_descompuestos_cuatro_vistas_y_ninguna_tabla() -> None:
    ejecutable = _compacto(_texto(RUTA_VISTAS_DES))
    assert ejecutable.count("CREATE OR REPLACE VIEW") == 4
    assert "CREATE TABLE" not in ejecutable and "ALTER TABLE" not in ejecutable
