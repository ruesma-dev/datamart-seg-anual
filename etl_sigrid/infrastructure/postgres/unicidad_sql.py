# etl_sigrid/infrastructure/postgres/unicidad_sql.py
"""
Genera la comprobación de UNICIDAD de la clave de negocio (F-006, T26).

Es la mitad del problema que la puerta offline no puede cubrir. La puerta
comprueba lo derivable del texto —que la clave no nombre columnas fuera del
`GROUP BY`, que case con la PK declarada— pero **no puede saber si la clave es
demasiado CORTA**: eso exige saber si una columna depende funcionalmente de
otra, y eso no está en el SQL, está en los datos.

Y es el hueco que más daño hace, porque **se propaga**: la detección de fan-out
deriva la unicidad de la clave declarada, así que una clave reducida no solo
miente sobre el grano, además **desarma la comprobación de cardinalidades**. Hoy
eso solo lo cazan una persona o la suerte.

Contra la base se resuelve entero:

    SELECT count(*) AS claves_duplicadas, COALESCE(sum(filas), 0) AS filas
    FROM (
        SELECT <clave>, count(*) AS filas FROM <esquema>.<objeto>
        GROUP BY <clave> HAVING count(*) > 1
    ) AS duplicadas

`GROUP BY … HAVING count(*) > 1` y no `count(*) - count(DISTINCT …)` por dos
motivos: agrupa los NULOS como un valor más —que es como se comportan en un
`JOIN`, y el JOIN es lo que le va a salir mal al agente— y devuelve **cuántas**
claves duplican, que es lo accionable.

Este módulo **no abre ninguna conexión**: solo construye el texto. Ejecutarlo
contra la base es T27, y lo hace el humano.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from etl_sigrid.domain.diccionario import Diccionario, Ficha

#: Un identificador que se puede interpolar sin miedo. Todo lo que llega aquí
#: sale del diccionario, que es nuestro, pero el diccionario es un YAML editable
#: a mano y esto acaba dentro de un `SELECT`: se valida igual. `_meta` empieza
#: por guion bajo, así que el patrón lo admite.
_IDENTIFICADOR = re.compile(r"^[a-z_][a-z0-9_]*$")

#: Esquemas cuyas tablas tienen la clave garantizada POR EL MOTOR.
#:
#: `raw` se ingiere con `pg.ensure_raw_table(tabla, cols, primary_key=id_column)`
#: (`ingest_raw_step.py`), así que `ide` es PRIMARY KEY en las 31. Comprobar su
#: unicidad es pagar un escaneo completo por algo que Postgres ya impide, y
#: varias de esas tablas son de las más grandes del datamart.
ESQUEMAS_CON_CLAVE_GARANTIZADA = ("raw",)

#: Segundos por consulta, como `SET LOCAL statement_timeout`: acotado a la
#: transacción, sin tocar la configuración del servidor.
#:
#: Existe porque esto corre contra `psql-albaranes-rs9k2`, **compartido con
#: `albaranes` y `partes` en producción**. Una consulta correcta que deje el
#: servidor sin CPU no es aceptable. Si el tiempo salta, el objeto se reporta
#: **NO COMPROBADO**, nunca como correcto.
TIMEOUT_POR_CONSULTA_S = 30


@dataclass(frozen=True, slots=True)
class ConsultaUnicidad:
    """Una comprobación lista para ejecutar, con lo que hace falta para entender
    su resultado sin volver a investigar."""

    objeto: str
    clave: tuple[str, ...]
    sql: str
    #: La misma pregunta devolviendo las claves que colisionan, para pegarla en
    #: un cliente cuando la primera diga que las hay. Es la diferencia entre
    #: «hay 12 duplicados» y «estos son».
    sql_detalle: str


def _valida(nombre: str) -> str:
    if not _IDENTIFICADOR.match(nombre):
        raise ValueError(
            f"identificador no interpolable en SQL: {nombre!r}. Sale del "
            f"diccionario, que es un YAML editable a mano"
        )
    return nombre


def _clave_garantizada_por_el_motor(ficha: Ficha) -> str | None:
    """Por qué NO hace falta comprobar esta ficha, o `None` si sí hace falta."""
    if ficha.esquema in ESQUEMAS_CON_CLAVE_GARANTIZADA:
        return (
            f"`{ficha.esquema}` se ingiere con `ide` como PRIMARY KEY: la "
            f"unicidad la impone el motor"
        )
    if len(ficha.clave_negocio) == 1:
        columna = next(
            (c for c in ficha.columnas if c.nombre == ficha.clave_negocio[0]), None
        )
        if columna is not None and columna.agregacion == "clave_sustituta":
            return (
                f"`{ficha.clave_negocio[0]}` es una clave sustituta (BIGSERIAL o "
                f"PK): unica por construccion"
            )
    return None


def consultas_de_unicidad(
    dicc: Diccionario, *, solo_consumo: bool = True
) -> list[ConsultaUnicidad]:
    """Una consulta por objeto cuya clave declarada convenga comprobar.

    Se DERIVAN del diccionario: no hay lista de objetos escrita a mano, así que
    una ficha nueva entra sola y una que cambie de clave se comprueba con la
    nueva. Es la misma decisión que ya salvó al trinquete y a la regla de oro de
    envejecer.

    `solo_consumo=True` por defecto, y la razón es de daño y de coste:

    * **Daño**: una clave corta en la superficie de consumo produce un número
      falso en una respuesta. Fuera de ella el objeto no debería consultarse
      —su propia ficha dice a dónde ir—, así que el mismo defecto no llega al
      usuario por esa vía.
    * **Coste**: `stg.plan_mensual` ronda los **29 millones de filas**, y esto es
      una agregación completa sobre cinco columnas. Contra un servidor
      compartido con dos proyectos en producción, esa consulta se lanza cuando
      alguien ha decidido lanzarla, no por defecto.

    Con `solo_consumo=False` entra todo lo que tenga clave y no esté garantizado
    por el motor: es la pasada completa, para una ventana tranquila.
    """
    consultas: list[ConsultaUnicidad] = []
    for ficha in sorted(dicc.fichas, key=lambda f: f.nombre):
        if ficha.tipo == "funcion" or not ficha.clave_negocio:
            continue
        if solo_consumo and not ficha.consumo_recomendado:
            continue
        if _clave_garantizada_por_el_motor(ficha) is not None:
            continue

        esquema = _valida(ficha.esquema)
        objeto = _valida(ficha.objeto)
        clave = tuple(_valida(c) for c in ficha.clave_negocio)
        columnas = ", ".join(clave)

        consultas.append(
            ConsultaUnicidad(
                objeto=ficha.nombre,
                clave=clave,
                sql=(
                    "SELECT count(*) AS claves_duplicadas,\n"
                    "       COALESCE(sum(filas), 0) AS filas_implicadas\n"
                    "FROM (\n"
                    f"    SELECT {columnas}, count(*) AS filas\n"
                    f"    FROM {esquema}.{objeto}\n"
                    f"    GROUP BY {columnas}\n"
                    "    HAVING count(*) > 1\n"
                    ") AS duplicadas"
                ),
                sql_detalle=(
                    f"SELECT {columnas}, count(*) AS filas\n"
                    f"FROM {esquema}.{objeto}\n"
                    f"GROUP BY {columnas}\n"
                    "HAVING count(*) > 1\n"
                    "ORDER BY filas DESC\n"
                    "LIMIT 20"
                ),
            )
        )
    return consultas


def objetos_saltados(
    dicc: Diccionario, *, solo_consumo: bool = True
) -> list[tuple[str, str]]:
    """Qué se salta y POR QUÉ, para que el informe no tenga huecos mudos.

    Un chequeo que dice «todo correcto» sin decir sobre qué corrió invita a
    creer que cubrió más de lo que cubrió. Ya pasó dos veces en esta feature con
    detectores que se saltaban fichas dando un motivo que no era el real.
    """
    saltados: list[tuple[str, str]] = []
    for ficha in sorted(dicc.fichas, key=lambda f: f.nombre):
        if ficha.tipo == "funcion":
            saltados.append((ficha.nombre, "es una funcion: no tiene filas"))
        elif not ficha.clave_negocio:
            saltados.append((ficha.nombre, "no declara clave de negocio"))
        elif (motivo := _clave_garantizada_por_el_motor(ficha)) is not None:
            saltados.append((ficha.nombre, motivo))
        elif solo_consumo and not ficha.consumo_recomendado:
            saltados.append(
                (ficha.nombre, "fuera de la superficie de consumo (usa `--todos`)")
            )
    return saltados


def sentencias_previas(timeout_s: int = TIMEOUT_POR_CONSULTA_S) -> Sequence[str]:
    """Lo que se emite ANTES de la consulta, y que el cliente emite de verdad.

    Las dos van con `SET LOCAL`, o sea acotadas a la transacción en curso: no
    cambian la configuración del servidor ni afectan a `albaranes` ni a
    `partes`, que lo comparten.

    * `statement_timeout` corta una consulta que se alargue. Si salta, el objeto
      se reporta **NO COMPROBADO**, nunca como correcto.
    * `transaction_read_only` hace que el motor **rechace** cualquier escritura.
      Es la misma garantía que `BEGIN READ ONLY` pero aplicable a una
      transacción **ya abierta**, que es el caso: `PostgresClient.connection()`
      devuelve la conexión en estado `INTRANS`.

    **Esta función existía antes devolviendo `BEGIN READ ONLY … COMMIT` y no la
    llamaba nadie**: el cliente emitía solo el `statement_timeout` mientras el
    comando imprimía por pantalla «transaccion READ ONLY». Un constructor
    muerto, con su test en verde, sosteniendo una garantía falsa que además iba
    impresa. Ahora la emite el cliente, así que el test comprueba lo que ocurre.
    """
    return (
        f"SET LOCAL statement_timeout = '{int(timeout_s)}s'",
        "SET LOCAL transaction_read_only = on",
    )


def interpretar_resultado(
    consulta: ConsultaUnicidad, claves_duplicadas: int, filas_implicadas: int
) -> str:
    """El veredicto de un objeto, escrito para que la corrección sea evidente.

    **Un resultado vacío NO demuestra que la clave sea correcta.** Demuestra que
    los datos de HOY no la contradicen. Una clave puede ser insuficiente y no
    haber colisionado todavía: basta con que ninguna obra haya repetido aún esa
    combinación. Por eso el mensaje dice «no la contradicen» y nunca «es
    correcta»: la diferencia es la que separa una comprobación de una garantía.
    """
    clave = ", ".join(consulta.clave)
    if claves_duplicadas == 0:
        return (
            f"OK   {consulta.objeto}: los datos de hoy no contradicen la clave "
            f"({clave}). No prueba que sea correcta; prueba que aun no ha "
            f"colisionado"
        )
    return (
        f"KO   {consulta.objeto}: la clave declarada ({clave}) NO identifica una "
        f"fila. {claves_duplicadas} combinacion(es) se repiten, afectando a "
        f"{filas_implicadas} filas. La ficha miente sobre su grano, y ademas la "
        f"deteccion de fan-out que deriva de esta clave queda desarmada. Para "
        f"ver cuales son:\n{consulta.sql_detalle}"
    )


def veredicto_no_comprobado(consulta: ConsultaUnicidad, motivo: str) -> str:
    """Cuando la consulta no llegó a terminar. **Nunca se cuenta como OK.**

    Un `statement_timeout` que salta significa «no lo sabemos», y contarlo como
    correcto convertiría el límite de tiempo —que está para proteger un servidor
    compartido— en una forma de aprobar sin mirar.
    """
    return (
        f"?    {consulta.objeto}: NO COMPROBADO ({motivo}). No es un OK: la "
        f"clave ({', '.join(consulta.clave)}) sigue sin verificar"
    )


def veredicto_no_existe(consulta: ConsultaUnicidad) -> str:
    """El objeto esta fichado y no existe en la base.

    No es un fallo del chequeo ni un OK: es el hallazgo. Significa que **la base
    va por detras del repositorio** —alguien anadio el objeto al SQL y no se ha
    vuelto a construir ese esquema— o que la ficha sobra. Lo primero es lo
    normal en los cuatro esquemas de refresco manual.
    """
    return (
        f"!    {consulta.objeto}: FICHADO Y NO EXISTE en la base. La ficha "
        f"describe algo que el repositorio crea y la base no tiene: falta "
        f"lanzar el build de su esquema, o la ficha sobra. No es un OK"
    )
