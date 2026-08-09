# tests/test_f015_mutacion.py
"""F-015 · Mutador del arnés (R1, R3, R5, R6, R7).

Ningún test de este fichero lanza pytest de verdad ni abre conexión alguna:
el ejecutor de tests se sustituye siempre por un doble.
"""

from __future__ import annotations

from harness.mutacion import Mutante, aplicar_mutante, generar_mutantes


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
    assert mutada == "# modulo_x.py\nimport os\n\n\ndef f(a, b):\n    return a >= b\n"


def test_f015_r6_operadores_con_acentos_en_la_misma_linea() -> None:
    # col_offset de ast son bytes UTF-8: una tilde antes del operador
    # desalinea el empalme textual si se trabaja con caracteres.
    fuente = 'año = "camión"\nx = año == 1\n'

    generados = [m for m in mutantes_de(fuente) if m.operador == "comparacion"]

    assert [m.mutado for m in generados] == ["x = año != 1"]
    assert aplicar_mutante(fuente, generados[0]) == 'año = "camión"\nx = año != 1\n'
