# tests/test_f140_paso.py
"""
F-140 · La carga de las hipótesis en `build_tesoreria` (R2-R4) y su SQL.

Ningún test toca red ni BBDD: se sustituye `build_postgres_client` y, cuando
hace falta, el lector del YAML.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from psycopg.types.json import Json

from etl_sigrid.application.steps import build_tesoreria_step as modulo
from etl_sigrid.application.steps.build_tesoreria_step import BuildTesoreriaStep
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.infrastructure.config.hipotesis_caja_yaml import (
    HipotesisLeidas,
    cargar_hipotesis_caja,
)
from etl_sigrid.infrastructure.postgres import hipotesis_caja_sql as hsql

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria"
RUTA_SETUP = DIR_SQL / "00_setup.sql"


def _columnas_setup(tabla: str) -> list[str]:
    texto = re.sub(r"\s+", " ", "\n".join(
        l for l in RUTA_SETUP.read_text(encoding="utf-8").splitlines()
        if not l.lstrip().startswith("--")
    ))
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(tabla)} \((.*?)\);", texto)
    assert m
    columnas = []
    for trozo in re.split(r",(?![^()]*\))", m.group(1)):
        nombre = trozo.strip().split(" ")[0]
        if nombre and nombre.upper() != "PRIMARY":
            columnas.append(nombre)
    return columnas


# ===========================================================================
# R4 · las filas que se publican, en el orden de las columnas del setup
# ===========================================================================

def test_f140_r4_el_insert_del_catalogo_lleva_las_columnas_del_setup() -> None:
    m = re.search(r"INSERT INTO tesoreria\.hipotesis_caja \((.*?)\) VALUES \((.*?)\)",
                  hsql.SQL_INSERT_CATALOGO)
    assert m
    columnas = [c.strip() for c in m.group(1).split(",")]
    assert columnas == _columnas_setup("tesoreria.hipotesis_caja")
    assert m.group(2).count("%s") == len(columnas), "parametrizado, nada se interpola"


def test_f140_r3_el_insert_de_los_manuales_lleva_las_columnas_del_setup() -> None:
    m = re.search(r"INSERT INTO tesoreria\.hipotesis_caja_manual \((.*?)\) VALUES \((.*?)\)",
                  hsql.SQL_INSERT_MANUAL)
    assert m
    columnas = [c.strip() for c in m.group(1).split(",")]
    assert columnas == _columnas_setup("tesoreria.hipotesis_caja_manual")
    assert m.group(2).count("%s") == len(columnas)


def test_f140_r4_se_vacian_las_dos_tablas_y_nada_mas() -> None:
    assert hsql.SQL_VACIAR == (
        "TRUNCATE tesoreria.hipotesis_caja, tesoreria.hipotesis_caja_manual"
    )


def test_f140_r4_una_fila_por_hipotesis_del_catalogo_real() -> None:
    leidas = cargar_hipotesis_caja()
    filas = hsql.filas_catalogo(leidas.catalogo)
    assert [f[0] for f in filas] == [h.codigo for h in leidas.catalogo]
    assert len(filas) == 23
    for fila, h in zip(filas, leidas.catalogo):
        assert len(fila) == len(_columnas_setup("tesoreria.hipotesis_caja"))
        assert isinstance(fila[4], Json) and fila[4].obj == h.valor_defecto
        assert (fila[5] is None) == (not h.opciones)
        if h.opciones:
            assert isinstance(fila[5], Json) and fila[5].obj == list(h.opciones)
        assert fila[1:4] == (h.sentido, h.descripcion, h.unidad)
        assert fila[6:] == (h.fuente_defecto, h.ingrediente, h.validado,
                            h.fecha_validacion, h.admite_obra)


def test_f140_r3_las_filas_manuales_llevan_el_valor_como_json() -> None:
    filas = hsql.filas_manuales([
        {"clave_obra": "1-0462", "codigo": "H09", "valor": 90,
         "motivo": "pactado", "fecha": "2026-10-25"},
    ])
    assert len(filas) == 1
    clave, codigo, valor, motivo, fecha = filas[0]
    assert (clave, codigo, motivo, fecha) == ("1-0462", "H09", "pactado", "2026-10-25")
    assert isinstance(valor, Json) and valor.obj == 90


# ===========================================================================
# R2, R3 · el paso: valida, y con errores falla sin escribir
# ===========================================================================

class _PgFalso:
    def __init__(self) -> None:
        self.ejecutados: list[str] = []
        self.cargas: list[tuple] = []

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)

    def count_rows(self, schema: str, table: str) -> int:
        return 1

    def cargar_hipotesis_caja(self, catalogo, obras) -> int:
        self.cargas.append((tuple(catalogo), list(obras)))
        return len(catalogo) + len(obras)


@pytest.fixture
def pg(monkeypatch: pytest.MonkeyPatch) -> _PgFalso:
    doble = _PgFalso()
    monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: doble)
    return doble


def _paso() -> BuildTesoreriaStep:
    return BuildTesoreriaStep(SimpleNamespace())


def test_f140_r2_el_paso_carga_el_catalogo_del_repositorio(pg) -> None:
    resultado = _paso().run()
    assert resultado.status == StepStatus.SUCCESS, resultado.error_message
    assert len(pg.cargas) == 1
    catalogo, obras = pg.cargas[0]
    assert len(catalogo) == 23 and obras == []


def test_f140_r2_con_errores_falla_con_la_lista_y_no_escribe(pg, monkeypatch) -> None:
    monkeypatch.setattr(modulo, "cargar_hipotesis_caja", lambda: HipotesisLeidas(
        (), [], ["H01: unidad desconocida", "H02: falta valor_defecto"],
    ))
    resultado = _paso().run()
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en hipotesis_carga: ")
    assert "H01: unidad desconocida" in resultado.error_message
    assert "H02: falta valor_defecto" in resultado.error_message
    assert pg.cargas == [], "con errores no se escribe nada"
    assert "08_hipotesis_caja_obra.sql" not in pg.ejecutados


def test_f140_r3_los_valores_de_obra_viajan_a_la_carga(pg, monkeypatch) -> None:
    leidas = cargar_hipotesis_caja()
    obra = {"clave_obra": "1-0462", "codigo": "H09", "valor": 90,
            "motivo": "pactado", "fecha": "2026-10-25"}
    monkeypatch.setattr(modulo, "cargar_hipotesis_caja",
                        lambda: HipotesisLeidas(leidas.catalogo, [obra], []))
    resultado = _paso().run()
    assert resultado.status == StepStatus.SUCCESS
    assert pg.cargas == [(leidas.catalogo, [obra])]


def test_f140_r2_un_yaml_que_falta_es_failed_con_su_nombre(pg, monkeypatch) -> None:
    def _no_esta():
        raise FileNotFoundError("config/hipotesis_caja.yaml")
    monkeypatch.setattr(modulo, "cargar_hipotesis_caja", _no_esta)
    resultado = _paso().run()
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en hipotesis_carga: ")
    assert pg.cargas == []


def test_f140_r5_la_carga_va_justo_antes_de_08(pg) -> None:
    nombres = [s.name for s in modulo.SUB_PASOS]
    i = nombres.index("hipotesis_carga")
    assert modulo.SUB_PASOS[i].sql_file is None
    assert modulo.SUB_PASOS[i + 1].sql_file == "08_hipotesis_caja_obra.sql"
    assert nombres.index("devengo_pendiente") < i, "08 lee las obras de devengo_corte_obra"
