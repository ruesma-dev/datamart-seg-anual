# tests/test_f004_aux_file_source.py
"""
F-004 · Tests del puerto de lectura de Excels auxiliares (R1-R11).

Ninguno toca red ni BBDD: los `.xlsx` de prueba se generan con openpyxl en
`tmp_path` y el cliente de blob se sustituye por un doble inyectado en el
límite del adaptador. El SDK de Azure NO se importa en ningún test.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from config.settings import AuxExcelSettings
from etl_sigrid.infrastructure.excel.aux_file_source import (
    BLOB_HOST_SUFFIX,
    AuxFileAccessError,
    AuxFileConfigError,
    AuxFileError,
    AuxFileNotFoundError,
    AuxFileRef,
    LocalAuxFileSource,
    get_aux_file_source,
    parse_aux_file_ref,
)
from etl_sigrid.infrastructure.excel.blob_aux_file_source import (
    BlobAuxFileSource,
    _importar_sdk,
)

SAS ="sv=2024-11-04&sig=FIRMA-SECRETA-QUE-NO-DEBE-SALIR&se=2030-01-01"


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


# ---------------------------------------------------------------------------
# R3 · el adaptador local lee de verdad un .xlsx del sistema de ficheros
# ---------------------------------------------------------------------------

def _xlsx(destino, hojas=("Hoja1",)) -> bytes:
    """Genera un .xlsx real con openpyxl y devuelve sus bytes."""
    from openpyxl import Workbook

    libro = Workbook()
    libro.active.title = hojas[0]
    for hoja in hojas[1:]:
        libro.create_sheet(hoja)
    libro.active["A1"] = "codigo"
    libro.save(destino)
    return Path(destino).read_bytes()


def test_f004_r3_lee_un_xlsx_real_del_sistema_de_ficheros(tmp_path) -> None:
    """El camino local sigue funcionando: es requisito, no cortesía."""
    fichero = tmp_path / "TipoPartida.xlsx"
    esperado = _xlsx(fichero)

    ref = parse_aux_file_ref("tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", str(fichero))
    datos = LocalAuxFileSource().read_bytes(ref)

    assert datos == esperado
    assert datos[:2] == b"PK"


def test_f004_r3_la_fabrica_devuelve_el_adaptador_local_para_una_ruta(tmp_path) -> None:
    """get_aux_file_source elige por el origen de la referencia, no por configuración."""
    ref = parse_aux_file_ref(
        "tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", str(tmp_path / "x.xlsx")
    )

    assert isinstance(get_aux_file_source(ref), LocalAuxFileSource)


# ---------------------------------------------------------------------------
# R8 · el error de un fichero local ausente tiene que ser accionable a las 3 AM
# ---------------------------------------------------------------------------

def test_f004_r8_ruta_local_inexistente_produce_mensaje_accionable(tmp_path) -> None:
    """Nombre lógico, variable responsable, ruta recibida y la pista del contenedor."""
    ausente = tmp_path / "no_existe" / "TipoPartida.xlsx"
    ref = parse_aux_file_ref("tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", str(ausente))

    with pytest.raises(AuxFileNotFoundError) as exc:
        LocalAuxFileSource().read_bytes(ref)

    mensaje = str(exc.value)
    assert "tipo_partida" in mensaje
    assert "AUX_EXCEL_TIPO_PARTIDA" in mensaje
    assert str(ausente) in mensaje
    assert "contenedor" in mensaje
    assert BLOB_HOST_SUFFIX in mensaje


def test_f004_r8_un_directorio_en_vez_de_un_fichero_tambien_falla_nombrando_la_variable(
    tmp_path,
) -> None:
    """Apuntar a una carpeta es un error de configuración frecuente; no puede reventar feo."""
    ref = parse_aux_file_ref("tipo_coste", "AUX_EXCEL_TIPO_COSTE", str(tmp_path))

    with pytest.raises(AuxFileError) as exc:
        LocalAuxFileSource().read_bytes(ref)

    assert "AUX_EXCEL_TIPO_COSTE" in str(exc.value)


# ---------------------------------------------------------------------------
# Dobles del cliente de blob. Se inyectan en el límite del adaptador: el SDK de
# Azure no se importa, no se parchea y no hace falta tenerlo instalado.
# ---------------------------------------------------------------------------

class _DescargaFalsa:
    def __init__(self, datos: bytes) -> None:
        self._datos = datos

    def readall(self) -> bytes:
        return self._datos


class _ClienteFalso:
    """Cliente que devuelve bytes o revienta con la excepción que se le diga."""

    def __init__(self, datos: bytes = b"PK-datos", error: Exception | None = None) -> None:
        self._datos = datos
        self._error = error
        self.descargas = 0

    def download_blob(self) -> _DescargaFalsa:
        self.descargas += 1
        if self._error is not None:
            raise self._error
        return _DescargaFalsa(self._datos)


class _DefaultAzureCredentialFalsa:
    """Homónima de la del SDK: el adaptador la instancia por su papel, no por su origen."""

    instancias = 0

    def __init__(self) -> None:
        type(self).instancias += 1


class _BlobClientFalso:
    """Registra con qué argumentos lo construye el adaptador."""

    construidos: list[dict] = []

    def __init__(self, **kwargs: object) -> None:
        type(self).construidos.append(kwargs)
        self.kwargs = kwargs

    def download_blob(self) -> _DescargaFalsa:
        return _DescargaFalsa(b"PK-datos")


class ResourceNotFoundError(Exception):
    """Doble homónimo de azure.core.exceptions.ResourceNotFoundError."""


class ClientAuthenticationError(Exception):
    """Homónima de azure.core.exceptions.ClientAuthenticationError."""


class CredentialUnavailableError(Exception):
    """Homónima de azure.identity.CredentialUnavailableError."""


class HttpResponseError(Exception):
    """Homónima de azure.core.exceptions.HttpResponseError, con status_code."""

    def __init__(self, status_code: int, mensaje: str = "fallo http") -> None:
        super().__init__(mensaje)
        self.status_code = status_code


def _ref_blob(logico: str = "tipo_coste") -> AuxFileRef:
    return parse_aux_file_ref(
        logico,
        f"AUX_EXCEL_{logico.upper()}",
        f"https://stdatamartsegdev.blob.core.windows.net/aux/{logico}.xlsx",
    )


def _fuente(cliente: object) -> BlobAuxFileSource:
    """BlobAuxFileSource con el cliente doblado en el límite del adaptador."""
    return BlobAuxFileSource(blob_client_factory=lambda ref: cliente)


# ---------------------------------------------------------------------------
# R1 · la misma llamada sirve para ruta local y para URI de blob
# ---------------------------------------------------------------------------

def test_f004_r1_la_misma_llamada_sirve_para_ruta_local_y_para_uri_de_blob(tmp_path) -> None:
    """Quien lee no sabe de dónde viene el fichero: read_bytes(ref) y punto."""
    fichero = tmp_path / "TipoPartida.xlsx"
    contenido = _xlsx(fichero)

    ref_local = parse_aux_file_ref("tipo_partida", "AUX_EXCEL_TIPO_PARTIDA", str(fichero))
    ref_blob = _ref_blob("tipo_partida")

    fuente_local = get_aux_file_source(ref_local)
    fuente_blob = _fuente(_ClienteFalso(datos=contenido))

    assert isinstance(get_aux_file_source(ref_blob), BlobAuxFileSource)
    assert fuente_local.read_bytes(ref_local) == contenido
    assert fuente_blob.read_bytes(ref_blob) == contenido


# ---------------------------------------------------------------------------
# R4 · autenticación por DefaultAzureCredential, sin cadenas ni claves
# ---------------------------------------------------------------------------

def test_f004_r4_el_cliente_de_blob_se_construye_con_default_azure_credential() -> None:
    """La cuenta sale de la URI, la credencial es DefaultAzureCredential y se reutiliza."""
    _BlobClientFalso.construidos.clear()
    _DefaultAzureCredentialFalsa.instancias = 0

    fuente = BlobAuxFileSource(
        importar_sdk=lambda: (_BlobClientFalso, _DefaultAzureCredentialFalsa)
    )
    fuente.read_bytes(_ref_blob("tipo_partida"))
    fuente.read_bytes(_ref_blob("tipo_coste"))

    assert len(_BlobClientFalso.construidos) == 2
    primero = _BlobClientFalso.construidos[0]
    assert primero["account_url"] == "https://stdatamartsegdev.blob.core.windows.net"
    assert primero["container_name"] == "aux"
    assert primero["blob_name"] == "tipo_partida.xlsx"
    assert isinstance(primero["credential"], _DefaultAzureCredentialFalsa)
    assert "connection_string" not in primero
    # Una sola credencial por instancia, reutilizada para los tres ficheros.
    assert _DefaultAzureCredentialFalsa.instancias == 1
    assert primero["credential"] is _BlobClientFalso.construidos[1]["credential"]


def test_f004_r4_el_sdk_se_importa_de_forma_perezosa_y_es_el_oficial() -> None:
    """
    El import real vive en una sola función y se comprueba por su fuente: con el
    SDK sin instalar (el caso de este puesto) ningún doble puede fingir esto.
    """
    fuente_del_import = inspect.getsource(_importar_sdk)

    assert "from azure.identity import DefaultAzureCredential" in fuente_del_import
    assert "from azure.storage.blob import BlobClient" in fuente_del_import


def test_f004_r4_sin_el_sdk_instalado_el_error_dice_como_arreglarlo() -> None:
    """Un ImportError del import perezoso no puede salir como un traceback críptico."""
    def _revienta() -> tuple[type, type]:
        raise ImportError("No module named 'azure'")

    fuente = BlobAuxFileSource(importar_sdk=_revienta)

    with pytest.raises(AuxFileAccessError) as exc:
        fuente.read_bytes(_ref_blob())

    mensaje = str(exc.value)
    assert "requirements.txt" in mensaje
    assert "azure-storage-blob" in mensaje


def test_f004_r4_no_hay_cadenas_de_conexion_ni_claves_en_el_codigo() -> None:
    """Barrido del código que viaja en la imagen: ni claves de cuenta ni SAS."""
    prohibidos = (
        "AccountKey",
        "DefaultEndpointsProtocol",
        "connection_string",
        "from_connection_string",
        "SharedKeyCredential",
        "AzureNamedKeyCredential",
        "sas_token",
    )
    raiz = Path(__file__).resolve().parents[1]
    ficheros = [
        *(raiz / "etl_sigrid").rglob("*.py"),
        *(raiz / "config").rglob("*.py"),
        raiz / "main.py",
    ]

    hallazgos = [
        f"{fichero.relative_to(raiz).as_posix()}: {prohibido}"
        for fichero in ficheros
        for prohibido in prohibidos
        if prohibido in fichero.read_text(encoding="utf-8")
    ]

    assert hallazgos == []


# ---------------------------------------------------------------------------
# R9 · blob inexistente: el mensaje dice cuenta, contenedor y blob
# ---------------------------------------------------------------------------

def test_f004_r9_blob_inexistente_produce_mensaje_con_cuenta_contenedor_y_blob() -> None:
    """Traducido por NOMBRE de clase, para no atarse a la jerarquía de azure-core."""
    fuente = _fuente(_ClienteFalso(error=ResourceNotFoundError("blob does not exist")))

    with pytest.raises(AuxFileNotFoundError) as exc:
        fuente.read_bytes(_ref_blob("tipo_coste"))

    mensaje = str(exc.value)
    assert "stdatamartsegdev" in mensaje
    assert "aux" in mensaje
    assert "tipo_coste.xlsx" in mensaje
    assert "AUX_EXCEL_TIPO_COSTE" in mensaje
    assert "sube" in mensaje.lower()


# ---------------------------------------------------------------------------
# R10 · permisos y credencial: el mensaje nombra el rol y las dos salidas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error",
    [
        ClientAuthenticationError("no autorizado"),
        HttpResponseError(403),
        HttpResponseError(401),
    ],
)
def test_f004_r10_error_de_permisos_menciona_el_rol_y_las_dos_salidas(error: Exception) -> None:
    """403, 401 y error de autenticación acaban en el mismo mensaje accionable."""
    fuente = _fuente(_ClienteFalso(error=error))

    with pytest.raises(AuxFileAccessError) as exc:
        fuente.read_bytes(_ref_blob("tipo_coste"))

    mensaje = str(exc.value)
    assert "Storage Blob Data Reader" in mensaje
    assert "stdatamartsegdev" in mensaje
    assert "az login" in mensaje
    assert "identidad gestionada" in mensaje


def test_f004_r10_falta_de_credencial_menciona_az_login_e_identidad_gestionada() -> None:
    """Sin credencial disponible el diagnóstico es otro; el remedio, el mismo."""
    fuente = _fuente(_ClienteFalso(error=CredentialUnavailableError("sin credencial")))

    with pytest.raises(AuxFileAccessError) as exc:
        fuente.read_bytes(_ref_blob("tipo_partida"))

    mensaje = str(exc.value)
    assert "az login" in mensaje
    assert "identidad gestionada" in mensaje
    assert "Storage Blob Data Reader" in mensaje


def test_f004_r10_un_error_http_que_no_es_de_permisos_no_se_disfraza() -> None:
    """Un 500 no es un problema de rol: se reporta como fallo genérico con su tipo."""
    fuente = _fuente(_ClienteFalso(error=HttpResponseError(500, "servidor caido")))

    with pytest.raises(AuxFileError) as exc:
        fuente.read_bytes(_ref_blob())

    mensaje = str(exc.value)
    assert "Storage Blob Data Reader" not in mensaje
    assert "HttpResponseError" in mensaje
    assert "servidor caido" in mensaje


def test_f004_r11_el_adaptador_de_blob_devuelve_bytes_sin_tocar_el_disco(tmp_path) -> None:
    """Descarga a memoria: ni temporales ni ficheros nuevos en el directorio de trabajo."""
    cliente = _ClienteFalso(datos=b"PK-contenido-del-libro")
    antes = set(tmp_path.iterdir())

    datos = _fuente(cliente).read_bytes(_ref_blob())

    assert datos == b"PK-contenido-del-libro"
    assert cliente.descargas == 1
    assert set(tmp_path.iterdir()) == antes
