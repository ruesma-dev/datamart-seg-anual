# tests/test_f025_cli.py
"""
F-025 · Los comandos y el enganche a `run-all` (T15, T16, T18, T19, R27).

Tres cosas se protegen aquí, y las tres son de las que se rompen sin que nadie
lo note:

1. **`ventana-plan` no escribe.** Es un dry-run, y el doble de cliente **no
   implementa ni un método de escritura**: si el comando intentara escribir,
   esto reventaría con `AttributeError` en vez de pasar de largo.
2. **`check-ventana` sale KO sobre cero obras.** Un guardián que da verde
   cuando no ha podido mirar es peor que no tenerlo. Es el defecto que se
   arregló en `check-cobertura` el 2026-09-03, y este nace con él resuelto.
3. **`run-all` termina en verde con el guardián en KO** (DA-5). Es el precio
   declarado de no bloquear: la alerta de fallo no se dispara, así que la regla
   de `infra/97_create_alert_ventana.ps1` es la ÚNICA vía por la que el
   hallazgo llega a una persona.

Ningún test abre red ni BBDD.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.ventana import MARCADOR_KO, ObraCensada

#: Centinela para «no me han dicho nada», distinto de `None`, que aquí significa
#: «nunca se ha hecho una reconstrucción completa».
_RECIEN = object()


def sello_del_repositorio() -> str:
    from config.settings import get_settings

    return main.sello_vigente_del_repositorio(get_settings())


class PgSoloLectura:
    """Doble que sirve filas enlatadas y **no sabe escribir**.

    No tiene `registrar_obras_construidas`, ni `marcar_obras_congeladas`, ni
    `execute_sql_text`, ni `truncate_table`. Es el contrato de estos dos
    comandos, y así se comprueba solo.
    """

    def __init__(
        self,
        censo: list[ObraCensada] | None = None,
        filas: dict[str, list] | None = None,
        ultima_completa: datetime | None = _RECIEN,
        revienta: bool = False,
    ) -> None:
        self._censo = censo if censo is not None else []
        self._filas = filas or {}
        # `None` significa «nunca se ha hecho una completa», que es un caso que
        # hay que poder probar. Por eso el default es un centinela y no `None`:
        # confundirlos dejaría sin cubrir justo la denuncia de la base cero.
        self._ultima = (
            datetime.utcnow() if ultima_completa is _RECIEN else ultima_completa
        )
        self._revienta = revienta
        self.consultas: list[str] = []
        self.timeouts: list[int] = []

    def fetch_censo_de_obras(self) -> list[ObraCensada]:
        if self._revienta:
            raise RuntimeError("connection reset by peer")
        return list(self._censo)

    def fetch_ultima_reconstruccion_completa(self, paso: str) -> datetime | None:
        return self._ultima

    def filas_solo_lectura(self, sql: str, timeout_s: int) -> list:
        if self._revienta:
            raise RuntimeError("connection reset by peer")
        self.consultas.append(sql)
        self.timeouts.append(timeout_s)
        if "count(*) FROM _meta.obra_build" in sql:
            return self._filas.get("censo", [(len(self._censo),)])
        if "firma_origen <> firma_actual" in sql:
            return self._filas.get("firma_divergente", [])
        if "NOT EXISTS" in sql:
            return self._filas.get("sin_filas", [])
        return self._filas.get("sello", [])


def obra_viva(obra_id: int = 1, codigo: str = "0710") -> ObraCensada:
    return ObraCensada(
        obra_id=obra_id,
        codigo_obra=codigo,
        estado_id=15,
        ultima_actividad=date.today(),
        tiene_filas=True,
        registrada=True,
        sello_registrado=sello_del_repositorio(),
        firma_origen="f1",
        firma_registrada="f1",
    )


def obra_congelada(obra_id: int = 2, codigo: str = "0599") -> ObraCensada:
    return ObraCensada(
        obra_id=obra_id,
        codigo_obra=codigo,
        estado_id=25,
        ultima_actividad=date(2019, 6, 1),
        tiene_filas=True,
        registrada=True,
        sello_registrado=sello_del_repositorio(),
        firma_origen="f1",
        firma_registrada="f1",
    )


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    def _con(pg):
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        return CliRunner()

    return _con


# ---------------------------------------------------------------------------
# T16 · ventana-plan
# ---------------------------------------------------------------------------


def test_f025_r30_ventana_plan_esta_registrado_con_sus_opciones() -> None:
    resultado = CliRunner().invoke(main.cli, ["ventana-plan", "--help"])

    assert resultado.exit_code == 0
    assert "--detalle" in resultado.output
    assert "--reconstruir-todo" in resultado.output


def test_f025_r30_ventana_plan_separa_lo_que_se_reconstruye_de_lo_congelado(
    cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PG_VENTANA_ACTIVA", "true")
    _sin_cache_de_settings()

    pg = PgSoloLectura(censo=[obra_viva(), obra_congelada()])
    resultado = cli(pg).invoke(main.cli, ["ventana-plan"])

    assert resultado.exit_code == 0
    assert "1 se reconstruirian" in resultado.output
    assert "1 se quedarian" in resultado.output


def test_f025_r30_ventana_plan_con_detalle_nombra_obra_y_motivo(
    cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin el motivo, el «por qué no se actualizó la 0599» es arqueología."""
    monkeypatch.setenv("PG_VENTANA_ACTIVA", "true")
    _sin_cache_de_settings()

    pg = PgSoloLectura(censo=[obra_viva(), obra_congelada()])
    resultado = cli(pg).invoke(main.cli, ["ventana-plan", "--detalle"])

    assert "CONGELAR" in resultado.output
    assert "0599" in resultado.output
    assert "estado 25" in resultado.output


def test_f025_r30_ventana_plan_NO_escribe_nada(  # noqa: N802
    cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**El contrato del dry-run.** El doble no implementa ni un método de
    escritura: si el comando intentara escribir, esto reventaría."""
    monkeypatch.setenv("PG_VENTANA_ACTIVA", "true")
    _sin_cache_de_settings()

    pg = PgSoloLectura(censo=[obra_viva(), obra_congelada()])
    resultado = cli(pg).invoke(main.cli, ["ventana-plan"])

    assert resultado.exit_code == 0
    for escritura in (
        "registrar_obras_construidas",
        "marcar_obras_congeladas",
        "execute_sql_text",
        "truncate_table",
    ):
        assert not hasattr(pg, escritura)


def test_f025_r30_un_censo_VACIO_en_ventana_plan_sale_KO(  # noqa: N802
    cli,
) -> None:
    """Cero obras no es «no hay nada que hacer»: es que no se ha podido mirar.
    Misma regla que el guardián, y por el mismo motivo."""
    resultado = cli(PgSoloLectura(censo=[])).invoke(main.cli, ["ventana-plan"])

    assert resultado.exit_code == 1
    assert "VACIO" in resultado.output


def test_f025_r5_ventana_plan_avisa_de_que_la_ventana_esta_apagada(cli) -> None:
    """Con `PG_VENTANA_ACTIVA=false` —el default— se reconstruye todo. Que el
    comando lo diga evita el susto de leer «920 se reconstruirían» y pensar que
    el criterio no funciona."""
    _sin_cache_de_settings()

    resultado = cli(PgSoloLectura(censo=[obra_congelada()])).invoke(
        main.cli, ["ventana-plan"]
    )

    assert "DESACTIVADA" in resultado.output


# ---------------------------------------------------------------------------
# T18 · check-ventana
# ---------------------------------------------------------------------------


def test_f025_r26_check_ventana_esta_registrado_con_sus_opciones() -> None:
    resultado = CliRunner().invoke(main.cli, ["check-ventana", "--help"])

    assert resultado.exit_code == 0
    assert "--timeout" in resultado.output
    assert "--dry-run" in resultado.output


def test_f025_r27_dry_run_imprime_las_consultas_y_no_abre_conexion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def revienta():
        raise AssertionError("--dry-run ha abierto una conexion")

    monkeypatch.setattr(main, "_get_pg", revienta)

    resultado = CliRunner().invoke(main.cli, ["check-ventana", "--dry-run"])

    assert resultado.exit_code == 0
    assert "_meta.obra_build" in resultado.output
    assert resultado.output.count("--") >= 4


def test_f025_r26_sin_hallazgos_sale_con_cero(cli) -> None:
    pg = PgSoloLectura(censo=[obra_viva()], filas={"censo": [(920,)]})
    resultado = cli(pg).invoke(main.cli, ["check-ventana"])

    assert resultado.exit_code == 0
    assert MARCADOR_KO not in resultado.output


def test_f025_r26_sobre_CERO_obras_sale_KO(cli) -> None:  # noqa: N802
    """**El defecto que este guardián NO reintroduce.** Si
    `_meta.obra_build` está vacía no hay nada que comprobar, y decir OK sería
    confundir «no hay nada malo» con «no he podido mirar». Es lo que le pasó a
    `check-cobertura` contra producción el 2026-09-02."""
    pg = PgSoloLectura(censo=[], filas={"censo": [(0,)]})
    resultado = cli(pg).invoke(main.cli, ["check-ventana"])

    assert resultado.exit_code == 1
    assert MARCADOR_KO in resultado.output
    assert "obras_miradas=0" in resultado.output


def test_f025_r26_una_firma_divergente_se_denuncia_nombrando_la_obra(cli) -> None:
    """La denuncia tiene que decir QUÉ obra: «hay una obra rara» no sirve."""
    pg = PgSoloLectura(
        filas={
            "censo": [(920,)],
            "firma_divergente": [
                (1442383, "0599", datetime(2026, 8, 20), datetime(2026, 9, 3))
            ],
        }
    )
    resultado = cli(pg).invoke(main.cli, ["check-ventana"])

    assert resultado.exit_code == 1
    assert "0599" in resultado.output
    assert "el origen ha cambiado" in resultado.output


def test_f025_r26_una_congelada_sin_filas_se_denuncia(cli) -> None:
    pg = PgSoloLectura(
        filas={
            "censo": [(920,)],
            "sin_filas": [(1442383, "0599", datetime(2026, 8, 20), "ventana")],
        }
    )
    resultado = cli(pg).invoke(main.cli, ["check-ventana"])

    assert resultado.exit_code == 1
    assert "SIN filas" in resultado.output


def test_f025_r26_un_sello_viejo_se_denuncia(cli) -> None:
    pg = PgSoloLectura(
        filas={
            "censo": [(920,)],
            "sello": [(1442383, "0599", datetime(2026, 8, 20), "a" * 64)],
        }
    )
    resultado = cli(pg).invoke(main.cli, ["check-ventana"])

    assert resultado.exit_code == 1
    assert "SELLO" in resultado.output


def test_f025_r26_una_completa_vencida_se_denuncia(cli) -> None:
    """El domingo no corrió y el «hasta 6 días» que el humano aceptó ha dejado
    de ser cierto. Sin esto, las 880 obras podrían quedarse congeladas
    indefinidamente sin que nada chirriara."""
    pg = PgSoloLectura(
        filas={"censo": [(920,)]},
        ultima_completa=datetime(2026, 8, 1),
    )
    resultado = cli(pg).invoke(main.cli, ["check-ventana"])

    assert resultado.exit_code == 1
    assert "VENCIDA" in resultado.output


def test_f025_r26_sin_ninguna_completa_registrada_tambien_se_denuncia(cli) -> None:
    pg = PgSoloLectura(filas={"censo": [(920,)]}, ultima_completa=None)

    assert cli(pg).invoke(main.cli, ["check-ventana"]).exit_code == 1


def test_f025_r27_el_timeout_llega_a_las_consultas(cli) -> None:
    pg = PgSoloLectura(filas={"censo": [(920,)]})
    cli(pg).invoke(main.cli, ["check-ventana", "--timeout", "45"])

    assert pg.timeouts == [45, 45, 45, 45]


def test_f025_r26_un_fallo_leyendo_NO_se_traga_como_OK(cli) -> None:  # noqa: N802
    """Callarlo dejaría una noche en verde sin haber comprobado nada, que es
    literalmente el modo de fallo que este guardián existe para eliminar."""
    resultado = cli(PgSoloLectura(revienta=True)).invoke(main.cli, ["check-ventana"])

    assert resultado.exit_code == 1
    assert "NO es un OK" in resultado.output


def test_f025_r26_las_consultas_van_sobre_obra_build_y_no_barren_el_fact(
    cli,
) -> None:
    """Lo que hace barato correr esto cada noche: cuatro lecturas sobre una
    tabla de una fila por obra. La única que baja a `stg.plan_mensual` lo hace
    con `NOT EXISTS`, que es una sonda de índice."""
    pg = PgSoloLectura(filas={"censo": [(920,)]})
    cli(pg).invoke(main.cli, ["check-ventana"])

    assert len(pg.consultas) == 4
    assert all("_meta.obra_build" in c for c in pg.consultas)
    assert sum("stg.plan_mensual" in c for c in pg.consultas) == 1
    assert not any("mart.fact_seguimiento_mensual" in c for c in pg.consultas)


# ---------------------------------------------------------------------------
# T19 · el enganche a run-all: avisa y NO tumba
# ---------------------------------------------------------------------------


def test_f025_r27_el_guardian_devuelve_su_veredicto_sin_tumbar_nada() -> None:
    """DA-5: `run-all` NO mira este valor para decidir su código de salida. Es
    una decisión con su precio declarado, y el precio es que la regla de
    `infra/97_create_alert_ventana.ps1` es la única vía por la que esto se hace
    oír. **Sin desplegarla, el guardián es mudo.**"""
    pg = PgSoloLectura(
        filas={
            "censo": [(920,)],
            "firma_divergente": [
                (1442383, "0599", datetime(2026, 8, 20), datetime(2026, 9, 3))
            ],
        }
    )

    veredicto = main._guardian_de_ventana(pg)

    assert veredicto is not None
    assert veredicto.codigo == 1


def test_f025_r27_run_all_llama_al_guardian_de_la_ventana() -> None:
    """El enganche está en el código de `run-all`, después del de F-052 y del de
    F-047. Si alguien lo quita, la ventana deja de vigilarse y nadie se entera
    hasta que una obra lleve meses vieja."""
    import inspect

    fuente = inspect.getsource(main.run_all.callback)

    assert "_guardian_de_ventana" in fuente
    assert fuente.index("_guardian_de_cobertura") < fuente.index("_guardian_de_ventana")


def test_f025_r27_el_guardian_de_la_ventana_NO_entra_en_el_codigo_de_salida() -> None:  # noqa: N802
    """El test que fija DA-5. `run-all` sale con 1 por pasos fallidos o por el
    guardián de lo declarado (F-047), nunca por este."""
    import inspect

    fuente = inspect.getsource(main.run_all.callback)
    salida = fuente[fuente.index("failed = sum") :]

    assert "_guardian_de_ventana" not in salida
    assert "guardian_ok" in salida


def test_f025_r27_un_fallo_leyendo_dentro_de_run_all_devuelve_None() -> None:
    """No escala, pero se imprime: callarlo dejaría una noche en verde sin haber
    comprobado nada."""
    assert main._guardian_de_ventana(PgSoloLectura(revienta=True)) is None


# ---------------------------------------------------------------------------
# T15 · --reconstruir-todo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("comando", ["run-all", "stage"])
def test_f025_r25_el_flag_de_reconstruccion_completa_existe(comando: str) -> None:
    """R25: la completa se dispara sola los domingos, por antigüedad
    registrada. Este flag es para forzarla a mano."""
    resultado = CliRunner().invoke(main.cli, [comando, "--help"])

    assert resultado.exit_code == 0
    assert "--reconstruir-todo" in resultado.output


def test_f025_r25_el_flag_llega_al_step_desde_run_all() -> None:
    import inspect

    fuente = inspect.getsource(main.build_pipeline_steps)

    assert "reconstruir_todo=reconstruir_todo" in fuente


def test_f025_r25_el_flag_llega_al_step_desde_stage() -> None:
    import inspect

    assert "reconstruir_todo=reconstruir_todo" in inspect.getsource(main.stage.callback)


def _sin_cache_de_settings() -> None:
    """`get_settings` es un singleton con `lru_cache`: sin vaciarlo, el cambio
    de variable de entorno no llega."""
    from config.settings import get_settings

    get_settings.cache_clear()
