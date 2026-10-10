# tests/test_f097_ingesta_descompuestos.py
"""
F-097 · El paso `ingest_descompuestos` (R2-R4, R6-R11) y la escritura en una
sola transaccion de `PostgresClient.reemplazar_filas` (R8), sin red ni BBDD.

El paso lee Sigrid SOLO con `SigridApiClient.leer_sql` (un `SELECT`) y escribe
en `descompuestos._des_texto` y `descompuestos._versiones_cargadas`. Aqui los
dos lados son dobles:

- `_ApiFalsa` imita `SigridApiClient.leer_sql` y el protocolo de contexto, y
  responde a las tres consultas del paso (la huella, el ambito 3 y una version)
  segun su texto.
- `_PgFalso` imita los TRES metodos del cliente que usa el paso, con su firma
  real (la vigila `tests/test_f025_contrato_cliente.py`).

`reemplazar_filas` se prueba contra un doble de la CONEXION de psycopg: lo que
se mira es que el `DELETE`, el `COPY` y la fila de control van por la misma
conexion y con un solo `commit` (o un `rollback` y ningun `commit`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.domain.extraccion import es_sentencia_de_lectura

RAIZ = Path(__file__).resolve().parents[1]
MEDICION_HUELLA = RAIZ / "progress" / "mediciones" / "F-097_huella_master.sql"

COLUMNAS_SIGRID = ["ide", "obride", "paride", "amb", "fas", "can", "pre", "haydes", "des"]


# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


def _fila_sigrid(ide: int, obra: int, amb: int, fas: int, des: str = "~D|X|Y|1||UD|\n") -> list:
    return [ide, obra, 1000 + ide, amb, fas, 2.5, 10.25, 1, des]


class _ApiFalsa:
    """Doble de `SigridApiClient`: responde por el texto de la consulta."""

    def __init__(
        self,
        huellas: list[list],
        ambito3: list[list],
        versiones: Mapping[tuple[int, int], list[list]],
        *,
        fallan: Iterable[tuple[int, int]] = (),
    ) -> None:
        self._huellas = huellas
        self._ambito3 = ambito3
        self._versiones = dict(versiones)
        self._fallan = set(fallan)
        self.llamadas: list[tuple[str, list, int | None]] = []
        self.cerrada = False

    def __enter__(self) -> _ApiFalsa:
        return self

    def __exit__(self, *_: object) -> None:
        self.cerrada = True

    @staticmethod
    def _pagina(filas: list[list], desde: int, maximo: int) -> list[list]:
        return [f for f in filas if f[0] > desde][:maximo]

    def leer_sql(self, sql: str, parameters: list | None = None, max_rows: int | None = None) -> dict:
        from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiHttpError

        params = list(parameters or [])
        self.llamadas.append((sql, params, max_rows))
        if "CHECKSUM_AGG" in sql:
            filas = self._huellas
            columnas = ["obride", "fas", "filas", "bytes", "huella", "vigente"]
        elif "amb = 3" in sql:
            filas = self._pagina(self._ambito3, params[-1], max_rows or 10**9)
            columnas = COLUMNAS_SIGRID
        else:
            obra, fas, desde = params
            if (obra, fas) in self._fallan:
                raise SigridApiHttpError("HTTP 500 de sigrid-api: se cayo")
            filas = self._pagina(self._versiones.get((obra, fas), []), desde, max_rows or 10**9)
            columnas = COLUMNAS_SIGRID
        return {"columns": columnas, "rows": filas, "row_count": len(filas)}


class _PgFalso:
    """Doble de `PostgresClient` con los tres metodos que usa el paso."""

    def __init__(self, cargadas: list[tuple] | None = None, falla_setup: bool = False) -> None:
        self._cargadas = cargadas or []
        self._falla_setup = falla_setup
        self.ficheros: list[str] = []
        self.lecturas: list[str] = []
        self.reemplazos: list[dict] = []

    def execute_sql_file(self, path: Path, *, params: dict | tuple | None = None) -> None:
        self.ficheros.append(path.name)
        if self._falla_setup:
            raise RuntimeError("permission denied for schema descompuestos")

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.lecturas.append(sql_text)
        return list(self._cargadas)

    def reemplazar_filas(
        self,
        schema: str,
        tabla: str,
        filtro: Mapping[str, Any],
        columnas: Sequence[str],
        filas: Iterable[Mapping[str, Any]],
        control: Any = None,
    ) -> int:
        materializadas = [dict(f) for f in filas]
        self.reemplazos.append({
            "schema": schema, "tabla": tabla, "filtro": dict(filtro),
            "columnas": list(columnas), "filas": materializadas, "control": control,
        })
        return len(materializadas)


def _settings(presupuesto_mb: float = 300, page_size: int = 10_000) -> SimpleNamespace:
    return SimpleNamespace(
        sigrid_api=SimpleNamespace(page_size=page_size),
        business_rules={"sigrid": {"campos_extendidos": {"cod_version_master_vigente": "15"}}},
        descompuestos=SimpleNamespace(presupuesto_mb=presupuesto_mb),
    )


def _huella(obra: int, fas: int, filas: int, bytes_: int = 1000, huella: int = 5,
            vigente: int | None = None) -> list:
    return [obra, fas, filas, bytes_, huella, vigente]


def _ejecutar(monkeypatch: pytest.MonkeyPatch, api: _ApiFalsa, pg: _PgFalso, **kwargs: Any):
    from etl_sigrid.application.steps import ingest_descompuestos_step
    from etl_sigrid.application.steps.ingest_descompuestos_step import IngestDescompuestosStep

    monkeypatch.setattr(ingest_descompuestos_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(ingest_descompuestos_step, "abrir_api", lambda _s: api)
    settings = kwargs.pop("settings", _settings())
    return IngestDescompuestosStep(settings, batch_id="B1", **kwargs).run()


def _escenario() -> _ApiFalsa:
    """Obra 7: v0 y v1 (vigente la 1); obra 9: v2. Ambito 3: 1.005 filas."""
    huellas = [_huella(7, 0, 2), _huella(7, 1, 1, vigente=1), _huella(9, 2, 3)]
    ambito3 = [_fila_sigrid(i, 7, 3, 0) for i in range(1, 1006)]
    versiones = {
        (7, 0): [_fila_sigrid(5001, 7, 8, 0), _fila_sigrid(5002, 7, 8, 0)],
        (7, 1): [_fila_sigrid(6001, 7, 8, 1)],
        (9, 2): [_fila_sigrid(7001 + i, 9, 8, 2) for i in range(3)],
    }
    return _ApiFalsa(huellas, ambito3, versiones)


def _de_versiones(pg: _PgFalso) -> list[dict]:
    return [r for r in pg.reemplazos if r["filtro"].get("ambito_id") == 8]


# ===========================================================================
# R2 · un paso propio, fuera de tables_sigrid.yaml, que solo lee
# ===========================================================================


def test_f097_r2_paso_propio_sin_dependencias() -> None:
    from etl_sigrid.application.steps.ingest_descompuestos_step import IngestDescompuestosStep

    paso = IngestDescompuestosStep(_settings())
    assert paso.name == "ingest_descompuestos"
    assert paso.stage == "ingest"
    assert paso.depends_on == []


def test_f097_r2_fuera_de_tables_sigrid_y_la_ingesta_sigue_en_71() -> None:
    config = yaml.safe_load((RAIZ / "config" / "tables_sigrid.yaml").read_text(encoding="utf-8"))
    tablas = config["tables"]
    assert len(tablas) == 74, (
        "TOTAL_TABLAS: 71 + `usu` (F-085) + `rcg` y `gra` (F-090); el des no pasa por raw (D12)"
    )
    destinos = {t["target_table"] for t in tablas}
    assert not {"_des_texto", "obrparpre_des", "des_texto"} & destinos
    obrparpre = next(t for t in tablas if t["source_table"] == "obrparpre")
    assert "des" in obrparpre["exclude_columns"], "la entrada obrparpre sigue excluyendo des"


def test_f097_r2_solo_select_y_escribe_en_sus_dos_tablas(monkeypatch: pytest.MonkeyPatch) -> None:
    api, pg = _escenario(), _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg)

    assert resultado.status == StepStatus.SUCCESS, resultado.error_message
    assert api.llamadas, "el paso lee de Sigrid"
    for sql, _params, _max in api.llamadas:
        assert es_sentencia_de_lectura(sql), sql[:80]
    assert {(r["schema"], r["tabla"]) for r in pg.reemplazos} == {("descompuestos", "_des_texto")}
    controles = {(r["control"].schema, r["control"].tabla) for r in pg.reemplazos if r["control"]}
    assert controles == {("descompuestos", "_versiones_cargadas")}
    assert api.cerrada, "el cliente de Sigrid se cierra al terminar"


def test_f097_r2_el_setup_va_antes_que_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    api, pg = _escenario(), _PgFalso()
    _ejecutar(monkeypatch, api, pg)
    assert pg.ficheros == ["00_setup.sql"]


def test_f097_r2_si_el_setup_falla_no_se_lee_sigrid(monkeypatch: pytest.MonkeyPatch) -> None:
    api, pg = _escenario(), _PgFalso(falla_setup=True)
    resultado = _ejecutar(monkeypatch, api, pg)
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en setup:")
    assert api.llamadas == [] and pg.reemplazos == []
    assert resultado.finished_at is not None


def test_f097_r2_las_columnas_del_texto(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps.ingest_descompuestos_step import COLUMNAS_DES_TEXTO

    assert list(COLUMNAS_DES_TEXTO) == [
        "presupuesto_id", "obra_id", "partida_id", "ambito_id", "fase_num",
        "cantidad", "precio", "haydes", "des", "batch_id",
    ]
    api, pg = _escenario(), _PgFalso()
    _ejecutar(monkeypatch, api, pg)
    (v0,) = [r for r in _de_versiones(pg) if r["filtro"]["fase_num"] == 0]
    fila = v0["filas"][0]
    assert fila == {
        "presupuesto_id": 5001, "obra_id": 7, "partida_id": 6001, "ambito_id": 8,
        "fase_num": 0, "cantidad": 2.5, "precio": 10.25, "haydes": 1,
        "des": "~D|X|Y|1||UD|\n", "batch_id": "B1",
    }
    assert all(r["columnas"] == list(COLUMNAS_DES_TEXTO) for r in pg.reemplazos)


# ===========================================================================
# R3 · el ambito 3 entero cada noche
# ===========================================================================


def test_f097_r3_ambito_3_entero_en_una_sustitucion(monkeypatch: pytest.MonkeyPatch) -> None:
    api, pg = _escenario(), _PgFalso()
    _ejecutar(monkeypatch, api, pg)

    (a3,) = [r for r in pg.reemplazos if r["filtro"] == {"ambito_id": 3}]
    assert len(a3["filas"]) == 1005, "las dos paginas, 1.000 + 5"
    assert a3["control"] is None, "el ambito 3 no tiene fila de control"
    lecturas = [c for c in api.llamadas if "amb = 3" in c[0]]
    assert [c[1] for c in lecturas] == [[0], [1000]], "keyset por ide"
    assert pg.reemplazos[0] is a3, "el ambito 3 va primero"


def test_f097_r3_ambito_3_aunque_no_haya_versiones(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _ApiFalsa([], [_fila_sigrid(1, 7, 3, 0)], {})
    pg = _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg)
    assert resultado.status == StepStatus.SUCCESS
    assert [r["filtro"] for r in pg.reemplazos] == [{"ambito_id": 3}]


def test_f097_r3_la_consulta_del_ambito_3() -> None:
    from etl_sigrid.application.steps.ingest_descompuestos_step import SQL_AMBITO_3

    for trozo in ("SELECT TOP 1000 ", "FROM obrparpre", "amb = 3", "fas = 0",
                  "DATALENGTH(des) > 0", "ide > ?", "ORDER BY ide"):
        assert trozo in SQL_AMBITO_3


# ===========================================================================
# R4 · la huella de todas las versiones en UNA consulta
# ===========================================================================


def test_f097_r4_una_sola_consulta_de_huella(monkeypatch: pytest.MonkeyPatch) -> None:
    api, pg = _escenario(), _PgFalso()
    _ejecutar(monkeypatch, api, pg, settings=_settings(page_size=4321))
    huellas = [c for c in api.llamadas if "CHECKSUM_AGG" in c[0]]
    assert len(huellas) == 1
    _sql, params, maximo = huellas[0]
    assert params == ["15"], "el cod de la vigente viene de business_rules"
    assert maximo == 4321
    assert api.llamadas[0] is huellas[0], "la huella se pide la primera"


def test_f097_r4_la_huella_es_la_de_la_medicion() -> None:
    """La misma expresion que la toma del 2026-09-27: si no, T0 compara peras con manzanas."""
    from etl_sigrid.application.steps.ingest_descompuestos_step import SQL_HUELLA

    medida = MEDICION_HUELLA.read_text(encoding="utf-8")
    expresion = medida[medida.index("CHECKSUM_AGG("): medida.index(" huella FROM")]
    assert expresion in SQL_HUELLA
    for trozo in ("amb = 8", "DATALENGTH(des) > 0", "GROUP BY obride, fas", "conext",
                  "cod = ?", "MAX(valn)"):
        assert trozo in SQL_HUELLA


def test_f097_r4_la_huella_truncada_para_el_paso(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _ApiFalsa([_huella(1, f, 1) for f in range(3)], [], {})
    pg = _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg, settings=_settings(page_size=3))
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en huella:")
    assert "3" in resultado.error_message
    assert pg.reemplazos == []


def test_f097_r4_la_huella_se_guarda_en_el_control(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _ApiFalsa([_huella(7, 0, 2, bytes_=4096, huella=-77)], [],
                    {(7, 0): [_fila_sigrid(1, 7, 8, 0), _fila_sigrid(2, 7, 8, 0)]})
    pg = _PgFalso()
    _ejecutar(monkeypatch, api, pg)
    (version,) = _de_versiones(pg)
    control = version["control"]
    assert dict(control.clave) == {"obra_id": 7, "fase_num": 0}
    assert control.valores["filas"] == 2
    assert control.valores["bytes"] == 4096
    assert control.valores["huella"] == -77


def test_f097_r4_lee_lo_cargado_de_su_tabla_de_control(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps.ingest_descompuestos_step import SQL_CARGADAS

    assert "FROM descompuestos._versiones_cargadas" in SQL_CARGADAS
    api = _escenario()
    # (7, 0) ya cargada e igual: no se relee; (9, 2) cargada e igual tampoco.
    pg = _PgFalso(cargadas=[(7, 0, 2, 1000, 5), (9, 2, 3, 1000, 5)])
    _ejecutar(monkeypatch, api, pg)
    assert pg.lecturas == [SQL_CARGADAS]
    assert [(r["filtro"]["obra_id"], r["filtro"]["fase_num"]) for r in _de_versiones(pg)] == [(7, 1)]


# ===========================================================================
# R6 · R7 · el tope por noche y --sin-tope
# ===========================================================================


def test_f097_r6_lo_aplazado_se_registra(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.domain.descompuestos import MB

    huellas = [_huella(1, f, 1, bytes_=int(0.6 * MB)) for f in range(3)]
    versiones = {(1, f): [_fila_sigrid(100 + f, 1, 8, f)] for f in range(3)}
    api = _ApiFalsa(huellas, [], versiones)
    pg = _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg, settings=_settings(presupuesto_mb=1))

    assert resultado.status == StepStatus.SUCCESS
    assert len(_de_versiones(pg)) == 1
    assert resultado.metadata["versiones_aplazadas"] == 2
    assert resultado.metadata["mb_aplazados"] == 1.2
    assert resultado.metadata["sin_tope"] is False


def test_f097_r7_sin_tope_lo_lee_todo(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.domain.descompuestos import MB

    huellas = [_huella(1, f, 1, bytes_=int(0.6 * MB)) for f in range(3)]
    versiones = {(1, f): [_fila_sigrid(100 + f, 1, 8, f)] for f in range(3)}
    api = _ApiFalsa(huellas, [], versiones)
    pg = _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg, settings=_settings(presupuesto_mb=1), sin_tope=True)
    assert len(_de_versiones(pg)) == 3
    assert resultado.metadata["versiones_aplazadas"] == 0
    assert resultado.metadata["sin_tope"] is True


# ===========================================================================
# R8 · cada version en UNA sustitucion, y nunca dos copias
# ===========================================================================


def test_f097_r8_cada_version_una_sustitucion_con_su_control(monkeypatch: pytest.MonkeyPatch) -> None:
    api, pg = _escenario(), _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg)

    versiones = _de_versiones(pg)
    assert [r["filtro"] for r in versiones] == [
        {"obra_id": 7, "ambito_id": 8, "fase_num": 1},   # la vigente primero
        {"obra_id": 7, "ambito_id": 8, "fase_num": 0},
        {"obra_id": 9, "ambito_id": 8, "fase_num": 2},
    ]
    for r in versiones:
        valores = r["control"].valores
        assert valores["sello_troceado"] is None, "releida: hay que volver a trocearla"
        assert valores["cargada_at"] is not None
        assert "troceada_at" not in valores, "la fecha del ultimo troceado no se pierde"
    assert resultado.rows_processed == 1005 + 2 + 1 + 3
    assert resultado.metadata["versiones_releidas"] == 3
    assert resultado.metadata["releidas_por_motivo"] == {"vigente": 1, "cambiada": 0, "nueva": 2}


def test_f097_r8_la_version_que_sigrid_ya_no_tiene_se_borra(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _ApiFalsa([], [], {})
    pg = _PgFalso(cargadas=[(4, 3, 10, 1000, 1)])
    resultado = _ejecutar(monkeypatch, api, pg)

    (borrado,) = _de_versiones(pg)
    assert borrado["filtro"] == {"obra_id": 4, "ambito_id": 8, "fase_num": 3}
    assert borrado["filas"] == []
    assert dict(borrado["control"].clave) == {"obra_id": 4, "fase_num": 3}
    assert borrado["control"].valores is None, "sin valores: se borra la fila de control"
    assert resultado.metadata["versiones_borradas"] == 1


# ===========================================================================
# R9 · el recuento contra la huella
# ===========================================================================


def test_f097_r9_recuento_distinto_se_revierte_y_sigue(monkeypatch: pytest.MonkeyPatch) -> None:
    huellas = [_huella(7, 0, 5), _huella(9, 2, 1)]
    versiones = {(7, 0): [_fila_sigrid(1, 7, 8, 0)], (9, 2): [_fila_sigrid(2, 9, 8, 2)]}
    api = _ApiFalsa(huellas, [], versiones)
    pg = _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg)

    assert [r["filtro"]["obra_id"] for r in _de_versiones(pg)] == [9], "la 7/0 no se escribe"
    assert resultado.status == StepStatus.FAILED
    assert "7/0" in resultado.error_message and "5" in resultado.error_message
    assert resultado.metadata["versiones_fallidas"] == ["7/0: Sigrid dio 1 filas y la huella dice 5"]
    assert resultado.finished_at is not None


def test_f097_r9_un_fallo_de_sigrid_en_una_version_no_para_las_demas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huellas = [_huella(7, 0, 1), _huella(9, 2, 1)]
    versiones = {(7, 0): [_fila_sigrid(1, 7, 8, 0)], (9, 2): [_fila_sigrid(2, 9, 8, 2)]}
    api = _ApiFalsa(huellas, [], versiones, fallan=[(7, 0)])
    pg = _PgFalso()
    resultado = _ejecutar(monkeypatch, api, pg)

    assert [r["filtro"]["obra_id"] for r in _de_versiones(pg)] == [9]
    assert resultado.status == StepStatus.FAILED
    assert resultado.metadata["versiones_fallidas"][0].startswith("7/0: HTTP 500")


def test_f097_r9_todo_bien_es_success_sin_mensaje(monkeypatch: pytest.MonkeyPatch) -> None:
    resultado = _ejecutar(monkeypatch, _escenario(), _PgFalso())
    assert resultado.status == StepStatus.SUCCESS
    assert resultado.error_message is None
    assert resultado.metadata["versiones_fallidas"] == []


# ===========================================================================
# R10 · la lectura de una version: indice `oaf`, paginada por ide, 1.000 filas
# ===========================================================================


def test_f097_r10_la_consulta_de_una_version() -> None:
    from etl_sigrid.application.steps.ingest_descompuestos_step import (
        FILAS_POR_PAGINA,
        SQL_VERSION,
    )

    assert FILAS_POR_PAGINA == 1000
    for trozo in ("SELECT TOP 1000 ", "FROM obrparpre", "obride = ?", "amb = 8",
                  "fas = ?", "DATALENGTH(des) > 0", "ide > ?", "ORDER BY ide"):
        assert trozo in SQL_VERSION
    assert SQL_VERSION.index("obride = ?") < SQL_VERSION.index("fas = ?") < SQL_VERSION.index("ide > ?")


def test_f097_r10_pagina_por_ide_hasta_la_pagina_corta(monkeypatch: pytest.MonkeyPatch) -> None:
    filas = [_fila_sigrid(10_000 + i, 3, 8, 4) for i in range(2001)]
    api = _ApiFalsa([_huella(3, 4, 2001)], [], {(3, 4): filas})
    pg = _PgFalso()
    _ejecutar(monkeypatch, api, pg)
    lecturas = [c for c in api.llamadas if "obride = ?" in c[0]]
    assert [c[1] for c in lecturas] == [[3, 4, 0], [3, 4, 10_999], [3, 4, 11_999]]
    assert {c[2] for c in lecturas} == {1000}
    assert len(_de_versiones(pg)[0]["filas"]) == 2001


def test_f097_r10_un_cursor_que_no_avanza_se_corta() -> None:
    from etl_sigrid.application.steps.ingest_descompuestos_step import leer_paginado

    class _Atascada:
        def leer_sql(self, sql: str, parameters: list | None = None, max_rows: int | None = None) -> dict:
            return {"columns": COLUMNAS_SIGRID, "rows": [_fila_sigrid(0, 1, 8, 0)] * (max_rows or 1),
                    "row_count": max_rows}

    with pytest.raises(RuntimeError, match="no avanza"):
        leer_paginado(_Atascada(), "SELECT TOP 2 ide FROM obrparpre WHERE ide > ?", [], filas_por_pagina=2)


# ===========================================================================
# R11 · el batch_id de cada version
# ===========================================================================


def test_f097_r11_batch_id_en_el_control_y_en_cada_fila(monkeypatch: pytest.MonkeyPatch) -> None:
    api, pg = _escenario(), _PgFalso()
    _ejecutar(monkeypatch, api, pg)
    for r in pg.reemplazos:
        assert {f["batch_id"] for f in r["filas"]} <= {"B1"}
        if r["control"] is not None and r["control"].valores is not None:
            assert r["control"].valores["batch_id"] == "B1"


# ===========================================================================
# R8 · PostgresClient.reemplazar_filas: una conexion, una transaccion
# ===========================================================================


class _CopiaFalsa:
    def __init__(self, registro: list) -> None:
        self._registro = registro

    def __enter__(self) -> _CopiaFalsa:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def write(self, datos: str) -> None:
        self._registro.append(("write", datos))


class _CursorFalso:
    def __init__(self, registro: list, falla_en: str | None) -> None:
        self._registro = registro
        self._falla_en = falla_en

    def __enter__(self) -> _CursorFalso:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, query: Any, params: Any = None) -> None:
        texto = query.as_string(None) if hasattr(query, "as_string") else str(query)
        self._registro.append(("execute", texto, params))
        if self._falla_en and self._falla_en in texto:
            raise RuntimeError("fallo a proposito")

    def copy(self, query: Any) -> _CopiaFalsa:
        self._registro.append(("copy", query.as_string(None)))
        return _CopiaFalsa(self._registro)


class _ConexionFalsa:
    def __init__(self, falla_en: str | None = None) -> None:
        self.registro: list = []
        self._falla_en = falla_en

    def cursor(self) -> _CursorFalso:
        return _CursorFalso(self.registro, self._falla_en)

    def commit(self) -> None:
        self.registro.append(("commit",))

    def rollback(self) -> None:
        self.registro.append(("rollback",))

    def close(self) -> None:
        self.registro.append(("close",))


def _cliente(conexion: _ConexionFalsa):
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    cliente = PostgresClient("postgresql://nadie", "postgresql://nadie", "nada", auto_create_db=False)
    cliente._bootstrap_done = True
    cliente._connect = lambda *_a, **_k: conexion  # type: ignore[method-assign]
    return cliente


def test_f097_r8_reemplazar_filas_borra_copia_y_controla_en_una_transaccion() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import FilaControl

    conexion = _ConexionFalsa()
    escritas = _cliente(conexion).reemplazar_filas(
        "descompuestos", "_des_texto", {"obra_id": 7, "ambito_id": 8, "fase_num": 1},
        ["presupuesto_id", "des"],
        [{"presupuesto_id": 1, "des": "a\tb\nc"}, {"presupuesto_id": 2, "des": None}],
        FilaControl(schema="descompuestos", tabla="_versiones_cargadas",
                    clave={"obra_id": 7, "fase_num": 1}, valores={"filas": 2, "sello_troceado": None}),
    )
    assert escritas == 2
    tipos = [r[0] for r in conexion.registro]
    assert tipos == ["execute", "copy", "write", "write", "execute", "commit", "close"]
    borrado = conexion.registro[0]
    assert borrado[1] == (
        'DELETE FROM "descompuestos"."_des_texto" WHERE "obra_id" = %s AND "ambito_id" = %s '
        'AND "fase_num" = %s'
    )
    assert borrado[2] == [7, 8, 1]
    assert conexion.registro[1][1] == (
        'COPY "descompuestos"."_des_texto" ("presupuesto_id", "des") FROM STDIN '
        "WITH (FORMAT text, NULL '\\N')"
    )
    assert conexion.registro[2] == ("write", "1\ta\\tb\\nc\n")
    assert conexion.registro[3] == ("write", "2\t\\N\n")
    upsert = conexion.registro[4]
    assert upsert[1] == (
        'INSERT INTO "descompuestos"."_versiones_cargadas" ("obra_id", "fase_num", "filas", '
        '"sello_troceado") VALUES (%s, %s, %s, %s) ON CONFLICT ("obra_id", "fase_num") '
        'DO UPDATE SET "filas" = EXCLUDED."filas", "sello_troceado" = EXCLUDED."sello_troceado"'
    )
    assert upsert[2] == [7, 1, 2, None]


def test_f097_r8_reemplazar_filas_sin_valores_borra_el_control() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import FilaControl

    conexion = _ConexionFalsa()
    escritas = _cliente(conexion).reemplazar_filas(
        "descompuestos", "_des_texto", {"obra_id": 4, "ambito_id": 8, "fase_num": 3},
        ["presupuesto_id"], [],
        FilaControl(schema="descompuestos", tabla="_versiones_cargadas",
                    clave={"obra_id": 4, "fase_num": 3}, valores=None),
    )
    assert escritas == 0
    ejecutadas = [r for r in conexion.registro if r[0] == "execute"]
    assert ejecutadas[-1][1] == (
        'DELETE FROM "descompuestos"."_versiones_cargadas" WHERE "obra_id" = %s AND "fase_num" = %s'
    )
    assert ejecutadas[-1][2] == [4, 3]
    assert conexion.registro[-2:] == [("commit",), ("close",)]


def test_f097_r8_reemplazar_filas_sin_control_no_toca_otra_tabla() -> None:
    conexion = _ConexionFalsa()
    _cliente(conexion).reemplazar_filas("descompuestos", "_des_texto", {"ambito_id": 3},
                                        ["presupuesto_id"], [{"presupuesto_id": 1}])
    assert [r[0] for r in conexion.registro] == ["execute", "copy", "write", "commit", "close"]


def test_f097_r8_si_falla_el_control_no_queda_nada() -> None:
    """Nunca dos copias ni medio reemplazo: rollback y ningun commit."""
    from etl_sigrid.infrastructure.postgres.postgres_client import FilaControl

    conexion = _ConexionFalsa(falla_en="ON CONFLICT")
    with pytest.raises(RuntimeError, match="a proposito"):
        _cliente(conexion).reemplazar_filas(
            "descompuestos", "_des_texto", {"obra_id": 1, "ambito_id": 8, "fase_num": 0},
            ["presupuesto_id"], [{"presupuesto_id": 1}],
            FilaControl(schema="descompuestos", tabla="_versiones_cargadas",
                        clave={"obra_id": 1, "fase_num": 0}, valores={"filas": 1}),
        )
    tipos = [r[0] for r in conexion.registro]
    assert "commit" not in tipos and tipos[-2:] == ["rollback", "close"]


@pytest.mark.parametrize(("filtro", "columnas"), [({}, ["a"]), ({"a": 1}, [])])
def test_f097_r8_reemplazar_filas_sin_filtro_o_sin_columnas_se_rechaza(
    filtro: dict, columnas: list
) -> None:
    conexion = _ConexionFalsa()
    with pytest.raises(ValueError):
        _cliente(conexion).reemplazar_filas("descompuestos", "_des_texto", filtro, columnas, [])
    assert conexion.registro == [], "ni se abre la conexion"


def test_f097_r8_la_fila_de_control_es_inmutable() -> None:
    import dataclasses

    from etl_sigrid.infrastructure.postgres.postgres_client import FilaControl

    control = FilaControl(schema="s", tabla="t", clave={"a": 1}, valores=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        control.tabla = "otra"  # type: ignore[misc]
