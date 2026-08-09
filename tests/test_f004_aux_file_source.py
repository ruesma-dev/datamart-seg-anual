# tests/test_f004_aux_file_source.py
"""
F-004 · Tests del puerto de lectura de Excels auxiliares (R1-R11).

Ninguno toca red ni BBDD: los `.xlsx` de prueba se generan con openpyxl en
`tmp_path` y el cliente de blob se sustituye por un doble inyectado en el
límite del adaptador. El SDK de Azure NO se importa en ningún test.
"""

from __future__ import annotations

import pytest

from config.settings import AuxExcelSettings
from etl_sigrid.infrastructure.excel.aux_file_source import (
    AuxFileConfigError,
    parse_aux_file_ref,
)

SAS = "sv=2024-11-04&sig=FIRMA-SECRETA-QUE-NO-DEBE-SALIR&se=2030-01-01"


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


def test_f004_r1_valor_vacio_es_error_de_configuracion() -> None:
    """Llegar aquí con un valor vacío es un bug del llamante: el step los filtra antes."""
    with pytest.raises(AuxFileConfigError) as exc:
        parse_aux_file_ref("tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", "   ")

    assert "AUX_EXCEL_TIPO_PARTIDA" in str(exc.value)


# ---------------------------------------------------------------------------
# R2 · una URI de blob se clasifica como blob y se descompone
# ---------------------------------------------------------------------------

def test_f004_r2_uri_de_blob_se_clasifica_como_blob_y_se_descompone() -> None:
    """Cuenta, contenedor y blob salen de la propia URI; nada se configura aparte."""
    ref = parse_aux_file_ref(
        "tipo_coste",
        "AUX_EXCEL_TIPO_COSTE",
        "https://stdatamartsegdev.blob.core.windows.net/aux/TipoCoste.xlsx",
    )

    assert ref.origin == "blob"
    assert ref.account == "stdatamartsegdev"
    assert ref.container == "aux"
    assert ref.blob_name == "TipoCoste.xlsx"
    assert ref.local_path is None
    assert ref.logical_name == "tipo_coste"
    assert ref.env_var == "AUX_EXCEL_TIPO_COSTE"
    assert ref.display == "blob: stdatamartsegdev/aux/TipoCoste.xlsx"


def test_f004_r2_nombre_de_blob_con_subcarpetas_se_conserva_entero() -> None:
    """El blob es TODO lo que sigue al contenedor, con sus barras."""
    ref = parse_aux_file_ref(
        "tipo_partida",
        "AUX_EXCEL_TIPO_PARTIDA",
        "https://cuenta.blob.core.windows.net/aux/2026/negocio/TipoPartida.xlsx",
    )

    assert ref.container == "aux"
    assert ref.blob_name == "2026/negocio/TipoPartida.xlsx"


def test_f004_r2_el_esquema_https_no_distingue_mayusculas() -> None:
    """HTTPS:// y el host en mayúsculas siguen siendo una URI de blob válida."""
    ref = parse_aux_file_ref(
        "tipo_partida",
        "AUX_EXCEL_TIPO_PARTIDA",
        "HTTPS://Cuenta.Blob.Core.Windows.Net/aux/TipoPartida.xlsx",
    )

    assert ref.origin == "blob"
    assert ref.account == "cuenta"


# ---------------------------------------------------------------------------
# R3 · lo que no es URI de blob es ruta local, y el ETL sigue corriendo en local
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "valor",
    [
        "D:/datos/TipoPartida.xlsx",
        "D:\\datos\\TipoPartida.xlsx",
        "/datos/TipoPartida.xlsx",
        "\\\\servidor\\recurso\\TipoPartida.xlsx",
        "TipoPartida.xlsx",
    ],
)
def test_f004_r3_ruta_windows_posix_y_unc_se_clasifican_como_local(valor: str) -> None:
    """Windows, POSIX, UNC y relativa: todas locales, con la ruta intacta."""
    ref = parse_aux_file_ref("tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", valor)

    assert ref.origin == "local"
    assert ref.local_path == valor
    assert ref.account is None
    assert ref.container is None
    assert ref.blob_name is None
    assert ref.display == f"ruta local: {valor}"


def test_f004_r3_los_espacios_del_borde_no_cuentan() -> None:
    """Un valor pegado en .env con espacios sobrantes no cambia la clasificación."""
    ref = parse_aux_file_ref(
        "tipo_partida",
        "AUX_EXCEL_TIPO_PARTIDA",
        "  https://cuenta.blob.core.windows.net/aux/TipoPartida.xlsx  ",
    )

    assert ref.origin == "blob"
    assert ref.blob_name == "TipoPartida.xlsx"


# ---------------------------------------------------------------------------
# R5 · una URI https ajena a Blob Storage NO se trata como ruta local
# ---------------------------------------------------------------------------

def test_f004_r5_uri_https_ajena_a_blob_storage_es_error_de_configuracion() -> None:
    """Nombra la variable y el host recibido, y no cae al camino local."""
    with pytest.raises(AuxFileConfigError) as exc:
        parse_aux_file_ref(
            "tipo_coste",
            "AUX_EXCEL_TIPO_COSTE",
            "https://ejemplo.sharepoint.com/aux/TipoCoste.xlsx",
        )

    mensaje = str(exc.value)
    assert "AUX_EXCEL_TIPO_COSTE" in mensaje
    assert "ejemplo.sharepoint.com" in mensaje
    assert ".blob.core.windows.net" in mensaje


def test_f004_r5_uri_http_sin_tls_es_error_de_configuracion() -> None:
    """La identidad gestionada exige TLS: http:// se rechaza explícitamente."""
    with pytest.raises(AuxFileConfigError) as exc:
        parse_aux_file_ref(
            "tipo_coste",
            "AUX_EXCEL_TIPO_COSTE",
            "http://cuenta.blob.core.windows.net/aux/TipoCoste.xlsx",
        )

    mensaje = str(exc.value)
    assert "AUX_EXCEL_TIPO_COSTE" in mensaje
    assert "https" in mensaje


# ---------------------------------------------------------------------------
# R6 · un SAS en la variable es un secreto en el entorno: se rechaza sin filtrarlo
# ---------------------------------------------------------------------------

def test_f004_r6_uri_con_sas_se_rechaza() -> None:
    """El rechazo remite a la identidad gestionada, no a un simple 'quita el token'."""
    with pytest.raises(AuxFileConfigError) as exc:
        parse_aux_file_ref(
            "tipo_partida",
            "AUX_EXCEL_TIPO_PARTIDA",
            f"https://cuenta.blob.core.windows.net/aux/TipoPartida.xlsx?{SAS}",
        )

    mensaje = str(exc.value)
    assert "AUX_EXCEL_TIPO_PARTIDA" in mensaje
    assert "identidad gestionada" in mensaje


def test_f004_r6_el_mensaje_de_rechazo_no_filtra_el_token() -> None:
    """El mensaje corta antes del '?': el token no entra en el log ni en la excepción."""
    with pytest.raises(AuxFileConfigError) as exc:
        parse_aux_file_ref(
            "tipo_partida",
            "AUX_EXCEL_TIPO_PARTIDA",
            f"https://cuenta.blob.core.windows.net/aux/TipoPartida.xlsx?{SAS}",
        )

    mensaje = str(exc.value)
    assert "sig=" not in mensaje
    assert "FIRMA-SECRETA-QUE-NO-DEBE-SALIR" not in mensaje
    assert "?" not in mensaje
    assert "https://cuenta.blob.core.windows.net/aux/TipoPartida.xlsx" in mensaje


def test_f004_r6_el_fragmento_tambien_se_rechaza() -> None:
    """Un '#' tras la URI no es parte del nombre del blob: se rechaza igual."""
    with pytest.raises(AuxFileConfigError) as exc:
        parse_aux_file_ref(
            "tipo_partida",
            "AUX_EXCEL_TIPO_PARTIDA",
            "https://cuenta.blob.core.windows.net/aux/TipoPartida.xlsx#hoja1",
        )

    assert "hoja1" not in str(exc.value)


# ---------------------------------------------------------------------------
# R7 · una URI que no identifica contenedor Y blob es error de configuración
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "valor",
    [
        "https://cuenta.blob.core.windows.net",
        "https://cuenta.blob.core.windows.net/",
        "https://cuenta.blob.core.windows.net/aux",
        "https://cuenta.blob.core.windows.net/aux/",
    ],
)
def test_f004_r7_uri_sin_contenedor_o_sin_blob_es_error_de_configuracion(valor: str) -> None:
    """El mensaje enseña la forma esperada, que es lo único accionable aquí."""
    with pytest.raises(AuxFileConfigError) as exc:
        parse_aux_file_ref("tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", valor)

    mensaje = str(exc.value)
    assert "AUX_EXCEL_TIPO_PARTIDA" in mensaje
    assert "https://<cuenta>.blob.core.windows.net/<contenedor>/<blob>" in mensaje


def test_f004_r7_una_cuenta_vacia_tambien_se_rechaza() -> None:
    """Sin nombre de cuenta antes del sufijo no hay a qué conectarse."""
    with pytest.raises(AuxFileConfigError):
        parse_aux_file_ref(
            "tipo_partida",
            "AUX_EXCEL_TIPO_PARTIDA",
            "https://.blob.core.windows.net/aux/TipoPartida.xlsx",
        )
