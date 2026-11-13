# harness/e2e.py
"""Capa e2e del arnés (F-059): tests de navegador versionados que ejecuta un runner.

La puerta no es un agente haciendo clic: son tests Playwright guardados en el
repositorio y ejecutados por su runner (`pytest-playwright` o `playwright-test`)
contra la aplicación levantada en local. Este módulo los lanza, clasifica cada
servicio (VERDE, ROJO, TIMEOUT o NO ARRANCA), deja junit, trazas y salida en
`.arnes_cache/e2e/F-XXX/<servicio>/` y escribe el resumen en
`progress/e2e_F-XXX.md`.

Regla de oro, la de `harness/servicios.py`: sin ningún servicio que declare el
bloque `e2e`, la capa es N/A con su motivo y no se lanza ni un proceso.

Modos de la orden:

- `--feature F-XXX` (o la de la rama): ejecuta la capa.
- `--estado`: una sola línea `CAPA E2E: …` para `init.sh`, sin ejecutar nada.
- `--plantilla --servicio NOMBRE`: copia las plantillas del runner al servicio.

Playwright lo instala el proyecto, nunca el arnés.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from harness.alcance import EjecutorGit, ejecutar_git, rama_base_configurada
from harness.rigor import (
    cargar_features,
    cargar_rigor,
    exige,
    feature_de_rama,
    informativa,
    nivel_de_feature,
)
from harness.rutas_sensibles import _casa, ficheros_tocados
from harness.servicios import (
    RUTA_SERVICIOS,
    Servicio,
    cargar_servicios,
    host_de_url,
    host_prohibido,
    interprete,
)

ETIQUETA = "CAPA E2E"

VERDE = "VERDE"
ROJO = "ROJO"
TIMEOUT = "TIMEOUT"
NO_ARRANCA = "NO ARRANCA"

#: Códigos de salida de la ejecución (R9). El de configuración inválida manda.
CODIGO_ROJO = 1
CODIGO_TIMEOUT = 2
CODIGO_NO_ARRANCA = 3
CODIGO_CONFIGURACION = 4

#: Dónde quedan junit, trazas y salida: nunca en `progress/` (R12).
RUTA_CACHE = Path(".arnes_cache/e2e")

#: Cada cuánto se sondea `url_base` mientras arranca la aplicación.
SONDEO_S = 0.5

#: Líneas de la salida que van al resumen cuando un servicio no sale VERDE.
LINEAS_COLA = 20


@dataclass(frozen=True)
class ResultadoServicio:
    """Lo que se midió de un servicio. Lo que no se midió es `None`."""

    servicio: str
    runner: str
    comando: str
    url_base: str
    resultado: str
    pasados: int | None
    fallados: int | None
    omitidos: int | None
    duracion_s: float
    trazas: str
    cola_salida: tuple[str, ...]


# --- Procesos ---------------------------------------------------------------


def _opciones_arbol() -> dict:
    """Opciones de `Popen` que dan al proceso un árbol propio que matar entero."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def parar_arbol(proceso: subprocess.Popen) -> None:
    """Para el proceso y TODOS sus descendientes; no hace nada si ya terminó.

    Windows: `taskkill /T /F`, que recorre el árbol por PID padre. POSIX: el
    grupo de procesos que abrió `start_new_session`.
    """
    if proceso.poll() is not None:
        return
    if os.name == "nt":
        # check=False a propósito: si el proceso muere entre `poll` y `taskkill`,
        # este sale con 128; lanzar aquí, dentro de un `finally`, taparía el
        # resultado de la capa. Lo que importa lo dice el `wait` de después.
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proceso.pid)],
            capture_output=True, check=False,
        )
    else:
        try:
            os.killpg(proceso.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - el sistema no lo soltó
        proceso.kill()
        proceso.wait(timeout=10)


def url_responde(url: str, timeout_s: float = 2.0) -> bool:
    """¿`url` contesta algo por HTTP? Un 4xx o un 5xx también es responder.

    Sin proxies: la aplicación vive en local y un proxy del entorno contestaría
    por ella.
    """
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with abridor.open(url, timeout=timeout_s):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


# --- Comando de cada runner (R8) ----------------------------------------------


def _npx() -> str:
    """`npx` resuelto: en Windows es `npx.cmd` y `Popen` sin shell no lo busca."""
    return shutil.which("npx") or "npx"


def comando_efectivo(
    servicio: Servicio, url_base: str, dir_trazas: Path, raiz: str = "."
) -> tuple[list[str] | str, dict]:
    """El comando de la capa y su entorno.

    El declarado en `comando` es un texto que va por shell; el del runner es una
    lista, sin shell. El entorno lleva siempre `ARNES_E2E=1`,
    `ARNES_E2E_URL_BASE` y `ARNES_E2E_SALIDA` (R6).
    """
    bloque = servicio.e2e
    salida = Path(dir_trazas).resolve()
    entorno = {
        **os.environ,
        "ARNES_E2E": "1",
        "ARNES_E2E_URL_BASE": url_base,
        "ARNES_E2E_SALIDA": str(salida),
    }
    if bloque.comando:
        return bloque.comando, entorno
    if bloque.runner == "playwright-test":
        entorno["PLAYWRIGHT_JUNIT_OUTPUT_NAME"] = str(salida / "junit.xml")
        return [_npx(), "playwright", "test", "--reporter=junit"], entorno
    return [
        interprete(servicio, raiz), "-m", "pytest", bloque.ruta_tests,
        f"--base-url={url_base}", "--tracing=retain-on-failure",
        f"--output={salida / 'trazas'}", f"--junitxml={salida / 'junit.xml'}",
        "-p", "no:cacheprovider",
    ], entorno


def _texto_comando(comando: list[str] | str) -> str:
    return comando if isinstance(comando, str) else subprocess.list2cmdline(comando)


def _cola(fichero: Path) -> tuple[str, ...]:
    try:
        lineas = fichero.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ()
    return tuple(lineas[-LINEAS_COLA:])


# --- Ejecución de un servicio (R6–R9) -------------------------------------------


def _esperar_arranque(
    arranque: subprocess.Popen, url: str, espera_s: int,
    sonda: Callable[[str], bool], reloj: Callable[[], float],
    dormir: Callable[[float], None],
) -> str | None:
    """`None` si `url` responde a tiempo; si no, por qué no arrancó."""
    limite = reloj() + espera_s
    while True:
        codigo = arranque.poll()
        if codigo is not None:
            return f"el arranque terminó con código {codigo} antes de que {url} respondiera"
        if sonda(url):
            return None
        if reloj() >= limite:
            return f"{url} no respondió en {espera_s} s"
        dormir(SONDEO_S)


def ejecutar_servicio(
    servicio: Servicio,
    feature: str,
    url_base: str | None = None,
    raiz: str = ".",
    lanzar: Callable[..., subprocess.Popen] | None = None,
    sonda: Callable[[str], bool] = url_responde,
    reloj: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> ResultadoServicio:
    """Ejecuta la capa de un servicio y la clasifica.

    El arranque (si lo hay) se para con todo su árbol al terminar, también tras
    un rojo, un timeout o una excepción (R7).
    """
    lanzar = lanzar or subprocess.Popen
    bloque = servicio.e2e
    url = url_base or bloque.url_base
    dir_trazas = Path(raiz) / RUTA_CACHE / feature / servicio.nombre
    shutil.rmtree(dir_trazas, ignore_errors=True)
    dir_trazas.mkdir(parents=True)
    cwd = Path(raiz) / servicio.ruta
    comando, entorno = comando_efectivo(servicio, url, dir_trazas, raiz)

    inicio = reloj()
    arranque = proceso = None
    cola_de = dir_trazas / "salida.txt"
    try:
        if bloque.arranque:
            with open(dir_trazas / "arranque.txt", "wb") as registro:
                arranque = lanzar(
                    bloque.arranque, shell=True, cwd=cwd, env=entorno,
                    stdout=registro, stderr=subprocess.STDOUT, **_opciones_arbol(),
                )
            motivo = _esperar_arranque(arranque, url, bloque.espera_arranque_s,
                                       sonda, reloj, dormir)
            if motivo is not None:
                parar_arbol(arranque)
                cola_de = dir_trazas / "arranque.txt"
                with open(cola_de, "a", encoding="utf-8") as registro:
                    registro.write(f"\n[arnés] NO ARRANCA: {motivo}\n")
                return _medir(servicio, comando, url, NO_ARRANCA, reloj() - inicio,
                              dir_trazas, raiz, cola_de)

        with open(dir_trazas / "salida.txt", "wb") as registro:
            proceso = lanzar(
                comando, shell=isinstance(comando, str), cwd=cwd, env=entorno,
                stdout=registro, stderr=subprocess.STDOUT, **_opciones_arbol(),
            )
            try:
                codigo = proceso.wait(timeout=bloque.timeout_s)
            except subprocess.TimeoutExpired:
                parar_arbol(proceso)
                resultado = TIMEOUT
            else:
                resultado = VERDE if codigo == 0 else ROJO
        return _medir(servicio, comando, url, resultado, reloj() - inicio,
                      dir_trazas, raiz, cola_de)
    finally:
        for vivo in (proceso, arranque):
            if vivo is not None:
                parar_arbol(vivo)


def _medir(
    servicio: Servicio, comando: list[str] | str, url: str, resultado: str,
    duracion_s: float, dir_trazas: Path, raiz: str, cola_de: Path,
) -> ResultadoServicio:
    contados = contar_junit(dir_trazas / "junit.xml")
    pasados, fallados, omitidos = contados if contados else (None, None, None)
    try:
        trazas = dir_trazas.resolve().relative_to(Path(raiz).resolve()).as_posix()
    except ValueError:
        trazas = dir_trazas.as_posix()
    return ResultadoServicio(
        servicio=servicio.nombre,
        runner=servicio.e2e.runner,
        comando=_texto_comando(comando),
        url_base=url,
        resultado=resultado,
        pasados=pasados,
        fallados=fallados,
        omitidos=omitidos,
        duracion_s=round(duracion_s, 1),
        trazas=trazas,
        cola_salida=() if resultado == VERDE else _cola(cola_de),
    )


PASA = "PASA"
FALLA = "FALLA"
OMITIDO = "OMITIDO"
SIN_TEST = "sin test"
SIN_JUNIT = "desconocido (sin junit)"


def _casos_junit(ruta: Path) -> list[tuple[str, str]] | None:
    """`[(nombre, PASA|FALLA|OMITIDO)]` de un junit; `None` si no hay o no se lee."""
    try:
        arbol = ET.parse(ruta)
    except (OSError, ET.ParseError):
        return None
    casos = []
    for caso in arbol.iter("testcase"):
        etiquetas = {hijo.tag for hijo in caso}
        if etiquetas & {"failure", "error"}:
            estado = FALLA
        elif "skipped" in etiquetas:
            estado = OMITIDO
        else:
            estado = PASA
        casos.append((caso.get("name", ""), estado))
    return casos


def contar_junit(ruta: Path) -> tuple[int, int, int] | None:
    """`(pasados, fallados, omitidos)` de un junit; `None` si no hay o no se lee."""
    casos = _casos_junit(ruta)
    if casos is None:
        return None
    estados = [estado for _, estado in casos]
    return (estados.count(PASA), estados.count(FALLA), estados.count(OMITIDO))


# --- Requisitos `(capa: e2e)` (R13) ---------------------------------------------

#: Una línea que abre un requisito: `- **R4.** …` (con o sin viñeta).
_INICIO_REQUISITO = re.compile(r"^\s*(?:[-*]\s+)?\*\*R(\d+)\.\*\*")

#: La marca va AL FINAL del requisito (`specs/SPECS.md`): citarla en medio de
#: un texto no lo convierte en e2e.
_MARCA_E2E = re.compile(r"\(capa:\s*e2e\)\.?$", re.IGNORECASE)


def requisitos_e2e(feature: str, raiz: str = ".") -> list[str]:
    """Requisitos de `specs/F-XXX-*/requirements.md` que terminan en `(capa: e2e)`.

    Un requisito empieza en su línea `**R<n>.**` y llega hasta el siguiente o
    hasta un encabezado.
    """
    ficheros = sorted((Path(raiz) / "specs").glob(f"{feature}-*/requirements.md"))
    if not ficheros:
        return []
    bloques: list[tuple[str, list[str]]] = []
    for linea in ficheros[0].read_text(encoding="utf-8").splitlines():
        inicio = _INICIO_REQUISITO.match(linea)
        if inicio:
            bloques.append((f"R{inicio.group(1)}", [linea]))
        elif linea.lstrip().startswith("#"):
            bloques.append(("", []))
        elif bloques:
            bloques[-1][1].append(linea)
    return [
        requisito for requisito, lineas in bloques
        if requisito and _MARCA_E2E.search(" ".join(" ".join(lineas).split()))
    ]


def trazar_requisitos(
    feature: str, requisitos: list[str], rutas_junit: list[Path] | Path
) -> list[tuple[str, list[str], str]]:
    """`(requisito, tests, resultado)`: tests cuyo nombre contiene `fXXX_rN_`."""
    if isinstance(rutas_junit, (str, Path)):
        rutas_junit = [Path(rutas_junit)]
    leidos = [_casos_junit(Path(ruta)) for ruta in rutas_junit]
    casos = [caso for leido in leidos if leido for caso in leido]
    hay_junit = any(leido is not None for leido in leidos)
    numero = re.sub(r"\D", "", feature)
    filas = []
    for requisito in requisitos:
        patron = re.compile(rf"f{numero}_r{requisito[1:]}_", re.IGNORECASE)
        propios = [(nombre, estado) for nombre, estado in casos if patron.search(nombre)]
        if not hay_junit:
            resultado = SIN_JUNIT
        elif not propios:
            resultado = SIN_TEST
        elif any(estado == FALLA for _, estado in propios):
            resultado = FALLA
        elif all(estado == OMITIDO for _, estado in propios):
            resultado = OMITIDO
        else:
            resultado = PASA
        filas.append((requisito, [nombre for nombre, _ in propios], resultado))
    return filas


# --- Resumen (R11) --------------------------------------------------------------


def _dato(valor: object) -> str:
    return "desconocido" if valor is None else str(valor)


def _celda(texto: str) -> str:
    return texto.replace("|", "\\|")


def resultado_global(resultados: list[ResultadoServicio]) -> str:
    """El peor resultado, con la misma prioridad que el código de salida (R9)."""
    for candidato in (ROJO, NO_ARRANCA, TIMEOUT):
        if any(r.resultado == candidato for r in resultados):
            return candidato
    return VERDE


def escribir_resumen(
    feature: str,
    resultados: list[ResultadoServicio],
    filas_req: list[tuple[str, list[str], str]],
    nivel: str,
    modo: str,
    ruta: Path,
    raiz: str = ".",
) -> None:
    """Reescribe entero el resumen de la capa. Lo que no se midió, «desconocido»."""
    sha = ejecutar_git(["rev-parse", "HEAD"], raiz=raiz).strip() or None
    lineas = [
        f"# {feature} · Capa e2e",
        "",
        "Generado por `python -m harness.e2e`; se reescribe en cada ejecución.",
        "",
        "| Dato | Valor |",
        "|---|---|",
        f"| Fecha | {datetime.datetime.now().astimezone().isoformat(timespec='seconds')} |",
        f"| SHA de HEAD | {_dato(sha)} |",
        f"| Nivel | {nivel} |",
        f"| Modo de la capa | {modo} |",
        f"| Resultado global | {resultado_global(resultados)} |",
        "",
        "## Servicios",
        "",
        ("| Servicio | Runner | Comando | url_base | Resultado | Pasados | Fallados "
         "| Omitidos | Duración (s) | Trazas |"),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        lineas.append(
            f"| {r.servicio} | {r.runner} | `{_celda(r.comando)}` | {r.url_base} | "
            f"{r.resultado} | {_dato(r.pasados)} | {_dato(r.fallados)} | "
            f"{_dato(r.omitidos)} | {r.duracion_s} | {r.trazas} |"
        )
    lineas += ["", "## Requisitos e2e", ""]
    if filas_req:
        lineas += ["| Requisito | Tests | Resultado |", "|---|---|---|"]
        lineas += [
            f"| {req} | {', '.join(tests) or '—'} | {resultado} |"
            for req, tests, resultado in filas_req
        ]
    else:
        lineas.append("La spec no marca requisitos `(capa: e2e)`.")
    con_cola = [r for r in resultados if r.resultado != VERDE]
    if con_cola:
        lineas += ["", "## Cola de salida (servicios que no salen VERDE)"]
        for r in con_cola:
            lineas += ["", f"### {r.servicio} ({r.resultado})", "", "```",
                       *r.cola_salida, "```"]
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")


def codigo_global(resultados: list[ResultadoServicio]) -> int:
    """1 con algún ROJO; si no, 3 con algún NO ARRANCA; si no, 2 con TIMEOUT; 0 (R9)."""
    vistos = {resultado.resultado for resultado in resultados}
    if ROJO in vistos:
        return CODIGO_ROJO
    if NO_ARRANCA in vistos:
        return CODIGO_NO_ARRANCA
    if TIMEOUT in vistos:
        return CODIGO_TIMEOUT
    return 0


# --- Estado para init.sh (R15–R16) ----------------------------------------------

CODIGO_AVISO = 3

#: Fila del resumen que lee `--estado` (la escribe `escribir_resumen`).
_FILA_GLOBAL = re.compile(r"^\| Resultado global \| ([^|]+?) \|$", re.MULTILINE)


def ficheros_de_ui(ficheros: list[str], servicios: list[Servicio]) -> list[str]:
    """Ficheros del diff que casan con un glob de `rutas_ui` de su servicio (R16)."""
    tocados = set()
    for servicio in servicios:
        if servicio.e2e is None:
            continue
        prefijo = "" if servicio.ruta in ("", ".") else f"{servicio.ruta}/"
        for fichero in ficheros:
            if any(_casa(fichero, prefijo + glob) for glob in servicio.e2e.rutas_ui):
                tocados.add(fichero.replace("\\", "/"))
    return sorted(tocados)


def _describir_ui(ficheros: list[str]) -> str:
    resto = len(ficheros) - 1
    return f"toca UI: {ficheros[0]}" + (f" y {resto} más" if resto else "")


def estado(
    feature: str, base: str, raiz: str = ".", git: EjecutorGit | None = None
) -> tuple[int, str]:
    """`(código, línea)` de la capa para la feature en curso, sin ejecutar nada.

    0 N/A u OK; 3 AVISO (la capa es informativa); 1 KO (la exige el nivel, o la
    configuración no se puede leer). La frescura del resumen no se mira: el
    commit del propio resumen mueve HEAD; la cubre el reviewer reejecutando.
    """
    if not feature:
        return (0, (f"{ETIQUETA}: N/A (sin feature en curso: ni la rama actual "
                    f"corresponde a una feature sin cerrar ni hay ninguna activa)"))
    if not (Path(raiz) / RUTA_SERVICIOS).is_file():
        return (0, (f"{ETIQUETA}: N/A (sin {RUTA_SERVICIOS.as_posix()}: declara el "
                    f"proyecto como servicio para usar la capa e2e)"))
    try:
        servicios = [s for s in cargar_servicios(raiz=raiz) if s.e2e is not None]
        if not servicios:
            return (0, f"{ETIQUETA}: N/A (ningún servicio declara el bloque e2e)")
        rigor = cargar_rigor(Path(raiz) / "harness/rigor.json")
        features = cargar_features(Path(raiz) / "harness/features.json")
        ficha = next((f for f in features if f.get("id") == feature), {})
        nivel = nivel_de_feature(ficha, rigor)
        exigida = exige(nivel, "e2e", rigor)
        if not exigida and not informativa(nivel, "e2e", rigor):
            return (0, f"{ETIQUETA}: N/A (nivel {nivel}: la capa no aplica)")
        de_ui = ficheros_de_ui(ficheros_tocados(feature, base, None, raiz, git), servicios)
        requisitos = requisitos_e2e(feature, raiz)
    except (ValueError, SystemExit, OSError) as error:
        return (1, f"{ETIQUETA}: KO ({' '.join(str(error).split())})")

    if not de_ui and not requisitos:
        return (0, (f"{ETIQUETA}: N/A ({feature} ni toca rutas_ui ni su spec marca "
                    f"requisitos (capa: e2e))"))

    motivos = []
    if de_ui:
        motivos.append(_describir_ui(de_ui))
    if requisitos:
        motivos.append(f"requisitos e2e: {', '.join(requisitos)}")
    por_que = "; ".join(motivos)
    resumen = f"progress/e2e_{feature}.md"
    fichero = Path(raiz) / resumen
    global_ = None
    if fichero.is_file():
        encontrado = _FILA_GLOBAL.search(fichero.read_text(encoding="utf-8"))
        global_ = encontrado.group(1).strip() if encontrado else "ilegible"
    if global_ == VERDE:
        return (0, f"{ETIQUETA}: OK ({resumen}: resultado global VERDE; {por_que})")
    falta = (f"{resumen}: resultado global {global_}" if global_
             else f"no existe {resumen}")
    lanzala = f"lánzala con: python -m harness.e2e --feature {feature}"
    if exigida:
        return (1, f"{ETIQUETA}: KO ({falta}; {por_que}; {lanzala})")
    return (CODIGO_AVISO, (f"{ETIQUETA}: AVISO (informativa, no bloquea): {falta}; "
                           f"{por_que}; {lanzala}"))


# --- Plantillas (R18–R19) -----------------------------------------------------

#: Plantillas por runner. Llevan `.plantilla`: ni pytest, ni compileall, ni ruff,
#: ni la mutación las ven mientras viajan dentro de `harness/`.
RUTA_PLANTILLAS = Path(__file__).resolve().parent / "plantillas_e2e"
SUFIJO_PLANTILLA = ".plantilla"

#: Marca que se sustituye por la `ruta_tests` del servicio al copiar.
MARCA_RUTA_TESTS = "__RUTA_TESTS__"

#: Carpetas de tests de las plantillas: al copiarse pasan a ser `ruta_tests`.
_CARPETAS_DE_TESTS = ("tests_e2e", "e2e")

_INSTALACION = {
    "pytest-playwright": "pip install pytest-playwright && playwright install chromium "
                         "(en el venv del servicio)",
    "playwright-test": "npm install -D @playwright/test && npx playwright install chromium",
}


def copiar_plantillas(servicio: Servicio, raiz: str = ".") -> tuple[list[str], list[str]]:
    """Copia las plantillas del runner al servicio sin pisar nada.

    Devuelve `(copiados, omitidos)`, rutas relativas a `raiz`. No instala nada.
    """
    if servicio.e2e is None:
        raise ValueError(f"el servicio '{servicio.nombre}' no declara el bloque e2e")
    bloque = servicio.e2e
    origen = RUTA_PLANTILLAS / bloque.runner
    base = Path(raiz) / servicio.ruta
    copiados: list[str] = []
    omitidos: list[str] = []
    for plantilla in sorted(origen.rglob(f"*{SUFIJO_PLANTILLA}")):
        partes = list(plantilla.relative_to(origen).parts)
        partes[-1] = partes[-1][: -len(SUFIJO_PLANTILLA)]
        if len(partes) > 1 and partes[0] in _CARPETAS_DE_TESTS:
            partes = [*bloque.ruta_tests.split("/"), *partes[1:]]
        destino = base.joinpath(*partes)
        relativa = destino.relative_to(Path(raiz)).as_posix()
        if destino.exists():
            omitidos.append(relativa)
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        texto = plantilla.read_text(encoding="utf-8").replace(MARCA_RUTA_TESTS,
                                                              bloque.ruta_tests)
        destino.write_text(texto, encoding="utf-8", newline="\n")
        copiados.append(relativa)
    return sorted(copiados), sorted(omitidos)


def _plantilla(opciones: argparse.Namespace) -> int:
    try:
        servicios = cargar_servicios(raiz=opciones.raiz)
    except ValueError as error:
        print(f"{ETIQUETA}: configuración inválida: {error}", file=sys.stderr)
        return CODIGO_CONFIGURACION
    servicio = next((s for s in servicios if s.nombre == opciones.servicio), None)
    if not opciones.servicio or servicio is None or servicio.e2e is None:
        print(f"{ETIQUETA}: --plantilla necesita --servicio NOMBRE de un servicio que "
              f"declare el bloque e2e", file=sys.stderr)
        return CODIGO_CONFIGURACION
    copiados, omitidos = copiar_plantillas(servicio, opciones.raiz)
    print(f"{ETIQUETA}: plantillas de {servicio.e2e.runner} para '{servicio.nombre}'")
    for ruta in copiados:
        print(f"    copiado: {ruta}")
    for ruta in omitidos:
        print(f"    omitido (ya existe, no se pisa): {ruta}")
    print(f"    El arnés no instala nada. Playwright lo instala el proyecto: "
          f"{_INSTALACION[servicio.e2e.runner]}")
    if servicio.e2e.runner == "pytest-playwright":
        print(f"    Los tests e2e viven en {servicio.ruta}/{servicio.e2e.ruta_tests}/ con "
              f"su conftest.py: sin él, la suite de init.sh los colectaría.")
    return 0


# --- CLI --------------------------------------------------------------------


def _feature_de_la_rama(raiz: str) -> str:
    """La feature en curso de la rama actual (sin las `done`); vacío si no hay."""
    rama = ejecutar_git(["branch", "--show-current"], raiz=raiz).strip()
    ficha = feature_de_rama(rama, cargar_features(Path(raiz) / "harness/features.json"))
    if not ficha or ficha.get("status") == "done":
        return ""
    return ficha.get("id", "")


def _nivel_y_modo(feature: str, raiz: str) -> tuple[str, str]:
    """Nivel de rigor de la feature y si la capa es exigida, informativa o no aplica."""
    try:
        rigor = cargar_rigor(Path(raiz) / "harness/rigor.json")
    except ValueError:
        return ("desconocido", "desconocido")
    features = cargar_features(Path(raiz) / "harness/features.json")
    ficha = next((f for f in features if f.get("id") == feature), {})
    nivel = nivel_de_feature(ficha, rigor)
    if exige(nivel, "e2e", rigor):
        return (nivel, "exigida")
    if informativa(nivel, "e2e", rigor):
        return (nivel, "informativa")
    return (nivel, "no aplica por nivel")


def _ejecutar(opciones: argparse.Namespace) -> int:
    raiz = opciones.raiz
    if opciones.url_base is not None and not host_de_url(opciones.url_base):
        # Mismo criterio que R1 para `url_base`: sin esquema o sin host, la guarda
        # de hosts_prohibidos no vería el host y el runner lo recibiría igual.
        print(f"{ETIQUETA}: --url-base {opciones.url_base!r} debe empezar por http:// "
              f"o https:// y llevar host, sin barra invertida, blancos ni caracteres "
              f"de control, con el host en ASCII (nada no ASCII: un IDN va en "
              f"forma xn--) y la IP en forma canónica (IPv4 de cuatro decimales, "
              f"IPv6 sin IPv4 embebida): no se lanza nada", file=sys.stderr)
        return CODIGO_CONFIGURACION
    try:
        servicios = cargar_servicios(raiz=raiz)
    except ValueError as error:
        print(f"{ETIQUETA}: configuración inválida: {error}", file=sys.stderr)
        return CODIGO_CONFIGURACION

    feature = opciones.feature or _feature_de_la_rama(raiz)
    if not feature:
        print(f"{ETIQUETA}: no hay feature: pásala con --feature F-XXX", file=sys.stderr)
        return CODIGO_CONFIGURACION

    con_e2e = [servicio for servicio in servicios if servicio.e2e is not None]
    if opciones.servicio:
        con_e2e = [s for s in con_e2e if s.nombre == opciones.servicio]
        if not con_e2e:
            print(f"{ETIQUETA}: el servicio '{opciones.servicio}' no existe o no "
                  f"declara el bloque e2e", file=sys.stderr)
            return CODIGO_CONFIGURACION

    requisitos = requisitos_e2e(feature, raiz)
    if not con_e2e:
        motivo = (
            f"sin {RUTA_SERVICIOS.as_posix()}: declara el proyecto como servicio para "
            f"usar la capa e2e"
            if not servicios
            else "ningún servicio declara el bloque e2e"
        )
        if requisitos:
            print(f"{ETIQUETA}: incoherencia: la spec de {feature} marca requisitos "
                  f"(capa: e2e) ({', '.join(requisitos)}) y {motivo}: declara el bloque "
                  f"e2e del servicio o cambia la capa de esos requisitos",
                  file=sys.stderr)
            return CODIGO_CONFIGURACION
        print(f"{ETIQUETA}: N/A ({motivo})")
        return 0

    if opciones.url_base:
        for servicio in con_e2e:
            patron = host_prohibido(opciones.url_base, servicio.e2e.hosts_prohibidos)
            if patron is not None:
                print(f"{ETIQUETA}: --url-base {opciones.url_base} apunta a un host "
                      f"declarado como productivo en '{servicio.nombre}' ('{patron}'): "
                      f"no se lanza nada", file=sys.stderr)
                return CODIGO_CONFIGURACION

    resultados = [
        ejecutar_servicio(servicio, feature, opciones.url_base, raiz)
        for servicio in con_e2e
    ]
    junits = [Path(raiz) / RUTA_CACHE / feature / s.nombre / "junit.xml" for s in con_e2e]
    filas = trazar_requisitos(feature, requisitos, junits)
    nivel, modo = _nivel_y_modo(feature, raiz)
    ruta = Path(opciones.salida) if opciones.salida else (
        Path(raiz) / "progress" / f"e2e_{feature}.md")
    escribir_resumen(feature, resultados, filas, nivel, modo, ruta, raiz)
    for resultado in resultados:
        print(f"{ETIQUETA} [{resultado.servicio}]: {resultado.resultado} "
              f"({resultado.duracion_s} s; trazas en {resultado.trazas})")
    print(f"{ETIQUETA}: resumen en {ruta.as_posix()}")
    return codigo_global(resultados)


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la capa e2e, informa de su estado o copia las plantillas."""
    analizador = argparse.ArgumentParser(
        prog="python -m harness.e2e",
        description="Capa e2e (Playwright) del arnés: ejecución, estado y plantillas.",
    )
    analizador.add_argument("--feature", default=None)
    analizador.add_argument("--servicio", default=None)
    analizador.add_argument("--url-base", default=None)
    analizador.add_argument("--salida", default=None)
    analizador.add_argument("--estado", action="store_true",
                            help="una línea CAPA E2E para init.sh; no ejecuta nada")
    analizador.add_argument("--base", default=None,
                            help="rama de integración (por defecto, RAMA_BASE de init.sh)")
    analizador.add_argument("--plantilla", action="store_true",
                            help="copia las plantillas del runner al --servicio")
    analizador.add_argument("--raiz", default=".")
    opciones = analizador.parse_args(argv)
    if opciones.plantilla:
        return _plantilla(opciones)
    if opciones.estado:
        codigo, linea = estado(_feature_de_la_rama(opciones.raiz),
                               opciones.base or rama_base_configurada(opciones.raiz),
                               opciones.raiz)
        print(linea)
        return codigo
    return _ejecutar(opciones)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
