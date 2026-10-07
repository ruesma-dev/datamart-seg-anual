# tests/test_f085_dominio.py
"""
F-085 · El oráculo del HISTORIAL DE PROCESOS de los documentos y del enlace
usuario -> empleado.

La regla vive en SQL (`sql/compras/12_documento_procesos.sql` y
`sql/personal/06_usuarios_sigrid.sql`) y NO se puede ejecutar en los tests: la
base es compartida con producción. Así que se escribe UNA vez en
`etl_sigrid/domain/documento_procesos.py` y se prueba aquí, caso a caso
(design §7 bis); `tests/test_f085_sql.py` comprueba que el SQL lleva **los
mismos** literales. Mismo patrón que F-067 y F-038.

El caso guía es la FR26/10025 (documento 2843469), medida en Sigrid el
2026-10-07: cuatro pasos, al segundo, los de la captura de Carmen Calle.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from etl_sigrid.domain.documento_procesos import (
    COLUMNAS_CREDENCIALES_USU,
    EMPRESA_PREFERENTE,
    FAMILIAS,
    Paso,
    PasoEncadenado,
    empleado_de_usuario,
    encadenar,
    hora_sigrid,
    normalizar_login,
)

# Los estados de la factura (tipo 15): REC 1, COM 2, CON 3, APJO 4, APRJG 5.
REC, COM, CON, APJO, APRJG = 1, 2, 3, 4, 5
FR26_10025 = 2843469


def _fr26_10025() -> list[Paso]:
    """Los cuatro pasos de la FR26/10025, desordenados a propósito."""
    return [
        Paso(2612564, FR26_10025, APJO, APRJG, date(2026, 10, 5), time(16, 58, 15)),
        Paso(2605997, FR26_10025, REC, COM, date(2026, 9, 28), time(16, 52, 11)),
        Paso(2612420, FR26_10025, CON, APJO, date(2026, 10, 5), time(16, 23, 32)),
        Paso(2605998, FR26_10025, COM, CON, date(2026, 9, 28), time(16, 52, 50)),
    ]


# ===========================================================================
# Las constantes: lo que el SQL y el YAML tienen que repetir
# ===========================================================================


def test_f085_r6_las_cuatro_familias_decididas() -> None:
    """D2 del humano (2026-10-07): factura, contrato, comparativo y obra."""
    assert FAMILIAS == {15: "FACTURA", 44: "CONTRATO", 46: "COMPARATIVO", 42: "OBRA"}


def test_f085_r3_las_seis_credenciales_de_usu() -> None:
    """Contraseña, firma digital, política de la clave, SID y certificado."""
    assert frozenset(
        {"cla", "fir", "feccla", "diascla", "sid", "cerid"}
    ) == COLUMNAS_CREDENCIALES_USU


def test_f085_r18_la_empresa_preferente_es_la_1() -> None:
    assert EMPRESA_PREFERENTE == 1


# ===========================================================================
# R10 · la hora de Sigrid
# ===========================================================================


@pytest.mark.parametrize(
    ("hhmmss", "esperada"),
    [
        (None, None),
        (0, None),                      # sin hora: 2 filas de 2,5 M
        (165211, time(16, 52, 11)),     # la de la FR26/10025
        (1, time(0, 0, 1)),             # el primer segundo del día
        (235959, time(23, 59, 59)),     # el último
        (240000, None),                 # fuera de rango
        (-5, None),
        (126000, None),                 # 60 minutos
        (125960, None),                 # 60 segundos
        (125959, time(12, 59, 59)),
    ],
)
def test_f085_r10_hora_sigrid(hhmmss: int | None, esperada: time | None) -> None:
    assert hora_sigrid(hhmmss) == esperada


def test_f085_r10_momento_es_fecha_mas_hora_y_null_si_falta_una() -> None:
    con_todo = Paso(1, 9, 1, 2, date(2026, 9, 28), time(16, 52, 11))
    sin_hora = Paso(2, 9, 1, 2, date(2026, 9, 28), None)
    sin_fecha = Paso(3, 9, 1, 2, None, time(16, 52, 11))

    assert con_todo.momento is not None
    assert con_todo.momento.isoformat() == "2026-09-28T16:52:11"
    assert sin_hora.momento is None
    assert sin_fecha.momento is None


# ===========================================================================
# R14 · el login
# ===========================================================================


@pytest.mark.parametrize(
    ("login", "esperado"),
    [
        (" Magomez ", "MAGOMEZ"),
        ("MAGOMEZ", "MAGOMEZ"),
        ("jmvargas", "JMVARGAS"),
        ("", None),
        ("   ", None),
        (None, None),
        ("\tjm", "\tJM"),   # BTRIM de Postgres quita solo espacios
    ],
)
def test_f085_r14_normalizar_login(login: str | None, esperado: str | None) -> None:
    assert normalizar_login(login) == esperado


# ===========================================================================
# R11-R13 · la cadena de pasos de cada documento
# ===========================================================================


def test_f085_r11_la_fr26_10025_sale_en_su_orden() -> None:
    cadena = encadenar(_fr26_10025())

    assert [e.paso.paso_id for e in cadena] == [2605997, 2605998, 2612420, 2612564]
    assert [e.orden for e in cadena] == [1, 2, 3, 4]
    assert [e.es_ultimo for e in cadena] == [False, False, False, True]


def test_f085_r12_la_fr26_10025_encaja_paso_a_paso() -> None:
    cadena = encadenar(_fr26_10025())

    assert [e.encaja_con_anterior for e in cadena] == [None, True, True, True]


def test_f085_r13_dias_entre_pasos_de_la_fr26_10025() -> None:
    """39 s, 6 d 23:30:42 y 34 min 43 s: 0,00 / 6,98 / 0,02."""
    cadena = encadenar(_fr26_10025())

    assert [e.dias_desde_anterior for e in cadena] == [
        None, Decimal("0.00"), Decimal("6.98"), Decimal("0.02"),
    ]


def test_f085_r13_redondeo_a_la_mitad_hacia_arriba_como_postgres() -> None:
    """12 h exactas son 0,5 días; 6 h 36 min son 0,275 -> 0,28 (no 0,27)."""
    pasos = [
        Paso(1, 7, 1, 2, date(2026, 1, 1), time(0, 0, 1)),
        Paso(2, 7, 2, 3, date(2026, 1, 1), time(12, 0, 1)),
        Paso(3, 7, 3, 4, date(2026, 1, 1), time(18, 36, 1)),
    ]

    cadena = encadenar(pasos)

    assert [e.dias_desde_anterior for e in cadena] == [
        None, Decimal("0.50"), Decimal("0.28"),
    ]


def test_f085_r12_un_salto_no_encaja() -> None:
    """Un cambio de estado fuera de un proceso: el origen no es el destino
    anterior (2,2 % de las facturas)."""
    pasos = [
        Paso(10, 5, REC, COM, date(2026, 1, 1), time(9, 0, 0)),
        Paso(11, 5, CON, APJO, date(2026, 1, 2), time(9, 0, 0)),
    ]

    cadena = encadenar(pasos)

    assert [e.encaja_con_anterior for e in cadena] == [None, False]


def test_f085_r11_empate_de_fecha_y_hora_desempata_por_paso_id() -> None:
    pasos = [
        Paso(31, 5, COM, CON, date(2026, 1, 1), time(9, 0, 0)),
        Paso(30, 5, REC, COM, date(2026, 1, 1), time(9, 0, 0)),
    ]

    cadena = encadenar(pasos)

    assert [e.paso.paso_id for e in cadena] == [30, 31]
    assert [e.dias_desde_anterior for e in cadena] == [None, Decimal("0.00")]


def test_f085_r11_un_paso_sin_fecha_va_el_ultimo_y_sin_dias() -> None:
    """`NULLS LAST`: el paso sin fecha cierra la cadena aunque su id sea menor."""
    pasos = [
        Paso(1, 5, CON, APJO, None, time(9, 0, 0)),
        Paso(2, 5, REC, COM, date(2026, 1, 1), time(9, 0, 0)),
        Paso(3, 5, COM, CON, date(2026, 1, 1), time(10, 0, 0)),
    ]

    cadena = encadenar(pasos)

    assert [e.paso.paso_id for e in cadena] == [2, 3, 1]
    assert cadena[-1].es_ultimo
    assert cadena[-1].dias_desde_anterior is None


def test_f085_r11_un_paso_sin_hora_va_detras_de_los_de_su_dia() -> None:
    pasos = [
        Paso(1, 5, REC, COM, date(2026, 1, 1), None),
        Paso(2, 5, COM, CON, date(2026, 1, 1), time(23, 0, 0)),
        Paso(3, 5, CON, APJO, date(2026, 1, 2), time(1, 0, 0)),
    ]

    cadena = encadenar(pasos)

    assert [e.paso.paso_id for e in cadena] == [2, 1, 3]
    assert [e.dias_desde_anterior for e in cadena] == [None, None, None]


def test_f085_r11_dos_documentos_intercalados_no_se_mezclan() -> None:
    pasos = [
        Paso(1, 200, REC, COM, date(2026, 1, 1), time(9, 0, 0)),
        Paso(2, 100, REC, COM, date(2026, 1, 1), time(9, 30, 0)),
        Paso(3, 200, COM, CON, date(2026, 1, 1), time(10, 0, 0)),
        Paso(4, 100, COM, CON, date(2026, 1, 3), time(9, 30, 0)),
        Paso(5, 200, CON, APJO, date(2026, 1, 1), time(11, 0, 0)),
    ]

    cadena = encadenar(pasos)

    por_doc = {
        doc: [(e.paso.paso_id, e.orden, e.es_ultimo) for e in cadena
              if e.paso.documento_id == doc]
        for doc in (100, 200)
    }
    assert por_doc[100] == [(2, 1, False), (4, 2, True)]
    assert por_doc[200] == [(1, 1, False), (3, 2, False), (5, 3, True)]
    assert [e.paso.documento_id for e in cadena] == [100, 100, 200, 200, 200]
    doc100 = [e for e in cadena if e.paso.documento_id == 100]
    assert doc100[1].dias_desde_anterior == Decimal("2.00")
    assert all(e.encaja_con_anterior is not False for e in cadena)


def test_f085_r11_un_documento_de_un_solo_paso() -> None:
    cadena = encadenar([Paso(1, 5, REC, COM, date(2026, 1, 1), time(9, 0, 0))])

    assert cadena == [
        PasoEncadenado(
            paso=Paso(1, 5, REC, COM, date(2026, 1, 1), time(9, 0, 0)),
            orden=1, es_ultimo=True, encaja_con_anterior=None,
            dias_desde_anterior=None,
        )
    ]


def test_f085_r11_sin_pasos_no_hay_cadena() -> None:
    assert encadenar([]) == []


def test_f085_r12_estados_nulos_no_encajan_con_un_destino_informado() -> None:
    pasos = [
        Paso(1, 5, REC, COM, date(2026, 1, 1), time(9, 0, 0)),
        Paso(2, 5, None, CON, date(2026, 1, 1), time(10, 0, 0)),
    ]

    assert encadenar(pasos)[1].encaja_con_anterior is False


# ===========================================================================
# R18 · el empleado de un usuario
# ===========================================================================


def test_f085_r18_una_sola_ficha_es_esa() -> None:
    assert empleado_de_usuario([(501, 18)]) == 501


def test_f085_r18_varias_fichas_se_queda_la_de_la_empresa_1() -> None:
    assert empleado_de_usuario([(501, 18), (502, 1), (503, 27)]) == 502


def test_f085_r18_varias_sin_la_empresa_1_no_elige() -> None:
    assert empleado_de_usuario([(501, 18), (503, 27)]) is None


def test_f085_r18_varias_con_dos_de_la_empresa_1_no_elige() -> None:
    assert empleado_de_usuario([(501, 1), (502, 1)]) is None


def test_f085_r18_ninguna_ficha_es_none() -> None:
    assert empleado_de_usuario([]) is None
