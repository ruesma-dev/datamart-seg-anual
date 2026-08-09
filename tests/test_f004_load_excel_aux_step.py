# tests/test_f004_load_excel_aux_step.py
"""
F-004 · Tests del step load_excel_aux (R11-R14).

La fuente de ficheros se inyecta: ningún test toca red, disco ni BBDD. Los
libros de prueba se generan con openpyxl EN MEMORIA, que es justamente la
propiedad que R11 exige del step.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from config.settings import AuxExcelSettings
from etl_sigrid.application.steps import load_excel_aux_step as modulo_step
from etl_sigrid.application.steps.load_excel_aux_step import LoadExcelAuxStep
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.infrastructure.excel.aux_file_source import (
    AuxFileNotFoundError,
    AuxFileRef,
)

BLOB = "https://stdatamartsegdev.blob.core.windows.net/aux"


def _libro(*hojas: str) -> bytes:
    """Un .xlsx real, generado y devuelto sin pasar por el sistema de ficheros."""
    from openpyxl import Workbook

    libro = Workbook()
    libro.active.title = hojas[0]
    for hoja in hojas[1:]:
        libro.create_sheet(hoja)
    libro.active["A1"] = "codigo"
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _settings(**kwargs: str) -> SimpleNamespace:
    """Lo único que el step necesita de Settings es `aux_excel`."""
    base: dict[str, str] = {
        "tipo_partida": "",
        "tipo_coste": "",
        "mapeo_proporcionales": "",
    }
    base.update(kwargs)
    return SimpleNamespace(
        aux_excel=AuxExcelSettings(_env_file=None, **base)  # type: ignore[arg-type]
    )


class _FuenteFalsa:
    """Fuente inyectada: devuelve bytes o lanza el error que se le indique."""

    def __init__(self, respuestas: dict[str, bytes | Exception]) -> None:
        self._respuestas = respuestas
        self.leidos: list[str] = []

    def read_bytes(self, ref: AuxFileRef) -> bytes:
        self.leidos.append(ref.logical_name)
        respuesta = self._respuestas[ref.logical_name]
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def _step(settings: SimpleNamespace, fuente: _FuenteFalsa) -> LoadExcelAuxStep:
    return LoadExcelAuxStep(settings, source_factory=lambda ref: fuente)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# R11 · el libro se abre desde memoria, sin ruta que exista en ninguna parte
# ---------------------------------------------------------------------------

def test_f004_r11_el_step_abre_el_libro_desde_memoria_sin_ruta_existente() -> None:
    """La ubicación es un blob: si el step necesitara un fichero en disco, fallaría."""
    settings = _settings(tipo_partida=f"{BLOB}/TipoPartida.xlsx")
    fuente = _FuenteFalsa({"tipo_partida": _libro("Partidas")})

    resultado = _step(settings, fuente).run()

    assert resultado.status == StepStatus.SUCCESS
    assert resultado.metadata["files"]["tipo_partida"]["hojas"] == ["Partidas"]
    assert not Path("TipoPartida.xlsx").exists()


# ---------------------------------------------------------------------------
# R12 · los tres legibles: SUCCESS con metadata por fichero
# ---------------------------------------------------------------------------

def test_f004_r12_los_tres_ficheros_legibles_dan_success_con_metadata() -> None:
    """Origen, ubicación segura, tamaño y hojas de cada uno, y el orden respetado."""
    partida = _libro("Partidas")
    coste = _libro("Costes", "Notas")
    mapeo = _libro("Mapeo")
    settings = _settings(
        tipo_partida=f"{BLOB}/TipoPartida.xlsx",
        tipo_coste="D:/datos/TipoCoste.xlsx",
        mapeo_proporcionales=f"{BLOB}/mapeo_proporcionales.xlsx",
    )
    fuente = _FuenteFalsa(
        {"tipo_partida": partida, "tipo_coste": coste, "mapeo_proporcionales": mapeo}
    )

    resultado = _step(settings, fuente).run()

    assert resultado.status == StepStatus.SUCCESS
    assert resultado.error_message is None
    assert resultado.rows_processed == 3
    assert fuente.leidos == ["tipo_partida", "tipo_coste", "mapeo_proporcionales"]
    assert resultado.metadata["omitidos"] == []
    assert resultado.metadata["files"] == {
        "tipo_partida": {
            "origen": "blob",
            "ubicacion": "blob: stdatamartsegdev/aux/TipoPartida.xlsx",
            "bytes": len(partida),
            "hojas": ["Partidas"],
        },
        "tipo_coste": {
            "origen": "local",
            "ubicacion": "ruta local: D:/datos/TipoCoste.xlsx",
            "bytes": len(coste),
            "hojas": ["Costes", "Notas"],
        },
        "mapeo_proporcionales": {
            "origen": "blob",
            "ubicacion": "blob: stdatamartsegdev/aux/mapeo_proporcionales.xlsx",
            "bytes": len(mapeo),
            "hojas": ["Mapeo"],
        },
    }


def test_f004_r12_el_step_no_escribe_una_sola_fila_en_postgres() -> None:
    """
    Frontera explícita de F-004: lee y valida, no carga. La carga a aux.* exige
    el esquema de los tres Excel, que no está en el repositorio (DA-1).
    """
    fuente_del_modulo = Path(modulo_step.__file__).read_text(encoding="utf-8")

    for prohibido in ("PostgresClient", "build_postgres_client", "INSERT", "COPY"):
        assert prohibido not in fuente_del_modulo


# ---------------------------------------------------------------------------
# R13 · sin configuración no se rompe run-all
# ---------------------------------------------------------------------------

def test_f004_r13_sin_variables_configuradas_el_step_queda_skipped() -> None:
    """Un clon recién hecho no tiene los Excels: SKIPPED, no FAILED."""
    fuente = _FuenteFalsa({})

    resultado = _step(_settings(), fuente).run()

    assert resultado.status == StepStatus.SKIPPED
    assert fuente.leidos == []
    mensaje = resultado.error_message or ""
    assert "AUX_EXCEL_TIPO_PARTIDA" in mensaje
    assert "AUX_EXCEL_TIPO_COSTE" in mensaje
    assert "AUX_EXCEL_MAPEO_PROPORCIONALES" in mensaje
    assert resultado.metadata["omitidos"] == [
        "tipo_partida",
        "tipo_coste",
        "mapeo_proporcionales",
    ]


def test_f004_r13_configuracion_parcial_lee_lo_configurado_y_lista_lo_omitido() -> None:
    """Lo que hay se lee; lo que falta se dice, y el step sigue en SUCCESS."""
    settings = _settings(tipo_coste=f"{BLOB}/TipoCoste.xlsx")
    fuente = _FuenteFalsa({"tipo_coste": _libro("Costes")})

    resultado = _step(settings, fuente).run()

    assert resultado.status == StepStatus.SUCCESS
    assert resultado.rows_processed == 1
    assert fuente.leidos == ["tipo_coste"]
    assert list(resultado.metadata["files"]) == ["tipo_coste"]
    assert resultado.metadata["omitidos"] == ["tipo_partida", "mapeo_proporcionales"]


# ---------------------------------------------------------------------------
# R14 · un fichero ilegible es FAILED, y se listan TODOS los problemáticos
# ---------------------------------------------------------------------------

def test_f004_r14_fichero_ilegible_da_failed_nombrando_el_fichero() -> None:
    """Un .xlsx corrupto no puede salir como un traceback de openpyxl."""
    settings = _settings(tipo_partida=f"{BLOB}/TipoPartida.xlsx")
    fuente = _FuenteFalsa({"tipo_partida": b"esto no es un xlsx"})

    resultado = _step(settings, fuente).run()

    assert resultado.status == StepStatus.FAILED
    mensaje = resultado.error_message or ""
    assert "tipo_partida" in mensaje
    assert "blob: stdatamartsegdev/aux/TipoPartida.xlsx" in mensaje


def test_f004_r14_dos_fallos_se_reportan_los_dos_en_el_mismo_mensaje() -> None:
    """Nadie quiere arreglar de uno en uno y volver a esperar al job nocturno."""
    settings = _settings(
        tipo_partida=f"{BLOB}/TipoPartida.xlsx",
        tipo_coste="D:/datos/TipoCoste.xlsx",
        mapeo_proporcionales=f"{BLOB}/mapeo_proporcionales.xlsx",
    )
    fuente = _FuenteFalsa(
        {
            "tipo_partida": AuxFileNotFoundError("el blob tipo_partida no existe"),
            "tipo_coste": b"esto tampoco es un xlsx",
            "mapeo_proporcionales": _libro("Mapeo"),
        }
    )

    resultado = _step(settings, fuente).run()

    assert resultado.status == StepStatus.FAILED
    mensaje = resultado.error_message or ""
    assert "el blob tipo_partida no existe" in mensaje
    assert "tipo_coste" in mensaje
    assert "2" in mensaje
    # El tercero sí se leyó: el step no aborta al primer fallo.
    assert fuente.leidos == ["tipo_partida", "tipo_coste", "mapeo_proporcionales"]
    assert list(resultado.metadata["files"]) == ["mapeo_proporcionales"]


def test_f004_r14_una_variable_mal_configurada_tambien_es_failed() -> None:
    """El error de configuración (R5-R7) se acumula igual que el de lectura."""
    settings = _settings(tipo_partida="https://ejemplo.sharepoint.com/aux/TipoPartida.xlsx")
    fuente = _FuenteFalsa({})

    resultado = _step(settings, fuente).run()

    assert resultado.status == StepStatus.FAILED
    assert "AUX_EXCEL_TIPO_PARTIDA" in (resultado.error_message or "")
    assert fuente.leidos == []


def test_f004_r14_un_fallo_inesperado_de_la_fuente_se_atribuye_a_su_fichero() -> None:
    """Red de seguridad: lo no previsto tampoco puede tumbar a los otros dos."""
    settings = _settings(
        tipo_partida=f"{BLOB}/TipoPartida.xlsx",
        tipo_coste=f"{BLOB}/TipoCoste.xlsx",
    )
    fuente = _FuenteFalsa(
        {
            "tipo_partida": RuntimeError("el SDK ha hecho algo raro"),
            "tipo_coste": _libro("Costes"),
        }
    )

    resultado = _step(settings, fuente).run()

    assert resultado.status == StepStatus.FAILED
    mensaje = resultado.error_message or ""
    assert "tipo_partida" in mensaje
    assert "RuntimeError" in mensaje
    assert "el SDK ha hecho algo raro" in mensaje
    assert list(resultado.metadata["files"]) == ["tipo_coste"]
