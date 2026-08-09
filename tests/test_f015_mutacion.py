# tests/test_f015_mutacion.py
"""F-015 · Mutador del arnés (R1, R3, R5, R6, R7).

Ningún test de este fichero lanza pytest de verdad ni abre conexión alguna:
el ejecutor de tests se sustituye siempre por un doble.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    MUERTO,
    SUPERVIVIENTE,
    TIMEOUT,
    EjecutorPytest,
    Mutante,
    aplicar_mutante,
    ejecutar_campania,
    escribir_informe,
    generar_mutantes,
)
from harness.rigor import cargar_rigor, timeout_mutacion


def mutantes_de(fuente: str, lineas: set[int] | None = None) -> list[Mutante]:
    """Genera los mutantes de un fragmento, por defecto sobre todas sus líneas."""
    if lineas is None:
        lineas = set(range(1, len(fuente.split("\n")) + 1))
    return generar_mutantes(fuente, lineas, "modulo_x.py")


def mutados(fuente: str, operador: str) -> list[str]:
    return [m.mutado for m in mutantes_de(fuente) if m.operador == operador]


# --- R6: los operadores de mutación -----------------------------------------


def test_f015_r6_operador_comparaciones() -> None:
    casos = {
        "a == b": "a != b",
        "a != b": "a == b",
        "a < b": "a <= b",
        "a <= b": "a < b",
        "a > b": "a >= b",
        "a >= b": "a > b",
    }
    for original, esperado in casos.items():
        assert mutados(f"x = {original}\n", "comparacion") == [f"x = {esperado}"]


def test_f015_r6_operador_aritmetico() -> None:
    casos = {
        "a + b": "a - b",
        "a - b": "a + b",
        "a * b": "a // b",
        "a // b": "a * b",
    }
    for original, esperado in casos.items():
        assert mutados(f"x = {original}\n", "aritmetico") == [f"x = {esperado}"]


def test_f015_r6_operador_logico() -> None:
    assert mutados("x = a and b\n", "logico") == ["x = a or b"]
    assert mutados("x = a or b\n", "logico") == ["x = a and b"]


def test_f015_r6_operador_booleanos() -> None:
    assert mutados("x = True\n", "booleano") == ["x = False"]
    assert mutados("x = False\n", "booleano") == ["x = True"]


def test_f015_r6_operador_enteros() -> None:
    assert mutados("x = 3\n", "entero") == ["x = 4"]
    assert mutados("limite = 0\n", "entero") == ["limite = 1"]
    # `True` es subclase de int: no puede colarse como mutación de entero.
    assert all(m.operador == "booleano" for m in mutantes_de("x = True\n"))


def test_f015_r6_operador_not() -> None:
    assert mutados("x = not a\n", "not") == ["x = a"]
    assert mutados("if not activo:\n    pass\n", "not") == ["if activo:"]


def test_f015_r6_operador_en_asignacion_aumentada() -> None:
    assert mutados("total += 1\n", "aritmetico") == ["total -= 1"]
    assert mutados("total *= 2\n", "aritmetico") == ["total //= 2"]


def test_f015_r6_comparacion_encadenada_muta_cada_operador() -> None:
    assert mutados("x = a < b < c\n", "comparacion") == ["x = a <= b < c", "x = a < b <= c"]


def test_f015_r6_operador_logico_encadenado_muta_cada_hueco() -> None:
    assert mutados("x = a and b and c\n", "logico") == [
        "x = a or b and c",
        "x = a and b or c",
    ]


def test_f015_r6_fuente_que_no_compila_no_da_mutantes() -> None:
    assert mutantes_de("def f(:\n") == []


def test_f015_r6_operador_repartido_en_varias_lineas() -> None:
    fuente = "x = (\n    a\n    == b\n)\n"

    (mutante,) = [m for m in mutantes_de(fuente) if m.operador == "comparacion"]

    assert mutante.linea == 3
    assert mutante.mutado == "!= b"


def test_f015_r6_un_mutante_un_solo_cambio() -> None:
    fuente = "y = (a + b) * c\n"

    generados = mutantes_de(fuente)

    assert {m.mutado for m in generados} == {"y = (a - b) * c", "y = (a + b) // c"}
    for mutante in generados:
        mutada = aplicar_mutante(fuente, mutante)
        distintas = [
            (a, b)
            for a, b in zip(fuente.split("\n"), mutada.split("\n"), strict=True)
            if a != b
        ]
        assert len(distintas) == 1, f"{mutante} tocó {len(distintas)} líneas"
        assert distintas[0][1].strip() == mutante.mutado


def test_f015_r6_aplicar_mutante_respeta_el_resto_del_fichero() -> None:
    fuente = "# modulo_x.py\nimport os\n\n\ndef f(a, b):\n    return a > b\n"

    (mutante,) = [m for m in mutantes_de(fuente) if m.operador == "comparacion"]
    mutada = aplicar_mutante(fuente, mutante)

    assert mutante.linea == 6
    assert mutante.original == "return a > b"
    assert mutada == "# modulo_x.py\nimport os\n\n\ndef f(a, b):\n    return a >= b\n"


def test_f015_r6_el_mutante_es_inmutable() -> None:
    (mutante,) = mutantes_de("x = a > b\n")

    with pytest.raises(Exception):  # noqa: B017  (FrozenInstanceError)
        mutante.linea = 99


def test_f015_r6_muta_la_ultima_linea_aunque_no_acabe_en_salto() -> None:
    # El fichero sin salto final tiene una línea menos al partirlo: el
    # recorrido no puede quedarse corto justo en la última.
    assert mutados("x = a\ny = b > c", "comparacion") == ["y = b >= c"]


def test_f015_r6_operador_al_principio_de_una_linea_de_continuacion() -> None:
    fuente = "x = (\na\n==b\n)\n"

    (mutante,) = [m for m in mutantes_de(fuente) if m.operador == "comparacion"]

    assert (mutante.linea, mutante.col) == (3, 0)
    assert mutante.mutado == "!=b"


def test_f015_r6_operadores_con_acentos_en_la_misma_linea() -> None:
    # Los col_offset de ast son bytes UTF-8: una tilde antes del operador
    # desalinea el empalme textual si se trabaja con caracteres.
    fuente = 'año = "camión"\nx = año == 1\n'

    generados = [m for m in mutantes_de(fuente) if m.operador == "comparacion"]

    assert [m.mutado for m in generados] == ["x = año != 1"]
    assert aplicar_mutante(fuente, generados[0]) == 'año = "camión"\nx = año != 1\n'


# --- Dobles del ejecutor de tests -------------------------------------------


class EjecutorFalso:
    """Doble del ejecutor de pytest: nunca lanza la suite ni abre nada.

    Devuelve los veredictos que se le pasan, en orden (el último se repite), y
    anota el contenido que tenía el fichero mutado en cada llamada.
    """

    def __init__(self, veredictos: list[str], vigilar: Path | None = None) -> None:
        self.veredictos = list(veredictos)
        self.vigilar = vigilar
        self.llamadas = 0
        self.vistos: list[str] = []
        self.timeouts_recibidos: list[int] = []

    def ejecutar(self, timeout_s: int) -> str:
        self.llamadas += 1
        self.timeouts_recibidos.append(timeout_s)
        if self.vigilar is not None:
            self.vistos.append(self.vigilar.read_text(encoding="utf-8"))
        indice = min(self.llamadas - 1, len(self.veredictos) - 1)
        return self.veredictos[indice]


class EjecutorQueRevienta(EjecutorFalso):
    def ejecutar(self, timeout_s: int) -> str:
        self.llamadas += 1
        if self.llamadas == 2:
            raise RuntimeError("pytest se cayó de forma inesperada")
        return MUERTO


FUENTE = "def clasifica(a, b):\n    if a > b:\n        return True\n    return False\n"


def preparar(
    tmp_path: Path, fuente: str = FUENTE, lineas: set[int] | None = None
) -> tuple[Path, Alcance]:
    """Deja un módulo de mentira en disco y devuelve su ruta y su alcance."""
    fichero = tmp_path / "modulo_x.py"
    fichero.write_text(fuente, encoding="utf-8")
    alcance = Alcance(
        feature="F-042",
        origen="rama",
        ref_diff=("base", "feature/F-042-x"),
        lineas={"modulo_x.py": lineas or set(range(1, len(fuente.split("\n")) + 1))},
    )
    return fichero, alcance


# --- R1: la campaña cuenta muertos y supervivientes -------------------------


def test_f015_r1_campania_cuenta_muertos_y_supervivientes(tmp_path: Path) -> None:
    _, alcance = preparar(tmp_path)
    ejecutor = EjecutorFalso([MUERTO, SUPERVIVIENTE, MUERTO])
    progreso: list[str] = []

    informe = ejecutar_campania(
        alcance, ejecutor, timeout_s=5, raiz=str(tmp_path), eco=progreso.append
    )

    assert informe.generados == 3  # `a > b`, `True` y `False`
    assert informe.evaluados == 3
    assert ejecutor.llamadas == 3
    assert informe.muertos == 2
    assert len(informe.supervivientes) == 1
    assert informe.supervivientes[0].mutado == "return False"
    assert informe.timeouts == []
    assert informe.muestreado is False
    # El tiempo es la duración de la campaña, no una marca de reloj.
    assert 0 <= informe.segundos < 60
    # Y el avance se numera desde el primero.
    assert progreso[0].startswith("[1/3]")
    assert progreso[-1].startswith("[3/3]")


def test_f015_r1_no_genera_mutantes_fuera_del_alcance(tmp_path: Path) -> None:
    _, alcance = preparar(tmp_path, lineas={2})
    ejecutor = EjecutorFalso([MUERTO])

    informe = ejecutar_campania(alcance, ejecutor, timeout_s=5, raiz=str(tmp_path))

    assert informe.generados == 1
    assert informe.mutantes_evaluados[0].linea == 2
    assert informe.mutantes_evaluados[0].mutado == "if a >= b:"


def test_f015_r1_exit_code_0_sin_supervivientes_y_1_con_ellos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, alcance = preparar(tmp_path, lineas={2})
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: alcance)
    salida = tmp_path / "mutacion_F-042.md"
    argumentos = ["--feature", "F-042", "--raiz", str(tmp_path), "--salida", str(salida)]

    assert mutacion.main(argumentos, ejecutor=EjecutorFalso([MUERTO])) == 0
    assert mutacion.main(argumentos, ejecutor=EjecutorFalso([SUPERVIVIENTE])) == 1
    assert salida.is_file()


def test_f015_r1_alcance_vacio_no_muta_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    alcance = Alcance("F-042", "rama", ("base", "rama"), {})
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: alcance)
    salida = tmp_path / "informe.md"
    ejecutor = EjecutorFalso([SUPERVIVIENTE])

    codigo = mutacion.main(
        ["--feature", "F-042", "--raiz", str(tmp_path), "--salida", str(salida)],
        ejecutor=ejecutor,
    )

    assert codigo == 0
    assert ejecutor.llamadas == 0
    assert salida.is_file()
    assert "nada que mutar" in capsys.readouterr().out


def test_f015_r1_sin_alcance_resoluble_el_codigo_es_de_error_de_uso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_hay_alcance(*args: object, **kwargs: object) -> None:
        raise SystemExit("ni rama ni merge")

    monkeypatch.setattr(mutacion, "alcance_de_feature", no_hay_alcance)

    codigo = mutacion.main(["--feature", "F-042", "--raiz", str(tmp_path)])

    assert codigo == 2


def test_f015_r11_el_timeout_por_mutante_sale_de_la_configuracion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, alcance = preparar(tmp_path, lineas={2})
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: alcance)
    ejecutor = EjecutorFalso([MUERTO])

    mutacion.main(
        [
            "--feature",
            "F-042",
            "--raiz",
            str(tmp_path),
            "--salida",
            str(tmp_path / "informe.md"),
        ],
        ejecutor=ejecutor,
    )

    esperado = timeout_mutacion(cargar_rigor())
    assert ejecutor.timeouts_recibidos == [esperado]


def test_f015_r1_muestreo_reproducible_con_semilla(tmp_path: Path) -> None:
    _, alcance = preparar(tmp_path)

    uno = ejecutar_campania(
        alcance,
        EjecutorFalso([MUERTO]),
        timeout_s=5,
        raiz=str(tmp_path),
        max_mutantes=2,
        semilla=20260809,
    )
    otro = ejecutar_campania(
        alcance,
        EjecutorFalso([MUERTO]),
        timeout_s=5,
        raiz=str(tmp_path),
        max_mutantes=2,
        semilla=20260809,
    )

    assert uno.generados == 3
    assert uno.evaluados == 2
    assert uno.muestreado is True
    assert [m.descripcion() for m in uno.mutantes_evaluados] == [
        m.descripcion() for m in otro.mutantes_evaluados
    ]


def test_f015_r1_un_tope_que_no_recorta_no_es_muestreo(tmp_path: Path) -> None:
    _, alcance = preparar(tmp_path)

    informe = ejecutar_campania(
        alcance,
        EjecutorFalso([MUERTO]),
        timeout_s=5,
        raiz=str(tmp_path),
        max_mutantes=3,  # justo los que hay: no se descarta ninguno
    )

    assert informe.generados == 3
    assert informe.evaluados == 3
    assert informe.muestreado is False


def test_f015_r1_sin_feature_el_uso_es_incorrecto() -> None:
    with pytest.raises(SystemExit):
        mutacion.main([])


# --- R3: el informe ---------------------------------------------------------


def test_f015_r3_informe_contiene_totales_y_detalle_por_superviviente(
    tmp_path: Path,
) -> None:
    _, alcance = preparar(tmp_path)
    informe = ejecutar_campania(
        alcance,
        EjecutorFalso([SUPERVIVIENTE, MUERTO, TIMEOUT]),
        timeout_s=5,
        raiz=str(tmp_path),
    )
    destino = tmp_path / "mutacion_F-042.md"

    escribir_informe(informe, destino)
    texto = destino.read_text(encoding="utf-8")

    # Alcance: ficheros y número de líneas.
    assert "Alcance" in texto
    assert "modulo_x.py" in texto
    # Totales.
    for etiqueta in (
        "Mutantes generados",
        "Muertos",
        "Supervivientes",
        "Timeouts",
        "Tiempo total",
    ):
        assert etiqueta in texto, etiqueta
    # Las dos referencias del diff, en su orden.
    assert "`base` .. `feature/F-042-x`" in texto
    # Detalle del superviviente: fichero, línea, operador y original -> mutado.
    superviviente = informe.supervivientes[0]
    assert "### 1. " in texto
    assert f"modulo_x.py:{superviviente.linea}" in texto
    assert superviviente.original in texto
    assert superviviente.mutado in texto
    assert superviviente.operador in texto


def test_f015_r3_el_informe_se_escribe_aunque_falte_el_directorio(
    tmp_path: Path,
) -> None:
    _, alcance = preparar(tmp_path)
    informe = ejecutar_campania(
        alcance, EjecutorFalso([MUERTO]), timeout_s=5, raiz=str(tmp_path)
    )
    destino = tmp_path / "sin" / "crear" / "mutacion_F-042.md"

    escribir_informe(informe, destino)

    assert destino.is_file()
    assert "Ninguno" in destino.read_text(encoding="utf-8")


def test_f015_r3_cada_superviviente_lleva_seccion_de_analisis(tmp_path: Path) -> None:
    _, alcance = preparar(tmp_path)
    informe = ejecutar_campania(
        alcance, EjecutorFalso([SUPERVIVIENTE]), timeout_s=5, raiz=str(tmp_path)
    )
    destino = tmp_path / "mutacion_F-042.md"

    escribir_informe(informe, destino)
    texto = destino.read_text(encoding="utf-8")

    assert len(informe.supervivientes) == 3
    assert texto.count("Análisis") == len(informe.supervivientes)
    assert texto.count("PENDIENTE") >= len(informe.supervivientes)


# --- R5: restauración garantizada -------------------------------------------


def test_f015_r5_restaura_el_fichero_tras_cada_mutante(tmp_path: Path) -> None:
    fichero, alcance = preparar(tmp_path)
    ejecutor = EjecutorFalso([MUERTO], vigilar=fichero)

    ejecutar_campania(alcance, ejecutor, timeout_s=5, raiz=str(tmp_path))

    # Durante la campaña el fichero estuvo mutado de verdad...
    assert ejecutor.vistos and all(visto != FUENTE for visto in ejecutor.vistos)
    # ...y al terminar quedó exactamente como estaba.
    assert fichero.read_text(encoding="utf-8") == FUENTE


def test_f015_r5_restaura_aunque_el_ejecutor_lance_excepcion(tmp_path: Path) -> None:
    fichero, alcance = preparar(tmp_path)

    with pytest.raises(RuntimeError):
        ejecutar_campania(
            alcance, EjecutorQueRevienta([]), timeout_s=5, raiz=str(tmp_path)
        )

    assert fichero.read_text(encoding="utf-8") == FUENTE


# --- R7: timeouts y mutantes que no compilan --------------------------------


def test_f015_r7_timeout_no_cuelga_la_campania(tmp_path: Path) -> None:
    _, alcance = preparar(tmp_path)
    ejecutor = EjecutorFalso([TIMEOUT, MUERTO, MUERTO])

    informe = ejecutar_campania(alcance, ejecutor, timeout_s=1, raiz=str(tmp_path))

    assert ejecutor.llamadas == 3, "la campaña siguió con los mutantes restantes"
    assert len(informe.timeouts) == 1
    assert informe.supervivientes == [], "un timeout no es un superviviente"
    assert informe.muertos == 2


class Proceso:
    def __init__(self, codigo: int) -> None:
        self.returncode = codigo


def test_f015_r7_ejecutor_pytest_traduce_el_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ejecutor = EjecutorPytest(raiz=".")

    def revienta(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(mutacion.subprocess, "run", revienta)
    assert ejecutor.ejecutar(1) == TIMEOUT

    monkeypatch.setattr(mutacion.subprocess, "run", lambda *a, **k: Proceso(0))
    assert ejecutor.ejecutar(1) == SUPERVIVIENTE
    monkeypatch.setattr(mutacion.subprocess, "run", lambda *a, **k: Proceso(1))
    assert ejecutor.ejecutar(1) == MUERTO


def test_f015_r7_el_ejecutor_no_deja_que_pytest_tumbe_la_campania(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro: dict[str, object] = {}

    def espia(orden: list[str], **kwargs: object) -> Proceso:
        registro["orden"] = orden
        registro.update(kwargs)
        return Proceso(1)

    monkeypatch.setattr(mutacion.subprocess, "run", espia)
    EjecutorPytest(raiz="/una/raiz").ejecutar(7)

    # Un mutante que hace fallar la suite NO puede lanzar excepción: es un
    # muerto, que es el caso normal.
    assert registro["check"] is False
    # Ni escupir la salida de pytest por consola en cada uno de los cientos
    # de mutantes.
    assert registro["capture_output"] is True
    # Y el timeout es el que se le pasa, no otro.
    assert registro["timeout"] == 7
    assert registro["cwd"] == "/una/raiz"
    assert "pytest" in registro["orden"]


def test_f015_r7_mutante_que_no_compila_cuenta_como_muerto(tmp_path: Path) -> None:
    fichero, alcance = preparar(tmp_path, fuente="x = 1 + 1\n")
    roto = Mutante(
        fichero="modulo_x.py",
        linea=1,
        col=4,
        original="x = 1 + 1",
        mutado="x = 1 +",
        operador="sintaxis",
        longitud=5,
        sustituto="1 +",
    )
    ejecutor = EjecutorFalso([SUPERVIVIENTE])

    informe = ejecutar_campania(
        alcance, ejecutor, timeout_s=5, raiz=str(tmp_path), mutantes=[roto]
    )

    assert ejecutor.llamadas == 0, "un mutante que no compila ya está muerto"
    assert informe.muertos == 1
    assert informe.supervivientes == []
    assert fichero.read_text(encoding="utf-8") == "x = 1 + 1\n"
