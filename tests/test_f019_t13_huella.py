# tests/test_f019_t13_huella.py
"""
F-019 · T13 · La huella no puede sumar claves sustitutas.

`mart.fact_seguimiento_mensual.fact_id` es un BIGSERIAL: se asigna por orden
de inserción y el build no lleva ORDER BY, así que dos máquinas con el MISMO
dato reparten los identificadores de otra forma. Sumarlo produce fallos falsos.

Medido en las huellas de T13 (local vs Azure), donde `sum_fact_id` era la
ÚNICA diferencia de esas dos vistas —mismo `count` y mismas sumas de negocio—:

    v_fact_periodificado · sum_fact_id  12.268.877.267.673 | 12.268.948.757.630
    v_pbi_fact           · sum_fact_id  12.268.877.267.673 | 12.268.948.757.630

Sin red ni BBDD: cliente falso, como en `tests/test_f005_verificacion.py`.
"""

from __future__ import annotations

from datetime import date

from etl_sigrid.infrastructure.postgres import fingerprint as fp


class _ClienteFalso:
    """Cliente de huella que expone las columnas que se le den."""

    def __init__(self, columnas: list[tuple]) -> None:
        self.columnas = columnas
        self.consultas: list[str] = []

    def list_view_columns(self, schemas: object) -> list[tuple]:
        return self.columnas

    def fetch_aggregates(self, query: str) -> tuple:
        self.consultas.append(query)
        return tuple(range(query.count("SUM(") + 1))


COLUMNAS_V_PBI_FACT = [
    ("mart", "v_pbi_fact", 1, "fact_id", "bigint"),
    ("mart", "v_pbi_fact", 2, "obra_id", "integer"),
    ("mart", "v_pbi_fact", 3, "partida_id", "integer"),
    ("mart", "v_pbi_fact", 4, "anio_mes", "date"),
    ("mart", "v_pbi_fact", 5, "importe_mes", "numeric"),
]


def test_f019_t13_la_huella_no_suma_las_claves_sustitutas() -> None:
    """
    Ni en el bloque vivo ni en el cerrado: `fact_id` no dice nada del dato, y
    lo que decía era mentira.
    """
    cliente = _ClienteFalso(COLUMNAS_V_PBI_FACT)

    metricas = fp.construir_huella(cliente, ["mart"], date(2026, 6, 1))

    assert "sum_fact_id" not in {m.metrica for m in metricas}
    assert all("fact_id" not in c for c in cliente.consultas), (
        "tampoco se pide a la BBDD: la SUM ni se llega a calcular"
    )


def test_f019_t13_las_claves_naturales_se_siguen_sumando() -> None:
    """
    `obra_id` y `partida_id` vienen de Sigrid y son estables entre máquinas:
    son señal buena y NO se excluyen. Excluir todo lo acabado en `_id` habría
    vaciado la huella de la mitad de su valor.
    """
    metricas = fp.construir_huella(_ClienteFalso(COLUMNAS_V_PBI_FACT), ["mart"])

    assert {"sum_obra_id", "sum_partida_id", "sum_importe_mes"} <= {
        m.metrica for m in metricas
    }


def test_f019_t13_las_sustitutas_siguen_en_el_bloque_estructura() -> None:
    """
    Dejan de sumarse, pero la estructura de la vista no cambia: si `fact_id`
    desaparece o cambia de tipo, eso sigue siendo un FALLO.
    """
    metricas = fp.construir_huella(_ClienteFalso(COLUMNAS_V_PBI_FACT), ["mart"])

    estructura = {m.valor for m in metricas if m.bloque == fp.BLOQUE_ESTRUCTURA}
    assert "fact_id:bigint" in estructura


def test_f019_t13_la_lista_de_sustitutas_es_explicita_y_cerrada() -> None:
    """
    La exclusión se nombra una a una, no se adivina por sufijo: cualquier
    heurística sobre `_id` se llevaría por delante las claves naturales.
    """
    assert {"fact_id", "fact_cat_id"} <= set(fp.COLUMNAS_SUSTITUTAS)
    assert not {"obra_id", "partida_id", "albaran_id", "proveedor_id"} & set(
        fp.COLUMNAS_SUSTITUTAS
    )


def test_f019_t13_una_vista_solo_de_sustitutas_conserva_su_recuento() -> None:
    """Sin columnas que sumar sigue habiendo `count`: la vista no desaparece."""
    cliente = _ClienteFalso([("mart", "v_x", 1, "fact_id", "bigint")])

    metricas = fp.construir_huella(cliente, ["mart"])

    assert [m.metrica for m in metricas if m.bloque == fp.BLOQUE_VIVO] == [
        fp.METRICA_COUNT
    ]


def test_f019_t13_la_exclusion_no_depende_del_tipo_ni_de_la_vista() -> None:
    """
    Una sustituta se excluye se llame como se llame la vista y venga como
    venga tipada (bigint aquí, numeric en una vista que la agregue).
    """
    columnas = [
        ("mart", "v_pbi_fact_categoria", 1, "fact_cat_id", "bigint"),
        ("mart", "v_pbi_fact_categoria", 2, "importe_mes", "numeric"),
        ("cierre", "v_otra", 1, "fact_cat_id", "numeric"),
        ("cierre", "v_otra", 2, "importe", "numeric"),
    ]

    metricas = fp.construir_huella(_ClienteFalso(columnas), ["mart", "cierre"])

    assert not [m for m in metricas if m.metrica == "sum_fact_cat_id"]
    assert len([m for m in metricas if m.metrica == "sum_importe_mes"]) == 1
    assert len([m for m in metricas if m.metrica == "sum_importe"]) == 1
