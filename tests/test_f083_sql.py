# tests/test_f083_sql.py
"""
F-083 · El estado de la FACTURA y sus dos fechas, comprobados sobre el TEXTO.

`sql/compras/01_documentos.sql` construye tablas en un Postgres **compartido
con produccion**, asi que aqui no se ejecuta: se lee. Mismo criterio que
`tests/test_f073_sql.py` y `tests/test_f080_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, y es lo unico que puede romper algo:
`compras.facturas` **ya existe y la consume Negocio** (Power BI y el MCP). Las
seis columnas nuevas se anaden; las diez de siempre no se tocan, no se
renombran y no cambian de sitio. Y la traduccion del estado va por la **pareja
`(tipo de documento, estado)`**: el mismo `estado_id` significa cosas distintas
en una obra (42), un contrato (44) o una factura (15), asi que unir solo por
`estado_id` traduce con el diccionario equivocado. La guarda de grano es un
`LEFT JOIN LATERAL ... LIMIT 1`: hoy `(tip, est)` es unico —21 de 21 medido el
2026-09-16— y la tabla no puede depender de que siga siendolo.

LAS TRES FECHAS QUE SE CONFUNDEN: `fecha` (la de siempre, que es la de ALTA en
Sigrid y se conserva por compatibilidad), `fecha_alta` (la misma, con nombre
inequivoco) y `fecha_factura` (`dcf.fecdoc`, la que el proveedor pone en su
documento). Se separan en el **77,8 %** de las facturas.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
)
RUTA_DOCUMENTOS = DIRECTORIO_SQL / "compras" / "01_documentos.sql"


@cache
def _sql() -> str:
    assert RUTA_DOCUMENTOS.exists(), f"SQL no encontrado: {RUTA_DOCUMENTOS}"
    return RUTA_DOCUMENTOS.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


@cache
def _bloque_facturas() -> str:
    """El texto ejecutable del bloque que construye `compras.facturas`.

    Acotado a proposito: `01_documentos.sql` construye ademas contratos,
    albaranes y las lineas de los tres, y un `in` sobre el fichero entero daria
    verde por una coincidencia en el bloque de al lado.
    """
    texto = _sql()
    inicio = texto.index("DROP TABLE IF EXISTS compras.facturas")
    fin = texto.index("ALTER TABLE compras.facturas ADD PRIMARY KEY")
    return _compacto(texto[inicio:fin])


def _columnas_publicadas() -> list[str]:
    """Los alias `AS <columna>` del SELECT de `compras.facturas`, en orden."""
    return re.findall(r"\bAS ([a-z_]+)\b", _bloque_facturas())


#: Las diez columnas que `compras.facturas` publica desde F-067, EN SU ORDEN.
#: Ninguna puede desaparecer, renombrarse ni cambiar de posicion (criterio 3).
COLUMNAS_DE_SIEMPRE = (
    "factura_id",
    "codigo_factura",
    "serie",
    "tipo_documento",
    "descripcion",
    "fecha",
    "proveedor_id",
    "proveedor_nombre",
    "proveedor_cif",
    "referencia_proveedor",
)

#: Lo que anade F-083, y va DETRAS de las diez de siempre.
COLUMNAS_NUEVAS = (
    "estado_id",
    "estado_codigo",
    "estado",
    "fecha_factura",
    "fecha_alta",
)


# ===========================================================================
# Criterio 3 · el grano y las columnas de siempre, intactos
# ===========================================================================


@pytest.mark.parametrize("columna", COLUMNAS_DE_SIEMPRE)
def test_f083_ninguna_columna_de_siempre_desaparece(columna: str) -> None:
    assert columna in _columnas_publicadas(), (
        f"`compras.facturas` dejaria de publicar `{columna}`: la consumen Power "
        "BI y el MCP, y el criterio 3 prohibe que ninguna columna actual "
        "desaparezca ni se renombre"
    )


def test_f083_las_columnas_de_siempre_van_primero_y_en_su_orden() -> None:
    """Las nuevas se anaden AL FINAL, no intercaladas.

    `compras.facturas` es una tabla, no una vista, asi que PostgreSQL no lo
    impide: lo impide el consumidor. Intercalar `estado` entre `tipo_documento`
    y `descripcion` —que es donde se lee mejor— reordena las columnas de una
    tabla que ya esta en produccion.
    """
    publicadas = _columnas_publicadas()
    assert tuple(publicadas[: len(COLUMNAS_DE_SIEMPRE)]) == COLUMNAS_DE_SIEMPRE, (
        "las diez columnas de siempre tienen que seguir siendo las diez "
        f"primeras y en su orden; hoy son {publicadas[:10]}"
    )


def test_f083_la_columna_fecha_conserva_su_expresion_de_siempre() -> None:
    """`fecha` sigue siendo la de ALTA (`con.fec`), ni una cosa ni otra.

    Reapuntarla a `dcf.fecdoc` seria cambiar en silencio el significado de una
    columna viva: los informes seguirian funcionando y darian otra fecha.
    """
    assert "compras.fn_sigrid_date(con.fec) AS fecha," in _bloque_facturas(), (
        "`fecha` tiene que seguir saliendo de `con.fec`: se conserva por "
        "compatibilidad y su significado no cambia (criterio 3)"
    )


def test_f083_el_universo_de_facturas_no_se_filtra() -> None:
    """Ni un WHERE en la consulta EXTERNA: las 165.866 facturas siguen estando.

    Publicar el estado no puede dejar fuera a las facturas cuyo estado no case
    con el catalogo (criterio 4: se publican igual). El `WHERE` que acota el
    catalogo dentro del `LATERAL` no cuenta: ese filtra el catalogo, no las
    facturas, y por eso el texto se corta justo antes de el.
    """
    bloque = _bloque_facturas()
    desde_el_from = bloque.split("FROM raw.dcf f")[1].split("LEFT JOIN LATERAL")[0]
    assert " WHERE " not in desde_el_from, (
        "ha aparecido un WHERE en el FROM de `compras.facturas`: eso cambia el "
        "grano, que es justo lo que el criterio 3 prohibe"
    )


# ===========================================================================
# Criterios 1 y 2 · el estado, traducido por la PAREJA (tipo, estado)
# ===========================================================================


@pytest.mark.parametrize("columna", ("estado_id", "estado_codigo", "estado"))
def test_f083_publica_el_estado_de_la_factura(columna: str) -> None:
    assert columna in _columnas_publicadas(), (
        f"`compras.facturas` no publica `{columna}`: sin el estado, "
        "Administracion no puede ver por donde va el circuito de aprobacion "
        "(criterio 1)"
    )


def test_f083_el_estado_id_se_lee_de_la_superclase_con() -> None:
    """No esta en `dcf`: esta en `con.est`. Es la leccion de F-080."""
    assert "con.est AS estado_id" in _bloque_facturas(), (
        "`estado_id` tiene que leerse de `con.est`, la superclase de "
        "documentos, y no de `dcf` (criterio 1)"
    )


def test_f083_la_traduccion_filtra_el_tipo_de_documento_de_factura() -> None:
    """Sin `tip = 15` traduciria con el diccionario de obras o de contratos.

    **Reescrito por F-084 (2026-09-16), y solo donde mira, no lo que exige.**
    El `WHERE` de la traduccion ya no esta aqui: vive una sola vez en
    `compras.fn_estado_documento`, y lo que este bloque escribe es el TIPO con
    el que la llama. Que es exactamente donde se puede equivocar —el cuerpo de
    la funcion no sabe de facturas—, asi que la comprobacion no pierde nada al
    mudarse a la llamada. La guarda del propio `WHERE` la vigila
    `tests/test_f084_sql.py`.
    """
    lateral = _lateral_del_estado()
    assert re.search(r"fn_estado_documento\(15, ?con\.est\)", lateral), (
        "la traduccion del estado no se pide para `tip = 15`: el mismo "
        "`estado_id` significa otra cosa en una obra (42) o en un contrato "
        f"(44), y hoy la llamada es «{lateral.strip()}» (criterio 2)"
    )


def test_f083_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id() -> None:
    """El test que el criterio 2 pide por su nombre.

    Falla si alguien deja la union solo por `est`, que es exactamente el
    refactor «simplificador» que rompe la traduccion sin romper el build.

    **F-084 lo hizo MAS dificil de romper, no menos.** La union vive ahora en
    `compras.fn_estado_documento(p_tip, p_est)`, cuya firma **obliga** a pasar
    el tipo: una llamada sin el no compila, asi que la mitad de la pareja que
    mas se olvidaba dejo de poderse olvidar. Este test comprueba las dos
    piezas: que el cuerpo sigue uniendo por los dos campos, y que la factura
    sigue llamando con su tipo. La comprobacion del cuerpo esta duplicada a
    proposito con `tests/test_f084_sql.py`: el dia que se borre una de las dos
    features, la otra sigue guardando la traduccion que comparten.
    """
    cuerpo = _cuerpo_de_la_funcion_de_estado()
    condicion = cuerpo.split(" WHERE ")[1].split(" ORDER BY ")[0]
    assert re.search(r"\.tip = p_tip\b", condicion) and re.search(
        r"\.est = p_est\b", condicion
    ), (
        "la union al catalogo tiene que ir por la PAREJA (tipo, estado): "
        f"hoy la condicion es «{condicion.strip()}»"
    )
    assert " AND " in condicion, (
        "una sola condicion en el WHERE del lateral significa que se esta "
        "uniendo solo por `estado_id`, que es lo que el criterio 2 prohibe"
    )
    assert "fn_estado_documento(15," in _bloque_facturas(), (
        "`compras.facturas` tiene que seguir pidiendo la traduccion con su "
        "tipo de documento: sin el 15, la pareja se queda coja en la llamada"
    )


def test_f083_la_traduccion_del_estado_no_puede_multiplicar_filas() -> None:
    """La guarda anti-multiplicacion del criterio 3.

    Hoy `(tip, est)` es unico —21 de 21 en el tipo 15, y ni un par repetido en
    las 193 filas del catalogo—, pero una tabla que ya consume Negocio no puede
    depender de un dato de origen que nadie controla. El patron es el de F-073.

    **F-084 movio la guarda al cuerpo de la funcion compartida**, que es la
    ganancia de haberla factorizado: se escribe una vez y protege tanto a
    `compras.facturas` como a `compras.contratos`.
    """
    cuerpo = _cuerpo_de_la_funcion_de_estado()
    assert "LIMIT 1" in cuerpo, (
        "sin `LIMIT 1`, el dia en que el catalogo traiga dos filas para el "
        "mismo `(15, est)` `compras.facturas` duplica facturas en silencio"
    )
    assert "ORDER BY" in cuerpo, (
        "`LIMIT 1` sin `ORDER BY` elige una fila al azar: el literal "
        "publicado cambiaria de una noche a otra sin que nadie lo note"
    )


def test_f083_el_lateral_del_estado_es_left_y_no_pierde_facturas() -> None:
    bloque = _bloque_facturas()
    assert "LEFT JOIN LATERAL" in bloque, (
        "con `JOIN LATERAL` se perderian las facturas cuyo estado no case con "
        "el catalogo, y el criterio 4 dice que se publican igual"
    )
    assert re.search(
        r"LEFT JOIN LATERAL compras\.fn_estado_documento\([^)]*\) \w+ ON TRUE",
        bloque,
    ), (
        "el lateral tiene que cerrarse con `ON TRUE`, como en `maestro.obras`: "
        "sin el, una factura sin estado en catalogo no se publicaria"
    )


def _lateral_del_estado() -> str:
    """La llamada a la traduccion del estado dentro del bloque, acotada.

    Hasta F-084 esto devolvia el subselect entero, escrito a mano aqui. Hoy
    devuelve el `LEFT JOIN LATERAL compras.fn_estado_documento(15, con.est) est
    ON TRUE`: el mismo sitio del fichero, con el cuerpo mudado a `00_setup.sql`.
    """
    bloque = _bloque_facturas()
    assert "LEFT JOIN LATERAL" in bloque, (
        "`compras.facturas` no traduce el estado con un lateral: sin el no hay "
        "guarda de grano (criterio 3)"
    )
    inicio = bloque.index("LEFT JOIN LATERAL")
    return bloque[inicio : bloque.index("ON TRUE", inicio)]


def _cuerpo_de_la_funcion_de_estado() -> str:
    """El cuerpo de `compras.fn_estado_documento`, en `compras/00_setup.sql`.

    Donde F-084 dejo la traduccion que F-083 tenia copiada en el bloque
    FACTURAS. Este fichero la sigue vigilando: los dos tests que la miran son
    de F-083 porque son SUS garantias, aunque el texto viva ahora en otro sitio.
    """
    ruta = DIRECTORIO_SQL / "compras" / "00_setup.sql"
    texto = _sin_comentarios(ruta.read_text(encoding="utf-8"))
    marca = "CREATE OR REPLACE FUNCTION compras.fn_estado_documento"
    assert marca in texto, (
        "`compras.fn_estado_documento` no esta definida: `compras.facturas` la "
        "necesita para traducir su estado desde F-084 (criterio 3 de F-083)"
    )
    inicio = texto.index(marca)
    return re.sub(r"\s+", " ", texto[inicio : texto.index("$$;", inicio)])


# ===========================================================================
# Ampliacion del humano · las dos fechas, separadas
# ===========================================================================


def test_f083_publica_la_fecha_de_la_propia_factura() -> None:
    assert "compras.fn_sigrid_date(f.fecdoc) AS fecha_factura" in _bloque_facturas(), (
        "`fecha_factura` es la fecha que el proveedor pone en su documento y "
        "sale de `dcf.fecdoc`, informada en el 99,95 % de las facturas"
    )


def test_f083_publica_la_fecha_de_alta_con_nombre_inequivoco() -> None:
    assert "compras.fn_sigrid_date(con.fec) AS fecha_alta" in _bloque_facturas(), (
        "`fecha_alta` es la fecha de alta del documento en Sigrid (`con.fec`), "
        "la misma que `fecha` pero con un nombre que no se confunde"
    )


def test_f083_las_dos_fechas_nuevas_salen_de_campos_distintos() -> None:
    """Si las dos apuntaran al mismo campo, separarlas no habria servido de nada.

    Se separan en 129.012 de 165.783 facturas (77,8 %), con una mediana de
    cuatro dias y un p95 de 42: no son la misma fecha con dos nombres.
    """
    bloque = _bloque_facturas()
    assert "f.fecdoc" in bloque and "con.fec)" in bloque, (
        "las dos fechas tienen que leer de dos campos distintos: `dcf.fecdoc` "
        "la del documento y `con.fec` la de alta"
    )


# ===========================================================================
# La cabecera del fichero avisa de la confusion que origino la feature
# ===========================================================================


def test_f083_la_cabecera_avisa_de_que_el_estado_no_es_el_del_efecto() -> None:
    """El correo de Administracion denuncia exactamente esta confusion."""
    cabecera = _sql()[: _sql().index("DROP TABLE IF EXISTS compras.contratos")]
    plano = re.sub(r"\s+", " ", cabecera).lower()
    assert "vencimientos" in plano and "efecto" in plano, (
        "la cabecera de `01_documentos.sql` tiene que decir que el estado de "
        "la factura NO es el `estado_pago` del efecto de `compras.vencimientos`"
    )
