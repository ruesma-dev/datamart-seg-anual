# tests/test_f132_retirada.py
"""
F-132 · Fase B, rama BORRAR: la foto diaria de estados de F-067 se retira
(R25, R26). Decisión del humano del 2026-10-09 (D6 acortada, D7 = BORRAR).

LO QUE ESTE FICHERO DEFIENDE:

1. **Nadie vuelve a crear la foto** (R25): `build_compras` ya no tiene el
   sub-paso `11`, el fichero no existe y ningún SQL ni código de `etl_sigrid/`
   nombra sus tablas, salvo el SQL que las BORRA. Si alguien las recreara, la
   nocturna volvería a escribir dos tablas que el diccionario ya no describe.
2. **La época de Delphi sobrevive** (R25): `fn_sigrid_tiempo` la sigue usando,
   y ahora vive en `domain/fecha_delphi.py`.
3. **`retirar-foto-estados` solo borra con `--confirmar`** (R26), las dos
   tablas en UNA transacción y sin `CASCADE`; sin él lee (READ ONLY) y dice qué
   borraría.

Ningún test toca red ni BBDD: el SQL se lee como texto y el comando se ejecuta
contra un doble de `main._get_pg`.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import date, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

import main

RAIZ = Path(__file__).resolve().parents[1]
DIR_ETL = RAIZ / "etl_sigrid"
DIR_SQL_COMPRAS = DIR_ETL / "infrastructure" / "postgres" / "sql" / "compras"
TABLAS_FOTO = ("historial_estados", "historial_estados_fotos")


# ===========================================================================
# R25 · el build deja de tomar la foto
# ===========================================================================


def test_f132_r25_el_fichero_de_la_foto_ya_no_existe() -> None:
    assert not (DIR_SQL_COMPRAS / "11_historial_estados.sql").exists()


def test_f132_r25_build_compras_ya_no_tiene_el_sub_paso_de_la_foto() -> None:
    from etl_sigrid.application.steps.build_compras_step import SUB_PASOS

    assert "historial_estados" not in [s.name for s in SUB_PASOS]
    # F-090 añade `14` (el índice de adjuntos) detrás de `13`: lo que se
    # defiende es que tras `necesidades` ya no va `11`.
    ficheros = [s.sql_file for s in SUB_PASOS]
    i = ficheros.index("10_necesidades.sql")
    assert ficheros[i : i + 3] == [
        "10_necesidades.sql", "12_documento_procesos.sql", "13_estado_documentos.sql",
    ]
    assert all(s.target_table not in TABLAS_FOTO for s in SUB_PASOS)


def test_f132_r25_la_epoca_de_delphi_sigue_en_el_dominio() -> None:
    from etl_sigrid.domain.fecha_delphi import EPOCA_DELPHI, fecha_delphi

    assert date(1899, 12, 30) == EPOCA_DELPHI
    # Medido en Sigrid: 46300,537627 es el 2026-10-05 a las 12:54:10.
    valor = fecha_delphi(46300.537627)
    assert valor is not None
    assert valor.replace(microsecond=0) == datetime(2026, 10, 5, 12, 54, 10)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (1.0, datetime(1899, 12, 31)),
        (0.5, datetime(1899, 12, 30, 12, 0)),
        (2.25, datetime(1900, 1, 1, 6, 0)),
    ],
)
def test_f132_r25_fecha_delphi_la_hora_va_en_la_parte_decimal(
    valor: float, esperado: datetime
) -> None:
    from etl_sigrid.domain.fecha_delphi import fecha_delphi

    assert fecha_delphi(valor) == esperado


@pytest.mark.parametrize("valor", [None, 0, 0.0, -1.0])
def test_f132_r25_fecha_delphi_cero_nulo_o_negativo_no_es_una_fecha(
    valor: float | None,
) -> None:
    from etl_sigrid.domain.fecha_delphi import fecha_delphi

    assert fecha_delphi(valor) is None


def test_f132_r25_fecha_delphi_no_importa_infraestructura_ni_configuracion() -> None:
    texto = (DIR_ETL / "domain" / "fecha_delphi.py").read_text(encoding="utf-8")
    assert "infrastructure" not in texto and "config" not in texto.split('"""', 2)[2]


def test_f132_r25_el_dominio_de_la_foto_ya_no_existe() -> None:
    assert importlib.util.find_spec("etl_sigrid.domain.historial_estados") is None


def _sin_comentarios_sql(texto: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def test_f132_r25_veto_ningun_sql_ni_modulo_nombra_la_foto_salvo_quien_la_borra() -> None:
    """Ni un `CREATE TABLE IF NOT EXISTS` que la resucite, ni un step que la
    cuente, ni un SELECT que la lea: solo `retirar_foto_sql.py`, que la borra.

    Lo que se busca es la TABLA (`compras.historial_estados...` o su nombre
    entre comillas), no el fichero que la creaba: un docstring que cuenta que
    `11_historial_estados.sql` existió no la toca. En el SQL cuenta lo
    EJECUTABLE: la cabecera de `01_documentos.sql` aún cita la foto en un
    comentario y está fijada por la huella de `test_f073_sql` r23.
    """
    tabla = re.compile(r"compras\.historial_estados|[\"']historial_estados")
    nombran = {
        ruta.relative_to(RAIZ).as_posix()
        for patron in ("**/*.sql", "**/*.py")
        for ruta in DIR_ETL.glob(patron)
        if tabla.search(
            _sin_comentarios_sql(ruta.read_text(encoding="utf-8"))
            if ruta.suffix == ".sql" else ruta.read_text(encoding="utf-8")
        )
    }
    assert nombran == {"etl_sigrid/infrastructure/postgres/retirar_foto_sql.py"}


# ===========================================================================
# R26 · el SQL de la retirada
# ===========================================================================


def _sql():
    from etl_sigrid.infrastructure.postgres import retirar_foto_sql

    return retirar_foto_sql


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios_sql(texto)).strip()


def test_f132_r26_las_tablas_a_borrar_son_las_dos_de_la_foto() -> None:
    assert _sql().TABLAS_FOTO == TABLAS_FOTO


def test_f132_r26_la_lectura_es_un_select_que_no_escribe() -> None:
    texto = _compacto(_sql().SQL_TABLAS_FOTO)
    assert texto.startswith("SELECT ") and ";" not in texto
    assert not re.search(
        r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE)\b", texto, re.IGNORECASE
    )
    assert "n.nspname = 'compras'" in texto
    assert "c.relname IN ('historial_estados', 'historial_estados_fotos')" in texto
    assert "ORDER BY c.relname" in texto


def test_f132_r26_el_borrado_es_un_drop_de_las_dos_sin_cascade_y_con_lock_timeout() -> None:
    sentencias = [_compacto(s) for s in _sql().SENTENCIAS_RETIRADA]
    assert sentencias == [
        "SET LOCAL lock_timeout = '30s'",
        "DROP TABLE IF EXISTS compras.historial_estados, compras.historial_estados_fotos",
    ]
    assert not any("CASCADE" in s.upper() for s in sentencias), (
        "sin CASCADE: si algo dependiera de ellas, el DROP falla y no se borra nada"
    )


# ===========================================================================
# R26 · el comando `retirar-foto-estados`
# ===========================================================================


class _Cursor:
    def __init__(self, ejecutadas: list[str]) -> None:
        self._ejecutadas = ejecutadas

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str) -> None:
        self._ejecutadas.append(sql)


class _Conexion:
    def __init__(self) -> None:
        self.ejecutadas: list[str] = []
        self.commits = 0

    def __enter__(self) -> _Conexion:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> _Cursor:
        return _Cursor(self.ejecutadas)

    def commit(self) -> None:
        self.commits += 1


class _PgFalso:
    """Lee las tablas presentes (la primera lectura, antes; la segunda, después
    del borrado) y apunta lo que se ejecuta por la conexión de escritura."""

    def __init__(self, *lecturas: list[tuple[str, int]]) -> None:
        self._lecturas = list(lecturas)
        self.leidas: list[str] = []
        self.timeouts: list[int] = []
        self.conexiones: list[_Conexion] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple[str, int]]:
        self.leidas.append(sql_text)
        self.timeouts.append(timeout_s)
        return self._lecturas.pop(0)

    def connection(self) -> _Conexion:
        conexion = _Conexion()
        self.conexiones.append(conexion)
        return conexion


PRESENTES = [("historial_estados", 186412), ("historial_estados_fotos", 3)]


def _lanzar(monkeypatch: pytest.MonkeyPatch, pg: _PgFalso, *argumentos: str):
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    return CliRunner().invoke(main.cli, ["retirar-foto-estados", *argumentos])


def test_f132_r26_sin_confirmar_dice_que_borraria_y_no_toca_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgFalso(PRESENTES)

    resultado = _lanzar(monkeypatch, pg)

    assert resultado.exit_code == 0, resultado.output
    assert pg.conexiones == [], "sin --confirmar no se abre conexion de escritura"
    assert pg.leidas == [_sql().SQL_TABLAS_FOTO]
    assert "compras.historial_estados: 186412 filas" in resultado.output
    assert "compras.historial_estados_fotos: 3 filas" in resultado.output
    assert "NO se ha borrado nada" in resultado.output
    assert "--confirmar" in resultado.output


def test_f132_r26_con_confirmar_borra_las_dos_en_una_transaccion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgFalso(PRESENTES, [])

    resultado = _lanzar(monkeypatch, pg, "--confirmar")

    assert resultado.exit_code == 0, resultado.output
    assert len(pg.conexiones) == 1
    conexion = pg.conexiones[0]
    assert conexion.ejecutadas == list(_sql().SENTENCIAS_RETIRADA)
    assert conexion.commits == 1
    assert pg.leidas == [_sql().SQL_TABLAS_FOTO, _sql().SQL_TABLAS_FOTO], (
        "lee antes para decir qué borra y después para comprobar que ya no están"
    )
    assert "Borradas: compras.historial_estados, compras.historial_estados_fotos" in (
        resultado.output
    )
    assert "Comprobado: ya no queda ninguna de las dos." in resultado.output


def test_f132_r26_las_dos_lecturas_llevan_su_statement_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contar 186.000 filas en un servidor compartido: dos minutos como mucho por
    lectura, antes y después del borrado (superviviente de la mutación de la
    Fase B: ningún test miraba el `timeout_s` que se pasa)."""
    pg = _PgFalso(PRESENTES, [])

    resultado = _lanzar(monkeypatch, pg, "--confirmar")

    assert resultado.exit_code == 0, resultado.output
    assert pg.timeouts == [120, 120]


def test_f132_r26_si_tras_borrar_sigue_alguna_sale_con_uno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgFalso(PRESENTES, [("historial_estados", 186412)])

    resultado = _lanzar(monkeypatch, pg, "--confirmar")

    assert resultado.exit_code == 1, resultado.output
    assert "siguen existiendo: compras.historial_estados" in resultado.output


@pytest.mark.parametrize("argumentos", [(), ("--confirmar",)])
def test_f132_r26_sin_tablas_no_hay_nada_que_borrar(
    monkeypatch: pytest.MonkeyPatch, argumentos: tuple[str, ...]
) -> None:
    pg = _PgFalso([])

    resultado = _lanzar(monkeypatch, pg, *argumentos)

    assert resultado.exit_code == 0, resultado.output
    assert pg.conexiones == []
    assert "Ninguna de las dos tablas existe: nada que borrar." in resultado.output


def test_f132_r26_con_una_sola_presente_borra_igual_las_dos_con_if_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = _PgFalso([("historial_estados_fotos", 3)], [])

    resultado = _lanzar(monkeypatch, pg, "--confirmar")

    assert resultado.exit_code == 0, resultado.output
    assert pg.conexiones[0].ejecutadas == list(_sql().SENTENCIAS_RETIRADA)
    assert "compras.historial_estados_fotos: 3 filas" in resultado.output
    assert "compras.historial_estados: no existe" in resultado.output


# ===========================================================================
# R26 · el contraste desaparece
# ===========================================================================


def test_f132_r26_el_comando_contraste_estados_ya_no_existe() -> None:
    assert "contraste-estados" not in main.cli.commands
    assert "retirar-foto-estados" in main.cli.commands


def test_f132_r26_el_sql_del_contraste_ya_no_existe() -> None:
    assert importlib.util.find_spec(
        "etl_sigrid.infrastructure.postgres.contraste_estados_sql"
    ) is None


@pytest.mark.parametrize(
    "nombre",
    ["clasificar_cambio", "clasificar_no_visto", "contrastar", "formatear_contraste",
     "CLASES_CAMBIO", "CLASES_NO_VISTO", "Contrastado"],
)
def test_f132_r26_el_dominio_ya_no_contrasta(nombre: str) -> None:
    from etl_sigrid.domain import estado_documentos

    assert not hasattr(estado_documentos, nombre)
