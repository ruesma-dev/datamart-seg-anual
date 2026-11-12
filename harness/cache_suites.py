# harness/cache_suites.py
"""Caché de las suites de los servicios: cuándo un verde anterior sigue valiendo.

El portero (`harness/init.sh`, sección 7 bis) se salta la suite de un servicio
si nada de lo que puede cambiar su resultado ha cambiado desde su último verde.
Antes de la 1.7.16 la clave era solo el árbol del servicio en `HEAD`, y eso dejaba
fuera lo que el servicio importa de otras carpetas: un commit en la librería
común no invalidaba la caché de quien la usa, y en un worktree la suite
importaba la común de OTRO árbol mientras el portero daba verde por caché.

La clave es el `sha256` de un texto canónico con:

- una marca de formato (una caché del formato anterior nunca coincide);
- el hash en `HEAD` de la ruta del servicio y de cada ruta de `depende_de`;
- la ruta resuelta del intérprete con el que corre la suite;
- dónde resuelve ese intérprete cada módulo de `importa` (una sonda lo
  pregunta sin importarlo);
- la huella de las entradas no versionadas: `.env` de la raíz, el del servicio
  y las declaradas. Huella = nombre, tamaño y fecha de modificación. El
  contenido NO se lee nunca: puede llevar secretos.

Sin clave no hay caché: con cambios sin commitear (como siempre), con una
dependencia fuera de `HEAD`, con un módulo que resuelve fuera del repositorio
o de las rutas declaradas, o si la sonda falla. Salvo el primer caso, todos
avisan: un verde que no se puede reutilizar debe decir por qué.

Dos casos que la clave no ve (F-028). `depende_de: ["."]` declara el
repositorio entero: su hash es el árbol raíz en `HEAD`, así que cualquier
commit, y cualquier cambio sin commitear, anula la caché. Más barato para un
barrido que lee todo el repositorio (`progress/`, `docs/`...) es declararlo en
`ejecutar_siempre`: al servir de caché, la salida lleva una línea
`SIEMPRE|<ruta>` por cada una e init.sh las ejecuta igualmente. No entran en
la clave: declararlas o cambiarlas no invalida un verde.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from harness import servicios
from harness.servicios import Servicio

#: Marca de formato: entra en el texto de la clave. Cambiarla invalida todas.
FORMATO_CLAVE = "cache-suites/2"

#: Segundos que se espera a la sonda antes de darla por fallida.
LIMITE_SONDA_S = 30

#: Entradas locales que entran siempre en la clave: en la raíz y bajo la ruta
#: de cada servicio.
ENTRADAS_LOCALES_POR_DEFECTO: tuple[str, ...] = (".env",)

#: Sonda: se ejecuta con el intérprete del servicio desde su carpeta. Localiza
#: cada módulo con `find_spec`, que NO ejecuta el `__init__` del primer nivel
#: (en un nombre con puntos sí importa los padres: es inevitable). La respuesta
#: va en la última línea, por si un padre imprime algo al importarse.
SONDA = """
import importlib.util, json, sys
origenes = {}
for nombre in sys.argv[1:]:
    try:
        spec = importlib.util.find_spec(nombre)
    except Exception:
        spec = None
    origen = None
    if spec is not None:
        if spec.origin and spec.origin != "namespace":
            origen = spec.origin
        elif spec.submodule_search_locations:
            origen = list(spec.submodule_search_locations)[0]
    origenes[nombre] = origen
print()
print(json.dumps({"origenes": origenes,
                  "coverage": importlib.util.find_spec("coverage") is not None}))
"""


@dataclass(frozen=True)
class Sondeo:
    """Lo que responde la sonda sobre el intérprete de un servicio."""

    origenes: dict[str, str | None]
    tiene_coverage: bool


@dataclass(frozen=True)
class Decision:
    """Servir la suite de caché o ejecutarla (y con qué clave guardar el verde)."""

    servir: bool
    #: `None` = no se guarda caché tras el verde.
    clave: str | None
    #: `AAAA-MM-DD HH:MM` (hora local) del verde que se reutiliza; solo si `servir`.
    fecha_verde: str | None
    avisos: tuple[str, ...]
    #: Rutas de `ejecutar_siempre` que init.sh ejecuta aunque sirva la suite
    #: de caché (F-028); solo si `servir`: al ejecutar, la suite entera ya las
    #: incluye.
    siempre: tuple[str, ...] = ()


class ErrorDeSonda(Exception):
    """La sonda no pudo responder: no hay clave."""


# --- Piezas: git, ficheros y la sonda ----------------------------------------


def _git(args: list[str], raiz: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=raiz,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        check=False,
    )


def hash_en_head(ruta: str, raiz: str) -> str | None:
    """Hash del objeto de `ruta` en `HEAD`; `None` si no está versionada.

    `.` es el repositorio entero (F-028): `HEAD:` da el árbol raíz, y `HEAD:.`
    falla porque git no resuelve `.` dentro de un árbol.
    """
    objeto = "" if ruta == "." else ruta
    proceso = _git(["rev-parse", "--verify", "--quiet", f"HEAD:{objeto}"], raiz)
    hash_objeto = proceso.stdout.strip()
    if proceso.returncode != 0 or not hash_objeto:
        return None
    return hash_objeto


def hay_cambios(rutas: list[str], raiz: str) -> bool:
    """¿Hay cambios sin commitear (o ficheros sin rastrear) bajo `rutas`?

    Si git no responde, se contesta que sí: sin certeza no hay caché.
    """
    proceso = _git(["status", "--porcelain", "--", *rutas], raiz)
    return proceso.returncode != 0 or bool(proceso.stdout.strip())


def raiz_del_repositorio(raiz: str) -> Path:
    """Raíz del árbol de trabajo en curso (`git rev-parse --show-toplevel`)."""
    proceso = _git(["rev-parse", "--show-toplevel"], raiz)
    return Path(proceso.stdout.strip()).resolve()


def huella_local(ruta: str, raiz: str) -> str:
    """`<ruta>@<tamaño>:<mtime_ns>` o `<ruta>@ausente`. Solo `os.stat`: no se abre."""
    try:
        estado = os.stat(Path(raiz) / ruta)
    except OSError:
        return f"{ruta}@ausente"
    return f"{ruta}@{estado.st_size}:{estado.st_mtime_ns}"


def sondear(
    interprete: str,
    modulos: tuple[str, ...],
    cwd: Path,
    limite_s: int = LIMITE_SONDA_S,
) -> Sondeo:
    """Pregunta al intérprete del servicio dónde resuelve cada módulo.

    Sin `-I`: la sonda tiene que ver el mismo `sys.path` que verá
    `python -m pytest` lanzado desde la carpeta del servicio.
    """
    try:
        proceso = subprocess.run(
            [interprete, "-c", SONDA, *modulos],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=limite_s,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ErrorDeSonda(f"la sonda tardó más de {limite_s} s") from error
    except OSError as error:
        raise ErrorDeSonda(f"no se pudo lanzar la sonda con {interprete}: {error}") from error

    if proceso.returncode != 0:
        detalle = (proceso.stderr.strip().splitlines() or [""])[-1]
        raise ErrorDeSonda(f"la sonda salió con código {proceso.returncode}: {detalle}")
    try:
        datos = json.loads(proceso.stdout.strip().splitlines()[-1])
        return Sondeo(
            origenes={nombre: datos["origenes"].get(nombre) for nombre in modulos},
            tiene_coverage=bool(datos["coverage"]),
        )
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        raise ErrorDeSonda(f"la sonda dio una respuesta ilegible: {error!r}") from error


def _canonica(ruta: str) -> str:
    """Ruta resuelta y con la capitalización que el sistema operativo ignora."""
    return os.path.normcase(str(Path(ruta).resolve()))


def _dentro_de(ruta: str, base: str) -> bool:
    """¿`ruta` es `base` o cuelga de ella? Ignora mayúsculas donde el SO las ignora."""
    canonica = _canonica(ruta)
    canonica_base = _canonica(base)
    return canonica == canonica_base or canonica.startswith(
        canonica_base.rstrip(os.sep) + os.sep
    )


# --- La clave ------------------------------------------------------------------


def _entradas_locales(servicio: Servicio) -> list[str]:
    por_defecto = [
        *ENTRADAS_LOCALES_POR_DEFECTO,
        *(f"{servicio.ruta}/{entrada}" for entrada in ENTRADAS_LOCALES_POR_DEFECTO),
    ]
    return sorted(set(por_defecto) | set(servicio.entradas_no_versionadas))


def _lineas_de_modulos(
    servicio: Servicio, raiz: str, sondeo: Sondeo, avisos: list[str]
) -> list[str] | None:
    """Una línea por módulo vigilado; `None` (con su aviso) si alguno no vale."""
    if not servicio.importa:
        return []
    repositorio = raiz_del_repositorio(raiz)
    rutas = [servicio.ruta, *servicio.depende_de]
    lineas: list[str] = []
    valido = True
    for modulo in sorted(servicio.importa):
        origen = sondeo.origenes.get(modulo)
        if origen is None:
            avisos.append(
                f"no se encuentra `{modulo}` con el intérprete de `{servicio.nombre}`; "
                f"no se cachea"
            )
        elif not os.path.isabs(origen) or not _dentro_de(origen, str(repositorio)):
            avisos.append(
                f"`{servicio.nombre}` importa `{modulo}` desde {origen}, fuera de este "
                f"repositorio: su suite prueba ESA copia y no la de este árbol; "
                f"no se cachea"
            )
        elif not any(_dentro_de(origen, str(Path(raiz) / ruta)) for ruta in rutas):
            relativa = Path(_canonica(origen)).relative_to(
                Path(_canonica(str(repositorio)))
            ).as_posix()
            avisos.append(
                f"`{servicio.nombre}` importa `{modulo}` desde {relativa}, que no está "
                f"declarada: añádela a `depende_de`; no se cachea"
            )
        else:
            lineas.append(f"modulo={modulo}@{_canonica(origen)}")
            continue
        valido = False
    return lineas if valido else None


def texto_de_clave(
    servicio: Servicio, raiz: str, interprete: str, sondeo: Sondeo
) -> tuple[str | None, list[str]]:
    """Texto canónico del que sale la clave, o `None` con los avisos del porqué."""
    if hay_cambios([servicio.ruta, *servicio.depende_de], raiz):
        return None, []

    avisos: list[str] = []
    valido = True
    hash_servicio = hash_en_head(servicio.ruta, raiz)
    if hash_servicio is None:
        valido = False

    lineas_depende: list[str] = []
    for dependencia in sorted(servicio.depende_de):
        hash_dependencia = hash_en_head(dependencia, raiz)
        if hash_dependencia is None:
            avisos.append(
                f"`{dependencia}` no está versionada en HEAD; si es un fichero local, "
                f"declárala en `entradas_no_versionadas`; no se cachea"
            )
            valido = False
        else:
            lineas_depende.append(f"depende={dependencia}@{hash_dependencia}")

    lineas_modulos = _lineas_de_modulos(servicio, raiz, sondeo, avisos)
    if not valido or lineas_modulos is None:
        return None, avisos

    lineas = [
        f"formato={FORMATO_CLAVE}",
        f"servicio={servicio.ruta}@{hash_servicio}",
        *lineas_depende,
        f"interprete={_canonica(interprete)}",
        *lineas_modulos,
        *(f"local={huella_local(entrada, raiz)}" for entrada in _entradas_locales(servicio)),
    ]
    return "\n".join(lineas), avisos


def clave_de(
    servicio: Servicio, raiz: str, interprete: str, sondeo: Sondeo
) -> tuple[str | None, list[str]]:
    """`sha256` hexadecimal del texto canónico, o `None` con sus avisos."""
    texto, avisos = texto_de_clave(servicio, raiz, interprete, sondeo)
    if texto is None:
        return None, avisos
    return hashlib.sha256(texto.encode("utf-8")).hexdigest(), avisos


# --- Decisión y CLI ---------------------------------------------------------------


def decidir(
    servicio: Servicio,
    raiz: str = ".",
    *,
    sin_cache: bool = False,
    sondear=sondear,
) -> Decision:
    """¿Se sirve la suite de caché? `sondear` es inyectable para los tests."""
    interprete = servicios.interprete(servicio, raiz)
    try:
        sondeo = sondear(interprete, servicio.importa, Path(raiz) / servicio.ruta)
    except ErrorDeSonda as error:
        aviso = f"no se pudo sondear el intérprete de `{servicio.nombre}`: {error}; no se cachea"
        return Decision(servir=False, clave=None, fecha_verde=None, avisos=(aviso,))

    clave, avisos = clave_de(servicio, raiz, interprete, sondeo)
    fichero = Path(raiz) / ".arnes_cache" / f"suite_{servicio.nombre}.ok"
    servir = (
        not sin_cache
        and clave is not None
        and fichero.is_file()
        and fichero.read_text(encoding="utf-8").strip() == clave
        and (
            not sondeo.tiene_coverage
            or (Path(raiz) / servicio.ruta / "coverage.json").is_file()
        )
    )
    fecha_verde = (
        time.strftime("%Y-%m-%d %H:%M", time.localtime(fichero.stat().st_mtime))
        if servir
        else None
    )
    return Decision(
        servir=servir,
        clave=clave,
        fecha_verde=fecha_verde,
        avisos=tuple(avisos),
        siempre=servicio.ejecutar_siempre if servir else (),
    )


def lineas_de_salida(decision: Decision) -> list[str]:
    """Protocolo para init.sh: `AVISO|...`, al servir `SIEMPRE|<ruta>` por cada
    ruta de `ejecutar_siempre`, y al final `SERVIR|` o `EJECUTAR|`."""
    lineas = [f"AVISO|{' '.join(aviso.split())}" for aviso in decision.avisos]
    if decision.servir:
        lineas.extend(f"SIEMPRE|{ruta}" for ruta in decision.siempre)
        lineas.append(f"SERVIR|{decision.fecha_verde}")
    else:
        lineas.append(f"EJECUTAR|{decision.clave or ''}")
    return lineas


def main(argv: list[str] | None = None) -> int:
    """`--servicio NOMBRE [--sin-cache] [--raiz .]`: decide la caché de un servicio."""
    analizador = argparse.ArgumentParser(
        prog="python -m harness.cache_suites",
        description="Decide si la suite de un servicio se sirve de caché.",
    )
    analizador.add_argument("--servicio", required=True)
    analizador.add_argument("--sin-cache", action="store_true")
    analizador.add_argument("--raiz", default=".")
    opciones = analizador.parse_args(argv)

    try:
        declarados = servicios.cargar_servicios(raiz=opciones.raiz)
        servicio = next(
            (s for s in declarados if s.nombre == opciones.servicio), None
        )
        if servicio is None:
            raise ValueError(
                f"el servicio '{opciones.servicio}' no está declarado en "
                f"harness/servicios.json"
            )
        if servicio.lenguaje != "python":
            raise ValueError(
                f"el servicio '{servicio.nombre}' no es de lenguaje 'python': "
                f"su suite no pasa por esta caché"
            )
        decision = decidir(
            servicio, opciones.raiz, sin_cache=opciones.sin_cache, sondear=sondear
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    for linea in lineas_de_salida(decision):
        print(linea)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
