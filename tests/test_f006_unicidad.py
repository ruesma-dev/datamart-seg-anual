# tests/test_f006_unicidad.py
"""
La comprobación de unicidad de la clave de negocio (F-006, T26).

Cierra la mitad del problema que la puerta offline **no puede** cubrir. La
puerta sabe si la clave nombra columnas de más —eso está en el `GROUP BY`— pero
no si es demasiado **corta**: eso exige saber si una columna depende
funcionalmente de otra, y eso no está en el SQL, está en los datos.

Y es el hueco que más se propaga: la detección de fan-out deriva la unicidad de
la clave declarada, así que una clave reducida no solo miente sobre el grano,
además **desarma la comprobación de cardinalidades**.

Aquí **no se abre ninguna conexión**. Se comprueba la CONSTRUCCIÓN de las
consultas y el manejo del resultado, con dobles, como se hizo con el bloque E.
Ejecutarlas contra la base es T27 y lo hace el humano.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest

from etl_sigrid.domain.diccionario import Columna, Diccionario, Ficha
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from etl_sigrid.infrastructure.postgres.unicidad_sql import (
    TIMEOUT_POR_CONSULTA_S,
    ConsultaUnicidad,
    consultas_de_unicidad,
    interpretar_resultado,
    objetos_saltados,
    sentencias_previas,
    veredicto_no_comprobado,
)

DIR_DICCIONARIO = pathlib.Path(__file__).resolve().parents[1] / "config" / "diccionario"


@lru_cache(maxsize=1)
def _dicc() -> Diccionario:
    return cargar_diccionario(DIR_DICCIONARIO)[0]


def _ficha(**kwargs) -> Ficha:
    base = dict(
        esquema="mart",
        objeto="ejemplo",
        tipo="tabla",
        capa="consumo",
        consumo_recomendado=True,
        descripcion="D" * 60,
        grano="Una fila por obra y mes, que es su clave.",
        clave_negocio=("obra_id", "anio_mes"),
        paso_etl="build_mart",
        refresco="nocturno",
        columnas=(Columna(nombre="obra_id", significado="S" * 40),),
        relaciones=(),
        ejemplos_preguntas=("Cuanto llevamos gastado en la obra X",),
    )
    base.update(kwargs)
    return Ficha(**base)


def _diccionario_con(*fichas: Ficha) -> Diccionario:
    return Diccionario(
        version="1",
        base="sigrid_dm",
        fichas=fichas,
        reglas=(),
        esquemas={},
        pendientes=(),
        global_raw={},
    )


# ---------------------------------------------------------------------------
# La consulta que se genera
# ---------------------------------------------------------------------------


def test_f006_t26_la_consulta_agrupa_por_la_clave_entera() -> None:
    """La forma exacta que se acordó, y el porqué está en el módulo."""
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))

    assert consulta.objeto == "mart.ejemplo"
    assert consulta.clave == ("obra_id", "anio_mes")
    assert "GROUP BY obra_id, anio_mes" in consulta.sql
    assert "HAVING count(*) > 1" in consulta.sql
    assert "FROM mart.ejemplo" in consulta.sql
    # Devuelve las dos cifras que hacen accionable el resultado.
    assert "claves_duplicadas" in consulta.sql
    assert "filas_implicadas" in consulta.sql


def test_f006_t26_no_se_usa_count_distinct() -> None:
    """`count(*) - count(DISTINCT …)` descartaría los NULOS y daría un número.

    Se prefiere `GROUP BY … HAVING` porque agrupa los NULOS **como un valor
    más**, que es como se comportan en un `JOIN` —y el JOIN es lo que le va a
    salir mal al agente—, y porque dice CUÁNTAS claves duplican.
    """
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))
    assert "DISTINCT" not in consulta.sql.upper()


def test_f006_t26_la_consulta_de_detalle_devuelve_las_claves_que_colisionan() -> None:
    """«Hay 12 duplicados» no es accionable; «estos son» sí."""
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))
    assert "SELECT obra_id, anio_mes, count(*)" in consulta.sql_detalle
    assert "ORDER BY filas DESC" in consulta.sql_detalle
    assert "LIMIT" in consulta.sql_detalle


def test_f006_t26_un_identificador_raro_no_se_interpola() -> None:
    """El diccionario es un YAML editable a mano y esto acaba en un `SELECT`."""
    malicioso = _ficha(clave_negocio=("obra_id; DROP TABLE mart.x --",))
    with pytest.raises(ValueError, match="no interpolable"):
        consultas_de_unicidad(_diccionario_con(malicioso))


# ---------------------------------------------------------------------------
# A qué objetos alcanza, y por qué a los demás no
# ---------------------------------------------------------------------------


def test_f006_t26_se_salta_lo_que_el_motor_ya_garantiza() -> None:
    """Pagar un escaneo por lo que impone una PRIMARY KEY no tiene sentido."""
    sustituta = _ficha(
        objeto="con_sustituta",
        clave_negocio=("fact_id",),
        columnas=(
            Columna(nombre="fact_id", significado="S" * 40, agregacion="clave_sustituta"),
        ),
    )
    de_raw = _ficha(esquema="raw", objeto="obr", clave_negocio=("ide",), columnas=())

    consultas = consultas_de_unicidad(_diccionario_con(sustituta, de_raw))
    assert consultas == []

    motivos = dict(objetos_saltados(_diccionario_con(sustituta, de_raw)))
    assert "sustituta" in motivos["mart.con_sustituta"]
    assert "PRIMARY KEY" in motivos["raw.obr"]


def test_f006_t26_se_saltan_las_funciones_y_las_fichas_sin_clave() -> None:
    funcion = _ficha(objeto="fn_algo", tipo="funcion", grano=None, clave_negocio=())
    sin_clave = _ficha(objeto="sin_clave", clave_negocio=(), consumo_recomendado=False)

    assert consultas_de_unicidad(_diccionario_con(funcion, sin_clave)) == []
    motivos = dict(objetos_saltados(_diccionario_con(funcion, sin_clave)))
    assert "funcion" in motivos["mart.fn_algo"]
    assert "no declara clave" in motivos["mart.sin_clave"]


def test_f006_t26_el_alcance_por_defecto_es_la_superficie_de_consumo() -> None:
    """Decisión de coste y de daño, documentada en el módulo."""
    de_consumo = _ficha(objeto="de_consumo")
    interna = _ficha(
        objeto="interna",
        consumo_recomendado=False,
        motivo_no_consumo="M" * 40,
    )
    dicc = _diccionario_con(de_consumo, interna)

    assert [c.objeto for c in consultas_de_unicidad(dicc)] == ["mart.de_consumo"]
    assert [c.objeto for c in consultas_de_unicidad(dicc, solo_consumo=False)] == [
        "mart.de_consumo",
        "mart.interna",
    ]


def test_f006_t26_sobre_el_diccionario_real_alcanza_a_las_claves_compuestas() -> None:
    """El control: donde está el riesgo es en las claves de varias columnas.

    Si este número se desplomara, el generador habría dejado de ver los objetos
    que importan y el chequeo pasaría en vacío.
    """
    todas = consultas_de_unicidad(_dicc(), solo_consumo=False)
    compuestas = [c for c in todas if len(c.clave) > 1]

    assert len(todas) >= 50, f"solo {len(todas)} objetos con clave que comprobar"
    assert len(compuestas) >= 20, (
        f"solo {len(compuestas)} claves compuestas; ahí es donde vive el riesgo "
        f"de «la clave es demasiado corta»"
    )
    # Y ninguna de `raw`, que el motor ya garantiza.
    assert not [c for c in todas if c.objeto.startswith("raw.")]


# ---------------------------------------------------------------------------
# El coste: contra un servidor compartido en producción
# ---------------------------------------------------------------------------


def test_f006_t26_la_transaccion_acota_el_tiempo_y_no_escribe() -> None:
    """`SET LOCAL` no toca la configuración del servidor; el READ ONLY lo blinda.

    Y se comprueba que el **cliente las emite**, no solo que el constructor las
    fabrique. La versión anterior devolvía `BEGIN READ ONLY … COMMIT` que **no
    llamaba nadie**, mientras el comando anunciaba «transaccion READ ONLY» por
    pantalla contra un servidor compartido con producción: un test verde sobre
    código muerto, sosteniendo una garantía falsa y además impresa.
    """
    previas = sentencias_previas(timeout_s=15)
    assert previas[0] == "SET LOCAL statement_timeout = '15s'"
    assert previas[1] == "SET LOCAL transaction_read_only = on"
    assert TIMEOUT_POR_CONSULTA_S > 0

    # Lo que de verdad se ejecuta, en orden y antes de la consulta.
    cursor = _CursorFalso(fila=(0, 0))
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))
    _comprobar(_ClienteFalso(_ConexionFalsa(cursor)), consulta, timeout=15)

    assert cursor.ejecutadas[:2] == list(previas), (
        f"el cliente no emite las sentencias previas: {cursor.ejecutadas[:2]}"
    )
    assert "GROUP BY" in cursor.ejecutadas[2]


#: Los módulos que este barrido cubre, y por tanto el ALCANCE sobre el que
#: concluye. Está escrito porque la vez anterior dije «era el único» y era
#: cierto **dentro de un alcance que no declaré**: solo miraba `unicidad_sql`, y
#: al ampliarlo apareció `list_objetos_catalogo`, duplicado de un método mío con
#: el mismo SQL y con un test como único consumidor.
#:
#: Una afirmación de completitud sin su alcance es de la misma familia que las
#: que esta feature lleva trece pasadas corrigiendo.
MODULOS_BARRIDOS = (
    "etl_sigrid/infrastructure/postgres/unicidad_sql.py",
    "etl_sigrid/infrastructure/postgres/catalogo.py",
    "etl_sigrid/infrastructure/postgres/diccionario_sql.py",
    "etl_sigrid/domain/inventario.py",
    "etl_sigrid/infrastructure/diccionario/cargador_yaml.py",
)

#: Dónde puede vivir un consumidor legítimo. Si una función solo aparece en
#: `tests/`, es código muerto con test verde.
CONSUMIDORES = (
    "main.py",
    "etl_sigrid/infrastructure/postgres/postgres_client.py",
    "etl_sigrid/application/steps/publicar_diccionario_step.py",
)


def _funciones_publicas(texto: str) -> list[str]:
    return re.findall(r"^def ([a-z][a-z_0-9]*)\(", texto, re.M)


def _metodos_publicos(texto: str) -> list[str]:
    return re.findall(r"^    def ([a-z][a-z_0-9]*)\(", texto, re.M)


def test_f006_control_el_barrido_de_codigo_muerto_declara_su_alcance() -> None:
    """El alcance existe, es el que se dice, y no está vacío."""
    raiz = pathlib.Path(__file__).resolve().parents[1]
    for ruta in MODULOS_BARRIDOS + CONSUMIDORES:
        assert (raiz / ruta).exists(), f"{ruta} ya no existe: revisar el alcance"
    assert len(MODULOS_BARRIDOS) >= 5


def test_f006_ningun_constructor_esta_muerto_en_el_alcance_declarado() -> None:
    """Una función que solo usa su test es una garantía sin respaldo.

    Fue el caso de `sentencias_de_la_transaccion`, que fabricaba un
    `BEGIN READ ONLY` que **nadie emitía** mientras el comando lo anunciaba por
    pantalla. Y de `list_objetos_catalogo`, duplicado con el mismo SQL.
    """
    raiz = pathlib.Path(__file__).resolve().parents[1]
    consumidores = "\n".join(
        (raiz / f).read_text(encoding="utf-8") for f in CONSUMIDORES
    )

    muertos: list[str] = []
    for ruta in MODULOS_BARRIDOS:
        texto = (raiz / ruta).read_text(encoding="utf-8")
        otros = "\n".join(
            (raiz / m).read_text(encoding="utf-8")
            for m in MODULOS_BARRIDOS
            if m != ruta
        )
        for nombre in _funciones_publicas(texto):
            propio = texto.replace(f"def {nombre}(", "", 1)
            usado = (
                f"{nombre}(" in consumidores
                or f"{nombre}(" in propio
                or f"{nombre}(" in otros
                or f"import {nombre}" in consumidores
            )
            if not usado:
                muertos.append(f"{ruta}::{nombre}")

    assert muertos == [], (
        f"código muerto con test verde: {muertos}. Alcance del barrido: "
        f"{list(MODULOS_BARRIDOS)}"
    )


def test_f006_ningun_metodo_del_cliente_de_f006_esta_duplicado() -> None:
    """Dos métodos con el mismo SQL es la otra cara del código muerto.

    `list_objetos_catalogo` y `fetch_catalogo_objetos` ejecutaban la misma
    consulta; el segundo lo escribí yo en la tanda que decía haber barrido el
    código muerto.
    """
    raiz = pathlib.Path(__file__).resolve().parents[1]
    cliente = (
        raiz / "etl_sigrid/infrastructure/postgres/postgres_client.py"
    ).read_text(encoding="utf-8")

    usos = cliente.count("SQL_OBJETOS_CATALOGO")
    assert usos <= 2, (
        f"`SQL_OBJETOS_CATALOGO` aparece {usos} veces en el cliente: "
        f"probablemente hay dos métodos haciendo lo mismo"
    )


# ---------------------------------------------------------------------------
# Cómo se lee el resultado
# ---------------------------------------------------------------------------


def test_f006_t26_un_resultado_vacio_no_dice_que_la_clave_sea_correcta() -> None:
    """La frase importa: es la diferencia entre comprobar y garantizar.

    Una clave puede ser insuficiente y no haber colisionado todavía; basta con
    que ninguna obra haya repetido aún esa combinación.
    """
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))
    texto = interpretar_resultado(consulta, 0, 0)

    assert texto.startswith("OK")
    assert "no contradicen" in texto
    assert "correcta" in texto and "No prueba que sea correcta" in texto


def test_f006_t26_un_duplicado_dice_objeto_clave_y_cuantas_filas() -> None:
    """Requisito: que la corrección sea evidente sin volver a investigar."""
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))
    texto = interpretar_resultado(consulta, 12, 37)

    assert texto.startswith("KO")
    assert "mart.ejemplo" in texto
    assert "obra_id, anio_mes" in texto
    assert "12" in texto and "37" in texto
    # Y la consulta para ver cuáles, pegada en el propio mensaje.
    assert "ORDER BY filas DESC" in texto
    # Y el efecto de segundo orden, que es lo que no se ve solo.
    assert "fan-out" in texto


def test_f006_t26_un_timeout_nunca_se_cuenta_como_correcto() -> None:
    """Si no, el límite que protege el servidor sería una forma de aprobar."""
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))
    texto = veredicto_no_comprobado(consulta, "timeout de 30s")

    assert "NO COMPROBADO" in texto
    assert "No es un OK" in texto
    assert not texto.startswith("OK")


# ---------------------------------------------------------------------------
# El cliente, con un doble. NO se abre ninguna conexión.
# ---------------------------------------------------------------------------


class _CursorFalso:
    def __init__(self, fila, revienta=None):
        self.fila = fila
        self.revienta = revienta
        self.ejecutadas: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, *_args):
        self.ejecutadas.append(sql)
        if self.revienta is not None and "GROUP BY" in sql:
            raise self.revienta

    def fetchone(self):
        return self.fila


class _ConexionFalsa:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = True
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


class _ClienteFalso:
    """Solo lo que `comprobar_unicidad` usa: `connection()`."""

    def __init__(self, conexion):
        self._conexion = conexion

    def connection(self):
        return self._conexion


def _comprobar(cliente, consulta, timeout=30):
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    return PostgresClient.comprobar_unicidad(cliente, consulta, timeout)


def test_f006_t26_el_cliente_acota_el_tiempo_y_devuelve_las_dos_cifras() -> None:
    cursor = _CursorFalso(fila=(3, 9))
    conexion = _ConexionFalsa(cursor)
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))

    assert _comprobar(_ClienteFalso(conexion), consulta, timeout=45) == (3, 9)

    assert cursor.ejecutadas[0] == "SET LOCAL statement_timeout = '45s'"
    assert cursor.ejecutadas[1] == "SET LOCAL transaction_read_only = on"
    assert "GROUP BY obra_id, anio_mes" in cursor.ejecutadas[2]
    assert conexion.commits == 1 and conexion.rollbacks == 0


def test_f006_t26_un_timeout_del_motor_devuelve_none_y_no_deja_la_transaccion_abierta() -> None:
    """`None` es «no lo sabemos», y el `rollback` es lo que no deja basura.

    Sin ese `rollback`, una consulta cancelada dejaría la transacción en estado
    fallido y la siguiente del bucle reventaría por un motivo que no es el suyo,
    contra un servidor que además comparten otros dos proyectos.
    """
    import psycopg

    cursor = _CursorFalso(fila=None, revienta=psycopg.errors.QueryCanceled("timeout"))
    conexion = _ConexionFalsa(cursor)
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))

    assert _comprobar(_ClienteFalso(conexion), consulta) is None
    assert conexion.rollbacks == 1 and conexion.commits == 0


def _cuerpo_de_comprobar_unicidad() -> str:
    """El metodo entero, hasta el siguiente `def` del mismo nivel.

    Rebanar por numero de caracteres era fragil y ya cortaba el metodo por la
    mitad: el test decia que faltaba `UndefinedTable` cuando estaba tres lineas
    mas abajo.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    fuente = pathlib.Path(
        PostgresClient.__module__.replace(".", "/") + ".py"
    ).read_text(encoding="utf-8")
    desde = fuente.index("    def comprobar_unicidad")
    resto = fuente[desde + 10 :]
    hasta = re.search(chr(10) + r"    def \w+", resto)
    return resto[: hasta.start()] if hasta else resto


def _codigo_de_comprobar_unicidad() -> str:
    """Solo el codigo, sin el docstring.

    Se busca la ASIGNACION (`autocommit =`) y no la palabra: el codigo lleva un
    comentario que explica por que no se toca, y buscar la palabra suelta hacia
    que el propio aviso disparase el test.
    """
    cuerpo = _cuerpo_de_comprobar_unicidad()
    trozos = cuerpo.split('"""')
    return trozos[2] if len(trozos) > 2 else cuerpo


def test_f006_t26_control_el_doble_ejercita_el_camino_real() -> None:
    """Si el método dejara de usar `connection()`, el doble no lo notaría.

    Es el control que impide que estos tests se conviertan en una comprobación
    de sí mismos: se afirma que el método REAL es el que se está llamando.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    assert hasattr(PostgresClient, "comprobar_unicidad")
    cuerpo = _cuerpo_de_comprobar_unicidad()
    # El texto de las sentencias previas vive en `unicidad_sql`; aqui se
    # comprueba que el cliente las PIDA y las ejecute.
    assert "sentencias_previas" in cuerpo
    assert "QueryCanceled" in cuerpo
    assert "UndefinedTable" in cuerpo
    assert "rollback" in cuerpo
    # Y que NO se toque `autocommit`, que es lo que reventó contra la base real.
    assert "autocommit =" not in _codigo_de_comprobar_unicidad()


def test_f006_t26_el_cliente_no_toca_autocommit() -> None:
    """Lo aprendió la ejecución real, no el doble. Y es la lección de la tanda.

    La primera versión hacía `conn.autocommit = False` antes de la consulta. El
    doble no se quejó —ahí `autocommit` es un atributo normal— y contra la base
    reventó a la primera:

        psycopg.ProgrammingError: can't change 'autocommit' now:
        connection in transaction status INTRANS

    `self.connection()` devuelve una conexión que **ya viene en transacción**, así
    que `SET LOCAL` funciona sin tocar nada. Es exactamente lo que un doble no
    puede garantizar: el doble prueba que llamas a lo que crees, no que el otro
    extremo se comporte como crees.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    cuerpo = _cuerpo_de_comprobar_unicidad()
    assert "autocommit =" not in _codigo_de_comprobar_unicidad(), (
        "volver a tocar `autocommit` reventaría contra la base con INTRANS"
    )


def test_f006_t26_un_objeto_fichado_que_no_existe_no_tumba_el_chequeo() -> None:
    """El otro hallazgo de la ejecución real: `cierre.v_pbi_planif_vs_real`.

    Está fichado, el repositorio lo crea y la base no lo tiene porque
    `build-cierre` no se ha vuelto a lanzar. La primera versión del comando
    moría con `UndefinedTable` a mitad del recorrido y se llevaba por delante
    las comprobaciones que faltaban. Ahora es un veredicto más —y uno valioso:
    dice que la base va por detrás del repositorio—.
    """
    import psycopg

    from etl_sigrid.infrastructure.postgres.unicidad_sql import veredicto_no_existe

    cursor = _CursorFalso(
        fila=None, revienta=psycopg.errors.UndefinedTable("no existe")
    )
    conexion = _ConexionFalsa(cursor)
    (consulta,) = consultas_de_unicidad(_diccionario_con(_ficha()))

    assert _comprobar(_ClienteFalso(conexion), consulta) == "NO_EXISTE"
    assert conexion.rollbacks == 1

    texto = veredicto_no_existe(consulta)
    assert "NO EXISTE" in texto and "No es un OK" in texto
