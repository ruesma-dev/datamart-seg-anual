# tests/test_f024_infra_alerta.py
"""
F-024 · Tests de la alerta de frescura (R21, R22).

Fijan los DOS extremos del mismo contrato, y a propósito en el mismo fichero:
el orquestador emite el evento `step_finished` con `step` y `status`, y el
script de la alerta busca exactamente esos tres términos en los logs. Si
alguien renombra el evento, lo que tiene que romperse es la suite, no la
alerta en silencio a las 02:00 de un martes.

(Desviación menor respecto a `design.md`, que ponía el test del orquestador en
`test_f024_meta_y_formato.py`: separarlos deja cada mitad del contrato sin
constancia de la otra, que es justo lo que el requisito quiere impedir.)

Los helpers de lectura de `infra/` se IMPORTAN de `test_f003_infra.py`, no se
copian: dos copias de un barrido de secretos divergen, y ya pasó en este
repositorio.

Ninguno toca Azure: se lee el `.ps1` como texto.
"""

from __future__ import annotations

import functools
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.test_f003_infra import (
    INFRA,
    PATRONES_PROHIBIDOS,
    REPO_ROOT,
    _config,
    _lineas_de_codigo,
    _ps1,
    _script,
    _texto,
)

SCRIPT = "95_create_alert_frescura.ps1"

#: Los tres términos que la consulta de la alerta busca en la línea de log.
#: Son los que emite el orquestador al terminar `build_mart` correctamente.
TERMINOS_DEL_EVENTO = ("step_finished", "build_mart", "SUCCESS")

#: Granularidades de ventana que ADMITE `az monitor scheduled-query`, en
#: minutos. No es una elección nuestra ni una lista defensiva: es la que
#: devolvió el ARM el 2026-08-19 al rechazar la primera creación de la regla,
#: copiada literal del error:
#:
#:     (InvalidRequestContent) The request content was invalid and could not be
#:     deserialized: 'WindowSize of 1800 minutes is not supported. Supported
#:     granularities are: 5, 10, 15, 30, 45, 60, 120, 180, 240, 300, 360, 720,
#:     1440, 2880'
#:
#: 1800 minutos eran las 30 h de DA-4. Entre 1440 (24 h) y 2880 (48 h) no hay
#: nada, así que el umbral acordado NO cabe como ventana. Esta constante vive
#: aquí, en el test, a propósito: es la verdad del servicio contra la que se
#: mide el script, no algo que el script pueda redefinir para ponerse en verde.
GRANULARIDADES_ADMITIDAS_MINUTOS = (
    5, 10, 15, 30, 45, 60, 120, 180, 240, 300, 360, 720, 1440, 2880,
)

#: La función del `.ps1` que traduce el umbral a una ventana admisible.
FUNCION_VENTANA = "Resolver-VentanaAdmitida"

#: El puesto del humano no tiene `pwsh`; los scripts corren con `powershell`.
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")

#: Todo lo que el script tiene que leer del fichero de entorno (R22.1).
CLAVES_QUE_LEE = (
    "frescuraAlertName",
    "frescuraUmbralHoras",
    "logAnalytics",
    "job",
    "resourceGroup",
    "alertActionGroupName",
    "alertActionGroupRg",
)


# --- utilidades -------------------------------------------------------------


def _minutos_de_ventana(ventana: str) -> int | None:
    """Traduce una ventana `##h##m##s` a minutos; `None` si no lo es.

    `az` acepta ese formato y NO ISO 8601 (`PT30H` se rechaza), así que los
    valores escritos en la documentación viajan así y hay que interpretarlos
    para poder compararlos con las granularidades del servicio.
    """
    casa = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", ventana)
    if casa is None or not any(casa.groups()):
        return None
    horas, minutos, segundos = (int(g or 0) for g in casa.groups())
    return horas * 60 + minutos + segundos // 60


def _funcion_ps(nombre: str) -> str:
    """El texto de una función del `.ps1`, para poder EJECUTARLA de verdad.

    Leer el script como cadena comprueba que dice lo que tiene que decir, pero
    no lo que hace: el defecto del 2026-08-19 fue justo eso —una ventana bien
    formada (`30h`) y a la vez inválida para el servicio—. Extraer la función
    y ejecutarla es lo único que caza el valor equivocado.

    Delimitación: desde `function <nombre>` hasta la primera `}` en la columna
    cero, que es como está escrito el fichero (el cuerpo va indentado).
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


#: Umbrales con los que se ejercita la función: los dos lados de cada frontera
#: de la lista de granularidades, el que está configurado (30), el mayor que
#: cabe (48) y los que no tienen ventana posible o no tienen sentido.
UMBRALES_A_PROBAR = (-1, 0, 1, 2, 6, 11, 12, 24, 25, 30, 47, 48, 49, 72)

_PLANTILLA_PRUEBA = """
$ErrorActionPreference = 'Stop'
foreach ($u in @(UMBRALES)) {
    try {
        "$u;OK;$(FUNCION -UmbralHoras $u)"
    } catch {
        $mensaje = $_.Exception.Message -replace "\\s+", " "
        "$u;ERROR;$mensaje"
    }
}
"""


@functools.lru_cache(maxsize=1)
def _resolver_ventanas() -> dict[int, tuple[bool, str]]:
    """Ejecuta la función del `.ps1` con todos los umbrales, de una sola vez.

    Arrancar `powershell` cuesta cerca de un segundo, y la campaña de mutación
    lanza la suite entera una vez por mutante: catorce invocaciones sueltas
    saldrían mucho más caras que el valor que aportan. Una sola pasada, con el
    resultado en caché, y cada test lee de ella.

    Devuelve `{umbral: (fue_bien, ventana_o_mensaje_de_error)}`.
    """
    assert POWERSHELL is not None

    guion = _PLANTILLA_PRUEBA.replace(
        "UMBRALES", ", ".join(str(u) for u in UMBRALES_A_PROBAR)
    ).replace("FUNCION", FUNCION_VENTANA)

    with tempfile.TemporaryDirectory() as carpeta:
        fichero = Path(carpeta) / "resolver_ventana.ps1"
        fichero.write_text(_funcion_ps(FUNCION_VENTANA) + guion, encoding="utf-8")

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

    resultados: dict[int, tuple[bool, str]] = {}
    for linea in proceso.stdout.splitlines():
        if ";" not in linea:
            continue
        umbral, estado, valor = linea.strip().split(";", 2)
        resultados[int(umbral)] = (estado == "OK", valor)

    assert set(resultados) == set(UMBRALES_A_PROBAR), (
        f"faltan umbrales en la salida: {sorted(set(UMBRALES_A_PROBAR) - set(resultados))}"
    )
    return resultados


# ---------------------------------------------------------------------------
# R21 · El evento que vigila la alerta es estable, por los dos lados
# ---------------------------------------------------------------------------


def test_f024_r21_orquestador_emite_step_finished_con_step_y_status() -> None:
    """El extremo del ETL: el evento existe y lleva `step` y `status`.

    La alerta de frescura no mide la BBDD: mide que en el log del job haya
    aparecido una línea diciendo que `build_mart` terminó en `SUCCESS`. Si el
    evento cambiara de nombre o dejara de llevar el estado, la alerta seguiría
    sin disparar y nadie se enteraría hasta echar de menos un correo.
    """
    from etl_sigrid.application.orchestrator import Orchestrator
    from etl_sigrid.domain.entities import StepResult, StepStatus

    eventos: list[tuple[str, dict]] = []

    class _LoggerFalso:
        def info(self, evento: str, **kwargs: object) -> None:
            eventos.append((evento, dict(kwargs)))

        def warning(self, evento: str, **kwargs: object) -> None:
            eventos.append((evento, dict(kwargs)))

        def exception(self, evento: str, **kwargs: object) -> None:
            eventos.append((evento, dict(kwargs)))

    class _PasoFalso:
        name = "build_mart"
        stage = "build_mart"

        @property
        def depends_on(self) -> list[str]:
            return []

        def run(self) -> StepResult:
            from datetime import datetime

            return StepResult(
                step_name="build_mart",
                status=StepStatus.SUCCESS,
                started_at=datetime(2026, 8, 19, 5, 0, 0),
                finished_at=datetime(2026, 8, 19, 5, 25, 0),
                rows_processed=1_000,
            )

    import etl_sigrid.application.orchestrator as modulo

    original = modulo.logger
    modulo.logger = _LoggerFalso()  # type: ignore[assignment]
    try:
        Orchestrator([_PasoFalso()]).run_all()  # type: ignore[list-item]
    finally:
        modulo.logger = original

    terminados = [kw for nombre, kw in eventos if nombre == "step_finished"]
    assert terminados, "el orquestador ya no emite 'step_finished'"
    assert terminados[0]["step"] == "build_mart"
    assert terminados[0]["status"] == "SUCCESS"


def test_f024_r21_la_alerta_filtra_por_los_tres_terminos() -> None:
    """El otro extremo: el script busca esos tres términos y ninguna otra cosa."""
    texto = _script(SCRIPT)

    for termino in TERMINOS_DEL_EVENTO:
        assert termino in texto, (
            f"la consulta de la alerta no busca '{termino}': dejaría de vigilar "
            f"lo que R21 dice que vigila"
        )

    # Y los busca JUNTOS, en la misma línea de log, no cada uno por su lado.
    assert re.search(r"has_all\s*\(", texto), (
        "los tres términos tienen que exigirse en la MISMA línea (has_all): por "
        "separado, un 'SUCCESS' de cualquier otro paso apagaría la alerta"
    )


def test_f024_r21_la_alerta_mira_el_job_por_la_columna_real() -> None:
    """`ContainerJobName_s`, confirmada con `getschema` en T3.

    `ContainerAppName_s` —la que decía el README— NO existe en
    `ContainerAppConsoleLogs_CL` para un job: filtrar por ella devolvería
    siempre cero filas y la alerta dispararía todas las noches.
    """
    # Solo el CÓDIGO: la cabecera del script menciona `ContainerAppName_s` a
    # propósito, para explicar por qué NO se usa. Prohibir la palabra también
    # en los comentarios obligaría a borrar justo la explicación que evita que
    # alguien la reintroduzca.
    codigo = "\n".join(linea for _n, linea in _lineas_de_codigo(INFRA / SCRIPT))

    assert "ContainerJobName_s" in codigo
    assert "ContainerAppName_s" not in codigo
    assert "ContainerAppConsoleLogs_CL" in codigo


# ---------------------------------------------------------------------------
# R22 · El script de la alerta
# ---------------------------------------------------------------------------


def test_f024_r22_script_alerta_frescura_lee_de_cfg_y_sin_nombres() -> None:
    """Todo de `$CFG`. Ni un nombre de recurso, ni un correo, escrito aquí."""
    texto = _script(SCRIPT)

    for clave in CLAVES_QUE_LEE:
        assert f"$CFG.{clave}" in texto, f"el script no lee $CFG.{clave}"

    # Ningún valor concreto del entorno aparece escrito.
    cfg = _config("dev")
    for clave in ("resourceGroup", "logAnalytics", "job", "frescuraAlertName",
                  "alertActionGroupName", "alertActionGroupRg"):
        assert str(cfg[clave]) not in texto, (
            f"el script escribe el valor de '{clave}' en vez de leerlo de $CFG"
        )

    assert not re.search(PATRONES_PROHIBIDOS["dirección de correo"], texto), (
        "los destinatarios se resuelven contra el action group, nunca se escriben"
    )


def test_f024_r22_la_alerta_es_idempotente() -> None:
    """Si la regla ya existe, no se recrea. Igual que los otros doce scripts."""
    texto = _script(SCRIPT)

    assert re.search(r"scheduled-query\s+show", texto), (
        "no se comprueba si la regla ya existe antes de crearla"
    )
    assert re.search(r"scheduled-query\s+create", texto)


def test_f024_r22_la_ventana_sale_del_umbral_y_no_es_iso_8601() -> None:
    """La ventana se deriva de `frescuraUmbralHoras` y no se escribe a mano.

    Dos cosas distintas que el script tiene que cumplir a la vez:
    el formato es `##h##m##s` (`az` rechaza un `PT30H`), y el valor sale de
    `Resolver-VentanaAdmitida`, no de pegarle una «h» al umbral. Lo segundo es
    el defecto del 2026-08-19: `$ventana = "{0}h" -f $horas` daba `30h`, bien
    formado y rechazado por el ARM.
    """
    texto = _script(SCRIPT)
    codigo = "\n".join(linea for _n, linea in _lineas_de_codigo(INFRA / SCRIPT))

    assert "$CFG.frescuraUmbralHoras" in texto
    assert "--window-size" in texto

    ventana = re.search(r"--window-size\s+(\S+)", texto)
    assert ventana is not None
    assert not ventana.group(1).startswith("PT"), (
        "la ventana está en ISO 8601 y az la rechaza; el formato es ##h##m##s"
    )

    # El umbral, que es un criterio en horas, NO vale como ventana tal cual.
    assert not re.search(r"\$ventana\s*=\s*\"\{0\}h\"\s*-f\s*\$horas", codigo), (
        "la ventana se compone pegando una 'h' al umbral: eso produjo 30h "
        "(1800 min), que Azure no admite, y la alerta no se pudo crear nunca"
    )
    assert re.search(rf"\$ventana\s*=\s*{FUNCION_VENTANA}\b", codigo), (
        f"la ventana no sale de {FUNCION_VENTANA}, que es lo que garantiza que "
        f"sea una granularidad admitida derivada del umbral"
    )

    assert re.search(r"--evaluation-frequency\s+1h", texto), (
        "la regla debe evaluarse cada hora"
    )


def test_f024_r22_el_script_declara_las_granularidades_que_admite_azure() -> None:
    """La lista del error del ARM está en el script, entera y sin retocar.

    Si alguien la «simplifica» —quita la de 2880, añade una inventada— la
    ventana derivada dejará de ser admisible y el `create` volverá a fallar
    con `InvalidRequestContent`. Aquí manda la constante del test, que es la
    que devolvió el servicio.
    """
    funcion = _funcion_ps(FUNCION_VENTANA)

    numeros = tuple(int(n) for n in re.findall(r"\d+", funcion))
    faltan = [g for g in GRANULARIDADES_ADMITIDAS_MINUTOS if g not in numeros]
    assert not faltan, (
        f"{FUNCION_VENTANA} no contempla las granularidades {faltan} que el ARM "
        f"declara admitidas"
    )

    # Y las contempla como una lista de la que elegir, no a base de ifs sueltos.
    assert re.search(r"@\(\s*5\s*,", funcion), (
        "las granularidades no están en una lista literal: escribirlas sueltas "
        "hace imposible ver de un vistazo si falta alguna"
    )


def test_f024_r22_la_kql_acota_el_criterio_con_el_umbral() -> None:
    """El criterio de DA-4 (30 h) viaja DENTRO de la consulta, no en la ventana.

    La ventana es más ancha que el criterio porque Azure solo admite unas
    granularidades fijas (48 h es la primera que contiene 30 h). Sin el filtro
    temporal en la KQL, la regla juzgaría con 48 h y `check-frescura` con 30:
    dos verdades distintas sobre el mismo datamart.
    """
    codigo = "\n".join(linea for _n, linea in _lineas_de_codigo(INFRA / SCRIPT))

    filtro = re.search(r"TimeGenerated\s*>\s*ago\([^)]*\)", codigo)
    assert filtro is not None, (
        "la KQL no acota por TimeGenerated: la regla contaría los eventos de "
        "toda la ventana (48 h) en vez de los del umbral (30 h)"
    )

    assert not re.search(r"ago\(\s*\d+\s*h\s*\)", codigo), (
        "el filtro temporal lleva el número de horas escrito a mano: tiene que "
        "salir del MISMO umbral que la ventana"
    )

    linea_del_filtro = next(
        linea for _n, linea in _lineas_de_codigo(INFRA / SCRIPT)
        if "TimeGenerated" in linea
    )
    assert "$horas" in linea_del_filtro, (
        f"el filtro temporal no se deriva del umbral: {linea_del_filtro.strip()}"
    )


@pytest.mark.skipif(POWERSHELL is None, reason="no hay powershell en este puesto")
def test_f024_r23_la_ventana_del_umbral_configurado_es_una_granularidad_admitida() -> None:
    """El caso real: con `frescuraUmbralHoras` de `dev.json`, ¿qué envía?

    Este es el test que faltaba el 2026-08-18. Ejecuta la función del script
    con el umbral que está configurado de verdad y comprueba que el valor que
    acabaría en `--window-size` es una granularidad que el ARM acepta. Con el
    script anterior habría salido `30h` = 1800 min, que no está en la lista.
    """
    umbral = _config("dev")["frescuraUmbralHoras"]
    assert umbral in UMBRALES_A_PROBAR, (
        "el umbral configurado ya no está entre los que se ejercitan: el test "
        "estaría comprobando otro caso que el real"
    )

    fue_bien, ventana = _resolver_ventanas()[umbral]
    assert fue_bien, ventana

    minutos = _minutos_de_ventana(ventana)
    assert minutos is not None, f"la ventana '{ventana}' no está en formato ##h##m##s"
    assert minutos in GRANULARIDADES_ADMITIDAS_MINUTOS, (
        f"con un umbral de {umbral} h el script enviaría --window-size {ventana} "
        f"({minutos} min), que Azure rechaza con InvalidRequestContent"
    )
    assert minutos >= umbral * 60, (
        f"la ventana ({minutos} min) no contiene el umbral ({umbral * 60} min): "
        f"la regla juzgaría con menos historia de la que dice DA-4"
    )
    # Con el umbral acordado en DA-4, esto son 48 h y no otra cosa.
    assert ventana == "48h", ventana


@pytest.mark.skipif(POWERSHELL is None, reason="no hay powershell en este puesto")
@pytest.mark.parametrize("umbral", [u for u in UMBRALES_A_PROBAR if 1 <= u <= 48])
def test_f024_r23_la_ventana_es_la_menor_granularidad_que_contiene_el_umbral(
    umbral: int,
) -> None:
    """Regla completa, no solo el caso de 30 h.

    «La menor granularidad admitida que contenga el umbral»: ni una que se
    quede corta (la regla vigilaría menos de lo acordado) ni la mayor de la
    lista por comodidad (mirar 48 h de logs cuando bastan 12 es más caro y
    hace la alerta más lenta en reaccionar).
    """
    esperado = min(g for g in GRANULARIDADES_ADMITIDAS_MINUTOS if g >= umbral * 60)

    fue_bien, ventana = _resolver_ventanas()[umbral]
    assert fue_bien, ventana

    minutos = _minutos_de_ventana(ventana)
    assert minutos == esperado, (
        f"umbral {umbral} h -> ventana {ventana} ({minutos} min); "
        f"la menor admitida que lo contiene es {esperado} min"
    )


@pytest.mark.skipif(POWERSHELL is None, reason="no hay powershell en este puesto")
@pytest.mark.parametrize("umbral", [u for u in UMBRALES_A_PROBAR if u < 1 or u > 48])
def test_f024_r23_un_umbral_imposible_falla_antes_de_llamar_a_azure(umbral: int) -> None:
    """Por encima de 2880 min no hay ventana: se para aquí, no en el ARM.

    Enviar una petición que sabemos que se va a rechazar cuesta un viaje a
    Azure y devuelve un `InvalidRequestContent` que no dice qué hacer. El
    mensaje del script sí: nombra la clave del fichero de entorno y el tope.
    """
    fue_bien, mensaje = _resolver_ventanas()[umbral]

    assert not fue_bien, (
        f"con un umbral de {umbral} h el script no falla: enviaría a Azure una "
        f"ventana inválida ({mensaje})"
    )
    assert "frescuraumbralhoras" in mensaje.lower(), (
        f"el mensaje no dice qué clave hay que cambiar: {mensaje}"
    )
    assert "48" in mensaje, f"el mensaje no dice cuál es el tope: {mensaje}"


def test_f024_r23_la_documentacion_no_manda_restaurar_una_ventana_invalida() -> None:
    """Las ventanas escritas en la prosa también tienen que ser admisibles.

    La prueba de extremo a extremo de R23 acorta la ventana y luego la
    restaura. Si el comando de restaurar lleva un valor que Azure no admite,
    la regla se queda con la ventana corta de la prueba y dispara cada hora
    hasta que alguien se harte de los correos.
    """
    documentos = (
        INFRA / "README.md",
        REPO_ROOT / "specs" / "F-024-coherencia-cargas-truncadas" / "requirements.md",
        REPO_ROOT / "specs" / "F-024-coherencia-cargas-truncadas" / "design.md",
    )

    # Solo los bloques de código, que es lo que alguien copia y pega. La prosa
    # puede -y debe- citar el `30h` que resultó inválido: contar la historia es
    # justo lo que evita que alguien lo reintroduzca, igual que con
    # `ContainerAppName_s` en la cabecera del script.
    encontradas = 0
    for documento in documentos:
        for bloque in re.findall(r"^```.*?^```", _texto(documento), re.S | re.M):
            for ventana in re.findall(r"--window-size\s+([0-9]\S*)", bloque):
                encontradas += 1
                minutos = _minutos_de_ventana(ventana)
                assert minutos in GRANULARIDADES_ADMITIDAS_MINUTOS, (
                    f"{documento.name} manda ejecutar --window-size {ventana} "
                    f"({minutos} min), que Azure rechaza"
                )

    assert encontradas >= 2, (
        "no se ha encontrado ni la ventana de la prueba ni la de restaurar: el "
        "test no está mirando donde cree"
    )


def test_f024_r22_la_alerta_dispara_por_ausencia_y_se_desactiva_sola() -> None:
    """`count < 1`: lo que se vigila es la AUSENCIA del evento.

    Una regla que buscara «el último evento» no dispararía nunca cuando no hay
    eventos, que es justo el caso a detectar.
    """
    texto = _script(SCRIPT)

    condicion = re.search(r'--condition\s+"([^"]+)"', texto)
    assert condicion is not None, "no hay --condition"
    assert re.search(r"count\s+\S+\s*<\s*1", condicion.group(1)), condicion.group(1)

    assert re.search(r"--severity\s+2", texto), "severidad 2 (R22.4)"
    assert re.search(r"--auto-mitigate\s+true", texto), (
        "sin auto-mitigación no llega el 'Deactivated' cuando vuelve a haber carga"
    )


def test_f024_r22_script_alerta_frescura_bom_crlf_cabecera() -> None:
    """UTF-8 con BOM, CRLF y primera línea con su ruta (docs/CONVENTIONS.md).

    Lo comprueba también el test genérico de F-003 sobre todos los `.ps1`; se
    repite aquí para que el fallo señale a este script y a esta feature.
    """
    ruta = INFRA / SCRIPT
    crudo = ruta.read_bytes()

    assert crudo.startswith(b"\xef\xbb\xbf"), "no está en UTF-8 con BOM"
    assert b"\r\n" in crudo, "no usa CRLF"
    assert not re.search(rb"(?<!\r)\n", crudo), "mezcla LF y CRLF"
    assert _texto(ruta).splitlines()[0] == f"# infra/{SCRIPT}"


def test_f024_r22_ninguna_variable_se_llama_como_las_de_00_vars() -> None:
    """`00_vars.ps1` define `$TAG`, `$IMG`, `$SUB`, `$CFG` y `$PG_SERVER`.

    Se carga con dot-sourcing DESPUÉS de los parámetros, así que una variable
    propia con uno de esos nombres se machaca sin avisar. Le pasó de verdad a
    `80_create_job.ps1` con `-Tag`, y costó una imagen desplegada con el tag
    equivocado.
    """
    texto = _script(SCRIPT)
    reservadas = ("TAG", "IMG", "SUB", "CFG", "PG_SERVER", "BUILD_DATE")

    for nombre in reservadas:
        asignacion = re.search(rf"(?m)^\s*\${nombre}\s*=", texto)
        assert asignacion is None, (
            f"el script asigna ${nombre}, que ya define 00_vars.ps1 y se "
            f"machacaría al cargarlo"
        )
        parametro = re.search(rf"(?im)^\s*\[\w+.*\]\s*\${nombre}\b", texto)
        assert parametro is None, f"hay un parámetro llamado ${nombre}"


def test_f024_r22_readme_documenta_el_script_en_orden() -> None:
    """El README lista los scripts en orden de ejecución: el 95 va tras el 90."""
    readme = _texto(INFRA / "README.md")

    assert SCRIPT in readme, f"{SCRIPT} no está documentado en infra/README.md"
    assert readme.index("90_create_alert.ps1") < readme.index(SCRIPT)

    # Y explica el paso previo que no es un script.
    assert "scheduled-query" in readme, (
        "el README no dice que hay que instalar la extensión de az una vez"
    )


def test_f024_r22_dev_json_declara_umbral_y_nombre() -> None:
    cfg = _config("dev")

    assert cfg["frescuraUmbralHoras"] == 30, "DA-4: el umbral acordado son 30 h"
    assert cfg["frescuraAlertName"], "falta el nombre de la regla de frescura"
    # Nombre de recurso, no un correo ni un identificador.
    assert not re.search(PATRONES_PROHIBIDOS["dirección de correo"], cfg["frescuraAlertName"])


def test_f024_r22_el_script_esta_en_la_lista_de_los_ps1() -> None:
    """Contraste: si el fichero no existiera, los tests de arriba que leen su
    texto fallarían con FileNotFoundError en vez de decir qué falta."""
    assert SCRIPT in [p.name for p in _ps1()]
