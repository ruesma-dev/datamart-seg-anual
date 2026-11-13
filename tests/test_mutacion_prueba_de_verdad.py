# tests/test_mutacion_prueba_de_verdad.py
"""La prueba de verdad: reproducir el defecto, no describirlo.

`test_mutacion_linea_base.py` comprueba el MENSAJE de aborto con dobles de
test. Eso no basta, y la razón está escrita en el propio encargo: hasta la
1.5.2 la limitación estaba **documentada** en la docstring de
`harness/mutacion_paralela.py` y nada la comprobaba. Un aviso en un docstring
no es una salvaguarda; un test con un doble tampoco demuestra que el escenario
real acabe donde se cree.

Aquí se monta un repositorio git de juguete, con su suite de verdad y pytest de
verdad, y se mide la MISMA campaña con el comportamiento de antes y con el de
ahora. Dos escenarios, los dos vistos en producción:

A · **Paralelo, fichero no versionado** (datamart-seg-anual, 2026-08-19). Un
   test depende de un fichero que `.gitignore` excluye. Dentro del `git
   worktree` que crea cada worker ese fichero no existe, la suite arranca roja
   y TODO mutante sale «muerto».

B · **Serie, recolección rota** (albaranes, 2026-08-19). Un fichero que no
   pertenece a ningún servicio lo juzga `ejecutor_para` con `python -m pytest`
   **sin ruta**; sin configuración de pytest en la raíz, esa invocación recoge
   lo que no debe y revienta en la recolección haga lo que haga el mutante.
   Exit 2, que hasta la 1.5.2 se contaba como MUERTO. Este escenario NO
   necesita worktrees: afecta también a las campañas en serie, y por eso el
   alcance del daño es mayor de lo que decía el encargo.

C · **Bytecode rancio** (descubierto AQUÍ, montando este fichero: el escenario
   A daba 3 supervivientes o 2 según el segundo en que cayera). CPython
   reutiliza un `.pyc` cuando el fuente conserva tamaño y mtime en segundos
   enteros, y dos mutantes consecutivos del mismo fichero cumplen las dos cosas
   con facilidad. El segundo se juzga con el bytecode del primero.

Los escenarios se miden por partida doble: CONTROL (lo que la campaña debería
decir), ANTES (lo que decía la 1.5.2) y DESPUÉS (lo que dice la 1.6.0). La
comparación es la evidencia; sin ella no se puede afirmar que esté arreglado.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from harness import mutacion_paralela
from harness.alcance import Alcance
from harness.mutacion import (
    MUERTO,
    NO_COMPILA,
    PYTEST_OK,
    PYTEST_SIN_TESTS,
    SUPERVIVIENTE,
    TIMEOUT,
    BaseRota,
    EjecutorPytest,
    InformeMutacion,
    Mutante,
    _escribir,
    _leer,
    clave_de_orden,
    ejecutar_campania,
    escribir_informe,
    generar_mutantes,
    lineas_comparables,
)
from harness.mutacion_paralela import ejecutar_campania_paralela

#: Peor tiempo MEDIDO de un pytest anidado de este fichero (F-038,
#: 2026-10-18, 22 núcleos): 64,3 s para el de `test_C_regresion...` con 44
#: procesos de CPU al 100 %, es decir, con la máquina sobresuscrita al doble.
#: En reposo ese mismo anidado tarda ~1 s y la suite de juguete ~0,7 s; con
#: seis suites completas a la vez, 3 y 2 s. La latencia no crece en
#: proporción a la carga: se dispara en cuanto hay más procesos que núcleos.
#: Si esta máquina es mucho más lenta que aquella, se vuelve a medir y se
#: cambia ESTE número, no el timeout a ojo.
PEOR_ANIDADO_MEDIDO_S = 64.3

#: Margen sobre ese peor caso. El reloj de estos tests NO mide rendimiento:
#: solo existe para que un cuelgue de verdad acabe como timeout en vez de
#: colgar la suite real. Por eso el margen es ancho a propósito: ×4 deja sitio
#: a una carga bastante mayor que la medida, y el precio —lo que tarda en
#: aflorar un cuelgue real— se queda por debajo de cinco minutos. El 90 fijo
#: de antes quedaba a solo 1,4× del peor caso medido y daba rojos falsos.
MARGEN_CUELGUE = 4

#: Segundos por mutante y por pytest anidado, derivados de lo medido.
TIMEOUT_S = math.ceil(PEOR_ANIDADO_MEDIDO_S * MARGEN_CUELGUE)

#: Código bajo mutación. `descuento` la cubren los tests; `etiqueta` no la
#: cubre nadie, a propósito: sus mutantes SOBREVIVEN, y ese superviviente es lo
#: que el defecto hacía desaparecer.
APP = '''# app.py
def descuento(importe, ratio):
    if importe > 100:
        return importe * ratio
    return importe


def etiqueta(cantidad):
    if cantidad > 5:
        return "muchos"
    return "pocos"
'''

#: Suite que depende de un fichero NO versionado, como el `.env` de un
#: proyecto real. En el árbol principal existe; dentro de un worktree, no.
TEST_APP = '''# test_app.py
from pathlib import Path

import app

RAIZ = Path(__file__).resolve().parent


def test_hay_datos_locales():
    assert (RAIZ / "datos.local").is_file()


def test_descuento_aplica_el_ratio_por_encima_del_umbral():
    assert app.descuento(200, 0.5) == 100.0


def test_por_debajo_del_umbral_no_hay_descuento():
    assert app.descuento(100, 0.5) == 100
'''

#: Fichero de test que ni siquiera se puede recoger: pytest sale con código 2
#: sin ejecutar nada. Es el escenario B en su forma mínima.
TEST_IRRECOLECTABLE = '''# tests/test_irrecolectable.py
import modulo_que_no_existe  # noqa: F401


def test_nunca_llega_a_correr():
    assert True
'''

#: Líneas de `app.py` que entran en el alcance de la campaña: las cuatro que
#: contienen operadores mutables.
LINEAS_EN_ALCANCE = {3, 4, 8, 9}

#: Mutantes de esas líneas: 5 hasta F-026; 7 desde que cada `if` da también su
#: `negacion` (`if not (importe > 100):`, `if not (cantidad > 5):`).
GENERADOS_APP = 7


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


def _repositorio(destino: Path, con_suite_rota: bool = False) -> Path:
    """Repositorio de juguete: código, suite, `.gitignore` y un commit."""
    destino.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "dev", str(destino)], check=True, capture_output=True
    )
    _git(destino, "config", "user.email", "arnes@ruesma.es")
    _git(destino, "config", "user.name", "Arnes")

    (destino / "app.py").write_text(APP, encoding="utf-8", newline="")
    (destino / "test_app.py").write_text(TEST_APP, encoding="utf-8", newline="")
    # El fichero del que depende un test queda FUERA de git, igual que un
    # `.env`. Ignorado, además, para que el árbol se vea limpio: si saliera
    # como `??`, la campaña paralela abortaría por otro motivo y el escenario
    # que se quiere reproducir no llegaría a darse.
    (destino / ".gitignore").write_text("datos.local\n", encoding="utf-8")
    if con_suite_rota:
        (destino / "tests").mkdir()
        (destino / "tests" / "test_irrecolectable.py").write_text(
            TEST_IRRECOLECTABLE, encoding="utf-8"
        )
    _git(destino, "add", "-A")
    _git(destino, "commit", "-q", "-m", "inicial")

    (destino / "datos.local").write_text("dato local\n", encoding="utf-8")
    return destino


def _alcance() -> Alcance:
    return Alcance(
        feature="F-999",
        origen="rama",
        ref_diff=("dev", "feature/F-999-juguete"),
        lineas={"app.py": set(LINEAS_EN_ALCANCE)},
    )


@contextmanager
def arnes_1_5_2() -> Iterator[None]:
    """Devuelve el mutador al comportamiento de la 1.5.2, para medir el ANTES.

    Deshace exactamente lo que la 1.6.0 añade en este camino y nada más:

    1. el veredicto vuelve a ser binario —cualquier suite que no acabe en
       verde es un mutante muerto, sin preguntarse por qué—;
    2. la campaña deja de correr la línea base.

    Hace falta porque el código de hoy **se niega** a producir el número falso:
    sin volver atrás no hay ANTES con el que comparar, y una comparación contra
    un recuerdo no es una comparación.
    """
    ejecutar_original = EjecutorPytest.ejecutar
    campania_original = mutacion_paralela.ejecutar_campania

    def ejecutar_binario(self: EjecutorPytest, timeout_s: int) -> str:
        resultado = self.correr(timeout_s)
        if resultado.expirado:
            return TIMEOUT
        if resultado.codigo in (PYTEST_OK, PYTEST_SIN_TESTS):
            return SUPERVIVIENTE
        return MUERTO

    def campania_sin_linea_base(*args: object, **kwargs: object) -> object:
        kwargs["comprobar_base"] = False
        return campania_original(*args, **kwargs)  # type: ignore[arg-type]

    def juzgar_binario(self: EjecutorPytest, timeout_s: int) -> tuple[str, str]:
        # F-023: la campaña pregunta a `juzgar`, no a `ejecutar`. Sin parchear
        # también éste, el ANTES mediría el criterio de hoy.
        return (ejecutar_binario(self, timeout_s), "n/d")

    juzgar_original = EjecutorPytest.juzgar
    EjecutorPytest.ejecutar = ejecutar_binario  # type: ignore[method-assign]
    EjecutorPytest.juzgar = juzgar_binario  # type: ignore[method-assign]
    mutacion_paralela.ejecutar_campania = campania_sin_linea_base  # type: ignore[assignment]
    try:
        yield
    finally:
        EjecutorPytest.ejecutar = ejecutar_original  # type: ignore[method-assign]
        EjecutorPytest.juzgar = juzgar_original  # type: ignore[method-assign]
        mutacion_paralela.ejecutar_campania = campania_original  # type: ignore[assignment]


def _entorno_que_escribe_bytecode() -> dict[str, str]:
    """Entorno para los subprocesos que TIENEN que dejar `.pyc` en disco.

    El escenario C necesita que el intérprete hijo escriba bytecode; si no lo
    escribe, no hay `.pyc` rancio que reutilizar y el test no prueba nada. Y
    quién lo escribe no lo decide el test: lo decide **quien invoca a pytest**,
    porque `PYTHONDONTWRITEBYTECODE` se hereda.

    Eso reventó el 2026-08-26 en `datamart-seg-anual` de la peor manera
    posible: la campaña de mutación lanza cada evaluación con
    `PYTHONDONTWRITEBYTECODE=1` —es el arreglo de la 1.6.3, el que evita
    envenenar el árbol—, y la línea base que mide antes de mutar corre la suite
    del proyecto, este test incluido. Resultado: línea base SIEMPRE en rojo y
    campaña abortada sin informe. El test que vigila el bytecode no sobrevivía
    a la propia campaña del arnés.

    Por eso el entorno del hijo se construye aquí y no se hereda tal cual: se
    parte de `os.environ` —el subproceso necesita `PATH` y compañía— y se
    quitan las dos variables que deciden dónde y si se escribe bytecode.
    Quitarlas es lo contrario de debilitar el test: es lo que garantiza que
    haya `.pyc` que comprobar en cualquier entorno.
    """
    entorno = dict(os.environ)
    entorno.pop("PYTHONDONTWRITEBYTECODE", None)
    # Si apunta a otro árbol, el `__pycache__` no aparece junto al fuente y el
    # `glob` sale vacío igual que con la anterior.
    entorno.pop("PYTHONPYCACHEPREFIX", None)
    return entorno


def _sin_mutar(repositorio: Path) -> None:
    """El árbol quedó como estaba: ni un mutante escrito en disco."""
    assert _leer(repositorio / "app.py") == APP, (
        "la campaña dejó app.py MUTADO: es el defecto que arregla la pieza 3"
    )


# --- Timeout frente a rojo (F-038) ------------------------------------------
#
# Un pytest anidado puede acabar mal de dos formas que no se parecen en nada:
# ROJO (terminó y algo falla: hay que leer su salida) o TIMEOUT (no terminó a
# tiempo: con la máquina cargada, casi siempre es la máquina). Antes las dos
# llegaban igual de mal: un `TimeoutExpired` a pelo o, en las campañas, un
# `assert 3 == 5` que parecía un rojo de la campaña y no lo era.


@dataclass(frozen=True)
class Anidado:
    """Lo que devolvió un pytest anidado, con el reloj que se le concedió."""

    codigo: int | None
    salida: str
    timeout_s: int

    @property
    def expirado(self) -> bool:
        return self.codigo is None

    def diagnostico(self) -> str | None:
        """`None` si acabó en verde; si no, un mensaje que empieza por la
        palabra que importa: `TIMEOUT` o `ROJO`."""
        if self.expirado:
            return (
                f"TIMEOUT tras {self.timeout_s} s: el pytest anidado no terminó. "
                "No es un rojo: no llegó a dar veredicto. Casi siempre es la "
                "máquina sobresuscrita (ver PEOR_ANIDADO_MEDIDO_S); si se "
                "repite en reposo, algo se cuelga.\n"
                f"Salida parcial:\n{self.salida}"
            )
        if self.codigo != 0:
            return f"ROJO (código {self.codigo}):\n{self.salida}"
        return None


def correr_anidado(
    orden: list[str], cwd: Path, env: dict[str, str], timeout_s: int
) -> Anidado:
    """Lanza un subproceso con reloj y lo traduce a `Anidado`, sin juzgarlo."""
    try:
        completado = subprocess.run(
            orden,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,  # el veredicto lo da quien llama, con el diagnóstico
        )
    except subprocess.TimeoutExpired as expirado:
        parcial = [
            texto.decode("utf-8", "replace") if isinstance(texto, bytes) else texto
            for texto in (expirado.stdout, expirado.stderr)
            if texto
        ]
        return Anidado(codigo=None, salida="\n".join(parcial), timeout_s=timeout_s)
    return Anidado(
        codigo=completado.returncode,
        salida=f"{completado.stdout}\n{completado.stderr}",
        timeout_s=timeout_s,
    )


def diagnostico_de_timeouts(informe: InformeMutacion, timeout_s: int) -> str | None:
    """`None` si ningún mutante quedó en timeout; si no, el aviso de que los
    recuentos de la campaña no se pueden leer."""
    if not informe.timeouts:
        return None
    nombres = "\n".join(f"- {m.descripcion()}" for m in informe.timeouts)
    return (
        f"TIMEOUT tras {timeout_s} s en {len(informe.timeouts)} mutante(s): "
        "no es un rojo de la campaña. Esos mutantes no tienen veredicto, así "
        "que los recuentos de muertos y supervivientes no se pueden comparar "
        "con lo esperado. Casi siempre es la máquina sobresuscrita.\n"
        f"{nombres}"
    )


def _sin_timeouts(informe: InformeMutacion) -> None:
    """Se llama ANTES de comprobar recuentos: un timeout cae como TIMEOUT."""
    diagnostico = diagnostico_de_timeouts(informe, TIMEOUT_S)
    if diagnostico is not None:
        pytest.fail(diagnostico)


# --- Escenario A · paralelo con un fichero no versionado --------------------


def test_A_control_en_serie_hay_supervivientes(tmp_path: Path) -> None:
    """Lo que la campaña DEBE decir: `etiqueta` no la comprueba nadie.

    En el árbol principal `datos.local` existe, así que la base está verde y
    los números salen bien. Este es el `--workers 1` del encargo: el que se
    demostró bueno.
    """
    repositorio = _repositorio(tmp_path / "juguete")

    informe = ejecutar_campania(
        _alcance(),
        EjecutorPytest(raiz=str(repositorio), ejecutable=sys.executable),
        timeout_s=TIMEOUT_S,
        raiz=str(repositorio),
    )

    _sin_timeouts(informe)
    # F-026: los dos `if` dan además su `negacion` (5 → 7). La de `descuento`
    # muere; la de `etiqueta`, que no la prueba nadie, sobrevive (3 → 4).
    assert informe.generados == GENERADOS_APP
    assert len(informe.supervivientes) == 4, [
        m.descripcion() for m in informe.supervivientes
    ]
    assert informe.muertos == 3
    assert informe.fiable
    _sin_mutar(repositorio)


def test_A_antes_la_campania_paralela_daba_cero_supervivientes_falsos(
    tmp_path: Path,
) -> None:
    """El defecto, reproducido: mismo árbol, cero supervivientes.

    Los cuatro supervivientes que el control acaba de demostrar desaparecen. No
    porque ningún test los cace —ninguno lo hace—, sino porque la suite del
    worker ya estaba roja: le falta `datos.local`, que no está versionado.
    """
    repositorio = _repositorio(tmp_path / "juguete")

    with arnes_1_5_2():
        informe = ejecutar_campania_paralela(
            _alcance(),
            [],
            timeout_s=TIMEOUT_S,
            raiz=str(repositorio),
            workers=2,
        )

    _sin_timeouts(informe)
    assert informe.generados == GENERADOS_APP
    assert informe.muertos == GENERADOS_APP, "el ANTES daba TODOS los mutantes por muertos"
    assert informe.supervivientes == [], "el cero falso, medido"
    # Y lo peor: el informe no tenía ni una pega que ponerle.
    assert informe.fiable
    _sin_mutar(repositorio)


def test_A_despues_la_campania_paralela_aborta_y_dice_por_que(tmp_path: Path) -> None:
    """El arreglo: la línea base del worktree no está verde, así que no se
    juzga a nadie y el mensaje nombra el test que falla."""
    repositorio = _repositorio(tmp_path / "juguete")

    with pytest.raises(BaseRota) as caido:
        ejecutar_campania_paralela(
            _alcance(),
            [],
            timeout_s=TIMEOUT_S,
            raiz=str(repositorio),
            workers=2,
        )

    mensaje = str(caido.value)
    assert "LÍNEA BASE EN ROJO" in mensaje
    assert "test_app.py::test_hay_datos_locales" in mensaje
    assert "no existen dentro de un git worktree" in mensaje
    assert "--workers 1" in mensaje
    _sin_mutar(repositorio)


# --- Escenario B · serie con la recolección rota ----------------------------


def test_B_antes_una_recoleccion_rota_mataba_a_todo_el_mundo(tmp_path: Path) -> None:
    """El tercer caso, en serie y sin worktrees de por medio.

    `python -m pytest` sin ruta revienta en la recolección (exit 2) haga lo que
    haga el mutante. La 1.5.2 traducía cualquier salida distinta de 0 y 5 a
    MUERTO, así que la campaña entera salía «sin supervivientes» en segundos
    sin que un solo test juzgara nada. Pasó con los 19 mutantes de F-034 en
    albaranes y con los 61 de F-012, todos sobre ficheros de `harness/`.
    """
    repositorio = _repositorio(tmp_path / "juguete", con_suite_rota=True)

    with arnes_1_5_2():
        informe = ejecutar_campania(
            _alcance(),
            EjecutorPytest(raiz=str(repositorio), ejecutable=sys.executable),
            timeout_s=TIMEOUT_S,
            raiz=str(repositorio),
            comprobar_base=False,
        )

    _sin_timeouts(informe)
    assert informe.muertos == GENERADOS_APP
    assert informe.supervivientes == []
    _sin_mutar(repositorio)


def test_C_un_mutante_nunca_se_juzga_con_el_bytecode_del_anterior(
    tmp_path: Path,
) -> None:
    """El tercer camino hacia un muerto que nadie mató: el `.pyc` rancio.

    Este test salió de una discrepancia real entre dos ejecuciones de
    `test_A_control...`: la misma campaña sobre el mismo repositorio daba 3
    supervivientes o 2 según el segundo en que cayera. El que desaparecía se
    contaba MUERTO sin que ningún test lo tocara, porque CPython reutilizaba el
    bytecode del mutante anterior —mismo tamaño de fuente, mismo mtime en
    segundos enteros—.

    Aquí se fuerza esa coincidencia con `os.utime` en vez de esperar a que el
    reloj la regale, que es lo que la hace reproducible. Y los dos subprocesos
    parten del entorno que fija `_entorno_que_escribe_bytecode()`, no del que
    traiga quien invoque a pytest: ver allí por qué.
    """
    entorno = _entorno_que_escribe_bytecode()

    modulo = tmp_path / "m.py"
    _escribir(modulo, "VALOR = 1\n")
    subprocess.run(
        [sys.executable, "-c", "import m"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=entorno,
    )
    assert list((tmp_path / "__pycache__").glob("m.*.pyc")), (
        "el intérprete no dejó bytecode: este test no estaría probando nada"
    )
    antes = modulo.stat()

    _escribir(modulo, "VALOR = 9\n")  # mismo tamaño EXACTO que el anterior
    os.utime(modulo, (antes.st_atime, antes.st_mtime))  # y mismo mtime

    salida = subprocess.run(
        [sys.executable, "-c", "import m; print(m.VALOR)"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env=entorno,
    ).stdout.strip()

    assert salida == "9", (
        "se ejecutó el bytecode rancio y no el fuente que hay en disco: un "
        "mutante juzgado así sale muerto sin que ningún test lo cace"
    )


def test_C_regresion_el_escenario_del_bytecode_aguanta_la_variable_puesta() -> None:
    """El escenario C, corrido con `PYTHONDONTWRITEBYTECODE=1` puesta.

    Esta es la regresión del defecto de la 1.7.6, y se ejecuta de la única
    forma que demuestra algo: relanzando el test C en un subproceso con la
    variable envenenada, exactamente como se la pone la campaña de mutación al
    medir su línea base. Si vuelve a salir en rojo, es que alguien ha dejado el
    escenario C a merced del entorno que herede.

    No vale con comprobar el código fuente ni con marcar el test como `skip`
    cuando la variable esté puesta: saltárselo apagaría justo el test que
    protege el arreglo de la 1.6.3, y entonces la campaña arrancaría verde
    sobre un árbol envenenado sin que nadie lo notara.
    """
    raiz = Path(__file__).resolve().parents[1]
    fichero = Path(__file__).resolve().relative_to(raiz).as_posix()
    caso = test_C_un_mutante_nunca_se_juzga_con_el_bytecode_del_anterior.__name__

    anidado = correr_anidado(
        # `-m pytest` y no el ejecutable: es lo que mete la raíz en `sys.path`
        # y lo que hace que `from harness import ...` importe aquí dentro.
        # `-p no:cacheprovider` para no ensuciar `.pytest_cache` del anidado.
        [
            sys.executable,
            "-m",
            "pytest",
            f"{fichero}::{caso}",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=raiz,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout_s=TIMEOUT_S,
    )

    # Un TIMEOUT no dice nada del escenario C: se informa como tal y no con el
    # texto del rojo, que mandaría a buscar un defecto que no existe.
    if anidado.expirado:
        pytest.fail(anidado.diagnostico())
    assert anidado.codigo == 0, (
        "el escenario C falla con PYTHONDONTWRITEBYTECODE puesta, que es como "
        "lo corre la campaña de mutación al medir la línea base: la campaña "
        "aborta sin escribir informe y ninguna feature se puede cerrar.\n"
        f"{anidado.diagnostico()}"
    )


def test_B_despues_una_recoleccion_rota_aborta_la_campania(tmp_path: Path) -> None:
    """El mismo árbol, con la 1.6.0: no se cuenta ni un muerto."""
    repositorio = _repositorio(tmp_path / "juguete", con_suite_rota=True)

    with pytest.raises(BaseRota) as caido:
        ejecutar_campania(
            _alcance(),
            EjecutorPytest(raiz=str(repositorio), ejecutable=sys.executable),
            timeout_s=TIMEOUT_S,
            raiz=str(repositorio),
        )

    mensaje = str(caido.value)
    assert "LÍNEA BASE EN ROJO" in mensaje
    # Que el aborto NOMBRE lo que falla es la mitad del arreglo: «código 2» a
    # secas manda al humano a adivinar, y adivinar cuesta una tarde.
    assert "tests/test_irrecolectable.py" in mensaje
    _sin_mutar(repositorio)


# --- F-038 · un TIMEOUT no se confunde con un ROJO --------------------------


def test_f038_un_anidado_que_expira_dice_TIMEOUT_y_no_rojo(tmp_path: Path) -> None:
    """Un `sleep` de 30 s contra un reloj de 1 s: expira siempre, con carga o sin
    ella, y el diagnóstico tiene que decirlo con esa palabra."""
    resultado = correr_anidado(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=tmp_path,
        env=dict(os.environ),
        timeout_s=1,
    )

    assert resultado.expirado
    diagnostico = resultado.diagnostico()
    assert diagnostico is not None
    assert diagnostico.startswith("TIMEOUT tras 1 s"), diagnostico
    assert "ROJO" not in diagnostico


def test_f038_un_anidado_rojo_dice_ROJO_con_su_salida(tmp_path: Path) -> None:
    resultado = correr_anidado(
        [sys.executable, "-c", "import sys; print('salida del rojo'); sys.exit(3)"],
        cwd=tmp_path,
        env=dict(os.environ),
        timeout_s=TIMEOUT_S,
    )

    assert not resultado.expirado
    diagnostico = resultado.diagnostico()
    assert diagnostico is not None
    assert diagnostico.startswith("ROJO (código 3)"), diagnostico
    assert "salida del rojo" in diagnostico, "un rojo sin su salida manda a adivinar"
    assert "TIMEOUT" not in diagnostico


def test_f038_un_anidado_verde_no_tiene_diagnostico(tmp_path: Path) -> None:
    resultado = correr_anidado(
        [sys.executable, "-c", "pass"],
        cwd=tmp_path,
        env=dict(os.environ),
        timeout_s=TIMEOUT_S,
    )

    assert resultado.diagnostico() is None


def test_f038_una_campania_con_timeouts_lo_dice_antes_de_contar_muertos() -> None:
    """El síntoma de `partes`: «3 muertos en vez de 5». Si hay mutantes en
    timeout, el test tiene que caer diciendo TIMEOUT, no `assert 3 == 5`."""
    mutantes = generar_mutantes(APP, LINEAS_EN_ALCANCE, "app.py")
    con_timeouts = InformeMutacion(
        feature="F-999", alcance=_alcance(), generados=5, muertos=3,
        timeouts=mutantes[:2],
    )
    limpio = InformeMutacion(feature="F-999", alcance=_alcance(), generados=5, muertos=5)

    diagnostico = diagnostico_de_timeouts(con_timeouts, TIMEOUT_S)

    assert diagnostico is not None
    assert diagnostico.startswith(f"TIMEOUT tras {TIMEOUT_S} s en 2 mutante(s)"), diagnostico
    assert "no es un rojo" in diagnostico
    assert diagnostico_de_timeouts(limpio, TIMEOUT_S) is None


# --- F-023 · Escenarios D (código 5) y E (no compila) -----------------------
#
# D: un `conftest.py` cuyo `collect_ignore` depende de una constante del código
# bajo mutación. El mutante `True -> False` deja la suite SIN TESTS (código 5)
# con la base verde. Hasta F-023 eso era un superviviente; ahora es
# `indeterminado`, con su código, y en serie y en paralelo sale lo mismo.
#
# E: un mutante que no compila (paréntesis desparejado, como datamart F-148).
# Hasta F-023 contaba como MUERTO sin que ningún test lo juzgara.

PRODUCTO_D = """# producto.py
ACTIVO = True


def doble(x):
    return x * 2
"""

CONFTEST_D = """# conftest.py
import producto

collect_ignore = [] if producto.ACTIVO else ["test_producto.py"]
"""

TEST_PRODUCTO_D = """# test_producto.py
import producto


def test_doble():
    assert producto.doble(3) == 6
"""

LINEAS_D = {2, 6}


def _repositorio_d(destino: Path) -> Path:
    destino.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "dev", str(destino)], check=True, capture_output=True
    )
    _git(destino, "config", "user.email", "arnes@ruesma.es")
    _git(destino, "config", "user.name", "Arnes")
    for nombre, texto in (("producto.py", PRODUCTO_D), ("conftest.py", CONFTEST_D),
                          ("test_producto.py", TEST_PRODUCTO_D)):
        (destino / nombre).write_text(texto, encoding="utf-8", newline="")
    _git(destino, "add", "-A")
    _git(destino, "commit", "-q", "-m", "inicial")
    return destino


def _alcance_d() -> Alcance:
    return Alcance(feature="F-999", origen="rama", ref_diff=("dev", "feature/F-999-d"),
                   lineas={"producto.py": set(LINEAS_D)})


def _mutantes_d() -> list:
    """`ACTIVO = True -> False` (código 5) y `x * 2 -> x // 2` (muerto)."""
    return [m for m in generar_mutantes(PRODUCTO_D, LINEAS_D, "producto.py")
            if m.mutado in ("ACTIVO = False", "return x // 2")]


def _mutantes_e() -> list:
    """Un mutante que no compila y uno que muere, en la misma línea 6."""
    roto = Mutante("producto.py", 6, 4, "return x * 2", "(return x * 2", "roto", 0, "(")
    return [roto, *[m for m in _mutantes_d() if m.linea == 6]]


def _campanias(repositorio: Path, mutantes: list, tmp_path: Path) -> tuple:
    serie = ejecutar_campania(
        _alcance_d(), EjecutorPytest(raiz=str(repositorio)), timeout_s=TIMEOUT_S,
        raiz=str(repositorio), mutantes=list(mutantes),
    )
    paralela = ejecutar_campania_paralela(
        _alcance_d(), [], timeout_s=TIMEOUT_S, raiz=str(repositorio), workers=2,
        mutantes=list(mutantes),
    )
    textos = []
    for nombre, informe in (("serie", serie), ("paralela", paralela)):
        ruta = tmp_path / nombre / "mutacion_F-999.md"
        escribir_informe(informe, ruta)
        textos.append(lineas_comparables(ruta.read_text(encoding="utf-8")))
    return serie, paralela, textos


def test_D_codigo_5_es_indeterminado_igual_en_serie_y_en_paralelo(tmp_path: Path) -> None:
    repositorio = _repositorio_d(tmp_path / "juguete")
    activo = next(m for m in _mutantes_d() if m.mutado == "ACTIVO = False")

    serie, paralela, (texto_serie, texto_paralela) = _campanias(
        repositorio, _mutantes_d(), tmp_path
    )

    for informe in (serie, paralela):
        _sin_timeouts(informe)
        assert informe.supervivientes == [], "el código 5 ya no es un superviviente"
        assert informe.indeterminados == [activo]
        assert informe.codigos[clave_de_orden(activo)] == "5"
        assert informe.muertos == 1
        assert informe.fiable
    assert texto_serie == texto_paralela
    assert "| `producto.py:2` | booleano | indeterminado | 5 |" in texto_serie
    _sin_mutar_d(repositorio)


def test_E_no_compila_es_indeterminado_igual_en_serie_y_en_paralelo(tmp_path: Path) -> None:
    repositorio = _repositorio_d(tmp_path / "juguete")
    roto = _mutantes_e()[0]

    serie, paralela, (texto_serie, texto_paralela) = _campanias(
        repositorio, _mutantes_e(), tmp_path
    )

    for informe in (serie, paralela):
        _sin_timeouts(informe)
        assert informe.indeterminados == [roto]
        assert informe.codigos[clave_de_orden(roto)] == NO_COMPILA
        assert informe.muertos == 1, "el que no compila no se suma a los muertos"
    assert texto_serie == texto_paralela
    assert "| `producto.py:6` | roto | indeterminado | no compila |" in texto_serie
    _sin_mutar_d(repositorio)


def _sin_mutar_d(repositorio: Path) -> None:
    assert _leer(repositorio / "producto.py") == PRODUCTO_D


# --- Escenario F · lo que el mutador no veía (F-026, R24 y R25) ---------------
#
# Un fichero con una línea por patrón que hasta F-026 daba CERO mutantes (o uno
# que no compilaba, el `not (` de datamart F-148), y otro cuyas líneas en
# alcance son solo declaraciones. ANTES (1.8.0): las líneas de patrón no dan
# mutante y `constantes.py` se suma al resto sin que el informe lo diga.
# DESPUÉS: cada línea da su mutante, todos compilan, el test débil deja vivo a
# su superviviente y `constantes.py` sale señalado, en serie y en paralelo.

PATRONES_F = '''# patrones.py
def pertenece(x, xs):
    return x in xs


def mitad(a):
    return a / 2


def menor(a, b):
    return min(a, b)


def signo(a):
    if a:
        return 1
    return 0


def elige(a, b, c):
    return a if c else b


def presente(x):
    return x is not None


def codigo(n):
    return f"{n:03d}"


def ambos(a, b):
    if not (a and b):
        return 0
    return 1
'''

CONSTANTES_F = '''# constantes.py
NOMBRE = "arnes"
VERSION = "1.0"
'''

#: Matan todo menos `min` ↔ `max`: `menor(2, 2)` da lo mismo con los dos. Es el
#: superviviente que el informe TIENE que enseñar.
TEST_PATRONES_F = '''# test_patrones.py
import constantes
import patrones


def test_pertenece():
    assert patrones.pertenece(1, [1]) is True
    assert patrones.pertenece(2, [1]) is False


def test_mitad():
    assert patrones.mitad(8) == 4


def test_menor_debil():
    assert patrones.menor(2, 2) == 2


def test_signo():
    assert patrones.signo(5) == 1
    assert patrones.signo(0) == 0


def test_elige():
    assert patrones.elige(1, 2, True) == 1


def test_presente():
    assert patrones.presente(0) is True
    assert patrones.presente(None) is False


def test_codigo():
    assert patrones.codigo(7) == "007"


def test_ambos():
    assert patrones.ambos(1, 1) == 1
    assert patrones.ambos(1, 0) == 0


def test_constantes():
    assert constantes.NOMBRE == "arnes"
'''

#: Línea de cada patrón en `PATRONES_F`: R1 `in`, R2 `/`, R3 `min`, R4 `if a`,
#: R5 ternario, R9 `is not None`, R8 `:03d` y R11 `not (`.
LINEAS_PATRON_F = {3: "in", 7: "/", 11: "min", 15: "if", 21: "ternario",
                   25: "is not None", 29: "03d", 33: "not ("}
LINEAS_CONSTANTES_F = {2, 3}


def _repositorio_f(destino: Path) -> Path:
    destino.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "dev", str(destino)], check=True, capture_output=True
    )
    _git(destino, "config", "user.email", "arnes@ruesma.es")
    _git(destino, "config", "user.name", "Arnes")
    for nombre, texto in (("patrones.py", PATRONES_F), ("constantes.py", CONSTANTES_F),
                          ("test_patrones.py", TEST_PATRONES_F)):
        (destino / nombre).write_text(texto, encoding="utf-8", newline="")
    _git(destino, "add", "-A")
    _git(destino, "commit", "-q", "-m", "inicial")
    return destino


def _alcance_f() -> Alcance:
    return Alcance(feature="F-999", origen="rama", ref_diff=("dev", "feature/F-999-f"),
                   lineas={"patrones.py": set(LINEAS_PATRON_F),
                           "constantes.py": set(LINEAS_CONSTANTES_F)})


def _campanias_f(repositorio: Path, tmp_path: Path) -> tuple:
    serie = ejecutar_campania(
        _alcance_f(), EjecutorPytest(raiz=str(repositorio)), timeout_s=TIMEOUT_S,
        raiz=str(repositorio),
    )
    paralela = ejecutar_campania_paralela(
        _alcance_f(), [], timeout_s=TIMEOUT_S, raiz=str(repositorio), workers=2,
    )
    textos = []
    for nombre, informe in (("serie", serie), ("paralela", paralela)):
        ruta = tmp_path / nombre / "mutacion_F-999.md"
        escribir_informe(informe, ruta)
        textos.append(ruta.read_text(encoding="utf-8"))
    return serie, paralela, textos


def test_F_cada_patron_da_su_mutante_y_el_cero_por_fichero_sale_señalado(
    tmp_path: Path,
) -> None:
    repositorio = _repositorio_f(tmp_path / "juguete")
    generados = generar_mutantes(PATRONES_F, set(LINEAS_PATRON_F), "patrones.py")
    sin_mutante = sorted(set(LINEAS_PATRON_F) - {m.linea for m in generados})
    assert sin_mutante == [], (
        f"líneas de patrón sin mutante: {[LINEAS_PATRON_F[n] for n in sin_mutante]}"
    )

    serie, paralela, (texto_serie, texto_paralela) = _campanias_f(repositorio, tmp_path)

    for informe in (serie, paralela):
        _sin_timeouts(informe)
        assert informe.generados == len(generados)
        no_compilan = [m for m in informe.indeterminados
                       if informe.codigos.get(clave_de_orden(m)) == NO_COMPILA]
        assert no_compilan == [], "R24: ningún mutante de F-026 deja de compilar"
        assert informe.indeterminados == []
        assert [(m.linea, m.operador) for m in informe.supervivientes] == [(11, "minmax")]
        assert informe.muertos == len(generados) - 1
        assert informe.por_fichero == {"constantes.py": 0, "patrones.py": len(generados)}
        assert informe.fiable
    assert lineas_comparables(texto_serie) == lineas_comparables(texto_paralela)
    for texto in (texto_serie, texto_paralela):
        assert "### 1. `patrones.py:11` [minmax]" in texto
        assert "| `constantes.py` | 2 | 0 — sin mutantes |" in texto
        assert f"| `patrones.py` | 8 | {len(generados)} |" in texto
        assert "### `constantes.py` — 2 líneas en alcance, 0 mutantes" in texto
    assert _leer(repositorio / "patrones.py") == PATRONES_F
    assert _leer(repositorio / "constantes.py") == CONSTANTES_F
