# tests/test_f006_comandos.py
"""
Los comandos de F-006, ejercitados con `CliRunner` y sin conexión.

Eran dos —`check-unicidad` y `check-diccionario`— y son tres desde que la
batería de aceptación obligó a `check-relaciones`. El tercero entra aquí y no en
un fichero aparte por el mismo motivo que los otros dos: **el cuerpo de un
comando es código**, y dejarlo fuera de la suite es lo que ya convirtió 64
líneas sin cubrir en paisaje.

Llevaba tres tandas **explicando** que la cobertura bajaba porque el cuerpo de
`check-unicidad` y `check-diccionario` «no se puede cubrir sin base». Medido por
la review: **64 de las 85 líneas sin cubrir eran el cuerpo entero de los dos
comandos**, y `catalogo.py` estaba al 100 %. O sea que lo que faltaba no era una
conexión: era usar el `CliRunner` que este repositorio ya usa en otros seis
sitios.

Explicar una laguna tres veces cuesta más que cerrarla, y además la convierte en
paisaje. Aquí se cierra.

Los dobles sustituyen **solo** a `PostgresClient`: el resto —cargar el
diccionario real, generar las consultas, comparar contra el catálogo, formatear
los veredictos— es código de verdad, ejecutado de verdad.
"""

from __future__ import annotations

import pathlib

import pytest
from click.testing import CliRunner

RAIZ = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Dobles: solo el cliente de Postgres
# ---------------------------------------------------------------------------


class _PgUnicidad:
    """Devuelve lo que se le diga por objeto, y anota qué se le preguntó."""

    def __init__(self, respuestas=None, por_defecto=(0, 0)):
        self.respuestas = respuestas or {}
        self.por_defecto = por_defecto
        self.preguntados: list[str] = []
        self.timeouts: list[int] = []

    def comprobar_unicidad(self, consulta, timeout_s):
        self.preguntados.append(consulta.objeto)
        self.timeouts.append(timeout_s)
        return self.respuestas.get(consulta.objeto, self.por_defecto)


class _PgRelaciones:
    """Devuelve lo que se le diga por relación, y anota qué se le preguntó."""

    def __init__(self, respuestas=None, por_defecto=(500, 500)):
        self.respuestas = respuestas or {}
        self.por_defecto = por_defecto
        self.preguntadas: list[str] = []
        self.timeouts: list[int] = []

    def comprobar_relacion(self, consulta, timeout_s):
        self.preguntadas.append(f"{consulta.nombre} -> {consulta.a}")
        self.timeouts.append(timeout_s)
        return self.respuestas.get(f"{consulta.nombre} -> {consulta.a}", self.por_defecto)


class _PgCatalogo:
    def __init__(self, catalogo, publicado):
        self.catalogo = catalogo
        self.publicado = publicado
        self.esquemas_pedidos: list[str] | None = None

    def list_objetos_catalogo(self, schemas):
        self.esquemas_pedidos = list(schemas)
        return self.catalogo

    def fetch_hash_publicado(self):
        return self.publicado


def _cuantas_consultas(solo_consumo=True) -> int:
    """Cuántas consultas toca generar, derivado del diccionario.

    Escribir 47 y 56 a mano se quedó atrás en cuanto el contrato creció con
    `_meta.diccionario_contexto`. Es el mismo recuento cableado de siempre.
    """
    from etl_sigrid.infrastructure.postgres.unicidad_sql import consultas_de_unicidad

    dicc, _ = _diccionario_real()
    return len(consultas_de_unicidad(dicc, solo_consumo=solo_consumo))


def _cuantas_relaciones(solo_consumo=True) -> int:
    """Cuántas relaciones toca comprobar, derivado del diccionario."""
    from etl_sigrid.infrastructure.postgres.relaciones_sql import (
        consultas_de_relaciones,
    )

    dicc, _ = _diccionario_real()
    return len(consultas_de_relaciones(dicc, solo_consumo=solo_consumo))


def _una_relacion_real(solo_consumo=True) -> str:
    """La primera relación del alcance, para nombrarla sin cablearla."""
    from etl_sigrid.infrastructure.postgres.relaciones_sql import (
        consultas_de_relaciones,
    )

    dicc, _ = _diccionario_real()
    consulta = consultas_de_relaciones(dicc, solo_consumo=solo_consumo)[0]
    return f"{consulta.nombre} -> {consulta.a}"


def _runner(monkeypatch, pg) -> CliRunner:
    import main

    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    return CliRunner()


def _diccionario_real():
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    return cargar_diccionario(RAIZ / "config" / "diccionario")


def _catalogo_de_las_fichas():
    tipos = {"tabla": "BASE TABLE", "vista": "VIEW", "funcion": "funcion"}
    dicc, _ = _diccionario_real()
    return [(f.esquema, f.objeto, tipos[f.tipo]) for f in dicc.fichas]


# ---------------------------------------------------------------------------
# check-unicidad
# ---------------------------------------------------------------------------


def test_f006_t26_cli_dry_run_no_toca_la_base(monkeypatch) -> None:
    """`--dry-run` imprime las consultas y no llama al cliente ni una vez."""
    import main

    pg = _PgUnicidad()
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-unicidad", "--dry-run"])

    assert resultado.exit_code == 0, resultado.output
    assert pg.preguntados == [], "el dry-run ha abierto conexion"
    assert "No se ha abierto ninguna conexion" in resultado.output
    assert "GROUP BY" in resultado.output
    assert "HAVING count(*) > 1" in resultado.output


def test_f006_t26_cli_todo_limpio_sale_con_cero(monkeypatch) -> None:
    import main

    pg = _PgUnicidad()
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-unicidad"])

    assert resultado.exit_code == 0, resultado.output
    assert len(pg.preguntados) == _cuantas_consultas(), (
        f"alcance por defecto: {len(pg.preguntados)}"
    )
    assert "0 con la clave rota" in resultado.output
    # El aviso que impide leer un verde como una garantia.
    assert "NO tiene la clave demostrada" in resultado.output


def test_f006_t26_cli_una_clave_rota_sale_con_uno(monkeypatch) -> None:
    """El caso real: `mart.fact_seguimiento_mensual`, 8778 claves duplicadas."""
    import main

    pg = _PgUnicidad(respuestas={"mart.fact_seguimiento_mensual": (8778, 17556)})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-unicidad"])

    assert resultado.exit_code == 1
    assert "KO   mart.fact_seguimiento_mensual" in resultado.output
    assert "8778" in resultado.output and "17556" in resultado.output
    assert "fan-out" in resultado.output
    assert "1 con la clave rota" in resultado.output


def test_f006_t26_cli_un_timeout_no_cuenta_como_ok(monkeypatch) -> None:
    """Lo que el dato de los 180 s demostró: un timeout no es un verde."""
    import main

    pg = _PgUnicidad(respuestas={"mart.v_pbi_fact": None})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-unicidad"])

    assert resultado.exit_code == 1
    assert "NO COMPROBADO" in resultado.output
    assert "1 sin comprobar" in resultado.output


def test_f006_t26_cli_un_objeto_que_no_existe_no_tumba_el_recorrido(monkeypatch) -> None:
    """El caso real: `cierre.v_pbi_planif_vs_real`."""
    import main

    pg = _PgUnicidad(respuestas={"cierre.v_pbi_planif_vs_real": "NO_EXISTE"})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-unicidad"])

    assert resultado.exit_code == 1
    assert "FICHADO Y NO EXISTE" in resultado.output
    assert "1 fichados que no existen" in resultado.output
    assert len(pg.preguntados) == _cuantas_consultas(), (
        "el recorrido tiene que continuar"
    )


def test_f006_t26_cli_todos_amplia_el_alcance(monkeypatch) -> None:
    import main

    pg = _PgUnicidad()
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-unicidad", "--todos"])

    assert resultado.exit_code == 0
    assert len(pg.preguntados) == _cuantas_consultas(solo_consumo=False), (
        f"con --todos: {len(pg.preguntados)}"
    )
    assert "TODO objeto con clave" in resultado.output
    assert not [o for o in pg.preguntados if o.startswith("raw.")], (
        "`raw` nunca entra: su `ide` es PRIMARY KEY"
    )


def test_f006_t26_cli_el_timeout_llega_al_cliente(monkeypatch) -> None:
    import main

    pg = _PgUnicidad()
    _runner(monkeypatch, pg).invoke(main.cli, ["check-unicidad", "--timeout", "180"])

    assert set(pg.timeouts) == {180}, "la bandera no llega al cliente"


# ---------------------------------------------------------------------------
# check-relaciones
# ---------------------------------------------------------------------------


def test_f006_t40_cli_dry_run_no_toca_la_base(monkeypatch) -> None:
    import main

    pg = _PgRelaciones()
    resultado = _runner(monkeypatch, pg).invoke(
        main.cli, ["check-relaciones", "--dry-run"]
    )

    assert resultado.exit_code == 0, resultado.output
    assert pg.preguntadas == [], "el dry-run ha abierto conexion"
    assert "No se ha abierto ninguna conexion" in resultado.output
    assert "WITH muestra AS" in resultado.output
    assert "WHERE EXISTS" in resultado.output


def test_f006_t40_cli_todo_une_sale_con_cero(monkeypatch) -> None:
    import main

    pg = _PgRelaciones()
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones"])

    assert resultado.exit_code == 0, resultado.output
    assert len(pg.preguntadas) == _cuantas_relaciones()
    assert "0 que NO unen" in resultado.output
    # El aviso que impide leer un verde como una garantia.
    assert "NO esta demostrada" in resultado.output


def test_f006_t40_cli_una_relacion_que_no_une_sale_con_uno(monkeypatch) -> None:
    """El caso real que trajo esta puerta: 0 de 261."""
    import main

    rota = _una_relacion_real()
    pg = _PgRelaciones(respuestas={rota: (261, 0)})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones"])

    assert resultado.exit_code == 1
    assert f"KO   {rota}" in resultado.output
    assert "0 de 261" in resultado.output
    assert "cero filas" in resultado.output
    assert "1 que NO unen" in resultado.output


def test_f006_t40_cli_una_cobertura_escasa_avisa_y_no_tumba(monkeypatch) -> None:
    """Un hueco puede ser legítimo: `cierre` solo cubre 583 de 918 obras."""
    import main

    escasa = _una_relacion_real()
    pg = _PgRelaciones(respuestas={escasa: (261, 3)})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones"])

    assert resultado.exit_code == 0, resultado.output
    assert f"AVISO {escasa}" in resultado.output
    assert "1 con cobertura escasa" in resultado.output


def test_f006_t40_cli_una_muestra_vacia_no_cuenta_como_ok(monkeypatch) -> None:
    """Cero valores muestreados es «no lo sabemos», no «correcto»."""
    import main

    vacia = _una_relacion_real()
    pg = _PgRelaciones(respuestas={vacia: (0, 0)})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones"])

    assert resultado.exit_code == 1
    assert "sin valores" in resultado.output
    assert "1 sin comprobar" in resultado.output


def test_f006_t40_cli_un_timeout_no_cuenta_como_ok(monkeypatch) -> None:
    import main

    lenta = _una_relacion_real()
    pg = _PgRelaciones(respuestas={lenta: None})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones"])

    assert resultado.exit_code == 1
    assert "NO COMPROBADA" in resultado.output
    assert "1 sin comprobar" in resultado.output


def test_f006_t40_cli_un_extremo_que_no_existe_no_tumba_el_recorrido(
    monkeypatch,
) -> None:
    import main

    ausente = _una_relacion_real()
    pg = _PgRelaciones(respuestas={ausente: "NO_EXISTE"})
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones"])

    assert resultado.exit_code == 1
    assert "NO EXISTE en la base" in resultado.output
    assert len(pg.preguntadas) == _cuantas_relaciones(), (
        "el recorrido tiene que continuar"
    )


def test_f006_t40_cli_todos_amplia_el_alcance(monkeypatch) -> None:
    import main

    pg = _PgRelaciones()
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones", "--todos"])

    assert resultado.exit_code == 0
    assert len(pg.preguntadas) == _cuantas_relaciones(solo_consumo=False)
    assert "TODA relacion declarada" in resultado.output


def test_f006_t40_cli_el_timeout_llega_al_cliente(monkeypatch) -> None:
    import main

    pg = _PgRelaciones()
    _runner(monkeypatch, pg).invoke(main.cli, ["check-relaciones", "--timeout", "90"])

    assert set(pg.timeouts) == {90}, "la bandera no llega al cliente"


# ---------------------------------------------------------------------------
# check-diccionario
# ---------------------------------------------------------------------------


def test_f006_r28_cli_biyeccion_exacta_y_publicado_al_dia(monkeypatch) -> None:
    import main

    _dicc, hash_arbol = _diccionario_real()
    pg = _PgCatalogo(_catalogo_de_las_fichas(), ("3", hash_arbol))
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-diccionario"])

    assert resultado.exit_code == 0, resultado.output
    assert "biyeccion exacta" in resultado.output
    assert "lo publicado ES lo del arbol" in resultado.output
    assert pg.esquemas_pedidos is not None and len(pg.esquemas_pedidos) == 9


def test_f006_r28_cli_detecta_la_huerfana_real(monkeypatch) -> None:
    """`cierre.v_pbi_planif_vs_real`: el repositorio la crea y la base no la tiene."""
    import main

    _dicc, hash_arbol = _diccionario_real()
    catalogo = [f for f in _catalogo_de_las_fichas() if f[1] != "v_pbi_planif_vs_real"]
    pg = _PgCatalogo(catalogo, ("3", hash_arbol))
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-diccionario"])

    assert resultado.exit_code == 1
    assert "FICHADO Y NO EXISTE" in resultado.output
    assert "cierre.v_pbi_planif_vs_real" in resultado.output


def test_f006_r28_cli_avisa_de_que_lo_publicado_se_quedo_atras(monkeypatch) -> None:
    """El defecto que dejó `_meta` sirviendo un grano que T26 refutó."""
    import main

    pg = _PgCatalogo(_catalogo_de_las_fichas(), ("1", "0" * 64))
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-diccionario"])

    assert resultado.exit_code == 1
    assert "LO PUBLICADO NO ES LO DEL ARBOL" in resultado.output
    assert "publicar-diccionario" in resultado.output


def test_f006_r28_cli_sin_nada_publicado(monkeypatch) -> None:
    import main

    pg = _PgCatalogo(_catalogo_de_las_fichas(), None)
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-diccionario"])

    assert resultado.exit_code == 1
    assert "no hay nada publicado" in resultado.output


def test_f006_r28_cli_detecta_un_objeto_publicado_sin_ficha(monkeypatch) -> None:
    import main

    _dicc, hash_arbol = _diccionario_real()
    catalogo = _catalogo_de_las_fichas() + [("mart", "v_pbi_inventada", "VIEW")]
    pg = _PgCatalogo(catalogo, ("3", hash_arbol))
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-diccionario"])

    assert resultado.exit_code == 1
    assert "PUBLICADO Y SIN FICHA" in resultado.output
    assert "mart.v_pbi_inventada" in resultado.output
