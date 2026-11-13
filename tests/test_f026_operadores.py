# tests/test_f026_operadores.py
"""F-026: lo que el mutador no veía, y el `not` que no compilaba.

Hasta F-026 una línea con `in`, `/`, `min`/`max`, un ternario, el ancho de una
f-string o un `if c` sin operadores daba CERO mutantes, y nadie lo veía: la
campaña solo aborta cuando el cero es de la campaña entera. Y el operador `not`
ante un operando entre paréntesis se comía el `(`: `if not (a and b):` daba
`if a and b):`, un mutante que no compila (datamart F-148).

Todos los tests son puros: AST sobre fuentes en cadena. Ni red, ni BBDD, ni
subprocesos.
"""

from __future__ import annotations

import pytest

from harness.mutacion import aplicar_mutante, generar_mutantes

FICHERO = "patrones.py"

#: Un fuente que reúne TODOS los patrones de la spec de F-026, más los de
#: siempre. Sobre él se comprueba que cada mutante de cada operador compila
#: (R13): es el invariante que el `not` con paréntesis rompía.
PATRONES = '''\
def patrones(a, b, xs, n, s, x, obj):
    if not (a and b):
        return 0
    if not x:
        return 1
    if not(x):
        return 1
    if a in xs:
        return 2
    if b not in xs:
        return 3
    r = a / b
    r /= 2
    m = min(a, b)
    mx = max(xs)
    k = obj.min(xs)
    if a:
        pass
    while x:
        break
    if a and b:
        pass
    if a < b:
        pass
    if (a or b):
        pass
    if obj.listo:
        pass
    if xs[0]:
        pass
    if callable(x):
        pass
    v = a if b else n
    w = a if b or x else n
    if x is not None:
        pass
    if obj.y is None:
        pass
    t = f"{n:03d}"
    u = f"{s:>10}|{n:08.2f}"
    z = f"{n:{a}}"
    e = f"{n:.2f}"
    return a == b, a + b, a - b, a * b, a // b, True, 1, r, m, mx, k, v, w, t, u, z, e
'''

#: Operadores cuyos mutantes se compilan sobre `PATRONES`. Cada uno tiene que
#: dar al menos un mutante ahí: un operador sin mutantes en el fuente de
#: patrones no está probado, solo declarado.
OPERADORES = [
    "comparacion", "aritmetico", "logico", "not", "booleano", "entero", "minmax",
    "negacion", "ternario", "veracidad", "formato",
]


def _todas(fuente: str) -> set[int]:
    return set(range(1, fuente.count("\n") + 2))


def _mutantes(fuente: str) -> list:
    return generar_mutantes(fuente, _todas(fuente), FICHERO)


def _compila(fuente: str) -> bool:
    try:
        compile(fuente, FICHERO, "exec")
    except SyntaxError:
        return False
    return True


# --- R11, R12: el `not` respeta los paréntesis --------------------------------


def test_f026_r11_not_con_parentesis_quita_solo_la_palabra() -> None:
    fuente = "def f(a, b):\n    if not (a and b):\n        return 1\n"

    nots = [m for m in _mutantes(fuente) if m.operador == "not"]

    assert [m.mutado for m in nots] == ["if (a and b):"]
    assert _compila(aplicar_mutante(fuente, nots[0]))


def test_f026_r11_not_con_parentesis_en_un_return() -> None:
    fuente = "def f(p, q):\n    return not (p or q)\n"

    nots = [m for m in _mutantes(fuente) if m.operador == "not"]

    assert [m.mutado for m in nots] == ["return (p or q)"]
    assert _compila(aplicar_mutante(fuente, nots[0]))


@pytest.mark.parametrize(
    ("linea", "esperado"),
    [
        ("    if not x:", "if x:"),
        ("    if not(x):", "if (x):"),
        ("    if not  x:", "if x:"),
        ("    if not\tx:", "if x:"),
        ("    if not -x:", "if -x:"),
    ],
)
def test_f026_r12_not_sin_blancos_de_mas(linea: str, esperado: str) -> None:
    fuente = f"def f(x):\n{linea}\n        return 1\n"

    nots = [m for m in _mutantes(fuente) if m.operador == "not"]

    assert [m.mutado for m in nots] == [esperado]
    assert _compila(aplicar_mutante(fuente, nots[0]))


def test_f026_r12_not_con_el_operando_en_otra_linea() -> None:
    """El operando que arranca en la línea siguiente: se quita `not` y nada más."""
    fuente = "def f(a, b):\n    return not (\n        a and b\n    )\n"

    nots = [m for m in _mutantes(fuente) if m.operador == "not"]

    assert [m.mutado for m in nots] == ["return ("]
    assert _compila(aplicar_mutante(fuente, nots[0]))


# --- R13: todo mutante generado compila ----------------------------------------


def test_f026_r13_el_fuente_de_patrones_compila() -> None:
    assert _compila(PATRONES)


@pytest.mark.parametrize("operador", OPERADORES)
def test_f026_r13_cada_mutante_del_operador_compila(operador: str) -> None:
    mutantes = [m for m in _mutantes(PATRONES) if m.operador == operador]

    assert mutantes, f"el operador {operador} no da ningún mutante en PATRONES"
    rotos = [
        m.descripcion() for m in mutantes if not _compila(aplicar_mutante(PATRONES, m))
    ]
    assert rotos == []


# --- R1–R3, R10: operadores de token ------------------------------------------


def _de(fuente: str, operador: str) -> list[str]:
    return [m.mutado for m in _mutantes(fuente) if m.operador == operador]


def test_f026_r1_in_pasa_a_not_in() -> None:
    assert _de("def f(a, xs):\n    return a in xs\n", "comparacion") == [
        "return a not in xs"
    ]


def test_f026_r1_not_in_pasa_a_in() -> None:
    assert _de("def f(a, xs):\n    return a not in xs\n", "comparacion") == [
        "return a in xs"
    ]


def test_f026_r1_in_no_casa_dentro_de_una_palabra() -> None:
    """`in` está dentro de `inicio` y de `fin`: solo se muta el operador."""
    fuente = "def f(inicio, fin):\n    return inicio in fin\n"

    assert _de(fuente, "comparacion") == ["return inicio not in fin"]


def test_f026_r1_in_de_un_for_no_es_una_comparacion() -> None:
    assert _de("def f(xs):\n    for x in xs:\n        pass\n", "comparacion") == []


def test_f026_r2_division_pasa_a_producto() -> None:
    assert _de("def f(a, b):\n    return a / b\n", "aritmetico") == ["return a * b"]


def test_f026_r2_division_aumentada_pasa_a_producto_aumentado() -> None:
    assert _de("def f(a):\n    a /= 2\n    return a\n", "aritmetico") == ["a *= 2"]


def test_f026_r2_division_entera_sigue_como_antes() -> None:
    assert _de("def f(a, b):\n    return a // b\n", "aritmetico") == ["return a * b"]


def test_f026_r3_minmax_min_pasa_a_max_y_viceversa() -> None:
    fuente = "def f(a, b, xs):\n    m = min(a, b)\n    return max(xs) + m\n"

    assert _de(fuente, "minmax") == ["m = max(a, b)", "return min(xs) + m"]


def test_f026_r3_minmax_con_atributo_no_genera_mutante() -> None:
    fuente = "def f(np, xs):\n    return np.min(xs), np.max(xs)\n"

    assert _de(fuente, "minmax") == []


def test_f026_r3_minmax_otro_nombre_no_genera_mutante() -> None:
    assert _de("def f(xs):\n    return minimo(xs)\n", "minmax") == []


def test_f026_r10_in_partido_entre_lineas_no_falla() -> None:
    """Mismo molde que `COMPARACIONES`: el token se muta en la línea donde está."""
    fuente = "def f(a, xs):\n    return (a\n            in xs)\n"

    assert _de(fuente, "comparacion") == ["not in xs)"]
    assert all(_compila(aplicar_mutante(fuente, m)) for m in _mutantes(fuente))


# --- R4–R10: operadores de tramo -------------------------------------------------


def _cond(cabecera: str) -> str:
    """Una función con `cabecera` como sentencia compuesta y un cuerpo trivial."""
    return f"def f(a, b, c, x, obj, xs, n, s):\n    {cabecera}\n        pass\n"


@pytest.mark.parametrize(
    ("cabecera", "esperado"),
    [
        ("if c:", "if not c:"),
        ("while x:", "while not x:"),
        ("if obj.listo:", "if not obj.listo:"),
        ("if callable(x):", "if not callable(x):"),
        ("if xs[0]:", "if not xs[0]:"),
        ("if a and b:", "if not (a and b):"),
        ("if a < b:", "if not (a < b):"),
        ("if a < b < c:", "if not (a < b < c):"),
        ("if (a or b):", "if (not (a or b)):"),
        ("if -x:", "if not (-x):"),
    ],
)
def test_f026_r4_r7_negacion_de_la_condicion(cabecera: str, esperado: str) -> None:
    fuente = _cond(cabecera)

    negados = [m for m in _mutantes(fuente) if m.operador == "negacion"]

    assert [m.mutado for m in negados] == [esperado]
    assert _compila(aplicar_mutante(fuente, negados[0]))


def test_f026_r4_negacion_del_elif() -> None:
    fuente = "def f(a, b):\n    if a:\n        pass\n    elif b:\n        pass\n"

    assert _de(fuente, "negacion") == ["if not a:", "elif not b:"]


@pytest.mark.parametrize(
    "cabecera",
    [
        "if not c:",
        "if True:",
        "while 1:",
        "if a == b:",
        "if a != b:",
        "if x is None:",
        "if x is not None:",
        "if a in xs:",
        "if a not in xs:",
    ],
)
def test_f026_r6_negacion_no_duplica_a_otro_operador(cabecera: str) -> None:
    assert _de(_cond(cabecera), "negacion") == []


def test_f026_r6_negacion_si_en_una_comparacion_encadenada_de_igualdad() -> None:
    """Dos operadores: negarla no es lo mismo que cambiar uno de ellos."""
    assert _de(_cond("if a == b == c:"), "negacion") == ["if not (a == b == c):"]


def test_f026_r5_ternario_niega_la_condicion() -> None:
    fuente = "def f(a, b, c, x):\n    v = a if c else b\n    w = a if c or x else b\n"

    assert _de(fuente, "ternario") == ["v = a if not c else b", "w = a if not (c or x) else b"]


@pytest.mark.parametrize("condicion", ["not c", "True", "c == 1", "c is None", "c in b"])
def test_f026_r6_ternario_no_duplica_a_otro_operador(condicion: str) -> None:
    fuente = f"def f(a, b, c):\n    return a if {condicion} else b\n"

    assert _de(fuente, "ternario") == []


def test_f026_r9_veracidad_de_is_not_none_y_de_is_none() -> None:
    fuente = (
        "def f(x, obj):\n"
        "    if x is not None:\n"
        "        return 1\n"
        "    return obj.y is None\n"
    )

    assert _de(fuente, "veracidad") == ["if x:", "return not obj.y"]


def test_f026_r9_veracidad_convive_con_la_comparacion() -> None:
    fuente = "def f(x):\n    return x is not None\n"

    operadores = sorted(m.operador for m in _mutantes(fuente))

    assert operadores == ["comparacion", "veracidad"]


@pytest.mark.parametrize(
    "expresion",
    ["f(x) is None", "x[0] is None", "x is 0", "x is y", "None is x", "x is None is y"],
)
def test_f026_r9_veracidad_solo_con_nombre_o_atributo_contra_none(expresion: str) -> None:
    fuente = f"def f(x, y):\n    return {expresion}\n"

    assert _de(fuente, "veracidad") == []


@pytest.mark.parametrize(
    ("campo", "esperado"),
    [
        ('f"{n:03d}"', 'f"{n:04d}"'),
        ('f"{s:>10}"', 'f"{s:>11}"'),
        ('f"{s:*^9}"', 'f"{s:*^10}"'),
        ('f"{n:08.2f}"', 'f"{n:09.2f}"'),
        ('f"{n!r:>5}"', 'f"{n!r:>6}"'),
        ('f"{n:+10,d}"', 'f"{n:+11,d}"'),
    ],
)
def test_f026_r8_formato_suma_uno_al_ancho(campo: str, esperado: str) -> None:
    fuente = f"def f(n, s):\n    return {campo}\n"

    formatos = [m for m in _mutantes(fuente) if m.operador == "formato"]

    assert [m.mutado for m in formatos] == [f"return {esperado}"]
    assert _compila(aplicar_mutante(fuente, formatos[0]))


def test_f026_r8_formato_dos_campos_dos_mutantes() -> None:
    fuente = 'def f(n, s):\n    return f"{s:>10}|{n:08.2f}"\n'

    assert _de(fuente, "formato") == [
        'return f"{s:>11}|{n:08.2f}"',
        'return f"{s:>10}|{n:09.2f}"',
    ]


@pytest.mark.parametrize(
    "campo",
    ['f"{n:.2f}"', 'f"{n:{w}}"', 'f"{n}"', 'f"{n:d}"', 'f"{d:%Y-%m-%d}"', '"{n:03d}"'],
)
def test_f026_r8_formato_sin_ancho_no_genera_mutante(campo: str) -> None:
    fuente = f"def f(n, w, d):\n    return {campo}\n"

    assert _de(fuente, "formato") == []


@pytest.mark.parametrize(
    ("fuente", "operador"),
    [
        ("def f(a, b):\n    if (a and\n            b):\n        pass\n", "negacion"),
        ("def f(a, b, c):\n    return (a if (b and\n              c) else 0)\n", "ternario"),
        ('def f(n):\n    return (f"{n:03d}"\n            f"{n:>4}")\n', "formato"),
        ("def f(x):\n    return (x is\n            None)\n", "veracidad"),
    ],
)
def test_f026_r10_tramo_de_mas_de_una_linea_no_da_mutante(fuente: str, operador: str) -> None:
    assert _de(fuente, operador) == []
    assert all(_compila(aplicar_mutante(fuente, m)) for m in _mutantes(fuente))


def test_f026_r10_veracidad_multilinea_no_deja_candidato_vacio() -> None:
    """Mutación de la campaña de F-026 (`texto and izquierda` → `or`).

    Con la comparación partida, el texto del tramo es vacío y el operando de la
    izquierda no: un candidato con `buscar` vacío no da mutante (lo descarta
    `_localizar`), pero tampoco debe existir.
    """
    import ast

    from harness.mutacion import _veracidad

    fuente = "def f(x):\n    return (x is\n            None)\n"
    nodo = next(n for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.Compare))

    assert list(_veracidad(nodo, fuente.split("\n"))) == []
