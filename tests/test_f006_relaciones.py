# tests/test_f006_relaciones.py
"""
La comprobación de que cada relación declarada UNE de verdad (F-006, T40).

Por qué existe, con el incidente delante. La batería de aceptación descubrió que
`retenciones.movimientos.obra_id -> maestro.obras.obra_id` casaba **0 de 261**
valores: `obra_id` en `retenciones` es el `ide` del CENTRO DE COSTE, una entidad
distinta y contigua a la de la obra. Un `INNER JOIN` por ahí devuelve cero filas
y un `LEFT JOIN` devuelve todo a NULL, **en silencio y sin error**. El
diccionario publicaba esa relación como un hecho.

Lo que la puerta offline ya cubría y lo que no. El validador del dominio
comprueba que la relación RESUELVE —que el destino existe, que la columna está
documentada, que la cardinalidad no promete una unicidad falsa—. Todo eso es
derivable del texto. Lo que no es derivable del texto es **si los valores de un
lado aparecen en el otro**: eso está en los datos, y ahí solo se llega
ejecutando el JOIN.

Aquí **no se abre ninguna conexión**. Se comprueba la CONSTRUCCIÓN de las
consultas y el manejo del resultado, con dobles. Ejecutarlas contra la base es
manual, con `python main.py check-relaciones`, y su salida real va a
`progress/impl_F-006.md`.
"""

from __future__ import annotations

import pathlib
from functools import lru_cache

import pytest

from tests._texto import contiene

from etl_sigrid.domain.diccionario import Columna, Diccionario, Ficha, Relacion
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from etl_sigrid.infrastructure.postgres.relaciones_sql import (
    TAMANO_MUESTRA,
    UMBRAL_AVISO_COBERTURA,
    ConsultaRelacion,
    consultas_de_relaciones,
    interpretar_relacion,
    relaciones_saltadas,
    veredicto_relacion_no_comprobada,
    veredicto_relacion_no_existe,
)

DIR_DICCIONARIO = pathlib.Path(__file__).resolve().parents[1] / "config" / "diccionario"


@lru_cache(maxsize=1)
def _dicc() -> Diccionario:
    return cargar_diccionario(DIR_DICCIONARIO)[0]


def _ficha(**kwargs) -> Ficha:
    base = dict(
        esquema="retenciones",
        objeto="movimientos",
        tipo="tabla",
        capa="consumo",
        consumo_recomendado=True,
        descripcion="D" * 60,
        grano="Una fila por efecto de retencion, que es su clave.",
        clave_negocio=("sentido", "movimiento_id"),
        paso_etl="build_retenciones",
        refresco="nocturno",
        columnas=(
            Columna(nombre="sentido", significado="S" * 40),
            Columna(nombre="movimiento_id", significado="S" * 40),
            Columna(nombre="obra_id", significado="S" * 40),
        ),
        relaciones=(),
        ejemplos_preguntas=("Que retenciones tengo de la obra X",),
    )
    base.update(kwargs)
    return Ficha(**base)


def _destino(**kwargs) -> Ficha:
    base = dict(
        esquema="maestro",
        objeto="obras",
        tipo="vista",
        clave_negocio=("obra_id",),
        grano="Una fila por obra, que es su clave.",
        columnas=(Columna(nombre="obra_id", significado="S" * 40),),
    )
    base.update(kwargs)
    return _ficha(**base)


def _relacion(**kwargs) -> Relacion:
    base = dict(
        de="obra_id",
        a="maestro.obras.obra_id",
        cardinalidad="N:1",
        porque="P" * 40,
    )
    base.update(kwargs)
    return Relacion(**base)


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


def _par(**kwargs) -> Diccionario:
    """El caso normal: una ficha con UNA relación y su destino fichado."""
    return _diccionario_con(_ficha(relaciones=(_relacion(**kwargs),)), _destino())


# ---------------------------------------------------------------------------
# La consulta que se genera
# ---------------------------------------------------------------------------


def test_f006_t40_la_consulta_ejecuta_el_join_de_la_relacion_declarada() -> None:
    """Los dos extremos salen de la relación, no de una lista escrita a mano."""
    (consulta,) = consultas_de_relaciones(_par())

    assert consulta.origen == "retenciones.movimientos"
    assert consulta.de == "obra_id"
    assert consulta.a == "maestro.obras.obra_id"
    assert "FROM retenciones.movimientos" in consulta.sql
    assert "FROM maestro.obras" in consulta.sql
    assert "obra_id" in consulta.sql


def test_f006_t40_la_consulta_muestrea_el_lado_izquierdo_y_lo_dice() -> None:
    """Sin cota, esto barre tablas de 29 millones de filas en un servidor
    compartido con dos aplicaciones EN PRODUCCIÓN."""
    (consulta,) = consultas_de_relaciones(_par())

    assert f"LIMIT {TAMANO_MUESTRA}" in consulta.sql
    assert consulta.muestra == TAMANO_MUESTRA


def test_f006_t40_los_nulos_quedan_fuera_de_la_muestra() -> None:
    """Un NULO no casa con nada por definición: contarlo como fallo del JOIN
    convertiría toda relación opcional en un falso positivo."""
    (consulta,) = consultas_de_relaciones(_par())

    assert "IS NOT NULL" in consulta.sql


def test_f006_t40_la_consulta_de_detalle_devuelve_valores_que_no_casan() -> None:
    """«0 de 261» no se arregla solo; «estos 20 valores no casan» sí."""
    (consulta,) = consultas_de_relaciones(_par())

    assert "NOT EXISTS" in consulta.sql_detalle
    assert "LIMIT" in consulta.sql_detalle


def test_f006_t40_un_identificador_raro_no_se_interpola() -> None:
    """Todo esto sale de un YAML editable a mano y acaba dentro de un SELECT."""
    malicioso = _par(de="obra_id; DROP TABLE mart.x --")
    with pytest.raises(ValueError, match="no interpolable"):
        consultas_de_relaciones(malicioso)


def test_f006_t40_la_columna_del_destino_tampoco_se_interpola() -> None:
    """El destino se parte en tres y los tres trozos se validan, no solo el
    origen: el defecto sobrevive en el campo de al lado.

    La columna es el trozo que de verdad llega libre hasta el `SELECT`: el
    esquema y el objeto tienen que resolver contra una ficha para que la
    relación se comprueba siquiera, y las fichas ya pasan por los vocabularios
    cerrados del dominio. La columna no.
    """
    malicioso = _par(a="maestro.obras.obra_id; DROP TABLE x --")
    with pytest.raises(ValueError, match="no interpolable"):
        consultas_de_relaciones(malicioso)


def test_f006_t40_un_destino_sin_ficha_se_salta_diciendolo() -> None:
    """No revienta el barrido ni lo aprueba: lo declara. El validador del
    dominio ya denuncia ese destino como R5."""
    dicc = _diccionario_con(
        _ficha(relaciones=(_relacion(a="compras.inventada.obra_id"),))
    )

    assert consultas_de_relaciones(dicc) == []
    motivos = dict(relaciones_saltadas(dicc))
    assert "no tiene ficha" in motivos["retenciones.movimientos.obra_id"]


# ---------------------------------------------------------------------------
# Qué se salta, y por qué
# ---------------------------------------------------------------------------


def test_f006_t40_se_saltan_las_relaciones_hacia_una_funcion() -> None:
    """Una función no tiene filas contra las que unir."""
    dicc = _diccionario_con(
        _ficha(relaciones=(_relacion(a="maestro.fn_fecha.obra_id"),)),
        _destino(objeto="fn_fecha", tipo="funcion", grano=None, clave_negocio=()),
    )

    assert consultas_de_relaciones(dicc) == []
    motivos = dict(relaciones_saltadas(dicc))
    assert "funcion" in motivos["retenciones.movimientos.obra_id"]


def test_f006_t40_se_salta_lo_que_todavia_no_tiene_ficha() -> None:
    """Un destino en `pendientes` no se puede comprobar: aún no está descrito.
    Se salta DICIÉNDOLO, nunca en silencio."""
    dicc = Diccionario(
        version="1",
        base="sigrid_dm",
        fichas=(_ficha(relaciones=(_relacion(a="compras.futura.obra_id"),)),),
        reglas=(),
        esquemas={},
        pendientes=("compras.futura",),
        global_raw={},
    )

    assert consultas_de_relaciones(dicc) == []
    motivos = dict(relaciones_saltadas(dicc))
    assert "pendientes" in motivos["retenciones.movimientos.obra_id"]


def test_f006_t40_el_alcance_por_defecto_es_la_superficie_de_consumo() -> None:
    interna = _ficha(
        esquema="stg",
        objeto="plan_mensual",
        consumo_recomendado=False,
        motivo_no_consumo="M" * 40,
        relaciones=(_relacion(),),
    )
    dicc = _diccionario_con(_ficha(relaciones=(_relacion(),)), interna, _destino())

    assert [c.origen for c in consultas_de_relaciones(dicc)] == [
        "retenciones.movimientos"
    ]
    assert len(consultas_de_relaciones(dicc, solo_consumo=False)) == 2
    motivos = dict(relaciones_saltadas(dicc))
    assert "--todos" in motivos["stg.plan_mensual.obra_id"]


def test_f006_t40_sobre_el_diccionario_real_alcanza_a_todas_las_relaciones() -> None:
    """Control de que esto no corre sobre una lista vacía.

    El diccionario real declara del orden de un centenar de relaciones. Si el
    barrido cayera a un puñado, el verde no significaría nada.
    """
    todas = consultas_de_relaciones(_dicc(), solo_consumo=False)
    saltadas = relaciones_saltadas(_dicc(), solo_consumo=False)
    declaradas = sum(len(f.relaciones) for f in _dicc().fichas)

    assert len(todas) + len(saltadas) == declaradas
    assert len(todas) >= 60


def test_f006_t40_ninguna_relacion_real_queda_sin_comprobar_ni_sin_motivo() -> None:
    """Toda relación o se comprueba, o aparece en la lista de saltadas con su
    motivo. Un hueco mudo es lo que permitió que la relación falsa viviera
    diecisiete pasadas."""
    comprobadas = {
        f"{c.origen}.{c.de}" for c in consultas_de_relaciones(_dicc(), solo_consumo=False)
    }
    saltadas = dict(relaciones_saltadas(_dicc(), solo_consumo=False))

    for ficha in _dicc().fichas:
        for relacion in ficha.relaciones:
            clave = f"{ficha.nombre}.{relacion.de}"
            assert clave in comprobadas or clave in saltadas, (
                f"{clave} no se comprueba y tampoco declara por qué se salta"
            )
            if clave in saltadas:
                assert saltadas[clave].strip(), f"{clave} se salta sin motivo escrito"


# ---------------------------------------------------------------------------
# Cómo se lee el resultado
# ---------------------------------------------------------------------------


def test_f006_t40_cero_casos_es_el_fallo_que_esta_puerta_existe_para_cazar() -> None:
    (consulta,) = consultas_de_relaciones(_par())

    veredicto = interpretar_relacion(consulta, muestreados=261, casan=0)

    assert veredicto.startswith("KO")
    assert veredicto.endswith(consulta.sql_detalle)
    assert "0 de 261" in veredicto
    assert "cero filas" in veredicto
    assert consulta.a in veredicto


def test_f006_t40_una_cobertura_parcial_avisa_pero_no_es_un_fallo() -> None:
    """Una relación que casa 251 de 261 es cierta y tiene huecos; una que casa 3
    de 261 es cierta sobre el papel e inútil en la práctica. Ni una ni otra son
    el fallo que esta puerta corta, así que avisan."""
    (consulta,) = consultas_de_relaciones(_par())

    parcial = interpretar_relacion(consulta, muestreados=261, casan=251)
    escasa = interpretar_relacion(consulta, muestreados=261, casan=3)

    assert parcial.startswith("OK")
    assert "251 de 261" in parcial
    assert escasa.startswith("AVISO")
    assert f"{int(UMBRAL_AVISO_COBERTURA * 100)}" in escasa


def test_f006_t40_una_muestra_vacia_no_se_cuenta_como_correcta() -> None:
    """Cero valores muestreados significa que la columna está entera a NULO o el
    objeto vacío. No hay JOIN que comprobar, y decir OK sería aprobar sin
    mirar."""
    (consulta,) = consultas_de_relaciones(_par())

    veredicto = interpretar_relacion(consulta, muestreados=0, casan=0)

    assert not veredicto.startswith("OK")
    assert "sin valores" in veredicto


def test_f006_t40_un_verde_no_dice_que_la_relacion_sea_correcta() -> None:
    """Misma frase y mismo motivo que en la comprobación de unicidad: los datos
    de hoy no la contradicen, que es otra cosa."""
    (consulta,) = consultas_de_relaciones(_par())

    assert "no la contradicen" in interpretar_relacion(
        consulta, muestreados=261, casan=261
    )


def test_f006_t40_un_timeout_nunca_se_cuenta_como_correcto() -> None:
    (consulta,) = consultas_de_relaciones(_par())

    veredicto = veredicto_relacion_no_comprobada(consulta, "timeout de 30s")

    assert not veredicto.startswith("OK")
    assert "NO COMPROBADA" in veredicto
    assert "timeout de 30s" in veredicto


def test_f006_t40_un_objeto_fichado_que_no_existe_es_un_hallazgo_no_un_ok() -> None:
    (consulta,) = consultas_de_relaciones(_par())

    veredicto = veredicto_relacion_no_existe(consulta)

    assert not veredicto.startswith("OK")
    assert "NO EXISTE" in veredicto


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
        if self.revienta is not None and "SELECT" in sql and "SET LOCAL" not in sql:
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
    def __init__(self, conexion):
        self._conexion = conexion

    def connection(self):
        return self._conexion


def _comprobar(cliente, consulta, timeout=30):
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    return PostgresClient.comprobar_relacion(cliente, consulta, timeout)


def test_f006_t40_el_cliente_acota_el_tiempo_y_no_escribe() -> None:
    """Mismas dos sentencias previas que la comprobación de unicidad, y por el
    mismo motivo: esto corre contra un servidor compartido con `albaranes` y
    `partes` en producción."""
    cursor = _CursorFalso(fila=(261, 0))
    conexion = _ConexionFalsa(cursor)
    (consulta,) = consultas_de_relaciones(_par())

    assert _comprobar(_ClienteFalso(conexion), consulta, timeout=45) == (261, 0)

    assert cursor.ejecutadas[0] == "SET LOCAL statement_timeout = '45s'"
    assert cursor.ejecutadas[1] == "SET LOCAL transaction_read_only = on"
    assert conexion.commits == 1 and conexion.rollbacks == 0


def test_f006_t40_un_timeout_del_motor_devuelve_none_y_hace_rollback() -> None:
    import psycopg

    cursor = _CursorFalso(fila=None, revienta=psycopg.errors.QueryCanceled("timeout"))
    conexion = _ConexionFalsa(cursor)
    (consulta,) = consultas_de_relaciones(_par())

    assert _comprobar(_ClienteFalso(conexion), consulta) is None
    assert conexion.rollbacks == 1 and conexion.commits == 0


def test_f006_t40_un_objeto_que_no_existe_se_distingue_del_timeout() -> None:
    """«No he podido comprobarlo» y «eso no está en la base» exigen cosas
    distintas de quien lo lea."""
    import psycopg

    cursor = _CursorFalso(
        fila=None, revienta=psycopg.errors.UndefinedTable("no existe")
    )
    conexion = _ConexionFalsa(cursor)
    (consulta,) = consultas_de_relaciones(_par())

    assert _comprobar(_ClienteFalso(conexion), consulta) == "NO_EXISTE"
    assert conexion.rollbacks == 1 and conexion.commits == 0


def test_f006_t40_una_columna_que_no_existe_tambien_es_un_hallazgo() -> None:
    """El caso que de verdad aparece cuando la base va por detrás del árbol: el
    objeto está, la columna no. Sin esto reventaría el barrido entero por una
    sola relación."""
    import psycopg

    cursor = _CursorFalso(
        fila=None, revienta=psycopg.errors.UndefinedColumn("no existe")
    )
    conexion = _ConexionFalsa(cursor)
    (consulta,) = consultas_de_relaciones(_par())

    assert _comprobar(_ClienteFalso(conexion), consulta) == "NO_EXISTE"


def test_f006_t40_la_consulta_es_un_objeto_con_lo_necesario_para_entenderla() -> None:
    """Control de forma: quien lee un KO tiene que poder arreglarlo sin volver a
    investigar de dónde salió la relación."""
    (consulta,) = consultas_de_relaciones(_par())

    assert isinstance(consulta, ConsultaRelacion)
    assert consulta.cardinalidad == "N:1"
    assert consulta.porque


# ---------------------------------------------------------------------------
# La premisa de la que cuelga la deteccion de fan-out (F-042, R20)
# ---------------------------------------------------------------------------
#
# `_validar_cardinalidad` deriva la unicidad de un extremo de su `clave_negocio`
# DECLARADA. Es una derivacion buena —seis relaciones publicadas como `N:1`
# sobre `obra_id` cayeron por ella— pero se apoya en una premisa que el texto no
# puede sostener: **que la clave declarada sea cierta en los datos**.
#
# No es una objecion teorica. Durante ocho dias el detector dio por unica a
# `mart.fact_seguimiento_mensual` por (obra_id, partida_id, anio_mes, escenario)
# mientras esa combinacion se repetia en 8.778 casos: la declaracion era falsa,
# 22 obras tenian dos fases en el mismo mes y el detector no tenia forma de
# saberlo. F-042 arreglo el dato; lo que sigue aqui es que **la premisa se
# verifique**, no que se de por buena.
#
# Lo verificable sin conexion es esto: todo objeto del que se derive un lado `1`
# tiene que estar dentro del alcance de `check-unicidad`. Si no lo esta, esta
# validacion cuelga de una afirmacion que nadie contrasta nunca contra la base.


def _objetos_de_los_que_se_deriva_unicidad() -> set[str]:
    """Los extremos cuya `clave_negocio` sostiene un lado `1` de una relacion.

    Se derivan del diccionario real, sin lista a mano: una relacion nueva entra
    sola y una que cambie de cardinalidad sale sola.
    """
    dicc = _dicc()
    objetos: set[str] = set()
    for ficha in dicc.fichas:
        for relacion in ficha.relaciones:
            if not relacion.cardinalidad or ":" not in relacion.cardinalidad:
                continue
            izquierda, derecha = relacion.cardinalidad.split(":")
            destino = relacion.a.split(".")[0] + "." + relacion.a.split(".")[1]
            if izquierda == "1":
                objetos.add(ficha.nombre)
            if derecha == "1" and destino in dicc.por_nombre:
                objetos.add(destino)
    return objetos


def test_f006_r20_control_hay_lados_uno_de_los_que_se_deriva_unicidad() -> None:
    """Si el derivador se quedara vacio, el test de abajo pasaria sin mirar."""
    objetos = _objetos_de_los_que_se_deriva_unicidad()
    assert len(objetos) >= 3, f"solo {sorted(objetos)}: la derivacion se ha quedado corta"


def test_f006_r20_la_unicidad_que_sostiene_el_fan_out_se_comprueba_contra_la_base() -> None:
    """La premisa de la deteccion de fan-out no puede quedar sin verificar.

    Un objeto del que se deriva un lado `1` y que `check-unicidad` no llega a
    comprobar deja la validacion de cardinalidad apoyada en una declaracion que
    nadie contrasta. Es exactamente la situacion en la que estuvo
    `mart.fact_seguimiento_mensual` hasta que la comprobacion se ejecuto por
    primera vez y devolvio 8.778.

    Se admite `--todos`: lo que no se admite es que el objeto quede fuera de
    cualquier pasada, ni siquiera de la completa.
    """
    from etl_sigrid.infrastructure.postgres.unicidad_sql import (
        consultas_de_unicidad,
        objetos_saltados,
    )

    dicc = _dicc()
    comprobables = {c.objeto for c in consultas_de_unicidad(dicc, solo_consumo=False)}
    # Los que se saltan POR MOTIVO estructural —la clave la garantiza el motor,
    # o no declaran clave— no son un hueco: son objetos sobre los que esta
    # derivacion tampoco afirma nada.
    con_motivo = {
        nombre
        for nombre, motivo in objetos_saltados(dicc, solo_consumo=False)
        if contiene(motivo, "PRIMARY KEY") or contiene(motivo, "clave sustituta")
    }

    sin_verificar = sorted(
        _objetos_de_los_que_se_deriva_unicidad() - comprobables - con_motivo
    )
    assert sin_verificar == [], (
        f"{sin_verificar} sostienen un lado `1` de alguna relacion y "
        f"`check-unicidad` no los comprueba ni con `--todos`. La deteccion de "
        f"fan-out quedaria apoyada en una clave declarada que nadie contrasta "
        f"contra la base, que es como se publicaron 8.778 duplicados durante "
        f"ocho dias"
    )


def test_f006_r20_el_detector_declara_de_que_premisa_cuelga() -> None:
    """Y lo dice donde lo va a leer quien lo mantenga, no en un informe.

    Un detector que no declara su limite invita a tratarlo como suficiente. Este
    es necesario y no suficiente: su complemento es `check-unicidad`.
    """
    from etl_sigrid.domain import diccionario as modulo

    documentacion = modulo._validar_cardinalidad.__doc__ or ""

    assert "check-unicidad" in documentacion, (
        "`_validar_cardinalidad` no nombra la comprobacion que verifica su "
        "premisa: quien lo mantenga lo tratara como suficiente"
    )
    assert "8.778" in documentacion, (
        "el limite se declara sin el caso que lo demostro, y una advertencia sin "
        "evidencia se borra en la siguiente limpieza"
    )
