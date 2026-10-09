# tests/test_f132_retirada.py
"""
F-132 · Fase B, rama BORRAR: la foto diaria de estados de F-067 se retira
(R25, R26). Decisión del humano del 2026-10-09 (D6 acortada, D7 = BORRAR).

LO QUE ESTE FICHERO DEFIENDE:

1. **Nadie vuelve a crear la foto** (R25): `build_compras` ya no tiene el
   sub-paso `11`, el fichero no existe y ningún SQL ni código de `etl_sigrid/`
   nombra sus tablas, salvo el SQL que las BORRA. Si alguien las recreara, la
   nocturna volvería a escribir dos tablas que el diccionario ya no describe.
2. **La época de Delphi sobrevive** (R25): `fn_sigrid_tiempo` la sigue usando,
   y ahora vive en `domain/fecha_delphi.py`.
3. **`retirar-foto-estados` solo borra con `--confirmar`** (R26), las dos
   tablas en UNA transacción y sin `CASCADE`; sin él lee (READ ONLY) y dice qué
   borraría.

Ningún test toca red ni BBDD: el SQL se lee como texto y el comando se ejecuta
contra un doble de `main._get_pg`.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import date, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

import main

RAIZ = Path(__file__).resolve().parents[1]
DIR_ETL = RAIZ / "etl_sigrid"
DIR_SQL_COMPRAS = DIR_ETL / "infrastructure" / "postgres" / "sql" / "compras"
TABLAS_FOTO = ("historial_estados", "historial_estados_fotos")


# ===========================================================================
# R25 · el build deja de tomar la foto
# ===========================================================================


def test_f132_r25_el_fichero_de_la_foto_ya_no_existe() -> None:
    assert not (DIR_SQL_COMPRAS / "11_historial_estados.sql").exists()


def test_f132_r25_build_compras_ya_no_tiene_el_sub_paso_de_la_foto() -> None:
    from etl_sigrid.application.steps.build_compras_step import SUB_PASOS

    assert "historial_estados" not in [s.name for s in SUB_PASOS]
    assert [s.sql_file for s in SUB_PASOS][-3:] == [
        "10_necesidades.sql", "12_documento_procesos.sql", "13_estado_documentos.sql",
    ]
    assert all(s.target_table not in TABLAS_FOTO for s in SUB_PASOS)


def test_f132_r25_la_epoca_de_delphi_sigue_en_el_dominio() -> None:
    from etl_sigrid.domain.fecha_delphi import EPOCA_DELPHI, fecha_delphi

    assert EPOCA_DELPHI == date(1899, 12, 30)
    # Medido en Sigrid: 46300,537627 es el 2026-10-05 a las 12:54:10.
    valor = fecha_delphi(46300.537627)
    assert valor is not None
    assert valor.replace(microsecond=0) == datetime(2026, 10, 5, 12, 54, 10)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (1.0, datetime(1899, 12, 31)),
        (0.5, datetime(1899, 12, 30, 12, 0)),
        (2.25, datetime(1900, 1, 1, 6, 0)),
    ],
)
def test_f132_r25_fecha_delphi_la_hora_va_en_la_parte_decimal(
    valor: float, esperado: datetime
) -> None:
    from etl_sigrid.domain.fecha_delphi import fecha_delphi

    assert fecha_delphi(valor) == esperado


@pytest.mark.parametrize("valor", [None, 0, 0.0, -1.0])
def test_f132_r25_fecha_delphi_cero_nulo_o_negativo_no_es_una_fecha(
    valor: float | None,
) -> None:
    from etl_sigrid.domain.fecha_delphi import fecha_delphi

    assert fecha_delphi(valor) is None


def test_f132_r25_fecha_delphi_no_importa_infraestructura_ni_configuracion() -> None:
    texto = (DIR_ETL / "domain" / "fecha_delphi.py").read_text(encoding="utf-8")
    assert "infrastructure" not in texto and "config" not in texto.split('"""', 2)[2]
