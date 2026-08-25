# etl_sigrid/infrastructure/postgres/relaciones_sql.py
"""
Genera la comprobación de que cada relación declarada UNE de verdad (F-006, T40).

El incidente que la trajo. La batería de aceptación cruzó retenciones con obras
y no salió nada. La ficha declaraba
`retenciones.movimientos.obra_id -> maestro.obras.obra_id (N:1)` y esa relación
casa **0 de 261** valores: en `retenciones`, `obra_id` es el `ide` del CENTRO DE
COSTE de la obra, una entidad distinta y **contigua** a la de la obra (0655 es
1990274 como centro de coste y 1990273 como obra). Un `INNER JOIN` por ahí
devuelve cero filas y un `LEFT JOIN` devuelve todo a NULL, **en silencio y sin
error**: ni el motor protesta ni el agente sospecha.

Por qué no lo cazaba nada. El validador del dominio comprueba lo que es
derivable del TEXTO: que el destino tenga ficha, que la columna esté
documentada, que la cardinalidad no prometa una unicidad que la clave de negocio
no respalda. Todo correcto en esa relación. Lo que no está en el texto es **si
los valores de un lado aparecen en el otro**; eso está en los datos, y ahí solo
se llega ejecutando el JOIN.

La consulta, por relación:

    WITH muestra AS (
        SELECT DISTINCT <de> AS valor FROM <origen>
        WHERE <de> IS NOT NULL LIMIT 500
    )
    SELECT count(*),
           count(*) FILTER (WHERE EXISTS (
               SELECT 1 FROM <destino> d WHERE d.<columna> = m.valor))
    FROM muestra m

Tres decisiones con motivo:

* **Se muestrea el lado izquierdo.** Sin cota esto barre `stg.plan_mensual`, que
  ronda los 29 millones de filas, contra `psql-albaranes-rs9k2`, **compartido
  con `albaranes` y `partes` EN PRODUCCIÓN**. Quinientos valores distintos
  bastan de sobra para distinguir «une» de «no une nada».
* **Los NULOS quedan fuera.** Un NULO no casa con nada por definición; contarlo
  como fallo convertiría toda relación opcional en un falso positivo.
* **`EXISTS` y no un `JOIN`.** No hay que contar coincidencias sino saber si el
  valor existe al otro lado, y así una relación N:N no infla el recuento.

Qué corta y qué solo avisa. **Cero casos es KO**: es el defecto que esta puerta
existe para cazar. Una cobertura parcial es un AVISO, porque un hueco puede ser
legítimo —`cierre` solo cubre 583 de las 918 obras— y no es lo mismo que una
relación que miente entera.

Este módulo **no abre ninguna conexión**: solo construye el texto. Ejecutarlo es
`python main.py check-relaciones`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from dataclasses import dataclass

from etl_sigrid.domain.diccionario import Diccionario, Ficha, Relacion

#: Un identificador que se puede interpolar sin miedo. Mismo criterio y mismo
#: motivo que en `unicidad_sql`: todo esto sale de un YAML editable a mano y
#: acaba dentro de un `SELECT`. `_meta` empieza por guion bajo, así que entra.
_IDENTIFICADOR = re.compile(r"^[a-z_][a-z0-9_]*$")

#: Cuántos valores DISTINTOS del lado izquierdo se muestrean.
#:
#: No es una consulta completa a propósito: el objetivo es distinguir «une» de
#: «no une nada», y para eso quinientos valores sobran. Lo que se compra con la
#: cota es no barrer tablas de decenas de millones de filas en un servidor que
#: comparten dos aplicaciones en producción.
TAMANO_MUESTRA = 500

#: Por debajo de esta fracción de valores que casan, la relación AVISA.
#:
#: No es un fallo: `cierre.v_pbi_cierre_cabecera` solo cubre 583 de las 918
#: obras, así que una relación hacia ella casa de forma legítima menos del 100 %.
#: Pero una que casa el 3 % es cierta sobre el papel e inútil en la práctica, y
#: quien la lea merece saberlo antes de escribir el JOIN.
UMBRAL_AVISO_COBERTURA = 0.5


@dataclass(frozen=True, slots=True)
class ConsultaRelacion:
    """Una relación lista para comprobar, con lo que hace falta para entender su
    resultado sin volver a investigar de dónde salió."""

    origen: str
    de: str
    a: str
    cardinalidad: str
    #: El `porque` de la ficha. Va aquí porque es lo que hay que reescribir
    #: cuando la comprobación sale en rojo: el JOIN no se arregla, se retira o
    #: se cuenta bien.
    porque: str
    muestra: int
    sql: str
    sql_detalle: str

    @property
    def nombre(self) -> str:
        return f"{self.origen}.{self.de}"


def _valida(nombre: str) -> str:
    if not _IDENTIFICADOR.match(nombre):
        raise ValueError(
            f"identificador no interpolable en SQL: {nombre!r}. Sale del "
            f"diccionario, que es un YAML editable a mano"
        )
    return nombre


def _motivo_para_saltar(
    ficha: Ficha,
    relacion: Relacion,
    indice: dict[str, Ficha],
    pendientes: Sequence[str],
    *,
    solo_consumo: bool,
) -> str | None:
    """Por qué NO se comprueba esta relación, o `None` si sí se comprueba.

    Un chequeo que dice «todo correcto» sin decir sobre qué corrió invita a
    creer que cubrió más de lo que cubrió. Ya pasó dos veces en esta feature.
    """
    if ficha.tipo == "funcion":
        return f"`{ficha.nombre}` es una funcion: no tiene filas que unir"

    partes = relacion.a.split(".")
    if len(partes) != 3:
        # El validador del dominio ya lo denuncia como R5; aquí solo evita
        # reventar el barrido entero por una relación mal escrita.
        return f"el destino `{relacion.a}` no tiene la forma `esquema.objeto.columna`"

    destino_nombre = f"{partes[0]}.{partes[1]}"
    destino = indice.get(destino_nombre)
    if destino is None:
        if destino_nombre in pendientes:
            return (
                f"`{destino_nombre}` esta en `pendientes`: todavia no tiene ficha "
                f"que comprobar"
            )
        return f"`{destino_nombre}` no tiene ficha en el diccionario"
    if destino.tipo == "funcion":
        return f"`{destino_nombre}` es una funcion: no tiene filas que unir"

    if solo_consumo and not ficha.consumo_recomendado:
        return "fuera de la superficie de consumo (usa `--todos`)"
    return None


def consultas_de_relaciones(
    dicc: Diccionario, *, solo_consumo: bool = True
) -> list[ConsultaRelacion]:
    """Una consulta por relación declarada que convenga comprobar.

    Se DERIVAN del diccionario: no hay lista escrita a mano, así que una
    relación nueva entra sola y una que cambie de destino se comprueba con el
    nuevo. Es la misma decisión que ya salvó a la comprobación de unicidad de
    envejecer.

    `solo_consumo=True` por defecto, por daño y por coste: una relación falsa en
    la superficie de consumo produce un JOIN vacío en una respuesta de negocio,
    mientras que fuera de ella el objeto no debería consultarse. Y el lado
    izquierdo de las relaciones internas incluye `stg.plan_mensual`.
    """
    indice = dicc.por_nombre
    consultas: list[ConsultaRelacion] = []

    for ficha in sorted(dicc.fichas, key=lambda f: f.nombre):
        for relacion in ficha.relaciones:
            if _motivo_para_saltar(
                ficha, relacion, indice, dicc.pendientes, solo_consumo=solo_consumo
            ) is not None:
                continue

            esquema = _valida(ficha.esquema)
            objeto = _valida(ficha.objeto)
            de = _valida(relacion.de)
            d_esquema, d_objeto, d_columna = relacion.a.split(".")
            d_esquema = _valida(d_esquema)
            d_objeto = _valida(d_objeto)
            d_columna = _valida(d_columna)

            muestra = (
                "WITH muestra AS (\n"
                f"    SELECT DISTINCT {de} AS valor\n"
                f"    FROM {esquema}.{objeto}\n"
                f"    WHERE {de} IS NOT NULL\n"
                f"    LIMIT {TAMANO_MUESTRA}\n"
                ")\n"
            )
            existe = (
                f"SELECT 1 FROM {d_esquema}.{d_objeto} d\n"
                f"        WHERE d.{d_columna} = m.valor"
            )

            consultas.append(
                ConsultaRelacion(
                    origen=ficha.nombre,
                    de=de,
                    a=relacion.a,
                    cardinalidad=relacion.cardinalidad,
                    porque=relacion.porque,
                    muestra=TAMANO_MUESTRA,
                    sql=(
                        muestra + "SELECT count(*) AS valores_muestreados,\n"
                        "       count(*) FILTER (\n"
                        f"           WHERE EXISTS ({existe})\n"
                        "       ) AS valores_que_casan\n"
                        "FROM muestra m"
                    ),
                    sql_detalle=(
                        muestra + "SELECT m.valor\n"
                        "FROM muestra m\n"
                        f"WHERE NOT EXISTS ({existe})\n"
                        "ORDER BY 1\n"
                        "LIMIT 20"
                    ),
                )
            )
    return consultas


def relaciones_saltadas(
    dicc: Diccionario, *, solo_consumo: bool = True
) -> list[tuple[str, str]]:
    """Qué relación se salta y POR QUÉ, una entrada por relación.

    Junto con `consultas_de_relaciones` tiene que cubrir TODAS las relaciones
    declaradas: un hueco mudo en el barrido es exactamente lo que permitió que
    la relación falsa de `retenciones` sobreviviera diecisiete pasadas.
    """
    indice = dicc.por_nombre
    saltadas: list[tuple[str, str]] = []
    for ficha in sorted(dicc.fichas, key=lambda f: f.nombre):
        for relacion in ficha.relaciones:
            motivo = _motivo_para_saltar(
                ficha, relacion, indice, dicc.pendientes, solo_consumo=solo_consumo
            )
            if motivo is not None:
                saltadas.append((f"{ficha.nombre}.{relacion.de}", motivo))
    return saltadas


def interpretar_relacion(
    consulta: ConsultaRelacion, muestreados: int, casan: int
) -> str:
    """El veredicto de una relación, escrito para que la corrección sea evidente.

    **Un verde NO demuestra que la relación sea correcta.** Demuestra que los
    valores de hoy no la contradicen: la relación puede unir por la columna
    equivocada y coincidir por casualidad en un dominio pequeño. La frase dice
    «no la contradicen» por el mismo motivo que en la comprobación de unicidad.
    """
    cabecera = f"{consulta.nombre} -> {consulta.a}"

    if muestreados == 0:
        return (
            f"?    {cabecera}: NO COMPROBADA, la muestra sale sin valores. O la "
            f"columna `{consulta.de}` esta entera a NULO o el objeto esta vacio. "
            f"No es un OK: la relacion sigue sin verificar"
        )

    if casan == 0:
        return (
            f"KO   {cabecera}: la relacion NO UNE. {casan} de {muestreados} "
            f"valores de `{consulta.de}` existen en `{consulta.a}`. Un INNER JOIN "
            f"devuelve cero filas y un LEFT JOIN devuelve todo a NULL, en "
            f"silencio y sin error: quien copie esta relacion escribira una "
            f"consulta vacia y se la creera. La relacion hay que retirarla o "
            f"reescribirla hacia la columna que si une. Para ver que valores "
            f"no casan:\n{consulta.sql_detalle}"
        )

    cobertura = casan / muestreados
    if cobertura < UMBRAL_AVISO_COBERTURA:
        return (
            f"AVISO {cabecera}: une, pero poco. {casan} de {muestreados} valores "
            f"casan ({cobertura:.0%}), por debajo del "
            f"{int(UMBRAL_AVISO_COBERTURA * 100)} % desde el que esto avisa. La "
            f"relacion es cierta y practicamente inutil: si el hueco es "
            f"legitimo, la ficha tiene que decirlo en `porque`"
        )

    return (
        f"OK   {cabecera}: {casan} de {muestreados} valores muestreados casan "
        f"({cobertura:.0%}). Los datos de hoy no la contradicen; no prueba que "
        f"la relacion sea correcta, prueba que une"
    )


def veredicto_relacion_no_comprobada(consulta: ConsultaRelacion, motivo: str) -> str:
    """Cuando la consulta no llegó a terminar. **Nunca se cuenta como OK.**

    Contar un `statement_timeout` como correcto convertiría el límite de tiempo
    —que está para no ahogar un servidor compartido— en una forma de aprobar sin
    mirar.
    """
    return (
        f"?    {consulta.nombre} -> {consulta.a}: NO COMPROBADA ({motivo}). No es "
        f"un OK: la relacion sigue sin verificar"
    )


def veredicto_relacion_no_existe(consulta: ConsultaRelacion) -> str:
    """Un extremo de la relación está fichado y no existe en la base.

    No es un fallo del chequeo ni un OK: es el hallazgo. Significa que la base
    va por detrás del repositorio —falta lanzar el build de ese esquema— o que
    la ficha sobra. Lo primero es lo normal en los esquemas de refresco manual.
    """
    return (
        f"!    {consulta.nombre} -> {consulta.a}: NO EXISTE en la base uno de los "
        f"dos extremos, o la columna. La ficha describe algo que el repositorio "
        f"crea y la base no tiene: falta lanzar el build de su esquema, o la "
        f"ficha sobra. No es un OK"
    )
