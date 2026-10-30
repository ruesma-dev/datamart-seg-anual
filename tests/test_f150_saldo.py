# tests/test_f150_saldo.py
"""
F-150 · El saldo de partida (N14, R38-R40) y el IVA ya recuperado (N15, R43).

La caja de una obra no empieza en cero: lo cobrado menos lo pagado hasta hoy
(CON IVA, efectos REALIZADO) es el PASO 0 de la receta, SALDO. Es opcional (H28)
y los pagarés agrupados (AGR) pierden la obra: H29 elige entre contarlos por
sus ORIGINALES o por el AGR que conserva obra. Primero el catálogo (R39);
después el SQL de `10_saldo_partida.sql`, leído como texto (R38, R43).
"""

from __future__ import annotations

from pathlib import Path

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import Hipotesis
from etl_sigrid.infrastructure.config import hipotesis_caja_yaml as lector

RAIZ = Path(__file__).resolve().parents[1]
RUTA_YAML = RAIZ / "config" / "hipotesis_caja.yaml"


def _catalogo() -> dict[str, Hipotesis]:
    leido = lector.cargar_hipotesis_caja(RUTA_YAML)
    assert leido.errores == []
    return {h.codigo: h for h in leido.catalogo}


def _texto(h: Hipotesis) -> str:
    return " ".join(f"{h.descripcion} {h.fuente_defecto}".split())


# ===========================================================================
# R39 · el paso SALDO, H28 y H29
# ===========================================================================


def test_f150_r39_saldo_es_el_primer_paso_y_son_ocho() -> None:
    assert dom.PASOS_RECETA[0] == "SALDO"
    assert len(dom.PASOS_RECETA) == 8
    assert dom.PASOS_RECETA[1:] == (
        "DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA", "CARTERA",
    )


def test_f150_r39_h28_el_saldo_de_partida_es_opcional() -> None:
    h = _catalogo()["H28"]
    assert (h.sentido, h.unidad, h.valor_defecto, h.opciones) == (
        "AMBOS", "OPCION", "CON_SALDO", ("CON_SALDO", "SIN_SALDO"),
    )
    assert (h.paso_receta, h.admite_obra, h.validado) == ("SALDO", True, False)
    assert h.ingrediente == "tesoreria.saldo_partida_obra"
    assert "CON IVA" in _texto(h) and "cartera vencida" in _texto(h)


def test_f150_r39_h29_los_agrupados_por_sus_originales() -> None:
    h = _catalogo()["H29"]
    assert (h.sentido, h.unidad, h.valor_defecto, h.opciones) == (
        "PAGO", "OPCION", "ORIGINALES", ("ORIGINALES", "AGR"),
    )
    assert (h.paso_receta, h.admite_obra, h.validado) == ("SALDO", True, False)
    assert h.ingrediente == "tesoreria.saldo_partida_obra"
    texto = _texto(h)
    assert "R-TESORERIA-ESTADO" in texto, "rompe la regla a proposito y se declara"
    assert "1,32" in texto and "0,27" in texto, "lo medido en la 0686"


def test_f150_r39_son_29_en_su_orden() -> None:
    assert list(_catalogo())[:29] == [f"H{n:02d}" for n in range(1, 30)]
