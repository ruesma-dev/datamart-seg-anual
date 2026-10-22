# tests/test_f147_presupuesto_contexto.py
"""
F-147 · La puerta de tamaño del contexto del MCP (R17-R20).

`contexto_bbdd()` de `mcp-bbdd` se sirve ENTERO en cada conversación, antes de
la primera pregunta, y se queda en el historial de todos los mensajes
siguientes. Con la v58 eran ~86.000 caracteres. Esta puerta mide desde los
YAML —sin red ni BBDD— lo que se servirá entero, y falla si crece en silencio.

Qué se mide (R17), con la misma lectura que publica (`filas_contexto`):

* reglas publicables: `codigo + titulo + resumen`, y `regla + motivo` de las
  `entera`;
* enrutado: `esquema.objeto` y sus 2 primeras `ejemplos_preguntas`, por ficha
  recomendada (`MAX_PREGUNTAS_ENRUTADO`, contrato con `mcp-bbdd`);
* el `texto` de todas las filas de `_meta.diccionario_contexto`.

Qué NO se mide: los rótulos y epígrafes de `mcp-bbdd`, que son suyos y
constantes. El tope se fija sobre esta misma medida: compara igual con igual.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from etl_sigrid.domain import diccionario as dominio
from etl_sigrid.domain.diccionario import (
    HOLGURA_TRINQUETE,
    MAX_PREGUNTAS_ENRUTADO,
    PresupuestoContexto,
    presupuesto_contexto,
    veredicto_presupuesto,
)
from tests.test_f006_formato import _dicc, _ficha, _regla

#: EL TOPE de lo que `contexto_bbdd` sirve entero, en caracteres, con la
#: fórmula de R17. Solo baja (trinquete: R19 falla si sobra más de
#: `HOLGURA_TRINQUETE`). Historia, de la más reciente a la más antigua:
#:
#: * 29.513 · 2026-10-22, F-147 T12 (diccionario v59): reglas 7.107 (20
#:   publicadas; `R-PERFILES` entera), enrutado 13.901 (114 fichas, 2 preguntas
#:   cada una como mucho), bloques 8.505 (`esquemas` 5.931). Antes de F-147,
#:   con la misma fórmula y lo que servía el MCP de entonces (reglas enteras,
#:   todas las preguntas): 78.057.
#: * 29.787 · 2026-10-22, F-147 T5: PROVISIONAL, la medida de T2 sobre la v58
#:   (sin resúmenes todavía: reglas 2.233, enrutado 13.886, bloques 13.668).
PRESUPUESTO_MAX = 29_513


def _medir(dicc) -> PresupuestoContexto:
    """La medida con la MISMA función que publica los bloques (no otra lectura)."""
    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_contexto

    return presupuesto_contexto(dicc, [fila[3] for fila in filas_contexto(dicc)])


def _diccionario_real():
    from tests.test_f006_publicacion import _diccionario_real as real

    return real()[0]


# ---------------------------------------------------------------------------
# R17 · Qué se mide
# ---------------------------------------------------------------------------


def test_f147_r17_el_enrutado_son_dos_preguntas_por_objeto() -> None:
    """D8: el número es contrato con `mcp-bbdd` (lo recorta su F-029)."""
    assert MAX_PREGUNTAS_ENRUTADO == 2


def test_f147_r17_las_reglas_cuentan_resumen_y_las_enteras_todo() -> None:
    resumen = _regla("R-A", titulo="Tit A", resumen="r" * 50)
    entera = _regla("R-BB", titulo="Tit B", resumen="s" * 60, regla="x" * 70, motivo="y" * 80)
    entera = replace(entera, entrega="entera")
    fuera = replace(_regla("R-CCC", resumen="t" * 90, regla="z" * 500), entrega="fuera_mcp")

    medida = presupuesto_contexto(_dicc(fichas=[], reglas=[resumen, entera, fuera]), [])

    assert medida.reglas == (3 + 5 + 50) + (4 + 5 + 60 + 70 + 80)
    assert medida.enrutado == 0 and medida.bloques == 0


def test_f147_r17_el_enrutado_cuenta_clave_y_dos_primeras_de_las_recomendadas() -> None:
    preguntas = ("p" * 30, "q" * 31, "r" * 32)
    recomendada = _ficha(objeto="uno", ejemplos_preguntas=preguntas)
    otra = _ficha(objeto="dos", ejemplos_preguntas=("s" * 40,))
    no_recomendada = _ficha(
        objeto="tres", consumo_recomendado=False, ejemplos_preguntas=("t" * 50,)
    )

    medida = presupuesto_contexto(
        _dicc(fichas=[recomendada, otra, no_recomendada], reglas=[]), []
    )

    assert medida.enrutado == (len("mart.uno") + 30 + 31) + (len("mart.dos") + 40)


def test_f147_r17_los_bloques_cuentan_su_texto_entero() -> None:
    medida = presupuesto_contexto(_dicc(fichas=[], reglas=[]), ["abc", "de", ""])

    assert medida.bloques == 5
    assert medida.total == 5


def test_f147_r17_el_total_es_la_suma_de_las_tres_partes() -> None:
    assert PresupuestoContexto(reglas=1, enrutado=20, bloques=300).total == 321


# ---------------------------------------------------------------------------
# R18, R19 · El veredicto de la puerta
# ---------------------------------------------------------------------------


def test_f147_r18_por_encima_del_tope_dice_cuanto_sobra_y_el_desglose() -> None:
    medida = PresupuestoContexto(reglas=6_000, enrutado=14_000, bloques=9_000)

    mensaje = veredicto_presupuesto(medida, tope=28_500)

    assert mensaje is not None
    assert "500" in mensaje, "cuánto sobra"
    for parte, cifra in (("reglas", "6000"), ("enrutado", "14000"), ("bloques", "9000")):
        assert parte in mensaje and cifra in mensaje.replace(".", ""), mensaje


def test_f147_r18_en_el_tope_justo_pasa() -> None:
    medida = PresupuestoContexto(reglas=1, enrutado=2, bloques=3)

    assert veredicto_presupuesto(medida, tope=6) is None


def test_f147_r19_con_mas_holgura_que_la_permitida_pide_bajar_el_tope() -> None:
    medida = PresupuestoContexto(reglas=0, enrutado=0, bloques=10_000)

    mensaje = veredicto_presupuesto(medida, tope=10_000 + HOLGURA_TRINQUETE + 1)

    assert mensaje is not None and "baja" in mensaje.lower(), mensaje
    assert "10000" in mensaje.replace(".", ""), "dice a cuánto bajarlo"


def test_f147_r19_la_holgura_justa_pasa() -> None:
    medida = PresupuestoContexto(reglas=0, enrutado=0, bloques=10_000)

    assert veredicto_presupuesto(medida, tope=10_000 + HOLGURA_TRINQUETE) is None
    assert HOLGURA_TRINQUETE == 1_000


# ---------------------------------------------------------------------------
# R20 · Un bloque nuevo del contexto cuenta solo
# ---------------------------------------------------------------------------


def test_f147_r20_un_bloque_nuevo_de_diccionario_contexto_cuenta(monkeypatch) -> None:
    """Se mide con `filas_contexto`, que DERIVA los bloques de
    `CONTEXTO_PUBLICADO`: publicar uno nuevo lo suma sin tocar la puerta."""
    real = _diccionario_real()
    antes = _medir(real)

    publicado = dict(dominio.CONTEXTO_PUBLICADO, bloque_de_prueba="Un bloque nuevo.")
    monkeypatch.setattr(dominio, "CONTEXTO_PUBLICADO", publicado)
    import etl_sigrid.infrastructure.postgres.diccionario_sql as publicacion

    monkeypatch.setattr(publicacion, "CONTEXTO_PUBLICADO", publicado)
    texto = "x" * 1_234
    despues = _medir(
        replace(real, global_raw={**real.global_raw, "bloque_de_prueba": {"una": texto}})
    )

    assert despues.bloques - antes.bloques == len(f"una: {texto}")
    assert despues.total > antes.total


# ---------------------------------------------------------------------------
# LA PUERTA sobre el diccionario del árbol
# ---------------------------------------------------------------------------


def test_f147_r18_r19_el_contexto_del_arbol_cabe_en_su_tope() -> None:
    medida = _medir(_diccionario_real())

    mensaje = veredicto_presupuesto(medida, tope=PRESUPUESTO_MAX)

    assert mensaje is None, mensaje


@pytest.mark.parametrize("parte", ["reglas", "enrutado", "bloques"])
def test_f147_r17_ninguna_parte_del_arbol_mide_cero(parte: str) -> None:
    """Una medida a cero es una puerta ciega: lo que no se mide no se frena."""
    assert getattr(_medir(_diccionario_real()), parte) > 0
