# tests/test_f132_sql.py
"""
F-132 · `compras.v_estado_documentos` desde `rac` (`13_estado_documentos.sql`)
y lo que deja de hacer `11_historial_estados.sql`, sobre su TEXTO.

Los SQL construyen objetos en un Postgres **compartido con producción**, así
que aquí no se ejecutan: se leen. Mismo criterio que `tests/test_f085_sql.py`.

LO QUE ESTE FICHERO DEFIENDE:

1. **La vista no lee la foto** (R1): la antigüedad sale del último paso de
   `compras.documento_procesos`, y el estado, de la cabecera (R3).
2. **Los literales del SQL son los del dominio** (R11,
   `domain/estado_documentos.py`): las familias, los estados iniciales y los
   tres orígenes.
3. **La foto de F-067 no cambia ni una línea ejecutable** (R10): `11` solo
   pierde la vista.
"""

from __future__ import annotations

import hashlib
import re
from functools import cache
from pathlib import Path

from etl_sigrid.domain.estado_documentos import (
    ESTADOS_INICIALES,
    FAMILIAS_ESTADO,
    ORIGENES_FECHA,
)

RAIZ = Path(__file__).resolve().parents[1]
DIRECTORIO_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RUTA_VISTA = DIRECTORIO_SQL / "compras" / "13_estado_documentos.sql"
RUTA_FOTO = DIRECTORIO_SQL / "compras" / "11_historial_estados.sql"

#: Lo que publica la vista, EN ORDEN (R2, D4 del humano).
COLUMNAS_VISTA = (
    "documento_id",
    "tipo_documento_codigo",
    "tipo_documento",
    "codigo_documento",
    "estado_id",
    "estado_codigo",
    "estado",
    "en_estado_desde",
    "origen_fecha",
    "dias_en_estado",
    "cambio_posterior_a",
    "paso_id",
    "proceso",
    "usuario",
    "nombre_usuario",
)

#: La huella de lo EJECUTABLE de `11_historial_estados.sql` (sin comentarios y
#: con los blancos plegados) SIN la vista, medida sobre 4d25fcb antes de F-132:
#: las dos tablas, el índice y el bloque `DO` de la foto. Si cambia, alguien
#: ha tocado la foto, y la Fase A no lo hace (R10).
HUELLA_FOTO = "dce136a1f998087e525dc3be77667194debb19ea7776dc920176d751111865f8"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


def _vista() -> str:
    return _compacto(_texto(RUTA_VISTA))


def _proyeccion() -> str:
    """La lista del SELECT final, la que da nombre y orden a las columnas."""
    vista = _vista()
    inicio = vista.rindex(") SELECT ") + len(") SELECT ")
    return vista[inicio : vista.rindex(" FROM ")]


def _elementos(proyeccion: str) -> list[str]:
    partes, actual, profundidad = [], [], 0
    for caracter in proyeccion:
        profundidad += (caracter == "(") - (caracter == ")")
        if caracter == "," and profundidad == 0:
            partes.append("".join(actual).strip())
            actual = []
        else:
            actual.append(caracter)
    partes.append("".join(actual).strip())
    return partes


def _alias(elemento: str) -> str:
    return (re.search(r"\bAS (\w+)$", elemento) or re.search(r"\.(\w+)$", elemento)).group(1)


# ===========================================================================
# R10 · el fichero, su sitio y lo que deja de hacer `11`
# ===========================================================================


def test_f132_r10_la_vista_se_tira_y_se_crea_en_13() -> None:
    texto = _texto(RUTA_VISTA)
    assert texto.startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/compras/13_estado_documentos.sql\n"
    )
    vista = _vista()
    assert vista.startswith(
        "DROP VIEW IF EXISTS compras.v_estado_documentos; "
        "CREATE VIEW compras.v_estado_documentos AS WITH documentos AS ("
    ), vista[:200]
    assert vista.endswith(";")
    assert vista.count(";") == 3, "DROP, CREATE VIEW y COMMENT: nada más"


def test_f132_r10_la_cabecera_dice_por_que_va_detras_de_12() -> None:
    cabecera = re.sub(r"\s+", " ", _texto(RUTA_VISTA).split("DROP VIEW", 1)[0])
    assert "12_documento_procesos.sql" in cabecera
    assert "CASCADE" in cabecera
    assert "historia NETA" in cabecera


def test_f132_r10_la_foto_ya_no_crea_la_vista() -> None:
    assert "v_estado_documentos" not in _compacto(_texto(RUTA_FOTO))


def test_f132_r10_la_foto_no_cambia_ni_una_linea_ejecutable() -> None:
    huella = hashlib.sha256(_compacto(_texto(RUTA_FOTO)).encode()).hexdigest()
    assert huella == HUELLA_FOTO


def test_f132_r10_la_cabecera_de_la_foto_la_presenta_como_respaldo() -> None:
    texto = _texto(RUTA_FOTO)
    cabecera = re.sub(r"\s+", " ", texto[: texto.index("CREATE TABLE")])
    assert "F-132" in cabecera
    assert "RESPALDO" in cabecera
    assert "La fecha en que un documento cambia de estado no está en Sigrid" not in cabecera
    assert "QUE NO EXISTE EN SIGRID" not in cabecera


# ===========================================================================
# R1, R3 · lee la cabecera y `rac`, nunca la foto
# ===========================================================================


def test_f132_r1_no_lee_la_foto_ni_raw() -> None:
    vista = _vista()
    assert "historial_estados" not in vista
    assert "raw." not in vista
    assert "tiemod" not in vista and "fn_sigrid_tiempo" not in vista


def test_f132_r1_una_fila_por_documento_de_las_tres_cabeceras() -> None:
    vista = _vista()
    documentos = vista[vista.index("WITH documentos AS (") : vista.index("), con_paso AS (")]
    assert documentos.count(" UNION ALL ") == 2
    for tabla in ("compras.contratos c", "compras.facturas f", "compras.comparativos m"):
        assert f"FROM {tabla}" in documentos, tabla
    # El último paso, uno por documento: LEFT JOIN por `es_ultimo` (no multiplica).
    assert (
        "FROM documentos d LEFT JOIN compras.documento_procesos u "
        "ON u.documento_id = d.documento_id AND u.es_ultimo" in vista
    )


def test_f132_r3_el_estado_es_el_de_la_cabecera() -> None:
    vista = _vista()
    documentos = vista[vista.index("WITH documentos AS (") : vista.index("), con_paso AS (")]
    assert (
        "c.contrato_id AS documento_id, c.codigo_contrato AS codigo_documento, "
        "c.estado_id, c.estado_codigo, c.estado, c.fecha AS fecha_alta "
        "FROM compras.contratos c" in documentos
    )
    assert (
        "f.factura_id, f.codigo_factura, f.estado_id, f.estado_codigo, f.estado, "
        "f.fecha_alta FROM compras.facturas f" in documentos
    )
    assert (
        "m.comparativo_id, m.codigo_comparativo, m.estado_id, m.estado_codigo, "
        "m.estado, m.fecha_alta FROM compras.comparativos m" in documentos
    )
    elementos = _elementos(_proyeccion())
    for columna in ("estado_id", "estado_codigo", "estado"):
        assert f"f.{columna}" in elementos, columna
    assert "estado_destino" not in _proyeccion()


# ===========================================================================
# R2 · las columnas, en su orden
# ===========================================================================


def test_f132_r2_publica_sus_columnas_en_orden() -> None:
    alias = tuple(_alias(e) for e in _elementos(_proyeccion()))
    assert alias == COLUMNAS_VISTA, alias


# ===========================================================================
# R4-R9, R11 · la regla, con los literales del dominio
# ===========================================================================


def test_f132_r11_las_familias_son_las_del_dominio() -> None:
    caso = " ".join(f"WHEN {t} THEN '{n}'" for t, n in FAMILIAS_ESTADO.items())
    assert (
        f"CASE f.tipo_documento_codigo {caso} END::TEXT AS tipo_documento"
        in _elementos(_proyeccion())
    )
    vista = _vista()
    for tipo in FAMILIAS_ESTADO:
        assert f"SELECT {tipo}" in vista, tipo


def test_f132_r11_los_estados_iniciales_son_los_del_dominio() -> None:
    parejas = ", ".join(
        f"({tipo}, {estado})"
        for tipo in sorted(ESTADOS_INICIALES)
        for estado in sorted(ESTADOS_INICIALES[tipo])
    )
    assert f"(d.tipo_documento_codigo, d.estado_id) IN ({parejas})" in _vista()


def test_f132_r11_los_origenes_son_los_del_dominio() -> None:
    literales = set(re.findall(r"'([A-Z_]+)'", _vista())) - set(FAMILIAS_ESTADO.values())
    assert literales == set(ORIGENES_FECHA), literales


def test_f132_r4_r5_r6_el_origen_en_el_orden_del_dominio() -> None:
    paso, alta, fuera = ORIGENES_FECHA
    assert (
        "CASE WHEN u.paso_id IS NOT NULL "
        "AND u.estado_destino_id IS NOT DISTINCT FROM d.estado_id "
        f"THEN '{paso}' WHEN u.paso_id IS NULL AND (d.tipo_documento_codigo, d.estado_id) IN "
        in _vista()
    )
    assert f"THEN '{alta}' ELSE '{fuera}' END AS origen_fecha" in _vista()


def test_f132_r4_el_momento_del_paso_o_su_dia_a_las_cero() -> None:
    assert "COALESCE(u.momento, u.fecha::TIMESTAMP) AS momento_ultimo" in _vista()


def test_f132_r4_r5_r8_en_estado_desde_paso_o_alta_y_si_no_nulo() -> None:
    assert (
        "CASE p.origen_fecha WHEN 'PASO' THEN p.momento_ultimo "
        "WHEN 'ALTA' THEN p.fecha_alta::TIMESTAMP END AS en_estado_desde" in _vista()
    )
    assert "f.en_estado_desde" in _elementos(_proyeccion())


def test_f132_r9_los_dias_se_cuentan_al_consultar_en_madrid() -> None:
    assert (
        "((now() AT TIME ZONE 'Europe/Madrid')::date - f.en_estado_desde::date) "
        "AS dias_en_estado" in _elementos(_proyeccion())
    )


def test_f132_r6_r7_la_cota_solo_fuera_de_proceso() -> None:
    assert (
        "CASE WHEN f.origen_fecha = 'FUERA_DE_PROCESO' THEN f.momento_ultimo END "
        "AS cambio_posterior_a" in _elementos(_proyeccion())
    )


def test_f132_r4_r6_el_paso_solo_se_publica_cuando_explica_el_estado() -> None:
    elementos = _elementos(_proyeccion())
    for columna in ("paso_id", "proceso", "usuario", "nombre_usuario"):
        assert (
            f"CASE WHEN f.origen_fecha = 'PASO' THEN f.{columna} END AS {columna}"
            in elementos
        ), columna


def test_f132_r11_el_sql_remite_a_su_oraculo_del_dominio() -> None:
    cabecera = _texto(RUTA_VISTA).split("DROP VIEW", 1)[0]
    assert "etl_sigrid/domain/estado_documentos.py" in cabecera
    assert "tests/test_f132_sql.py" in cabecera


# ===========================================================================
# R10 · el sub-paso de `build_compras`, el último
# ===========================================================================


def test_f132_r10_compras_acaba_en_la_vista_detras_de_documento_procesos() -> None:
    from etl_sigrid.application.steps import build_compras_step

    subs = build_compras_step.SUB_PASOS
    assert [s.sql_file for s in subs][-3:] == [
        "11_historial_estados.sql", "12_documento_procesos.sql", "13_estado_documentos.sql",
    ]
    ultimo = subs[-1]
    assert ultimo.name == "estado_documentos"
    # Es una vista: no se cuentan filas (contarlas la recorrería entera).
    assert ultimo.target_schema is None and ultimo.target_table is None


def test_f132_r10_el_docstring_del_paso_nombra_el_13() -> None:
    from etl_sigrid.application.steps import build_compras_step

    assert "13_estado_documentos.sql" in (build_compras_step.__doc__ or "")
