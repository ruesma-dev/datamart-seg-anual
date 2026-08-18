# tests/test_f024_dominio.py
"""
F-024 · Tests del dominio puro: identidad de ejecución (R1) y veredicto de
coherencia (R8, R9).

NINGÚN test de este fichero abre red ni BBDD. Todo lo que se prueba aquí son
funciones puras: reciben datos y devuelven datos. Es a propósito, y es la
razón de que la decisión de «construir o negarse» viva en el dominio y no
dentro de un step: así se puede comprobar exhaustivamente sin un servidor
delante.
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from etl_sigrid.domain.coherencia import (
    EstadoPaso,
    EstadoTablaRaw,
    VeredictoCoherencia,
    evaluar_coherencia_raw,
    evaluar_coherencia_stg,
    formatear_veredicto_raw,
    formatear_veredicto_stg,
)
from etl_sigrid.domain.ejecucion import (
    BYTES_DEL_SUFIJO,
    FORMATO_INSTANTE,
    MOTIVO_HUERFANA,
    Ejecucion,
    nueva_ejecucion,
)
from etl_sigrid.domain.entities import StepStatus

# La forma exacta que exige R1: UTC compacto + guion + 6 hexadecimales. Se
# escribe aquí como literal y no derivada del código para que un cambio en el
# formato tenga que pasar por este test: el `batch_id` acaba en `_meta` de
# producción y en las consultas del MCP, no es un detalle interno.
FORMA_BATCH = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")


# ---------------------------------------------------------------------------
# R1 · Cada ejecución tiene un identificador único
# ---------------------------------------------------------------------------


def test_f024_r1_batch_id_tiene_forma_y_es_unico() -> None:
    """Forma `YYYYMMDDTHHMMSSZ-xxxxxx` y sin colisiones dentro del proceso."""
    ejecucion = nueva_ejecucion()

    assert FORMA_BATCH.match(ejecucion.batch_id), (
        f"batch_id fuera de forma: {ejecucion.batch_id!r}"
    )

    # 500 en el mismo segundo: el sufijo es lo único que las distingue, así que
    # esto comprueba de verdad que hay aleatoriedad y cuánta.
    lote = {nueva_ejecucion().batch_id for _ in range(500)}
    assert len(lote) == 500, "hay batch_id repetidos dentro del mismo proceso"


def test_f024_r1_el_sufijo_aleatorio_mide_seis_hexadecimales() -> None:
    """Seis, ni cinco ni ocho: es lo que fija la forma de R1 y lo que da
    16,7 millones de combinaciones por segundo."""
    assert BYTES_DEL_SUFIJO == 3  # 3 bytes = 6 caracteres hex

    sufijo = nueva_ejecucion().batch_id.split("-")[1]
    assert len(sufijo) == 6
    assert set(sufijo) <= set("0123456789abcdef")


def test_f024_r1_batch_id_ordena_cronologicamente() -> None:
    """Como TEXTO. Es lo que permite `ORDER BY batch_id` sin parsear nada."""
    instantes = [
        datetime(2026, 1, 1, 0, 0, 0),
        datetime(2026, 1, 1, 0, 0, 1),
        datetime(2026, 1, 1, 0, 1, 0),
        datetime(2026, 1, 1, 1, 0, 0),
        datetime(2026, 1, 2, 0, 0, 0),
        datetime(2026, 2, 1, 0, 0, 0),
        datetime(2027, 1, 1, 0, 0, 0),
    ]
    batches = [nueva_ejecucion(ahora=t, sufijo="aaaaaa").batch_id for t in instantes]

    assert batches == sorted(batches)
    # Y estrictamente creciente: dos instantes distintos no dan el mismo texto.
    assert len(set(batches)) == len(batches)


def test_f024_r1_el_instante_inyectado_manda_sobre_el_reloj() -> None:
    """`ahora` y `sufijo` se inyectan para que el resultado sea comprobable."""
    momento = datetime(2026, 8, 18, 2, 0, 5)
    ejecucion = nueva_ejecucion(ahora=momento, sufijo="0f1e2d")

    assert ejecucion.batch_id == "20260818T020005Z-0f1e2d"
    assert ejecucion.iniciada_en == momento
    assert momento.strftime(FORMATO_INSTANTE) == "20260818T020005Z"


def test_f024_r1_sin_instante_se_usa_el_reloj_utc() -> None:
    """Sin `ahora`, la marca es la de este momento en UTC (no la local)."""
    antes = datetime.utcnow()
    ejecucion = nueva_ejecucion()
    despues = datetime.utcnow()

    assert antes <= ejecucion.iniciada_en <= despues
    assert ejecucion.batch_id.startswith(ejecucion.iniciada_en.strftime(FORMATO_INSTANTE))


def test_f024_r1_la_ejecucion_es_inmutable() -> None:
    """Una vez creada no se le cambia el batch: todas las filas de esa
    ejecución tienen que compartir el mismo, y un objeto mutable invita a
    reasignarlo a mitad de una carga."""
    ejecucion = nueva_ejecucion(ahora=datetime(2026, 8, 18), sufijo="abc123")

    with pytest.raises(FrozenInstanceError):
        ejecucion.batch_id = "otro"  # type: ignore[misc]


def test_f024_r1_dos_ejecuciones_iguales_son_iguales() -> None:
    """Dataclass con igualdad por valor: lo que permite compararlas en tests
    y meterlas en un conjunto sin sorpresas."""
    momento = datetime(2026, 8, 18, 2, 0, 0)
    una = Ejecucion(batch_id="20260818T020000Z-aaaaaa", iniciada_en=momento)
    otra = nueva_ejecucion(ahora=momento, sufijo="aaaaaa")

    assert una == otra
    assert len({una, otra}) == 1


# ---------------------------------------------------------------------------
# R4 (vocabulario) · el motivo de la marca de huérfana y el estado ABORTED
# ---------------------------------------------------------------------------


def test_f024_r4_el_motivo_de_huerfana_nombra_ejecucion_e_instante() -> None:
    """El `error_message` tiene que decir QUIÉN la marcó y CUÁNDO: sin eso,
    una fila ABORTED es indistinguible de un fallo real del paso."""
    motivo = MOTIVO_HUERFANA.format(
        batch_id="20260818T020000-abc123", ahora="2026-08-19 07:31:02"
    )

    assert "20260818T020000-abc123" in motivo
    assert "2026-08-19 07:31:02" in motivo
    assert "huérfana" in motivo
    # Y por qué pasó: es lo que se lee a las 8 de la mañana sin más contexto.
    for pista in ("deadline", "OOM", "reinicio"):
        assert pista in motivo, f"el motivo no menciona '{pista}'"

    # La plantilla no deja marcadores sin sustituir.
    assert "{" not in motivo and "}" not in motivo


def test_f024_r4_aborted_es_parte_del_vocabulario_de_estados() -> None:
    """`ABORTED` no es una cadena suelta: es un `StepStatus` como los demás,
    y es lo que escribe el SQL de la marca a través de `.value`."""
    assert StepStatus.ABORTED.value == "ABORTED"
    assert StepStatus("ABORTED") is StepStatus.ABORTED
    # No sustituye a ninguno de los que ya había.
    assert {s.value for s in StepStatus} == {
        "PENDING", "RUNNING", "SUCCESS", "FAILED", "SKIPPED", "ABORTED",
    }


# ---------------------------------------------------------------------------
# R8 · Veredicto de coherencia de `raw` (dominio puro)
# ---------------------------------------------------------------------------

# Tres tablas declaradas: lo mínimo para poder observar «una falla y las otras
# no», «una viene de otro batch» y «una no está».
REQUERIDAS = ("con", "obr", "obrparpre")

BATCH_BUENO = "20260818T020000Z-aaaaaa"
BATCH_VIEJO = "20260817T020000Z-bbbbbb"


def estado(
    tabla: str,
    status: str = "SUCCESS",
    batch_id: str | None = BATCH_BUENO,
    fin: datetime | None = None,
    filas: int = 1_000,
) -> EstadoTablaRaw:
    """Una fila de `_meta.v_raw_state` como la ve el dominio."""
    return EstadoTablaRaw(
        tabla=tabla,
        status=status,
        batch_id=batch_id,
        started_at=datetime(2026, 8, 18, 2, 0, 0),
        finished_at=fin if fin is not None else datetime(2026, 8, 18, 2, 30, 0),
        filas=filas,
    )


def todas_bien() -> list[EstadoTablaRaw]:
    return [estado(t) for t in REQUERIDAS]


def test_f024_r8_ok_cuando_todas_del_mismo_batch_success() -> None:
    """La noche normal: ingesta completa, todo SUCCESS, un solo batch."""
    veredicto = evaluar_coherencia_raw(todas_bien(), REQUERIDAS)

    assert veredicto.ok is True
    assert veredicto.batch_id == BATCH_BUENO
    assert veredicto.faltantes == ()
    assert veredicto.no_exitosas == ()
    assert veredicto.sin_batch == ()
    assert veredicto.batches_distintos == ()


def test_f024_r8_ko_si_falta_una_tabla() -> None:
    """Una tabla declarada que nunca se ingirió (típico: se añadió al YAML)."""
    veredicto = evaluar_coherencia_raw([estado("con"), estado("obr")], REQUERIDAS)

    assert veredicto.ok is False
    assert veredicto.batch_id is None
    assert veredicto.faltantes == ("obrparpre",)
    # Las que sí están y están bien no se acusan de nada.
    assert veredicto.no_exitosas == ()
    assert veredicto.sin_batch == ()


@pytest.mark.parametrize("estado_malo", ["FAILED", "ABORTED", "RUNNING"])
def test_f024_r8_ko_si_la_ultima_ingesta_no_es_success(estado_malo: str) -> None:
    """El ÚLTIMO intento manda: un FAILED posterior a un SUCCESS significa que
    se intentó recargar y nadie sabe qué quedó en la tabla."""
    estados = [estado("con"), estado("obr", status=estado_malo), estado("obrparpre")]

    veredicto = evaluar_coherencia_raw(estados, REQUERIDAS)

    assert veredicto.ok is False
    assert [e.tabla for e in veredicto.no_exitosas] == ["obr"]
    # El estado real viaja con el motivo: no es lo mismo FAILED que RUNNING.
    assert veredicto.no_exitosas[0].status == estado_malo
    # Una tabla que no terminó bien no cuenta además como «de otro batch».
    assert veredicto.batches_distintos == ()


def test_f024_r8_ko_si_batch_nulo() -> None:
    """El raw anterior a F-024: SUCCESS, pero sin acreditar de qué carga viene.

    Las otras dos comparten batch a propósito: así el único motivo del KO es
    el batch nulo.
    """
    estados = [estado("con"), estado("obr"), estado("obrparpre", batch_id=None)]

    veredicto = evaluar_coherencia_raw(estados, REQUERIDAS)

    assert veredicto.ok is False
    assert [e.tabla for e in veredicto.sin_batch] == ["obrparpre"]
    assert veredicto.batch_id is None


def test_f024_r8_ko_si_todo_el_historico_es_sin_batch() -> None:
    """Primera vez tras desplegar: NINGUNA tabla tiene batch."""
    estados = [estado(t, batch_id=None) for t in REQUERIDAS]

    veredicto = evaluar_coherencia_raw(estados, REQUERIDAS)

    assert veredicto.ok is False
    assert [e.tabla for e in veredicto.sin_batch] == list(REQUERIDAS)
    assert veredicto.batches_distintos == ()


def test_f024_r8_ko_si_batches_distintos() -> None:
    """La muerte externa a mitad de ingesta: unas tablas nuevas, otras viejas."""
    estados = [
        estado("con"),
        estado("obr"),
        estado("obrparpre", batch_id=BATCH_VIEJO, fin=datetime(2026, 8, 17, 2, 30, 0)),
    ]

    veredicto = evaluar_coherencia_raw(estados, REQUERIDAS)

    assert veredicto.ok is False
    assert veredicto.batch_id is None

    # Mapa batch -> tablas, ordenado por batch (y por tanto cronológicamente).
    mapa = {b: [e.tabla for e in tablas] for b, tablas in veredicto.batches_distintos}
    assert mapa == {BATCH_BUENO: ["con", "obr"], BATCH_VIEJO: ["obrparpre"]}
    assert [b for b, _ in veredicto.batches_distintos] == [BATCH_VIEJO, BATCH_BUENO]


def test_f024_r8_ignora_tablas_no_declaradas() -> None:
    """`raw` puede tener restos de tablas que ya no se ingieren (compras,
    retenciones cargadas a mano): no son asunto de la puerta."""
    estados = [
        *todas_bien(),
        estado("tabla_vieja", status="FAILED", batch_id=None),
        estado("otra_de_otro_batch", batch_id=BATCH_VIEJO),
    ]

    veredicto = evaluar_coherencia_raw(estados, REQUERIDAS)

    assert veredicto.ok is True
    assert veredicto.batch_id == BATCH_BUENO


def test_f024_r8_el_veredicto_es_determinista_y_ordenado() -> None:
    """Mismo conjunto, distinto orden de entrada => mismo veredicto.

    El mensaje de R9 se lee a las 8 de la mañana: que las tablas salgan hoy en
    un orden y mañana en otro convierte dos incidentes iguales en dos textos
    distintos.
    """
    estados = [
        estado("obrparpre", status="FAILED"),
        estado("con", batch_id=None),
        estado("obr"),
    ]
    veredicto = evaluar_coherencia_raw(estados, REQUERIDAS)
    al_reves = evaluar_coherencia_raw(
        list(reversed(estados)), tuple(reversed(REQUERIDAS))
    )

    assert veredicto == al_reves
    assert [e.tabla for e in veredicto.no_exitosas] == ["obrparpre"]
    assert [e.tabla for e in veredicto.sin_batch] == ["con"]


def test_f024_r8_sin_tablas_requeridas_no_hay_nada_que_acreditar() -> None:
    """Caso degenerado: un YAML sin tablas. No hay batch único, así que KO.

    Es lo conservador: un `tables_sigrid.yaml` vacío es un error de
    configuración, no una carga coherente.
    """
    veredicto = evaluar_coherencia_raw(todas_bien(), ())

    assert veredicto.ok is False
    assert veredicto.faltantes == ()


# ---------------------------------------------------------------------------
# R9 · Mensaje accionable
# ---------------------------------------------------------------------------


def test_f024_r9_mensaje_lista_tablas_y_batches() -> None:
    """Cada motivo con sus tablas; cada batch con su fecha de fin."""
    estados = [
        estado("con"),
        estado("obr", status="ABORTED"),
        estado("obrparpre", batch_id=BATCH_VIEJO, fin=datetime(2026, 8, 17, 2, 30, 0)),
    ]
    veredicto = evaluar_coherencia_raw(estados, (*REQUERIDAS, "obrfas"))
    texto = formatear_veredicto_raw(veredicto)

    assert "KO" in texto
    # Faltante, no exitosa con su estado, y los dos batches con sus tablas.
    assert "obrfas" in texto
    assert "obr" in texto and "ABORTED" in texto
    assert BATCH_BUENO in texto and BATCH_VIEJO in texto
    assert "2026-08-17" in texto, "el batch viejo no dice cuándo terminó"
    assert "2026-08-18" in texto, "el batch nuevo no dice cuándo terminó"


def test_f024_r9_mensaje_nombra_el_historico_sin_batch() -> None:
    veredicto = evaluar_coherencia_raw(
        [estado(t, batch_id=None) for t in REQUERIDAS], REQUERIDAS
    )
    texto = formatear_veredicto_raw(veredicto)

    assert "F-024" in texto, "no se explica que el raw es anterior a la feature"
    for tabla in REQUERIDAS:
        assert tabla in texto


def test_f024_r9_mensaje_termina_con_las_dos_acciones() -> None:
    """Las dos, en este orden, y NINGUNA otra sugerencia (R9 es explícito)."""
    veredicto = evaluar_coherencia_raw([estado("con")], REQUERIDAS)
    texto = formatear_veredicto_raw(veredicto)

    assert "python main.py ingest --full" in texto
    assert "python main.py stage --sin-puerta" in texto
    assert texto.index("ingest --full") < texto.index("stage --sin-puerta")
    assert "registrado" in texto or "SKIPPED" in texto, (
        "no se advierte de que --sin-puerta queda registrado"
    )

    # Ni un tercer comando: el mensaje no invita a improvisar.
    comandos = set(re.findall(r"python main\.py ([a-z-]+)", texto))
    assert comandos == {"ingest", "stage"}, f"sugerencias de más: {comandos}"


def test_f024_r9_mensaje_ok_dice_de_que_batch_viene_el_raw() -> None:
    texto = formatear_veredicto_raw(evaluar_coherencia_raw(todas_bien(), REQUERIDAS))

    assert "OK" in texto
    assert BATCH_BUENO in texto
    # Un veredicto OK no propone acciones correctivas.
    assert "--sin-puerta" not in texto


# ---------------------------------------------------------------------------
# R15 · Veredicto de coherencia de `stg` (misma mecánica, otra pregunta)
# ---------------------------------------------------------------------------


def paso(step: str, status: str = "SUCCESS", ident: int = 42) -> EstadoPaso:
    return EstadoPaso(
        id=ident,
        step=step,
        status=status,
        batch_id=BATCH_BUENO,
        started_at=datetime(2026, 8, 18, 2, 40, 0),
        finished_at=datetime(2026, 8, 18, 4, 30, 0),
    )


def test_f024_r15_stg_ok_si_la_ultima_fila_es_el_paso_completo() -> None:
    veredicto = evaluar_coherencia_stg(paso("build_stg"))

    assert veredicto.ok is True
    assert veredicto.batch_id == BATCH_BUENO


@pytest.mark.parametrize(
    "ultimo",
    [
        None,                                                    # ninguna fila
        paso("build_stg", status="FAILED"),                      # el paso falló
        paso("build_stg", status="ABORTED"),                     # murió el proceso
        paso("build_stg.build_plan_mensual", status="RUNNING"),  # sub-paso vivo
        paso("build_stg.build_plan_mensual.tramo_39", status="ABORTED"),
        # El caso sutil: un sub-paso que SÍ terminó bien, pero que no es el
        # paso. Es lo que queda si el proceso muere entre dos sub-pasos.
        paso("build_stg.build_obras", status="SUCCESS"),
    ],
    ids=[
        "sin_filas", "failed", "aborted", "subpaso_running", "tramo_aborted",
        "subpaso_success",
    ],
)
def test_f024_r15_stg_ko_si_el_ultimo_stage_no_termino(
    ultimo: EstadoPaso | None,
) -> None:
    veredicto = evaluar_coherencia_stg(ultimo)

    assert veredicto.ok is False
    assert veredicto.batch_id is None


def test_f024_r15_mensaje_de_stg_es_accionable() -> None:
    texto = formatear_veredicto_stg(
        evaluar_coherencia_stg(paso("build_stg.build_plan_mensual.tramo_39", "ABORTED"))
    )

    assert "KO" in texto
    assert "build_stg.build_plan_mensual.tramo_39" in texto
    assert "ABORTED" in texto
    assert "python main.py stage" in texto
    assert "--sin-puerta" in texto

    comandos = set(re.findall(r"python main\.py ([a-z-]+)", texto))
    assert comandos == {"stage", "build-mart"}, f"sugerencias de más: {comandos}"


def test_f024_r15_mensaje_de_stg_sin_ninguna_fila_lo_dice() -> None:
    texto = formatear_veredicto_stg(evaluar_coherencia_stg(None))

    assert "KO" in texto
    assert "python main.py stage" in texto


def test_f024_r15_mensaje_de_stg_ok() -> None:
    texto = formatear_veredicto_stg(evaluar_coherencia_stg(paso("build_stg")))

    assert "OK" in texto
    assert "--sin-puerta" not in texto


# ---------------------------------------------------------------------------
# Los objetos de valor del dominio son inmutables y sin `__dict__`
#
# Nacen de la campaña de mutación: `frozen=True` y `slots=True` sobrevivían a
# la suite entera, o sea que eran decoraciones sin nadie que las sostuviera.
# No son decoración:
#
#   - `frozen` es lo que impide que un veredicto o un estado se «corrija» a
#     mitad de camino entre que la puerta lo emite y el step lo obedece. Un
#     `VeredictoCoherencia` mutable invita exactamente a eso.
#   - `slots` es lo que convierte una errata (`estado.tabl`) en AttributeError
#     en vez de en un atributo fantasma que nadie vuelve a leer.
# ---------------------------------------------------------------------------

OBJETOS_DE_VALOR = (
    (
        EstadoTablaRaw,
        {"tabla": "con", "status": "SUCCESS", "batch_id": "b", "started_at": None,
         "finished_at": None, "filas": 1},
        "tabla",
    ),
    (
        EstadoPaso,
        {"id": 1, "step": "build_stg", "status": "SUCCESS", "batch_id": "b",
         "started_at": None, "finished_at": None},
        "step",
    ),
    (VeredictoCoherencia, {"ok": True}, "ok"),
    (
        Ejecucion,
        {"batch_id": "20260819T020000Z-aaaaaa", "iniciada_en": datetime(2026, 8, 19)},
        "batch_id",
    ),
)


@pytest.mark.parametrize(
    ("clase", "argumentos", "campo"),
    OBJETOS_DE_VALOR,
    ids=lambda v: v.__name__ if isinstance(v, type) else "",
)
def test_f024_los_objetos_de_valor_son_inmutables(
    clase: type, argumentos: dict, campo: str
) -> None:
    objeto = clase(**argumentos)

    with pytest.raises(FrozenInstanceError):
        setattr(objeto, campo, "otra cosa")


@pytest.mark.parametrize(
    ("clase", "argumentos", "campo"),
    OBJETOS_DE_VALOR,
    ids=lambda v: v.__name__ if isinstance(v, type) else "",
)
def test_f024_los_objetos_de_valor_no_admiten_campos_inventados(
    clase: type, argumentos: dict, campo: str
) -> None:
    """`slots=True`: una errata no crea un atributo fantasma en silencio."""
    objeto = clase(**argumentos)

    assert not hasattr(objeto, "__dict__"), (
        f"{clase.__name__} tiene __dict__: perdió slots=True y una errata como "
        f"'{campo[:3]}' pasaría a crear un atributo nuevo sin avisar"
    )


def test_f024_r8_una_tabla_sin_filas_conocidas_cuenta_cero() -> None:
    """El default de `filas` es 0, no 1.

    Lo lee `check-coherencia` y acaba impreso al lado del nombre de la tabla:
    un 1 por defecto diría que se ingirió una fila donde no se ingirió ninguna.
    """
    sin_filas = EstadoTablaRaw(
        tabla="con",
        status="ABORTED",
        batch_id=None,
        started_at=None,
        finished_at=None,
    )
    assert sin_filas.filas == 0
