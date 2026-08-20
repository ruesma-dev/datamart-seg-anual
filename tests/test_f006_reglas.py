# tests/test_f006_reglas.py
"""
F-006 · Tests de las reglas duras del diccionario (R9-R12) y de la batería de
aceptación (R39).

Las reglas duras son **la pieza de más valor por línea de toda la feature**: son
lo que impide que un agente devuelva un número plausible y falso. Casi todas
están escritas a partir de un error real —el que multiplicaba por nueve, el que
dio 38,9 M€ en una sola obra siendo esa la cifra de toda la empresa— y por eso
el validador exige `motivo` además de `regla`.

Ningún test de este fichero abre red ni BBDD.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.diccionario import (
    CODIGOS_REGLAS_OBLIGATORIAS,
    SEVERIDADES,
    Regla,
    derivar_avisos,
    validar,
)

from tests.test_f006_formato import (  # reutiliza las fábricas de fixtures
    PASOS_NOCTURNOS,
    _dicc,
    _ficha,
    _regla,
)


def _codigos(errores) -> set[str]:
    return {e.regla for e in errores}


# ---------------------------------------------------------------------------
# R9 · Las doce reglas duras
# ---------------------------------------------------------------------------


def test_f006_r9_son_doce_reglas_y_estas() -> None:
    """La lista es cerrada y explícita: si mañana se añade una, se ve en el diff."""
    assert len(CODIGOS_REGLAS_OBLIGATORIAS) == 12
    assert set(CODIGOS_REGLAS_OBLIGATORIAS) == {
        "R-FRESCURA-MANUAL",
        "R-IMPORTE-MES",
        "R-UNIVERSO-OBRA",
        "R-OBRA-ACTIVA",
        "R-VERSION-MASTER",
        "R-FAS-AMBIGUO",
        "R-CLAVE-SUSTITUTA",
        "R-ABONO-NEGATIVO",
        "R-LINEA-ID-NO-UNICA",
        "R-RETENCION-NO-JOIN-LINEAS",
        "R-COMPRAS-SIN-IVA",
        "R-COMPRAS-TIPO-DOC",
    }


@pytest.mark.parametrize("codigo", CODIGOS_REGLAS_OBLIGATORIAS)
def test_f006_r9_falta_una_regla_obligatoria_y_falla(codigo: str) -> None:
    """Quitar una regla del YAML deja al agente sin esa defensa. Es bloqueante."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS if c != codigo]

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert errores, f"faltando {codigo} tenía que fallar"
    assert any(codigo in e.detalle for e in errores), (
        f"el error no nombra la regla que falta: {errores}"
    )


def test_f006_r9_las_doce_completas_no_producen_error() -> None:
    assert validar(_dicc(), PASOS_NOCTURNOS) == []


@pytest.mark.parametrize("campo", ["titulo", "regla", "motivo"])
def test_f006_r9_una_regla_sin_texto_falla(campo: str) -> None:
    """`motivo` es obligatorio: una regla sin porqué se desobedece a la primera."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(CODIGOS_REGLAS_OBLIGATORIAS[0], **{campo: "  "})

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any(campo in e.detalle for e in errores), errores


def test_f006_r9_una_regla_sin_ambito_falla() -> None:
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(CODIGOS_REGLAS_OBLIGATORIAS[0], ambito=())

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("ambito" in e.detalle for e in errores)


@pytest.mark.parametrize("severidad", SEVERIDADES)
def test_f006_r9_las_severidades_del_vocabulario_validan(severidad: str) -> None:
    reglas = [_regla(c, severidad=severidad) for c in CODIGOS_REGLAS_OBLIGATORIAS]

    assert validar(_dicc(reglas=reglas), PASOS_NOCTURNOS) == []


def test_f006_r9_una_regla_duplicada_falla() -> None:
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas.append(_regla(CODIGOS_REGLAS_OBLIGATORIAS[0]))

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("duplicad" in e.detalle.lower() for e in errores)


# ---------------------------------------------------------------------------
# R11 · Un ámbito que apunta a la nada no protege nada
# ---------------------------------------------------------------------------


def test_f006_r11_una_regla_bloqueante_con_objeto_inexistente_falla() -> None:
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(
        CODIGOS_REGLAS_OBLIGATORIAS[0],
        severidad="bloqueante",
        ambito=("mart.objeto_que_no_existe",),
    )

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert errores
    assert any("mart.objeto_que_no_existe" in e.detalle for e in errores)
    assert "R11" in _codigos(errores)


def test_f006_r11_un_esquema_inexistente_en_el_ambito_tambien_falla() -> None:
    """`tesoreria` no existe todavía (es F-037): protegerlo sería protegar humo."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(CODIGOS_REGLAS_OBLIGATORIAS[0], ambito=("tesoreria",))

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("tesoreria" in e.detalle for e in errores)


def test_f006_r11_tambien_se_exige_a_las_reglas_de_aviso() -> None:
    """R11 solo obliga a las `bloqueante`; aquí se es más estricto a propósito.

    No hay ningún caso legítimo en el que una regla de aviso deba apuntar a un
    objeto inexistente, y dejarlo pasar convertiría `severidad: aviso` en la
    forma de colar un ámbito roto.
    """
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(
        CODIGOS_REGLAS_OBLIGATORIAS[0],
        severidad="aviso",
        ambito=("mart.objeto_que_no_existe",),
    )

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("mart.objeto_que_no_existe" in e.detalle for e in errores)


def test_f006_r11_un_ambito_de_esquema_valido_resuelve() -> None:
    reglas = [_regla(c, ambito=("mart", "cierre")) for c in CODIGOS_REGLAS_OBLIGATORIAS]

    assert validar(_dicc(reglas=reglas), PASOS_NOCTURNOS) == []


def test_f006_r11_un_ambito_de_objeto_existente_resuelve() -> None:
    reglas = [
        _regla(c, ambito=("mart.fact_seguimiento_mensual",))
        for c in CODIGOS_REGLAS_OBLIGATORIAS
    ]

    assert validar(_dicc(reglas=reglas), PASOS_NOCTURNOS) == []


# ---------------------------------------------------------------------------
# R12 · Los avisos se DERIVAN, no se escriben
# ---------------------------------------------------------------------------


def test_f006_r12_una_regla_de_esquema_alcanza_a_todas_sus_fichas() -> None:
    """El agente que solo consulte la ficha de un objeto ve sus trampas igual."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla("R-IMPORTE-MES", ambito=("mart",))

    derivado = derivar_avisos(_dicc(reglas=reglas))

    ficha = derivado.por_nombre["mart.fact_seguimiento_mensual"]
    assert "R-IMPORTE-MES" in ficha.avisos


def test_f006_r12_una_regla_de_objeto_solo_alcanza_a_ese_objeto() -> None:
    otra = _ficha(objeto="fact_seguimiento_categoria")
    reglas = [_regla(c, ambito=("cierre",)) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(
        "R-IMPORTE-MES", ambito=("mart.fact_seguimiento_mensual",)
    )

    derivado = derivar_avisos(_dicc(fichas=[_ficha(), otra], reglas=reglas))

    assert "R-IMPORTE-MES" in derivado.por_nombre["mart.fact_seguimiento_mensual"].avisos
    assert "R-IMPORTE-MES" not in derivado.por_nombre["mart.fact_seguimiento_categoria"].avisos


def test_f006_r12_los_avisos_salen_ordenados_y_sin_repetir() -> None:
    """Determinismo: la misma ficha publica siempre la misma lista de avisos."""
    reglas = [
        _regla(c, ambito=("mart", "mart.fact_seguimiento_mensual"))
        for c in CODIGOS_REGLAS_OBLIGATORIAS
    ]

    avisos = derivar_avisos(_dicc(reglas=reglas)).por_nombre[
        "mart.fact_seguimiento_mensual"
    ].avisos

    assert list(avisos) == sorted(set(avisos))
    assert len(avisos) == len(CODIGOS_REGLAS_OBLIGATORIAS)


def test_f006_r12_derivar_no_muta_el_diccionario_original() -> None:
    """Las entidades son inmutables: `derivar_avisos` devuelve uno nuevo."""
    dicc = _dicc()

    derivado = derivar_avisos(dicc)

    assert dicc.por_nombre["mart.fact_seguimiento_mensual"].avisos == ()
    assert derivado is not dicc


def test_f006_r12_derivar_conserva_el_resto_de_la_ficha() -> None:
    dicc = _dicc()

    derivado = derivar_avisos(dicc)

    antes = dicc.por_nombre["mart.fact_seguimiento_mensual"]
    despues = derivado.por_nombre["mart.fact_seguimiento_mensual"]
    assert despues.descripcion == antes.descripcion
    assert despues.columnas == antes.columnas
    assert despues.relaciones == antes.relaciones


def test_f006_r12_escribir_avisos_a_mano_es_un_error() -> None:
    """El autor de la ficha no tiene que acordarse; tampoco puede inventárselos."""
    a_mano = _ficha(avisos=("R-IMPORTE-MES",))

    errores = validar(_dicc(fichas=[a_mano]), PASOS_NOCTURNOS)

    assert errores
    assert any("avisos" in e.detalle for e in errores)
    assert "R12" in _codigos(errores)


def test_f006_r12_derivar_es_idempotente() -> None:
    """Publicar dos veces el mismo YAML tiene que dar exactamente lo mismo."""
    dicc = _dicc()

    una = derivar_avisos(dicc)
    dos = derivar_avisos(una)

    assert una.fichas == dos.fichas
