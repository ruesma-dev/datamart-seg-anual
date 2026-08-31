# tests/test_f052_marcador.py
"""
F-052 · El marcador `[F052-COBERTURA-KO]`, fijado por sus DOS extremos (R28-R30).

**Por qué esto es un fichero de tests y no un comentario.** `check-cobertura`
avisa y **no bloquea** (DA-4): la nocturna termina en verde, así que la alerta de
fallo existente (`alert-caj-datamart-seg-dev-failed`) no se dispara. La **única**
vía por la que este guardián se hace oír es una línea de log con un literal fijo
que una regla de consulta programada busca. Si el literal del código y el del
`.ps1` divergen, la regla vigila un texto que ya nadie escribe y **nadie se
entera** — que es, exactamente, el modo de fallo que esta feature existe para
eliminar.

Es el mismo patrón con el que `test_f024_r19_umbral_por_defecto_coincide_con_dev_json`
protege el umbral de frescura, y con el que `test_f024_infra_alerta.py` cruza el
evento `step_finished` con la consulta que lo busca: **los dos extremos, en el
mismo fichero**, para que lo que se rompa sea la suite y no la alerta a las 02:00
de un martes.

Los helpers de lectura de `infra/` se **importan** de `test_f003_infra.py`, no se
copian: dos copias de un barrido de secretos divergen, y ya pasó en este
repositorio.

Ninguno toca Azure: se lee el `.ps1` como texto y se **ejecuta** su función de
composición con `powershell`, que es lo único que caza un literal bien formado y
equivocado.
"""

from __future__ import annotations

import functools
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

import main
from etl_sigrid.domain.cobertura import MARCADOR_KO
from tests.test_f003_infra import (
    INFRA,
    PATRONES_PROHIBIDOS,
    _config,
    _lineas_de_codigo,
    _ps1,
    _script,
    _texto,
)

SCRIPT = "96_create_alert_cobertura.ps1"

#: La función del `.ps1` que compone el argumento de `--condition-query`. Va en
#: una función, y no suelta en el cuerpo, para que un test pueda EJECUTARLA y
#: mirar la cadena que se envía de verdad. Es la lección del 2026-08-19: leer el
#: script como texto comprueba la forma, no el valor.
FUNCION_CONSULTA = "Componer-ConsultaCobertura"

#: El nombre del resultado que cuenta `--condition`. Son dos argumentos
#: distintos que se refieren al mismo resultado y hay un test que los cruza: si
#: divergen, la regla cuenta algo que no existe y se queda muda sin que Azure
#: proteste.
NOMBRE_DE_LA_CONSULTA = "Cobertura"

#: Todo lo que el script tiene que leer del fichero de entorno.
CLAVES_QUE_LEE = (
    "coberturaAlertName",
    "coberturaVentanaHoras",
    "logAnalytics",
    "job",
    "resourceGroup",
    "alertActionGroupName",
    "alertActionGroupRg",
)

#: El puesto del humano no tiene `pwsh`; los scripts corren con `powershell`.
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


# --- utilidades -------------------------------------------------------------


def _funcion_ps(nombre: str) -> str:
    """El texto de una función del `.ps1`, para poder EJECUTARLA de verdad.

    Delimitación: desde `function <nombre>` hasta la primera `}` en la columna
    cero, que es como está escrito el fichero (el cuerpo va indentado). Misma
    convención que `tests/test_f024_infra_alerta.py`.
    """
    lineas = _script(SCRIPT).splitlines()

    inicio = next(
        (i for i, linea in enumerate(lineas) if linea.startswith(f"function {nombre}")),
        None,
    )
    assert inicio is not None, f"el script no define la función {nombre}"

    for fin in range(inicio + 1, len(lineas)):
        if lineas[fin] == "}":
            return "\n".join(lineas[inicio : fin + 1])

    raise AssertionError(f"la función {nombre} no se cierra con '}}' en la columna cero")


@functools.lru_cache(maxsize=1)
def _consulta_compuesta() -> str:
    """La consulta KQL tal y como el script la envía, ejecutando su función."""
    assert POWERSHELL is not None

    cfg = _config("dev")
    guion = (
        "$ErrorActionPreference = 'Stop'\n"
        f"\"CONSULTA;$({FUNCION_CONSULTA} -Job '{cfg['job']}')\"\n"
    )

    with tempfile.TemporaryDirectory() as carpeta:
        fichero = Path(carpeta) / "funcion_de_la_alerta.ps1"
        fichero.write_text(_funcion_ps(FUNCION_CONSULTA) + "\n" + guion, encoding="utf-8")

        # La ruta del intérprete la resuelve `shutil.which`, no viene de fuera,
        # y el guión lo escribe este mismo test: no hay entrada de usuario.
        proceso = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(fichero)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

    assert proceso.returncode == 0, (
        f"el guión de prueba no llegó a ejecutarse: {proceso.stderr}"
    )
    for linea in proceso.stdout.splitlines():
        if linea.startswith("CONSULTA;"):
            return linea.split(";", 1)[1]
    raise AssertionError(f"la función no devolvió nada: {proceso.stdout!r}")


# ---------------------------------------------------------------------------
# R28 · el literal, cruzado por los dos extremos
# ---------------------------------------------------------------------------


def test_f052_r28_el_marcador_del_ps1_es_el_MISMO_que_emite_el_codigo():  # noqa: N802
    """**El test de esta feature.** Si estos dos literales divergen, el guardián
    detecta la obra invisible, la escribe en el log y no se entera nadie."""
    assert MARCADOR_KO in _script(SCRIPT), (
        f"la alerta no busca {MARCADOR_KO!r}, que es lo que emite "
        f"etl_sigrid/domain/cobertura.py. Con eso la regla vigila un texto que "
        f"nadie escribe y el guardián se queda mudo"
    )


@pytest.mark.skipif(POWERSHELL is None, reason="no hay powershell en este puesto")
def test_f052_r28_el_marcador_llega_a_la_consulta_que_se_envia_de_verdad():
    """No basta con que el literal esté en el fichero: tiene que llegar a la
    cadena que viaja en `--condition-query`.

    Es el defecto del 2026-08-19 en `95_create_alert_frescura.ps1`: el filtro
    temporal estaba definido, bien escrito y **no llegaba a la consulta**, y la
    suite entera seguía en verde.
    """
    consulta = _consulta_compuesta()

    assert MARCADOR_KO in consulta
    assert consulta.startswith(f"{NOMBRE_DE_LA_CONSULTA}=")
    assert "ContainerAppConsoleLogs_CL" in consulta
    assert _config("dev")["job"] in consulta


@pytest.mark.skipif(POWERSHELL is None, reason="no hay powershell en este puesto")
def test_f052_r28_la_alerta_mira_el_job_por_la_columna_real():
    """`ContainerJobName_s`, verificada con `| getschema` el 2026-08-18.
    `ContainerAppName_s` NO existe para un job: filtrar por ella devolvería
    siempre cero filas y la alerta no dispararía nunca."""
    consulta = _consulta_compuesta()

    assert "ContainerJobName_s" in consulta
    assert "ContainerAppName_s" not in consulta


def test_f052_r28_el_nombre_de_la_consulta_es_el_que_cuenta_la_condicion():
    """`--condition "count 'X' > 0"` y `--condition-query X=<kql>`: si las dos X
    divergen, la regla cuenta un resultado que no existe y se queda muda sin que
    Azure proteste."""
    texto = _script(SCRIPT)

    condicion = re.search(r"--condition\s+\"count\s+'([^']+)'\s*([<>]=?)\s*(\d+)\"", texto)
    assert condicion is not None, "no se encuentra el argumento --condition"

    nombre, operador, umbral = condicion.groups()
    assert nombre == NOMBRE_DE_LA_CONSULTA
    assert (operador, umbral) == (">", "0"), (
        "esta alerta dispara por PRESENCIA del marcador, no por su ausencia: es "
        "al revés que la de frescura, y confundirlas la deja disparando todas "
        "las noches o ninguna"
    )


def test_f052_r28_el_codigo_emite_el_marcador_cuando_hay_hallazgos():
    """El otro extremo del contrato: que el ETL escriba de verdad esa línea."""
    import inspect

    fuente = inspect.getsource(main._emitir_marcador_de_cobertura)

    assert "marcador" in fuente
    assert "MARCADOR_KO" in fuente, (
        "el comando compone el literal a mano en vez de leerlo del dominio"
    )


def test_f052_r28_el_marcador_es_estable_y_buscable():
    """Sin fecha, sin nombres y sin espacios: un literal que cambia cada versión
    no sirve para una regla escrita una vez y desplegada a mano."""
    assert MARCADOR_KO == "[F052-COBERTURA-KO]"
    assert " " not in MARCADOR_KO
    assert not re.search(r"\d{4}-\d{2}-\d{2}", MARCADOR_KO)


# ---------------------------------------------------------------------------
# R29, R30 · el script, y ni una dirección de correo
# ---------------------------------------------------------------------------


def test_f052_r30_el_script_no_lleva_ninguna_direccion_de_correo():
    """Los destinatarios viven en el grupo de acción y se pasan con `-AlertEmail`
    al desplegar `infra/90_create_alert.ps1`. **Nunca** en un `.ps1`, una spec o
    un `.json`."""
    assert not re.search(PATRONES_PROHIBIDOS["dirección de correo"], _script(SCRIPT))


def test_f052_r29_el_script_lee_todo_de_cfg_y_no_cablea_ningun_nombre():
    texto = _script(SCRIPT)

    for clave in CLAVES_QUE_LEE:
        assert f"$CFG.{clave}" in texto, f"el script no lee $CFG.{clave}"

    cfg = _config("dev")
    for clave in ("resourceGroup", "logAnalytics", "job", "coberturaAlertName",
                  "alertActionGroupName", "alertActionGroupRg"):
        assert str(cfg[clave]) not in texto, (
            f"el script escribe el valor de '{clave}' en vez de leerlo de $CFG"
        )


def test_f052_r29_el_script_notifica_al_grupo_de_accion_que_ya_existe():
    """No se crea canal nuevo: se reutiliza `ag-datamart-seg-dev`, que crea o
    localiza `90_create_alert.ps1`, que es donde se pasan los destinatarios."""
    texto = _script(SCRIPT)

    assert "action-group show" in texto
    assert "--action-groups" in texto


def test_f052_r29_la_alerta_es_idempotente():
    """Si la regla ya existe, no se recrea. Igual que los otros trece scripts."""
    texto = _script(SCRIPT)

    assert re.search(r"scheduled-query\s+show", texto)
    assert re.search(r"scheduled-query\s+create", texto)


def test_f052_r29_la_ventana_sale_del_entorno_y_no_es_iso_8601():
    """`az` acepta `##h##m##s` y rechaza un `PT24H`, y el valor sale de
    `coberturaVentanaHoras`: no se escribe a mano."""
    texto = _script(SCRIPT)

    assert "$CFG.coberturaVentanaHoras" in texto
    assert not re.search(r"--window-size\s+PT", texto)
    assert re.search(r"--window-size\s+\$", texto), (
        "la ventana va cableada en vez de derivarse del entorno"
    )


def test_f052_r29_dev_json_declara_el_nombre_y_la_ventana():
    cfg = _config("dev")

    assert cfg["coberturaAlertName"]
    assert cfg["coberturaVentanaHoras"] == 24, (
        "el guardián corre una vez por noche: la ventana tiene que cubrir una"
    )
    assert not re.search(
        PATRONES_PROHIBIDOS["dirección de correo"], cfg["coberturaAlertName"]
    )


def test_f052_r29_el_script_esta_en_la_lista_de_los_ps1():
    """Contraste: si el fichero no existiera, los tests de arriba fallarían con
    `FileNotFoundError` en vez de decir qué falta."""
    assert SCRIPT in [p.name for p in _ps1()]


def test_f052_r29_utf8_bom_crlf_y_cabecera_de_ruta():
    """UTF-8 con BOM, CRLF y primera línea con su ruta (`docs/CONVENTIONS.md`).

    Lo comprueba también el test genérico de F-003 sobre todos los `.ps1`; se
    repite aquí para que el fallo señale a este script y a esta feature.
    """
    ruta = INFRA / SCRIPT
    crudo = ruta.read_bytes()

    assert crudo.startswith(b"\xef\xbb\xbf"), "no está en UTF-8 con BOM"
    assert b"\r\n" in crudo, "no usa CRLF"
    assert not re.search(rb"(?<!\r)\n", crudo), "mezcla LF y CRLF"
    assert _texto(ruta).splitlines()[0] == f"# infra/{SCRIPT}"


def test_f052_r29_ninguna_llamada_a_az_va_suelta():
    """Todas por `Invoke-Az`, que es donde están resueltas las trampas de
    Windows PowerShell 5.1."""
    sin_cadenas = re.compile(r"\"[^\"]*\"|'[^']*'")

    for numero, linea in _lineas_de_codigo(INFRA / SCRIPT):
        assert not re.search(r"(?<![\w-])az\s+\w", sin_cadenas.sub("", linea)), (
            f"{SCRIPT}:{numero} invoca az directamente"
        )
    assert "Invoke-Az " in _script(SCRIPT)


def test_f052_r29_el_readme_documenta_el_script_despues_del_95():
    """El README lista los scripts en orden de ejecución."""
    readme = _texto(INFRA / "README.md")

    assert SCRIPT in readme, f"{SCRIPT} no está documentado en infra/README.md"
    assert readme.index("95_create_alert_frescura.ps1") < readme.index(SCRIPT)


def test_f052_r29_el_script_dice_que_sin_desplegarlo_el_guardian_es_mudo():
    """El riesgo declarado del diseño, escrito donde lo va a leer quien
    despliega: el despliegue es MANUAL y sin él nadie recibe nada."""
    texto = _script(SCRIPT).lower()

    assert "mudo" in texto or "nadie" in texto, (
        "el script no advierte de que sin desplegarlo el guardián no avisa"
    )
