# harness/alcance.py
"""Alcance de una feature: qué líneas de código de producción toca.

El alcance NO se mantiene a mano: sale del diff de git entre la base de
integración y la rama de la feature (o, si la rama ya no existe, entre el
primer padre de su commit de merge y el propio merge).

Lo usan por igual la campaña de mutación (`harness.mutacion`) y la puerta de
cobertura (`harness.cobertura`): una sola fuente de verdad para el «qué
cambió».
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from harness.servicios import Servicio, cargar_servicios, servicio_de_ruta

#: Directorios cuyo contenido nunca es código de producción mutable. Se
#: comparan como SEGMENTO de ruta a cualquier profundidad, no como prefijo de
#: la raíz: en un repositorio con servicios en subcarpetas, los tests de un
#: servicio son tests igual que los de la raíz.
#:
#: `harness` está aquí por la misma razón que `tests`: es utillaje, no producto.
#: Sin excluirlo, tocar el arnés desde la rama de una feature mete sus propias
#: líneas en el alcance, y entonces la campaña **se muta a sí misma** y la
#: puerta de cobertura mide la herramienta en vez de lo que la herramienta
#: vigila.
#:
#: La excepción la declara el propio proyecto, servicio a servicio, con
#: `"alcance_incluye": ["harness"]` en `harness/servicios.json` (F-052): en el
#: repositorio que fabrica el arnés, `<payload>/harness/` es el producto. Ver
#: `excluidos_de_ruta`.
DIRECTORIOS_EXCLUIDOS: tuple[str, ...] = (
    "tests",
    "specs",
    "progress",
    "docs",
    "harness",
)

#: Exclusiones que aplican cuando el alcance lo DECLARA una persona con
#: `--ficheros`. `harness` NO está, a propósito: la exclusión de arriba protege
#: el alcance AUTOMÁTICO —el que sale del diff, que nadie eligió y que arrastra
#: el arnés sin querer en cuanto una rama lo toca—, y aquí no hay nada de lo que
#: proteger a quien escribe la lista. Medir si la maquinaria del arnés está
#: protegida por sus tests es, literalmente, la razón por la que `--ficheros`
#: existe (ver `alcance_de_ficheros`), y en el repositorio del propio arnés esa
#: maquinaria es el producto, no el utillaje.
DIRECTORIOS_EXCLUIDOS_AL_DECLARAR: tuple[str, ...] = (
    "tests",
    "specs",
    "progress",
    "docs",
)

#: Ruta por defecto del inventario de features del arnés.
RUTA_FEATURES = "harness/features.json"

_CABECERA_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

EjecutorGit = Callable[[list[str]], str]


# --- Ejecución de git -------------------------------------------------------


def ejecutar_git(args: list[str], raiz: str = ".") -> str:
    """Ejecuta `git` en `raiz` y devuelve su salida estándar.

    Un código de salida distinto de cero devuelve cadena vacía: quien llama
    decide qué significa (por ejemplo, que una rama no existe).
    """
    proceso = subprocess.run(
        ["git", "-C", raiz, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proceso.returncode != 0:
        return ""
    return proceso.stdout or ""


def git_en(raiz: str = ".") -> EjecutorGit:
    """Devuelve un ejecutor de git atado a un directorio de trabajo."""

    def _git(args: list[str]) -> str:
        return ejecutar_git(args, raiz=raiz)

    return _git


# --- Parseo del diff --------------------------------------------------------


def parsear_diff(texto: str) -> dict[str, set[int]]:
    """Extrae del diff unificado las líneas añadidas o cambiadas por fichero.

    Función pura: no toca git ni el disco. Las líneas se numeran sobre la
    versión NUEVA del fichero, que es la que se va a mutar o medir. Un fichero
    nuevo entra entero (todas sus líneas son añadidas). Un fichero borrado no
    entra: ya no hay nada que mutar.
    """
    resultado: dict[str, set[int]] = {}
    ruta: str | None = None
    numero = 0

    for linea in texto.splitlines():
        if linea.startswith("+++ "):
            destino = linea[4:].strip()
            if destino == "/dev/null":
                ruta = None
            else:
                ruta = destino[2:] if destino.startswith(("a/", "b/")) else destino
                resultado.setdefault(ruta, set())
            continue
        if linea.startswith("--- "):
            continue
        if linea.startswith("@@"):
            coincidencia = _CABECERA_HUNK.match(linea)
            numero = int(coincidencia.group(1)) if coincidencia else 0
            continue
        if ruta is None or numero == 0:
            continue
        if linea.startswith("\\"):  # "\ No newline at end of file"
            continue
        if linea.startswith("+"):
            resultado[ruta].add(numero)
            numero += 1
        elif linea.startswith("-"):
            continue  # línea eliminada: no avanza la numeración del fichero nuevo
        else:  # línea de contexto (o ruido entre ficheros, que el próximo @@ corrige)
            numero += 1

    return {ruta: lineas for ruta, lineas in resultado.items() if lineas}


def es_produccion(
    ruta: str, excluidos: tuple[str, ...] = DIRECTORIOS_EXCLUIDOS
) -> bool:
    """¿Es `ruta` código de producción susceptible de mutarse o medirse?

    Solo Python, y con ningún directorio excluido en su camino: basta con que
    uno de `excluidos` aparezca como un segmento completo, esté en la raíz o
    dentro de un servicio del monorepo. El nombre del propio fichero no cuenta
    (`app/docs.py` es código), ni vale como prefijo (`harnesses/util.py` también
    lo es).

    `excluidos` se pasa a mano en un solo sitio: el alcance declarado con
    `--ficheros`, que sí puede nombrar el arnés. Ver
    `DIRECTORIOS_EXCLUIDOS_AL_DECLARAR`.
    """
    normalizada = ruta.replace("\\", "/")
    if not normalizada.endswith(".py"):
        return False
    directorios = normalizada.split("/")[:-1]
    return not any(nombre in excluidos for nombre in directorios)


def excluidos_de_ruta(
    ruta: str, servicios: Sequence[Servicio] = ()
) -> tuple[str, ...]:
    """Exclusiones del alcance automático que aplican a `ruta` (F-052).

    Las de siempre, menos lo que declare en `alcance_incluye` el servicio al
    que pertenece la ruta. La pertenencia es por SEGMENTOS, la misma de
    `servicio_de_ruta`: `arnes-base-x/harness/a.py` no cae bajo `arnes-base`.
    Sin servicios, o con servicios que no declaran nada, el resultado es
    exactamente `DIRECTORIOS_EXCLUIDOS`.
    """
    servicio = servicio_de_ruta(ruta, list(servicios))
    if servicio is None or not servicio.alcance_incluye:
        return DIRECTORIOS_EXCLUIDOS
    return tuple(
        nombre
        for nombre in DIRECTORIOS_EXCLUIDOS
        if nombre not in servicio.alcance_incluye
    )


def filtrar_produccion(
    lineas: dict[str, set[int]], servicios: Sequence[Servicio] = ()
) -> dict[str, set[int]]:
    """Deja solo los ficheros de producción del mapa de líneas.

    `servicios` es la declaración de `harness/servicios.json`: solo cambia algo
    si algún servicio declara `alcance_incluye` (ver `excluidos_de_ruta`).
    """
    return {
        ruta: nums
        for ruta, nums in lineas.items()
        if es_produccion(ruta, excluidos_de_ruta(ruta, servicios))
    }


# --- Resolución de referencias ----------------------------------------------

#: Base que se usaba antes de que existiera `RAMA_BASE` en `harness/init.sh`.
#: Solo es el último recurso: la base de verdad la declara cada proyecto.
RAMA_BASE_POR_DEFECTO = "dev"

#: Ramas de larga vida que se vigilan al diagnosticar la base (1.7.14): si los
#: commits que la puerta mediría ya viven en alguna de ellas, no son de la
#: rama, y la base se ha quedado por detrás de donde se integra el trabajo.
RAMAS_DE_LARGA_VIDA: tuple[str, ...] = ("main", "master", "dev", "develop")

_RAMA_BASE_EN_INIT = re.compile(
    r"""^[ \t]*RAMA_BASE=(["']?)([^"'\s#]+)\1""", re.MULTILINE
)


def rama_base_configurada(raiz: str = ".") -> str:
    """La rama de integración que declara `RAMA_BASE` en `harness/init.sh`.

    Es la ÚNICA fuente de verdad de la base: el portero la pasa con `--base` a
    las puertas, y las herramientas que se lanzan a mano (`harness.mutacion`,
    `harness.cobertura`, `harness.rutas_sensibles`) la leen de aquí cuando no
    se les pasa. Antes cada una traía `dev` cableado, y en un repositorio que
    integra en `main` eso medía semanas de trabajo ajeno sin avisar (1.7.14).
    Sin `init.sh` o sin la variable, `RAMA_BASE_POR_DEFECTO`.
    """
    guion = Path(raiz) / "harness" / "init.sh"
    try:
        texto = guion.read_text(encoding="utf-8")
    except OSError:
        return RAMA_BASE_POR_DEFECTO
    coincidencia = _RAMA_BASE_EN_INIT.search(texto)
    return coincidencia.group(2) if coincidencia else RAMA_BASE_POR_DEFECTO


def _existe(ref: str, git: EjecutorGit) -> bool:
    return bool(git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]).strip())


def _contar(git: EjecutorGit, refs: list[str]) -> int:
    salida = git(["rev-list", "--count", "--no-merges", *refs]).strip()
    return int(salida) if salida.isdigit() else 0


def diagnosticar_base(
    base: str,
    rama: str,
    git: EjecutorGit | None = None,
    vigiladas: tuple[str, ...] = RAMAS_DE_LARGA_VIDA,
) -> str | None:
    """¿Mediría la puerta, contra `base`, commits que no son de `rama`?

    Devuelve `None` si la base es sana y, si no, el motivo listo para imprimir.
    La puerta calcula el diff desde el merge-base de `rama` con `base`: si
    alguno de esos commits ya vive en otra rama de larga vida, es trabajo ajeno
    que la puerta atribuiría a la feature. Es exactamente lo que pasaba con
    `dev` parada y el trabajo integrándose en `main` (1.7.14): la cobertura
    «de la feature» era la de semanas de features cerradas, y dos features
    distintas daban la misma cifra.

    Solo cuenta commits que no son merges: un merge de integración no aporta
    líneas propias, y en un flujo con `main` ← `dev` el merge de release no
    debe dar un falso rojo. Fuera de un repositorio git no diagnostica nada
    (las puertas ya declaran su N/A por su lado); una base que no existe SÍ es
    un problema: sin ella el diff sale vacío y la puerta aprobaría en silencio.
    """
    git = git or git_en()
    if not git(["rev-parse", "--git-dir"]).strip():
        return None
    if not _existe(base, git):
        return (
            f"la rama base «{base}» no existe en este repositorio: no se puede "
            "calcular qué cambió la feature. Revisa RAMA_BASE en harness/init.sh"
        )

    propios = _contar(git, [rama, f"^{base}"])
    ajenos: list[str] = []
    for otra in vigiladas:
        if otra in (base, rama) or not _existe(otra, git):
            continue
        repetidos = propios - _contar(git, [rama, f"^{base}", f"^{otra}"])
        if repetidos > 0:
            ajenos.append(f"{repetidos} de los {propios} ya están en «{otra}»")
    if not ajenos:
        return None
    return (
        f"la base «{base}» se ha quedado por detrás: de los commits que se "
        f"medirían desde su merge-base con {rama}, {'; '.join(ajenos)} y no son "
        "de esta rama. Pon en RAMA_BASE (harness/init.sh) la rama donde se "
        "integra el trabajo"
    )


def merge_que_integra(rama: str, base: str, git: EjecutorGit | None = None) -> str | None:
    """El commit de merge de `base` que integró `rama`, o `None`.

    Recorre la línea principal de `base` (primer padre) desde lo más antiguo y
    se queda con el primer merge que contiene la punta de `rama` y cuyo primer
    padre no la contenía. Una rama recién creada, sin commits propios, está
    sobre la línea principal: ningún merge la «trae» y la respuesta es `None`.
    """
    git = git or git_en()
    punta = git(["rev-parse", "--verify", "--quiet", rama]).strip()
    if not punta:
        return None
    candidatos = git(
        ["rev-list", "--first-parent", "--merges", "--reverse", f"{rama}..{base}"]
    ).split()
    for merge in candidatos:
        if git(["merge-base", rama, merge]).strip() != punta:
            continue
        if git(["merge-base", rama, f"{merge}^1"]).strip() == punta:
            continue
        return merge
    return None



def resolver_refs(
    feature_id: str,
    rama: str | None,
    base: str = "dev",
    git: EjecutorGit | None = None,
) -> tuple[str, str, str]:
    """Decide entre qué dos referencias se calcula el diff de la feature.

    Orden: (1) la rama existe → base común con `base` frente a la rama, salvo
    que la rama ya esté integrada en `base`: entonces el merge que la integró,
    del primer padre al propio merge; (2) la rama ya no existe → commit de
    merge localizado por su mensaje, y el diff va del primer padre al propio
    merge; (3) ni una cosa ni otra → `SystemExit` explícito, sin mutar ni medir
    nada.

    Devuelve `(ref_a, ref_b, origen)` con `origen` en {"rama", "merge"}.
    """
    git = git or git_en()

    punta = git(["rev-parse", "--verify", "--quiet", rama]).strip() if rama else ""
    if rama and punta:
        base_comun = git(["merge-base", base, rama]).strip() or base
        if base_comun == punta:
            # La rama entera ya está dentro de la base: o se integró, o aún no
            # tiene commits propios. En el primer caso el diff base..rama sale
            # VACÍO y la feature parecería no haber tocado nada; lo que cambió
            # es lo que trajo el merge que la integró (1.7.14).
            merge = merge_que_integra(rama, base, git=git)
            if merge:
                return (f"{merge}^1", merge, "merge")
        return (base_comun, rama, "rama")

    merge = git(
        ["log", "--merges", "--grep", feature_id, "-n", "1", "--format=%H", base]
    ).strip()
    if merge:
        return (f"{merge}^1", merge, "merge")

    raise SystemExit(
        f"No se puede calcular el alcance de {feature_id}: no existe la rama "
        f"{rama or '(sin declarar)'} ni un commit de merge que la mencione en "
        f"{base}. Abortado sin tocar nada."
    )


def rama_de_feature(feature_id: str, ruta_features: str = RUTA_FEATURES) -> str | None:
    """Lee del inventario del arnés la rama declarada para una feature."""
    fichero = Path(ruta_features)
    if not fichero.is_file():
        return None
    try:
        datos = json.loads(fichero.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for feature in datos.get("features", []):
        if feature.get("id") == feature_id:
            return feature.get("branch")
    return None


# --- Alcance ----------------------------------------------------------------


@dataclass
class Alcance:
    """Líneas de producción que toca una feature."""

    feature: str
    origen: str
    ref_diff: tuple[str, str]
    lineas: dict[str, set[int]] = field(default_factory=dict)

    def ficheros(self) -> list[str]:
        return sorted(self.lineas)

    def total_lineas(self) -> int:
        return sum(len(nums) for nums in self.lineas.values())

    def descripcion(self) -> str:
        return (
            f"{self.feature}: {len(self.lineas)} fichero(s), "
            f"{self.total_lineas()} línea(s) de producción "
            f"(origen {self.origen}, {self.ref_diff[0]}..{self.ref_diff[1]})"
        )


#: Primera referencia del `ref_diff` de un alcance declarado a mano: no hay
#: diff detrás, y decirlo es más honesto que inventar una base de comparación.
SIN_DIFF = "(sin diff)"

#: Valor de `Alcance.origen` cuando el alcance no sale de un diff sino de la
#: orden. Lo mira el informe para no imprimir dos refs que no comparan nada.
ORIGEN_FICHEROS = "ficheros"


def alcance_de_ficheros(rutas: list[str], feature_id: str, raiz: str = ".") -> Alcance:
    """Alcance declarado a mano: los ficheros indicados, ENTEROS.

    Existe porque hay campañas cuyo sujeto no es «lo que cambió» sino un módulo
    entero —medir si la maquinaria del arnés está protegida por sus tests, por
    ejemplo—, y para eso no hay diff que sirva: el de la rama numeraría líneas
    ajenas y el de la feature original apunta a un código que ya no existe.

    `origen="ficheros"` y `ref_diff=(SIN_DIFF, <sha de HEAD>)`, para que el
    informe pueda decir contra qué commit se midió. Aborta con `SystemExit` —sin
    tocar nada— si una ruta no existe, si `es_produccion` la rechaza —mutar lo
    que no es código de producción da supervivientes que no significan nada— o
    si, ya filtradas las entradas en blanco, no queda ni un fichero que mutar.
    """
    base = Path(raiz)
    lineas: dict[str, set[int]] = {}
    for ruta in rutas:
        normalizada = ruta.replace("\\", "/").strip()
        if not normalizada:
            continue
        fichero = base / normalizada
        if not fichero.is_file():
            raise SystemExit(
                f"--ficheros: {normalizada} no existe en {base.as_posix()}. "
                "Abortado sin tocar nada."
            )
        if not es_produccion(normalizada, DIRECTORIOS_EXCLUIDOS_AL_DECLARAR):
            raise SystemExit(
                f"--ficheros: {normalizada} no es código de producción "
                "(solo .py fuera de "
                f"{', '.join(DIRECTORIOS_EXCLUIDOS_AL_DECLARAR)}). "
                "Abortado sin tocar nada."
            )
        total = len(fichero.read_text(encoding="utf-8").splitlines())
        lineas[normalizada] = set(range(1, total + 1))

    # DESPUÉS del filtrado, no antes: desde el CLI la lista nunca llega vacía
    # —`split(",")` devuelve siempre al menos un elemento— y las entradas en
    # blanco se descartan una a una, así que `--ficheros ","` se colaba hasta
    # el final y escribía un informe de CERO mutantes. Una campaña vacía que
    # sale con éxito es peor que un aborto: se lee como «nada que mutar, todo
    # bien». Lo que importa no es cómo venga la lista, sino que quede algo.
    if not lineas:
        raise SystemExit(
            "--ficheros no deja ninguna ruta que mutar "
            f"({rutas!r}): no hay nada que medir. Abortado sin tocar nada."
        )

    sha = ejecutar_git(["rev-parse", "HEAD"], raiz=raiz).strip()
    return Alcance(
        feature=feature_id,
        origen=ORIGEN_FICHEROS,
        ref_diff=(SIN_DIFF, sha),
        lineas=lineas,
    )


def alcance_de_feature(
    feature_id: str,
    base: str = "dev",
    rama: str | None = None,
    raiz: str = ".",
    git: EjecutorGit | None = None,
    servicios: Sequence[Servicio] | None = None,
) -> Alcance:
    """Calcula el alcance de una feature desde el diff de git.

    `servicios`: la declaración ya cargada por quien llama (la puerta de
    cobertura y la campaña la necesitan igualmente); sin ella se lee la de
    `raiz`, y una declaración rota lanza `ValueError` como en `cargar_servicios`.
    """
    git = git or git_en(raiz)
    if servicios is None:
        servicios = cargar_servicios(raiz=raiz)
    if rama is None:
        rama = rama_de_feature(feature_id, str(Path(raiz) / RUTA_FEATURES))

    ref_a, ref_b, origen = resolver_refs(feature_id, rama, base, git=git)
    texto = git(["diff", ref_a, ref_b])
    return Alcance(
        feature=feature_id,
        origen=origen,
        ref_diff=(ref_a, ref_b),
        lineas=filtrar_produccion(parsear_diff(texto), servicios),
    )
