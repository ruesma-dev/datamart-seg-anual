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
from dataclasses import dataclass

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

#: Severidad de una regla dura del diccionario.
SEVERIDADES = ("bloqueante", "aviso")

#: Claves obligatorias de cada entrada de `esquemas` en `00_global.yaml` (R4).
CLAVES_ESQUEMA = ("titulo", "para_que_sirve", "consumo_recomendado", "refresco")


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
    if not (ficha.descripcion or "").strip():
        error("R2", "falta `descripcion`: qué es el objeto, en lenguaje de negocio")

    es_relacion = ficha.tipo in ("tabla", "vista")
    if es_relacion and not (ficha.grano or "").strip():
        error("R2", "falta `grano`: qué es UNA fila de este objeto")
    if es_relacion and not ficha.clave_negocio:
        error("R2", "falta `clave_negocio`: qué columnas identifican una fila")

    # --- R3: la puerta trasera cerrada --------------------------------------
    if not ficha.consumo_recomendado and not (ficha.motivo_no_consumo or "").strip():
        error(
            "R3",
            "`consumo_recomendado: false` exige `motivo_no_consumo` escrito. Sin "
            "esa exigencia, bajar el booleano sería la forma silenciosa de "
            "esquivar la puerta de cobertura de columnas",
        )

    # --- R6, R26: la superficie de consumo se describe entera ---------------
    # Las funciones quedan exentas de `columnas` aunque estén recomendadas:
    # una función no tiene columnas que describir.
    if ficha.consumo_recomendado and ficha.tipo != "funcion" and not ficha.columnas:
        error(
            "R6",
            "un objeto con `consumo_recomendado: true` tiene que documentar sus "
            "`columnas`: es la superficie que el agente va a consultar",
        )
    if ficha.consumo_recomendado and not ficha.ejemplos_preguntas:
        error(
            "R40",
            "un objeto con `consumo_recomendado: true` tiene que traer al menos "
            "una entrada en `ejemplos_preguntas`: es lo que permite enrutar de la "
            "pregunta al objeto",
        )

    errores.extend(_validar_columnas(ficha))
    errores.extend(_validar_clave_negocio(ficha))
    errores.extend(_validar_relaciones(ficha, indice))
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

        if not (columna.significado or "").strip():
            error(
                "R6",
                f"la columna `{columna.nombre}` no tiene `significado` en lenguaje "
                f"de negocio",
            )

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
    ficha: Ficha, indice: Mapping[str, Ficha]
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
            error(
                f"el destino `{relacion.a}` apunta a `{esquema}.{objeto}`, que no "
                f"tiene ficha en el diccionario"
            )
            continue

        if destino.columnas and columna not in {c.nombre for c in destino.columnas}:
            error(
                f"el destino `{relacion.a}` apunta a la columna `{columna}`, que no "
                f"está documentada en `{destino.nombre}`"
            )
    return errores


def _validar_frescura(
    ficha: Ficha, pasos_nocturnos: Sequence[str]
) -> list[ErrorValidacion]:
    """R13: `refresco` y `paso_etl` declarados.

    El cruce contra la composición REAL del pipeline (R14) se añade en T5;
    `pasos_nocturnos` llega hasta aquí desde `validar` para eso.
    """
    if ficha.refresco == "estatico":
        return []
    if (ficha.paso_etl or "").strip():
        return []
    return [
        ErrorValidacion(
            fichero=ficha.fichero,
            objeto=ficha.nombre,
            regla="R13",
            detalle=(
                "falta `paso_etl`: el nombre del paso tal y como aparece en la "
                "columna `paso` de `_meta.v_frescura`. Solo `refresco: estatico` "
                "está exento"
            ),
        )
    ]


def _validar_reglas(
    dicc: Diccionario, indice: Mapping[str, Ficha]
) -> list[ErrorValidacion]:
    """Formato de las reglas duras. El contenido exigible (las doce) es R9."""
    errores: list[ErrorValidacion] = []
    fichero = "00_global.yaml"

    for regla in dicc.reglas:
        def error(codigo_ears: str, detalle: str) -> None:
            errores.append(
                ErrorValidacion(
                    fichero=fichero,
                    objeto=regla.codigo,
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
    return errores


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
