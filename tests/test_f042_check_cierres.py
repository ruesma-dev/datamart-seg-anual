# tests/test_f042_check_cierres.py
"""
F-042 · `python main.py check-cierres` (R16, R17).

La comprobación de solo lectura que contrasta, obra a obra, lo que hay en
`stg.plan_mensual` contra lo que el oráculo de `domain/cierres.py` dice que
debería haber: qué cierre manda cada mes, que no queda más de uno, y que el
telescopio `SUM(importe_mes) = último importe_origen` se sigue cumpliendo.

**Por qué el contraste vale algo.** El oráculo no lee `plan_mensual`: recompone
los candidatos desde `stg.presupuesto` ⨝ `stg.fases`, que es de donde sale
`reales_base`. Así que compara dos caminos independientes —el SQL del build y la
regla escrita en Python— y una discrepancia significa que uno de los dos está
mal. Si el oráculo fuera una traducción del SQL, esto no probaría nada.

Aquí no se abre ninguna conexión: el cliente es un doble que sirve filas
enlatadas y **estalla si alguien intenta escribir**.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.cierres import (
    agrupar,
    contrastar,
    hay_hueco_de_origen,
    orden_de_los_publicados,
)
from etl_sigrid.infrastructure.postgres.cierres_sql import (
    AMBITOS_REALES,
    PALABRAS_DE_ESCRITURA,
    formatear_discrepancias,
    sql_cierres_candidatos,
    sql_cierres_publicados,
    sql_telescopio,
)

FEBRERO = date(2018, 2, 1)
ENERO = date(2018, 1, 1)
MARZO = date(2018, 3, 1)

#: La 0499 · VILLANUEVA en Coste Real: cuatro fases, dos colisiones. Es la obra
#: con la que se verificó a mano la decisión de Negocio.
OBRA_0499 = 584748 + 1  # un obra_id cualquiera; lo que importa es la forma
AMBITO_COSTE = 3

CANDIDATOS_0499 = (
    (OBRA_0499, AMBITO_COSTE, ENERO, 18, Decimal("3608280.89")),
    (OBRA_0499, AMBITO_COSTE, ENERO, 19, Decimal("4712823.94")),
    (OBRA_0499, AMBITO_COSTE, FEBRERO, 20, Decimal("5065310.42")),
    (OBRA_0499, AMBITO_COSTE, FEBRERO, 21, Decimal("5688073.92")),
    (OBRA_0499, AMBITO_COSTE, MARZO, 22, Decimal("7400000.00")),
)

#: Lo que `stg.plan_mensual` debe tener después del build: solo los vigentes.
PUBLICADO_CONFORME = (
    (OBRA_0499, AMBITO_COSTE, ENERO, 19, Decimal("4712823.94")),
    (OBRA_0499, AMBITO_COSTE, FEBRERO, 21, Decimal("5688073.92")),
    (OBRA_0499, AMBITO_COSTE, MARZO, 22, Decimal("7400000.00")),
)


# ---------------------------------------------------------------------------
# El contraste, en dominio puro
# ---------------------------------------------------------------------------


def test_f042_r17_una_obra_conforme_no_produce_ninguna_discrepancia():
    discrepancias = contrastar(
        agrupar(CANDIDATOS_0499), agrupar(PUBLICADO_CONFORME)
    )

    assert discrepancias == ()


def test_f042_r17_dos_cierres_en_el_mismo_mes_se_reportan_con_obra_mes_y_fases():
    """El estado de HOY: el build todavía publica las dos fases de febrero."""
    publicado = (*PUBLICADO_CONFORME, (OBRA_0499, AMBITO_COSTE, FEBRERO, 20, Decimal("5065310.42")))

    discrepancias = contrastar(agrupar(CANDIDATOS_0499), agrupar(publicado))

    assert len(discrepancias) == 1
    d = discrepancias[0]
    assert d.obra_id == OBRA_0499
    assert d.ambito_id == AMBITO_COSTE
    assert d.anio_mes == FEBRERO
    assert d.publicado == (20, 21)
    assert d.esperado == (21,)
    assert "mas de un cierre" in d.motivo


def test_f042_r17_publicar_el_cierre_equivocado_se_reporta():
    """Un solo cierre por mes, pero el que no era: el defecto que un `SELECT
    count(*)` no vería."""
    publicado = (
        (OBRA_0499, AMBITO_COSTE, ENERO, 19, Decimal("4712823.94")),
        (OBRA_0499, AMBITO_COSTE, FEBRERO, 20, Decimal("5065310.42")),
        (OBRA_0499, AMBITO_COSTE, MARZO, 22, Decimal("7400000.00")),
    )

    discrepancias = contrastar(agrupar(CANDIDATOS_0499), agrupar(publicado))

    assert len(discrepancias) == 1
    assert discrepancias[0].publicado == (20,)
    assert discrepancias[0].esperado == (21,)


def test_f042_r11_quedarse_con_el_cierre_a_cero_se_reporta():
    """0606 · PUY DU FOU: si el build eligiera la fase 16, esto lo caza."""
    obra = 1251489
    mes = date(2021, 2, 1)
    candidatos = (
        (obra, AMBITO_COSTE, mes, 14, Decimal("9053263.61")),
        (obra, AMBITO_COSTE, mes, 16, Decimal("0.00")),
    )
    publicado = ((obra, AMBITO_COSTE, mes, 16, Decimal("0.00")),)

    discrepancias = contrastar(agrupar(candidatos), agrupar(publicado))

    assert len(discrepancias) == 1
    assert discrepancias[0].esperado == (14,)


def test_f042_r17_un_mes_que_desaparece_entero_se_reporta():
    """Descartar de más es tan grave como descartar de menos, y un recuento de
    duplicados no lo vería: se quedaría en cero, tan contento."""
    publicado = tuple(f for f in PUBLICADO_CONFORME if f[2] != FEBRERO)

    discrepancias = contrastar(agrupar(CANDIDATOS_0499), agrupar(publicado))

    assert len(discrepancias) == 1
    assert discrepancias[0].anio_mes == FEBRERO
    assert discrepancias[0].publicado == ()


def test_f042_r17_un_mes_publicado_sin_candidato_se_reporta():
    """`plan_mensual` con un mes que `stg.presupuesto` no sostiene."""
    publicado = (
        *PUBLICADO_CONFORME,
        (OBRA_0499, AMBITO_COSTE, date(2018, 4, 1), 23, Decimal("1.00")),
    )

    discrepancias = contrastar(agrupar(CANDIDATOS_0499), agrupar(publicado))

    assert len(discrepancias) == 1
    assert discrepancias[0].anio_mes == date(2018, 4, 1)
    assert discrepancias[0].esperado == ()


def test_f042_r17_las_obras_conformes_no_ensucian_el_informe():
    """Con 500 obras bien y una mal, el informe nombra a una."""
    candidatos = list(CANDIDATOS_0499)
    publicado = list(PUBLICADO_CONFORME)
    for obra in range(900000, 900500):
        candidatos.append((obra, AMBITO_COSTE, ENERO, 1, Decimal("10.00")))
        publicado.append((obra, AMBITO_COSTE, ENERO, 1, Decimal("10.00")))
    publicado.append((OBRA_0499, AMBITO_COSTE, FEBRERO, 20, Decimal("5065310.42")))

    discrepancias = contrastar(agrupar(candidatos), agrupar(publicado))

    assert len(discrepancias) == 1
    assert discrepancias[0].obra_id == OBRA_0499


def test_f042_el_contraste_separa_los_ambitos():
    """Coste y Venta se deciden por separado: una obra puede colisionar en uno y
    no en el otro."""
    candidatos = (
        *CANDIDATOS_0499,
        (OBRA_0499, 7, ENERO, 18, Decimal("3000000.00")),
        (OBRA_0499, 7, ENERO, 19, Decimal("3881439.76")),
    )
    publicado = (
        *PUBLICADO_CONFORME,
        (OBRA_0499, 7, ENERO, 18, Decimal("3000000.00")),
    )

    discrepancias = contrastar(agrupar(candidatos), agrupar(publicado))

    assert len(discrepancias) == 1
    assert discrepancias[0].ambito_id == 7
    assert discrepancias[0].esperado == (19,)


def test_f042_r17_el_informe_nombra_obra_mes_y_cierres():
    publicado = (*PUBLICADO_CONFORME, (OBRA_0499, AMBITO_COSTE, FEBRERO, 20, Decimal("1.00")))
    discrepancias = contrastar(agrupar(CANDIDATOS_0499), agrupar(publicado))

    informe = formatear_discrepancias(discrepancias)

    assert str(OBRA_0499) in informe
    assert "2018-02" in informe
    assert "20" in informe and "21" in informe


# ---------------------------------------------------------------------------
# Las consultas: solo lectura y con el grano correcto
# ---------------------------------------------------------------------------

CONSTRUCTORES = (sql_cierres_candidatos, sql_cierres_publicados, sql_telescopio)


@pytest.mark.parametrize("constructor", CONSTRUCTORES, ids=lambda c: c.__name__)
def test_f042_r17_ninguna_consulta_escribe(constructor):
    """Contra `psql-albaranes-rs9k2`, que es producción y lo comparten
    `albaranes` y `partes`. La transacción va READ ONLY, pero el texto tampoco
    puede intentarlo."""
    texto = constructor().upper()

    for palabra in PALABRAS_DE_ESCRITURA:
        assert not re.search(rf"\b{palabra}\b", texto), f"{palabra} en la consulta"


@pytest.mark.parametrize("constructor", CONSTRUCTORES, ids=lambda c: c.__name__)
def test_f042_r17_ninguna_consulta_sale_de_los_ambitos_reales(constructor):
    """Los master (8, 11) no se tocan: ni para arreglarlos ni para mirarlos."""
    assert "ambito_id IN (3, 7)" in constructor()


@pytest.mark.parametrize("constructor", CONSTRUCTORES, ids=lambda c: c.__name__)
def test_f042_el_filtro_de_obras_es_opcional_y_solo_admite_enteros(constructor):
    con_filtro = constructor(obras=(584748, 950302))

    assert "584748" in con_filtro
    assert "950302" in con_filtro
    assert "obra_id IN" in con_filtro
    assert "obra_id IN" not in constructor()

    with pytest.raises(ValueError):
        constructor(obras=("584748; DROP TABLE stg.plan_mensual",))


def test_f042_r17_los_candidatos_no_leen_de_plan_mensual():
    """El oráculo tiene que ser INDEPENDIENTE del objeto que audita.

    Si los candidatos salieran de `stg.plan_mensual`, la comprobación se estaría
    preguntando a sí misma: por construcción no habría nunca un descarte que
    señalar y el verde no significaría nada.
    """
    texto = sql_cierres_candidatos()

    assert "plan_mensual" not in texto
    assert "stg.presupuesto" in texto
    assert "stg.fases" in texto


def test_f042_r17_los_candidatos_reproducen_el_filtro_de_reales_base():
    """Mismo universo que `reales_base`: si el oráculo mirara más filas o menos,
    inventaría discrepancias que el build no tiene."""
    texto = sql_cierres_candidatos()

    assert "fase_num >= 1" in texto
    assert "anio IS NOT NULL" in texto
    assert "mes  IS NOT NULL" in texto or "mes IS NOT NULL" in texto


def test_f042_r16_el_telescopio_aparta_las_series_con_hueco_de_origen():
    """Una serie con un hueco que la regla NO creó no telescopea, y tampoco
    telescopeaba antes. Contarla como rota sería una alarma falsa; callarla,
    una omisión. Se cuenta aparte."""
    texto = sql_telescopio()

    assert "con_hueco" in texto
    assert "SUM(importe_mes)" in texto


def test_f042_los_ambitos_reales_son_los_dos_de_siempre():
    assert AMBITOS_REALES == (3, 7)


# ---------------------------------------------------------------------------
# El comando, contra un cliente falso
# ---------------------------------------------------------------------------


class PgFalso:
    """Sirve filas enlatadas y estalla si le piden escribir.

    El reparto se hace por el texto de la consulta, no por el orden de llamada:
    así el test no se rompe si el comando reordena sus lecturas.
    """

    def __init__(self, candidatos, publicados, telescopio=(0, 0, 0)):
        self._candidatos = list(candidatos)
        self._publicados = list(publicados)
        self._telescopio = telescopio
        self.consultas: list[str] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.consultas.append(sql_text)
        if "plan_mensual" not in sql_text:
            return self._candidatos
        if "importe_mes" in sql_text:
            return [self._telescopio]
        return self._publicados

    def __getattr__(self, nombre: str):
        raise AssertionError(
            f"`check-cierres` es de solo lectura y ha llamado a pg.{nombre}"
        )


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    def _con(pg):
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        return CliRunner()

    return _con


def test_f042_r17_el_comando_sale_0_cuando_todo_cuadra(cli):
    pg = PgFalso(CANDIDATOS_0499, PUBLICADO_CONFORME)

    resultado = cli(pg).invoke(main.cli, ["check-cierres"])

    assert resultado.exit_code == 0, resultado.output
    assert "0 discrepancia" in resultado.output


def test_f042_r17_el_comando_sale_distinto_de_0_y_nombra_la_obra(cli):
    publicado = (*PUBLICADO_CONFORME, (OBRA_0499, AMBITO_COSTE, FEBRERO, 20, Decimal("1.00")))
    pg = PgFalso(CANDIDATOS_0499, publicado)

    resultado = cli(pg).invoke(main.cli, ["check-cierres"])

    assert resultado.exit_code != 0
    assert str(OBRA_0499) in resultado.output
    assert "2018-02" in resultado.output


def test_f042_r16_el_comando_falla_si_el_telescopio_esta_roto(cli):
    pg = PgFalso(CANDIDATOS_0499, PUBLICADO_CONFORME, telescopio=(1000, 3, 12))

    resultado = cli(pg).invoke(main.cli, ["check-cierres"])

    assert resultado.exit_code != 0
    assert "3" in resultado.output


def test_f042_el_comando_no_abre_conexion_en_dry_run(cli):
    class PgQueEstalla:
        def __getattr__(self, nombre: str):
            raise AssertionError(f"--dry-run no puede tocar la base (pg.{nombre})")

    resultado = cli(PgQueEstalla()).invoke(main.cli, ["check-cierres", "--dry-run"])

    assert resultado.exit_code == 0, resultado.output
    assert "stg.presupuesto" in resultado.output


def test_f042_el_comando_esta_registrado_con_su_ayuda():
    resultado = CliRunner().invoke(main.cli, ["check-cierres", "--help"])

    assert resultado.exit_code == 0
    assert "--obras" in resultado.output
    assert "--dry-run" in resultado.output


# ---------------------------------------------------------------------------
# El cliente, con un doble. NO se abre ninguna conexion.
# ---------------------------------------------------------------------------
#
# `filas_solo_lectura` es el unico sitio donde `check-cierres` y `huella-obras`
# tocan la base, y es la pieza de la que depende que el nivel 1 de la prueba de
# F-042 sea de solo lectura de verdad. Se prueba lo que se puede probar sin
# servidor: que emite las DOS sentencias previas antes de la consulta, que
# devuelve las filas, y que un error deja la transaccion en `ROLLBACK`.


class _CursorHuella:
    def __init__(self, filas, revienta=None):
        self.filas = filas
        self.revienta = revienta
        self.ejecutadas: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, *_args):
        self.ejecutadas.append(sql)
        if self.revienta is not None and "SELECT" in sql.upper():
            raise self.revienta

    def fetchall(self):
        return self.filas


class _ConexionHuella:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _ClienteConConexion:
    def __init__(self, conexion):
        self._conexion = conexion

    def connection(self):
        return self._conexion


def _leer(cliente, sql, timeout=30):
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    return PostgresClient.filas_solo_lectura(cliente, sql, timeout)


def test_f042_r17_la_lectura_va_read_only_y_con_su_timeout() -> None:
    """Las dos sentencias previas se emiten DE VERDAD, antes de la consulta.

    Es exactamente el defecto que F-006 encontro en su propia comprobacion de
    unicidad: un constructor de `BEGIN READ ONLY` que no llamaba nadie mientras
    el comando imprimia por pantalla «transaccion READ ONLY». La garantia iba
    impresa y no existia.
    """
    cursor = _CursorHuella([(1, "0499", 3, date(2018, 2, 1), 1, "21", 0, 0)])
    conexion = _ConexionHuella(cursor)

    filas = _leer(_ClienteConConexion(conexion), "SELECT 1", timeout=42)

    assert filas == [(1, "0499", 3, date(2018, 2, 1), 1, "21", 0, 0)]
    assert cursor.ejecutadas[0] == "SET LOCAL statement_timeout = '42s'"
    assert cursor.ejecutadas[1] == "SET LOCAL transaction_read_only = on"
    assert cursor.ejecutadas[2] == "SELECT 1"
    assert conexion.commits == 1 and conexion.rollbacks == 0


def test_f042_r17_un_error_en_la_lectura_deja_la_transaccion_en_rollback() -> None:
    cursor = _CursorHuella([], revienta=RuntimeError("el servidor dice que no"))
    conexion = _ConexionHuella(cursor)

    with pytest.raises(RuntimeError, match="el servidor dice que no"):
        _leer(_ClienteConConexion(conexion), "SELECT 1")

    assert conexion.rollbacks == 1
    assert conexion.commits == 0


# ---------------------------------------------------------------------------
# R16 · que es un hueco DE ORIGEN y que es un hueco que crea esta feature
# ---------------------------------------------------------------------------
#
# El defecto que estos tests existen para impedir, y que casi se publica: la
# clasificacion miraba si `version` era consecutiva, y `version` es el numero
# ORIGINAL de Sigrid (R7), o sea que LLEVA LOS HUECOS QUE ESTA FEATURE CREA.
# Tras el build, la 0499 publica 17, 19, 21, 22: se habria apartado por «hueco
# de origen» y habria quedado FUERA del recuento de series rotas. La unica
# comprobacion de R16 contra la base iba a excusar precisamente las 9 obras que
# hay que vigilar, y a devolver un «0 series rotas» sin haberlas mirado.


def test_f042_r16_una_serie_renumerada_no_es_un_hueco_de_origen():
    """0499 tras el build: publica 17, 19, 21, 22 con la 18 y la 20 descartadas.

    Sus `version` NO son consecutivos y su `orden_fase` SI lo es. La serie
    telescopea y tiene que entrar en el recuento de comprobadas, no en el de
    apartadas.
    """
    assert hay_hueco_de_origen([17, 19, 21, 22], [18, 20]) is False
    assert orden_de_los_publicados([17, 19, 21, 22], [18, 20]) == {
        17: 17, 19: 18, 21: 19, 22: 20
    }


def test_f042_r16_un_hueco_que_los_descartes_no_explican_si_se_aparta():
    """Fases 1, 2 y 4 sin ningun descarte: la 4 publica el acumulado entero y la
    serie no telescopea, ni telescopeaba antes de F-042."""
    assert hay_hueco_de_origen([1, 2, 4], []) is True


def test_f042_r16_una_partida_ausente_de_una_fase_descartada_no_es_un_hueco():
    """El caso real de la 0471 en Venta (marzo de 2016), que es el unico
    `importe_mes` que F-042 mueve.

    Esa partida tiene fila en las fases 4 y 6 y NO en la 5. Con la 5 descartada,
    `orden_fase(6) = 5` y la serie vuelve a ser consecutiva: pasa a publicar la
    diferencia en vez del acumulado entero, y el telescopio, que ahi estaba roto
    por +4.538,09, se repara.
    """
    assert hay_hueco_de_origen([4, 6], [5]) is False
    assert hay_hueco_de_origen([4, 6], []) is True


def test_f042_r16_el_telescopio_clasifica_por_orden_y_no_por_version():
    """Y el SQL hace lo mismo que el oraculo: reconstruye el orden desde los
    descartes en vez de mirar si `version` es consecutiva."""
    texto = sql_telescopio()

    assert "orden_previo <> orden_fase - 1" in texto
    assert "version - 1" not in texto, (
        "vuelve a clasificar por `version`, que lleva los huecos que crea F-042"
    )
    for cte in ("publicado AS (", "candidato AS (", "descarte AS (", "orden AS ("):
        assert cte in texto, f"falta la CTE {cte}"
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING" in texto


def test_f042_r16_los_descartes_del_telescopio_son_un_hecho_no_una_regla():
    """El SQL no reimplementa «manda el mas moderno»: observa que fases sostiene
    el origen y no estan publicadas. Si repitiera la regla, un fallo del build y
    un fallo de la comprobacion se cancelarian."""
    texto = sql_telescopio()

    assert "acumulado <> 0" not in texto
    assert "DISTINCT ON" not in texto
    assert "LEFT JOIN publicado p USING (obra_id, ambito_id, numero_fase)" in texto
