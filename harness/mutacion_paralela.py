# harness/mutacion_paralela.py
"""Campaña de mutación repartida entre varios workers, cada uno en su worktree.

La campaña en serie de `harness.mutacion` ya hace bien lo difícil: aplica un
mutante, lanza la suite del servicio dueño del fichero y restaura con
`try/finally` más una red de seguridad final. Aquí NO se reescribe nada de eso:
el paralelismo se monta por fuera.

1. El coordinador calcula los mutantes UNA vez desde el árbol principal y
   aplica el muestreo UNA vez, antes de repartir.
2. Crea N `git worktree` desechables desde `HEAD`, en el temp del sistema.
3. Lanza N hilos; cada uno llama a `ejecutar_campania` tal cual, con
   `raiz=<su worktree>` y `mutantes=<su partición>`. El trabajo pesado (pytest)
   va en subprocesos, así que el GIL no pinta nada.
4. Fusiona los parciales en un informe idéntico al de la campaña en serie
   salvo la fecha y la fila «Tiempo total».
5. `finally`: retira los worktrees pase lo que pase.

El árbol principal no se muta NUNCA en modo paralelo, y por eso se exige que
esté limpio: los worktrees se crean desde `HEAD` y con cambios sin commitear
evaluarían un código distinto del que se ve en disco.

Limitaciones conocidas del modo paralelo (en serie no aplican, porque la suite
corre sobre el propio árbol):

- **Instalación editable apuntando al árbol principal.** Si el venv de un
  servicio instala su paquete en modo editable contra el árbol principal, la
  suite del worker importaría el código SIN mutar y darían supervivientes
  falsos. Los venvs no se copian al worktree: solo se reutiliza su intérprete.
- **Suites que dependan de ficheros no versionados** (`.env`, datos locales):
  no existen dentro de un worktree. Las convenciones ya prohíben unit tests con
  esas dependencias; un proyecto que las viole verá la suite roja en el worker
  y contará mutantes «muertos» de más.

Todo con biblioteca estándar, como el resto del arnés.
"""

from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import TracebackType

from harness.alcance import Alcance
from harness.mutacion import (
    TIMEOUT_POR_DEFECTO,
    EjecutorPytest,
    InformeMutacion,
    Mutante,
    ejecutar_campania,
    ejecutor_para,
    generar_mutantes,
)
from harness.mutacion import (
    # privado de `harness.mutacion` a sabiendas: la campaña paralela tiene que
    # leer los fuentes EXACTAMENTE igual que la campaña en serie (sin traducir
    # saltos de línea) o los mutantes generados no serían los mismos.
    _leer as _leer_fuente,
)
from harness.servicios import Servicio, interprete, servicio_de_ruta

#: Fábrica de ejecutores: `(fichero, raíz del worker) -> ejecutor`.
Fabrica = Callable[[str, str], object]

#: Clave con la que la campaña en serie ordena sus mutantes. El informe
#: paralelo tiene que salir en ESTE orden para ser indistinguible del suyo.
Clave = tuple[str, int, int, str]


def clave_estable(mutante: Mutante) -> Clave:
    """Identidad ordenable de un mutante: `(fichero, línea, columna, operador)`."""
    return (mutante.fichero, mutante.linea, mutante.col, mutante.operador)


# --- Reparto y fusión (funciones puras) -------------------------------------


def repartir(mutantes: list[Mutante], n: int) -> list[list[Mutante]]:
    """Reparte los mutantes entre `n` workers en round-robin por índice.

    Determinista: las mismas entradas dan siempre las mismas particiones, y su
    unión es exactamente la lista recibida, sin repetidos ni omitidos. El
    round-robin sobre la lista ya ordenada equilibra el coste: mutantes del
    mismo fichero —cuya suite tarda lo mismo— se reparten entre todos.
    """
    cuantos = max(1, n)
    return [mutantes[indice::cuantos] for indice in range(cuantos)]


def fusionar(
    alcance: Alcance,
    parciales: list[InformeMutacion],
    generados: int,
    segundos: float,
    muestreado: bool = False,
    max_mutantes: int | None = None,
    semilla: int | None = None,
) -> InformeMutacion:
    """Funde los informes de los workers en el informe único de la campaña.

    Los totales se suman y las listas se reordenan por la clave estable, de
    forma que el resultado no delata en qué worker cayó cada mutante. Los
    metadatos de muestreo son los del coordinador, que es quien muestreó.
    """
    informe = InformeMutacion(
        feature=alcance.feature,
        alcance=alcance,
        generados=generados,
        muertos=sum(parcial.muertos for parcial in parciales),
        segundos=segundos,
        muestreado=muestreado,
        max_mutantes=max_mutantes,
        semilla=semilla,
    )
    for atributo in ("supervivientes", "timeouts", "mutantes_evaluados"):
        juntos: list[Mutante] = []
        for parcial in parciales:
            juntos.extend(getattr(parcial, atributo))
        setattr(informe, atributo, sorted(juntos, key=clave_estable))
    return informe


# --- Worktrees desechables ---------------------------------------------------


def _git(raiz: str, *args: str) -> tuple[int, str]:
    """Ejecuta git en `raiz` y devuelve `(código de salida, salida completa)`.

    No se usa `harness.alcance.ejecutar_git` a propósito: aquel devuelve cadena
    vacía cuando git falla, y aquí la diferencia entre «no hay cambios» y «git
    ha fallado» decide si se aborta la campaña.
    """
    proceso = subprocess.run(
        ["git", "-C", str(raiz), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proceso.returncode, (proceso.stdout or "") + (proceso.stderr or "")


def arbol_limpio(raiz: str = ".") -> bool:
    """¿El árbol de trabajo está sin cambios pendientes de commitear?

    Un git que falla —no es un repositorio, no está instalado— cuenta como NO
    limpio: la campaña paralela se apoya en `HEAD`, y sin poder comprobarlo lo
    prudente es abortar.
    """
    codigo, salida = _git(raiz, "status", "--porcelain")
    return codigo == 0 and not salida.strip()


class Worktrees:
    """Crea N worktrees desechables desde `HEAD` y garantiza su retirada.

    Se usa como gestor de contexto: `__enter__` devuelve las rutas y `__exit__`
    las retira pase lo que pase (fin normal, excepción o `KeyboardInterrupt`).
    Viven en el temp del sistema, nunca bajo el repositorio: dentro saldrían en
    `git status`, en la recolección de pytest y en el radar del portero, y el
    peor caso imaginable —el proceso matado a machetazos— dejaría basura dentro
    del árbol de trabajo.
    """

    def __init__(self, raiz: str, cuantos: int, etiqueta: str = "mutacion") -> None:
        self.raiz = str(raiz)
        self.cuantos = max(0, cuantos)
        self.etiqueta = etiqueta
        self.rutas: list[str] = []
        self._temporal: str | None = None

    def __enter__(self) -> list[str]:
        # Retira primero los registros huérfanos que dejó una campaña muerta:
        # si no, se acumulan campaña tras campaña en `git worktree list`.
        _git(self.raiz, "worktree", "prune")
        self._temporal = tempfile.mkdtemp(prefix=f"mutacion_{self.etiqueta}_")
        try:
            for indice in range(self.cuantos):
                destino = Path(self._temporal) / f"wk_{indice}"
                codigo, salida = _git(
                    self.raiz, "worktree", "add", "--detach", str(destino), "HEAD"
                )
                if codigo != 0:
                    raise RuntimeError(
                        f"No se pudo crear el worktree {destino.as_posix()}: "
                        f"{salida.strip()}"
                    )
                self.rutas.append(str(destino))
        except BaseException:
            self._retirar()
            raise
        return self.rutas

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        valor: BaseException | None,
        traza: TracebackType | None,
    ) -> bool:
        self._retirar()
        return False  # nunca traga la excepción: solo limpia

    def _retirar(self) -> None:
        """Borra los worktrees creados; lo que no se deje borrar, se desregistra."""
        for ruta in self.rutas:
            codigo, _ = _git(self.raiz, "worktree", "remove", "--force", ruta)
            if codigo != 0:
                # Windows: un proceso rezagado puede tener un fichero abierto.
                # Se borra el directorio y se desregistra después, en ese orden:
                # `prune` solo retira el registro de un worktree que ya no está.
                shutil.rmtree(ruta, ignore_errors=True)
                _git(self.raiz, "worktree", "prune")
        self.rutas = []
        if self._temporal is not None:
            shutil.rmtree(self._temporal, ignore_errors=True)
            self._temporal = None


# --- Piezas del coordinador --------------------------------------------------


def fabrica_de_ejecutores(servicios: list[Servicio], raiz_venvs: str) -> Fabrica:
    """Fábrica que juzga cada fichero con la suite de SU servicio en el worker.

    La suite se ejecuta DENTRO del worktree del worker (ahí está el código
    mutado) y con el intérprete resuelto contra el árbol principal (ahí están
    los venvs, que no se versionan y por tanto no existen en un worktree).
    """

    def fabrica(fichero: str, raiz_worker: str) -> object:
        return ejecutor_para(
            fichero, servicios, raiz=raiz_worker, raiz_venvs=raiz_venvs
        )

    return fabrica


def resolver_interpretes(
    alcance: Alcance, servicios: list[Servicio], raiz: str = "."
) -> dict[str, str]:
    """Resuelve por adelantado el intérprete de cada servicio del alcance.

    Se hace ANTES de crear ningún worktree: un venv declarado que no existe es
    un `ValueError` de `harness.servicios`, y descubrirlo con dieciséis
    checkouts ya en el temp del sistema sería tirar minutos a la basura.
    """
    resueltos: dict[str, str] = {}
    for fichero in alcance.ficheros():
        servicio = servicio_de_ruta(fichero, servicios)
        if servicio is None or servicio.lenguaje != "python":
            continue
        if servicio.nombre not in resueltos:
            resueltos[servicio.nombre] = interprete(servicio, raiz)
    return resueltos


def generar_y_muestrear(
    alcance: Alcance,
    raiz: str = ".",
    max_mutantes: int | None = None,
    semilla: int | None = None,
) -> tuple[list[Mutante], int, bool]:
    """Genera los mutantes del alcance y aplica el muestreo UNA sola vez.

    Devuelve `(mutantes a evaluar, generados, muestreado)`. Reproduce paso por
    paso lo que hace `ejecutar_campania` en serie —mismo orden de ficheros,
    misma lectura sin traducir saltos de línea, mismo `random.Random(semilla)`
    sobre la misma lista— porque de esa igualdad depende que el muestreo elija
    exactamente los mismos mutantes que la campaña en serie.
    """
    base = Path(raiz)
    mutantes: list[Mutante] = []
    for fichero in alcance.ficheros():
        ruta = base / fichero
        if ruta.is_file():
            mutantes.extend(
                generar_mutantes(_leer_fuente(ruta), alcance.lineas[fichero], fichero)
            )

    generados = len(mutantes)
    if max_mutantes is not None and generados > max_mutantes:
        sorteo = random.Random(semilla)
        return (
            sorted(sorteo.sample(mutantes, max_mutantes), key=clave_estable),
            generados,
            True,
        )
    return (mutantes, generados, False)


def renumerar(linea: str, indice: int, total: int) -> str:
    """Cambia el `[i/n]` que numera un worker por el `[i/n]` de la campaña.

    Cada worker numera su propia partición; por pantalla lo que interesa es
    cuánto queda de campaña. El orden de las líneas NO es contractual: el
    informe sí.
    """
    resto = linea.split("] ", 1)[1] if linea.startswith("[") and "] " in linea else linea
    return f"[{indice}/{total}] {resto}"


class _ParticionCancelable:
    """Partición que deja de rendir mutantes en cuanto se pide cancelar.

    Se pasa tal cual como `mutantes=` a `ejecutar_campania`, que solo le pide
    `len()` e iteración. Así la cancelación cooperativa no cuesta ni una línea
    dentro de la campaña en serie, que es la parte delicada del módulo.
    """

    def __init__(self, mutantes: list[Mutante], evento: threading.Event) -> None:
        self._mutantes = mutantes
        self._evento = evento

    def __len__(self) -> int:
        return len(self._mutantes)

    def __iter__(self) -> Iterator[Mutante]:
        for mutante in self._mutantes:
            if self._evento.is_set():
                return
            yield mutante


# --- Coordinador -------------------------------------------------------------


def ejecutar_campania_paralela(
    alcance: Alcance,
    servicios: list[Servicio],
    timeout_s: int = TIMEOUT_POR_DEFECTO,
    raiz: str = ".",
    workers: int = 2,
    max_mutantes: int | None = None,
    semilla: int | None = None,
    eco: Callable[[str], None] | None = None,
    fabrica: Fabrica | None = None,
) -> InformeMutacion:
    """Evalúa los mutantes del alcance repartidos entre varios worktrees.

    Devuelve el mismo `InformeMutacion` que produciría la campaña en serie
    sobre el mismo commit: mismos totales y mismas listas en el mismo orden.
    Solo cambian el reloj y en qué worker cayó cada mutante, que no se cuenta.

    Lanza `ValueError` si el árbol principal tiene cambios sin commitear o si
    un servicio del alcance declara un venv sin intérprete. En ambos casos, sin
    haber creado ningún worktree ni tocado ningún fichero.
    """
    inicio = time.monotonic()
    resolver_interpretes(alcance, servicios, raiz)  # R11: revienta aquí o nunca

    mutantes, generados, muestreado = generar_y_muestrear(
        alcance, raiz, max_mutantes, semilla
    )
    fabrica = fabrica or fabrica_de_ejecutores(servicios, raiz_venvs=raiz)
    efectivo = max(1, min(workers, len(mutantes)))
    total = len(mutantes)

    cerrojo = threading.Lock()
    hechos = 0

    def eco_compartido(linea: str) -> None:
        nonlocal hechos
        if eco is None:
            return
        with cerrojo:
            hechos += 1
            indice = hechos
        eco(renumerar(linea, indice, total))

    def correr(raiz_worker: str, particion: object) -> InformeMutacion:
        return ejecutar_campania(
            alcance,
            EjecutorPytest(raiz=raiz_worker),
            timeout_s=timeout_s,
            raiz=raiz_worker,
            mutantes=particion,  # type: ignore[arg-type]
            eco=eco_compartido if eco is not None else None,
            ejecutor_de=lambda fichero: fabrica(fichero, raiz_worker),
        )

    def informe_final(parciales: list[InformeMutacion]) -> InformeMutacion:
        return fusionar(
            alcance,
            parciales,
            generados=generados,
            segundos=time.monotonic() - inicio,
            muestreado=muestreado,
            max_mutantes=max_mutantes,
            semilla=semilla,
        )

    # R8: con menos de dos mutantes que evaluar, paralelizar solo cuesta. Se
    # muta in situ, como toda la vida, y no se crea ni un worktree.
    if efectivo < 2:
        parciales = [correr(raiz, mutantes)] if mutantes else []
        return informe_final(parciales)

    if not arbol_limpio(raiz):
        raise ValueError(
            "El árbol principal tiene cambios sin commitear y la campaña "
            "paralela crea sus worktrees desde HEAD: evaluaría un código "
            "distinto del que ves en disco. Commitea los cambios o lanza la "
            "campaña con --workers 1."
        )

    particiones = repartir(mutantes, efectivo)
    resultados: list[InformeMutacion | None] = [None] * efectivo
    fallos: list[BaseException] = []
    evento = threading.Event()

    def trabajo(indice: int, raiz_worker: str) -> None:
        particion = _ParticionCancelable(particiones[indice], evento)
        try:
            resultados[indice] = correr(raiz_worker, particion)
        except BaseException as error:  # noqa: BLE001  (se relanza en el hilo principal)
            # Un worker reventado cancela a los demás: seguir gastando minutos
            # para dar después un informe incompleto sería lo peor de ambos.
            evento.set()
            with cerrojo:
                fallos.append(error)

    with Worktrees(raiz, efectivo, etiqueta=alcance.feature) as rutas:
        hilos = [
            threading.Thread(
                target=trabajo, args=(indice, ruta), name=f"mutacion-{indice}"
            )
            for indice, ruta in enumerate(rutas)
        ]
        for hilo in hilos:
            hilo.start()
        try:
            for hilo in hilos:
                hilo.join()
        except KeyboardInterrupt:
            # Los workers dejan de coger mutantes; el que tenga una suite en
            # vuelo la termina o agota su timeout. La limpieza la garantiza el
            # `with` de Worktrees, pase lo que pase.
            evento.set()
            for hilo in hilos:
                hilo.join()
            raise

    if fallos:
        raise fallos[0]

    return informe_final([parcial for parcial in resultados if parcial is not None])
