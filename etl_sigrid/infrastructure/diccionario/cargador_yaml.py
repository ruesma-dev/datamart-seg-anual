# etl_sigrid/infrastructure/diccionario/cargador_yaml.py
"""
Lectura de `config/diccionario/*.yaml` y construcción del `Diccionario` (F-006).

Es el único punto del sistema que sabe que el diccionario se escribe en YAML.
El dominio (`etl_sigrid/domain/diccionario.py`) recibe entidades ya construidas
y no importa `yaml` ni abre un fichero: esa frontera es lo que permite que el
validador corra en cada `bash harness/init.sh` sin nada montado.

Reparto de responsabilidades, que no es evidente y conviene fijarlo:

* **este módulo** se ocupa de la FORMA: que el YAML parsee, que las claves sean
  las que existen, que el nombre del fichero case con el esquema que declara.
  Lo que aquí falla no se puede ni representar como entidad, así que sale como
  excepción `DiccionarioIlegible` con su fichero y su línea.
* **`validar`** se ocupa del CONTENIDO: vocabularios, relaciones resolubles,
  frescura que no miente. Por eso el cargador es permisivo con los valores —un
  `refresco` inventado se construye igual— y estricto con las claves: un
  `significao:` mal escrito dejaría la columna muda sin que nadie lo notase.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from etl_sigrid.domain.diccionario import (
    Columna,
    Diccionario,
    ErrorValidacion,
    Ficha,
    Regla,
    Relacion,
)

#: El bloque global. Va primero en orden alfabético a propósito: el `00_` hace
#: que encabece el listado y que entre el primero en el hash.
FICHERO_GLOBAL = "00_global.yaml"

CLAVES_GLOBAL = frozenset(
    {
        "version",
        "base",
        "titulo",
        "descripcion_negocio",
        "ejes",
        "convenciones",
        "esquemas",
        "reglas",
        "ordenes_de_magnitud",
        "ocultar",
        "pendientes",
        "preguntas_aceptacion",
    }
)
CLAVES_FICHERO_ESQUEMA = frozenset({"version", "esquema", "objetos"})
CLAVES_FICHA = frozenset(
    {
        "tipo",
        "capa",
        "consumo_recomendado",
        "motivo_no_consumo",
        "descripcion",
        "grano",
        "clave_negocio",
        "paso_etl",
        "refresco",
        "columnas",
        "relaciones",
        "ejemplos_preguntas",
        "avisos",
    }
)
CLAVES_COLUMNA = frozenset(
    {"significado", "unidad", "agregacion", "valores", "nulo_significa"}
)
CLAVES_RELACION = frozenset({"de", "a", "cardinalidad", "porque"})
CLAVES_REGLA = frozenset(
    {"codigo", "titulo", "severidad", "ambito", "regla", "motivo", "orden"}
)


class DiccionarioIlegible(Exception):  # noqa: N818 - el codigo de este repositorio esta en espanol y `DiccionarioIlegibleError` no se lee
    """El YAML no se puede convertir en entidades. Trae el porqué, no una traza.

    Un `yaml.scanner.ScannerError` crudo en la salida del ETL a las 2 de la
    mañana no dice qué fichero abrir. Estos errores sí.
    """

    def __init__(self, errores: Sequence[ErrorValidacion]) -> None:
        self.errores: tuple[ErrorValidacion, ...] = tuple(errores)
        super().__init__(
            "; ".join(f"{e.fichero}: {e.detalle}" for e in self.errores)
            or "diccionario ilegible"
        )


def _error(fichero: str, detalle: str, objeto: str | None = None) -> ErrorValidacion:
    return ErrorValidacion(
        fichero=fichero, objeto=objeto, regla="R1", detalle=detalle
    )


def _texto(valor: object) -> str:
    """Escalar del YAML a texto. `None` es cadena vacía, no la palabra 'None'."""
    return "" if valor is None else str(valor)


def _tupla(valor: object) -> tuple[str, ...]:
    """Lista del YAML a tupla de textos. Un escalar suelto vale como lista de uno."""
    if valor is None:
        return ()
    if isinstance(valor, (list, tuple)):
        return tuple(_texto(v) for v in valor)
    return (_texto(valor),)


def _claves_desconocidas(
    datos: Mapping[str, object], admitidas: frozenset[str], donde: str
) -> list[str]:
    return [
        f"`{clave}` no es una clave admitida en {donde}: "
        f"{', '.join(sorted(admitidas))}"
        for clave in datos
        if clave not in admitidas
    ]


def cargar_diccionario(directorio: Path) -> tuple[Diccionario, str]:
    """Lee el diccionario entero y devuelve `(Diccionario, hash_fuente)`.

    El `hash_fuente` es el SHA-256 de los ficheros **en orden alfabético de
    nombre**, incluyendo el nombre de cada uno en el flujo: así renombrar un
    fichero cambia el hash. Se normalizan los finales de línea a `\\n` antes de
    resumir, para que el mismo contenido dé el mismo hash en el puesto (CRLF) y
    en el contenedor (LF) — si no, la comparación «¿el diccionario publicado es
    el del repositorio?» daría siempre que no.

    Levanta `DiccionarioIlegible` si algo no se puede ni representar. No valida
    contenido: de eso se ocupa `validar`.
    """
    errores: list[ErrorValidacion] = []
    ficheros = sorted(p for p in directorio.glob("*.yaml") if p.is_file())

    if not any(p.name == FICHERO_GLOBAL for p in ficheros):
        raise DiccionarioIlegible(
            [
                _error(
                    FICHERO_GLOBAL,
                    f"no existe {FICHERO_GLOBAL} en {directorio}: sin bloque global "
                    f"no hay reglas, ni esquemas, ni pendientes",
                )
            ]
        )

    documentos: dict[str, Mapping[str, object]] = {}
    trozos: list[bytes] = []
    for ruta in ficheros:
        texto = ruta.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        trozos.append(ruta.name.encode("utf-8"))
        trozos.append(b"\n")
        trozos.append(texto.encode("utf-8"))
        try:
            datos = yaml.safe_load(texto)
        except yaml.YAMLError as exc:
            errores.append(_error(ruta.name, _detalle_yaml(exc)))
            continue
        if datos is None:
            datos = {}
        if not isinstance(datos, dict):
            errores.append(
                _error(ruta.name, "el fichero no contiene un mapa en su raíz")
            )
            continue
        documentos[ruta.name] = datos

    hash_fuente = hashlib.sha256(b"".join(trozos)).hexdigest()

    if errores:
        raise DiccionarioIlegible(errores)

    global_datos = documentos.pop(FICHERO_GLOBAL)
    errores.extend(
        _error(FICHERO_GLOBAL, detalle)
        for detalle in _claves_desconocidas(
            global_datos, CLAVES_GLOBAL, "00_global.yaml"
        )
    )

    reglas = _cargar_reglas(global_datos.get("reglas"), errores)
    fichas: list[Ficha] = []
    for nombre in sorted(documentos):
        fichas.extend(_cargar_fichero_esquema(nombre, documentos[nombre], errores))

    if errores:
        raise DiccionarioIlegible(errores)

    esquemas = global_datos.get("esquemas") or {}
    if not isinstance(esquemas, dict):
        raise DiccionarioIlegible(
            [_error(FICHERO_GLOBAL, "`esquemas` tiene que ser un mapa")]
        )

    dicc = Diccionario(
        version=_texto(global_datos.get("version")),
        base=_texto(global_datos.get("base")),
        fichas=tuple(fichas),
        reglas=tuple(reglas),
        esquemas=esquemas,
        pendientes=_tupla(global_datos.get("pendientes")),
        global_raw=dict(global_datos),
    )
    return dicc, hash_fuente


def _detalle_yaml(exc: yaml.YAMLError) -> str:
    """Mensaje de un error de parseo con su línea, sin la traza de `yaml`."""
    marca = getattr(exc, "problem_mark", None)
    problema = getattr(exc, "problem", None) or "YAML mal formado"
    if marca is None:
        return f"el YAML no parsea: {problema}"
    return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"


def _cargar_reglas(
    crudas: object, errores: list[ErrorValidacion]
) -> list[Regla]:
    if crudas is None:
        return []
    if not isinstance(crudas, list):
        errores.append(_error(FICHERO_GLOBAL, "`reglas` tiene que ser una lista"))
        return []

    reglas: list[Regla] = []
    for posicion, cruda in enumerate(crudas):
        if not isinstance(cruda, dict):
            errores.append(
                _error(FICHERO_GLOBAL, f"la regla en posición {posicion} no es un mapa")
            )
            continue
        codigo = _texto(cruda.get("codigo"))
        errores.extend(
            _error(FICHERO_GLOBAL, detalle, objeto=codigo)
            for detalle in _claves_desconocidas(
                cruda, CLAVES_REGLA, f"la regla `{codigo}`"
            )
        )
        reglas.append(
            Regla(
                codigo=codigo,
                titulo=_texto(cruda.get("titulo")),
                severidad=_texto(cruda.get("severidad")),
                ambito=_tupla(cruda.get("ambito")),
                regla=_texto(cruda.get("regla")),
                motivo=_texto(cruda.get("motivo")),
                orden=int(cruda.get("orden") or posicion),
            )
        )
    return reglas


def _cargar_fichero_esquema(
    fichero: str, datos: Mapping[str, object], errores: list[ErrorValidacion]
) -> list[Ficha]:
    errores.extend(
        _error(fichero, detalle)
        for detalle in _claves_desconocidas(datos, CLAVES_FICHERO_ESQUEMA, fichero)
    )

    esquema = _texto(datos.get("esquema"))
    esperado = fichero[: -len(".yaml")]
    if esquema != esperado:
        errores.append(
            _error(
                fichero,
                f"el fichero `{fichero}` declara `esquema: {esquema}`. El nombre del "
                f"fichero manda: tiene que ser `{esperado}`",
            )
        )
        return []

    objetos = datos.get("objetos") or {}
    if not isinstance(objetos, dict):
        errores.append(_error(fichero, "`objetos` tiene que ser un mapa"))
        return []

    return [
        ficha
        for nombre, cuerpo in objetos.items()
        if (ficha := _cargar_ficha(fichero, esquema, _texto(nombre), cuerpo, errores))
    ]


def _cargar_ficha(
    fichero: str,
    esquema: str,
    objeto: str,
    cuerpo: object,
    errores: list[ErrorValidacion],
) -> Ficha | None:
    nombre = f"{esquema}.{objeto}"
    if not isinstance(cuerpo, dict):
        errores.append(
            _error(
                fichero,
                f"la ficha `{objeto}` no tiene cuerpo: un objeto documentado necesita "
                f"al menos `tipo`, `capa`, `descripcion` y `grano`",
                objeto=nombre,
            )
        )
        return None

    errores.extend(
        _error(fichero, detalle, objeto=nombre)
        for detalle in _claves_desconocidas(cuerpo, CLAVES_FICHA, f"la ficha `{nombre}`")
    )

    return Ficha(
        esquema=esquema,
        objeto=objeto,
        tipo=_texto(cuerpo.get("tipo")),
        capa=_texto(cuerpo.get("capa")),
        consumo_recomendado=cuerpo.get("consumo_recomendado"),  # type: ignore[arg-type]
        descripcion=_texto(cuerpo.get("descripcion")),
        grano=cuerpo.get("grano") if cuerpo.get("grano") is None else _texto(cuerpo.get("grano")),
        clave_negocio=_tupla(cuerpo.get("clave_negocio")),
        paso_etl=None if cuerpo.get("paso_etl") is None else _texto(cuerpo.get("paso_etl")),
        refresco=_texto(cuerpo.get("refresco")),
        columnas=_cargar_columnas(fichero, nombre, cuerpo.get("columnas"), errores),
        relaciones=_cargar_relaciones(fichero, nombre, cuerpo.get("relaciones"), errores),
        ejemplos_preguntas=_tupla(cuerpo.get("ejemplos_preguntas")),
        motivo_no_consumo=(
            None
            if cuerpo.get("motivo_no_consumo") is None
            else _texto(cuerpo.get("motivo_no_consumo"))
        ),
        # Se conserva tal cual para que `validar` pueda acusarlo (R12): borrarlo
        # aquí en silencio dejaría al autor creyendo que su lista se publica.
        avisos=_tupla(cuerpo.get("avisos")),
    )


def _cargar_columnas(
    fichero: str, nombre: str, crudas: object, errores: list[ErrorValidacion]
) -> tuple[Columna, ...]:
    """Normaliza la forma abreviada `columna: "<significado>"` (R6).

    El orden del YAML se conserva: es editorial —primero las claves, luego los
    importes— y el MCP lo sirve tal cual.
    """
    if crudas is None:
        return ()
    if not isinstance(crudas, dict):
        errores.append(
            _error(fichero, "`columnas` tiene que ser un mapa", objeto=nombre)
        )
        return ()

    columnas: list[Columna] = []
    for columna, cuerpo in crudas.items():
        if cuerpo is None or isinstance(cuerpo, (str, int, float, bool)):
            columnas.append(Columna(nombre=_texto(columna), significado=_texto(cuerpo)))
            continue
        if not isinstance(cuerpo, dict):
            errores.append(
                _error(
                    fichero,
                    f"la columna `{columna}` no es ni un texto ni un mapa",
                    objeto=nombre,
                )
            )
            continue
        errores.extend(
            _error(fichero, detalle, objeto=nombre)
            for detalle in _claves_desconocidas(
                cuerpo, CLAVES_COLUMNA, f"la columna `{columna}` de `{nombre}`"
            )
        )
        columnas.append(
            Columna(
                nombre=_texto(columna),
                significado=_texto(cuerpo.get("significado")),
                unidad=None if cuerpo.get("unidad") is None else _texto(cuerpo.get("unidad")),
                agregacion=(
                    None
                    if cuerpo.get("agregacion") is None
                    else _texto(cuerpo.get("agregacion"))
                ),
                valores=_tupla(cuerpo.get("valores")),
                nulo_significa=(
                    None
                    if cuerpo.get("nulo_significa") is None
                    else _texto(cuerpo.get("nulo_significa"))
                ),
            )
        )
    return tuple(columnas)


def _cargar_relaciones(
    fichero: str, nombre: str, crudas: object, errores: list[ErrorValidacion]
) -> tuple[Relacion, ...]:
    if crudas is None:
        return ()
    if not isinstance(crudas, list):
        errores.append(
            _error(fichero, "`relaciones` tiene que ser una lista", objeto=nombre)
        )
        return ()

    relaciones: list[Relacion] = []
    for cruda in crudas:
        if not isinstance(cruda, dict):
            errores.append(
                _error(fichero, "una relación no es un mapa", objeto=nombre)
            )
            continue
        errores.extend(
            _error(fichero, detalle, objeto=nombre)
            for detalle in _claves_desconocidas(
                cruda, CLAVES_RELACION, f"una relación de `{nombre}`"
            )
        )
        relaciones.append(
            Relacion(
                de=_texto(cruda.get("de")),
                a=_texto(cruda.get("a")),
                cardinalidad=_texto(cruda.get("cardinalidad")),
                porque=_texto(cruda.get("porque")),
            )
        )
    return tuple(relaciones)
