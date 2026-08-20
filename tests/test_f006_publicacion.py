# tests/test_f006_publicacion.py
"""
F-006 · La publicación del diccionario en `_meta` (R15, R17-R23).

Esto es **la mitad del contrato con el repositorio `mcp-bbdd`**, y lo único que
este repositorio puede garantizarle: nombres de tabla, de columna y de vista
estables, y una publicación atómica. El otro lado —que el MCP lea `_meta` en vez
de su YAML local— no se puede garantizar desde aquí.

De ahí que estos tests sean tan literales con el DDL: no comprueban que «algo
parecido» exista, comprueban el contrato letra a letra, porque alguien va a
programar contra él sin poder preguntar.

Ningún test de este fichero abre conexión a la base. El `.env` de este puesto
apunta a `psql-albaranes-rs9k2`, compartido con `albaranes` y `partes` en
producción: todo lo que exige una base real queda como verificación
`MANUAL (humano)` y está listado en `progress/impl_F-006.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DDL = RAIZ / "etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql"


def _ddl() -> str:
    return DDL.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"--[^\n]*", " ", texto)


def _cuerpo_de_la_vista() -> str:
    """Solo el `CREATE OR REPLACE VIEW`, hasta su `;`.

    Sin este recorte, el `COMMENT ON VIEW` que explica el contrato entra en la
    comprobación y la rompe: su texto menciona `JOIN` y `DROP VIEW` justamente
    para advertir de ellos.
    """
    limpio = _sin_comentarios(_ddl())
    inicio = limpio.upper().index("CREATE OR REPLACE VIEW _META.V_DICCIONARIO")
    return limpio[inicio:].split(";")[0]


# ---------------------------------------------------------------------------
# ddl · las tres tablas y la vista
# ---------------------------------------------------------------------------


def test_f006_r17_ddl_el_fichero_existe_y_se_declara() -> None:
    assert DDL.exists()
    assert _ddl().splitlines()[0].strip().startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql"
    )


@pytest.mark.parametrize(
    "tabla",
    ["_meta.diccionario", "_meta.diccionario_reglas", "_meta.diccionario_publicacion"],
)
def test_f006_r17_ddl_crea_las_tres_tablas_de_forma_idempotente(tabla: str) -> None:
    """`CREATE TABLE IF NOT EXISTS`: el DDL se ejecuta en cada publicación."""
    assert re.search(
        rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{re.escape(tabla)}\s*\(",
        _sin_comentarios(_ddl()),
        re.IGNORECASE,
    ), f"falta el CREATE TABLE IF NOT EXISTS de {tabla}"


def test_f006_r18_ddl_no_hace_drop_de_nada() -> None:
    """LA REGLA QUE NO SE PUEDE ROMPER: un `DROP` se lleva los `GRANT`.

    Es el problema que ya obliga a reaplicar los permisos cada noche. Si estas
    tablas se recrearan, el rol del MCP se quedaría sin lectura sobre ellas
    hasta el `apply-grants` siguiente, es decir, justo cuando más falta hace.
    """
    # Se miran las SENTENCIAS, no el texto: la cabecera y el `COMMENT ON` de la
    # vista mencionan `DROP VIEW` a propósito, para advertir de lo que cuesta.
    sentencias = [s.strip() for s in _sin_comentarios(_ddl()).split(";")]
    verbos = [s.split()[0].upper() for s in sentencias if s.split()]

    assert "DROP" not in verbos
    assert "TRUNCATE" not in verbos, (
        "el vaciado es DELETE dentro de la transacción de publicación, no aquí"
    )


def test_f006_r15_ddl_crea_la_vista_con_create_or_replace() -> None:
    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.v_diccionario\s+AS",
        _sin_comentarios(_ddl()),
        re.IGNORECASE,
    )


def test_f006_r15_ddl_los_dos_joins_de_la_vista_son_left() -> None:
    """Los dos son deliberados y por motivos distintos.

    El de `v_frescura`, porque un objeto cuyo paso nunca terminó bien tiene que
    seguir saliendo con la frescura a nulo: esconderlo sería el silencio que
    F-024 eliminó. El de `diccionario_publicacion`, un `LEFT JOIN ... ON TRUE` y
    no un `CROSS JOIN`, porque con la tabla vacía un `CROSS JOIN` devolvería
    CERO filas y la vista mentiría diciendo que no hay diccionario.
    """
    vista = _cuerpo_de_la_vista()

    assert re.search(r"LEFT\s+JOIN\s+_meta\.v_frescura", vista, re.IGNORECASE)
    assert re.search(
        r"LEFT\s+JOIN\s+_meta\.diccionario_publicacion\s+AS\s+p\s+ON\s+TRUE",
        vista,
        re.IGNORECASE,
    )
    assert "CROSS JOIN" not in vista.upper()
    for union in re.finditer(r"(\w+)\s+JOIN\b", vista, re.IGNORECASE):
        assert union.group(1).upper() == "LEFT", f"JOIN no LEFT: {union.group(0)}"


def test_f006_r22_ddl_la_publicacion_es_un_singleton() -> None:
    """`CHECK (id = 1)`: no hay forma de que queden dos versiones publicadas."""
    assert re.search(
        r"id\s+SMALLINT\s+PRIMARY\s+KEY\s+DEFAULT\s+1\s+CHECK\s*\(\s*id\s*=\s*1\s*\)",
        _sin_comentarios(_ddl()),
        re.IGNORECASE,
    )


@pytest.mark.parametrize(
    ("tabla", "columnas"),
    [
        (
            "_meta.diccionario",
            [
                "esquema", "objeto", "tipo", "capa", "consumo_recomendado",
                "motivo_no_consumo", "descripcion", "grano", "clave_negocio",
                "paso_etl", "refresco", "avisos", "n_columnas", "ficha",
            ],
        ),
        (
            "_meta.diccionario_reglas",
            ["codigo", "titulo", "severidad", "ambito", "regla", "motivo", "orden"],
        ),
        (
            "_meta.diccionario_publicacion",
            [
                "id", "version", "hash_fuente", "publicado_en", "batch_id",
                "n_objetos", "n_reglas", "n_columnas", "cobertura_cols",
            ],
        ),
    ],
)
def test_f006_r22_ddl_el_contrato_de_columnas_es_exacto(
    tabla: str, columnas: list[str]
) -> None:
    """`design.md` §4.1 letra a letra: `mcp-bbdd` programa contra esto."""
    from tests.test_f006_fichas import columnas_del_create_table

    reales = columnas_del_create_table(_ddl(), tabla)

    assert reales == columnas, f"{tabla}: {reales}"


def test_f006_r22_ddl_los_tipos_del_contrato_no_se_improvisan() -> None:
    """Los que un cliente necesita conocer para deserializar sin adivinar."""
    limpio = _sin_comentarios(_ddl())

    assert re.search(r"clave_negocio\s+TEXT\[\]", limpio, re.IGNORECASE)
    assert re.search(r"avisos\s+TEXT\[\]", limpio, re.IGNORECASE)
    assert re.search(r"ficha\s+JSONB\s+NOT\s+NULL", limpio, re.IGNORECASE)
    assert re.search(r"cobertura_cols\s+NUMERIC\(5,\s*2\)", limpio, re.IGNORECASE)


def test_f006_r22_ddl_publicado_en_es_timestamp_sin_zona() -> None:
    """Como el resto de `_meta`: UTC sin zona, escrito con `utcnow()`.

    Mezclar aquí un `TIMESTAMPTZ` haría que la fecha del diccionario y la de
    `v_frescura` no fueran comparables, que es justo lo que la vista hace.
    """
    limpio = _sin_comentarios(_ddl())

    assert re.search(r"publicado_en\s+TIMESTAMP\s+NOT\s+NULL", limpio, re.IGNORECASE)
    assert "TIMESTAMPTZ" not in limpio.upper()


def test_f006_r15_ddl_la_vista_expone_significado_y_frescura_de_una_vez() -> None:
    """Es lo que resuelve P15: una sola consulta, semántica y fecha de build."""
    vista = _cuerpo_de_la_vista()

    for columna in (
        "esquema", "objeto", "descripcion", "grano", "clave_negocio", "refresco",
        "avisos", "n_columnas", "ficha", "paso_etl",
        "ultimo_ok_finished_at", "horas_desde_ultimo_ok", "ultimo_intento_status",
        "diccionario_version", "diccionario_publicado_en",
    ):
        assert columna in vista, f"la vista no expone `{columna}`"


def test_f006_r23_ddl_advierte_de_lo_que_cuesta_cambiar_la_vista() -> None:
    """R23: quitar o reordenar columnas exige `DROP VIEW`, y eso se lleva los
    `GRANT`. Quien lo haga tiene que ejecutar `apply-grants` acto seguido, y
    tiene que enterarse leyendo el propio fichero."""
    cabecera = "\n".join(_ddl().splitlines()[:40])

    assert "DROP VIEW" in cabecera
    assert "apply-grants" in cabecera
    assert "CREATE OR REPLACE VIEW" in cabecera


# ---------------------------------------------------------------------------
# constructores · las tuplas que se insertan (T16 · R17, R18, R22)
# ---------------------------------------------------------------------------

from etl_sigrid.domain.inventario import evaluar_cobertura  # noqa: E402
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario  # noqa: E402

DIR_DICCIONARIO = RAIZ / "config" / "diccionario"


def _diccionario_real():
    """El diccionario REAL, con sus avisos ya derivados.

    Los tests de publicación se hacen contra las fichas de verdad y no contra
    un ejemplo de juguete: si el mecanismo no traga el contenido real, es ahora
    cuando hay que enterarse y no la noche que se publique.
    """
    from etl_sigrid.domain.diccionario import derivar_avisos

    dicc, hash_fuente = cargar_diccionario(DIR_DICCIONARIO)
    return derivar_avisos(dicc), hash_fuente


def _informe_real():
    from tests.test_f006_cobertura import _inventario_del_repositorio

    dicc, _ = _diccionario_real()
    return evaluar_cobertura(dicc, _inventario_del_repositorio(), dicc.pendientes)


def test_f006_r17_filas_hay_una_por_ficha_y_en_orden_estable() -> None:
    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_diccionario

    dicc, _ = _diccionario_real()

    filas = filas_diccionario(dicc)

    assert len(filas) == len(dicc.fichas) >= 49
    claves = [(f[0], f[1]) for f in filas]
    assert claves == sorted(claves), "el orden tiene que ser estable entre publicaciones"


def test_f006_r22_filas_el_orden_de_columnas_es_el_del_insert() -> None:
    """La tupla y el `INSERT` tienen que casar, o se publican datos cruzados."""
    from etl_sigrid.infrastructure.postgres.diccionario_sql import (
        SQL_INSERT_DICCIONARIO,
        filas_diccionario,
    )

    dicc, _ = _diccionario_real()
    columnas = re.search(r"\(([^)]*)\)\s*VALUES", SQL_INSERT_DICCIONARIO, re.IGNORECASE)

    nombres = [c.strip() for c in columnas.group(1).split(",")]
    assert len(nombres) == len(filas_diccionario(dicc)[0])
    assert SQL_INSERT_DICCIONARIO.count("%s") == len(nombres)


def test_f006_r17_filas_la_ficha_de_mart_llega_completa() -> None:
    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_diccionario

    dicc, _ = _diccionario_real()

    fila = next(
        f for f in filas_diccionario(dicc)
        if (f[0], f[1]) == ("mart", "fact_seguimiento_mensual")
    )
    (_esquema, _objeto, tipo, capa, consumo, motivo, _descripcion, _grano,
     clave, paso, refresco, avisos, n_columnas, _ficha) = fila

    assert (tipo, capa, consumo, refresco, paso) == (
        "tabla", "consumo", True, "nocturno", "build_mart",
    )
    assert motivo is None
    assert clave == ["obra_id", "partida_id", "anio_mes", "escenario"]
    assert n_columnas == 34
    assert "R-IMPORTE-MES" in avisos and "R-CLAVE-SUSTITUTA" in avisos


def test_f006_r12_filas_los_avisos_van_derivados_y_ordenados() -> None:
    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_diccionario

    dicc, _ = _diccionario_real()

    for fila in filas_diccionario(dicc):
        avisos = fila[11]
        assert list(avisos) == sorted(avisos)
        assert len(avisos) == len(set(avisos))


def test_f006_r22_filas_la_ficha_jsonb_es_determinista_y_completa() -> None:
    """`sort_keys=True`: dos publicaciones del mismo YAML dan el mismo texto, y
    un `diff` sobre la tabla es legible en vez de ser todo el JSON."""
    import json

    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_diccionario

    dicc, _ = _diccionario_real()

    fila = next(
        f for f in filas_diccionario(dicc)
        if (f[0], f[1]) == ("mart", "fact_seguimiento_mensual")
    )
    ficha = json.loads(fila[13])

    assert set(ficha) == {"columnas", "relaciones", "ejemplos_preguntas"}
    assert list(ficha) == sorted(ficha)
    assert len(ficha["columnas"]) == 34
    assert ficha["columnas"][0]["nombre"] == "fact_id", "se conserva el orden del YAML"
    importe_mes = next(c for c in ficha["columnas"] if c["nombre"] == "importe_mes")
    assert importe_mes["agregacion"] == "suma_solo_dentro_del_mes"
    assert importe_mes["unidad"] == "EUR"
    assert ficha["relaciones"][0]["cardinalidad"] in {"1:1", "1:N", "N:1", "N:N"}


def test_f006_r22_filas_el_jsonb_no_arrastra_claves_vacias() -> None:
    """Una columna sin `unidad` no publica `"unidad": null`: es ruido en cada
    una de las 332 columnas y el MCP tendría que filtrarlo."""
    import json

    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_diccionario

    dicc, _ = _diccionario_real()

    for fila in filas_diccionario(dicc):
        for columna in json.loads(fila[13])["columnas"]:
            assert None not in columna.values()
            assert "nombre" in columna and "significado" in columna


def test_f006_r9_filas_de_reglas_van_las_doce_en_su_orden() -> None:
    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_reglas

    dicc, _ = _diccionario_real()

    filas = filas_reglas(dicc)

    assert len(filas) == len(dicc.reglas)
    assert [f[6] for f in filas] == sorted(f[6] for f in filas), "ordenadas por `orden`"
    codigos = [f[0] for f in filas]
    assert "R-IMPORTE-MES" in codigos
    ambitos = dict(zip([f[0] for f in filas], [f[3] for f in filas], strict=True))
    assert "cierre.fact_cierre_mensual" in ambitos["R-IMPORTE-MES"]


def test_f006_r22_fila_de_publicacion_lleva_los_recuentos_reales() -> None:
    from datetime import datetime

    from etl_sigrid.infrastructure.postgres.diccionario_sql import fila_publicacion

    dicc, hash_fuente = _diccionario_real()
    ahora = datetime(2026, 8, 20, 2, 15, 0)

    fila = fila_publicacion(dicc, hash_fuente, ahora, "20260820T021500Z-abcdef",
                            _informe_real())
    (ident, version, hash_pub, publicado, batch,
     n_objetos, n_reglas, n_columnas, cobertura) = fila

    assert ident == 1, "singleton: siempre la fila 1"
    assert version == "1"
    assert hash_pub == hash_fuente and len(hash_pub) == 64
    assert publicado == ahora
    assert batch == "20260820T021500Z-abcdef"
    assert (n_objetos, n_reglas, n_columnas) == (
        len(dicc.fichas),
        len(dicc.reglas),
        sum(len(f.columnas) for f in dicc.fichas),
    )
    assert n_objetos >= 49 and n_columnas >= 593
    assert cobertura == 100.0


def test_f006_r22_la_cobertura_publicada_baja_si_falta_un_significado() -> None:
    """El número que se publica tiene que moverse con la realidad.

    La víctima se **deriva**: tiene que ser una ficha de la superficie de
    consumo, porque `cobertura_columnas` solo mide ahí. Este test elegía
    `fichas[0]` a ciegas y funcionó mientras la primera ficha por orden
    alfabético de fichero fue de `mart`; al entrar `aux.yaml` —fuera del consumo
    recomendado— la columna muda dejó de contar y el test habría pasado a
    comprobar nada si no llega a romper. El aserto de abajo impide que vuelva a
    elegir una ficha que no se mide.
    """
    from dataclasses import replace
    from datetime import datetime

    from etl_sigrid.domain.diccionario import Columna
    from etl_sigrid.infrastructure.postgres.diccionario_sql import fila_publicacion

    dicc, hash_fuente = _diccionario_real()
    fichas = list(dicc.fichas)
    indice = next(
        i for i, f in enumerate(fichas) if f.consumo_recomendado and f.columnas
    )
    victima = fichas[indice]
    assert victima.consumo_recomendado and victima.columnas
    fichas[indice] = replace(
        victima,
        columnas=(Columna(nombre="muda", significado=""), *victima.columnas),
    )
    tocado = replace(dicc, fichas=tuple(fichas))

    fila = fila_publicacion(tocado, hash_fuente, datetime(2026, 8, 20), None,
                            _informe_real())

    assert fila[8] < 100.0


# ---------------------------------------------------------------------------
# cliente · la publicación, con un doble (T16 · R17, R18)
#
# El doble no es un atajo: es la única forma admisible de probar esto desde
# este puesto. El `.env` apunta a `psql-albaranes-rs9k2`, el servidor que
# comparten `albaranes` y `partes` en producción, y esta feature no tiene
# ninguna necesidad de abrirlo.
# ---------------------------------------------------------------------------


class _CursorFalso:
    def __init__(self, diario: list, filas_catalogo=None) -> None:
        self._diario = diario
        self._filas = filas_catalogo or []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self._diario.append(("execute", " ".join(str(sql).split()), params))

    def executemany(self, sql, filas):
        self._diario.append(("executemany", " ".join(str(sql).split()), list(filas)))

    def fetchall(self):
        return self._filas


class _ConexionFalsa:
    def __init__(self, diario: list, filas_catalogo=None) -> None:
        self._diario = diario
        self._filas = filas_catalogo
        self.transacciones = 0

    def __enter__(self):
        self.transacciones += 1
        self._diario.append(("abrir_transaccion", None, None))
        return self

    def __exit__(self, *_):
        self._diario.append(("cerrar_transaccion", None, None))
        return False

    def cursor(self):
        return _CursorFalso(self._diario, self._filas)


def _cliente_falso(diario: list, filas_catalogo=None):
    """Un `PostgresClient` que no conecta con nada."""
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    cliente = object.__new__(PostgresClient)
    conexion = _ConexionFalsa(diario, filas_catalogo)
    cliente.connection = lambda: conexion  # type: ignore[method-assign]
    cliente._conexion_falsa = conexion
    return cliente


def _publicar_y_diario():
    from datetime import datetime

    dicc, hash_fuente = _diccionario_real()
    diario: list = []
    cliente = _cliente_falso(diario)

    filas = cliente.publicar_diccionario(
        dicc,
        hash_fuente=hash_fuente,
        informe=_informe_real(),
        batch_id="20260820T021500Z-abcdef",
        ahora=datetime(2026, 8, 20, 2, 15, 0),
    )
    return filas, diario, cliente


def test_f006_r17_publicar_escribe_las_tres_tablas() -> None:
    filas, diario, _ = _publicar_y_diario()

    sentencias = [d[1] for d in diario if d[0] in ("execute", "executemany")]
    assert any(s == "DELETE FROM _meta.diccionario" for s in sentencias)
    assert any(s == "DELETE FROM _meta.diccionario_reglas" for s in sentencias)
    assert any(s == "DELETE FROM _meta.diccionario_publicacion" for s in sentencias)
    assert any("INSERT INTO _meta.diccionario (" in s for s in sentencias)
    assert any("INSERT INTO _meta.diccionario_reglas (" in s for s in sentencias)
    assert any("INSERT INTO _meta.diccionario_publicacion (" in s for s in sentencias)
    dicc, _ = _diccionario_real()
    assert filas == len(dicc.fichas) + len(dicc.reglas) + 1


def test_f006_r18_publicar_va_en_una_sola_transaccion() -> None:
    """R18: o se ve el diccionario anterior completo, o el nuevo completo.

    Un MCP consultando durante la publicación no puede encontrarse la tabla a
    medias, y menos vacía: le haría inventarse los significados, que es justo lo
    que esta feature existe para impedir.
    """
    _, diario, cliente = _publicar_y_diario()

    assert cliente._conexion_falsa.transacciones == 1
    aperturas = [d for d in diario if d[0] == "abrir_transaccion"]
    assert len(aperturas) == 1
    assert diario[0][0] == "abrir_transaccion"
    assert diario[-1][0] == "cerrar_transaccion"


def test_f006_r18_publicar_no_hace_drop_ni_truncate() -> None:
    """Un `DROP` se llevaría los `GRANT` del rol del MCP."""
    _, diario, _ = _publicar_y_diario()

    for _, sentencia, _p in diario:
        if sentencia is None:
            continue
        assert "DROP" not in sentencia.upper()
        assert "TRUNCATE" not in sentencia.upper()


def test_f006_r18_publicar_borra_antes_de_insertar() -> None:
    """El orden importa: un `INSERT` antes del `DELETE` chocaría con la PK."""
    _, diario, _ = _publicar_y_diario()

    sentencias = [d[1] for d in diario if d[1]]
    borrado = next(i for i, s in enumerate(sentencias) if s == "DELETE FROM _meta.diccionario")
    insercion = next(i for i, s in enumerate(sentencias) if "INSERT INTO _meta.diccionario (" in s)
    assert borrado < insercion


def test_f006_r17_publicar_manda_las_filas_reales_no_un_ejemplo() -> None:
    """Se prueba con las fichas de verdad, todas: si el mecanismo no traga el
    contenido real, es ahora cuando hay que enterarse."""
    _, diario, _ = _publicar_y_diario()

    lotes = {d[1]: d[2] for d in diario if d[0] == "executemany"}
    fichas = next(v for k, v in lotes.items() if "INSERT INTO _meta.diccionario (" in k)
    reglas = next(v for k, v in lotes.items() if "diccionario_reglas" in k)

    dicc, _ = _diccionario_real()
    assert len(fichas) == len(dicc.fichas) >= 49
    assert len(reglas) == len(dicc.reglas)
    assert all(len(f) == 14 for f in fichas)
    assert all(len(r) == 7 for r in reglas)


def test_f006_r22_publicar_registra_la_version_y_el_hash() -> None:
    _, diario, _ = _publicar_y_diario()

    publicacion = next(
        d[2] for d in diario
        if d[0] == "execute" and "INSERT INTO _meta.diccionario_publicacion" in (d[1] or "")
    )

    assert publicacion[0] == 1
    assert len(publicacion[2]) == 64
    assert publicacion[4] == "20260820T021500Z-abcdef"
    dicc, _ = _diccionario_real()
    assert publicacion[5:] == (
        len(dicc.fichas),
        len(dicc.reglas),
        sum(len(f.columnas) for f in dicc.fichas),
        100.0,
    )


def test_f006_r28_list_objetos_catalogo_pregunta_por_los_esquemas_pedidos() -> None:
    """Es la fuente que dice la verdad, la que usará `check-diccionario`."""
    diario: list = []
    cliente = _cliente_falso(diario, filas_catalogo=[("mart", "v_pbi_fact", "vista")])

    objetos = cliente.list_objetos_catalogo(["mart", "cierre"])

    assert objetos == [("mart", "v_pbi_fact", "vista")]
    sentencia, params = next((d[1], d[2]) for d in diario if d[0] == "execute")
    assert "information_schema.tables" in sentencia
    assert "pg_proc" in sentencia, "las funciones también son objetos publicados"
    assert params == (["mart", "cierre"], ["mart", "cierre"])


# ---------------------------------------------------------------------------
# pipeline · el paso y su sitio (T17 · R19, R20, R21)
# ---------------------------------------------------------------------------


def _settings_falso():
    from types import SimpleNamespace

    return SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        ),
        # Lo mira el callback del grupo de la CLI al configurar el log.
        logging=SimpleNamespace(log_level="INFO", log_format="console"),
    )


def test_f006_r20_pipeline_publicar_va_entre_build_mart_y_apply_grants() -> None:
    """EL ORDEN NO ES COSMÉTICO.

    `apply_grants` concede `SELECT ON ALL TABLES IN SCHEMA _meta`, que es una
    foto del instante en que corre. Publicar después dejaría las tres tablas
    nuevas dependiendo solo del `ALTER DEFAULT PRIVILEGES`: funcionaría hoy y
    dejaría de funcionar el día que alguien toque esa regla.
    """
    import main
    from etl_sigrid.application.orchestrator import Orchestrator
    from etl_sigrid.application.steps.publicar_diccionario_step import (
        PublicarDiccionarioStep,
    )

    pasos = main.build_pipeline_steps(_settings_falso())

    nombres = [p.name for p in pasos]
    assert nombres == [
        "ingest_raw",
        "load_excel_aux",
        "build_stg",
        "build_mart",
        "publicar_diccionario",
        "apply_grants",
    ]

    paso = next(p for p in pasos if p.name == "publicar_diccionario")
    assert isinstance(paso, PublicarDiccionarioStep)
    assert paso.depends_on == ["build_mart"]
    assert paso.stage == "diccionario"

    orden = [p.name for p in Orchestrator(pasos)._topological_sort()]
    assert orden.index("publicar_diccionario") > orden.index("build_mart")
    assert orden.index("publicar_diccionario") < orden.index("apply_grants")


def test_f006_r14_pipeline_los_pasos_nocturnos_se_inyectan_desde_la_composicion() -> None:
    """Ni el paso ni el validador tienen una lista de pasos escrita a mano.

    Se inyecta DESPUÉS de componer el pipeline, que es lo único que evita la
    copia: el día que `build-cierre` entre en `run-all`, el veredicto de R14
    cambia solo.
    """
    import main

    pasos = main.build_pipeline_steps(_settings_falso())
    publicar = next(p for p in pasos if p.name == "publicar_diccionario")

    assert tuple(publicar.pasos_nocturnos) == tuple(p.name for p in pasos)
    assert "build_cierre" not in publicar.pasos_nocturnos


class _ClienteEspia:
    """Cliente que grita si alguien intenta escribir."""

    def __init__(self) -> None:
        self.llamadas: list[str] = []

    def execute_sql_file(self, path, **_):
        self.llamadas.append(f"execute_sql_file:{path.name}")

    def publicar_diccionario(self, *_a, **_k):
        self.llamadas.append("publicar_diccionario")
        from tests.test_f006_publicacion import _diccionario_real as _d

        dicc, _ = _d()
        return len(dicc.fichas) + len(dicc.reglas) + 1

    def connection(self):  # pragma: no cover - no debería llamarse
        raise AssertionError("el paso no debe abrir conexión por su cuenta")


def _paso(pasos_nocturnos=("build_mart",), cliente=None, directorio=None):
    from etl_sigrid.application.steps.publicar_diccionario_step import (
        PublicarDiccionarioStep,
    )

    return PublicarDiccionarioStep(
        _settings_falso(),
        pasos_nocturnos=pasos_nocturnos,
        client=cliente or _ClienteEspia(),
        batch_id="20260820T021500Z-abcdef",
        directorio=directorio,
    )


def test_f006_r17_paso_publica_el_diccionario_real_y_lo_cuenta() -> None:
    from etl_sigrid.domain.entities import StepStatus
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    espia = _ClienteEspia()
    resultado = _paso(pasos_del_pipeline_nocturno(), espia).run()

    assert resultado.status is StepStatus.SUCCESS
    dicc, _ = _diccionario_real()
    assert resultado.rows_processed == len(dicc.fichas) + len(dicc.reglas) + 1
    assert espia.llamadas == [
        "execute_sql_file:01_diccionario.sql",
        "publicar_diccionario",
    ], "el DDL idempotente va ANTES de escribir"
    assert resultado.metadata["n_objetos"] == len(dicc.fichas)
    assert resultado.metadata["n_reglas"] == len(dicc.reglas)
    assert resultado.metadata["n_columnas"] == sum(len(f.columnas) for f in dicc.fichas)
    assert resultado.metadata["cobertura_cols"] == 100.0
    assert len(resultado.metadata["hash_fuente"]) == 64


def test_f006_r19_paso_con_diccionario_invalido_no_escribe_nada(tmp_path) -> None:
    """R19: si no valida, FAILED **antes** de abrir la transacción de escritura.

    El diccionario anterior se queda publicado intacto, que es infinitamente
    mejor que publicar uno a medias: el MCP sigue respondiendo con la semántica
    de ayer en vez de inventársela.
    """
    from etl_sigrid.domain.entities import StepStatus

    (tmp_path / "00_global.yaml").write_text(
        "version: 1\nbase: sigrid_dm\npendientes: []\n", encoding="utf-8"
    )

    espia = _ClienteEspia()
    resultado = _paso(("build_mart",), espia, directorio=tmp_path).run()

    assert resultado.status is StepStatus.FAILED
    assert espia.llamadas == [], "no se toca la base con un diccionario inválido"
    assert "R9" in resultado.error_message or "R4" in resultado.error_message


def test_f006_r19_paso_con_yaml_ilegible_da_failed_legible(tmp_path) -> None:
    from etl_sigrid.domain.entities import StepStatus

    (tmp_path / "00_global.yaml").write_text("version: [1,\n", encoding="utf-8")

    espia = _ClienteEspia()
    resultado = _paso(("build_mart",), espia, directorio=tmp_path).run()

    assert resultado.status is StepStatus.FAILED
    assert espia.llamadas == []
    assert "00_global.yaml" in resultado.error_message
    assert "linea" in resultado.error_message.lower()


def test_f006_r21_paso_si_la_base_falla_no_deshace_el_build() -> None:
    """Un fallo de publicación es una noticia, no una catástrofe.

    `mart` queda construido y el diccionario anterior sigue publicado; el paso
    termina en FAILED para que `run-all` salga con código 1 y alguien lo mire.
    """
    from etl_sigrid.domain.entities import StepStatus
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    class _ClienteQueFalla(_ClienteEspia):
        def publicar_diccionario(self, *_a, **_k):
            self.llamadas.append("publicar_diccionario")
            raise RuntimeError("connection reset by peer")

    espia = _ClienteQueFalla()
    resultado = _paso(pasos_del_pipeline_nocturno(), espia).run()

    assert resultado.status is StepStatus.FAILED
    assert "connection reset" in resultado.error_message
    assert "publicar_diccionario" in espia.llamadas


def test_f006_r25_paso_con_cobertura_rota_no_publica(tmp_path) -> None:
    """La puerta de cobertura también corre en la publicación, no solo en los
    tests: publicar un diccionario incompleto es publicar huecos."""
    import shutil

    from etl_sigrid.domain.entities import StepStatus

    for fichero in DIR_DICCIONARIO.glob("*.yaml"):
        shutil.copy(fichero, tmp_path / fichero.name)
    global_yaml = tmp_path / "00_global.yaml"
    # Se borra POR LÍNEA y no por substring: `      - stg.plan_mensual` es un
    # ámbito de regla y contiene la misma cadena. Un `replace` se lleva las dos
    # y entonces lo que rompe es el YAML, no la cobertura.
    lineas = global_yaml.read_text(encoding="utf-8").split("\n")
    global_yaml.write_text(
        "\n".join(ln for ln in lineas if ln != "  - stg.plan_mensual"),
        encoding="utf-8",
    )

    espia = _ClienteEspia()
    resultado = _paso(("build_mart",), espia, directorio=tmp_path).run()

    assert resultado.status is StepStatus.FAILED
    assert espia.llamadas == []
    assert "stg.plan_mensual" in resultado.error_message


# ---------------------------------------------------------------------------
# cli · `python main.py publicar-diccionario` (T18 · R17, DA-1)
# ---------------------------------------------------------------------------


class _PgDeCli:
    """Doble del cliente para la CLI: registra lo que se le pide."""

    def __init__(self, al_publicar=None) -> None:
        self.llamadas: list[str] = []
        self.pasos: list[tuple[str, str]] = []
        self._al_publicar = al_publicar

    # lo que usa `_arrancar_ejecucion` (F-024, R4)
    def abortar_runs_huerfanos(self, *_a, **_k):
        self.llamadas.append("abortar_runs_huerfanos")
        return []

    # lo que usa el grabador
    def record_run_start(self, *_a, **_k):
        return 1

    def record_run_completed(self, **kwargs):
        self.pasos.append((kwargs.get("step", "?"), kwargs.get("status", "?")))
        return 1

    def record_run(self, *_a, **_k):
        return 1

    # lo que usa el paso
    def execute_sql_file(self, path, **_k):
        self.llamadas.append(f"execute_sql_file:{path.name}")

    def publicar_diccionario(self, *_a, **_k):
        self.llamadas.append("publicar_diccionario")
        if self._al_publicar is not None:
            raise self._al_publicar
        from tests.test_f006_publicacion import _diccionario_real as _d

        dicc, _ = _d()
        return len(dicc.fichas) + len(dicc.reglas) + 1


def _cli_runner(monkeypatch, pg):
    from click.testing import CliRunner

    import main

    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    monkeypatch.setattr(main, "get_settings", _settings_falso)
    return CliRunner()


def test_f006_r17_cli_el_comando_publica_y_sale_con_cero(monkeypatch) -> None:
    import main

    pg = _PgDeCli()
    resultado = _cli_runner(monkeypatch, pg).invoke(main.cli, ["publicar-diccionario"])

    assert resultado.exit_code == 0, resultado.output
    assert "execute_sql_file:01_diccionario.sql" in pg.llamadas
    assert "publicar_diccionario" in pg.llamadas


def test_f006_r24_cli_marca_huerfanas_antes_de_escribir(monkeypatch) -> None:
    """Escribe, así que pasa por el mismo protocolo que el resto (F-024, R4)."""
    import main

    pg = _PgDeCli()
    _cli_runner(monkeypatch, pg).invoke(main.cli, ["publicar-diccionario"])

    assert pg.llamadas[0] == "abortar_runs_huerfanos"


def test_f006_r17_cli_registra_el_paso_en_meta(monkeypatch) -> None:
    import main

    pg = _PgDeCli()
    _cli_runner(monkeypatch, pg).invoke(main.cli, ["publicar-diccionario"])

    assert ("publicar_diccionario", "SUCCESS") in pg.pasos


def test_f006_r21_cli_si_falla_sale_con_uno(monkeypatch) -> None:
    import main

    pg = _PgDeCli(al_publicar=RuntimeError("se cayó la red"))
    resultado = _cli_runner(monkeypatch, pg).invoke(main.cli, ["publicar-diccionario"])

    assert resultado.exit_code == 1
    assert ("publicar_diccionario", "FAILED") in pg.pasos


def test_f006_r14_cli_usa_los_pasos_nocturnos_del_pipeline_real(monkeypatch) -> None:
    """El comando suelto valida con el MISMO criterio que la noche.

    Si usara otro, un diccionario podría publicarse a mano y ser rechazado por
    `run-all`, o al revés, que es peor.
    """
    import main
    from etl_sigrid.application.steps.publicar_diccionario_step import (
        PublicarDiccionarioStep,
    )

    vistos: list[tuple[str, ...]] = []
    original = PublicarDiccionarioStep.run

    def espiar(self):
        vistos.append(tuple(self.pasos_nocturnos))
        return original(self)

    monkeypatch.setattr(PublicarDiccionarioStep, "run", espiar)
    _cli_runner(monkeypatch, _PgDeCli()).invoke(main.cli, ["publicar-diccionario"])

    esperados = tuple(p.name for p in main.build_pipeline_steps(_settings_falso()))
    assert vistos == [esperados]


def test_f006_da1_los_builds_manuales_no_republican_el_diccionario() -> None:
    """DA-1: solo `run-all` y el comando suelto.

    El diccionario no depende de los datos, así que publicarlo al final de cada
    build manual no añadiría nada y sí superficie de fallo.
    """
    import main

    fuente = Path(main.__file__).read_text(encoding="utf-8")

    for comando in ("build-cierre", "build-compras", "build-maestros",
                    "build-retenciones"):
        inicio = fuente.index(f'@cli.command("{comando}")')
        fin = fuente.index("@cli.command(", inicio + 10)
        assert "PublicarDiccionarioStep" not in fuente[inicio:fin], comando


def test_f006_r17_el_comando_esta_documentado_en_claude_md() -> None:
    """El mapa del repositorio lista los comandos: si no está, no existe."""
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")

    assert "publicar-diccionario" in texto


# ---------------------------------------------------------------------------
# ddl · la vista, con sus columnas fijadas EN ORDEN (defecto 6 y 7)
#
# Era la unica de las cuatro estructuras del contrato sin contraste exacto: solo
# se comprobaba, por subcadena, que 15 de sus nombres aparecieran. Rigor
# asimetrico justo en la pieza mas expuesta, porque es la que `mcp-bbdd` va a
# consultar de verdad.
#
# El orden importa tanto como los nombres: quien desempaquete por posicion se
# encuentra los campos corridos si alguien inserta una columna por el medio, y
# la cabecera del propio fichero SQL prohibe reordenar precisamente por eso.
# ---------------------------------------------------------------------------

#: Las 18 columnas de `design.md` §4.2, EN SU ORDEN, mas lo que se ha anadido
#: despues AL FINAL, que es la unica forma compatible de crecer.
COLUMNAS_V_DICCIONARIO = [
    # --- las 18 del contrato original, posiciones 1 a 18 -------------------
    "esquema",
    "objeto",
    "tipo",
    "capa",
    "consumo_recomendado",
    "descripcion",
    "grano",
    "clave_negocio",
    "refresco",
    "avisos",
    "n_columnas",
    "ficha",
    "paso_etl",
    "ultimo_ok_finished_at",
    "horas_desde_ultimo_ok",
    "ultimo_intento_status",
    "diccionario_version",
    "diccionario_publicado_en",
    # --- anadidas despues, siempre al final --------------------------------
    "motivo_no_consumo",
]


def test_f006_r15_ddl_la_vista_proyecta_estas_columnas_y_en_este_orden() -> None:
    from tests.test_f006_fichas import columnas_proyectadas

    proyectadas = columnas_proyectadas(_cuerpo_de_la_vista() + "\n;")

    assert proyectadas == COLUMNAS_V_DICCIONARIO


def test_f006_r15_las_dieciocho_del_diseno_conservan_su_posicion() -> None:
    """El contrato de `design.md` §4.2 sigue intacto posicion a posicion.

    Anadir al final es compatible; insertar por el medio corre todo lo que va
    detras y rompe a quien desempaquete por indice. La columna 19 se anadio
    despues, y por eso esta la 19 y no la 6.
    """
    from tests.test_f006_fichas import columnas_proyectadas

    diseno = (RAIZ / "specs" / "F-006-mcp-azure" / "design.md").read_text(
        encoding="utf-8"
    )
    inicio = diseno.index("CREATE OR REPLACE VIEW _meta.v_diccionario AS")
    del_diseno = columnas_proyectadas(diseno[inicio:].split("```")[0])

    proyectadas = columnas_proyectadas(_cuerpo_de_la_vista() + "\n;")

    assert del_diseno == proyectadas, (
        "el diseno y la vista real tienen que proyectar lo mismo, en el mismo orden"
    )
    # El invariante es el PREFIJO, no cual es la ultima columna: fijar la ultima
    # rompia justo el crecimiento que la cabecera del DDL declara compatible
    # —anadir al final— aunque se actualizasen el SQL, el diseno y la lista.
    assert proyectadas[:18] == COLUMNAS_V_DICCIONARIO[:18], (
        "las 18 columnas del contrato original conservan su posicion"
    )
    assert "motivo_no_consumo" in proyectadas[18:], (
        "lo anadido despues va detras de las 18, en cualquier orden entre si"
    )


def test_f006_r23_el_diseno_documenta_la_columna_anadida() -> None:
    """Enmendar el documento es parte de anadir la columna, no un extra."""
    diseno = (RAIZ / "specs" / "F-006-mcp-azure" / "design.md").read_text(
        encoding="utf-8"
    )
    seccion = diseno[diseno.index("### 4.2"):diseno.index("### 4.3")]

    assert "motivo_no_consumo" in seccion


# ---------------------------------------------------------------------------
# Lo que faltaba fijar por un test, aunque hoy sea cierto
# ---------------------------------------------------------------------------


def test_f006_r20_apply_grants_no_depende_de_la_publicacion() -> None:
    """Si el diccionario no valida, los GRANT tienen que aplicarse igual.

    Es un test ESTRUCTURAL, no conductual: comprueba `depends_on`, que es la
    entrada de la que el orquestador decide si salta un paso. Protege del
    escenario que nombra —que alguien anada `publicar_diccionario` a esa lista
    «para que quede ordenado» y una noche con el diccionario invalido deje al
    MCP sin permisos, que es el fallo que R20 existe para evitar— y **no** de un
    cambio en la logica de salto del propio orquestador, que tiene sus tests.
    """
    import main

    pasos = main.build_pipeline_steps(_settings_falso())
    grants = next(p for p in pasos if p.name == "apply_grants")

    assert grants.depends_on == ["build_mart"]
    assert "publicar_diccionario" not in grants.depends_on


def test_f006_r18_una_excepcion_a_mitad_de_la_publicacion_hace_rollback() -> None:
    """Atomicidad comprobada por CONDUCTA, no solo por estructura.

    La rama del `rollback` **no la ejecutaba ningun test del repositorio**: el
    `commit` si —`test_f005_conexion.py` usa el `connection()` real—, pero para
    llegar al `rollback` hace falta que algo falle dentro del `with`, y eso no
    lo provocaba nadie. Era la mitad de la garantia que sostiene el contrato, sin
    ejercitar. Aqui se usa el `connection()` de verdad y solo se sustituye la
    apertura del socket.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    diario: list[str] = []

    class _ConexionQueRegistra:
        def cursor(self):
            raise RuntimeError("se cayó la red a mitad del INSERT")

        def commit(self):
            diario.append("commit")

        def rollback(self):
            diario.append("rollback")

        def close(self):
            diario.append("close")

    cliente = object.__new__(PostgresClient)
    cliente._bootstrap_done = True
    cliente._conninfo = "dsn-de-mentira"
    cliente._connect = lambda _dsn: _ConexionQueRegistra()

    with pytest.raises(RuntimeError, match="se cayó la red"), cliente.connection() as c:
        c.cursor()

    assert diario == ["rollback", "close"], diario
    assert "commit" not in diario


def test_f006_r18_sin_excepcion_hace_commit() -> None:
    """Control del test de arriba: si nunca hiciera commit, pasaria en falso."""
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    diario: list[str] = []

    class _ConexionQueRegistra:
        def commit(self):
            diario.append("commit")

        def rollback(self):  # pragma: no cover - no deberia llamarse
            diario.append("rollback")

        def close(self):
            diario.append("close")

    cliente = object.__new__(PostgresClient)
    cliente._bootstrap_done = True
    cliente._conninfo = "dsn-de-mentira"
    cliente._connect = lambda _dsn: _ConexionQueRegistra()

    with cliente.connection():
        pass

    assert diario == ["commit", "close"], diario
