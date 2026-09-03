# tests/test_f025_build.py
"""
F-025 · El build que NO borra lo que no reconstruye (R9-R13, T10-T14).

**Este es el fichero que protege la frase del humano**: *«que no se
reconstruyan, pero que **no se borren**, y que la información esté
consultable»*.

## Por qué el `TRUNCATE` era el enemigo

El vaciado de `stg.plan_mensual` **no está dentro del SQL troceado**: lo lanzaba
el step una sola vez, antes de los 60 tramos (en el log de la nocturna que
murió, `table_truncated` a las 03:23). Pasarle solo las obras vivas al troceado
de F-019 tal cual **habría vaciado la tabla y dejado 40 obras de 920**. Eso es
exactamente lo que el humano prohíbe, y por eso el borrado ahora se **deriva de
lo que se va a escribir**: cada tramo borra sus obras y las reinserta en la
misma transacción, así que es imposible borrar una obra que luego no se
reescriba.

## Y repara la avería de paso

La nocturna del 02-sep habría acabado con cinco obras al día y el resto con el
dato de anoche —coherente— en vez de con la tabla al 21,6 % —truncada—. Eso vale
por sí solo aunque el acotado no ahorrase nada, y es lo que prueba
`test_f025_r13_un_tramo_que_falla_NO_vacia_la_tabla`.

**Estos tests cambian una invariante de F-019 a propósito** (R13). Los de allí
exigían que abortar dejase la tabla VACÍA, porque una tabla a medias era
indistinguible de una completa. Con el borrado derivado eso ya no es cierto: lo
que queda no es «media tabla», son obras enteras con su última versión buena, y
vaciarlas destruiría lo congelado. Los tests de F-019 se han actualizado a la
invariante nueva, no relajado.

Con doble de `PostgresClient`: ni red ni BBDD.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    MARCADOR_FILTRO_OBRAS,
    MARCADOR_FILTRO_PRESUPUESTO,
    RAMAS_CON_FILTRO,
    BuildStgStep,
    componer_borrado_derivado,
    componer_sql_presupuesto,
    componer_sql_tramo,
)
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.domain.ventana import ObraCensada
from tests.test_f019_tramos import LoggerFalso


def sello_real() -> str:
    """El sello que el step calcula de verdad sobre los SQL del repositorio.

    Usarlo aquí no es un atajo: si el censo llevara un sello inventado, TODAS
    las obras entrarían por R17 y estos tests estarían midiendo el mecanismo
    del sello en vez del criterio de la ventana. Y de paso ejercita
    `_sello_vigente` contra los ficheros reales.
    """
    paso = BuildStgStep(settings_falsos())
    return paso._sello_vigente()


# ---------------------------------------------------------------------------
# La composición del borrado derivado, sin step ni cliente
# ---------------------------------------------------------------------------


def test_f025_r10_el_borrado_nombra_solo_las_obras_que_se_van_a_escribir() -> None:
    """**La propiedad que lo sostiene todo**: el conjunto que se borra ES el que
    se va a escribir. No hay dos listas que puedan desincronizarse."""
    borrado = componer_borrado_derivado("plan_mensual", [7, 9])

    assert "DELETE FROM stg.plan_mensual" in borrado
    assert "ARRAY[7, 9]::BIGINT[]" in borrado


def test_f025_r10_el_borrado_va_por_obra_id_que_es_el_prefijo_del_indice() -> None:
    """`idx_plan_mensual_obra_amb` e `idx_pres_obra_amb` empiezan los dos por
    `obra_id` (verificado contra `pg_indexes`): el `DELETE` no barre la tabla."""
    assert re.search(
        r"WHERE\s+obra_id\s*=\s*ANY", componer_borrado_derivado("presupuesto", [1])
    )


@pytest.mark.parametrize("obras", [[True], ["1"], [1.0], [None]])
def test_f025_r10_el_borrado_solo_admite_enteros(obras: list) -> None:
    """Mismo blindaje que el filtro de tramos de F-019: la composición es
    TEXTUAL, así que nada que no sea un entero validado puede concatenarse.
    `True` no cuenta como entero aunque Python lo considere subclase de `int`."""
    with pytest.raises(TypeError):
        componer_borrado_derivado("plan_mensual", obras)


def test_f025_r10_un_borrado_sin_obras_no_se_compone() -> None:
    """Un `ARRAY[]` vacío no borraría nada útil y delata un plan roto."""
    with pytest.raises(ValueError, match="sin obras"):
        componer_borrado_derivado("plan_mensual", [])


def test_f025_r10_el_borrado_solo_alcanza_a_las_tablas_acotadas() -> None:
    """El nombre de la tabla se interpola: no puede venir de fuera."""
    with pytest.raises(ValueError, match="no acotada"):
        componer_borrado_derivado("obras", [1])


def test_f025_r10_el_tramo_BORRA_y_luego_inserta_en_la_misma_transaccion() -> None:  # noqa: N802
    """Las dos sentencias viajan en el mismo texto, y `execute_sql_text` abre
    una conexión —una transacción— por llamada. Si el proceso muere entre las
    dos, no se ha perdido nada: la transacción no llegó a confirmarse."""
    compuesto = componer_sql_tramo(
        "SELECT /*F019_FILTRO_OBRAS*/ /*F019_FILTRO_OBRAS*/", [4]
    )

    assert compuesto.index("DELETE FROM stg.plan_mensual") < compuesto.index("SELECT")
    assert "TRUNCATE" not in compuesto.upper()


def test_f025_r10_el_tramo_borra_EXACTAMENTE_las_obras_que_filtra() -> None:  # noqa: N802
    """Si el `DELETE` y el `WHERE` del `INSERT` nombraran conjuntos distintos,
    se borrarían obras que nadie va a reescribir. Se componen del mismo dato."""
    compuesto = componer_sql_tramo(
        "SELECT /*F019_FILTRO_OBRAS*/ /*F019_FILTRO_OBRAS*/", [4, 8]
    )

    assert compuesto.count("ARRAY[4, 8]::BIGINT[]") == RAMAS_CON_FILTRO + 1


def test_f025_r11b_el_presupuesto_se_compone_con_su_propio_marcador() -> None:
    """`06_presupuesto.sql` no tiene ramas: su `WHERE` es uno solo, y el
    marcador se llama distinto para que nadie sustituya uno por otro."""
    compuesto = componer_sql_presupuesto(
        "INSERT ... WHERE pp.obride = ANY (/*F025_FILTRO_OBRAS*/)", [3]
    )

    assert MARCADOR_FILTRO_PRESUPUESTO not in compuesto
    assert "ARRAY[3]::BIGINT[]" in compuesto
    assert compuesto.startswith("DELETE FROM stg.presupuesto")


def test_f025_r11b_sin_marcador_el_presupuesto_no_se_ejecuta() -> None:
    """Igual que en F-019: si alguien borra el marcador al editar el fichero,
    esto falla ANTES de enviar nada, en vez de reconstruir las 920 obras."""
    with pytest.raises(ValueError, match="marcador"):
        componer_sql_presupuesto("INSERT ... WHERE 1=1", [3])


def test_f025_r11b_un_marcador_repetido_tampoco_cuela() -> None:
    doble = "A /*F025_FILTRO_OBRAS*/ B /*F025_FILTRO_OBRAS*/"

    with pytest.raises(ValueError, match="marcador"):
        componer_sql_presupuesto(doble, [3])


# ---------------------------------------------------------------------------
# El SQL del repositorio, tal y como está escrito
# ---------------------------------------------------------------------------


def sql_de(nombre: str) -> str:
    from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG

    return (DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8")


def test_f025_r10_el_presupuesto_ya_no_lleva_TRUNCATE() -> None:  # noqa: N802
    """**El cambio de fondo en `06_presupuesto.sql`.** Su `TRUNCATE` sí estaba
    dentro del fichero, y con la ventana encendida habría dejado 40 obras."""
    codigo = sin_comentarios_sql(sql_de("06_presupuesto.sql"))

    assert "TRUNCATE" not in codigo.upper()


def test_f025_r10_el_plan_mensual_sigue_sin_TRUNCATE() -> None:  # noqa: N802
    """Lo quitó F-019 y esta feature no lo devuelve."""
    assert "TRUNCATE" not in sin_comentarios_sql(sql_de("08_plan_mensual.sql")).upper()


def test_f025_r11b_el_presupuesto_declara_su_marcador_UNA_vez() -> None:  # noqa: N802
    assert sql_de("06_presupuesto.sql").count(MARCADOR_FILTRO_PRESUPUESTO) == 1


def test_f025_r11b_el_marcador_del_presupuesto_va_en_un_ANY() -> None:  # noqa: N802
    """Va como comentario SQL a propósito: un fichero al que le falte la
    sustitución **no es SQL válido** (`= ANY ()`), así que no puede colarse una
    ejecución sin filtro por descuido. Misma defensa que F-019."""
    assert re.search(
        r"=\s*ANY\s*\(\s*/\*F025_FILTRO_OBRAS\*/\s*\)", sql_de("06_presupuesto.sql")
    )


def test_f025_r7_la_logica_del_presupuesto_no_cambia() -> None:
    """«Ni una línea de su lógica cambia» (§10 del diseño). El `DISTINCT ON` y
    el redondeo por decimales de obra son lo que hace que el importe cuadre al
    céntimo con la pantalla de Sigrid."""
    sql = sql_de("06_presupuesto.sql")

    assert "DISTINCT ON (pp.obride, pp.paride, pp.amb, COALESCE(pp.fas, 0))" in sql
    assert "COALESCE(o.decp::INT, 2)" in sql
    assert "NULLIF(pp.impcoe::NUMERIC(18,2), 0)" in sql


def test_f025_r8_el_corte_por_obra_del_presupuesto_es_seguro() -> None:
    """Su `DISTINCT ON` **empieza por la obra**, así que ninguna deduplicación
    cruza obras y el resultado filtrado es idéntico al de una pasada entera.
    Es la misma propiedad estructural que hace seguro el troceado de F-019."""
    orden = re.search(r"DISTINCT ON \(([^)]*\)?[^)]*)\)", sql_de("06_presupuesto.sql"))

    assert orden is not None
    assert orden.group(1).strip().startswith("pp.obride")


def sin_comentarios_sql(texto: str) -> str:
    utiles = [
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    ]
    return chr(10).join(utiles)


# ---------------------------------------------------------------------------
# El step entero, con doble de cliente
# ---------------------------------------------------------------------------

TABLAS_DEL_YAML_FALSO = ("con", "obr", "obrparpre")


class PgVentana:
    """Doble de `PostgresClient` que deja traza de todo lo que le piden.

    No hereda del cliente real a propósito: si el step llamara a un método que
    este doble no implementa, el test tiene que fallar, no acabar en una
    conexión de verdad.
    """

    def __init__(
        self,
        censo: list[ObraCensada] | None = None,
        pesos: dict[int, int] | None = None,
        tramo_que_falla: int | None = None,
        vacuum_revienta: bool = False,
        ultima_completa: datetime | None = datetime(2026, 9, 1, 2, 0),
    ) -> None:
        self._censo = censo if censo is not None else censo_por_defecto()
        self.pesos = pesos if pesos is not None else {1: 10, 2: 10, 3: 10}
        self._tramo_que_falla = tramo_que_falla
        self._vacuum_revienta = vacuum_revienta
        self._ultima_completa = ultima_completa

        self.traza: list[str] = []
        self.truncados: list[tuple[str, str]] = []
        self.sql_ejecutado: list[str] = []
        self.ficheros_ejecutados: list[str] = []
        self.pasos_registrados: list[str] = []
        self.cierres: list[tuple] = []
        self.construidas: list[dict] = []
        self.congeladas: list[dict] = []
        self.vacuums: list[tuple[str, str]] = []
        self.obras_sobrantes_pedidas: list[str] = []
        self.hitos: list[dict] = []
        self._ultimo_run = 0

    # --- la ventana ---
    def fetch_censo_de_obras(self) -> list[ObraCensada]:
        self.traza.append("censo")
        return list(self._censo)

    def fetch_ultima_reconstruccion_completa(self, paso: str) -> datetime | None:
        return self._ultima_completa

    def fetch_obras_con_filas(self, tabla: str) -> set[int]:
        """Qué obras tienen hoy filas en cada tabla.

        `plan_mensual` se construye DESDE `stg.presupuesto`, así que solo tiene
        filas de las obras que pesan. Modelarlo así y no devolver el censo
        entero importa: si no, la limpieza de sobrantes creería que hay que
        borrar obras que nunca tuvieron filas.
        """
        self.obras_sobrantes_pedidas.append(tabla)
        if tabla == "plan_mensual":
            return set(self.pesos)
        return {o.obra_id for o in self._censo}

    def registrar_obras_construidas(self, registros) -> int:
        self.traza.append("registrar")
        self.construidas.extend(registros)
        return len(registros)

    def marcar_obras_congeladas(self, registros) -> int:
        self.traza.append("congelar")
        self.congeladas.extend(registros)
        return len(registros)

    def fetch_filas_por_obra(self, tabla: str, obras) -> dict[int, int]:
        return {int(o): 100 for o in obras}

    def vacuum_analyze(self, schema: str, table: str) -> None:
        self.traza.append("vacuum")
        self.vacuums.append((schema, table))
        if self._vacuum_revienta:
            raise RuntimeError("VACUUM cannot run inside a transaction block")

    # --- lo que ya usaba F-019 ---
    def fetch_pesos_plan_mensual(self) -> dict[int, int]:
        self.traza.append("pesos")
        return dict(self.pesos)

    def truncate_table(self, schema: str, table: str) -> None:
        self.traza.append("truncate")
        self.truncados.append((schema, table))

    def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
        self.traza.append("medicion")
        return 10.0

    def execute_sql_text(self, sql_text: str) -> int:
        self.traza.append("sql")
        self.sql_ejecutado.append(sql_text)
        if len(self.sql_ejecutado) == self._tramo_que_falla:
            raise RuntimeError("could not extend file: No space left on device")
        return 700

    def record_run_start(self, stage: str, step: str, batch_id: str | None = None) -> int:
        self.pasos_registrados.append(step)
        self._ultimo_run += 1
        return self._ultimo_run

    def record_run_end(
        self, run_id: int, status: str, rows_processed: int = 0,
        error_message: str | None = None,
    ) -> None:
        self.cierres.append((run_id, status, rows_processed, error_message))

    def record_run_completed(self, **kwargs: object) -> int:
        self.traza.append("hito")
        self.hitos.append(kwargs)
        return 0

    def fetch_estado_raw(self) -> list:
        from etl_sigrid.domain.coherencia import EstadoTablaRaw

        return [
            EstadoTablaRaw(
                tabla=tabla, status="SUCCESS", batch_id="20260903T020000Z-f025aa",
                started_at=datetime(2026, 9, 3, 2, 0),
                finished_at=datetime(2026, 9, 3, 2, 30), filas=10,
            )
            for tabla in TABLAS_DEL_YAML_FALSO
        ]

    def execute_sql_file(self, path: object, params: object = None) -> None:
        self.traza.append("fichero")
        self.ficheros_ejecutados.append(getattr(path, "name", str(path)))

    def count_rows(self, schema: str, table: str) -> int:
        return 0

    def assert_columns_exist(self, schema: str, table: str, columnas: list[str]) -> None:
        return None


def censo_por_defecto() -> list[ObraCensada]:
    """Tres obras: una viva y dos congeladas (CERRADA y administrativa)."""
    comun = {
        "tiene_filas": True,
        "registrada": True,
        "sello_registrado": sello_real(),
        "firma_origen": "f1",
        "firma_registrada": "f1",
    }
    return [
        ObraCensada(1, "0710", estado_id=15,
                    ultima_actividad=date(2026, 8, 1), **comun),
        ObraCensada(2, "0599", estado_id=25,
                    ultima_actividad=date(2019, 6, 1), **comun),
        ObraCensada(3, "201503", estado_id=15,
                    ultima_actividad=date(2019, 6, 1), **comun),
    ]


def settings_falsos(ventana_activa: bool = True, **extra: object) -> SimpleNamespace:
    postgres = {
        "tramo_max_filas": 1_000_000,
        "disco_total_gb": 32,
        "disco_limite_pct": 80.0,
        "ventana_activa": ventana_activa,
        "ventana_meses": 12,
        "ventana_dia_completa": 6,
        "ventana_rescate": False,
    }
    postgres.update(extra)
    return SimpleNamespace(
        postgres=SimpleNamespace(**postgres),
        business_rules={
            "sigrid": {"campos_extendidos": {"cod_version_master_vigente": "15"}},
            "ventana": {
                "estados_que_congelan": [1, 11, 25],
                "patron_codigo_administrativo": "^[0-9]{6}$",
                "meses_sin_actividad": 12,
            },
        },
        tables_sigrid={"tables": [{"source_table": t} for t in TABLAS_DEL_YAML_FALSO]},
    )


def ejecutar(pg: PgVentana, monkeypatch, **kwargs):
    import etl_sigrid.application.steps.build_stg_step as modulo

    monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: pg)
    paso = BuildStgStep(settings_falsos(**kwargs), batch_id="20260903T020000Z-f025aa")
    return paso.run()


# --- R10, R13 · el TRUNCATE ha desaparecido ---------------------------------


def test_f025_r10_el_build_NO_llama_a_truncate_para_las_tablas_acotadas(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**El test de T10.** Mientras exista una sola llamada a `truncate_table`
    sobre estas dos tablas, «no se borran» es mentira."""
    pg = PgVentana()
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.SUCCESS
    assert pg.truncados == []
    assert "truncate" not in pg.traza


def test_f025_r10_cada_tramo_borra_e_inserta_sus_obras(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    tramos = [s for s in pg.sql_ejecutado if MARCADOR_FILTRO_OBRAS not in s]
    assert tramos, "no se ejecutó ningún tramo"
    for sql in tramos:
        assert "DELETE FROM stg." in sql
        # Sin comentarios: el propio SQL EXPLICA en su cabecera el `TRUNCATE`
        # que se retiró, y buscar la palabra en el texto crudo se dispararía
        # con la frase que dice por qué ya no está.
        assert "TRUNCATE" not in sin_comentarios_sql(sql).upper()


def test_f025_r13_un_tramo_que_falla_NO_vacia_la_tabla(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**La invariante que cambia respecto a F-019, y el porqué.** Allí abortar
    vaciaba la tabla porque una tabla a medias era indistinguible de una
    completa. Ahora lo que queda no es media tabla: son obras enteras con su
    última versión buena, y vaciarlas destruiría lo congelado.

    Es también la reparación de la avería del 02-sep: esa noche habría acabado
    con cinco obras al día y el resto con el dato de anoche, en vez de con la
    tabla al 21,6 %."""
    pg = PgVentana(pesos={1: 10, 2: 10}, tramo_que_falla=2)
    resultado = ejecutar(pg, monkeypatch, ventana_activa=False)

    assert resultado.status is StepStatus.FAILED
    assert pg.truncados == []
    assert "truncate" not in pg.traza


def test_f025_r13_el_fallo_dice_QUE_obras_se_han_quedado_sin_reconstruir(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R13 lo exige: «se registra cuáles faltan». Sin eso, quien mire la mañana
    siguiente sabe que falló pero no qué obras llevan el dato de ayer."""
    import etl_sigrid.application.steps.build_stg_step as modulo

    registro = LoggerFalso()
    monkeypatch.setattr(modulo, "logger", registro)

    pg = PgVentana(pesos={1: 10, 2: 10}, tramo_que_falla=2)
    ejecutar(pg, monkeypatch, ventana_activa=False)

    eventos = registro.de("plan_mensual_abortado")
    assert eventos, "el aborto no deja evento estructurado"
    assert "obras_sin_reconstruir" in eventos[0]


def test_f025_r13_el_aborto_conserva_lo_ya_construido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los tramos que sí terminaron quedan registrados: la noche siguiente no
    los repite por R18 y el dato de esas obras es del día."""
    pg = PgVentana(pesos={1: 10, 2: 10}, tramo_que_falla=2)
    ejecutar(pg, monkeypatch, ventana_activa=False)

    assert pg.construidas, "no se registró el tramo que sí terminó"


# --- R9 · Un conjunto vacío no toca la tabla --------------------------------


def test_f025_r9_sin_obras_que_reconstruir_no_se_toca_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R9 literal: «SI el conjunto a reconstruir queda vacío, ENTONCES el
    sub-paso termina en SUCCESS sin ejecutar tramos y SIN TOCAR LA TABLA»."""
    todas_congeladas = [
        o for o in censo_por_defecto() if o.codigo_obra in ("0599", "201503")
    ]
    pg = PgVentana(censo=todas_congeladas, pesos={2: 10, 3: 10})
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.SUCCESS
    assert pg.sql_ejecutado == []
    assert pg.truncados == []


def test_f025_r9_con_el_conjunto_vacio_las_congeladas_igual_se_registran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No tocar la tabla no significa no dejar constancia: si no se escribiera
    el motivo, una noche sin trabajo sería indistinguible de una noche en la
    que el guardián no miró."""
    todas_congeladas = [
        o for o in censo_por_defecto() if o.codigo_obra in ("0599", "201503")
    ]
    pg = PgVentana(censo=todas_congeladas, pesos={2: 10, 3: 10})
    ejecutar(pg, monkeypatch)

    assert {r["codigo_obra"] for r in pg.congeladas} == {"0599", "201503"}


# --- R5 · Con la ventana apagada, el comportamiento es el de hoy ------------


def test_f025_r5_con_la_ventana_apagada_se_reconstruyen_TODAS(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El contenido publicado es el mismo que hoy: todas las obras. Lo que NO
    vuelve es el `TRUNCATE`, porque el borrado derivado de todas las obras deja
    exactamente el mismo resultado y además sobrevive a un tramo que falle."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch, ventana_activa=False)

    assert {r["obra_id"] for r in pg.construidas} == {1, 2, 3}
    assert pg.congeladas == []
    assert pg.truncados == []


def test_f025_r5_apagada_no_congela_ni_una_obra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = PgVentana()
    ejecutar(pg, monkeypatch, ventana_activa=False)

    for registro in pg.construidas:
        assert registro["motivo"] == "completa"


# --- R6, DA-2 · Las dos tablas se acotan igual ------------------------------


def test_f025_r6_el_presupuesto_tambien_se_acota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DA-2: el humano decidió acotar también `build_presupuesto`, contra la
    recomendación de la spec. Va con el mismo mecanismo y de una sola pasada."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    presupuesto = [
        s for s in pg.sql_ejecutado if s.startswith("DELETE FROM stg.presupuesto")
    ]
    assert len(presupuesto) == 1, "de una sola pasada, no por tramos"
    assert "ARRAY[1]::BIGINT[]" in presupuesto[0]
    assert "INSERT INTO stg.presupuesto" in presupuesto[0], (
        "el borrado y la insercion tienen que viajar en la MISMA transaccion"
    )


def test_f025_r6_el_presupuesto_ya_no_va_por_execute_sql_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si siguiera ejecutándose como fichero, se ejecutaría sin sustituir el
    marcador y no sería SQL válido."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    assert "06_presupuesto.sql" not in pg.ficheros_ejecutados


def test_f025_r7_el_resto_de_stg_sigue_ejecutandose_entero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R7: `00`-`05` y `07` no los toca esta feature."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    for fichero in (
        "00_functions.sql", "01_ddl.sql", "02_ambitos.sql", "03_obras.sql",
        "04_partidas.sql", "05_fases.sql", "07_version_master_vigente.sql",
    ):
        assert fichero in pg.ficheros_ejecutados


def test_f025_r1_el_plan_se_compone_DESPUES_de_construir_las_fases(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La regla de actividad se mide sobre `stg.fases`. Componer el plan antes
    de `05_fases.sql` lo calcularía con las fases de anoche."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    assert pg.ficheros_ejecutados.index("05_fases.sql") < pg.traza.index("censo")


# --- R14 · El VACUUM, y que un fallo suyo no tumbe la noche -----------------


def test_f025_r14_al_terminar_se_hace_vacuum_de_las_dos_tablas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El borrado derivado deja tuplas muertas cada noche en un servidor donde
    el autovacuum llega tarde (§9.1 del diseño)."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    assert set(pg.vacuums) == {("stg", "plan_mensual"), ("stg", "presupuesto")}


def test_f025_r14_un_vacuum_que_falla_avisa_pero_NO_tumba_la_noche(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El `VACUUM` es higiene, no producto. Tumbar por él dejaría sin datamart
    una noche entera por no haber podido limpiar tuplas muertas."""
    pg = PgVentana(vacuum_revienta=True)
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.SUCCESS


# --- R30 · Los recuentos en _meta.etl_runs ----------------------------------


def test_f025_r30_el_paso_registra_cuantas_reconstruye_y_cuantas_congela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R30: sin estos dos números no se puede medir el ahorro, y medir el
    ahorro es el criterio por el que esta feature existe."""
    pg = PgVentana()
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.metadata["obras_reconstruidas"] == 1
    assert resultado.metadata["obras_congeladas"] == 2


def test_f025_r30_el_plan_de_la_ventana_tiene_su_fila_en_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Como la puerta de F-024: aparece en `timings` con su duración y deja
    constancia escrita de qué se decidió esa noche."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    assert "build_stg.plan_ventana" in pg.pasos_registrados


# --- R14 · El registro por obra ---------------------------------------------


def test_f025_r14_cada_obra_reconstruida_registra_su_procedencia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    registro = next(r for r in pg.construidas if r["obra_id"] == 1)
    assert registro["batch_id"] == "20260903T020000Z-f025aa"
    assert registro["construido_at"] is not None
    assert registro["sello_sql"]
    assert registro["motivo"]
    assert registro["detalle"]


def test_f025_r16_la_obra_reconstruida_guarda_la_firma_de_ESTA_noche(  # noqa: N802
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`firma_origen` pasa a ser la del origen de ahora: es lo que hace que la
    comparación de la noche siguiente signifique «cambió desde que la
    construí»."""
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    assert next(r for r in pg.construidas if r["obra_id"] == 1)["firma_origen"] == "f1"


def test_f025_r14_cada_obra_congelada_deja_escrito_su_motivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = PgVentana()
    ejecutar(pg, monkeypatch)

    for registro in pg.congeladas:
        assert registro["motivo"] == "ventana"
        assert registro["detalle"].strip()
