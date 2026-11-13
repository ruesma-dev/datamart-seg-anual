# harness/servicios.py
"""Servicios de un monorepo: qué zonas del repositorio se validan por separado.

Un repositorio puede alojar varios servicios en subcarpetas, cada uno con su
entorno virtual, sus tests y hasta otro lenguaje. Este módulo lee la
declaración **opcional** `harness/servicios.json` y responde a las tres
preguntas que necesitan el portero, la puerta de cobertura y la campaña de
mutación: qué servicios hay, a cuál pertenece un fichero y con qué intérprete
se ejecuta su suite.

Regla de oro: **sin `harness/servicios.json` no cambia nada**. La ausencia del
fichero es la configuración del caso mayoritario —un solo proyecto en la
raíz—, y en ese caso `cargar_servicios()` devuelve una lista vacía y el resto
del arnés sigue exactamente el camino de siempre.

La otra cara: si el fichero existe pero está roto, el arnés **falla**. Degradar
en silencio a mono-proyecto dejaría servicios enteros sin comprobar mientras el
portero imprime que todo va bien, que es la peor de las salidas posibles.
"""

from __future__ import annotations

import argparse
import difflib
import ipaddress
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

#: Ruta (relativa a la raíz del repositorio) de la declaración de servicios.
RUTA_SERVICIOS = Path("harness/servicios.json")

#: Lenguajes que la declaración reconoce. `otro` significa «no es Python»: sus
#: comprobaciones de Python se degradan con aviso.
LENGUAJES: tuple[str, ...] = ("python", "otro")

#: Separador de la salida `--shell`. No puede aparecer dentro de un campo.
SEPARADOR = "|"

#: Rutas relativas donde vive el intérprete dentro de un entorno virtual.
INTERPRETES_DEL_VENV: tuple[str, ...] = ("Scripts/python.exe", "bin/python")

#: Forma de un nombre de módulo de Python, con o sin puntos (`pkg.sub`).
NOMBRE_DE_MODULO = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")

#: Directorios que el alcance AUTOMÁTICO excluye (`DIRECTORIOS_EXCLUIDOS` de
#: `harness.alcance`) y que un servicio puede pedir que, bajo su ruta, SÍ se
#: midan, con `"alcance_incluye"`. Solo `harness`: es el único excluido que
#: puede ser producto —en el repositorio que fabrica el arnés lo es—, y es el
#: mismo que ya admite el alcance declarado con `--ficheros`. Mutar `tests`,
#: `specs`, `progress` o `docs` no significa nada en ningún proyecto. Vive aquí
#: y no en `alcance` porque `alcance` importa este módulo, no al revés; un test
#: fija que coincide con la diferencia entre las dos listas de `alcance`.
DIRECTORIOS_INCLUIBLES: tuple[str, ...] = ("harness",)

#: Claves que entiende una entrada de la declaración. Las demás se ignoran
#: (compatibilidad), salvo las que se parecen a una de `CLAVES_VIGILADAS`: ver
#: `_rechazar_clave_parecida`.
CLAVES_DE_SERVICIO: tuple[str, ...] = (
    "nombre",
    "ruta",
    "lenguaje",
    "venv",
    "comando_tests",
    "depende_de",
    "importa",
    "entradas_no_versionadas",
    "alcance_incluye",
    "ejecutar_siempre",
    "e2e",
)

#: Runners de la capa e2e (F-059). El primero es el valor por defecto.
RUNNERS_E2E: tuple[str, ...] = ("pytest-playwright", "playwright-test")

#: Claves del bloque `e2e`. Al revés que fuera del bloque, aquí una clave
#: desconocida es un error: el bloque es nuevo y nadie tiene claves propias.
CLAVES_E2E: tuple[str, ...] = (
    "runner",
    "comando",
    "url_base",
    "arranque",
    "ruta_tests",
    "espera_arranque_s",
    "timeout_s",
    "rutas_ui",
    "hosts_prohibidos",
)

#: Valores por defecto de los enteros del bloque `e2e`: una sola fuente para el
#: dataclass y el cargador.
ESPERA_ARRANQUE_E2E_S = 60
TIMEOUT_E2E_S = 900

#: Claves cuyo error de escritura sería MUDO (ignorada, nadie se entera): una
#: clave que se les parezca tumba la declaración en vez de ignorarse.
CLAVES_VIGILADAS: tuple[str, ...] = ("alcance_incluye", "ejecutar_siempre")


@dataclass(frozen=True)
class BloqueE2E:
    """La capa e2e de un servicio (F-059): dónde vive la UI y cómo se prueba."""

    url_base: str
    #: Globs, relativos a la ruta del servicio, que hacen que un cambio «toque UI».
    rutas_ui: tuple[str, ...]
    runner: str = RUNNERS_E2E[0]
    comando: str | None = None
    arranque: str | None = None
    ruta_tests: str = "tests_e2e"
    espera_arranque_s: int = ESPERA_ARRANQUE_E2E_S
    timeout_s: int = TIMEOUT_E2E_S
    #: Globs de host contra los que la capa nunca se ejecuta (producción).
    hosts_prohibidos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Servicio:
    """Un servicio declarado del monorepo."""

    nombre: str
    ruta: str
    lenguaje: str
    venv: str | None = None
    comando_tests: str | None = None
    #: Rutas del repositorio de las que depende su suite (1.7.16): un commit en
    #: cualquiera de ellas invalida la caché del servicio.
    depende_de: tuple[str, ...] = ()
    #: Módulos cuya ruta real se comprueba antes de servir la caché (1.7.16).
    importa: tuple[str, ...] = ()
    #: Ficheros no versionados cuya huella (metadatos, nunca contenido) entra
    #: en la clave de la caché (1.7.16).
    entradas_no_versionadas: tuple[str, ...] = ()
    #: Directorios de `DIRECTORIOS_INCLUIBLES` que, bajo la ruta de este
    #: servicio, el alcance automático SÍ mide (F-052). Vacío: lo de siempre.
    alcance_incluye: tuple[str, ...] = ()
    #: Rutas de tests, relativas a la ruta del servicio, que se ejecutan aunque
    #: la suite se sirva de caché (F-028): barridos que leen todo el
    #: repositorio y que ninguna clave puede ver cambiar.
    ejecutar_siempre: tuple[str, ...] = ()
    #: Capa e2e del servicio (F-059); `None` si no la declara.
    e2e: BloqueE2E | None = None


# --- Carga y validación -----------------------------------------------------


def _normalizar(ruta: str) -> str:
    """Separadores a barras y sin barra final: una ruta, una sola escritura."""
    return ruta.replace("\\", "/").strip("/")


def _texto(entrada: dict, clave: str, nombre: str, obligatorio: bool) -> str | None:
    """Lee un campo de texto de la declaración, o falla diciendo cuál falla."""
    valor = entrada.get(clave)
    if valor is None and not obligatorio:
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(
            f"servicio '{nombre}': el campo '{clave}' debe ser un texto no vacío, "
            f"y es {valor!r}"
        )
    if SEPARADOR in valor:
        raise ValueError(
            f"servicio '{nombre}': el campo '{clave}' no puede contener "
            f"'{SEPARADOR}', que es el separador de la salida --shell"
        )
    return valor


def _es_absoluta(ruta: str) -> bool:
    """¿Ruta absoluta en cualquiera de los dos sistemas (`/x`, contrabarra, `C:`)?"""
    return (
        PurePosixPath(ruta.replace("\\", "/")).is_absolute()
        or PureWindowsPath(ruta).drive != ""
    )


def _lista(entrada: dict, clave: str, nombre: str) -> list:
    """Lee un campo de lista; ausente es lista vacía, cualquier otra cosa falla."""
    if clave not in entrada:
        return []
    valor = entrada[clave]
    if not isinstance(valor, list):
        raise ValueError(
            f"servicio '{nombre}': el campo '{clave}' debe ser una lista, y es "
            f"{valor!r}"
        )
    return valor


def _rutas(
    entrada: dict, clave: str, nombre: str, base: str = "la raíz del repositorio"
) -> tuple[str, ...]:
    """Lista de rutas relativas a `base`, normalizadas y sin repetir (R3, R5).

    La existencia NO se mira aquí: la exigen `depende_de` y `ejecutar_siempre`,
    y se comprueba con la raíz en `_comprobar_conjunto`. Un salto de línea
    rompería el protocolo de líneas con `init.sh` (F-028): no se admite.
    """
    rutas: list[str] = []
    for valor in _lista(entrada, clave, nombre):
        if not isinstance(valor, str) or not valor.strip():
            motivo = "debe contener textos no vacíos"
        elif SEPARADOR in valor:
            motivo = f"no puede contener '{SEPARADOR}'"
        elif "\n" in valor or "\r" in valor:
            motivo = "no puede contener saltos de línea"
        elif _es_absoluta(valor):
            motivo = f"debe contener rutas relativas a {base}"
        elif ".." in _normalizar(valor).split("/"):
            motivo = f"no puede salir de {base} con '..'"
        elif _normalizar(valor) in rutas:
            motivo = f"tiene la ruta '{_normalizar(valor)}' repetida"
        else:
            rutas.append(_normalizar(valor))
            continue
        raise ValueError(
            f"servicio '{nombre}': el campo '{clave}' {motivo}, y tiene {valor!r}"
        )
    return tuple(rutas)


def _modulos(entrada: dict, nombre: str, lenguaje: str) -> tuple[str, ...]:
    """Nombres de módulo vigilados (R4): con forma de módulo y sin repetir."""
    if "importa" in entrada and lenguaje != "python":
        raise ValueError(
            f"servicio '{nombre}': el campo 'importa' solo vale en un servicio "
            f"de lenguaje 'python', y este es {lenguaje!r}"
        )
    modulos: list[str] = []
    for valor in _lista(entrada, "importa", nombre):
        if not isinstance(valor, str) or not NOMBRE_DE_MODULO.fullmatch(valor):
            motivo = "debe contener nombres de módulo de Python (p. ej. 'pkg.sub')"
        elif valor in modulos:
            motivo = "tiene un módulo repetido"
        else:
            modulos.append(valor)
            continue
        raise ValueError(
            f"servicio '{nombre}': el campo 'importa' {motivo}, y tiene {valor!r}"
        )
    return tuple(modulos)


def _siempre(entrada: dict, nombre: str, lenguaje: str) -> tuple[str, ...]:
    """Rutas de tests que se ejecutan aunque haya caché (F-028); solo en python."""
    if "ejecutar_siempre" in entrada and lenguaje != "python":
        raise ValueError(
            f"servicio '{nombre}': el campo 'ejecutar_siempre' solo vale en un "
            f"servicio de lenguaje 'python', y este es {lenguaje!r}"
        )
    return _rutas(entrada, "ejecutar_siempre", nombre, base="la ruta del servicio")


def _incluidos(entrada: dict, nombre: str) -> tuple[str, ...]:
    """Directorios que el servicio saca de la exclusión del alcance (F-052)."""
    incluidos: list[str] = []
    for valor in _lista(entrada, "alcance_incluye", nombre):
        if valor not in DIRECTORIOS_INCLUIBLES:
            motivo = f"solo admite {list(DIRECTORIOS_INCLUIBLES)}"
        elif valor in incluidos:
            motivo = "tiene un directorio repetido"
        else:
            incluidos.append(valor)
            continue
        raise ValueError(
            f"servicio '{nombre}': el campo 'alcance_incluye' {motivo}, y tiene "
            f"{valor!r}"
        )
    return tuple(incluidos)


def host_de_url(url: str) -> str:
    """El host de `url` normalizado; "" si no lleva esquema http(s):// o host.

    Normalizar es lo que hace el navegador antes de resolver: decodificar el
    percent-encoding (`%2e` es un punto), pasar a minúsculas y quitar los puntos
    finales (`host.` es el mismo host por DNS). El host se compara como nombre,
    sin resolverlo.

    Una URL con barra invertida, blancos o caracteres de control da "": el
    analizador WHATWG del navegador trata `\\` como `/` y elimina los blancos y
    controles, y urlsplit no, así que verían hosts distintos
    (`http://prod\\@localhost/` es `localhost` para Python y `prod` para el
    navegador). Rechazarla falla cerrado sin emular WHATWG.

    El host normalizado pasa además por una lista blanca: nombre DNS ASCII,
    IPv4 solo en forma canónica de cuatro decimales o IPv6 sin IPv4 embebida;
    cualquier otra cosa da "". El navegador mapea por IDNA los caracteres no
    ASCII (`。` y `．` son un punto, el guion blando y el espacio de ancho cero
    desaparecen), y emularlo sería otra lista negra. Un IDN se declara en forma
    `xn--`, que los dos leen igual. Y si la última etiqueta es numérica, el
    navegador analiza el host entero como IPv4 en decimal, octal o hex
    (`10.5`, `0x0a000005`, `012.0.0.5` y `167772165` son `10.0.0.5`), así que
    solo vale la forma canónica, la única que casa con un `hosts_prohibidos`.
    """
    if any(c == "\\" or c.isspace() or unicodedata.category(c) == "Cc" for c in url):
        return ""
    if not re.fullmatch(r"https?://\S+", url):
        return ""
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:  # p. ej. un corchete de IPv6 sin cerrar
        return ""
    host = unquote(host).lower().rstrip(".")
    return host if _host_en_lista_blanca(host) else ""


#: Nombre DNS ASCII: etiquetas `[a-z0-9-]` separadas por puntos (`xn--` incluido).
#: Cubre también la IPv4, que se filtra aparte con `_ETIQUETA_NUMERICA`.
_NOMBRE_DNS_ASCII = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*")

#: Etiqueta que el analizador WHATWG lee como número (decimal, octal o hex): si
#: es la última, el host entero se analiza como IPv4.
_ETIQUETA_NUMERICA = re.compile(r"[0-9]+|0x[0-9a-f]*")


def _host_en_lista_blanca(host: str) -> bool:
    """Si `host` (ya normalizado) es un nombre DNS ASCII, una IPv4 o una IPv6.

    Un host cuya última etiqueta es numérica tiene que ser una IPv4 canónica de
    cuatro decimales (`ipaddress` ya rechaza los ceros a la izquierda). La IPv6
    llega entre corchetes y urlsplit la devuelve sin ellos; una zona (`%eth0`)
    o una IPv4 embebida (`::ffff:10.0.0.5`, que el navegador reescribe) no se
    aceptan. Todo lo demás, no ASCII incluido, falla cerrado.
    """
    if _NOMBRE_DNS_ASCII.fullmatch(host):
        if not _ETIQUETA_NUMERICA.fullmatch(host.rsplit(".", 1)[-1]):
            return True
        try:
            return str(ipaddress.IPv4Address(host)) == host
        except ValueError:
            return False
    if ":" not in host or "%" in host or "." in host or not host.isascii():
        return False
    try:
        return ipaddress.IPv6Address(host).ipv4_mapped is None
    except ValueError:
        return False


def host_prohibido(url: str, patrones: tuple[str, ...]) -> str | None:
    """El patrón de `patrones` con el que casa el host de `url`, o `None`.

    El host va normalizado con `host_de_url` (mayúsculas, `%xx`, punto final).
    """
    host = host_de_url(url)
    for patron in patrones:
        if fnmatchcase(host, patron.lower()):
            return patron
    return None


def _entero_e2e(bloque: dict, clave: str, nombre: str, defecto: int) -> int:
    """Entero estrictamente positivo; un booleano no cuenta como entero."""
    valor = bloque.get(clave, defecto)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.{clave}' debe ser un entero "
            f"positivo (un booleano no vale), y es {valor!r}"
        )
    return valor


def _texto_e2e(bloque: dict, clave: str, nombre: str) -> str | None:
    """Texto opcional del bloque. Admite '|': no viaja por la salida --shell."""
    if clave not in bloque:
        return None
    valor = bloque[clave]
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.{clave}' debe ser un texto no "
            f"vacío, y es {valor!r}"
        )
    return valor


def _e2e(entrada: dict, nombre: str, lenguaje: str) -> BloqueE2E | None:
    """El bloque `e2e` validado (R1–R3); `None` si el servicio no lo declara."""
    if "e2e" not in entrada:
        return None
    bloque = entrada["e2e"]
    if not isinstance(bloque, dict):
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e' debe ser un objeto, y es {bloque!r}"
        )
    for clave in bloque:
        if clave not in CLAVES_E2E:
            raise ValueError(
                f"servicio '{nombre}': clave 'e2e.{clave}' desconocida; el bloque "
                f"admite {list(CLAVES_E2E)}"
            )

    url_base = bloque.get("url_base")
    if not isinstance(url_base, str) or not host_de_url(url_base):
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.url_base' es obligatorio y debe "
            f"empezar por http:// o https:// y llevar host, sin barra invertida, "
            f"blancos ni caracteres de control, con el host en ASCII (nada no "
            f"ASCII: un IDN va en forma xn--) y la IP en forma canónica (IPv4 de "
            f"cuatro decimales, IPv6 sin IPv4 embebida), y es {url_base!r}"
        )
    if "rutas_ui" not in bloque or not isinstance(bloque["rutas_ui"], list) or not bloque[
        "rutas_ui"
    ]:
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.rutas_ui' es obligatorio y debe ser "
            f"una lista no vacía de globs, y es {bloque.get('rutas_ui')!r}"
        )
    rutas_ui = _rutas(bloque, "rutas_ui", nombre, base="la ruta del servicio")

    runner = bloque.get("runner", RUNNERS_E2E[0])
    if runner not in RUNNERS_E2E:
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.runner' debe ser uno de "
            f"{list(RUNNERS_E2E)}, y es {runner!r}"
        )
    if runner == "pytest-playwright" and lenguaje != "python":
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.runner' es 'pytest-playwright' (el "
            f"valor por defecto) y el servicio es de lenguaje {lenguaje!r}; declara "
            f"'runner': 'playwright-test'"
        )

    prohibidos = _lista(bloque, "hosts_prohibidos", nombre)
    if any(not isinstance(patron, str) or not patron.strip() for patron in prohibidos):
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.hosts_prohibidos' debe ser una "
            f"lista de textos no vacíos, y es {prohibidos!r}"
        )
    patron = host_prohibido(url_base, tuple(prohibidos))
    if patron is not None:
        raise ValueError(
            f"servicio '{nombre}': el campo 'e2e.url_base' ({url_base}) apunta a un "
            f"host declarado como productivo (casa con '{patron}' de hosts_prohibidos)"
        )

    return BloqueE2E(
        url_base=url_base,
        rutas_ui=rutas_ui,
        runner=runner,
        comando=_texto_e2e(bloque, "comando", nombre),
        arranque=_texto_e2e(bloque, "arranque", nombre),
        ruta_tests=_normalizar(_texto_e2e(bloque, "ruta_tests", nombre) or "tests_e2e"),
        espera_arranque_s=_entero_e2e(
            bloque, "espera_arranque_s", nombre, ESPERA_ARRANQUE_E2E_S),
        timeout_s=_entero_e2e(bloque, "timeout_s", nombre, TIMEOUT_E2E_S),
        hosts_prohibidos=tuple(prohibidos),
    )


def _rechazar_clave_parecida(entrada: dict, nombre: str) -> None:
    """Falla ante una clave que parece una de `CLAVES_VIGILADAS` mal escrita.

    Las claves desconocidas se ignoran desde siempre y así siguen (un proyecto
    instalado puede llevar las suyas). Estas son la excepción porque su fallo
    es MUDO: con `alcance_incluye` mal escrita, el `harness/` del servicio se
    queda sin medir (F-052); con `ejecutar_siempre`, los barridos dejan de
    ejecutarse (F-028). En los dos casos las puertas siguen en verde.
    """
    for clave in entrada:
        if clave in CLAVES_DE_SERVICIO or not isinstance(clave, str):
            continue
        # La mejor va primero: solo se usa esa (pedir n=1 era redundante).
        parecidas = difflib.get_close_matches(clave.lower(), CLAVES_VIGILADAS, cutoff=0.8)
        if parecidas:
            raise ValueError(
                f"servicio '{nombre}': clave {clave!r} desconocida; ¿querías "
                f"decir '{parecidas[0]}'?"
            )


def _servicio_de_entrada(entrada: object) -> Servicio:
    """Convierte una entrada de la declaración en un `Servicio` validado."""
    if not isinstance(entrada, dict):
        raise ValueError(
            f"cada servicio debe ser un objeto JSON con 'nombre', 'ruta' y "
            f"'lenguaje', y hay uno que es {entrada!r}"
        )

    nombre = entrada.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError(f"hay un servicio sin 'nombre' válido: {entrada!r}")

    lenguaje = entrada.get("lenguaje")
    if lenguaje not in LENGUAJES:
        raise ValueError(
            f"servicio '{nombre}': lenguaje {lenguaje!r} desconocido; "
            f"usa uno de {list(LENGUAJES)}"
        )

    _rechazar_clave_parecida(entrada, nombre)
    return Servicio(
        nombre=nombre,
        ruta=_normalizar(str(_texto(entrada, "ruta", nombre, obligatorio=True))),
        lenguaje=lenguaje,
        venv=_texto(entrada, "venv", nombre, obligatorio=False),
        comando_tests=_texto(entrada, "comando_tests", nombre, obligatorio=False),
        depende_de=_rutas(entrada, "depende_de", nombre),
        importa=_modulos(entrada, nombre, lenguaje),
        entradas_no_versionadas=_rutas(entrada, "entradas_no_versionadas", nombre),
        alcance_incluye=_incluidos(entrada, nombre),
        ejecutar_siempre=_siempre(entrada, nombre, lenguaje),
        e2e=_e2e(entrada, nombre, lenguaje),
    )


def _comprobar_conjunto(servicios: list[Servicio], raiz: str) -> None:
    """Valida lo que solo se ve mirando todos los servicios a la vez."""
    vistos_nombre: set[str] = set()
    vistas_ruta: list[str] = []

    for servicio in servicios:
        if servicio.nombre in vistos_nombre:
            raise ValueError(f"nombre duplicado en la declaración: '{servicio.nombre}'")
        vistos_nombre.add(servicio.nombre)

        for anterior in vistas_ruta:
            if anterior == servicio.ruta:
                raise ValueError(
                    f"ruta duplicada en la declaración: '{servicio.ruta}'"
                )
            if anterior.startswith(f"{servicio.ruta}/") or servicio.ruta.startswith(
                f"{anterior}/"
            ):
                raise ValueError(
                    f"la ruta '{servicio.ruta}' se solapa con '{anterior}': un "
                    f"fichero no puede pertenecer a dos servicios"
                )
        vistas_ruta.append(servicio.ruta)

        if not (Path(raiz) / servicio.ruta).is_dir():
            raise ValueError(
                f"servicio '{servicio.nombre}': la ruta '{servicio.ruta}' no existe "
                f"en el repositorio"
            )

        for dependencia in servicio.depende_de:
            if not (Path(raiz) / dependencia).exists():
                raise ValueError(
                    f"servicio '{servicio.nombre}': el campo 'depende_de' tiene "
                    f"'{dependencia}', que no existe en el repositorio (ni como "
                    f"fichero ni como carpeta)"
                )

        for ruta in servicio.ejecutar_siempre:
            if not (Path(raiz) / servicio.ruta / ruta).exists():
                raise ValueError(
                    f"servicio '{servicio.nombre}': el campo 'ejecutar_siempre' "
                    f"tiene '{ruta}', que no existe bajo '{servicio.ruta}'"
                )


def cargar_servicios(
    ruta: Path | str = RUTA_SERVICIOS, raiz: str = "."
) -> list[Servicio]:
    """Carga la declaración de servicios; lista vacía si no hay ninguna.

    `ruta` relativa se resuelve bajo `raiz`, para que una campaña lanzada sobre
    un worktree lea la declaración de ESE árbol y no la del directorio actual.
    """
    fichero = Path(ruta)
    if not fichero.is_absolute():
        fichero = Path(raiz) / fichero
    if not fichero.is_file():
        return []

    try:
        datos = json.loads(fichero.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(
            f"{fichero.as_posix()} no es JSON válido: {error}"
        ) from error

    declarados = datos.get("servicios") if isinstance(datos, dict) else None
    if not isinstance(declarados, list):
        raise ValueError(
            f"{fichero.as_posix()}: falta la lista 'servicios' (un objeto JSON con "
            f"la clave 'servicios')"
        )

    servicios = [_servicio_de_entrada(entrada) for entrada in declarados]
    _comprobar_conjunto(servicios, raiz)
    return servicios


# --- Consultas --------------------------------------------------------------


def servicio_de_ruta(ruta: str, servicios: list[Servicio]) -> Servicio | None:
    """Servicio al que pertenece `ruta`, por prefijo más largo; `None` si a ninguno."""
    normalizada = _normalizar(ruta)
    candidatos = [
        servicio
        for servicio in servicios
        if normalizada == servicio.ruta or normalizada.startswith(f"{servicio.ruta}/")
    ]
    if not candidatos:
        return None
    return max(candidatos, key=lambda servicio: len(servicio.ruta))


def interprete(servicio: Servicio, raiz: str = ".") -> str:
    """Intérprete Python con el que se ejecuta la suite de un servicio.

    Con `venv` declarado, el de ESE entorno, en ruta absoluta y con barras (Git
    Bash no ejecuta rutas con contrabarras). Sin `venv`, el que corre el arnés.
    Un `venv` declarado que no existe es un error: caer al intérprete global
    probaría el servicio con dependencias que no son las suyas.
    """
    if servicio.venv is None:
        return sys.executable

    base = Path(raiz) / servicio.venv
    for relativo in INTERPRETES_DEL_VENV:
        candidato = base / relativo
        if candidato.is_file():
            return candidato.resolve().as_posix()

    raise ValueError(
        f"servicio '{servicio.nombre}': el venv declarado '{servicio.venv}' no "
        f"contiene intérprete ({' ni '.join(INTERPRETES_DEL_VENV)}). No se usa el "
        f"intérprete global en su lugar: probaría con las dependencias equivocadas"
    )


def tiene_tests(servicio: Servicio, raiz: str = ".") -> bool:
    """¿El servicio tiene directorio de tests propio?"""
    return (Path(raiz) / servicio.ruta / "tests").is_dir()


def linea_shell(servicio: Servicio, raiz: str = ".") -> str:
    """Una línea `nombre|ruta|lenguaje|interprete|comando_tests` para `init.sh`.

    El intérprete va **ya resuelto**: el bucle del portero no tiene que adivinar
    dónde vive el ejecutable de un venv en cada sistema operativo. En un
    servicio que no es Python el campo va vacío.
    """
    ruta_interprete = (
        Path(interprete(servicio, raiz)).as_posix()
        if servicio.lenguaje == "python"
        else ""
    )
    return SEPARADOR.join(
        [
            servicio.nombre,
            servicio.ruta,
            servicio.lenguaje,
            ruta_interprete,
            servicio.comando_tests or "",
        ]
    )


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """`--validar` (0 si la declaración es sana) o `--shell` (una línea por servicio)."""
    analizador = argparse.ArgumentParser(
        prog="python -m harness.servicios",
        description="Declaración de servicios del monorepo (opcional).",
    )
    analizador.add_argument("--validar", action="store_true")
    analizador.add_argument(
        "--shell", action="store_true", help="salida parseable: un servicio por línea"
    )
    analizador.add_argument("--ruta", default=str(RUTA_SERVICIOS))
    analizador.add_argument("--raiz", default=".")
    opciones = analizador.parse_args(argv)

    try:
        servicios = cargar_servicios(opciones.ruta, opciones.raiz)
        lineas = [linea_shell(servicio, opciones.raiz) for servicio in servicios]
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    if opciones.shell:
        for linea in lineas:
            print(linea)
        return 0

    if not servicios:
        print("    sin harness/servicios.json: proyecto único en la raíz")
        return 0
    print(
        f"    {len(servicios)} servicio(s): "
        f"{', '.join(f'{s.nombre} ({s.lenguaje})' for s in servicios)}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
