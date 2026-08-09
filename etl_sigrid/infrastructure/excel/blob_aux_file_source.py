# etl_sigrid/infrastructure/excel/blob_aux_file_source.py
"""
Adaptador de Azure Blob Storage para los Excels auxiliares.

Descarga el blob A MEMORIA con `DefaultAzureCredential`: identidad gestionada
cuando el ETL corre en el Container Apps Job, sesión de `az` cuando corre en el
puesto del desarrollador. Ni cadena de conexión, ni clave de cuenta, ni SAS.

Los errores del SDK se traducen a la jerarquía del puerto por NOMBRE de clase,
no por la jerarquía de excepciones de `azure-core`: así el módulo se prueba con
dobles, sin el SDK instalado, y sigue funcionando si Microsoft reorganiza sus
clases base. El precio —reconocido— es que un renombrado de clase en el SDK
degradaría el mensaje a genérico, nunca a silencio.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from etl_sigrid.infrastructure.excel.aux_file_source import (
    BLOB_HOST_SUFFIX,
    AuxFileAccessError,
    AuxFileError,
    AuxFileNotFoundError,
    AuxFileRef,
)

#: Nombres de clase del SDK que significan "el blob no está".
ERRORES_NO_ENCONTRADO = frozenset({"ResourceNotFoundError"})

#: Nombres de clase del SDK que significan "no puedes leerlo".
ERRORES_DE_ACCESO = frozenset(
    {"ClientAuthenticationError", "CredentialUnavailableError"}
)

#: Códigos HTTP que son problema de permisos, no de disponibilidad.
CODIGOS_DE_ACCESO = frozenset({401, 403})


def _importar_sdk() -> tuple[type, type]:
    """
    Import PEREZOSO del SDK de Azure: (BlobClient, DefaultAzureCredential).

    Vive aquí solo, y solo se ejecuta cuando de verdad hay que leer un blob.
    Un entorno sin el SDK sigue ejecutando el camino local y toda la suite.
    """
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobClient

    return BlobClient, DefaultAzureCredential


def _nombres_de_clase(exc: BaseException) -> set[str]:
    """Nombres de la clase de la excepción y de todos sus ancestros."""
    return {tipo.__name__ for tipo in type(exc).__mro__}


class BlobAuxFileSource:
    """Adaptador de lectura de blobs. Cumple el puerto `AuxFileSource`."""

    def __init__(
        self,
        blob_client_factory: Callable[[AuxFileRef], Any] | None = None,
        *,
        importar_sdk: Callable[[], tuple[type, type]] = _importar_sdk,
    ) -> None:
        """
        `blob_client_factory` es el punto de inyección del doble en los tests:
        el SDK no se parchea nunca. `importar_sdk` existe para poder verificar
        la construcción del cliente por defecto sin tener el SDK instalado.
        """
        self._blob_client_factory = blob_client_factory or self._cliente_por_defecto
        self._importar_sdk = importar_sdk
        self._credential: Any | None = None

    def read_bytes(self, ref: AuxFileRef) -> bytes:
        """Descarga el blob entero a memoria. No escribe nada en disco (R11)."""
        cliente = self._blob_client_factory(ref)
        try:
            return bytes(cliente.download_blob().readall())
        except Exception as exc:  # se reclasifica y se relanza, nunca se traga
            raise self._traducir(ref, exc) from exc

    # -- Cliente por defecto -------------------------------------------------

    def _cliente_por_defecto(self, ref: AuxFileRef) -> Any:
        """`BlobClient` autenticado con `DefaultAzureCredential`, sin secretos."""
        try:
            blob_client_cls, credential_cls = self._importar_sdk()
        except ImportError as exc:
            raise AuxFileAccessError(
                f"Falta el SDK de Azure para leer el Excel auxiliar "
                f"'{ref.logical_name}' desde {ref.display} (variable {ref.env_var}): "
                f"{exc}. Instala las dependencias del proyecto con "
                f"'pip install -r requirements.txt' (paquetes azure-storage-blob y "
                f"azure-identity); en la imagen del ETL ya viajan instaladas."
            ) from exc

        if self._credential is None:
            # Una credencial por instancia, reutilizada para los tres ficheros:
            # DefaultAzureCredential recorre varias fuentes y no es barata.
            self._credential = credential_cls()

        return blob_client_cls(
            account_url=f"https://{ref.account}{BLOB_HOST_SUFFIX}",
            container_name=ref.container,
            blob_name=ref.blob_name,
            credential=self._credential,
        )

    # -- Traducción de errores ------------------------------------------------

    def _traducir(self, ref: AuxFileRef, exc: Exception) -> AuxFileError:
        """Convierte un fallo del SDK en el error del puerto que le corresponde."""
        if isinstance(exc, AuxFileError):
            return exc

        nombres = _nombres_de_clase(exc)
        codigo = getattr(exc, "status_code", None)

        if nombres & ERRORES_NO_ENCONTRADO:
            return AuxFileNotFoundError(
                f"No existe el Excel auxiliar '{ref.logical_name}' en Azure Blob "
                f"Storage: cuenta '{ref.account}', contenedor '{ref.container}', "
                f"blob '{ref.blob_name}' (variable {ref.env_var}). Sube el fichero al "
                f"contenedor '{ref.container}' con ese nombre exacto, o corrige la "
                f"variable si el blob se llama de otra forma."
            )

        if nombres & ERRORES_DE_ACCESO or codigo in CODIGOS_DE_ACCESO:
            return AuxFileAccessError(
                f"Acceso denegado al leer el Excel auxiliar '{ref.logical_name}' "
                f"({ref.display}, variable {ref.env_var}). La identidad que ejecuta el "
                f"ETL necesita el rol 'Storage Blob Data Reader' sobre la cuenta de "
                f"almacenamiento '{ref.account}'. En Azure: comprueba que el Container "
                f"Apps Job tiene identidad gestionada y ese rol asignado. En local: "
                f"ejecuta 'az login' con una cuenta que lo tenga. Detalle: {exc}"
            )

        return AuxFileError(
            f"Fallo al leer el Excel auxiliar '{ref.logical_name}' "
            f"({ref.display}, variable {ref.env_var}): "
            f"{type(exc).__name__}: {exc}"
        )
