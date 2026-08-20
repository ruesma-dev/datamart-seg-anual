# etl_sigrid/domain/diccionario.py
"""
El diccionario semántico del datamart: entidades y validación (F-006).

Qué es esto. El datamart tiene que **saber explicarse solo**: no basta con que
los datos estén, tienen que venir acompañados de su significado, su grano, sus
claves, sus relaciones, sus trampas y su régimen de refresco. Ese conocimiento
se escribe como YAML en `config/diccionario/`, se valida aquí y un paso del ETL
lo publica dentro de la propia base, en `_meta`. El servidor MCP lo lee por SQL
sin conocer este repositorio.

Por qué vive en el dominio. Todo lo de este módulo son **funciones puras sobre
estructuras de datos**: sin YAML, sin SQL, sin red, sin ficheros (R8). Quien lee
`config/diccionario/*.yaml` es infraestructura; aquí solo llegan entidades ya
construidas. Eso es lo que permite que la puerta de cobertura corra en cada
`bash harness/init.sh` sin un servidor delante, y que la mutación tenga dónde
morder.

El criterio que gobierna la severidad del validador: **una ficha que miente es
peor que una ficha que falta.** Una ficha que falta produce un «no lo sé»; una
ficha que miente produce un número plausible y falso, escrito con aplomo por un
agente que se creyó la descripción. Por eso `validar` es estricto con los
vocabularios y con las relaciones, y por eso devuelve TODOS los errores y no el
primero: con más de ochenta fichas, parar en el primer fallo obliga a ochenta
vueltas.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

# ---------------------------------------------------------------------------
# Vocabularios cerrados
# ---------------------------------------------------------------------------

#: Los NUEVE esquemas del datamart. Los informes de exploración dicen «ocho» y
#: se equivocan: `infra/sql/02_roles.sql` los crea uno a uno y su comentario ya
#: dice «los nueve esquemas». Ojo a la trampa de nombres: el esquema se llama
#: `aux` pero su carpeta de SQL es `sql/auxiliar/`.
ESQUEMAS_DEL_DATAMART = (
    "_meta",
    "aux",
    "cierre",
    "compras",
    "maestro",
    "mart",
    "raw",
    "retenciones",
    "stg",
)

#: Qué es el objeto para PostgreSQL.
TIPOS = ("tabla", "vista", "funcion")

#: Para qué sirve el objeto dentro del datamart. `origen` es la copia literal
#: de Sigrid, `preparacion` la capa intermedia, `consumo` lo que se pregunta y
#: `operacion` la instrumentación del propio ETL (`_meta`).
CAPAS = ("origen", "preparacion", "consumo", "operacion")

#: Régimen de refresco. `nocturno` = lo construye `run-all`; `manual` = lo
#: construye un comando propio y puede estar arbitrariamente desfasado;
#: `estatico` = no se reconstruye.
REFRESCOS = ("nocturno", "manual", "estatico")

#: Vocabulario CERRADO a propósito (R7): es exactamente lo que el MCP traduce a
#: «esta columna no se suma». Una palabra nueva aquí es un cambio de contrato.
AGREGACIONES = (
    "suma",
    "promedio",
    "no_sumable",
    "suma_solo_dentro_del_mes",
    "ultimo_valor",
    "clave_sustituta",
)

#: Vocabulario CERRADO de la cardinalidad de una relacion (R5).
#:
#: Cerrado por un incidente concreto: `cardinalidad: 1:1` escrito SIN COMILLAS
#: lo interpreta YAML como un numero sexagesimal y vale **61**. Ocho relaciones
#: se publicaron asi y no lo vio nadie, porque el campo era `str` y no se
#: contrastaba con nada. Es el mismo remedio que ya tenia `agregacion`.
CARDINALIDADES = ("1:1", "1:N", "N:1", "N:N")

#: Severidad de una regla dura del diccionario.
SEVERIDADES = ("bloqueante", "aviso")

#: Las DOCE reglas duras que `00_global.yaml` tiene que declarar sí o sí (R9).
#:
#: No es una lista de buenas prácticas: cada una nace de una trampa concreta del
#: modelo y varias de un número falso real. Se escriben aquí, en el dominio, para
#: que quitar una del YAML deje `bash harness/init.sh` en rojo en vez de dejar al
#: agente sin esa defensa en silencio.
CODIGOS_REGLAS_OBLIGATORIAS = (
    "R-ABONO-NEGATIVO",
    "R-CLAVE-SUSTITUTA",
    "R-COMPRAS-SIN-IVA",
    "R-COMPRAS-TIPO-DOC",
    "R-FAS-AMBIGUO",
    "R-FRESCURA-MANUAL",
    "R-IMPORTE-MES",
    "R-LINEA-ID-NO-UNICA",
    "R-OBRA-ACTIVA",
    "R-RETENCION-NO-JOIN-LINEAS",
    "R-UNIVERSO-OBRA",
    "R-VERSION-MASTER",
)

#: Claves obligatorias de cada entrada de `esquemas` en `00_global.yaml` (R4).
CLAVES_ESQUEMA = ("titulo", "para_que_sirve", "consumo_recomendado", "refresco")

#: Longitud mínima de cada texto de una ficha, en caracteres.
#:
#: No es burocracia: sin esto, `descripcion: x` y `motivo_no_consumo: x` pasan
#: la puerta. Se comprobó en la review que con fichas así el trinquete de
#: `pendientes` baja de 73 a 42 en verde, sin una línea de conocimiento, y que
#: `motivo_no_consumo: x` abre la puerta trasera que R3 existe para cerrar.
#:
#: Los números salen de lo que ya se exigía en el bloque global desde el
#: principio (`para_que_sirve >= 40`, `regla >= 40`, `motivo >= 30`): esto
#: extiende el mismo criterio a las fichas, que es donde está el volumen.
#: Medir caracteres no garantiza que el texto sea bueno; garantiza que alguien
#: se ha parado a escribirlo, que es todo lo que un test puede comprobar.
MINIMOS_TEXTO = {
    "descripcion": 40,
    "grano": 20,
    "motivo_no_consumo": 30,
    "significado": 15,
    "ejemplo_pregunta": 20,
}


def _corto(campo: str, valor: str | None, para_que: str) -> str | None:
    """Mensaje de error si el texto falta o no llega al mínimo (R2, R3, R6).

    Distingue los dos casos —falta, o está de relleno— porque se arreglan
    distinto y porque decirle a alguien «faltan 7 caracteres» sin más es la
    forma de que rellene con puntos suspensivos.
    """
    texto = (valor or "").strip()
    minimo = MINIMOS_TEXTO[campo]
    if not texto:
        return f"falta `{campo}`: {para_que}"
    if len(texto) < minimo:
        return (
            f"`{campo}` tiene {len(texto)} caracteres y el mínimo son {minimo}: "
            f"{texto!r} no explica {para_que}"
        )
    return None


def _lista(valores: Sequence[str]) -> str:
    """Vocabulario en el mensaje de error, siempre en el mismo orden."""
    return " | ".join(valores)


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Columna:
    """Una columna documentada.

    `significado` es de negocio, no técnico: «Importe imputado A ESE MES
    concreto, ya desacumulado», no «numeric(20,6) not null».
    """

    nombre: str
    significado: str
    unidad: str | None = None
    agregacion: str | None = None
    valores: tuple[str, ...] = ()
    nulo_significa: str | None = None


@dataclass(frozen=True, slots=True)
class Relacion:
    """Un camino de JOIN documentado, con el porqué de negocio.

    `a` se escribe siempre como `esquema.objeto.columna` y tiene que resolver
    contra el propio diccionario (R5). Una relación rota es peor que ninguna:
    el agente escribirá el JOIN igual.
    """

    de: str
    a: str
    cardinalidad: str
    porque: str


@dataclass(frozen=True, slots=True)
class Ficha:
    """Todo lo que hay que saber de un objeto publicado antes de consultarlo."""

    esquema: str
    objeto: str
    tipo: str
    capa: str
    consumo_recomendado: bool
    descripcion: str
    grano: str | None
    clave_negocio: tuple[str, ...]
    paso_etl: str | None
    refresco: str
    columnas: tuple[Columna, ...]
    relaciones: tuple[Relacion, ...]
    ejemplos_preguntas: tuple[str, ...]
    motivo_no_consumo: str | None = None
    #: DERIVADO por `derivar_avisos` (R12). No se escribe a mano en el YAML.
    avisos: tuple[str, ...] = ()

    @property
    def nombre(self) -> str:
        return f"{self.esquema}.{self.objeto}"

    @property
    def fichero(self) -> str:
        """Fichero del que sale la ficha, para poder nombrarlo en el error."""
        return f"{self.esquema}.yaml"


@dataclass(frozen=True, slots=True)
class Regla:
    """Una trampa del modelo, escrita como orden y con su porqué.

    `ambito` admite `esquema` o `esquema.objeto`. `motivo` lleva el incidente
    real cuando lo hubo: la regla que nace de un número falso concreto se
    respeta más que la que nace de una buena intención.
    """

    codigo: str
    titulo: str
    severidad: str
    ambito: tuple[str, ...]
    regla: str
    motivo: str
    orden: int = 0


@dataclass(frozen=True, slots=True)
class Diccionario:
    """El diccionario completo: las fichas, las reglas y el bloque global."""

    version: str
    base: str
    fichas: tuple[Ficha, ...]
    reglas: tuple[Regla, ...]
    esquemas: Mapping[str, Mapping[str, object]]
    pendientes: tuple[str, ...]
    #: Lo que se sirve tal cual: convenciones, ejes, órdenes de magnitud,
    #: `ocultar` y la batería de preguntas de aceptación.
    global_raw: Mapping[str, object]

    @property
    def por_nombre(self) -> dict[str, Ficha]:
        """Índice `esquema.objeto` -> ficha. La primera gana; los duplicados
        los denuncia `validar`."""
        indice: dict[str, Ficha] = {}
        for ficha in self.fichas:
            indice.setdefault(ficha.nombre, ficha)
        return indice


@dataclass(frozen=True, slots=True)
class ErrorValidacion:
    """Un fallo del diccionario, con lo necesario para arreglarlo sin buscar.

    `fichero` y `objeto` no son decoración: quien lee esto tiene que saber qué
    abrir. `regla` es el identificador EARS (`R3`, `R7`...), para poder rastrear
    el fallo hasta el requisito que lo exige.
    """

    fichero: str
    objeto: str | None
    regla: str
    detalle: str

    @property
    def clave_orden(self) -> tuple[str, str, str, str]:
        return (self.fichero, self.objeto or "", self.regla, self.detalle)


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------


def validar(
    dicc: Diccionario, pasos_nocturnos: Sequence[str]
) -> list[ErrorValidacion]:
    """Comprueba el diccionario entero y devuelve TODOS los errores.

    `pasos_nocturnos` se inyecta desde fuera —lo lee `main.build_pipeline_steps`
    real— para que la comprobación de frescura (R14) no dependa de una lista
    copiada a mano que se desincronizará el día que el pipeline cambie.

    La lista sale **ordenada** y por tanto es determinista: el mismo diccionario
    produce siempre el mismo informe, entren las fichas en el orden que entren.
    Un incidente que se repite tiene que producir el mismo texto.
    """
    errores: list[ErrorValidacion] = []

    errores.extend(_validar_esquemas(dicc))
    errores.extend(_validar_duplicados(dicc))

    indice = dicc.por_nombre
    for ficha in dicc.fichas:
        errores.extend(_validar_ficha(ficha, dicc, indice, pasos_nocturnos))

    errores.extend(_validar_reglas(dicc, indice))

    return sorted(errores, key=lambda e: e.clave_orden)


def _validar_esquemas(dicc: Diccionario) -> list[ErrorValidacion]:
    """R4: los NUEVE esquemas tienen entrada propia en `00_global.yaml`."""
    errores: list[ErrorValidacion] = []
    fichero = "00_global.yaml"

    for esquema in ESQUEMAS_DEL_DATAMART:
        entrada = dicc.esquemas.get(esquema)
        if entrada is None:
            errores.append(
                ErrorValidacion(
                    fichero=fichero,
                    objeto=None,
                    regla="R4",
                    detalle=(
                        f"el esquema `{esquema}` no tiene entrada en `esquemas`. "
                        f"El diccionario debe cubrir los nueve: "
                        f"{_lista(ESQUEMAS_DEL_DATAMART)}"
                    ),
                )
            )
            continue
        errores.extend(_validar_entrada_esquema(esquema, entrada, fichero))

    for esquema in sorted(dicc.esquemas):
        if esquema not in ESQUEMAS_DEL_DATAMART:
            errores.append(
                ErrorValidacion(
                    fichero=fichero,
                    objeto=None,
                    regla="R4",
                    detalle=(
                        f"`esquemas` declara `{esquema}`, que no es uno de los nueve "
                        f"esquemas del datamart: {_lista(ESQUEMAS_DEL_DATAMART)}"
                    ),
                )
            )
    return errores


def _validar_entrada_esquema(
    esquema: str, entrada: Mapping[str, object], fichero: str
) -> list[ErrorValidacion]:
    errores: list[ErrorValidacion] = []

    for clave in CLAVES_ESQUEMA:
        valor = entrada.get(clave)
        vacio = valor is None or (isinstance(valor, str) and not valor.strip())
        if vacio:
            errores.append(
                ErrorValidacion(
                    fichero=fichero,
                    objeto=None,
                    regla="R4",
                    detalle=f"el esquema `{esquema}` no declara `{clave}`",
                )
            )

    refresco = entrada.get("refresco")
    if isinstance(refresco, str) and refresco and refresco not in REFRESCOS:
        errores.append(
            ErrorValidacion(
                fichero=fichero,
                objeto=None,
                regla="R4",
                detalle=(
                    f"el esquema `{esquema}` declara `refresco` = '{refresco}', "
                    f"fuera del vocabulario: {_lista(REFRESCOS)}"
                ),
            )
        )

    consumo = entrada.get("consumo_recomendado")
    if consumo is not None and not isinstance(consumo, bool):
        errores.append(
            ErrorValidacion(
                fichero=fichero,
                objeto=None,
                regla="R4",
                detalle=(
                    f"el esquema `{esquema}` declara `consumo_recomendado` = "
                    f"{consumo!r}, que no es un booleano"
                ),
            )
        )
    return errores


def _validar_duplicados(dicc: Diccionario) -> list[ErrorValidacion]:
    """Dos fichas del mismo objeto: el MCP vería una sola, y a suertes."""
    vistos: set[str] = set()
    errores: list[ErrorValidacion] = []
    for ficha in dicc.fichas:
        if ficha.nombre in vistos:
            errores.append(
                ErrorValidacion(
                    fichero=ficha.fichero,
                    objeto=ficha.nombre,
                    regla="R2",
                    detalle=f"ficha duplicada: `{ficha.nombre}` aparece más de una vez",
                )
            )
        vistos.add(ficha.nombre)
    return errores


def _validar_ficha(
    ficha: Ficha,
    dicc: Diccionario,
    indice: Mapping[str, Ficha],
    pasos_nocturnos: Sequence[str],
) -> list[ErrorValidacion]:
    errores: list[ErrorValidacion] = []

    def error(regla: str, detalle: str) -> None:
        errores.append(
            ErrorValidacion(
                fichero=ficha.fichero,
                objeto=ficha.nombre,
                regla=regla,
                detalle=detalle,
            )
        )

    # --- R4: la ficha pertenece a uno de los nueve esquemas -----------------
    if ficha.esquema not in ESQUEMAS_DEL_DATAMART:
        error(
            "R4",
            f"la ficha pertenece al esquema `{ficha.esquema}`, que no existe en el "
            f"datamart: {_lista(ESQUEMAS_DEL_DATAMART)}",
        )
    elif ficha.esquema not in dicc.esquemas:
        error(
            "R4",
            f"el esquema `{ficha.esquema}` no tiene entrada en `esquemas` de "
            f"00_global.yaml",
        )

    # --- R2: vocabularios ---------------------------------------------------
    if ficha.tipo not in TIPOS:
        error(
            "R2",
            f"`tipo` = '{ficha.tipo}' no está en el vocabulario: {_lista(TIPOS)}",
        )
    if ficha.capa not in CAPAS:
        error(
            "R2",
            f"`capa` = '{ficha.capa}' no está en el vocabulario: {_lista(CAPAS)}",
        )
    if ficha.refresco not in REFRESCOS:
        error(
            "R2",
            f"`refresco` = '{ficha.refresco}' no está en el vocabulario: "
            f"{_lista(REFRESCOS)}",
        )
    if not isinstance(ficha.consumo_recomendado, bool):
        error("R2", "`consumo_recomendado` tiene que ser un booleano")

    # --- R2: texto de negocio obligatorio -----------------------------------
    error_texto = _corto(
        "descripcion", ficha.descripcion, "qué es el objeto, en lenguaje de negocio"
    )
    if error_texto:
        error("R2", error_texto)

    es_relacion = ficha.tipo in ("tabla", "vista")
    if es_relacion:
        error_texto = _corto("grano", ficha.grano, "qué es UNA fila de este objeto")
        if error_texto:
            error("R2", error_texto)
    if es_relacion and not ficha.clave_negocio:
        error("R2", "falta `clave_negocio`: qué columnas identifican una fila")

    # --- R3: la puerta trasera cerrada --------------------------------------
    if not ficha.consumo_recomendado:
        error_texto = _corto(
            "motivo_no_consumo",
            ficha.motivo_no_consumo,
            "por qué este objeto NO se recomienda para consulta. Sin esta "
            "exigencia, bajar el booleano sería la forma silenciosa de esquivar "
            "la puerta de cobertura de columnas",
        )
        if error_texto:
            error("R3", error_texto)

    # --- R6, R26: la superficie de consumo se describe entera ---------------
    # Las funciones quedan exentas de `columnas` aunque estén recomendadas:
    # una función no tiene columnas que describir.
    if ficha.consumo_recomendado and ficha.tipo != "funcion" and not ficha.columnas:
        error(
            "R6",
            "un objeto con `consumo_recomendado: true` tiene que documentar sus "
            "`columnas`: es la superficie que el agente va a consultar",
        )
    for ejemplo in ficha.ejemplos_preguntas:
        if len(ejemplo.strip()) < MINIMOS_TEXTO["ejemplo_pregunta"]:
            error(
                "R40",
                f"la entrada de `ejemplos_preguntas` {ejemplo!r} no llega a "
                f"{MINIMOS_TEXTO['ejemplo_pregunta']} caracteres: no es una "
                f"pregunta de negocio, es un hueco relleno",
            )

    if ficha.consumo_recomendado and not ficha.ejemplos_preguntas:
        error(
            "R40",
            "un objeto con `consumo_recomendado: true` tiene que traer al menos "
            "una entrada en `ejemplos_preguntas`: es lo que permite enrutar de la "
            "pregunta al objeto",
        )

    # --- R12: los avisos se derivan, no se escriben -------------------------
    if ficha.avisos:
        error(
            "R12",
            "`avisos` no se escribe a mano: lo deriva el validador desde el "
            "`ambito` de las reglas de 00_global.yaml. Borra la clave de la ficha",
        )

    errores.extend(_validar_columnas(ficha))
    errores.extend(_validar_clave_negocio(ficha))
    errores.extend(_validar_relaciones(ficha, indice, dicc.pendientes))
    errores.extend(_validar_frescura(ficha, pasos_nocturnos))

    return errores


def _validar_columnas(ficha: Ficha) -> list[ErrorValidacion]:
    """R6 (significado obligatorio) y R7 (vocabulario de `agregacion`)."""
    errores: list[ErrorValidacion] = []
    vistas: set[str] = set()

    for columna in ficha.columnas:
        def error(regla: str, detalle: str) -> None:
            errores.append(
                ErrorValidacion(
                    fichero=ficha.fichero,
                    objeto=ficha.nombre,
                    regla=regla,
                    detalle=detalle,
                )
            )

        if not (columna.nombre or "").strip():
            error("R6", "hay una columna sin nombre")
        elif columna.nombre in vistas:
            error("R6", f"columna duplicada: `{columna.nombre}`")
        vistas.add(columna.nombre)

        error_texto = _corto(
            "significado",
            columna.significado,
            f"qué es la columna `{columna.nombre}`, en lenguaje de negocio",
        )
        if error_texto:
            error("R6", f"columna `{columna.nombre}`: {error_texto}")

        if columna.agregacion is not None and columna.agregacion not in AGREGACIONES:
            error(
                "R7",
                f"la columna `{columna.nombre}` declara `agregacion` = "
                f"'{columna.agregacion}', fuera del vocabulario cerrado: "
                f"{_lista(AGREGACIONES)}",
            )
    return errores


def _validar_clave_negocio(ficha: Ficha) -> list[ErrorValidacion]:
    """La clave de negocio nombra columnas de la propia ficha (design §3.4).

    Solo se comprueba cuando la ficha documenta columnas: las de `raw` van a
    nivel de objeto (DA-2) y ahí no hay nada contra lo que contrastar.
    """
    if not ficha.columnas:
        return []
    nombres = {c.nombre for c in ficha.columnas}
    return [
        ErrorValidacion(
            fichero=ficha.fichero,
            objeto=ficha.nombre,
            regla="R2",
            detalle=(
                f"`clave_negocio` nombra la columna `{col}`, que no está "
                f"documentada en la propia ficha"
            ),
        )
        for col in ficha.clave_negocio
        if col not in nombres
    ]


def _validar_relaciones(
    ficha: Ficha, indice: Mapping[str, Ficha], pendientes: Sequence[str]
) -> list[ErrorValidacion]:
    """R5: toda relación resuelve contra el diccionario, en los dos extremos."""
    errores: list[ErrorValidacion] = []
    propias = {c.nombre for c in ficha.columnas}

    for relacion in ficha.relaciones:
        def error(detalle: str) -> None:
            errores.append(
                ErrorValidacion(
                    fichero=ficha.fichero,
                    objeto=ficha.nombre,
                    regla="R5",
                    detalle=detalle,
                )
            )

        if relacion.cardinalidad not in CARDINALIDADES:
            error(
                f"la relación hacia `{relacion.a}` declara `cardinalidad` = "
                f"'{relacion.cardinalidad}', fuera del vocabulario: "
                f"{_lista(CARDINALIDADES)}. Si querías `1:1`, escríbelo ENTRE "
                f"COMILLAS: YAML lee `1:1` sin comillas como el número 61"
            )

        if propias and relacion.de not in propias:
            error(
                f"la relación hacia `{relacion.a}` sale de `{relacion.de}`, que no "
                f"es una columna documentada de esta ficha"
            )

        partes = relacion.a.split(".")
        if len(partes) != 3:
            error(
                f"el destino `{relacion.a}` no tiene la forma "
                f"`esquema.objeto.columna`"
            )
            continue

        esquema, objeto, columna = partes
        destino = indice.get(f"{esquema}.{objeto}")
        if destino is None:
            # Mientras su bloque no esté escrito, el objeto está declarado en
            # `pendientes` y la relación se tolera: es lo que permite escribir
            # ya el camino de JOIN más valioso del datamart sin esperar a que
            # estén las ochenta fichas. La comprobación no se salta, se aplaza:
            # en cuanto el destino tenga ficha, la columna se verifica, y al
            # cerrar F-006 `pendientes` está vacía y esto vuelve a ser estricto.
            if f"{esquema}.{objeto}" not in pendientes:
                error(
                    f"el destino `{relacion.a}` apunta a `{esquema}.{objeto}`, que "
                    f"no tiene ficha en el diccionario ni está declarado en "
                    f"`pendientes`"
                )
            continue

        if destino.columnas and columna not in {c.nombre for c in destino.columnas}:
            error(
                f"el destino `{relacion.a}` apunta a la columna `{columna}`, que no "
                f"está documentada en `{destino.nombre}`"
            )
            continue

        errores.extend(_validar_cardinalidad(ficha, relacion, destino, columna))
    return errores


def _es_unica_por(ficha: Ficha, columna: str) -> bool | None:
    """¿Una fila de `ficha` queda identificada por esa columna sola?

    Devuelve `None` cuando no se puede saber —la ficha no declara clave de
    negocio ni columnas, como las de `raw`—, para poder aplazar el juicio en vez
    de inventárselo.

    Dos formas de ser única: ser ELLA SOLA la clave de negocio, o estar marcada
    `agregacion: clave_sustituta`. Lo segundo hace falta porque las claves
    sustitutas se dejan fuera de `clave_negocio` a propósito (cambian en cada
    build) y aun así identifican la fila dentro de un mismo build: es lo que
    hace legítima la relación `1:1` entre una tabla de hecho y su vista
    aligerada.
    """
    if not ficha.clave_negocio and not ficha.columnas:
        return None
    if tuple(ficha.clave_negocio) == (columna,):
        return True
    for candidata in ficha.columnas:
        if candidata.nombre == columna and candidata.agregacion == "clave_sustituta":
            return True
    return False


def _validar_cardinalidad(
    ficha: Ficha, relacion: Relacion, destino: Ficha, columna: str
) -> list[ErrorValidacion]:
    """Un lado `1` de la cardinalidad promete unicidad. Aquí se comprueba.

    Por qué esto merece un test y no una revisión a mano: seis relaciones se
    publicaron diciendo `N:1` sobre `obra_id` cuando el destino tiene muchas
    filas por obra. Un agente que se fía escribe el JOIN sin agregar antes y
    **duplica importes en silencio** — el mismo error que
    `R-RETENCION-NO-JOIN-LINEAS` existe para castigar, cometido dentro del
    propio diccionario.

    No hace falta auditar nada: el diccionario ya declara la clave de negocio de
    cada objeto, así que la unicidad es DERIVABLE. Cuando el extremo todavía no
    tiene ficha —está en `pendientes`— el juicio se aplaza, igual que el resto de
    comprobaciones de relación.
    """
    if relacion.cardinalidad not in CARDINALIDADES:
        return []

    izquierda, derecha = relacion.cardinalidad.split(":")
    problemas: list[tuple[str, str]] = []

    if izquierda == "1" and _es_unica_por(ficha, relacion.de) is False:
        problemas.append(
            (
                f"`{ficha.nombre}` tiene varias filas por `{relacion.de}` "
                f"(su clave es {list(ficha.clave_negocio)})",
                "izquierdo",
            )
        )
    if derecha == "1" and _es_unica_por(destino, columna) is False:
        problemas.append(
            (
                f"`{destino.nombre}` tiene varias filas por `{columna}` "
                f"(su clave es {list(destino.clave_negocio)})",
                "derecho",
            )
        )

    if not problemas:
        return []

    detalle = "; ".join(p for p, _ in problemas)
    return [
        ErrorValidacion(
            fichero=ficha.fichero,
            objeto=ficha.nombre,
            regla="R5",
            detalle=(
                f"la relación hacia `{relacion.a}` declara "
                f"`{relacion.cardinalidad}` y eso promete una unicidad que no "
                f"existe: {detalle}. El JOIN produciría fan-out y duplicaría "
                f"importes. La cardinalidad cierta es `N:N`, y conviene decir en "
                f"`porque` por qué clave hay que agregar antes de unir"
            ),
        )
    ]


def _validar_frescura(
    ficha: Ficha, pasos_nocturnos: Sequence[str]
) -> list[ErrorValidacion]:
    """R13 (`refresco` y `paso_etl` declarados) y R14 (y que no mientan).

    R14 es la defensa contra la respuesta de hace semanas dada con aplomo:
    `cierre`, `compras`, `maestro` y `retenciones` no están en el pipeline
    nocturno y se construyen a mano. Aquí no hay ninguna lista de esos cuatro
    esquemas escrita a mano: se comprueba contra `pasos_nocturnos`, que sale de
    `main.build_pipeline_steps`. El día que uno de ellos entre en `run-all`, el
    veredicto cambia solo.

    La comprobación es **en los dos sentidos**. Declararse `nocturno` sin correr
    de noche promete una frescura que no existe; declararse `manual` corriendo de
    noche hace que el agente cite una fecha de build que no hacía falta citar y
    desconfíe de un dato bueno. Las dos son mentiras sobre lo mismo.
    """
    errores: list[ErrorValidacion] = []

    def error(regla: str, detalle: str) -> None:
        errores.append(
            ErrorValidacion(
                fichero=ficha.fichero,
                objeto=ficha.nombre,
                regla=regla,
                detalle=detalle,
            )
        )

    if ficha.refresco == "estatico":
        return errores

    paso = (ficha.paso_etl or "").strip()
    if not paso:
        error(
            "R13",
            "falta `paso_etl`: el nombre del paso tal y como aparece en la "
            "columna `paso` de `_meta.v_frescura`. Solo `refresco: estatico` "
            "está exento",
        )
        return errores

    corre_de_noche = paso in pasos_nocturnos
    if ficha.refresco == "nocturno" and not corre_de_noche:
        error(
            "R14",
            f"declara `refresco: nocturno` pero su paso `{paso}` no forma parte "
            f"del pipeline de `run-all` ({_lista(tuple(pasos_nocturnos))}): se "
            f"construye a mano y puede estar arbitrariamente desfasado",
        )
    elif ficha.refresco == "manual" and corre_de_noche:
        error(
            "R14",
            f"declara `refresco: manual` pero su paso `{paso}` SÍ forma parte del "
            f"pipeline de `run-all`: el dato se refresca cada noche",
        )
    return errores


def _validar_reglas(
    dicc: Diccionario, indice: Mapping[str, Ficha]
) -> list[ErrorValidacion]:
    """R9 (las doce, completas y bien formadas) y R11 (ámbitos resolubles)."""
    errores: list[ErrorValidacion] = []
    fichero = "00_global.yaml"

    declaradas = [r.codigo for r in dicc.reglas]
    for codigo in CODIGOS_REGLAS_OBLIGATORIAS:
        if codigo not in declaradas:
            errores.append(
                ErrorValidacion(
                    fichero=fichero,
                    objeto=codigo,
                    regla="R9",
                    detalle=(
                        f"falta la regla obligatoria `{codigo}` en el bloque "
                        f"`reglas`. Sin ella el agente pierde esa defensa y nadie "
                        f"se entera"
                    ),
                )
            )

    vistos: set[str] = set()
    for regla in dicc.reglas:
        if regla.codigo in vistos:
            errores.append(
                ErrorValidacion(
                    fichero=fichero,
                    objeto=regla.codigo,
                    regla="R9",
                    detalle=f"regla duplicada: `{regla.codigo}` aparece más de una vez",
                )
            )
        vistos.add(regla.codigo)

    for regla in dicc.reglas:
        # `codigo` se liga en la firma a propósito: una función anidada que
        # capturase `regla` del bucle es un fallo clásico en cuanto alguien
        # difiera la llamada, y ruff lo marca (B023).
        def error(codigo_ears: str, detalle: str, codigo: str = regla.codigo) -> None:
            errores.append(
                ErrorValidacion(
                    fichero=fichero,
                    objeto=codigo,
                    regla=codigo_ears,
                    detalle=detalle,
                )
            )

        if regla.severidad not in SEVERIDADES:
            error(
                "R9",
                f"la regla `{regla.codigo}` declara `severidad` = "
                f"'{regla.severidad}', fuera del vocabulario: {_lista(SEVERIDADES)}",
            )
        for campo in ("titulo", "regla", "motivo"):
            if not (getattr(regla, campo) or "").strip():
                error("R9", f"la regla `{regla.codigo}` no declara `{campo}`")
        if not regla.ambito:
            error(
                "R9",
                f"la regla `{regla.codigo}` no declara `ambito`: una regla que no "
                f"se adjunta a ningún objeto no protege nada",
            )

        for destino in regla.ambito:
            if "." in destino:
                if destino not in indice and destino not in dicc.pendientes:
                    error(
                        "R11",
                        f"la regla `{regla.codigo}` declara en su `ambito` el objeto "
                        f"`{destino}`, que no tiene ficha en el diccionario ni está "
                        f"declarado en `pendientes`. Una regla que apunta a la nada "
                        f"no protege nada",
                    )
            elif destino not in ESQUEMAS_DEL_DATAMART:
                error(
                    "R11",
                    f"la regla `{regla.codigo}` declara en su `ambito` el esquema "
                    f"`{destino}`, que no existe en el datamart: "
                    f"{_lista(ESQUEMAS_DEL_DATAMART)}",
                )
    return errores


# ---------------------------------------------------------------------------
# R12 · Derivación de avisos
# ---------------------------------------------------------------------------


def alcanza(regla: Regla, ficha: Ficha) -> bool:
    """¿El ámbito de la regla incluye a esta ficha?

    Un ámbito sin punto es un esquema entero; con punto, un objeto concreto.
    """
    return ficha.esquema in regla.ambito or ficha.nombre in regla.ambito


def derivar_avisos(dicc: Diccionario) -> Diccionario:
    """Adjunta a cada ficha los códigos de las reglas cuyo ámbito la incluye (R12).

    Existe para que un agente que solo consulte la ficha de un objeto vea sus
    trampas **sin haber leído el bloque global**, que es lo que va a pasar en la
    práctica: el MCP sirve `describir_tabla` mucho más a menudo que el contexto
    entero.

    La derivación es automática a propósito: el autor de la ficha no tiene que
    acordarse de nada, y por eso `validar` rechaza un `avisos` escrito a mano.
    Devuelve un diccionario NUEVO —las entidades son inmutables— y es idempotente:
    aplicarla dos veces da exactamente lo mismo, porque reemplaza la lista en vez
    de acumularla.
    """
    fichas = tuple(
        replace(
            ficha,
            avisos=tuple(
                sorted({r.codigo for r in dicc.reglas if alcanza(r, ficha)})
            ),
        )
        for ficha in dicc.fichas
    )
    return replace(dicc, fichas=fichas)


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------


def formatear_errores(errores: Sequence[ErrorValidacion]) -> str:
    """Informe legible: fichero, ficha y regla en cada línea.

    Quien lo lea tiene que saber **qué abrir y qué corregir** sin volver a
    buscar. Por eso no se agrupa por regla: se agrupa por fichero, que es lo
    que se edita.
    """
    if not errores:
        return "Diccionario: OK. Ninguna ficha incumple el formato."

    lineas = [
        f"Diccionario: KO. {len(errores)} problema(s) de formato:",
    ]
    fichero_actual: str | None = None
    for error in sorted(errores, key=lambda e: e.clave_orden):
        if error.fichero != fichero_actual:
            fichero_actual = error.fichero
            lineas.append(f"  {fichero_actual}")
        donde = error.objeto or "(global)"
        lineas.append(f"    · [{error.regla}] {donde}: {error.detalle}")
    return "\n".join(lineas)
