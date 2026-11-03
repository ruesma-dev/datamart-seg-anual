# tests/test_f153_sql.py
"""
F-153 · El estado de cada albarán, sobre el TEXTO del SQL.

`compras.albaranes` publica `estado_id`, `estado_codigo` y `estado` (R1-R4) y
`compras.v_estado_documentos` añade el tipo 14 (R5-R10). Mismo criterio que
`tests/test_f132_sql.py`: los SQL no se ejecutan, se leen.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from etl_sigrid.domain.estado_documentos import (
    ESTADO_FACTURADO_ALBARAN,
    ESTADOS_INICIALES,
    FAMILIAS_ESTADO,
    FAMILIAS_SIN_HISTORIAL,
    ORIGENES_FECHA,
    TIPO_ALBARAN,
    TIPOS_DOCUMENTO_ALBARAN,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
RUTA_DOCUMENTOS = DIR_SQL / "01_documentos.sql"
RUTA_VISTA = DIR_SQL / "13_estado_documentos.sql"
RUTA_SETUP = DIR_SQL / "00_setup.sql"


@cache
def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _compacto(texto: str) -> str:
    sin_comentarios = "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _bloque_albaranes() -> str:
    texto = _compacto(_crudo(RUTA_DOCUMENTOS))
    inicio = texto.index("CREATE TABLE compras.albaranes AS")
    return texto[inicio : texto.index(";", inicio) + 1]


def _vista() -> str:
    return _compacto(_crudo(RUTA_VISTA))


def _documentos() -> str:
    vista = _vista()
    return vista[vista.index("WITH documentos AS (") : vista.index("), con_paso AS (")]


# --- R1-R4 · la cabecera --------------------------------------------------------


def test_f153_r1_las_tres_columnas_al_final_y_en_orden() -> None:
    bloque = _bloque_albaranes()
    assert (
        "NULLIF(a.idefac, 0) AS factura_cabecera_id, con.est AS estado_id, "
        "est.codigo_estado AS estado_codigo, est.nombre_estado AS estado FROM raw.dca a"
        in bloque
    ), bloque[-1800:]


def test_f153_r2_la_traduccion_va_por_la_pareja_con_el_tipo_14() -> None:
    bloque = _bloque_albaranes()
    assert "LEFT JOIN LATERAL compras.fn_estado_documento(14, con.est) est ON TRUE" in bloque
    assert "conest" not in bloque


def test_f153_r2_el_lateral_va_tras_prv_con_y_antes_de_los_joins_de_f128() -> None:
    bloque = _bloque_albaranes()
    assert bloque.index("LEFT JOIN raw.con prv_con") < bloque.index("LEFT JOIN LATERAL")
    assert bloque.index("LEFT JOIN LATERAL") < bloque.index("LEFT JOIN raw.auxpag pag")


def test_f153_r3_el_grano_no_cambia() -> None:
    bloque = _bloque_albaranes()
    assert re.findall(r"(?<!LEFT )JOIN (\S+)", bloque) == ["raw.con"]
    # Sin `WHERE` externo: los únicos están dentro de `FILTER` del agregado.
    assert " WHERE " not in re.sub(r"FILTER \(WHERE [^)]*\)", "", bloque)


def test_f153_r4_indice_por_estado() -> None:
    assert (
        "CREATE INDEX idx_com_alb_est ON compras.albaranes (estado_id);"
        in _compacto(_crudo(RUTA_DOCUMENTOS))
    )


def test_f153_la_cabecera_del_sql_cuenta_f153() -> None:
    cabecera = _crudo(RUTA_DOCUMENTOS).split("-- CONTRATOS\n", 1)[0]
    assert "F-153" in cabecera


# --- R5, R6 · el bloque del tipo 14 ---------------------------------------------


def test_f153_r5_cuatro_bloques_y_el_ultimo_lee_la_cabecera_de_albaranes() -> None:
    documentos = _documentos()
    assert documentos.count(" UNION ALL ") == 3
    assert (
        "SELECT 14, a.albaran_id, a.codigo_albaran, a.estado_id, a.estado_codigo, a.estado, "
        "a.fecha, a.tipo_documento, a.fecha_facturacion FROM compras.albaranes a" in documentos
    )


def test_f153_r5_los_otros_tres_bloques_rellenan_las_dos_columnas_nuevas() -> None:
    documentos = _documentos()
    assert (
        "c.fecha AS fecha_alta, NULL::TEXT AS tipo_albaran, "
        "NULL::DATE AS fecha_facturacion FROM compras.contratos c" in documentos
    )
    assert "f.fecha_alta, NULL, NULL FROM compras.facturas f" in documentos
    assert "m.fecha_alta, NULL, NULL FROM compras.comparativos m" in documentos


def test_f153_r6_tipo_documento_del_14_es_el_de_la_cabecera() -> None:
    caso = " ".join(f"WHEN {t} THEN '{n}'" for t, n in FAMILIAS_ESTADO.items())
    assert (
        f"CASE f.tipo_documento_codigo {caso} WHEN 14 THEN f.tipo_albaran END::TEXT "
        "AS tipo_documento" in _vista()
    )


# --- R7, R8 · la regla ----------------------------------------------------------


def test_f153_r7_origen_fecha_en_el_orden_del_dominio() -> None:
    paso, facturacion, alta, sin_historial, fuera = ORIGENES_FECHA
    parejas = ", ".join(
        f"({t}, {e})" for t in sorted(ESTADOS_INICIALES) for e in sorted(ESTADOS_INICIALES[t])
    )
    familias = ", ".join(str(t) for t in sorted(FAMILIAS_SIN_HISTORIAL))
    assert (
        "CASE WHEN u.paso_id IS NOT NULL "
        f"AND u.estado_destino_id IS NOT DISTINCT FROM d.estado_id THEN '{paso}' "
        f"WHEN d.tipo_documento_codigo = {TIPO_ALBARAN} "
        f"AND d.estado_id = {ESTADO_FACTURADO_ALBARAN} "
        f"AND d.fecha_facturacion IS NOT NULL THEN '{facturacion}' "
        f"WHEN u.paso_id IS NULL AND (d.tipo_documento_codigo, d.estado_id) IN ({parejas}) "
        f"THEN '{alta}' "
        f"WHEN u.paso_id IS NULL AND d.tipo_documento_codigo IN ({familias}) "
        f"THEN '{sin_historial}' "
        f"ELSE '{fuera}' END AS origen_fecha" in _vista()
    ), _vista()


def test_f153_r7_facturacion_es_ese_dia_a_las_cero() -> None:
    assert (
        "CASE p.origen_fecha WHEN 'PASO' THEN p.momento_ultimo "
        "WHEN 'FACTURACION' THEN p.fecha_facturacion::TIMESTAMP "
        "WHEN 'ALTA' THEN p.fecha_alta::TIMESTAMP END AS en_estado_desde" in _vista()
    )


def test_f153_r7_cota_y_paso_siguen_sin_tocar_a_los_origenes_nuevos() -> None:
    vista = _vista()
    assert (
        "CASE WHEN f.origen_fecha = 'FUERA_DE_PROCESO' THEN f.momento_ultimo END "
        "AS cambio_posterior_a" in vista
    )
    assert "CASE WHEN f.origen_fecha = 'PASO' THEN f.paso_id END AS paso_id" in vista


def test_f153_r8_f133_encaja_sin_tocar_la_vista() -> None:
    assert (
        "FROM documentos d LEFT JOIN compras.documento_procesos u "
        "ON u.documento_id = d.documento_id AND u.es_ultimo" in _vista()
    )


# --- R9, R10 --------------------------------------------------------------------


def test_f153_r9_la_vista_sigue_sin_leer_raw() -> None:
    vista = _vista()
    assert "raw." not in vista and "rac." not in vista


def test_f153_r10_los_literales_de_la_vista_son_los_del_dominio() -> None:
    literales = set(re.findall(r"'([A-Z_]+)'", _vista())) - set(FAMILIAS_ESTADO.values())
    assert literales == set(ORIGENES_FECHA), literales


def test_f153_r10_los_tipos_del_14_son_los_de_fn_tipo_documento() -> None:
    texto = _crudo(RUTA_SETUP)
    funcion = texto[texto.index("compras.fn_tipo_documento(tip INT") :]
    funcion = funcion[: funcion.index("$$;")]
    en_sql = re.findall(r"WHEN tip = 14\b.*?THEN '([A-Z]+)'", funcion)
    assert tuple(en_sql) == TIPOS_DOCUMENTO_ALBARAN


def test_f153_las_tres_sentencias_y_la_cabecera_dice_el_tipo_14() -> None:
    assert _vista().count(";") == 3
    cabecera = _crudo(RUTA_VISTA).split("DROP VIEW", 1)[0]
    assert "F-153" in cabecera and "`compras.albaranes`" in cabecera
    for origen in ORIGENES_FECHA:
        assert origen in cabecera, origen


def test_f153_el_comment_nombra_los_albaranes_y_los_cinco_origenes() -> None:
    comment = _compacto(_crudo(RUTA_VISTA)).split("COMMENT ON VIEW", 1)[1]
    assert "albaran" in comment and "F-153" in comment
    for origen in ORIGENES_FECHA:
        assert origen in comment, origen
