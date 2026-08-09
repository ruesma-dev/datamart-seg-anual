# etl_sigrid/infrastructure/excel/aux_file_source.py
"""
Puerto de lectura de los Excels auxiliares, con adaptador local.

El resto del código pide "el contenido del fichero X" y no sabe si vive en el
sistema de ficheros o en un contenedor de Azure Blob Storage: eso lo decide la
FORMA del valor de la variable `AUX_EXCEL_*`, no una variable de modo aparte.

Una URI `https://<cuenta>.blob.core.windows.net/<contenedor>/<blob>` se lee de
Blob Storage con identidad gestionada; cualquier otra cosa (ruta Windows,
POSIX o UNC) se lee del disco. No hay cadenas de conexión, claves de cuenta ni
tokens SAS en ninguno de los dos caminos: un secreto en una variable de
entorno es justo lo que este diseño evita.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

#: Sufijo del host de cualquier cuenta de Azure Blob Storage.
BLOB_HOST_SUFFIX = ".blob.core.windows.net"

#: Forma que debe tener una URI de blob. Se enseña en los errores de configuración.
BLOB_URI_FORM = f"https://<cuenta>{BLOB_HOST_SUFFIX}/<contenedor>/<blob>"

ORIGIN_LOCAL = "local"
ORIGIN_BLOB = "blob"


class AuxFileError(RuntimeError):
    """Fallo al obtener un Excel auxiliar. Raíz de la jerarquía."""


class AuxFileConfigError(AuxFileError):
    """El valor de la variable `AUX_EXCEL_*` no es utilizable (R5, R6, R7)."""


class AuxFileNotFoundError(AuxFileError):
    """El fichero configurado no existe, ni en disco ni en el contenedor (R8, R9)."""


class AuxFileAccessError(AuxFileError):
    """Existe pero no se puede leer: permisos o credencial ausente (R10)."""


@dataclass(frozen=True, slots=True)
class AuxFileRef:
    """
    Un Excel auxiliar ya resuelto: de dónde sale y cómo se nombra en un log.

    Es el único objeto que cruza la frontera entre el step (aplicación) y los
    adaptadores (infraestructura): el step no manipula URIs ni rutas.
    """

    logical_name: str
    env_var: str
    origin: str
    local_path: str | None = None
    account: str | None = None
    container: str | None = None
    blob_name: str | None = None

    @property
    def display(self) -> str:
        """
        Ubicación legible y segura para log.

        Nunca devuelve la URI cruda: si un día se colara un token en el valor,
        no puede acabar en stdout por esta vía.
        """
        if self.origin == ORIGIN_BLOB:
            return f"blob: {self.account}/{self.container}/{self.blob_name}"
        return f"ruta local: {self.local_path}"


def _sin_secretos(valor: str) -> str:
    """Corta la URI antes de la query y del fragmento: un SAS no se imprime jamás."""
    return valor.split("?", 1)[0].split("#", 1)[0]


def parse_aux_file_ref(logical_name: str, env_var: str, raw_value: str) -> AuxFileRef:
    """
    Clasifica el valor de una variable `AUX_EXCEL_*` y lo descompone.

    Orden de decisión (R2, R3, R5, R6, R7):

    1. Vacío -> error de configuración. El step filtra las vacías antes de
       llamar aquí, así que llegar con vacío es un fallo del llamante.
    2. ``http://`` -> error: la identidad gestionada exige TLS.
    3. ``https://`` -> URI de blob si el host termina en el sufijo de Blob
       Storage; si no, error (nunca se degrada a ruta local).
    4. Cualquier otra cosa -> ruta del sistema de ficheros, tal cual.
    """
    valor = raw_value.strip()
    if not valor:
        raise AuxFileConfigError(
            f"La variable {env_var} (Excel auxiliar '{logical_name}') está vacía. "
            f"Indica una ruta del sistema de ficheros o una URI de blob "
            f"con la forma {BLOB_URI_FORM}."
        )

    minusculas = valor.lower()

    if minusculas.startswith("http://"):
        raise AuxFileConfigError(
            f"La variable {env_var} (Excel auxiliar '{logical_name}') usa http:// sin "
            f"cifrar: '{_sin_secretos(valor)}'. Azure Blob Storage se lee siempre por "
            f"https, que es lo que exige la autenticación con identidad gestionada. "
            f"Forma esperada: {BLOB_URI_FORM}."
        )

    if minusculas.startswith("https://"):
        return _parse_blob_uri(logical_name, env_var, valor)

    return AuxFileRef(
        logical_name=logical_name,
        env_var=env_var,
        origin=ORIGIN_LOCAL,
        local_path=valor,
    )


def _parse_blob_uri(logical_name: str, env_var: str, valor: str) -> AuxFileRef:
    """Descompone una URI https en cuenta, contenedor y nombre de blob."""
    partes = urlsplit(valor)
    host = partes.hostname or ""
    seguro = _sin_secretos(valor)

    if not host.endswith(BLOB_HOST_SUFFIX):
        raise AuxFileConfigError(
            f"La variable {env_var} (Excel auxiliar '{logical_name}') apunta a "
            f"'{seguro}', cuyo host '{host}' no es una cuenta de Azure Blob Storage. "
            f"Se espera un host terminado en '{BLOB_HOST_SUFFIX}' "
            f"(forma: {BLOB_URI_FORM}) o una ruta del sistema de ficheros."
        )

    if partes.query or partes.fragment:
        raise AuxFileConfigError(
            f"La variable {env_var} (Excel auxiliar '{logical_name}') lleva parámetros "
            f"tras la URI '{seguro}'. No se admiten tokens SAS ni claves: el ETL lee "
            f"los blobs con identidad gestionada, y un token en una variable de entorno "
            f"es un secreto que además caduca. Deja la URI con la forma "
            f"{BLOB_URI_FORM} y asigna el rol 'Storage Blob Data Reader' a la identidad "
            f"que ejecuta el ETL."
        )

    account = host[: -len(BLOB_HOST_SUFFIX)]
    container, _, blob_name = partes.path.lstrip("/").partition("/")

    if not account or not container or not blob_name:
        raise AuxFileConfigError(
            f"La variable {env_var} (Excel auxiliar '{logical_name}') vale '{seguro}', "
            f"que no identifica cuenta, contenedor y blob. Forma esperada: "
            f"{BLOB_URI_FORM}."
        )

    return AuxFileRef(
        logical_name=logical_name,
        env_var=env_var,
        origin=ORIGIN_BLOB,
        account=account,
        container=container,
        blob_name=blob_name,
    )
