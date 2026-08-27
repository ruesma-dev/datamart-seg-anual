# tests/test_f003_infra.py
"""
F-003 · Tests del andamiaje de despliegue (R1-R11, R16-R19, R25, R26).

Ninguno toca red, ni Azure, ni BBDD: se leen los ficheros del repositorio y se
analizan como texto, y el contrato de variables de entorno del job se comprueba
por introspección de los modelos de `config/settings.py`.

La idea de fondo: un error en `infra/` no se manifiesta hasta las 02:00 de una
noche cualquiera, y para entonces nadie está mirando. Estos tests adelantan a
`pytest` los fallos que hoy solo aparecerían en Azure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from config.settings import (
    AuxExcelSettings,
    LoggingSettings,
    PostgresSettings,
    SigridApiSettings,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
INFRA = REPO_ROOT / "infra"
ENV_DIR = INFRA / "env"
SPEC_DIR = REPO_ROOT / "specs" / "F-003-infra-caj"
PROGRESS = REPO_ROOT / "progress"

# El cargador es el único script que puede nombrar el entorno por defecto (R2).
CARGADOR = "00_vars.ps1"

# Claves que todo fichero de entorno debe traer (§3 del diseño).
CLAVES_OBLIGATORIAS = (
    "environment",
    "location",
    "resourceGroup",
    "logAnalytics",
    "logRetentionDays",
    "containerAppsEnv",
    "job",
    "storageAccount",
    "auxContainer",
    "auxBlobs",
    "keyVault",
    "sigridSecretName",
    "jobSecretName",
    "managedIdentity",
    "acrName",
    "acrResourceGroup",
    "imageRepository",
    "cron",
    # Puerta del incidente del disco: obligatoria a propósito. Un fichero de
    # entorno nuevo que la olvide no se queda «sin puerta», se queda en rojo.
    "jobProgramable",
    "replicaTimeoutSeconds",
    "replicaRetryLimit",
    "parallelism",
    "replicaCompletionCount",
    "cpu",
    "memory",
    "sigridApiBaseUrl",
    # DA-4 opción B (enmienda del 2026-08-10): la contraseña de Postgres viaja
    # como referencia a Key Vault, así que el entorno declara dónde vive.
    "pgSecretName",
    "pgJobSecretName",
    "pgReadonlySecretName",
    "pgHost",
    "pgPort",
    "pgDatabase",
    "pgUser",
    "pgAuthMode",
    "pgSetRole",
    "pgReadonlyRole",
    "pgAutoCreateDb",
    "pgResourceGroup",
    "logLevel",
    "logFormat",
    "alertName",
    "alertActionGroupName",
    "alertActionGroupRg",
    # F-024: la alerta de frescura y su umbral. Obligatorias a propósito: un
    # entorno nuevo que las olvide no se queda «sin alerta de frescura», se
    # queda en rojo.
    "frescuraAlertName",
    "frescuraUmbralHoras",
    "tags",
)

TAGS_OBLIGATORIOS = (
    "acens-project",
    "acens-environment",
    "acens-customer",
    "acens-costcenter",
    "acens-compliance",
    "acens-responsable-iac",
    "acens-support",
)

# Claves cuyo valor ES el nombre de un recurso (o de un rol de base de datos).
# Ninguno de esos literales puede aparecer escrito en un `.ps1`: ahí es donde
# se cablea un entorno sin darse cuenta.
CLAVES_NOMBRE_DE_RECURSO = (
    "resourceGroup",
    "logAnalytics",
    "containerAppsEnv",
    "job",
    "storageAccount",
    "keyVault",
    "sigridSecretName",
    "managedIdentity",
    "acrName",
    "acrResourceGroup",
    "imageRepository",
    "sigridApiBaseUrl",
    "pgSecretName",
    "pgReadonlySecretName",
    "pgHost",
    "pgDatabase",
    "pgUser",
    "pgSetRole",
    "pgReadonlyRole",
    "pgResourceGroup",
    "alertName",
    "alertActionGroupName",
    "alertActionGroupRg",
    "frescuraAlertName",
)

# `auxContainer` ("aux") queda fuera de la lista de arriba a propósito: son tres
# letras que aparecen en prosa legítima ("Excels auxiliares"). Se comprueba de
# otra forma: el script que crea el contenedor tiene que leerlo de $CFG.

PREFIJOS_DEL_CONTRATO = ("PG_", "SIGRID_API_", "AUX_EXCEL_", "LOG_")


# --- utilidades -------------------------------------------------------------


def _ps1() -> list[Path]:
    """Todos los scripts de `infra/`, en orden de ejecución (por nombre)."""
    return sorted(INFRA.glob("*.ps1"))


def _texto(ruta: Path) -> str:
    """Contenido de un fichero descontando el BOM."""
    return ruta.read_text(encoding="utf-8-sig")


def _script(nombre: str) -> str:
    return _texto(INFRA / nombre)


def _config(nombre: str = "dev") -> dict:
    return json.loads(_texto(ENV_DIR / f"{nombre}.json"))


def _entornos() -> list[Path]:
    return sorted(ENV_DIR.glob("*.json"))


# ---------------------------------------------------------------------------
# R1 · los nombres viven en el fichero de entorno, no en los scripts
# ---------------------------------------------------------------------------


def test_f003_r1_dev_json_tiene_todas_las_claves_obligatorias() -> None:
    """El fichero de entorno declara todo lo que el despliegue necesita."""
    cfg = _config("dev")

    faltan = [c for c in CLAVES_OBLIGATORIAS if c not in cfg]
    assert not faltan, f"faltan claves obligatorias en infra/env/dev.json: {faltan}"

    faltan_tags = [t for t in TAGS_OBLIGATORIOS if t not in cfg["tags"]]
    assert not faltan_tags, f"faltan tags acens-* : {faltan_tags}"

    # Los tres Excels auxiliares que consume F-004, por su nombre lógico.
    assert set(cfg["auxBlobs"]) == {"tipo_partida", "tipo_coste", "mapeo_proporcionales"}


def test_f003_r1_los_ps1_no_contienen_nombres_de_recurso() -> None:
    """
    Ningún nombre concreto de recurso está escrito en un `.ps1`.

    Es la condición que hace que crear `sta` o `pro` sea añadir un fichero de
    datos y no duplicar doce scripts.
    """
    cfg = _config("dev")
    prohibidos = {c: str(cfg[c]) for c in CLAVES_NOMBRE_DE_RECURSO}

    for script in _ps1():
        texto = _script(script.name)
        for clave, valor in prohibidos.items():
            assert valor not in texto, (
                f"{script.name} escribe el valor de '{clave}' ({valor!r}) en vez de "
                f"leerlo de $CFG"
            )


def test_f003_r1_todos_los_scripts_leen_del_fichero_de_entorno() -> None:
    """Contraste del test anterior: no basta con no cablear, hay que leer de $CFG."""
    for script in _ps1():
        if script.name == CARGADOR:
            continue
        texto = _script(script.name)
        assert "$CFG." in texto, f"{script.name} no lee ningún valor de $CFG"

    # Y el contenedor de los Excels tampoco se escribe a mano.
    assert "$CFG.auxContainer" in _script("40_create_storage.ps1")


# ---------------------------------------------------------------------------
# R2 · el entorno se resuelve por parámetro, por variable o por defecto
# ---------------------------------------------------------------------------


def test_f003_r2_00_vars_resuelve_el_entorno_por_parametro_o_variable() -> None:
    """`-Entorno` manda; luego `$env:DATAMART_ENV`; y solo entonces el defecto."""
    texto = _script(CARGADOR)

    assert re.search(r"param\s*\(\s*(\[[^\]]*\]\s*)*\$Entorno", texto), (
        "00_vars.ps1 debe admitir el parámetro -Entorno"
    )

    # El orden es el que decide quién manda: primero el parámetro (que llega ya
    # asignado), luego la variable de entorno y solo entonces el defecto.
    de_variable = re.search(r"\$Entorno\s*=\s*\$env:DATAMART_ENV", texto)
    de_defecto = re.search(r"\$Entorno\s*=\s*[\"']\w+[\"']", texto)

    assert de_variable, "no se consulta $env:DATAMART_ENV"
    assert de_defecto, "no hay entorno por defecto"
    assert de_variable.start() < de_defecto.start(), (
        "el defecto se aplica antes que $env:DATAMART_ENV: la variable no serviría"
    )

    # El literal del entorno por defecto solo puede aparecer en el cargador.
    for script in _ps1():
        if script.name == CARGADOR:
            continue
        assert not re.search(r"\bdev\b", _script(script.name)), (
            f"{script.name} nombra un entorno concreto: eso rompe la parametrización"
        )


@pytest.mark.parametrize("fichero", [p.name for p in _entornos()] or ["dev.json"])
def test_f003_r2_todos_los_env_json_validan_igual(fichero: str) -> None:
    """Cualquier fichero que se añada a `infra/env/` cumple el mismo esquema."""
    cfg = _config(Path(fichero).stem)

    faltan = [c for c in CLAVES_OBLIGATORIAS if c not in cfg]
    assert not faltan, f"{fichero}: faltan claves {faltan}"
    assert cfg["environment"] == Path(fichero).stem, (
        f"{fichero}: la clave 'environment' debe coincidir con el nombre del fichero"
    )
    assert set(TAGS_OBLIGATORIOS) <= set(cfg["tags"])


# ---------------------------------------------------------------------------
# R3 · valores incompletos abortan antes de tocar Azure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fichero", [p.name for p in _entornos()] or ["dev.json"])
def test_f003_r3_ningun_valor_obligatorio_vacio_ni_TODO(fichero: str) -> None:  # noqa: N802
    """Un `TODO_` olvidado en el fichero de entorno es un despliegue a medias."""
    cfg = _config(Path(fichero).stem)

    for clave in CLAVES_OBLIGATORIAS:
        valor = cfg[clave]
        assert valor not in ("", None, {}), f"{fichero}: '{clave}' está vacía"
        if isinstance(valor, str):
            assert "TODO" not in valor.upper(), f"{fichero}: '{clave}' sigue con un TODO"

    for tag, valor in cfg["tags"].items():
        assert valor, f"{fichero}: el tag '{tag}' está vacío"
        assert "TODO" not in str(valor).upper(), f"{fichero}: el tag '{tag}' sigue con un TODO"


def test_f003_r3_00_vars_valida_antes_de_llamar_a_az() -> None:
    """
    La validación va ANTES del primer `az`. Al revés, un fichero incompleto
    crearía medio entorno y abortaría a la mitad, que es lo caro de deshacer.
    """
    texto = _script(CARGADOR)

    assert "throw" in texto, "00_vars.ps1 no aborta nunca: falta el validador"

    invocacion_az = re.search(r"(?m)^[^#\r\n]*(?<![\w-])az\s+\w", texto)
    assert invocacion_az is not None, "00_vars.ps1 debe resolver la suscripción con az"
    assert texto.index("throw") < invocacion_az.start(), (
        "hay una llamada a 'az' antes de validar el fichero de entorno"
    )


# ---------------------------------------------------------------------------
# R4, R26 · ni un identificador, ni una clave, ni un correo en el repositorio
# ---------------------------------------------------------------------------

# Lo que no puede aparecer en NINGUNO de los tres árboles vigilados. Son
# patrones sin ambigüedad: un GUID es un GUID y un correo es un correo.
PATRONES_PROHIBIDOS = {
    "GUID (suscripción o tenant)": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
                                   r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
    "dirección de correo": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    # Asignación con valor detrás. Se admiten el vacío y las referencias
    # ($VAR, <marcador>, {placeholder}, secretref:, ***): lo que se busca es un
    # literal, no la palabra 'password', que aparece por todas partes.
    #
    # La comilla invertida se exime SOLO cuando CIERRA un código en línea de
    # Markdown, o sea cuando no lleva un valor pegado detrás. La distinción
    # importa y por eso no vale eximirla a secas: un informe que enumera los
    # patrones de este mismo barrido escribe `password=` como código y no es
    # ningún secreto —pasó el 2026-08-26 y dejó el portero en rojo—, mientras
    # que una contraseña citada como código sí tiene que seguir cazándose.
    "contraseña escrita": (
        r"(?i)\bpassword\s*=\s*"
        r"(?![#$%<*{\"'\s]|secretref:|keyvaultref:|`(?![A-Za-z0-9_./+-]))\S"
    ),
}

# Patrones con forma de clave. Se aplican solo a `infra/` y a la spec de la
# feature, que es por donde una clave podría entrar de verdad: los informes de
# `progress/` hablan DE los secretos —el de F-004 documenta cómo se rechaza un
# SAS— y buscarlos ahí produce falsos positivos, que es justo lo que inutiliza
# un barrido (mismo hallazgo que el anotado para F-016).
PATRONES_DE_CLAVE = {
    "clave de cuenta de almacenamiento": r"AccountKey\s*=\s*[A-Za-z0-9+/]{20,}",
    "token SAS": r"(?:SharedAccessSignature=|[?&]sig=)[A-Za-z0-9%+/]{16,}",
    "clave privada": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "clave de function app": r"x-functions-key\s*[:=]\s*[^\s<$\"'#]",
}


def _buscar(carpetas: tuple[Path, ...], patrones: dict[str, str]) -> list[str]:
    hallazgos: list[str] = []
    for carpeta in carpetas:
        for fichero in sorted(p for p in carpeta.rglob("*") if p.is_file()):
            texto = fichero.read_text(encoding="utf-8-sig", errors="replace")
            for descripcion, patron in patrones.items():
                encontrado = re.search(patron, texto)
                if encontrado:
                    relativo = fichero.relative_to(REPO_ROOT).as_posix()
                    hallazgos.append(
                        f"{relativo}: {descripcion} -> {encontrado.group(0)!r}"
                    )
    return hallazgos


def test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec() -> None:
    """
    Barrido sobre `infra/`, la spec de F-003 y `progress/`.

    El ID de suscripción se toma del contexto de `az` o de una variable de
    entorno; nunca se escribe. Los correos de las alertas se resuelven contra
    el action group existente (R26).
    """
    hallazgos = _buscar((INFRA, SPEC_DIR, PROGRESS), PATRONES_PROHIBIDOS)
    hallazgos += _buscar((INFRA, SPEC_DIR), PATRONES_DE_CLAVE)

    assert not hallazgos, "el repositorio contiene datos que no deben versionarse:\n" + (
        "\n".join(hallazgos)
    )


@pytest.mark.parametrize(
    "texto, debe_cazarlo, que_es",
    [
        # El falso positivo real del 2026-08-26: el informe del reviewer
        # enumeraba los patrones de este mismo barrido y dejó el portero rojo.
        ("con los patrones `password=`, `pwd=`, `secret=`", False, "cita de Markdown"),
        # Y la otra cara, que es la que impide que el arreglo afloje el
        # guardián: una contraseña citada como código SIGUE cazándose.
        ("password=`hunter2`", True, "contraseña entre comillas invertidas"),
        ("password=hunter2", True, "contraseña a pelo"),
        ("Password = SuperSecreta1", True, "con mayúscula y espacios"),
        ("password=$PGPASSWORD", False, "referencia a variable"),
        ("password=", False, "valor vacío"),
        ("password=<pon-la-tuya>", False, "marcador"),
        ("password=secretref:pg-pass", False, "referencia a secreto"),
    ],
)
def test_f003_r4_la_contrasena_escrita_distingue_la_cita_del_secreto(
    texto: str, debe_cazarlo: bool, que_es: str
) -> None:
    """El patrón «contraseña escrita», caso a caso, por sus dos caras.

    Existe porque el arreglo del falso positivo tenía una versión fácil y
    equivocada: eximir la comilla invertida a secas. Eso habría dejado pasar
    una contraseña escrita como código en línea, que es una forma
    perfectamente normal de documentar mal un secreto. Se exime solo cuando la
    comilla CIERRA —sin valor pegado detrás—, y este test fija las dos caras
    para que nadie afloje la de arriba creyendo que arregla la de abajo.
    """
    hallado = re.search(PATRONES_PROHIBIDOS["contraseña escrita"], texto)
    if debe_cazarlo:
        assert hallado, f"el guardián deja pasar {que_es}: {texto!r}"
    else:
        assert not hallado, (
            f"el guardián da un falso positivo con {que_es}: {texto!r} -> "
            f"{hallado.group(0)!r}" if hallado else ""
        )


def test_f003_r26_el_script_de_alerta_no_lleva_correos_literales() -> None:
    """Los destinatarios llegan por parámetro o del action group ya existente."""
    texto = _script("90_create_alert.ps1")

    assert not re.search(PATRONES_PROHIBIDOS["dirección de correo"], texto)
    assert "-AlertEmail" in texto, "no hay forma de pasar destinatarios sin tocar el script"
    assert "action-group" in texto, "la alerta debe resolverse contra un action group"


# ---------------------------------------------------------------------------
# R5 · codificación y cabecera de los scripts
# ---------------------------------------------------------------------------


def test_f003_r5_ps1_utf8_bom_crlf_y_cabecera_de_ruta() -> None:
    """
    UTF-8 con BOM y CRLF (docs/CONVENTIONS.md) y primera línea con la ruta.

    Sin BOM, PowerShell 5.1 destroza los acentos de los mensajes; y sin la
    cabecera, un script suelto no dice de dónde viene.
    """
    scripts = _ps1()
    assert scripts, "no hay ningún script en infra/"

    for script in scripts:
        crudo = script.read_bytes()
        assert crudo.startswith(b"\xef\xbb\xbf"), f"{script.name} no está en UTF-8 con BOM"
        assert b"\r\n" in crudo, f"{script.name} no usa CRLF"
        assert not re.search(rb"(?<!\r)\n", crudo), f"{script.name} mezcla LF y CRLF"

        primera = _texto(script).splitlines()[0]
        assert primera == f"# infra/{script.name}", (
            f"{script.name}: la primera línea debe ser '# infra/{script.name}'"
        )


# ---------------------------------------------------------------------------
# R6 · el README explica el orden y no se deja ningún script fuera
# ---------------------------------------------------------------------------


def test_f003_r6_readme_menciona_todos_los_scripts_en_orden() -> None:
    """Todo `.ps1` presente en `infra/` está en el README, y en orden de ejecución."""
    readme = _texto(INFRA / "README.md")

    posiciones = []
    for script in _ps1():
        assert script.name in readme, f"{script.name} no está documentado en infra/README.md"
        posiciones.append(readme.index(script.name))

    assert posiciones == sorted(posiciones), (
        "el README no menciona los scripts en el orden en que se ejecutan"
    )

    # Lo que el humano tiene que ejecutar a mano, y la consulta de logs de R24.
    assert "ContainerAppConsoleLogs_CL" in readme, "falta la consulta KQL de R24"
    assert "DATAMART_ENV" in readme, "falta cómo se añade un entorno nuevo"


# ---------------------------------------------------------------------------
# R7 · el contrato de variables de entorno del job
# ---------------------------------------------------------------------------


def _nombres_declarados_en_settings() -> set[str]:
    """Nombres de variable de entorno que `config/settings.py` sabe leer."""
    nombres: set[str] = set()
    for clase in (SigridApiSettings, PostgresSettings, AuxExcelSettings, LoggingSettings):
        prefijo = str(clase.model_config.get("env_prefix") or "")
        for campo in clase.model_fields:
            nombres.add(f"{prefijo}{campo}".upper())
    return nombres


def _env_vars_del_job() -> list[str]:
    """Nombres de variable que el script del job pasa al contenedor."""
    texto = _script("80_create_job.ps1")
    return re.findall(r'"([A-Z][A-Z0-9_]*)=', texto)


def test_f003_r7_env_vars_del_job_existen_en_settings() -> None:
    """
    Toda variable `PG_*`, `SIGRID_API_*`, `AUX_EXCEL_*` o `LOG_*` que el job
    inyecta corresponde a un campo real de la configuración.

    Es el test que evita el fallo de las 02:00: una variable mal escrita que el
    ETL ignora en silencio y una carga que corre con el valor por defecto.
    """
    declaradas = _nombres_declarados_en_settings()
    pasadas = [v for v in _env_vars_del_job() if v.startswith(PREFIJOS_DEL_CONTRATO)]

    assert pasadas, "el script del job no pasa ninguna variable de configuración"

    desconocidas = sorted(set(pasadas) - declaradas)
    assert not desconocidas, (
        f"el job pasa variables que config/settings.py no lee: {desconocidas}"
    )

    # Y las imprescindibles están: sin ellas el job arranca y falla al conectar.
    for imprescindible in ("PG_HOST", "PG_DB", "PG_USER", "SIGRID_API_BASE_URL"):
        assert imprescindible in pasadas, f"el job no pasa {imprescindible}"


def test_f003_r7_el_job_inyecta_azure_client_id_de_la_identidad() -> None:
    """
    Con identidad asignada por el usuario (R19), `DefaultAzureCredential` no
    adivina cuál usar: necesita `AZURE_CLIENT_ID`.

    No lo cubre el barrido de prefijos —es una variable del SDK de Azure, no de
    `config/settings.py`— y su ausencia no se nota hasta la primera lectura de
    un blob. Aviso del reviewer de F-004.
    """
    variables = _env_vars_del_job()
    assert "AZURE_CLIENT_ID" in variables, (
        "el job no inyecta AZURE_CLIENT_ID: DefaultAzureCredential no sabrá qué "
        "identidad usar al leer los Excels del blob (F-004)"
    )


def test_f003_r7_el_job_fija_las_salvaguardas_de_la_base_compartida() -> None:
    """
    El job escribe en un servidor que además sirve a `albaranes` y `partes`.

    `PG_AUTO_CREATE_DB=false` impide un `CREATE DATABASE` ahí, y `PG_SET_ROLE`
    mantiene el propietario de los objetos. `PG_READONLY_ROLE` es lo que hace
    que `apply_grants` no sea un no-op y el MCP no pierda el acceso cada noche.
    """
    texto = _script("80_create_job.ps1")
    variables = _env_vars_del_job()

    for imprescindible in ("PG_AUTO_CREATE_DB", "PG_SET_ROLE", "PG_READONLY_ROLE"):
        assert imprescindible in variables, f"el job no pasa {imprescindible}"

    assert re.search(r'"PG_AUTO_CREATE_DB=\$\(?\$CFG\.pgAutoCreateDb', texto), (
        "PG_AUTO_CREATE_DB debe salir del fichero de entorno"
    )


# ---------------------------------------------------------------------------
# R8 · el alcance de la carga vive en el Dockerfile, en un solo sitio
# ---------------------------------------------------------------------------


def test_f003_r8_dockerfile_cmd_es_run_all_full() -> None:
    """La ejecución programada es siempre `run-all --full`."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert re.search(r'CMD\s*\[\s*"run-all"\s*,\s*"--full"\s*\]', dockerfile)
    assert re.search(r'ENTRYPOINT\s*\[\s*"python"\s*,\s*"main\.py"\s*\]', dockerfile)


def test_f003_r8_el_job_no_sobrescribe_el_comando_de_la_imagen() -> None:
    """
    Ni al crear ni al actualizar el job se pasa comando ni argumentos: si el
    alcance estuviera escrito en dos sitios, un día dejarían de coincidir.
    """
    for nombre in ("80_create_job.ps1", "85_update_job.ps1"):
        texto = _script(nombre)
        assert not re.search(r"--command\b", texto), f"{nombre} sobrescribe el comando"
        assert not re.search(r"--args\b", texto), f"{nombre} sobrescribe los argumentos"


# ---------------------------------------------------------------------------
# R9 · la programación sale del fichero de entorno
# ---------------------------------------------------------------------------


def test_f003_r9_cron_del_entorno_dev_es_0_2() -> None:
    """`0 2 * * *` UTC, y escrito una sola vez."""
    assert _config("dev")["cron"] == "0 2 * * *"

    for script in _ps1():
        assert not re.search(r"\d+\s+\d+\s+\*\s+\*\s+\*", _script(script.name)), (
            f"{script.name} lleva una expresión cron escrita a mano"
        )


# ---------------------------------------------------------------------------
# R10 · ningún valor de secreto viaja al contenedor
# ---------------------------------------------------------------------------
#
# ENMIENDA 2026-08-10 (DA-4, opción B, aprobada por el humano). R10 decía «el
# sistema no debe pasar ninguna contraseña al contenedor: no puede existir
# PG_PASSWORD». El servidor tiene la autenticación Entra deshabilitada y
# habilitarla afecta a `albaranes` y `partes`, así que el job se autentica como
# `sigrid_dm_app` con su contraseña. Lo que cambia es el nombre de la variable
# que se admite; lo que NO cambia —y es lo que estos tests sujetan— es que un
# VALOR de secreto no puede aparecer nunca: la contraseña viaja igual que la
# clave de sigrid-api, como referencia a Key Vault resuelta por la identidad
# gestionada. Ver specs/F-003-infra-caj/requirements.md §Enmiendas.


def _valores_de_secretos(texto: str) -> list[str]:
    """
    Los valores que un script pasa en `--secrets`, estén escritos en la llamada
    o dentro del array que se le pasa por variable.

    Mirar solo a los literales de la llamada era suficiente cuando el job tenía
    un secreto fijo. Al volverse condicional (la contraseña solo existe en modo
    `password`), el array pasó a construirse antes, y un test que solo mirase
    `--secrets "..."` se quedaría mirando a un sitio vacío: verde por no
    encontrar nada, que es la peor forma de estar verde.
    """
    valores: list[str] = []

    # Un argumento es una cadena entre comillas o una variable suelta. El orden
    # de la alternancia importa: la cadena se consume entera, para no confundir
    # una variable interpolada DENTRO del literal con el argumento en sí.
    argumento = r'"[^"]+"|\$\w+'
    for bloque in re.findall(rf"--secrets\s+((?:{argumento})(?:\s*`?\s*(?:{argumento}))*)", texto):
        for token in re.findall(argumento, bloque):
            if token.startswith('"'):
                valores.append(token.strip('"'))
            else:
                # Variable: valen las cadenas que se le asignan o se le añaden.
                valores += re.findall(rf'\{token}\s*\+?=\s*@?\(?\s*"([^"]+)"', texto)

    return valores


def test_f003_r10_ninguna_contrasena_literal_en_los_scripts() -> None:
    """
    Ni credenciales de registro, ni un `--secrets` con el valor escrito, ni un
    `PG_PASSWORD` con nada que no sea una referencia.

    Un secreto que no está escrito no se filtra por el repositorio ni hay que
    rotarlo cuando alguien clona el proyecto.
    """
    for script in _ps1():
        texto = _script(script.name)
        assert "--registry-password" not in texto, f"{script.name} usa credenciales de ACR"
        assert "--registry-username" not in texto, f"{script.name} usa credenciales de ACR"

        for secreto in _valores_de_secretos(texto):
            assert "keyvaultref:" in secreto, (
                f"{script.name} pasa un secreto literal: {secreto!r}"
            )

        for asignacion in re.finditer(r"PG_PASSWORD\s*=\s*(\S*)", texto):
            valor = asignacion.group(1)
            assert valor.startswith("secretref:"), (
                f"{script.name} asigna a PG_PASSWORD algo que no es una referencia al "
                f"secreto del job: {valor!r}"
            )


def test_f003_r10_el_secreto_de_sigrid_se_pasa_por_keyvaultref() -> None:
    """La clave de sigrid-api viaja como referencia, resuelta por la identidad."""
    texto = _script("80_create_job.ps1")

    assert "keyvaultref:" in texto
    assert "identityref:" in texto
    assert "secretref:" in texto, "la variable de entorno debe referenciar el secreto"
    assert "$CFG.sigridSecretName" in texto, "el nombre del secreto sale del entorno"


def test_f003_r10_la_contrasena_de_postgres_viaja_por_keyvaultref() -> None:
    """
    ENMIENDA DA-4 (B). En modo `password`, el job declara un segundo secreto —la
    contraseña de `sigrid_dm_app`— por referencia a Key Vault, y la variable
    `PG_PASSWORD` apunta a ese secreto, nunca a un valor.

    El contraste importa: el test no vale si se limita a comprobar que no hay
    contraseñas. Aquí se exige que el mecanismo **esté**, porque sin él el job
    se crea perfecto y falla al conectar todas las noches.
    """
    cfg = _config("dev")
    texto = _script("80_create_job.ps1")

    if cfg["pgAuthMode"] != "password":
        pytest.skip("el entorno no usa contraseña; ver test del modo entra")

    assert "$CFG.pgSecretName" in texto, (
        "el nombre del secreto de Postgres en el vault sale del fichero de entorno"
    )
    assert re.search(r'"PG_PASSWORD=secretref:\$\(\$CFG\.pgJobSecretName\)"', texto), (
        "PG_PASSWORD debe referenciar el secreto del job, y su nombre sale de $CFG"
    )

    declaracion = [s for s in _valores_de_secretos(texto) if "pgJobSecretName" in s]
    assert declaracion, "el job no declara el secreto de la contraseña de Postgres"
    for secreto in declaracion:
        assert "keyvaultref:" in secreto and "identityref:" in secreto, (
            f"el secreto de la contraseña no se resuelve con la identidad gestionada: "
            f"{secreto!r}"
        )


def test_f003_r10_el_job_solo_admite_los_dos_modos_de_autenticacion_previstos() -> None:
    """
    Un `pgAuthMode` con una errata no puede crear un job a medias: aborta.

    Antes de la enmienda el script exigía `entra` y lanzaba `throw` con
    cualquier otra cosa, que era la puerta de DA-4. Cerrada la decisión, la
    puerta no desaparece: se convierte en una lista blanca.
    """
    texto = _script("80_create_job.ps1")

    assert re.search(
        r"if\s*\(\s*\$CFG\.pgAuthMode\s+-notin\s+@\([^)]*\)\s*\)\s*\{[^}]*throw", texto
    ), "80_create_job.ps1 no aborta ante un modo de autenticación desconocido"


def test_f003_el_usuario_de_postgres_cuadra_con_el_modo_de_autenticacion() -> None:
    """
    En modo `entra` el usuario **es** la identidad gestionada; en modo
    `password` es un rol nativo de la base y no puede ser la identidad.

    La review de F-003 señaló esta incoherencia (`pgUser: sigrid_dm_app` con
    `pgAuthMode: entra`). Con DA-4 cerrada queda resuelta, y este test impide
    que vuelva: cambiar el modo sin cambiar el usuario deja la suite en rojo.
    """
    cfg = _config("dev")

    if cfg["pgAuthMode"] == "entra":
        assert cfg["pgUser"] == cfg["managedIdentity"], (
            "en modo entra el usuario de Postgres tiene que ser el nombre de la "
            "identidad gestionada, que es lo que el servidor reconoce"
        )
    else:
        assert cfg["pgUser"] != cfg["managedIdentity"], (
            "en modo password el usuario es un rol nativo de la base, no la identidad"
        )


def test_f003_los_prerrequisitos_comprueban_el_modo_de_autenticacion_declarado() -> None:
    """
    `05_check_prereqs.ps1` sigue siendo quien detecta el desajuste entre lo que
    el entorno declara y lo que el servidor admite.

    Con DA-4 cerrada el modo esperado es `password`, pero el modo `entra` queda
    implementado y dormido: si alguien lo reactiva, la comprobación contra
    `authConfig.activeDirectoryAuth` tiene que seguir ahí, o el job volvería a
    crearse perfecto y a fallar de noche.
    """
    texto = _script("05_check_prereqs.ps1")

    assert '"entra"' in texto, "se ha perdido la comprobación del modo entra"
    assert '"password"' in texto, "el modo con contraseña no se reconoce"
    assert "activeDirectoryAuth" in texto, "ya no se consulta si el servidor admite Entra"
    assert "DA-4" in texto, "el rastro de la decisión desaparece del script"


# ---------------------------------------------------------------------------
# R11 · la imagen se identifica por un tag fechado
# ---------------------------------------------------------------------------


def test_f003_r11_build_pasa_image_tag_y_build_date() -> None:
    """`python main.py version` tiene que poder decir qué build está corriendo."""
    texto = _script("70_build_image.ps1")

    assert re.search(r"--build-arg\s+\"?IMAGE_TAG=", texto)
    assert re.search(r"--build-arg\s+\"?BUILD_DATE=", texto)
    assert "acr build" in texto
    assert "$CFG.acrResourceGroup" in texto, "la imagen se construye en el RG del ACR"


def test_f003_r11_el_tag_es_fechado_y_no_latest() -> None:
    """Tag `rAAAAMMDD-hhmm`, derivado una sola vez, y nunca `latest`."""
    cargador = _script(CARGADOR)

    assert "yyyyMMdd-HHmm" in cargador, "el tag fechado se deriva en 00_vars.ps1"
    assert re.search(r"\$TAG\s*=", cargador)

    for script in _ps1():
        assert "latest" not in _script(script.name), (
            f"{script.name} usa 'latest': impide saber qué build corrió una noche"
        )


# ---------------------------------------------------------------------------
# R16-R19 · lo que los scripts de aprovisionamiento tienen que decir
# ---------------------------------------------------------------------------


def test_f003_r16_el_entorno_no_se_integra_en_vnet() -> None:
    """Sin VNet: es lo que da IP de salida estática para el firewall de R23."""
    texto = _script("30_create_env.ps1")

    assert "--infrastructure-subnet-resource-id" not in texto
    assert "--logs-destination" in texto and "log-analytics" in texto
    assert "staticIp" in texto, "el script debe imprimir la IP de salida (entrada de R23)"


def test_f003_r17_storage_endurecida() -> None:
    """Sin acceso público, sin clave compartida y TLS 1.2 como mínimo."""
    texto = _script("40_create_storage.ps1")

    assert "--allow-blob-public-access false" in texto
    assert "--allow-shared-key-access false" in texto
    assert "--min-tls-version TLS1_2" in texto
    assert "--auth-mode login" in texto, "el contenedor se crea con identidad, no con clave"


def test_f003_r18_keyvault_rbac_y_sin_secreto_en_el_script() -> None:
    """El vault se crea con RBAC; el secreto lo carga el humano (T20)."""
    texto = _script("50_create_keyvault.ps1")

    assert "--enable-rbac-authorization true" in texto
    assert "secret set" not in texto, "el script no debe cargar el secreto"
    assert "secret show" not in texto, "nunca se lee el valor de un secreto"


def test_f003_r19_tres_roles_y_ningun_ambito_de_suscripcion() -> None:
    """Exactamente tres asignaciones de rol, cada una sobre su recurso."""
    texto = _script("60_create_identity.ps1")

    asignaciones = re.findall(r"role assignment create", texto)
    assert len(asignaciones) == 3, f"se esperan 3 asignaciones de rol, hay {len(asignaciones)}"

    for rol in ("AcrPull", "Key Vault Secrets User", "Storage Blob Data Reader"):
        assert rol in texto, f"falta el rol {rol}"

    ambitos = re.findall(r"--scope\s+(\S+)", texto)
    assert len(ambitos) == 3, f"se esperan 3 ámbitos, hay {len(ambitos)}"
    for ambito in ambitos:
        limpio = ambito.strip('"`')
        assert limpio.startswith("$"), (
            f"ámbito escrito a mano en vez de resuelto con 'az ... --query id': {ambito}"
        )
        assert "subscriptions" not in limpio, f"ámbito de suscripción entera: {ambito}"


# ---------------------------------------------------------------------------
# R25 · la alerta apunta al job y a un canal de aviso
# ---------------------------------------------------------------------------


def test_f003_r25_la_alerta_apunta_al_job_y_a_un_action_group() -> None:
    """Alerta de métrica sobre las ejecuciones fallidas, con severidad alta."""
    texto = _script("90_create_alert.ps1")

    assert "metrics alert create" in texto
    assert "JobExecutionCount" in texto
    assert "Failed" in texto
    assert "--severity 1" in texto
    assert "$CFG.alertName" in texto
    # La alternativa acotada del diseño queda documentada, no improvisada.
    assert "scheduled-query" in texto


# ---------------------------------------------------------------------------
# Cómo se llama a `az` desde Windows PowerShell 5.1
# ---------------------------------------------------------------------------
#
# Defecto encontrado ejecutando de verdad `05_check_prereqs.ps1` contra Azure
# (bloque 5, paso 1). Dos trampas del intérprete, las dos silenciosas hasta que
# alguien despliega:
#
#   1. `az` en Windows es un `.cmd`, así que lo que se le pasa lo vuelve a
#      parsear `cmd.exe`. Una expresión JMESPath con paréntesis, `?`, `|` o `!`
#      que PowerShell no entrecomille (no lleva espacios) llega cruda al
#      intérprete de órdenes y revienta: «az : No se esperaba -o en este
#      momento.»
#   2. Redirigir la salida de error de un ejecutable nativo (`2>$null` o
#      `2>&1`) hace que PowerShell 5.1 envuelva cada línea en un ErrorRecord;
#      con `$ErrorActionPreference = "Stop"` eso ABORTA el script. Y como el
#      patrón se usaba justo en las comprobaciones de idempotencia («¿existe ya
#      el recurso?»), fallaba precisamente en el primer despliegue, que es
#      cuando el recurso no existe todavía.
#
# Comprobado en el puesto (PowerShell 5.1.26100): `2>$null` y `2>&1` lanzan;
# `2>&1 | Out-Null` también; no redirigir, no. La técnica elegida es la única
# que sobrevive: **no se redirige nunca**, se mira `$LASTEXITCODE`, y el
# mensaje de `az` se ve, que en un script de diagnóstico es una ventaja.

# Metacaracteres que `cmd.exe` reinterpreta al recibir la línea ya expandida.
METACARACTERES_DE_CMD = "()?|!<>^&"


def _consultas_jmespath(texto: str) -> list[str]:
    """
    Lo que un script pasa en `--query`, siga un literal o una variable.

    Las consultas largas se escriben en una variable por legibilidad, y son
    justo las que más probabilidades tienen de llevar un filtro `[?…]`: mirar
    solo a los literales dejaría fuera el caso peligroso.
    """
    consultas: list[str] = []

    for token in re.findall(r'--query\s+("[^"]*"|\$\w+)', texto):
        if token.startswith('"'):
            consultas.append(token.strip('"'))
        else:
            consultas += re.findall(rf'\{token}\s*=\s*"([^"]*)"', texto)

    return consultas


def test_f003_ninguna_consulta_a_az_lleva_metacaracteres_de_cmd() -> None:
    """
    Ninguna expresión `--query` puede llevar caracteres que `cmd.exe` reparse.

    Lo que se filtra o se agrega se hace **en PowerShell**, sobre el JSON ya
    devuelto. Es más código, pero funciona igual en 5.1 que en 7 y no depende
    de si el argumento llevaba un espacio que obligara a entrecomillarlo.
    """
    for script in _ps1():
        for consulta in _consultas_jmespath(_texto(script)):
            malos = sorted({c for c in consulta if c in METACARACTERES_DE_CMD})
            assert not malos, (
                f"{script.name}: la consulta {consulta!r} lleva {malos}, que cmd.exe "
                f"reinterpreta al invocar az.cmd. Pide -o json y filtra en PowerShell"
            )


def _lineas_de_codigo(script: Path) -> list[tuple[int, str]]:
    """
    Líneas del script que no son comentario, con su número.

    Contempla las dos formas de PowerShell: la de línea (`#`) y la de bloque
    (`<# … #>`), que es donde viven las explicaciones largas de las funciones.
    Sin lo segundo, un test que busca llamadas a `az` acaba señalando la prosa
    que documenta por qué no hay que llamarlo así.
    """
    lineas: list[tuple[int, str]] = []
    en_bloque = False

    for numero, linea in enumerate(_texto(script).splitlines(), start=1):
        if en_bloque:
            if "#>" in linea:
                en_bloque = False
            continue
        if "<#" in linea:
            en_bloque = "#>" not in linea
            continue
        if linea.lstrip().startswith("#"):
            continue
        lineas.append((numero, linea))

    return lineas


def test_f003_solo_el_ayudante_redirige_la_salida_de_error_de_az() -> None:
    """
    Ningún script redirige el stderr de `az`… salvo `Invoke-Az`, que es el
    único sitio donde hacerlo es correcto porque baja antes la preferencia de
    errores.

    Con `$ErrorActionPreference = "Stop"`, redirigir el stderr de un nativo
    convierte cada línea en un ErrorRecord **terminante**: el script muere en la
    comprobación que solo pretendía preguntar si algo existe. Le pasó de verdad
    a `20_create_observability.ps1` en el primer despliegue, y el workspace no
    se creó.
    """
    for script in _ps1():
        for numero, linea in _lineas_de_codigo(script):
            if not re.search(r"2>\s*(?:\$null|&1)", linea):
                continue
            assert script.name == CARGADOR and "@args" in linea, (
                f"{script.name}:{numero} redirige la salida de error de az fuera de "
                f"Invoke-Az. Con ErrorActionPreference=Stop eso aborta el script en "
                f"5.1: llama a través del ayudante"
            )


def test_f003_todas_las_llamadas_a_az_pasan_por_el_ayudante() -> None:
    """
    Ni una invocación de `az` suelta: todas por `Invoke-Az`.

    Un solo punto de entrada es lo que permite arreglar de una vez —y para
    siempre— las rarezas de Windows PowerShell 5.1. El puesto del humano **no
    tiene `pwsh`**: los scripts corren con `powershell -NoProfile -File`, así
    que 5.1 no es un caso raro, es el único.
    """
    # Las cadenas se descartan antes de buscar: un mensaje que le dice al humano
    # «ejecuta az login» no es una invocación, y un test que no distingue las dos
    # cosas se acaba desactivando.
    sin_cadenas = re.compile(r"\"[^\"]*\"|'[^']*'")

    for script in _ps1():
        for numero, linea in _lineas_de_codigo(script):
            assert not re.search(r"(?<![\w-])az\s+\w", sin_cadenas.sub("", linea)), (
                f"{script.name}:{numero} invoca az directamente: usa Invoke-Az, que "
                f"es donde están resueltas las trampas de PowerShell 5.1"
            )

    # Contraste: que nadie «apruebe» este test dejando de llamar a az.
    for script in _ps1():
        if script.name == CARGADOR:
            continue
        assert "Invoke-Az " in _script(script.name), (
            f"{script.name} no llama a Azure por ningún sitio"
        )


def test_f003_el_ayudante_de_az_esta_endurecido_para_powershell_51() -> None:
    """
    `Invoke-Az` tiene que hacer las cuatro cosas que lo justifican.

    Comprobado en el puesto (5.1.26100) con un `az` de mentira: con este patrón
    el script sobrevive tanto en consola como con la salida redirigida a un
    fichero, `$LASTEXITCODE` sigue siendo legible al volver y el mensaje de
    error queda disponible en vez de perderse.
    """
    cargador = _script(CARGADOR)

    assert re.search(r"function\s+Invoke-Az\b", cargador), (
        "no existe el ayudante Invoke-Az en 00_vars.ps1"
    )

    cuerpo = cargador[cargador.index("function Invoke-Az"):]
    cuerpo = cuerpo[: cuerpo.index("\nfunction ")] if "\nfunction " in cuerpo else cuerpo

    assert '$ErrorActionPreference = "Continue"' in cuerpo, (
        "Invoke-Az no baja la preferencia de errores: el stderr de az volvería a "
        "ser terminante"
    )
    assert "finally" in cuerpo, (
        "la preferencia de errores debe restaurarse en un finally, o un fallo la "
        "dejaría bajada para el resto del script"
    )
    assert "--only-show-errors" in cuerpo, "faltan los avisos silenciados de az"
    assert "AzUltimoError" in cuerpo, (
        "el mensaje de error de az debe quedar disponible; si no, un fallo real se "
        "diagnostica a ciegas"
    )


def test_f003_los_prerrequisitos_siguen_midiendo_el_disco_del_servidor() -> None:
    """
    Contraste de los dos anteriores: la forma más fácil de dejar de tener
    consultas problemáticas es dejar de comprobar cosas.

    La medición del disco es la que nació del incidente del 2026-08-09, así que
    se exige que siga ahí: la métrica, el umbral y el cálculo en PowerShell.
    """
    texto = _script("05_check_prereqs.ps1")

    assert "storage_percent" in texto, "ya no se mide la ocupación del disco"
    assert "ConvertFrom-Json" in texto, (
        "el máximo de la métrica debe calcularse en PowerShell sobre el JSON, "
        "no con una función JMESPath que cmd.exe rompe"
    )
    assert re.search(r"-ge\s+60", texto), "se ha perdido el umbral del 60 %"


# ---------------------------------------------------------------------------
# La puerta del disco (incidente del 2026-08-09), detectable por máquina
# ---------------------------------------------------------------------------
#
# El job nocturno ejecuta la MISMA carga completa que llenó el disco del
# servidor compartido y lo dejó en solo lectura diez minutos. La salvaguarda
# estuvo escrita solo en prosa y condicionada a «hasta que el humano decida»:
# una condición que ya se cumple —la decisión fue la opción B, F-019— y que por
# tanto leía como puerta abierta. Aquí se expresa contra algo comprobable: la
# feature bloqueante, y una clave del fichero de entorno que el script mira.

FEATURE_BLOQUEANTE = "F-019"


def _features() -> dict[str, dict]:
    """Las features del arnés indexadas por su identificador."""
    datos = json.loads((REPO_ROOT / "harness" / "features.json").read_text(encoding="utf-8"))
    return {f["id"]: f for f in datos["features"]}


def test_f003_la_puerta_del_job_programado_es_detectable_por_maquina() -> None:
    """
    `jobProgramable` no es documentación: `80_create_job.ps1` la comprueba y
    aborta con `throw` antes de crear nada.

    `-Confirmar` exige un acto deliberado, pero no distingue entre un humano
    que sabe que F-019 sigue abierta y otro que solo quiere terminar la tabla
    del README. Esta puerta sí.
    """
    cfg = _config("dev")

    assert isinstance(cfg["jobProgramable"], bool), (
        "'jobProgramable' debe ser un booleano JSON: como cadena, 'false' sería "
        "cierto en PowerShell y la puerta no frenaría nada"
    )

    texto = _script("80_create_job.ps1")

    assert re.search(r"if\s*\(\s*-not\s+\$CFG\.jobProgramable\s*\)\s*\{[^}]*throw", texto), (
        "80_create_job.ps1 no aborta cuando el entorno declara jobProgramable = false"
    )
    assert FEATURE_BLOQUEANTE in texto, (
        f"el script no nombra la feature que mantiene cerrada la puerta "
        f"({FEATURE_BLOQUEANTE}): sin el identificador nadie puede comprobar el "
        f"estado del bloqueo contra harness/features.json"
    )

    puerta = texto.index("$CFG.jobProgramable")
    creacion = texto.index("containerapp job create")
    assert puerta < creacion, "la puerta se comprueba después de crear el job"


def test_f003_la_puerta_solo_se_abre_cuando_la_feature_bloqueante_esta_cerrada() -> None:
    """
    Poner `jobProgramable: true` con F-019 sin cerrar deja la suite en rojo.

    Es el punto que la review echó en falta: una puerta escrita contra una
    condición **todavía no cumplida y verificable**, no contra «que se decida».
    Decidir ya se decidió (opción B); lo que protege del incidente es haberla
    implementado.
    """
    features = _features()

    assert FEATURE_BLOQUEANTE in features, (
        f"la puerta del job apunta a {FEATURE_BLOQUEANTE} y esa feature ya no "
        f"está en harness/features.json: el bloqueo se quedó sin referencia"
    )

    if _config("dev")["jobProgramable"]:
        assert features[FEATURE_BLOQUEANTE]["status"] == "done", (
            f"el entorno permite programar el job, pero {FEATURE_BLOQUEANTE} está en "
            f"'{features[FEATURE_BLOQUEANTE]['status']}': el job nocturno volvería a "
            f"lanzar la carga que llenó el disco del servidor compartido"
        )


def test_f003_la_puerta_nombra_la_feature_bloqueante_en_la_documentacion() -> None:
    """
    El README y `tasks.md` nombran `F-019`, no describen el problema.

    Un identificador se puede contrastar con `harness/features.json`; una
    condición en prosa («hasta que se decida qué hacer con el disco») envejece
    sola y acaba dando por abierta una puerta que sigue cerrada.
    """
    readme = _texto(INFRA / "README.md")
    tareas = _texto(SPEC_DIR / "tasks.md")

    assert FEATURE_BLOQUEANTE in readme, (
        f"infra/README.md no nombra {FEATURE_BLOQUEANTE} al explicar por qué el job "
        f"no debe quedar programado"
    )
    assert FEATURE_BLOQUEANTE in tareas, (
        f"specs/F-003-infra-caj/tasks.md no avisa de que T23 está bloqueada por "
        f"{FEATURE_BLOQUEANTE}: quien trabaje desde las tareas no ve la puerta"
    )
