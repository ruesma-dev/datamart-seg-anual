# tests/test_f132_contraste.py
"""
F-132 · El contraste foto diaria <-> `rac`: `python main.py contraste-estados`
(R12-R17).

El contraste decide si la foto de F-067 se puede retirar (Fase B, D7 del
humano), así que tiene que ser de fiar en las dos direcciones:

1. **No escribe** (R17): lee tablas PERSISTENTES que no se pueden recuperar, en
   un servidor compartido con producción. Cada SQL es un `SELECT`, y además la
   sesión va `READ ONLY`.
2. **Clasifica con el dominio** (R12-R14) y **sirve de puerta** (R15): una sola
   DISCREPANCIA sale con código 1.

Ningún test toca red ni BBDD: el cliente es un doble que devuelve filas con la
forma de las de verdad (las de la noche del 07-10 al 08-10).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

import pytest

from etl_sigrid.domain.historial_estados import MOTIVOS_CIERRE, TIPOS_HISTORIAL
from etl_sigrid.infrastructure.postgres import contraste_estados_sql as sql_contraste

#: Los SQL que ejecuta el comando, por nombre.
CONSULTAS = ("SQL_FOTOS", "SQL_CAMBIOS", "SQL_NO_VISTOS", "SQL_PASOS")

_ESCRITURA = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO)\b",
    re.IGNORECASE,
)


def _sin_comentarios(texto: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


# ===========================================================================
# R17 · ningún SQL del contraste escribe
# ===========================================================================


def test_f132_r17_el_modulo_declara_las_cuatro_consultas() -> None:
    assert tuple(getattr(sql_contraste, n) for n in CONSULTAS) == sql_contraste.CONSULTAS


@pytest.mark.parametrize("nombre", CONSULTAS)
def test_f132_r17_cada_consulta_es_un_select_de_una_sola_sentencia(nombre: str) -> None:
    texto = _compacto(getattr(sql_contraste, nombre))
    assert texto.startswith(("SELECT ", "WITH ")), texto[:40]
    assert ";" not in texto, "una sola sentencia y sin `;`"
    assert not _ESCRITURA.search(texto), _ESCRITURA.search(texto).group(0)


def test_f132_r17_el_contraste_lee_la_foto_y_rac_y_nada_mas() -> None:
    leidas = {
        tabla
        for nombre in CONSULTAS
        for tabla in re.findall(r"\b(?:FROM|JOIN) (\w+\.\w+)", _compacto(getattr(sql_contraste, nombre)))
    }
    assert leidas == {
        "compras.historial_estados",
        "compras.historial_estados_fotos",
        "compras.documento_procesos",
    }, leidas


# ===========================================================================
# R12-R14 · lo que lee cada consulta, con los literales del dominio
# ===========================================================================


def test_f132_r12_los_cambios_son_los_tramos_cerrados_por_cambio_con_su_ventana() -> None:
    texto = _compacto(sql_contraste.SQL_CAMBIOS)
    cambio = MOTIVOS_CIERRE[0]
    assert f"WHERE v.motivo_cierre = '{cambio}'" in texto
    # El tramo cerrado se une al que abre LA MISMA foto: su estado es el nuevo.
    assert "JOIN compras.historial_estados n ON n.documento_id = v.documento_id AND n.desde = v.hasta" in texto
    assert (
        "SELECT n.documento_id, n.tipo_documento_codigo, n.estado_id AS estado_nuevo, "
        "n.observado_antes AS inicio, n.desde AS fin " in texto
    )


def test_f132_r14_los_no_vistos_son_de_contrato_y_factura_y_sin_cambio_en_esa_foto() -> None:
    texto = _compacto(sql_contraste.SQL_NO_VISTOS)
    tipos = ", ".join(str(t) for t in TIPOS_HISTORIAL)
    assert f"p.tipo_documento_codigo IN ({tipos})" in texto
    assert f"x.hasta = v.fin AND x.motivo_cierre = '{MOTIVOS_CIERRE[0]}'" in texto
    assert "NOT EXISTS" in texto
    # El estado que la foto les vio en `fin` y si esa foto les abrió tramo.
    assert "h.desde <= v.fin AND (h.hasta IS NULL OR h.hasta > v.fin)" in texto
    assert "(h.desde = v.fin AND NOT h.es_linea_base) AS abierto_en_la_foto" in texto
    # La ventana es (foto anterior, foto], y la línea base no tiene ventana.
    assert "LAG(f.observado_en) OVER (ORDER BY f.observado_en) AS inicio" in texto
    assert "WHERE v.inicio IS NOT NULL" in texto


def test_f132_r13_los_pasos_se_comparan_en_utc() -> None:
    """`rac` guarda hora de Madrid sin zona y las fotos son TIMESTAMPTZ."""
    assert "(p.momento AT TIME ZONE 'Europe/Madrid') AS momento_utc" in _compacto(
        sql_contraste.SQL_PASOS
    )
    no_vistos = _compacto(sql_contraste.SQL_NO_VISTOS)
    assert "(p.momento AT TIME ZONE 'Europe/Madrid') > v.inicio" in no_vistos
    assert "(p.momento AT TIME ZONE 'Europe/Madrid') <= v.fin" in no_vistos


def test_f132_r12_los_pasos_de_una_lista_de_documentos_en_su_orden() -> None:
    texto = _compacto(sql_contraste.SQL_PASOS)
    assert "WHERE p.documento_id = ANY(%s)" in texto
    assert texto.endswith("ORDER BY p.documento_id, p.orden")
    assert texto.startswith("SELECT p.documento_id, p.orden, p.estado_destino_id, ")


def test_f132_r16_las_fotos_en_orden_con_su_linea_base() -> None:
    texto = _compacto(sql_contraste.SQL_FOTOS)
    assert texto == (
        "SELECT f.observado_en, f.es_linea_base, f.n_cambios "
        "FROM compras.historial_estados_fotos f ORDER BY f.observado_en"
    )


# ===========================================================================
# R12, R15-R17 · el comando, con un cliente falso
# ===========================================================================

CEST = timezone(timedelta(hours=2))
LINEA_BASE = datetime(2026, 10, 7, 0, 3, 0, tzinfo=UTC)
NOCHE_08 = datetime(2026, 10, 8, 0, 3, 1, 945572, tzinfo=UTC)
NOCHE_09 = datetime(2026, 10, 9, 0, 3, 2, tzinfo=UTC)


def _madrid(*partes: int) -> datetime:
    return datetime(*partes, tzinfo=CEST).astimezone(UTC)


#: Cambios reales de la noche del 07-10 al 08-10 (uno de cada clase medida) y
#: uno CONSTRUIDO como discrepancia: el 9999001, que la foto ve pasar a 7 y
#: cuyo paso a 7 es de DESPUÉS de la foto.
CAMBIOS = [
    (2808958, 15, 6, LINEA_BASE, NOCHE_08),   # PASO
    (2844510, 44, 3, LINEA_BASE, NOCHE_08),   # PASO
    (2831855, 15, 5, LINEA_BASE, NOCHE_08),   # DESHECHO
    (2833636, 44, 5, LINEA_BASE, NOCHE_08),   # DESHECHO
    (2775496, 44, 1, LINEA_BASE, NOCHE_08),   # VUELTA_AL_INICIAL
]
DISCREPANTE = (9999001, 44, 7, LINEA_BASE, NOCHE_08)
NO_VISTOS = [
    (2849508, 15, 4, True, NOCHE_08),   # ALTA
    (2652534, 44, 7, False, NOCHE_08),  # IDA_Y_VUELTA
]
PASOS = [
    (2652534, 1, 3, _madrid(2026, 10, 7, 8, 56, 28)),
    (2652534, 2, 5, _madrid(2026, 10, 7, 8, 56, 33)),
    (2652534, 3, 6, _madrid(2026, 10, 7, 8, 56, 41)),
    (2652534, 4, 7, _madrid(2026, 10, 7, 8, 56, 48)),
    (2808958, 1, 5, _madrid(2026, 8, 3, 17, 37, 8)),
    (2808958, 2, 6, _madrid(2026, 10, 7, 12, 43, 10)),
    (2831855, 1, 4, _madrid(2026, 9, 8, 13, 15, 22)),
    (2831855, 2, 5, _madrid(2026, 9, 8, 13, 17, 59)),
    (2833636, 1, 3, _madrid(2026, 9, 10, 13, 18, 30)),
    (2833636, 2, 5, _madrid(2026, 9, 10, 13, 18, 35)),
    (2844510, 1, 3, _madrid(2026, 10, 7, 12, 11, 10)),
    (2849508, 1, 2, _madrid(2026, 10, 7, 8, 7, 16)),
    (2849508, 2, 4, _madrid(2026, 10, 7, 8, 42, 18)),
    (9999001, 1, 3, _madrid(2026, 10, 1, 9, 0, 0)),
    (9999001, 2, 7, _madrid(2026, 10, 8, 10, 0, 0)),
]
FOTOS = [(LINEA_BASE, True, 0), (NOCHE_08, False, 6), (NOCHE_09, False, 0)]


class _PgContraste:
    """Doble de `PostgresClient`: solo `filas_solo_lectura`, como el comando."""

    def __init__(self, fotos, cambios, no_vistos, pasos) -> None:
        self._por_sql = {
            sql_contraste.SQL_FOTOS: fotos,
            sql_contraste.SQL_CAMBIOS: cambios,
            sql_contraste.SQL_NO_VISTOS: no_vistos,
        }
        self._pasos = pasos
        self.llamadas: list[tuple[str, int, tuple | None]] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int, params=None) -> list:
        self.llamadas.append((sql_text, timeout_s, params))
        if sql_text == sql_contraste.SQL_PASOS:
            (ids,) = params
            return [p for p in self._pasos if p[0] in ids]
        return self._por_sql[sql_text]


def _lanzar(monkeypatch: pytest.MonkeyPatch, pg: _PgContraste, *argumentos: str):
    from click.testing import CliRunner

    import main

    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    return CliRunner().invoke(main.cli, ["contraste-estados", *argumentos])


def _filas_de_la_tabla(salida: str) -> set[tuple[str, ...]]:
    return {
        tuple(c.strip() for c in linea.split("|"))
        for linea in salida.splitlines()
        if linea.count("|") == 4 and not linea.startswith("observado_en")
    }


def test_f132_r15_sin_discrepancias_tabla_por_noche_tipo_y_clase_y_sale_con_cero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgContraste(FOTOS, CAMBIOS, NO_VISTOS, PASOS)

    resultado = _lanzar(monkeypatch, pg)

    assert resultado.exit_code == 0, resultado.output
    noche = "2026-10-08 00:03:01"
    assert _filas_de_la_tabla(resultado.output) == {
        (noche, "CONTRATO", "CAMBIO", "PASO", "1"),
        (noche, "CONTRATO", "CAMBIO", "DESHECHO", "1"),
        (noche, "CONTRATO", "CAMBIO", "VUELTA_AL_INICIAL", "1"),
        (noche, "CONTRATO", "NO VISTO", "IDA_Y_VUELTA", "1"),
        (noche, "FACTURA", "CAMBIO", "PASO", "1"),
        (noche, "FACTURA", "CAMBIO", "DESHECHO", "1"),
        (noche, "FACTURA", "NO VISTO", "ALTA", "1"),
    }
    assert "2026-10-09 00:03:02 | sin cambios ni pasos que contrastar" in resultado.output
    assert "Resultado: 0 DISCREPANCIA" in resultado.output


def test_f132_r15_una_discrepancia_da_su_id_y_sale_con_uno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgContraste(FOTOS, [*CAMBIOS, DISCREPANTE], NO_VISTOS, PASOS)

    resultado = _lanzar(monkeypatch, pg)

    assert resultado.exit_code == 1, resultado.output
    assert ("2026-10-08 00:03:01", "CONTRATO", "CAMBIO", "DISCREPANCIA", "1") in (
        _filas_de_la_tabla(resultado.output)
    )
    assert "DISCREPANCIA 2026-10-08 00:03:01: 9999001" in resultado.output
    assert "Resultado: 1 DISCREPANCIA" in resultado.output


def test_f132_r15_como_mucho_50_ids_de_discrepancia_por_noche(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sin_pasos = [(9_000_000 + i, 44, 7, LINEA_BASE, NOCHE_08) for i in range(60)]
    pg = _PgContraste(FOTOS, sin_pasos, [], [])

    resultado = _lanzar(monkeypatch, pg)

    assert resultado.exit_code == 1
    linea = next(
        x for x in resultado.output.splitlines() if x.startswith("DISCREPANCIA 2026-10-08")
    )
    ids = linea.split(": ", 1)[1].split(" (")[0].split(", ")
    assert ids == [str(9_000_000 + i) for i in range(50)]
    assert linea.endswith("(y 10 más)")
    assert "Resultado: 60 DISCREPANCIA" in resultado.output


def test_f132_r16_sin_fotos_despues_de_la_linea_base_no_clasifica_y_sale_con_cero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgContraste([(LINEA_BASE, True, 0)], [DISCREPANTE], [], PASOS)

    resultado = _lanzar(monkeypatch, pg)

    assert resultado.exit_code == 0, resultado.output
    assert "ninguna foto posterior a la línea base" in resultado.output
    assert [sql for sql, _, _ in pg.llamadas] == [sql_contraste.SQL_FOTOS]


def test_f132_r16_sin_ninguna_foto_tampoco(monkeypatch: pytest.MonkeyPatch) -> None:
    resultado = _lanzar(monkeypatch, _PgContraste([], [], [], []))

    assert resultado.exit_code == 0, resultado.output
    assert "ninguna foto posterior a la línea base" in resultado.output


def test_f132_r17_todas_las_lecturas_van_por_la_sesion_de_solo_lectura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgContraste(FOTOS, CAMBIOS, NO_VISTOS, PASOS)

    _lanzar(monkeypatch, pg, "--timeout", "77")

    assert [sql for sql, _, _ in pg.llamadas] == list(sql_contraste.CONSULTAS)
    assert {t for _, t, _ in pg.llamadas} == {77}
    # Los pasos se piden UNA vez, de todos los documentos a la vez, ordenados.
    ids = sorted({fila[0] for fila in CAMBIOS} | {fila[0] for fila in NO_VISTOS})
    assert pg.llamadas[-1][2] == (ids,)
    assert all(params is None for _, _, params in pg.llamadas[:-1])


def test_f132_r12_sin_documentos_que_contrastar_no_pide_pasos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgContraste(FOTOS, [], [], PASOS)

    resultado = _lanzar(monkeypatch, pg)

    assert resultado.exit_code == 0, resultado.output
    assert sql_contraste.SQL_PASOS not in [sql for sql, _, _ in pg.llamadas]
    assert "2026-10-08 00:03:01 | sin cambios ni pasos que contrastar" in resultado.output


def test_f132_r12_un_paso_sin_hora_llega_al_dominio_sin_momento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El único paso sin hora de `rac`: sin momento no cae en ninguna ventana."""
    cambio = [(2844510, 44, 3, LINEA_BASE, NOCHE_08)]
    pasos = [(2844510, 1, 3, None)]

    resultado = _lanzar(monkeypatch, _PgContraste(FOTOS, cambio, [], pasos))

    assert resultado.exit_code == 1
    assert "DISCREPANCIA 2026-10-08 00:03:01: 2844510" in resultado.output


# ===========================================================================
# R17 · `filas_solo_lectura` acepta parámetros sin dejar de ser READ ONLY
# ===========================================================================


class _Cursor:
    def __init__(self) -> None:
        self.ejecutadas: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, *args):
        self.ejecutadas.append((sql, *args))

    def fetchall(self):
        return [(1,)]


class _Conexion:
    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise AssertionError("no debía fallar")


class _Cliente:
    def __init__(self, conexion) -> None:
        self._conexion = conexion

    def connection(self):
        return self._conexion


def test_f132_r17_los_parametros_viajan_tras_el_read_only() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    cursor = _Cursor()
    filas = PostgresClient.filas_solo_lectura(
        _Cliente(_Conexion(cursor)), sql_contraste.SQL_PASOS, 30, ([1, 2],)
    )

    assert filas == [(1,)]
    assert cursor.ejecutadas[0] == ("SET LOCAL statement_timeout = '30s'",)
    assert cursor.ejecutadas[1] == ("SET LOCAL transaction_read_only = on",)
    assert cursor.ejecutadas[2] == (sql_contraste.SQL_PASOS, ([1, 2],))


def test_f132_r17_sin_parametros_la_llamada_es_la_de_siempre() -> None:
    """Sin `params` el `execute` va SIN segundo argumento: un `%` literal de los
    SQL de diagnóstico de siempre no se interpreta como marcador."""
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    cursor = _Cursor()
    PostgresClient.filas_solo_lectura(_Cliente(_Conexion(cursor)), "SELECT '50%'", 30)

    assert cursor.ejecutadas[2] == ("SELECT '50%'",)


# ===========================================================================
# R15 · el informe: orden fijo, para que dos ejecuciones se puedan comparar
# ===========================================================================


def test_f132_r15_el_informe_va_por_noche_tipo_grupo_y_clase_en_ese_orden() -> None:
    from etl_sigrid.domain.estado_documentos import Contrastado, formatear_contraste

    noche = NOCHE_08.astimezone(CEST)  # la zona de la sesión no cambia la etiqueta UTC
    contrastados = [
        Contrastado(NOCHE_08, 15, "NO VISTO", "ALTA", 3),
        Contrastado(NOCHE_08, 44, "CAMBIO", "DISCREPANCIA", 9),
        Contrastado(NOCHE_08, 44, "NO VISTO", "IDA_Y_VUELTA", 8),
        Contrastado(noche, 44, "CAMBIO", "PASO", 7),
        Contrastado(NOCHE_08, 15, "CAMBIO", "DESHECHO", 2),
        Contrastado(NOCHE_08, 15, "CAMBIO", "PASO", 1),
        Contrastado(NOCHE_08, 15, "CAMBIO", "PASO", 4),
        Contrastado(NOCHE_08, 42, "CAMBIO", "PASO", 5),
        Contrastado(NOCHE_09, 44, "NO VISTO", "DISCREPANCIA", 6),
    ]

    texto = formatear_contraste(contrastados, [NOCHE_09, NOCHE_08])

    assert texto.splitlines() == [
        "observado_en (UTC)  | tipo        | grupo    | clase             | documentos",
        "2026-10-08 00:03:01 | 42          | CAMBIO   | PASO              | 1",
        "2026-10-08 00:03:01 | CONTRATO    | CAMBIO   | PASO              | 1",
        "2026-10-08 00:03:01 | CONTRATO    | CAMBIO   | DISCREPANCIA      | 1",
        "2026-10-08 00:03:01 | CONTRATO    | NO VISTO | IDA_Y_VUELTA      | 1",
        "2026-10-08 00:03:01 | FACTURA     | CAMBIO   | PASO              | 2",
        "2026-10-08 00:03:01 | FACTURA     | CAMBIO   | DESHECHO          | 1",
        "2026-10-08 00:03:01 | FACTURA     | NO VISTO | ALTA              | 1",
        "2026-10-09 00:03:02 | CONTRATO    | NO VISTO | DISCREPANCIA      | 1",
        "DISCREPANCIA 2026-10-08 00:03:01: 9",
        "DISCREPANCIA 2026-10-09 00:03:02: 6",
        "Resultado: 2 DISCREPANCIA sin explicar.",
    ]


def test_f132_r15_justo_50_discrepancias_no_dicen_que_haya_mas() -> None:
    from etl_sigrid.domain.estado_documentos import Contrastado, formatear_contraste

    contrastados = [
        Contrastado(NOCHE_08, 44, "CAMBIO", "DISCREPANCIA", 100 - i) for i in range(50)
    ]

    linea = formatear_contraste(contrastados, [NOCHE_08]).splitlines()[-2]

    assert linea.startswith("DISCREPANCIA 2026-10-08 00:03:01: 51, 52, ")
    assert linea.endswith(", 100")
