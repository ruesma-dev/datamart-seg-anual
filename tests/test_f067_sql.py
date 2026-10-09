# tests/test_f067_sql.py
"""
F-067 · El SQL de la foto diaria, del contrato y del código 2, sobre su TEXTO.

`sql/compras/*.sql` y `sql/descompuestos/06_views.sql` construyen objetos en un
Postgres **compartido con producción**, así que aquí no se ejecutan: se leen.
Mismo criterio que `tests/test_f084_sql.py` y `tests/test_f038_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Las dos tablas de la foto NO se reconstruyen** (R8): ni `DROP`, ni
   `TRUNCATE`, ni `DELETE` en `11_historial_estados.sql`. Es historia que no
   existe en Sigrid; lo que se borre no vuelve.
2. **Los literales del SQL son los del dominio** (`domain/historial_estados.py`):
   los tipos, el 0.98, los motivos y la época de Delphi. El oráculo se prueba
   en `tests/test_f067_dominio.py`; aquí, que el SQL dice lo mismo.
3. **Las columnas nuevas van AL FINAL** de tablas que ya consumen Power BI y el
   MCP, y las de siempre no se mueven.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain.historial_estados import (
    EPOCA_DELPHI,
    MOTIVOS_CIERRE,
    TIPOS_HISTORIAL,
    UMBRAL_PRESENCIA,
)

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
# R1-R8 · `11_historial_estados.sql`: las dos tablas persistentes y la foto
# ===========================================================================

RUTA_HISTORIAL = DIRECTORIO_SQL / "compras" / "11_historial_estados.sql"

#: Las columnas de cada tabla persistente, EN ORDEN (design §3).
COLUMNAS_HISTORIAL = (
    "documento_id",
    "tipo_documento_codigo",
    "estado_id",
    "desde",
    "hasta",
    "observado_antes",
    "es_linea_base",
    "motivo_cierre",
)
COLUMNAS_FOTOS = (
    "observado_en",
    "tomada_en",
    "es_linea_base",
    "n_documentos",
    "n_cambios",
    "n_altas",
    "n_desaparecidos",
)

#: Los únicos ficheros de `etl_sigrid/` que pueden nombrar las tablas de la foto.
QUIEN_PUEDE_NOMBRARLAS = {
    "application/steps/build_compras_step.py",
    "domain/historial_estados.py",
    "infrastructure/postgres/sql/compras/11_historial_estados.sql",
    # `reset-compras`: el que las PROTEGE (importa `TABLAS_PERSISTENTES`).
    "infrastructure/postgres/compras_reset_sql.py",
    # F-132: el contraste foto <-> `rac`, que las LEE con SELECT de solo
    # lectura (`tests/test_f132_contraste.py` fija que no escribe).
    "infrastructure/postgres/contraste_estados_sql.py",
}


def _ejecutable_historial() -> str:
    return _sin_comentarios(_texto(RUTA_HISTORIAL))


def _definicion_tabla(nombre: str) -> str:
    """El cuerpo del `CREATE TABLE IF NOT EXISTS <nombre> (...)`, sin comentarios."""
    texto = re.sub(r"--[^\n]*", " ", _texto(RUTA_HISTORIAL))
    marca = f"CREATE TABLE IF NOT EXISTS {nombre} ("
    assert marca in texto, f"`{nombre}` no se crea con CREATE TABLE IF NOT EXISTS"
    inicio = texto.index(marca) + len(marca)
    profundidad, fin = 1, inicio
    while profundidad:
        profundidad += (texto[fin] == "(") - (texto[fin] == ")")
        fin += 1
    return re.sub(r"\s+", " ", texto[inicio : fin - 1])


def _columnas_de(definicion: str) -> list[str]:
    partes, actual, profundidad = [], [], 0
    for caracter in definicion:
        profundidad += (caracter == "(") - (caracter == ")")
        if caracter == "," and profundidad == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(caracter)
    partes.append("".join(actual))
    return [
        p.split()[0] for p in partes
        if p.strip() and p.split()[0].upper() not in ("PRIMARY", "CHECK", "UNIQUE")
    ]


def _bloque_do() -> str:
    ejecutable = _compacto(_texto(RUTA_HISTORIAL))
    inicio = ejecutable.index("DO $$")
    return ejecutable[inicio : ejecutable.index("END $$;", inicio)]


def _paso(bloque: str, inicio: str, fin: str = "GET DIAGNOSTICS") -> str:
    desde = bloque.index(inicio)
    return bloque[desde : bloque.index(fin, desde)]


@pytest.mark.parametrize("palabra", ["DROP", "TRUNCATE", "DELETE"])
def test_f067_r8_veto_el_fichero_no_borra_ni_vacia_nada(palabra: str) -> None:
    """La historia no existe en Sigrid: lo que se borre no vuelve."""
    assert not re.search(rf"\b{palabra}\b", _ejecutable_historial(), re.IGNORECASE), (
        f"`11_historial_estados.sql` contiene `{palabra}`: las dos tablas de la "
        "foto son historia que no se puede recuperar (R8)"
    )


def test_f067_r8_veto_ningun_otro_sql_ni_step_nombra_las_tablas_de_la_foto() -> None:
    """Fuera de su fichero, nadie las toca: ni un DROP ... CASCADE de otro build."""
    raiz = DIRECTORIO_SQL.parents[2]
    nombran = {
        ruta.relative_to(raiz).as_posix()
        for patron in ("**/*.sql", "**/*.py")
        for ruta in raiz.glob(patron)
        # En el SQL cuenta lo ejecutable: un comentario que cita el fichero
        # del dominio no toca las tablas.
        if "historial_estados" in (
            _sin_comentarios(ruta.read_text(encoding="utf-8"))
            if ruta.suffix == ".sql" else ruta.read_text(encoding="utf-8")
        )
    }
    assert "infrastructure/postgres/sql/compras/11_historial_estados.sql" in nombran
    assert nombran <= QUIEN_PUEDE_NOMBRARLAS, sorted(nombran - QUIEN_PUEDE_NOMBRARLAS)


def test_f067_r8_historial_la_cabecera_avisa_de_que_no_se_reconstruyen() -> None:
    texto = _texto(RUTA_HISTORIAL)
    cabecera = re.sub(r"\s+", " ", texto[: texto.index("CREATE TABLE")])
    assert "NO SE RECONSTRUYEN" in cabecera
    assert "NO SE PUEDE RECUPERAR" in cabecera


def test_f067_r1_historial_columnas_clave_e_indice_del_tramo_abierto() -> None:
    definicion = _definicion_tabla("compras.historial_estados")
    assert tuple(_columnas_de(definicion)) == COLUMNAS_HISTORIAL
    assert "PRIMARY KEY (documento_id, desde)" in definicion
    ejecutable = _compacto(_texto(RUTA_HISTORIAL))
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_hist_est_abierto ON "
        "compras.historial_estados (documento_id) WHERE hasta IS NULL" in ejecutable
    ), "sin el índice parcial, dos tramos abiertos duplicarían la vista"


def test_f067_r5_historial_el_check_lleva_los_motivos_del_dominio() -> None:
    definicion = _definicion_tabla("compras.historial_estados")
    check = re.search(
        r"motivo_cierre TEXT CHECK \(motivo_cierre IN \(([^)]*)\)\)", definicion
    )
    assert check, definicion
    assert tuple(re.findall(r"'([A-Z_]+)'", check.group(1))) == MOTIVOS_CIERRE


def test_f067_r8_historial_fotos_columnas_y_clave() -> None:
    definicion = _definicion_tabla("compras.historial_estados_fotos")
    assert tuple(_columnas_de(definicion)) == COLUMNAS_FOTOS
    assert "observado_en TIMESTAMPTZ PRIMARY KEY" in definicion
    assert "tomada_en TIMESTAMPTZ NOT NULL DEFAULT now()" in definicion


def test_f067_r8_historial_las_tablas_no_se_crean_sin_if_not_exists() -> None:
    ejecutable = _compacto(_texto(RUTA_HISTORIAL))
    assert not re.search(r"CREATE TABLE compras\.", ejecutable), (
        "un CREATE TABLE sin IF NOT EXISTS falla la segunda noche o, peor, "
        "invita a anteponerle un DROP"
    )


def test_f067_r1_foto_los_tipos_del_sql_son_los_del_dominio() -> None:
    tipos = re.findall(r"\btip IN \(([^)]*)\)", _bloque_do())
    assert len(tipos) == 2, "el recuento de la guarda y el INSERT filtran los tipos"
    for lista in tipos:
        assert tuple(int(x) for x in lista.split(",")) == TIPOS_HISTORIAL


def test_f067_r7_foto_sin_ingesta_nueva_no_escribe_nada() -> None:
    bloque = _bloque_do()
    assert "SELECT max(c._ingested_at) INTO v_obs FROM raw.con c;" in bloque
    assert (
        "SELECT max(f.observado_en) INTO v_ult FROM compras.historial_estados_fotos f;"
        in bloque
    )
    guarda = "IF v_obs IS NULL OR v_obs <= v_ult THEN"
    assert guarda in bloque
    tras = bloque[bloque.index(guarda) :]
    assert tras.index("RETURN;") < tras.index("END IF;") < tras.index("UPDATE")


def test_f067_r6_foto_la_guarda_del_98_es_la_del_dominio_y_para_el_build() -> None:
    bloque = _bloque_do()
    guarda = (
        f"IF v_abiertos > 0 AND v_actual < {UMBRAL_PRESENCIA} * v_abiertos "
        "THEN RAISE EXCEPTION"
    )
    assert guarda in bloque, bloque
    assert (
        "SELECT count(*) INTO v_abiertos FROM compras.historial_estados h "
        "WHERE h.hasta IS NULL;" in bloque
    )
    assert bloque.index(guarda) < bloque.index("UPDATE"), "la guarda va antes de escribir"


def test_f067_r2_foto_cierra_los_cambiados_por_ide_y_tipo_con_is_distinct_from() -> None:
    paso = _paso(_bloque_do(), f"SET hasta = v_obs, motivo_cierre = '{MOTIVOS_CIERRE[0]}'")
    assert "FROM raw.con c WHERE h.hasta IS NULL" in paso
    assert "AND c.ide = h.documento_id AND c.tip = h.tipo_documento_codigo" in paso
    assert "AND c.est IS DISTINCT FROM h.estado_id;" in paso


def test_f067_r5_foto_cierra_los_desaparecidos_por_ide_y_tipo() -> None:
    paso = _paso(_bloque_do(), f"SET hasta = v_obs, motivo_cierre = '{MOTIVOS_CIERRE[1]}'")
    assert "WHERE h.hasta IS NULL AND NOT EXISTS ( SELECT 1 FROM raw.con c" in paso
    assert "WHERE c.ide = h.documento_id AND c.tip = h.tipo_documento_codigo )" in paso


def test_f067_r4_foto_abre_tramos_con_linea_base_solo_en_la_primera() -> None:
    paso = _paso(_bloque_do(), "INSERT INTO compras.historial_estados (")
    assert "SELECT c.ide, c.tip, c.est, v_obs, NULL, v_ult, (v_ult IS NULL), NULL" in paso
    assert (
        "AND NOT EXISTS ( SELECT 1 FROM compras.historial_estados h "
        "WHERE h.documento_id = c.ide AND h.hasta IS NULL )" in paso
    ), "un documento con tramo abierto no abre otro"


def test_f067_r2_foto_los_pasos_van_en_el_orden_del_design() -> None:
    bloque = _bloque_do()
    orden = [
        bloque.index("motivo_cierre = 'CAMBIO'"),
        bloque.index("motivo_cierre = 'DESAPARECIDO'"),
        bloque.index("INSERT INTO compras.historial_estados ("),
        bloque.index("INSERT INTO compras.historial_estados_fotos ("),
    ]
    assert orden == sorted(orden), (
        "cerrar los cambiados, luego los desaparecidos, luego abrir y al final "
        "registrar la foto: en otro orden, un cambiado se cerraría como "
        "desaparecido o no se le abriría tramo"
    )


def test_f067_r8_foto_registra_los_contadores() -> None:
    bloque = _bloque_do()
    assert "GET DIAGNOSTICS v_cambios = ROW_COUNT;" in bloque
    assert "GET DIAGNOSTICS v_desaparecid = ROW_COUNT;" in bloque
    assert "GET DIAGNOSTICS v_insertados = ROW_COUNT;" in bloque
    assert (
        "VALUES (v_obs, (v_ult IS NULL), v_actual, v_cambios, "
        "v_insertados - v_cambios, v_desaparecid);" in bloque
    )


# ===========================================================================
# R9-R11 · `compras.v_estado_documentos`: RETIRADOS por F-132
# ===========================================================================
#
# La vista ya no la crea este fichero ni sale de la foto: desde F-132 la crea
# `13_estado_documentos.sql` a partir de `rac` (`compras.documento_procesos`).
# Sus tests viven en `tests/test_f132_sql.py`, que además fija que `11` ya no
# la crea y que lo ejecutable de la foto no ha cambiado ni una línea.


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
