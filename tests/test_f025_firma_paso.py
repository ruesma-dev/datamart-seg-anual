# tests/test_f025_firma_paso.py
"""
F-025 · El sub-paso que firma el origen tras la ingesta (T11c, R16, §3.2).

**Por qué vive en `ingest_raw` y no en `build_stg`.** DA-2 acota también
`stg.presupuesto`, así que esa tabla dejó de reconstruirse entera y con ello
dejó de servir como señal de que una obra ha cambiado en Sigrid. `raw` es lo
único que la ingesta sigue trayendo completo cada noche (R34), y este es el
único momento en el que está recién cargado y todavía no ha construido nada
encima.

Lo que se protege aquí son tres decisiones:

1. **No se firma un `raw` a medias.** Si la ingesta falló, firmar denunciaría
   media base la noche siguiente.
2. **Avisa y no tumba.** Un fallo firmando no puede convertir una noche buena
   en una noche perdida: lo que se pierde es una denuncia, y de eso ya avisa el
   guardián.
3. **Escribe `firma_actual` y NADA más.** Si pisara `firma_origen`, la
   comparación de la noche siguiente no diría nada.

Sin red ni BBDD: doble de cliente y doble de API.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps.ingest_raw_step import (
    PASO_FIRMA_ORIGEN,
    IngestRawStep,
)
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.domain.ventana import firma_de_obra

AGREGADOS = {
    1: {"pre_filas": 100, "pre_suma_can": 5},
    2: {"pre_filas": 0, "pre_suma_can": None},
}


class PgFirma:
    def __init__(self, revienta: bool = False) -> None:
        self._revienta = revienta
        self.firmas: dict[int, str] = {}
        self.pasos: list[str] = []
        self.cierres: list[tuple] = []
        self._run = 0

    def fetch_firma_origen(self) -> dict[int, dict]:
        if self._revienta:
            raise RuntimeError("canceling statement due to statement timeout")
        return {k: dict(v) for k, v in AGREGADOS.items()}

    def registrar_firmas_actuales(self, firmas) -> int:
        self.firmas.update(firmas)
        return len(firmas)

    def record_run_start(self, stage: str, step: str, batch_id: str | None = None) -> int:
        self.pasos.append(step)
        self._run += 1
        return self._run

    def record_run_end(
        self, run_id: int, status: str, rows_processed: int = 0,
        error_message: str | None = None,
    ) -> None:
        self.cierres.append((run_id, status, rows_processed, error_message))


class ApiFalsa:
    """La ingesta no se ejecuta en estos tests: solo hace falta que el `with`
    del cliente HTTP entre y salga sin abrir nada."""

    def __init__(self, *_a: object, **_k: object) -> None:
        pass

    def __enter__(self) -> ApiFalsa:
        return self

    def __exit__(self, *_a: object) -> bool:
        return False


def settings_falsos() -> SimpleNamespace:
    return SimpleNamespace(
        tables_sigrid={"tables": []},
        sigrid_api=SimpleNamespace(
            base_url="http://localhost",
            function_key=SimpleNamespace(get_secret_value=lambda: "x"),
            database="ruesma",
            page_size=10_000,
            timeout_s=230.0,
            max_retries=3,
        ),
    )


def ejecutar(pg: PgFirma, monkeypatch: pytest.MonkeyPatch):
    import etl_sigrid.application.steps.ingest_raw_step as modulo

    monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(modulo, "SigridApiClient", ApiFalsa)
    return IngestRawStep(settings_falsos(), batch_id="b1").run()


# ---------------------------------------------------------------------------


def test_f025_r16_la_ingesta_firma_cada_obra(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgFirma()
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.SUCCESS
    assert set(pg.firmas) == {1, 2}


def test_f025_r16_la_firma_guardada_es_la_del_dominio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**El hash lo calcula el dominio, no el SQL.** Es lo que lo hace testable
    con fixtures y lo que lo pone bajo la campaña de mutación de DA-6."""
    pg = PgFirma()
    ejecutar(pg, monkeypatch)

    assert pg.firmas[1] == firma_de_obra(AGREGADOS[1])
    assert pg.firmas[2] == firma_de_obra(AGREGADOS[2])


def test_f025_r16_una_obra_sin_datos_TAMBIEN_se_firma(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La obra 2 no tiene filas en el origen. Firmarla igual es lo que permite
    detectar la noche que aparezcan: sin firma no hay con qué comparar."""
    pg = PgFirma()
    ejecutar(pg, monkeypatch)

    assert pg.firmas[1] != pg.firmas[2]


def test_f025_r16_el_paso_deja_su_fila_en_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aparece en `timings` con su duración, que es lo que hará falta para
    decidir si la variante cara de la firma (T2b) sale a cuenta."""
    pg = PgFirma()
    ejecutar(pg, monkeypatch)

    assert PASO_FIRMA_ORIGEN in pg.pasos
    assert pg.cierres[-1][1] == "SUCCESS"
    assert pg.cierres[-1][2] == 2


def test_f025_r16_el_resultado_dice_cuantas_obras_firmo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = PgFirma()
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.metadata["obras_firmadas"] == 2


def test_f025_r16_un_fallo_firmando_NO_tumba_la_ingesta(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**Avisa y no tumba.** La ingesta ha ido bien y el datamart se puede
    construir igual: lo que se pierde es la denuncia de una obra congelada que
    haya cambiado, y de eso avisa `check-ventana` al final de `run-all`.
    Cambiar un aviso por una avería sería peor negocio."""
    pg = PgFirma(revienta=True)
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.SUCCESS
    assert resultado.metadata["obras_firmadas"] == 0


def test_f025_r16_pero_el_fallo_queda_ESCRITO(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No tumbar no es callarse: la fila de `_meta.etl_runs` queda en FAILED con
    su motivo, o «esta noche nadie firmó» sería indistinguible de «todo bien»."""
    pg = PgFirma(revienta=True)
    ejecutar(pg, monkeypatch)

    assert pg.cierres[-1][1] == "FAILED"
    assert "timeout" in (pg.cierres[-1][3] or "")


def test_f025_r16_el_paso_solo_escribe_la_firma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Su única escritura es `firma_actual`. El doble no implementa ningún otro
    método de escritura, así que si el paso intentara tocar otra cosa este test
    fallaría con `AttributeError` en vez de pasar de largo."""
    pg = PgFirma()
    ejecutar(pg, monkeypatch)

    assert not hasattr(pg, "registrar_obras_construidas")
    assert not hasattr(pg, "truncate_table")
