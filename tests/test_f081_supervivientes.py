# tests/test_f081_supervivientes.py
"""
F-081 · Los dos supervivientes de la campaña de F-073 que sí eran de código
(criterios 4, 5 y 6).

**Un agujero de test se tapa escribiendo tests, no cambiando el código que se
prueba.** Ninguno de los dos sitios que vigila este fichero se toca: ni
`ventana_sql.py` ni `build_stg_step.py`. Aquí solo se añaden los asertos que
faltaban.

Nota medida el 2026-09-11, porque una premisa equivocada se propaga: el sello
de F-025 **no incluye este módulo**. `sello_vigente_del_repositorio` lo calcula
con `sello_sql` sobre `FICHEROS_DEL_SELLO`, que son dos `.sql` —
`06_presupuesto.sql` y `08_plan_mensual.sql`— más un parámetro de
`business_rules`. Cambiar el texto de `build_stg_step.py` no movería el sello
ni reconstruiría las 921 obras; la razón para no tocarlo es la de arriba, que
es mejor razón.

Los dos casos, tal y como los describe `progress/mutacion_F-073.md`:

1. **`ventana_sql.py:215`** — `codigo_obra=str(codigo or "")` en la denuncia
   de sello no vigente. Sobrevivía porque `test_f025_r26_un_sello_viejo_se_
   denuncia` comprueba que la palabra `SELLO` sale en el informe **y no mira
   qué obra se nombra**: con `codigo and ""` la denuncia sale sin código y el
   test pasa igual. Una alerta que no dice qué obra obliga a la arqueología
   que la alerta existía para evitar.
2. **`build_stg_step.py:732`** — la guarda `self._plan and self._plan.completa`
   del presupuesto acotado. **Medido el 2026-09-11: ese mutante ya NO
   sobrevive**; muere contra la suite entera, con los argumentos del propio
   arnés, en 157,7 s, a manos de `test_f025_r10_las_sobrantes_solo_se_miran_
   en_la_reconstruccion_completa`. Se añade igualmente el test directo, porque
   aquel lo caza de rebote —por una lista de llamadas al doble— y una sola
   línea indirecta es poca red para una guarda que decide si la noche acotada
   denuncia las 880 obras congeladas.

Ningún test de este fichero abre red ni BBDD: dominio puro y un doble de
`PostgresClient` que no sabe conectarse.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    BuildStgStep,
)
from etl_sigrid.domain.ventana import (
    TIPO_CONGELADA_SIN_FILAS,
    TIPO_FIRMA_DIVERGENTE,
    TIPO_SELLO_NO_VIGENTE,
    Decision,
    Plan,
)
from etl_sigrid.infrastructure.postgres.ventana_sql import hallazgos_de
from tests.test_f019_tramos import settings_falsos

# ---------------------------------------------------------------------------
# Criterio 4 · la denuncia dice QUÉ obra, en los tres tipos
# ---------------------------------------------------------------------------

#: Una fila de cada consulta, con el mismo código de obra en las tres, para que
#: el test no pueda pasar por casualidad de qué lista se lee.
CONSTRUIDA = datetime(2026, 8, 20, 2, 15)


def _una_de_cada() -> tuple:
    return (
        [(1442383, "0599", CONSTRUIDA, datetime(2026, 9, 3))],
        [(1442384, "0710", CONSTRUIDA, "ventana")],
        [(1442385, "0806", CONSTRUIDA, "a" * 64)],
    )


@pytest.mark.parametrize(
    ("tipo", "codigo"),
    [
        (TIPO_FIRMA_DIVERGENTE, "0599"),
        (TIPO_CONGELADA_SIN_FILAS, "0710"),
        (TIPO_SELLO_NO_VIGENTE, "0806"),
    ],
)
def test_f081_c4_cada_denuncia_de_la_ventana_nombra_su_obra(
    tipo: str, codigo: str
) -> None:
    """**El aserto que le faltaba a `ventana_sql`.**

    Los tres hallazgos construyen el código igual, `str(codigo or "")`, y los
    tres podían quedarse mudos sin que nada fallara. El de sello era el único
    que ningún test miraba; los otros dos entran aquí porque el modo de fallo
    es el mismo y sale igual de barato cerrarlo en los tres.
    """
    hallazgos = hallazgos_de(*_una_de_cada())
    del_tipo = [h for h in hallazgos if h.tipo == tipo]

    assert len(del_tipo) == 1, f"un hallazgo de {tipo}"
    assert del_tipo[0].codigo_obra == codigo, (
        f"la denuncia de {tipo} tiene que decir QUE obra es. Sin el codigo, "
        f"quien recibe la alerta no sabe donde mirar"
    )


def test_f081_c4_una_obra_sin_codigo_se_denuncia_igual_y_sin_reventar() -> None:
    """La otra mitad de `str(codigo or "")`: el `or` está para que un código a
    `NULL` no se convierta en la cadena `"None"` ni tumbe la denuncia. Sin este
    caso, el aserto de arriba se podría satisfacer con un `str(codigo)` pelado.
    """
    hallazgos = hallazgos_de([], [], [(1442385, None, CONSTRUIDA, "a" * 64)])

    assert len(hallazgos) == 1
    assert hallazgos[0].codigo_obra == "", "sin código, cadena vacía y no «None»"
    assert hallazgos[0].obra_id == 1442385, "y la obra se sigue pudiendo localizar"


# ---------------------------------------------------------------------------
# Criterio 5 · la noche acotada no mira las obras sobrantes
# ---------------------------------------------------------------------------


class PgDelPresupuesto:
    """Doble mínimo para `_build_presupuesto_acotado`. **No sabe conectarse.**

    Apunta si le preguntan por las obras sobrantes, que es lo único que
    distingue los dos caminos de la guarda.
    """

    def __init__(self) -> None:
        self.sobrantes_pedidas: list[str] = []
        self.sql_ejecutado: list[str] = []
        self.registradas: list[dict] = []

    def execute_sql_text(self, sql_text: str) -> int:
        self.sql_ejecutado.append(sql_text)
        return 700

    def fetch_obras_con_filas(self, tabla: str) -> set[int]:
        self.sobrantes_pedidas.append(tabla)
        return {1, 2, 9}

    def fetch_filas_por_obra(self, tabla: str, obras) -> dict[int, int]:
        return {int(o): 100 for o in obras}

    def registrar_obras_construidas(self, registros) -> int:
        self.registradas.extend(registros)
        return len(registros)


def _paso_con_plan(completa: bool) -> tuple[BuildStgStep, PgDelPresupuesto]:
    paso = BuildStgStep(settings_falsos())  # type: ignore[arg-type]
    paso._plan = Plan(
        reconstruir=(
            Decision(1, "0599", True, "ventana", "activa"),
            Decision(2, "0710", True, "ventana", "activa"),
        ),
        congelar=(Decision(9, "0806", False, "congelada", "sin actividad"),),
        sello_vigente="s" * 64,
        completa=completa,
    )
    return paso, PgDelPresupuesto()


def test_f081_c5_el_presupuesto_acotado_con_plan_PARCIAL_no_mira_las_sobrantes() -> (  # noqa: N802
    None
):
    """**El test directo de la guarda de la línea 732.**

    En una noche acotada, «no está en el conjunto» significa «está congelada»,
    que es lo contrario de «sobra»: mirarlo aquí denunciaría las 880 congeladas
    todas las noches y entrenaría a todo el mundo a ignorar el aviso. Con la
    conjunción cambiada por una disyunción, cualquier plan —y siempre hay
    plan— dispararía la denuncia.
    """
    paso, pg = _paso_con_plan(completa=False)

    filas = paso._build_presupuesto_acotado(
        pg, DIRECTORIO_SQL_STG / "06_presupuesto.sql"
    )

    assert filas == 700, "el presupuesto se construye igual"
    assert pg.sobrantes_pedidas == [], (
        "con un plan PARCIAL no se pregunta por las obras sobrantes: lo que no "
        "entra esta noche está congelado, no sobra"
    )
    assert [r["obra_id"] for r in pg.registradas] == [1, 2], (
        "y las dos obras del plan quedan registradas en _meta.obra_build"
    )


def test_f081_c5_pero_en_la_reconstruccion_COMPLETA_si_las_mira() -> None:  # noqa: N802
    """La otra dirección, sin la cual el test de arriba se cumpliría quitando
    la denuncia entera: la noche completa es la única en la que «no está en el
    conjunto» significa algo, y ahí sí se nombran las sobrantes."""
    paso, pg = _paso_con_plan(completa=True)

    paso._build_presupuesto_acotado(pg, DIRECTORIO_SQL_STG / "06_presupuesto.sql")

    assert pg.sobrantes_pedidas == ["presupuesto"], (
        "la noche completa sí mira qué obras tienen filas y no están en el censo"
    )


def test_f081_c5_sin_plan_no_se_toca_la_tabla_ni_se_pregunta_nada() -> None:
    """El tercer caso de la guarda, que es el que hace que la mutación no
    reviente sola: sin plan no hay obras, y sin obras el sub-paso ni ejecuta el
    SQL (R9). Si algún día `_obras_a_reconstruir` devolviera «todas» ante la
    duda, esto se pondría en rojo."""
    paso = BuildStgStep(settings_falsos())  # type: ignore[arg-type]
    pg = PgDelPresupuesto()

    filas = paso._build_presupuesto_acotado(
        pg, DIRECTORIO_SQL_STG / "06_presupuesto.sql"
    )

    assert filas == 0
    assert pg.sql_ejecutado == [], "con el conjunto vacío no se toca la tabla (R9)"
    assert pg.sobrantes_pedidas == []
