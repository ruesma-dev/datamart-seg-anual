# tests/test_f040_dominio.py
"""
F-040 · El dominio de ventas (`etl_sigrid/domain/ventas.py`), sin red ni BBDD.

Es el ORÁCULO de las reglas que el SQL de `sql/ventas/` repite: quién es
persona física (R6), si un CIF es válido (R8), a qué columna va cada recargo
(R11-R12, con `CLASES_GARANTIA` como ÚNICO punto de la decisión D4) y en qué
estado está el seguimiento de una certificación (R18). Que el SQL lleve los
MISMOS literales lo vigila `tests/test_f040_sql.py`; que dé los MISMOS
resultados, `tests/test_f040_sandbox.py` (contra un Postgres desechable).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from etl_sigrid.domain import ventas as v

# ===========================================================================
# Constantes
# ===========================================================================


def test_f040_constantes_de_tipo_y_estados() -> None:
    assert v.TIP_CERTIFICACION == 54
    assert v.TIP_FACTURA_VENTA == 11
    assert v.TIP_CLIENTE == 4
    assert v.DOCDESTIP_FACTURA_VENTA == 11
    assert v.ESTADOS_CERT_CUENTAN == (2, 3, 4)


def test_f040_r11_clases_de_recargo() -> None:
    assert v.CLASE_COEFICIENTES == 0
    assert v.CLASE_RETESP == 1
    # D4 = A provisional (2026-11-07): garantía = clases 4 y 5, como compras.
    assert v.CLASES_GARANTIA == (4, 5)
    assert v.CLASES_RECARGO == ("COEFICIENTES", "GARANTIA", "RETESP", "OTRAS")


def test_f040_r24_prefijos_prohibidos_en_ventas() -> None:
    assert v.PREFIJOS_PROHIBIDOS_EN_VENTAS == (
        "direccion", "telefono", "correo", "cif_cabecera", "nombre_cabecera",
    )


# ===========================================================================
# R6 · normalizar_cif y es_persona_fisica
# ===========================================================================


@pytest.mark.parametrize(("crudo", "esperado"), [
    ("b-12.345 678", "B12345678"),
    (" 12345678z ", "12345678Z"),
    ("x1234567l", "X1234567L"),
    ("", None),
    ("  ", None),
    (" .-. ", None),
    (None, None),
])
def test_f040_r6_normalizar_cif(crudo: str | None, esperado: str | None) -> None:
    assert v.normalizar_cif(crudo) == esperado


@pytest.mark.parametrize(("cif", "perfis", "esperado"), [
    ("12345678Z", 0, True),     # DNI
    ("X1234567L", 0, True),     # NIE
    ("Y1234567X", None, True),  # NIE, perfis desconocido
    ("K1234567A", 0, True),     # NIF K/L/M
    ("B12345678", 0, False),    # sociedad
    ("B12345678", 1, True),     # perfis manda aunque el CIF sea de sociedad
    ("B12345678", -1, True),    # cualquier perfis distinto de 0
    (None, 1, True),
    (None, 0, False),
    (None, None, False),
    ("1234567Z", 0, False),     # 7 cifras: no tiene forma de NIF
    ("123456789", 0, False),    # sin letra final
    ("A1234567Z", 0, False),    # la A no abre un NIF de persona
    ("12345678Z1", 0, False),   # anclado al final
])
def test_f040_r6_es_persona_fisica(cif: str | None, perfis: int | None, esperado: bool) -> None:
    assert v.es_persona_fisica(cif, perfis) is esperado


@pytest.mark.parametrize(("codigo", "persona", "esperado"), [
    ("C1", False, "C1"),                    # el código de una sociedad, público
    ("B12345678", False, "B12345678"),      # un CIF de sociedad como código, también
    ("C2", True, None),                     # de persona física, nunca (R1-H1)
    ("87654321-x", False, None),            # con forma de NIF de persona, tampoco
    (" x1234567l ", False, None),           # NIE, con espacios y minúsculas
    ("K1234567A", False, None),
    (None, False, None),
    ("", False, ""),                        # vacío no es un NIF: se deja tal cual
])
def test_f040_r24_codigo_cliente_publicado(codigo: str | None, persona: bool,
                                           esperado: str | None) -> None:
    """R1-H1: `con.cod` puede ser el NIF de una persona; a `ventas` no llega."""
    assert v.codigo_cliente_publicado(codigo, persona) == esperado


# ===========================================================================
# R8 · cif_valido
# ===========================================================================


@pytest.mark.parametrize(("cif", "esperado"), [
    ("12345678Z", True),    # 12345678 % 23 = 14 -> Z
    ("12345678A", False),   # letra de control mal
    ("00000000T", True),    # 0 -> T
    ("00000023T", True),    # 23 % 23 = 0 -> T
    ("00000022E", True),    # 22 -> E (la última de la tabla)
    ("X1234567L", True),    # X -> 0: 01234567 % 23 = 19 -> L
    ("X1234567A", False),
    ("Y1234567X", True),    # Y -> 1: 11234567 % 23 = 10 -> X
    ("Z1234567R", True),    # Z -> 2: 21234567 % 23 = 1 -> R
    ("Z1234567T", False),
    ("K1234567A", True),    # K/L/M: solo por forma
    ("M0000000Z", True),
    ("B12345678", True),    # sociedad: por forma
    ("A1234567J", True),    # control alfabético de A a J
    ("A1234567K", False),   # K no es control de sociedad
    ("I12345678", False),   # la I no abre CIF de sociedad
    ("", False),
    (None, False),
    ("1234", False),
    ("ESB12345678", False),
])
def test_f040_r8_cif_valido(cif: str | None, esperado: bool) -> None:
    assert v.cif_valido(cif) is esperado


def test_f040_r8_letras_dni() -> None:
    assert v.LETRAS_DNI == "TRWAGMYFPDXBNJZSQVHLCKE"
    assert len(v.LETRAS_DNI) == 23


# ===========================================================================
# R11-R12 · clase_recargo y el único punto de decisión de D4
# ===========================================================================


@pytest.mark.parametrize(("reccla", "esperado"), [
    (0, "COEFICIENTES"),
    (1, "RETESP"),
    (2, "OTRAS"),
    (3, "OTRAS"),
    (4, "GARANTIA"),
    (5, "GARANTIA"),
    (6, "OTRAS"),
    (None, "OTRAS"),
])
def test_f040_r11_clase_recargo_hoy(reccla: int | None, esperado: str) -> None:
    assert v.clase_recargo(reccla) == esperado


def test_f040_r12_si_el_retesp_pasa_a_garantia_cambia_de_columna(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basta tocar `CLASES_GARANTIA`: el `RETESP` deja su columna y va a garantía."""
    monkeypatch.setattr(v, "CLASES_GARANTIA", (1, 4, 5))
    assert v.clase_recargo(1) == "GARANTIA"
    assert v.clase_recargo(0) == "COEFICIENTES"
    assert v.clase_recargo(4) == "GARANTIA"
    assert v.clase_recargo(3) == "OTRAS"


@pytest.mark.parametrize("clases", [(4, 5), (1, 4, 5)])
def test_f040_r11_el_reparto_es_completo_y_sin_solapes(
    monkeypatch: pytest.MonkeyPatch, clases: tuple[int, ...],
) -> None:
    """Cada clase va a UNA columna; la suma de las cuatro es el total."""
    monkeypatch.setattr(v, "CLASES_GARANTIA", clases)
    recargos = [(0, Decimal("10")), (1, Decimal("5")), (3, Decimal("1")),
                (4, Decimal("2")), (5, Decimal("7")), (None, Decimal("0.5"))]
    columnas = v.repartir_recargos(recargos)
    assert set(columnas) == set(v.CLASES_RECARGO)
    assert sum(columnas.values()) == sum(c for _, c in recargos)
    assert columnas["COEFICIENTES"] == Decimal("10")
    if 1 in clases:
        assert columnas["RETESP"] == 0 and columnas["GARANTIA"] == Decimal("14")
    else:
        assert columnas["RETESP"] == Decimal("5") and columnas["GARANTIA"] == Decimal("9")
    assert columnas["OTRAS"] == Decimal("1.5")


def test_f040_r11_reparto_vacio() -> None:
    assert v.repartir_recargos([]) == {c: Decimal("0") for c in v.CLASES_RECARGO}


# ===========================================================================
# R18 · estado_seguimiento (precedencia)
# ===========================================================================

D = Decimal


@pytest.mark.parametrize(("estado", "facturas", "efectos", "emitido", "cobrado", "esperado"), [
    (1, 3, 3, D("100"), D("100"), "BORRADOR"),             # pendiente de emisión
    (None, 1, 1, D("1"), D("1"), "BORRADOR"),
    (5, 1, 1, D("1"), D("1"), "BORRADOR"),
    (2, 0, 0, D("0"), D("0"), "SIN_FACTURA"),
    (3, 0, 5, D("10"), D("10"), "SIN_FACTURA"),           # sin factura manda sobre efectos
    (3, 1, 0, D("0"), D("0"), "FACTURADA_SIN_EFECTO"),    # (solo BAJA: no cuentan)
    (4, 2, 1, D("100"), D("0"), "PENDIENTE_COBRO"),
    (4, 2, 1, D("100"), D("-5"), "PENDIENTE_COBRO"),
    (3, 1, 2, D("100"), D("50"), "COBRADA_PARCIAL"),
    (3, 1, 2, D("100"), D("99.98"), "COBRADA_PARCIAL"),   # a más de un céntimo
    (3, 1, 2, D("100"), D("99.99"), "COBRADA"),           # dentro del céntimo
    (3, 1, 2, D("100"), D("100"), "COBRADA"),
    (3, 1, 2, D("100"), D("120"), "COBRADA"),
    (2, 1, 1, D("0"), D("3"), "COBRADA"),                 # emitido 0 y algo cobrado
    (2, 1, 1, D("0"), D("0"), "PENDIENTE_COBRO"),
])
def test_f040_r18_estado_seguimiento(
    estado: int | None, facturas: int, efectos: int, emitido: Decimal, cobrado: Decimal,
    esperado: str,
) -> None:
    assert v.estado_seguimiento(estado, facturas, efectos, emitido, cobrado) == esperado
    assert esperado in v.ESTADOS_SEGUIMIENTO


def test_f040_r18_estados_y_tolerancia() -> None:
    assert v.ESTADOS_SEGUIMIENTO == (
        "BORRADOR", "SIN_FACTURA", "FACTURADA_SIN_EFECTO", "PENDIENTE_COBRO",
        "COBRADA_PARCIAL", "COBRADA",
    )
    assert v.TOLERANCIA_COBRO == Decimal("0.01")


def test_f040_r18_none_en_importes_es_cero() -> None:
    assert v.estado_seguimiento(3, 1, 1, None, None) == "PENDIENTE_COBRO"
    assert v.estado_seguimiento(3, None, None, None, None) == "SIN_FACTURA"


# ===========================================================================
# La capa domain no importa nada de fuera
# ===========================================================================


def test_f040_dominio_sin_dependencias() -> None:
    import ast
    from pathlib import Path

    arbol = ast.parse(Path(v.__file__).read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            assert not nodo.module.startswith(("etl_sigrid.infrastructure", "config")), nodo.module
        if isinstance(nodo, ast.Import):
            for n in nodo.names:
                assert not n.name.startswith(("etl_sigrid", "config", "psycopg")), n.name
