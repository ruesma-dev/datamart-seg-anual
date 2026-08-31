# tests/test_f052_comparar_huellas.py
"""
F-052 · Los dos comandos de la revisión de datos ampliada (T30, R11).

`huella-obras` pasa de dos orígenes a **cuatro** y `comparar-huellas` aprende a
reconocer las huellas nuevas por su cabecera. Es lo que hace ejecutable el
acuerdo del 2026-08-31: el humano eximió la campaña de mutación y puso a cambio
**cuatro** huellas antes/después sobre el mismo `raw`, con **tolerancia cero**
fuera de las seis obras afectadas.

Lo que hay que poder hacer, y que estos tests fijan:

    python main.py huella-obras --desde dimension --out huella_f052_dim_antes.csv
    python main.py huella-obras --desde cierre    --out huella_f052_cie_antes.csv
    ... (se reconstruye la base) ...
    python main.py comparar-huellas huella_f052_dim_antes.csv huella_f052_dim_despues.csv \\
        --obras-esperadas 0599,0613,0618,0630,0565,0686

**El paso viejo no puede romperse**: las huellas de F-042 se comparan igual que
antes, y hay un test que lo comprueba en el mismo fichero. Cambiar el comando
para las nuevas y estropearlo para las que ya se usaban sería el peor resultado
posible de esta tarea.

Sin red ni BBDD: el cliente es un doble que sirve filas enlatadas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.huella import FilaHuella
from etl_sigrid.domain.huella_ampliada import FORMATO_CIERRE, FORMATO_DIMENSION
from etl_sigrid.infrastructure.postgres.huella_ampliada import (
    construir_huella_ampliada,
    escribir_csv_ampliada,
)
from etl_sigrid.infrastructure.postgres.huella_obras import escribir_csv

DIM_0599 = (1442383, "0599", 1440, 3, 7, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
DIM_0613 = (1500000, "0613", 3210, 4, 5, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
DIM_0664 = (1600000, "0664", 900, 3, 6, "cccccccccccccccccccccccccccccccc")

CIE_0599 = (
    1442383, "0599", date(2022, 12, 1), "DIRECTOS", 1,
    Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"),
)


class PgFalso:
    def __init__(self, filas):
        self._filas = list(filas)
        self.consultas: list[str] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.consultas.append(sql_text)
        return self._filas

    def __getattr__(self, nombre: str):
        raise AssertionError(f"la huella es de solo lectura y ha llamado a pg.{nombre}")


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    def _con(pg):
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        return CliRunner()

    return _con


def _csv_dimension(path, filas):
    escribir_csv_ampliada(
        FORMATO_DIMENSION,
        construir_huella_ampliada(PgFalso(filas), FORMATO_DIMENSION),
        path,
    )


# ---------------------------------------------------------------------------
# `huella-obras` con los dos orígenes nuevos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("origen", ("stg", "mart", "dimension", "cierre"))
def test_f052_t30_huella_obras_admite_los_cuatro_origenes(origen: str):
    """Los cuatro de T14. Si `--desde` no los aceptara, la captura del ANTES no
    se podría hacer y las huellas 3 y 4 serían código que nadie ejecuta."""
    resultado = CliRunner().invoke(main.cli, ["huella-obras", "--help"])

    assert resultado.exit_code == 0
    assert origen in resultado.output


def test_f052_t30_la_huella_de_dimension_se_escribe_a_csv(cli, tmp_path):
    destino = tmp_path / "huella_dim.csv"
    pg = PgFalso([DIM_0599, DIM_0613])

    resultado = cli(pg).invoke(
        main.cli, ["huella-obras", "--desde", "dimension", "--out", str(destino)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert destino.exists()
    assert "stg.partidas" in pg.consultas[0]
    cabecera = destino.read_text(encoding="utf-8-sig").splitlines()[0]
    assert cabecera.split(";") == list(FORMATO_DIMENSION.cabecera)


def test_f052_t30_la_huella_de_cierre_se_escribe_a_csv(cli, tmp_path):
    destino = tmp_path / "huella_cie.csv"
    pg = PgFalso([CIE_0599])

    resultado = cli(pg).invoke(
        main.cli, ["huella-obras", "--desde", "cierre", "--out", str(destino)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "cierre.fact_cierre_mensual" in pg.consultas[0]
    cabecera = destino.read_text(encoding="utf-8-sig").splitlines()[0]
    assert cabecera.split(";") == list(FORMATO_CIERRE.cabecera)


def test_f052_t30_propuesta_no_tiene_sentido_con_las_huellas_nuevas(cli, tmp_path):
    """`--propuesta` reejecuta la rama de reales de `08_plan_mensual.sql`. Sobre
    `stg.partidas` o sobre `cierre` no significa nada, y aceptarlo en silencio
    produciría una huella que no es la que se cree."""
    resultado = cli(PgFalso([DIM_0599])).invoke(
        main.cli,
        [
            "huella-obras",
            "--desde", "dimension",
            "--propuesta",
            "--out", str(tmp_path / "x.csv"),
        ],
    )

    assert resultado.exit_code != 0
    assert "propuesta" in resultado.output.lower()


# ---------------------------------------------------------------------------
# `comparar-huellas` con tolerancia CERO
# ---------------------------------------------------------------------------


def test_f052_t30_dos_huellas_de_dimension_iguales_salen_0(tmp_path):
    antes, despues = tmp_path / "a.csv", tmp_path / "d.csv"
    _csv_dimension(antes, [DIM_0599, DIM_0664])
    _csv_dimension(despues, [DIM_0599, DIM_0664])

    resultado = CliRunner().invoke(
        main.cli,
        ["comparar-huellas", str(antes), str(despues), "--obras-esperadas", "0599"],
    )

    assert resultado.exit_code == 0, resultado.output
    assert "dimension" in resultado.output


def test_f052_t30_una_obra_ajena_que_se_mueve_tumba_la_comparacion(tmp_path):
    """**La prueba que decide.** Una sola celda de la 0664 y la feature se
    detiene: no hay umbral ni tolerancia."""
    movida = (1600000, "0664", 901, 3, 6, "cccccccccccccccccccccccccccccccc")
    antes, despues = tmp_path / "a.csv", tmp_path / "d.csv"
    _csv_dimension(antes, [DIM_0599, DIM_0664])
    _csv_dimension(despues, [DIM_0599, movida])

    resultado = CliRunner().invoke(
        main.cli,
        ["comparar-huellas", str(antes), str(despues), "--obras-esperadas", "0599"],
    )

    assert resultado.exit_code != 0
    assert "0664" in resultado.output
    assert "CERO" in resultado.output


def test_f052_t30_la_0599_moviendose_no_tumba_nada(tmp_path):
    movida = (1442383, "0599", 1440, 3, 7, "DISTINTO-DISTINTO-DISTINTO-DIST")
    antes, despues = tmp_path / "a.csv", tmp_path / "d.csv"
    _csv_dimension(antes, [DIM_0599, DIM_0664])
    _csv_dimension(despues, [movida, DIM_0664])

    resultado = CliRunner().invoke(
        main.cli,
        [
            "comparar-huellas", str(antes), str(despues),
            "--obras-esperadas", "0599,0613,0618,0630,0565,0686",
        ],
    )

    assert resultado.exit_code == 0, resultado.output
    assert "0599" in resultado.output


def test_f052_t30_mezclar_dos_formatos_distintos_se_rechaza(tmp_path):
    """Comparar una huella de dimensión contra una de cierre daría cientos de
    diferencias falsas y no significaría nada."""
    dimension, cierre = tmp_path / "dim.csv", tmp_path / "cie.csv"
    _csv_dimension(dimension, [DIM_0599])
    escribir_csv_ampliada(
        FORMATO_CIERRE,
        construir_huella_ampliada(PgFalso([CIE_0599]), FORMATO_CIERRE),
        cierre,
    )

    resultado = CliRunner().invoke(
        main.cli, ["comparar-huellas", str(dimension), str(cierre)]
    )

    assert resultado.exit_code != 0
    assert "formato" in resultado.output.lower()


def test_f052_t30_la_comparacion_vieja_de_f042_sigue_funcionando(tmp_path):
    """Lo peor que podría salir de esta tarea es arreglar las huellas nuevas y
    estropear las dos que ya se usaban."""
    def _celda(ambito: int, importe: str) -> FilaHuella:
        return FilaHuella(
            obra_id=1,
            codigo_obra="0664",
            ambito_id=ambito,
            periodo=date(2022, 1, 1),
            filas=1,
            versiones="1",
            importe_mes=Decimal(importe),
            importe_origen=Decimal(importe),
        )

    filas = tuple(_celda(a, "100.00") for a in (3, 7, 8, 11))
    antes, despues = tmp_path / "a.csv", tmp_path / "d.csv"
    escribir_csv(filas, antes)
    escribir_csv(filas, despues)

    resultado = CliRunner().invoke(main.cli, ["comparar-huellas", str(antes), str(despues)])

    assert resultado.exit_code == 0, resultado.output
    assert "Ambitos master 8 y 11" in resultado.output
