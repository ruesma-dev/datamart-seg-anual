# tests/test_f004_aux_file_source.py
"""
F-004 · Tests del puerto de lectura de Excels auxiliares (R1-R11).

Ninguno toca red ni BBDD: los `.xlsx` de prueba se generan con openpyxl en
`tmp_path` y el cliente de blob se sustituye por un doble inyectado en el
límite del adaptador. El SDK de Azure NO se importa en ningún test.
"""

from __future__ import annotations

from config.settings import AuxExcelSettings


def _aux(**kwargs: str) -> AuxExcelSettings:
    """
    AuxExcelSettings hermético: `_env_file=None` evita que el .env del puesto
    donde corran los tests cambie el resultado.
    """
    base: dict[str, str] = {
        "tipo_partida": "",
        "tipo_coste": "",
        "mapeo_proporcionales": "",
    }
    base.update(kwargs)
    return AuxExcelSettings(_env_file=None, **base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# R1 · las tres variables se resuelven por el mismo camino
# ---------------------------------------------------------------------------

def test_f004_r1_settings_declara_las_tres_variables_con_su_nombre_de_entorno() -> None:
    """entries() devuelve (nombre_lógico, variable_de_entorno, valor) de los tres."""
    ajustes = _aux(
        tipo_partida="D:/datos/TipoPartida.xlsx",
        tipo_coste="",
        mapeo_proporcionales="https://cuenta.blob.core.windows.net/aux/mapeo.xlsx",
    )

    assert ajustes.entries() == (
        ("tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", "D:/datos/TipoPartida.xlsx"),
        ("tipo_coste", "AUX_EXCEL_TIPO_COSTE", ""),
        (
            "mapeo_proporcionales",
            "AUX_EXCEL_MAPEO_PROPORCIONALES",
            "https://cuenta.blob.core.windows.net/aux/mapeo.xlsx",
        ),
    )
