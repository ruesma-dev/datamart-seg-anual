# tests/test_f006_fichas.py
"""
F-006 · Que las fichas no mientan: contraste contra el SQL que crea el objeto.

Este fichero existe por una sola razón. **Una ficha que miente es peor que una
ficha que falta**: la que falta produce un «no lo sé», y la que miente produce
un `SELECT` con un nombre de columna inventado, o peor, con una columna que
existe pero significa otra cosa. El agente no tiene forma de saberlo.

La puerta de cobertura (`test_f006_cobertura.py`) comprueba que cada objeto
publicado TIENE ficha. Esta comprueba que la ficha DICE LA VERDAD sobre sus
columnas, contrastándola con el DDL real. Son cosas distintas y las dos hacen
falta.

Alcance y honestidad sobre él:

* Para las **tablas** con `CREATE TABLE (...)` explícito la comprobación es
  exacta en los dos sentidos: ni una columna de menos ni una de más.
* Para las **vistas** también, desde la review de los bloques A-D: se lee la
  proyección del `SELECT` final de esa vista concreta, sin comentarios. Antes se
  buscaba el nombre en el fichero entero, y eso dejaba pasar una columna de otra
  vista del mismo fichero y no se enteraba de una columna omitida.
* Lo que sigue sin cubrirse: un objeto que exista en la base y no en el
  repositorio. Eso lo dirá `python main.py check-diccionario` contra
  `information_schema` (R28), que **está sin implementar** y llega en el bloque
  H. No se da por cubierto lo que no lo está.

Ningún test de este fichero abre red ni BBDD.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: Columnas de instrumentación del ETL: se documentan, pero el MCP las oculta.
TECNICAS = ("_built_at", "_ingested_at", "_source_tiemod")


@lru_cache(maxsize=1)
def _diccionario():
    """El diccionario real, cacheado.

    Se cachea porque este fichero lo pide en cada uno de sus ~160 tests y
    releerlo 160 veces son 49 ficheros YAML por vuelta: la suite pasó de 50 s a
    seis minutos al entrar `compras` y `retenciones`. Es de solo lectura y las
    entidades son inmutables, así que compartir la instancia no acopla nada.
    """
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _fichas_de(esquema: str) -> dict:
    return {
        f.objeto: f for f in _diccionario().fichas if f.esquema == esquema
    }


def _texto_sql(*rutas: str) -> str:
    return "\n".join((DIR_SQL / ruta).read_text(encoding="utf-8") for ruta in rutas)


def columnas_del_create_table(texto: str, nombre_cualificado: str) -> list[str]:
    """Nombres de columna de un `CREATE TABLE <esq>.<obj> ( ... );` explícito.

    Parser deliberadamente tonto: recorre el paréntesis del `CREATE TABLE` con
    un contador de profundidad —para no cortar dentro de un `NUMERIC(18,2)` ni
    de un `CHECK (...)`— y se queda con el primer identificador de cada
    definición de nivel 1 que no sea una restricción.
    """
    # Los comentarios se quitan ANTES de contar paréntesis y comas: el DDL real
    # tiene líneas como `unidad_medida VARCHAR(16), -- m3, m2, ud (de unimed)`,
    # cuya coma partiría la definición en dos y cuyo paréntesis descuadraría el
    # contador. Este fallo se dio de verdad al escribir la ficha de `mart`.
    texto = re.sub(r"--[^\n]*", " ", texto)

    patron = re.compile(
        rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{re.escape(nombre_cualificado)}\s*\(",
        re.IGNORECASE,
    )
    coincidencia = patron.search(texto)
    assert coincidencia, f"no se encontró el CREATE TABLE de {nombre_cualificado}"

    inicio = coincidencia.end()
    profundidad = 1
    fin = inicio
    while profundidad:
        caracter = texto[fin]
        profundidad += (caracter == "(") - (caracter == ")")
        fin += 1
    cuerpo = texto[inicio : fin - 1]

    definiciones: list[str] = []
    actual: list[str] = []
    profundidad = 0
    for caracter in cuerpo:
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        if caracter == "," and profundidad == 0:
            definiciones.append("".join(actual))
            actual = []
        else:
            actual.append(caracter)
    definiciones.append("".join(actual))

    restricciones = ("constraint", "primary", "unique", "foreign", "check", "exclude")
    columnas = []
    for definicion in definiciones:
        # Un comentario `-- ...` puede ir al final de la línea anterior.
        limpia = re.sub(r"--[^\n]*", " ", definicion).strip()
        if not limpia:
            continue
        primera = limpia.split()[0].strip('"')
        if primera.lower() in restricciones:
            continue
        columnas.append(primera)
    return columnas


# ---------------------------------------------------------------------------
# El parser, probado sobre un caso conocido antes de fiarse de él
# ---------------------------------------------------------------------------


def test_f006_r26_el_parser_de_ddl_no_se_corta_dentro_de_un_numeric() -> None:
    """Si el parser fuese malo, todos los tests de abajo pasarían en falso."""
    ddl = """
    CREATE TABLE mart.ejemplo (
        id          BIGSERIAL     PRIMARY KEY,
        importe     NUMERIC(18,2) NOT NULL,   -- con coma dentro
        etiqueta    VARCHAR(32),
        CONSTRAINT chk_algo CHECK (importe > 0 AND id <> 0)
    );
    """

    assert columnas_del_create_table(ddl, "mart.ejemplo") == [
        "id",
        "importe",
        "etiqueta",
    ]


# ---------------------------------------------------------------------------
# `mart` · las dos tablas de hecho (T12)
# ---------------------------------------------------------------------------

TABLAS_MART = {
    "fact_seguimiento_mensual": "mart/01_ddl.sql",
    "fact_seguimiento_categoria": "mart/03_agg_categoria.sql",
}


@pytest.mark.parametrize(("objeto", "fichero"), sorted(TABLAS_MART.items()))
def test_f006_r26_mart_las_tablas_documentan_exactamente_sus_columnas(
    objeto: str, fichero: str
) -> None:
    """Ni una columna de menos (habría un hueco) ni una de más (sería humo)."""
    ficha = _fichas_de("mart")[objeto]
    reales = columnas_del_create_table(_texto_sql(fichero), f"mart.{objeto}")

    documentadas = [c.nombre for c in ficha.columnas]

    assert set(documentadas) == set(reales), (
        f"faltan: {sorted(set(reales) - set(documentadas))}; "
        f"sobran: {sorted(set(documentadas) - set(reales))}"
    )


@pytest.mark.parametrize(("objeto", "fichero"), sorted(TABLAS_MART.items()))
def test_f006_r2_mart_la_clave_de_negocio_es_el_grano_declarado(
    objeto: str, fichero: str
) -> None:
    """La clave de negocio tiene que existir de verdad en la tabla."""
    ficha = _fichas_de("mart")[objeto]
    reales = set(columnas_del_create_table(_texto_sql(fichero), f"mart.{objeto}"))

    assert ficha.clave_negocio
    assert set(ficha.clave_negocio) <= reales


def test_f006_r7_mart_importe_origen_no_se_declara_sumable() -> None:
    """Es la trampa número uno del datamart, y se codifica en la propia ficha.

    `importe_mes` es `suma_solo_dentro_del_mes` e `importe_origen` es
    `ultimo_valor`: el MCP lo traduce a «esta columna no se suma en el tiempo».
    """
    for objeto in TABLAS_MART:
        columnas = {c.nombre: c for c in _fichas_de("mart")[objeto].columnas}

        assert columnas["importe_mes"].agregacion == "suma_solo_dentro_del_mes"
        assert columnas["importe_origen"].agregacion == "ultimo_valor"
        assert columnas["importe_mes"].unidad == "EUR"


def test_f006_r7_mart_las_claves_sustitutas_estan_marcadas() -> None:
    """`fact_id` y `fact_cat_id` son BIGSERIAL y cambian en cada build."""
    mensual = {c.nombre: c for c in _fichas_de("mart")["fact_seguimiento_mensual"].columnas}
    categoria = {
        c.nombre: c for c in _fichas_de("mart")["fact_seguimiento_categoria"].columnas
    }

    assert mensual["fact_id"].agregacion == "clave_sustituta"
    assert categoria["fact_cat_id"].agregacion == "clave_sustituta"


def test_f006_r12_mart_las_tablas_de_hecho_heredan_sus_avisos() -> None:
    """Quien solo mire la ficha tiene que ver las trampas del objeto."""
    from etl_sigrid.domain.diccionario import derivar_avisos

    derivado = derivar_avisos(_diccionario())

    for objeto in TABLAS_MART:
        avisos = derivado.por_nombre[f"mart.{objeto}"].avisos
        assert "R-IMPORTE-MES" in avisos, objeto
        assert "R-CLAVE-SUSTITUTA" in avisos, objeto


def test_f006_r7_mart_el_escenario_declara_sus_cuatro_valores() -> None:
    """El agente va a escribir `WHERE escenario = '...'`: los literales exactos."""
    for objeto in TABLAS_MART:
        columnas = {c.nombre: c for c in _fichas_de("mart")[objeto].columnas}

        assert set(columnas["escenario"].valores) == {
            "Coste Real",
            "Coste Planificado",
            "Venta Real",
            "Venta Planificada",
        }, objeto


# ---------------------------------------------------------------------------
# Todas las fichas · ninguna columna inventada
#
# Comprobación más débil que la de las tablas, y el docstring del módulo lo
# dice: para una vista haría falta un parser de SQL. Se limita a exigir que
# cada nombre de columna documentado aparezca como palabra en el fichero que
# crea el objeto. Caza los nombres inventados y las erratas —el 90 % de los
# casos— y no caza un alias mal atribuido. Para eso está `check-diccionario`.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _origen_por_objeto() -> dict[str, str]:
    """Qué fichero crea cada objeto. Cacheado por el mismo motivo: recorre el
    árbol SQL entero y lo piden decenas de tests parametrizados."""
    from tests.test_f006_cobertura import _inventario_del_repositorio

    return {o.nombre: o.origen for o in _inventario_del_repositorio()}


def _fichas_con_columnas() -> list:
    return [f for f in _diccionario().fichas if f.columnas]


def test_f006_r26_toda_ficha_con_columnas_la_cubre_una_comprobacion_exacta() -> None:
    """Meta-test: ninguna ficha con columnas se queda sin contrastar.

    Hasta la review existía aquí un contraste genérico y débil —que el nombre
    apareciera en algún sitio del fichero SQL— que daba falsa confianza: dejaba
    pasar columnas ajenas y columnas omitidas. Se retiró al hacer exacta la
    comprobación de las vistas. Este test es lo que impide que el hueco vuelva
    por la puerta de atrás: si mañana aparece una ficha con columnas que no sea
    ni tabla ni vista, aquí se ve.
    """
    sin_cubrir = [
        f.nombre
        for f in _fichas_con_columnas()
        if f.tipo not in ("tabla", "vista")
    ]

    assert not sin_cubrir, f"{sin_cubrir} tienen columnas y nadie las contrasta"
    assert len(_fichas_con_columnas()) >= 22


@pytest.mark.parametrize(
    "nombre", sorted(f.nombre for f in _fichas_con_columnas())
)
def test_f006_r26_las_columnas_tecnicas_no_se_declaran_de_negocio(nombre: str) -> None:
    """Si se documentan (y se documentan, para que la ficha esté completa), al
    menos que no se ofrezcan como cifra sumable."""
    ficha = _diccionario().por_nombre[nombre]

    for columna in ficha.columnas:
        if columna.nombre in TECNICAS:
            assert columna.agregacion == "no_sumable", f"{nombre}.{columna.nombre}"


# ---------------------------------------------------------------------------
# `cierre` · el esquema que NO se refresca de noche (T14)
# ---------------------------------------------------------------------------


def test_f006_r14_cierre_entero_se_declara_de_refresco_manual() -> None:
    """`cierre` no está en `build_pipeline_steps`: se construye a mano.

    Que una sola ficha de este esquema se declarase `nocturno` bastaría para que
    el agente diera un dato de hace semanas sin advertirlo.
    """
    fichas = _fichas_de("cierre")

    assert fichas, "no hay fichas de `cierre`"
    for nombre, ficha in fichas.items():
        assert ficha.refresco == "manual", nombre
        assert ficha.paso_etl == "build_cierre", nombre


def test_f006_r12_cierre_hereda_el_aviso_de_frescura() -> None:
    """Quien mire una ficha de `cierre` tiene que ver que hay que citar la fecha."""
    from etl_sigrid.domain.diccionario import derivar_avisos

    derivado = derivar_avisos(_diccionario())

    for nombre in _fichas_de("cierre"):
        avisos = derivado.por_nombre[f"cierre.{nombre}"].avisos
        assert "R-FRESCURA-MANUAL" in avisos, nombre


def test_f006_r26_cierre_la_tabla_de_hecho_documenta_sus_columnas() -> None:
    ficha = _fichas_de("cierre")["fact_cierre_mensual"]
    reales = columnas_del_create_table(
        _texto_sql("cierre/01_ddl_fact.sql"), "cierre.fact_cierre_mensual"
    )

    assert {c.nombre for c in ficha.columnas} == set(reales), (
        f"faltan: {sorted(set(reales) - {c.nombre for c in ficha.columnas})}; "
        f"sobran: {sorted({c.nombre for c in ficha.columnas} - set(reales))}"
    )


def test_f006_r2_cierre_las_tres_funciones_estan_documentadas() -> None:
    """Son las que deciden a qué mes pertenece un cierre, y la regla es
    contraintuitiva: si el texto y la fecha discrepan, manda el TEXTO."""
    funciones = {
        n: f for n, f in _fichas_de("cierre").items() if f.tipo == "funcion"
    }

    assert set(funciones) == {
        "fn_parse_mes_fase",
        "fn_mes_de_fase",
        "fn_mes_de_version_master",
    }
    for nombre, ficha in funciones.items():
        assert ficha.grano is None or ficha.grano == "", nombre
        assert ficha.motivo_no_consumo, nombre


# ---------------------------------------------------------------------------
# `orden_concepto`: el rango declarado tiene que ser el real (defecto 3)
#
# La ficha decia «(1 a 6)». Los valores reales son {1, 2, 2, 3, 4, 6}: el 2 esta
# DUPLICADO (INDIRECTOS lo hereda del fact y GASTOS lo recibe en la vista) y el
# 5 no existe. Un `ORDER BY orden_concepto` deja dos conceptos empatados en
# orden indefinido, que es la clase de fallo que nadie mira dos veces.
# ---------------------------------------------------------------------------


def _valores_orden(objeto: str, columna: str) -> list[str]:
    return list(
        {c.nombre: c for c in _fichas_de("cierre")[objeto].columnas}[columna].valores
    )


def test_f006_r7_cierre_el_orden_del_resumen_declara_sus_valores_reales() -> None:
    assert _valores_orden("v_pbi_cierre_resumen", "orden_concepto") == [
        "1",
        "2",
        "3",
        "4",
        "6",
    ]


def test_f006_r7_cierre_el_orden_del_resumen_avisa_del_empate() -> None:
    """No basta con listar los valores: hay que decir que el 2 se repite y por
    dónde se ordena de verdad."""
    columnas = {c.nombre: c for c in _fichas_de("cierre")["v_pbi_cierre_resumen"].columnas}

    significado = columnas["orden_concepto"].significado

    assert "2" in significado
    assert "v_pbi_dim_concepto" in significado, (
        "la ficha tiene que mandar ordenar por el dim, que sí es 1..6 sin huecos"
    )


def test_f006_r7_cierre_el_orden_de_la_tabla_base_solo_llega_a_cuatro() -> None:
    """`fact_cierre_mensual` solo tiene los cuatro conceptos base."""
    columnas = {c.nombre: c for c in _fichas_de("cierre")["fact_cierre_mensual"].columnas}

    assert list(columnas["orden_concepto"].valores) == ["1", "2", "3", "4"]


def test_f006_r7_cierre_el_dim_de_concepto_si_ordena_de_uno_a_seis() -> None:
    columnas = {c.nombre: c for c in _fichas_de("cierre")["v_pbi_dim_concepto"].columnas}

    assert list(columnas["orden"].valores) == ["1", "2", "3", "4", "5", "6"]


# ---------------------------------------------------------------------------
# `nulo_significa` en columnas `*_ide` (defecto 5)
#
# `cliente_ide` decia «la obra no tiene cliente asignado» y NUNCA es NULL: es el
# unico `*_ide` de la vista que se proyecta sin `NULLIF(..., 0)`, asi que las
# obras sin cliente traen **0** y un `WHERE cliente_ide IS NULL` no devuelve
# nada. Es comprobable, y por eso se comprueba: declarar un nulo que no existe
# manda al agente a escribir un filtro que siempre sale vacio.
# ---------------------------------------------------------------------------


def _proyeccion_de(sql: str, columna: str) -> str | None:
    """La línea del `SELECT` que crea ese alias, sin comentarios."""
    for linea in re.sub(r"--[^\n]*", " ", sql).split("\n"):
        if re.search(rf"\bAS\s+{re.escape(columna)}\s*,?\s*$", linea, re.IGNORECASE):
            return linea
    return None


@pytest.mark.parametrize(
    "nombre", sorted(f.nombre for f in _fichas_con_columnas() if f.tipo == "vista")
)
def test_f006_r2_un_nulo_declarado_en_un_ide_tiene_que_ser_posible(nombre: str) -> None:
    ficha = _diccionario().por_nombre[nombre]
    origen = _origen_por_objeto()[nombre]
    sql = (DIR_SQL / origen).read_text(encoding="utf-8")

    for columna in ficha.columnas:
        if not columna.nombre.endswith("_ide") or not columna.nulo_significa:
            continue
        proyeccion = _proyeccion_de(sql, columna.nombre)
        if proyeccion is None:
            continue
        assert "NULLIF" in proyeccion.upper(), (
            f"{nombre}.{columna.nombre} declara `nulo_significa` pero se proyecta "
            f"sin NULLIF, así que trae 0 y nunca es NULL: {proyeccion.strip()}"
        )


def test_f006_r2_cliente_ide_avisa_de_que_el_cero_es_el_sin_cliente() -> None:
    """No basta con quitar el `nulo_significa` falso: hay que decir qué hacer."""
    columnas = {
        c.nombre: c for c in _fichas_de("cierre")["v_pbi_cierre_cabecera"].columnas
    }

    cliente = columnas["cliente_ide"]

    assert cliente.nulo_significa is None
    assert "0" in cliente.significado
    assert "NULL" in cliente.significado.upper()


# ---------------------------------------------------------------------------
# El ejemplo de `design.md` §3.3 es el contrato (defecto 9)
#
# Es lo que copiara quien escriba `compras.yaml`, `retenciones.yaml` y las 73
# fichas que faltan. Que las fichas de este bloque esten bien no evita que el
# error se propague desde el documento.
# ---------------------------------------------------------------------------

DESIGN = RAIZ / "specs" / "F-006-mcp-azure" / "design.md"


def _yaml_del_contrato() -> str:
    """Solo los bloques YAML de `design.md`, no la prosa.

    La comprobación se acota al ejemplo porque es lo que se copia; la prosa
    puede (y debe) citar los nombres equivocados para explicar la enmienda.
    """
    texto = DESIGN.read_text(encoding="utf-8")
    bloques = texto.split("```")
    return chr(10).join(b for i, b in enumerate(bloques) if i % 2 == 1)


@pytest.mark.parametrize(
    "inventado",
    ["obra_codigo", "partida_codigo", "COSTE_REAL", "VENTA_PLAN", "COSTE_PLAN"],
)
def test_f006_r2_el_ejemplo_del_contrato_no_usa_nombres_que_no_existen(
    inventado: str,
) -> None:
    texto = _yaml_del_contrato()

    assert inventado not in texto, (
        f"`{inventado}` no existe en el SQL y el ejemplo del contrato lo usa"
    )


def test_f006_r2_el_ejemplo_del_contrato_usa_los_nombres_reales() -> None:
    texto = _yaml_del_contrato()

    for real in ("codigo_obra", "codigo_partida", "anio_mes", "Coste Real"):
        assert real in texto, f"el ejemplo del contrato no usa `{real}`"


def test_f006_r24_el_diseno_declara_el_recuento_real_de_objetos() -> None:
    """`design.md` estimaba «más de 80»; son 98, y el reparto por esquema
    tampoco coincidía."""
    from tests.test_f006_cobertura import _inventario_del_repositorio

    texto = DESIGN.read_text(encoding="utf-8")
    total = len(_inventario_del_repositorio())

    assert str(total) in texto, (
        f"el inventario real son {total} objetos y `design.md` no lo dice"
    )
    assert "más de 80 objetos" not in texto


# ---------------------------------------------------------------------------
# Defensas (b) y (c) de la puerta · las VISTAS, tan exactas como las tablas
#
# Dos huecos demostrados en la review, los dos sobre vistas:
#
#   * **Columna ajena que cuela.** El contraste buscaba `\b<nombre>\b` en el
#     TEXTO CRUDO DEL FICHERO ENTERO, comentarios incluidos. Documentar
#     `obra_label` —columna de `v_pbi_dim_obra`— dentro de la ficha de
#     `v_pbi_fact` pasaba en verde, porque las dos vistas viven en el mismo
#     fichero. Colaban hasta palabras que solo salen en un comentario.
#   * **Columna OMITIDA que no se nota.** Borrar `can_mes` de la ficha de
#     `v_pbi_fact` dejaba la suite en verde: para las vistas solo se exigía que
#     lo documentado apareciera, no que apareciera todo.
#
# Se cierran los dos leyendo la proyección final de CADA vista: su propio
# `CREATE VIEW`, sin comentarios, desde su último `SELECT` de nivel 0 hasta su
# `FROM`. Con eso la comprobación de las vistas es exacta en los dos sentidos,
# igual que la de las tablas, y ya no hace falta apelar a `check-diccionario`
# para esto.
# ---------------------------------------------------------------------------


def cuerpo_de_vista(sql: str, esquema: str, objeto: str) -> str | None:
    """El texto del `CREATE ... AS` de ESE objeto y solo de ese.

    Cubre las vistas y también las tablas creadas con `CREATE TABLE x AS
    SELECT`, que es como se construyen las siete de `compras` y las dos de
    `retenciones`: no tienen lista de columnas que parsear, tienen una
    proyección, exactamente igual que una vista.
    """
    patron = re.compile(
        rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?(?:VIEW|TABLE)\s+"
        rf"{re.escape(esquema)}\.{re.escape(objeto)}\s+AS",
        re.IGNORECASE,
    )
    coincidencia = patron.search(sql)
    if coincidencia is None:
        return None
    resto = sql[coincidencia.end() :]
    corte = re.search(r"^(CREATE|COMMENT|DROP|ALTER)\b", resto, re.MULTILINE)
    return resto[: corte.start()] if corte else resto


def columnas_proyectadas(cuerpo: str) -> list[str] | None:
    """Alias del `SELECT` final de una vista, o `None` si no se puede saber.

    Devolver `None` en vez de una lista a medias es deliberado: una lista
    incompleta convertiría la comprobación en un colador silencioso, que es
    justo el fallo que esto viene a arreglar. Si algún día una vista deja de
    parsearse, `test_..._todas_las_vistas_se_dejan_leer` se pone en rojo y
    obliga a mirar, en vez de dejar de comprobar sin avisar.
    """
    cuerpo = re.sub(r"--[^\n]*", " ", cuerpo)

    # Caso `SELECT * FROM (VALUES ...) AS t(a, b, c)`: los catálogos estáticos
    # declaran sus nombres al final y no en la proyección.
    alias_tupla = re.search(r"\)\s*AS\s+\w+\s*\(([^)]*)\)\s*;", cuerpo, re.IGNORECASE)
    if alias_tupla:
        return [c.strip() for c in alias_tupla.group(1).split(",") if c.strip()]

    lineas = cuerpo.split("\n")
    selects = [i for i, linea in enumerate(lineas) if re.match(r"^SELECT\b", linea)]
    if not selects:
        return None
    inicio = selects[-1]
    fin = next(
        (i for i in range(inicio + 1, len(lineas)) if re.match(r"^(FROM|;)\b", lineas[i])),
        None,
    )
    if fin is None:
        return None

    proyeccion = re.sub(
        r"^SELECT\s+(?:DISTINCT\s+(?:ON\s*\([^)]*\)\s*)?)?",
        "",
        "\n".join(lineas[inicio:fin]),
        flags=re.IGNORECASE,
    )

    items, actual, profundidad = [], [], 0
    for caracter in proyeccion:
        if caracter in "([":
            profundidad += 1
        elif caracter in ")]":
            profundidad -= 1
        if caracter == "," and profundidad == 0:
            items.append("".join(actual))
            actual = []
        else:
            actual.append(caracter)
    items.append("".join(actual))

    nombres: list[str] = []
    for item in items:
        item = " ".join(item.split())
        if not item:
            continue
        alias = re.search(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", item, re.IGNORECASE)
        if alias:
            nombres.append(alias.group(1))
            continue
        desnuda = re.match(
            r"^(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)$", item
        )
        if desnuda:
            nombres.append(desnuda.group(1))
            continue
        return None
    return nombres or None


def _vistas_del_diccionario() -> list:
    """Todo objeto que se crea con una PROYECCIÓN, sea vista o `TABLE AS`."""
    return [
        f
        for f in _diccionario().fichas
        if f.columnas and f.nombre not in TABLAS_CON_DDL_EXPLICITO
    ]


#: Objetos cuyo SQL declara la lista de columnas y se leen con el parser de DDL.
#: El resto se crea con `AS SELECT` y se lee de su proyección.
TABLAS_CON_DDL_EXPLICITO = {
    "mart.fact_seguimiento_mensual",
    "mart.fact_seguimiento_categoria",
    "cierre.fact_cierre_mensual",
}

#: La única excepción, y hay que decirla: `retenciones.v_src_lineas_compra` y
#: `v_src_lineas_venta` se crean con SQL DINÁMICO dentro de un `DO $$` —según
#: exista o no la tabla de origen en `raw`— así que su `SELECT` va dentro de una
#: cadena y ningún parser razonable lo alcanza. Sus dos columnas las comprueba
#: `test_f006_r26_las_vistas_dinamicas_de_retenciones`, escrito a mano.
CREADAS_CON_SQL_DINAMICO = {
    "retenciones.v_src_lineas_compra",
    "retenciones.v_src_lineas_venta",
}


def test_f006_r26_todos_los_objetos_con_proyeccion_se_dejan_leer() -> None:
    """Control: si la extracción dejara de funcionar, el test de abajo pasaría
    en falso sobre cero objetos."""
    ilegibles = []
    for ficha in _vistas_del_diccionario():
        if ficha.nombre in CREADAS_CON_SQL_DINAMICO:
            continue
        sql = (DIR_SQL / _origen_por_objeto()[ficha.nombre]).read_text(encoding="utf-8")
        cuerpo = cuerpo_de_vista(sql, ficha.esquema, ficha.objeto)
        if cuerpo is None or columnas_proyectadas(cuerpo) is None:
            ilegibles.append(ficha.nombre)

    assert not ilegibles, f"no se pudo leer la proyección de {ilegibles}"
    assert len(_vistas_del_diccionario()) >= 19


@pytest.mark.parametrize("nombre", sorted(f.nombre for f in _vistas_del_diccionario()))
def test_f006_r26_las_vistas_documentan_exactamente_su_proyeccion(nombre: str) -> None:
    """Ni una columna de menos (hueco) ni una de más (humo o columna ajena)."""
    if nombre in CREADAS_CON_SQL_DINAMICO:
        pytest.skip("se crea con SQL dinámico; tiene su propio test")

    ficha = _diccionario().por_nombre[nombre]
    sql = (DIR_SQL / _origen_por_objeto()[nombre]).read_text(encoding="utf-8")

    proyectadas = columnas_proyectadas(cuerpo_de_vista(sql, ficha.esquema, ficha.objeto))
    documentadas = [c.nombre for c in ficha.columnas]

    assert set(documentadas) == set(proyectadas), (
        f"faltan: {sorted(set(proyectadas) - set(documentadas))}; "
        f"sobran: {sorted(set(documentadas) - set(proyectadas))}"
    )


def test_f006_r26_las_vistas_dinamicas_de_retenciones() -> None:
    """Las dos que se crean dentro de un `EXECUTE`, comprobadas a mano.

    Las dos variantes que el SQL puede crear —la real y la vacía— proyectan las
    mismas dos columnas, y eso es justamente lo que hace que el resto del módulo
    funcione exista o no la tabla de origen.
    """
    fichas = _fichas_de("retenciones")
    if not fichas:
        pytest.skip("las fichas de `retenciones` llegan en el bloque F")

    sql = (DIR_SQL / "retenciones/00_setup.sql").read_text(encoding="utf-8")

    for objeto in ("v_src_lineas_compra", "v_src_lineas_venta"):
        documentadas = {c.nombre for c in fichas[objeto].columnas}
        assert documentadas == {"docide", "obride"}, objeto
        assert sql.count(f"CREATE VIEW retenciones.{objeto} AS") == 2, (
            "las dos variantes (con y sin tabla de origen) tienen que seguir ahí"
        )


def test_f006_r26_el_extractor_no_confunde_dos_vistas_del_mismo_fichero() -> None:
    """El hueco exacto: `obra_label` es de `v_pbi_dim_obra`, no de `v_pbi_fact`,
    y las dos viven en `05_views_powerbi.sql`."""
    sql = (DIR_SQL / "mart/05_views_powerbi.sql").read_text(encoding="utf-8")

    de_fact = columnas_proyectadas(cuerpo_de_vista(sql, "mart", "v_pbi_fact"))
    de_obra = columnas_proyectadas(cuerpo_de_vista(sql, "mart", "v_pbi_dim_obra"))

    assert "obra_label" in de_obra
    assert "obra_label" not in de_fact


def test_f006_r26_el_extractor_ignora_los_comentarios() -> None:
    """Colaban palabras que solo aparecían en un comentario del fichero."""
    sql = (DIR_SQL / "mart/05_views_powerbi.sql").read_text(encoding="utf-8")

    proyectadas = columnas_proyectadas(cuerpo_de_vista(sql, "mart", "v_pbi_dim_obra"))

    assert "segmentadores" not in proyectadas
    assert "estrella" not in proyectadas


# ---------------------------------------------------------------------------
# Hallazgos menores de la review · matices que el SQL contradice
#
# No bloqueaban, pero son texto que un agente lee para decidir, y estaban
# equivocados. Cada uno se comprobó contra el SQL antes de escribirlo.
# ---------------------------------------------------------------------------


def test_f006_r2_el_anterior_es_la_fila_anterior_no_el_mes_anterior() -> None:
    """`LAG` sobre (obra, concepto) ordenado por mes: salta los meses sin fila.

    «El mes anterior» invita a restar un mes de calendario, que es otra cosa.
    """
    fichas = _fichas_de("cierre")

    for objeto in ("fact_cierre_mensual", "v_pbi_cierre_resumen",
                   "v_pbi_cierre_indirectos_detalle",
                   "v_pbi_cierre_generales_detalle"):
        columnas = {c.nombre: c for c in fichas[objeto].columnas}
        for columna in ("ejecutado_anterior", "final_anterior"):
            if columna not in columnas:
                continue
            assert "fila anterior" in columnas[columna].significado.lower(), (
                f"{objeto}.{columna}"
            )


def test_f006_r2_final_anterior_es_cero_y_no_nulo_cuando_no_hubo_prevision() -> None:
    """`final_importe` es un `COALESCE(..., 0)`, así que su `LAG` es 0.

    Solo es NULL en la primera fila de la partición, que es la primera de esa
    obra y ese concepto. Decir «no había previsión el mes anterior» mandaba a
    filtrar por `IS NULL` y perder todas las filas con 0.
    """
    columnas = {
        c.nombre: c for c in _fichas_de("cierre")["fact_cierre_mensual"].columnas
    }

    nulo = columnas["final_anterior"].nulo_significa or ""

    assert "primera" in nulo.lower()
    assert "0" in columnas["final_anterior"].significado


def test_f006_r2_la_periodificacion_no_anula_todas_sus_columnas() -> None:
    """`importe_fase0` y `plazo_total_meses` traen valor también fuera de INFRA."""
    ficha = _fichas_de("cierre")["v_pbi_cierre_indirectos_detalle"]
    columnas = {c.nombre: c for c in ficha.columnas}

    assert columnas["importe_fase0"].nulo_significa
    assert "periodifica" not in (columnas["importe_fase0"].nulo_significa or "")
    assert "todas las columnas de periodificacion son nulas" not in ficha.grano
    assert "todas las columnas de periodificacion son nulas" not in (
        columnas["es_infraestructura"].significado
    )


def test_f006_r2_los_dos_plazos_se_advierten_entre_si() -> None:
    """`plazo_meses` de la cabecera y `plazo_total_meses` del detalle se
    calculan distinto y dan números distintos para la misma obra."""
    cabecera = {
        c.nombre: c for c in _fichas_de("cierre")["v_pbi_cierre_cabecera"].columnas
    }
    detalle = {
        c.nombre: c
        for c in _fichas_de("cierre")["v_pbi_cierre_indirectos_detalle"].columnas
    }

    assert "plazo_total_meses" in cabecera["plazo_meses"].significado
    assert "plazo_meses" in detalle["plazo_total_meses"].significado


def test_f006_r2_los_catalogos_estaticos_no_se_contradicen_con_su_refresco() -> None:
    """Se describían como «catálogo ESTATICO» declarando `refresco: manual`.

    Las dos cosas son ciertas y no se contradicen —el contenido está escrito en
    la vista, y la vista se recrea con `build-cierre`—, pero había que decirlo,
    porque leídas juntas parecen un error.
    """
    for objeto in ("v_pbi_dim_concepto", "v_pbi_dim_tipologia_cp"):
        ficha = _fichas_de("cierre")[objeto]

        assert ficha.refresco == "manual"
        assert "build-cierre" in ficha.descripcion, objeto


# ---------------------------------------------------------------------------
# `final_pct` no se autoincluye en su propia excepcion (arrastre 3)
#
# El texto decia que «en la fila VENTA los cinco porcentajes usan un divisor
# propio, la venta final», y `final_pct` es justo el que NO usa la venta final:
# usa `presupuesto_aprobado_venta`. Contarse a si mismo dentro del grupo del
# que se excluye deja al lector sin saber cual es su divisor.
#
# Los numeros reales, contra `sql/cierre/03_views.sql`: de las seis columnas de
# porcentaje, en la fila VENTA cuatro cambian su divisor a la venta final,
# `final_pct` lo cambia al presupuesto aprobado, y `variacion_pct` no tiene
# ninguna excepcion.
# ---------------------------------------------------------------------------


def test_f006_r2_final_pct_dice_cuantos_porcentajes_cambian_y_cuales() -> None:
    columnas = {
        c.nombre: c for c in _fichas_de("cierre")["v_pbi_cierre_resumen"].columnas
    }

    significado = columnas["final_pct"].significado

    assert "cinco porcentajes" not in significado
    assert "cuatro" in significado.lower(), (
        "hay que decir cuántos cambian de divisor de verdad"
    )
    assert "variacion_pct" in significado, (
        "y decir cuál no tiene ninguna excepción, que es la otra mitad del mapa"
    )


def test_f006_r2_variacion_pct_no_declara_una_excepcion_que_no_tiene() -> None:
    """Su divisor es `final_anterior` siempre, sin mirar el concepto.

    Mencionar la fila VENTA vale —y ayuda— mientras sea para decir que ahí NO
    pasa nada: es la duda que le queda a quien acaba de leer las otras cinco.
    """
    columnas = {
        c.nombre: c for c in _fichas_de("cierre")["v_pbi_cierre_resumen"].columnas
    }

    significado = columnas["variacion_pct"].significado

    if "VENTA" in significado:
        assert "NO cambia" in significado, (
            "si se nombra la fila VENTA, tiene que ser para decir que este "
            "porcentaje no tiene excepción"
        )
    assert "fila anterior" in significado.lower()


def test_f006_r2_el_sql_confirma_el_reparto_de_divisores() -> None:
    """Control: si el SQL cambiara, la ficha se quedaría mintiendo en silencio."""
    sql = (DIR_SQL / "cierre/03_views.sql").read_text(encoding="utf-8")
    cuerpo = cuerpo_de_vista(sql, "cierre", "v_pbi_cierre_resumen")

    con_excepcion_de_venta = cuerpo.count("WHEN t.concepto = 'VENTA' THEN")

    assert con_excepcion_de_venta == 5, (
        "cuatro porcentajes van a venta_final y uno al aprobado; variacion_pct "
        "no tiene excepción"
    )
    assert "a.aprobado_venta" in cuerpo


def test_f006_r2_no_queda_ningun_residuo_de_mes_anterior() -> None:
    """Arrastre 4: la comparación es contra la FILA anterior, siempre.

    Quedaban seis en `variacion_importe`, `ejecutado_anterior_pct` y
    `variacion_pct`. La frase «el mes anterior» invita a restar un mes de
    calendario, y el `LAG` que hay detrás salta los meses sin fase: en una obra
    que no cerró marzo, «el mes anterior» de abril es febrero.
    """
    import yaml as yaml_lib

    crudo = (DIR_DICCIONARIO / "cierre.yaml").read_text(encoding="utf-8")
    # La única mención legítima describe un comentario del SQL sobre el
    # incurrido, no una comparación entre filas de la propia vista.
    residuos = [
        linea.strip()
        for linea in crudo.split("\n")
        if "mes anterior" in linea and "INCURRIDO" not in linea
    ]

    assert not residuos, residuos
    assert yaml_lib.safe_load(crudo), "y el fichero sigue parseando"


# ---------------------------------------------------------------------------
# `compras` y `retenciones` · las trampas que el encargo exigía por escrito
#
# Estos dos esquemas sirven cuatro de los seis casos de uso del humano y son los
# que más trampas tienen. Cada una de ellas está aquí, contrastada contra el SQL
# que la origina, para que una reescritura bienintencionada no la diluya.
# ---------------------------------------------------------------------------


def _texto_de(nombre: str) -> str:
    """Todo lo que la ficha le dice al agente, en una sola cadena."""
    ficha = _diccionario().por_nombre[nombre]
    partes = [ficha.descripcion, ficha.grano or "", ficha.motivo_no_consumo or ""]
    partes += [c.significado for c in ficha.columnas]
    partes += [c.nulo_significa or "" for c in ficha.columnas]
    partes += [r.porque for r in ficha.relaciones]
    return " ".join(partes)


def test_f006_r2_compras_linea_id_no_se_declara_unico() -> None:
    """`linea_id` viene de `ctrpro`, `dcapro` y `dcfpro`, que colisionan.

    La clave real es `(tipo_doc, linea_id)` y la tabla no tiene PK declarada:
    tratarlo como único pierde filas al contar y las duplica al unir.
    """
    ficha = _diccionario().por_nombre["compras.fact_compras_linea"]

    assert list(ficha.clave_negocio) == ["tipo_doc", "linea_id"]
    columnas = {c.nombre: c for c in ficha.columnas}
    assert "NO ES UNICO" in columnas["linea_id"].significado
    assert "tipo_doc" in columnas["linea_id"].significado

    sql = (DIR_SQL / "compras/02_fact_linea.sql").read_text(encoding="utf-8")
    assert "ADD PRIMARY KEY" not in sql, (
        "si algún día se le pone PK a esta tabla, esta ficha hay que reescribirla"
    )


def test_f006_r2_compras_los_abonos_ya_vienen_en_negativo() -> None:
    texto = _texto_de("compras.fact_compras_linea")

    assert "ABONO" in texto
    assert "negativo" in texto

    sql = (DIR_SQL / "compras/03_views.sql").read_text(encoding="utf-8")
    assert "signo natural" in sql, "es de donde sale la afirmación"


def test_f006_r2_compras_los_importes_son_sin_iva_y_se_dice() -> None:
    """Y se dice también contra qué NO se pueden comparar."""
    for objeto in ("fact_compras_linea", "v_pbi_contrato_consumo",
                   "v_pbi_proveedor_obra", "v_pbi_partida_coste"):
        assert "SIN IVA" in _texto_de(f"compras.{objeto}").upper(), objeto

    assert "importe_contratado" in _texto_de("compras.v_pbi_proveedor_obra")


def test_f006_r2_compras_no_filtra_por_el_universo_del_seguimiento() -> None:
    """Puede traer obras administrativas que `stg.obras` excluye."""
    texto = _texto_de("compras.v_pbi_partida_coste")

    assert "stg.obras" in texto
    assert "administrativas" in texto


def test_f006_r2_compras_las_filas_sin_obra_no_se_pueden_perder() -> None:
    """Estructura y generales: filtrarlas fuera baja el total sin avisar."""
    columnas = {
        c.nombre: c
        for c in _diccionario().por_nombre["compras.fact_compras_linea"].columnas
    }

    nulo = columnas["obra_id"].nulo_significa or ""
    assert "estructura" in nulo.lower()
    assert "no se pueden perder" in nulo.lower()


def test_f006_r2_retenciones_prohibe_el_join_a_las_lineas() -> None:
    """La regla que más dinero ha costado: 38,9 M€ en una sola obra."""
    ficha = _diccionario().por_nombre["retenciones.movimientos"]

    assert "38,9" in ficha.grano
    assert "UNA FILA POR EFECTO" in ficha.grano

    hacia_factura = next(
        r for r in ficha.relaciones if r.a.startswith("compras.facturas")
    )
    assert "NUNCA" in hacia_factura.porque
    assert "factura_lineas" in hacia_factura.porque


def test_f006_r12_retenciones_hereda_la_regla_del_join() -> None:
    """No basta con contarlo en la ficha: la regla dura tiene que alcanzarla."""
    from etl_sigrid.domain.diccionario import derivar_avisos

    derivado = derivar_avisos(_diccionario())

    avisos = derivado.por_nombre["retenciones.movimientos"].avisos
    assert "R-RETENCION-NO-JOIN-LINEAS" in avisos


def test_f006_r2_retenciones_explica_la_cascada_de_atribucion_a_obra() -> None:
    columnas = {
        c.nombre: c
        for c in _diccionario().por_nombre["retenciones.movimientos"].columnas
    }

    obra = columnas["obra_id"]
    assert "CENTRO DE COSTE" in obra.significado
    assert "98" in obra.significado, "la cascada acierta en torno al 98 % por cenide"
    assert "num_obras_documento" in (obra.nulo_significa or "")


def test_f006_r2_retenciones_declara_las_dos_lecturas_del_saldo() -> None:
    """`saldo_vivo` es la de por defecto; `neto_practicado` es la otra, y no dan
    lo mismo. Dar una sin decir cuál es no es una respuesta completa."""
    for objeto in ("v_pbi_retencion_entidad", "v_pbi_retencion_resumen"):
        columnas = {
            c.nombre: c
            for c in _diccionario().por_nombre[f"retenciones.{objeto}"].columnas
        }
        assert "saldo_vivo" in columnas
        assert "neto_practicado" in columnas
        assert "NO es" in columnas["neto_practicado"].significado, objeto

    entidad = {
        c.nombre: c
        for c in _diccionario().por_nombre[
            "retenciones.v_pbi_retencion_entidad"
        ].columnas
    }
    assert "DEFECTO" in entidad["saldo_vivo"].significado.upper()


def test_f006_r2_retenciones_dice_que_la_vista_de_venta_esta_vacia() -> None:
    """`dvfpro` no se ingiere: consultarla no devuelve nada nunca."""
    ficha = _diccionario().por_nombre["retenciones.v_src_lineas_venta"]

    assert "VACIA" in ficha.descripcion.upper()
    assert "dvfpro" in ficha.descripcion
    assert ficha.consumo_recomendado is False


def test_f006_r14_los_dos_esquemas_manuales_lo_declaran_en_todas_sus_fichas() -> None:
    for esquema, paso in (("compras", "build_compras"),
                          ("retenciones", "build_retenciones")):
        fichas = _fichas_de(esquema)
        assert fichas, esquema
        for nombre, ficha in fichas.items():
            assert ficha.refresco == "manual", f"{esquema}.{nombre}"
            assert ficha.paso_etl == paso, f"{esquema}.{nombre}"


def _pasos_registrables() -> set[str]:
    """Los pasos que existen de verdad como step y por tanto dejan fila.

    Se derivan del propio código: un paso solo aparece en `_meta.v_frescura` si
    hay una clase `PipelineStep` cuyo `name` lo devuelve.
    """
    nombres: set[str] = set()
    for ruta in (RAIZ / "etl_sigrid" / "application" / "steps").rglob("*.py"):
        texto = ruta.read_text(encoding="utf-8")
        nombres |= set(re.findall(r'return "([a-z_]+)"', texto))
    return nombres


def test_f006_r13_control_hay_pasos_registrables_de_verdad() -> None:
    """Si la derivación devolviera vacío, el test de abajo no probaría nada."""
    registrables = _pasos_registrables()

    assert {"build_mart", "build_stg", "build_cierre", "publicar_diccionario"} <= (
        registrables
    )
    assert "build_compras" not in registrables
    assert "build_retenciones" not in registrables


def test_f006_r13_una_ficha_cuyo_paso_no_deja_rastro_lo_advierte() -> None:
    """`build-compras` y `build-retenciones` ejecutan SQL en línea, sin step.

    Su fecha de build NO es consultable por SQL, así que `_meta.v_diccionario`
    dará frescura a nulo para estos objetos. La ficha tiene que decirlo en vez
    de mandar al agente a una vista que no le va a responder.
    """
    from etl_sigrid.domain.diccionario import derivar_avisos

    registrables = _pasos_registrables()
    derivado = derivar_avisos(_diccionario())
    reglas = {r.codigo: r for r in derivado.reglas}

    afectadas = [
        f for f in derivado.fichas
        if f.paso_etl and f.paso_etl not in registrables
    ]
    assert afectadas, "el control de arriba dice que hay pasos no registrables"

    for ficha in afectadas:
        # El aviso puede llegar por el texto de la propia ficha o —lo normal—
        # por una regla dura que la alcance. Lo segundo es el mecanismo pensado
        # para esto: repetir la advertencia en las 24 fichas la diluiría, y una
        # nota en la cabecera del YAML no la ve el agente, porque los
        # comentarios del fichero no se publican.
        propio = _texto_de(ficha.nombre)
        heredado = " ".join(
            reglas[c].regla + " " + reglas[c].motivo
            for c in ficha.avisos
            if c in reglas
        )
        texto = propio + " " + heredado
        assert "no registran paso" in texto or "no es consultable" in texto, (
            f"{ficha.nombre} declara `paso_etl: {ficha.paso_etl}`, que no deja "
            f"fila en `_meta.etl_runs`, y ni la ficha ni sus avisos lo advierten"
        )


def test_f006_r13_el_aviso_de_frescura_llega_a_compras_y_retenciones() -> None:
    """Y llega por el mecanismo, no por copiar la advertencia 24 veces."""
    from etl_sigrid.domain.diccionario import derivar_avisos

    derivado = derivar_avisos(_diccionario())

    for esquema in ("compras", "retenciones"):
        fichas = [f for f in derivado.fichas if f.esquema == esquema]
        assert fichas, esquema
        for ficha in fichas:
            assert "R-FRESCURA-MANUAL" in ficha.avisos, ficha.nombre


# ===========================================================================
# EL MECANISMO · contrastar contra el SQL lo que hasta ahora no se contrastaba
#
# Dos huecos que el reviewer señaló dos veces y que costaron dos rechazos: la
# puerta comprobaba los NOMBRES de las columnas pero no `agregacion` ni
# `clave_negocio`. En `mart` y `cierre` no dolió porque sus claves son simples;
# en `compras` y `retenciones` son compuestas, y ahí es donde se cayó.
#
# Quedan 53 objetos por documentar, así que esto no es perfeccionismo: es la
# diferencia entre que los mismos errores se repitan cincuenta veces o no puedan
# volver a colarse.
#
# LÍMITE DECLARADO, para no marcar de más. De las dos direcciones de un error de
# clave, solo una es derivable:
#
#   * «la clave nombra algo que no identifica» SÍ lo es: basta con exigir que
#     esté contenida en el `GROUP BY`, o que case con la PK del DDL;
#   * «la clave es demasiado corta» NO lo es. Decidir si una columna del
#     `GROUP BY` puede omitirse exige saber si depende funcionalmente de otra, y
#     eso no se lee del texto: `codigo_obra` sí depende de `obra_id` y
#     `proveedor_cif` NO depende de `proveedor_id` —sale del CIF del documento—
#     y las dos se escriben igual. Exigir la igualdad con el `GROUP BY` marcaría
#     como falsas fichas correctas: `mart.fact_seguimiento_categoria` agrupa por
#     nueve columnas de las que cinco se derivan de otras dos.
#     Esa mitad se queda en revisión humana, y queda dicho aquí en vez de
#     dejarlo creer cubierto.
# ===========================================================================


def proyeccion_por_alias(cuerpo: str) -> dict[str, str] | None:
    """Alias -> expresión que lo produce, en el `SELECT` final del objeto.

    Es el mismo recorrido que `columnas_proyectadas`, guardando además el texto
    de cada elemento: es lo que permite preguntarle a una columna qué función la
    envuelve de verdad.
    """
    cuerpo = re.sub(r"--[^\n]*", " ", cuerpo)
    lineas = cuerpo.split("\n")
    selects = [i for i, linea in enumerate(lineas) if re.match(r"^SELECT\b", linea)]
    if not selects:
        return None
    inicio = selects[-1]
    fin = next(
        (i for i in range(inicio + 1, len(lineas)) if re.match(r"^(FROM|;)\b", lineas[i])),
        None,
    )
    if fin is None:
        return None

    proyeccion = re.sub(
        r"^SELECT\s+(?:DISTINCT\s+(?:ON\s*\([^)]*\)\s*)?)?",
        "",
        "\n".join(lineas[inicio:fin]),
        flags=re.IGNORECASE,
    )

    items, actual, profundidad = [], [], 0
    for caracter in proyeccion:
        if caracter in "([":
            profundidad += 1
        elif caracter in ")]":
            profundidad -= 1
        if caracter == "," and profundidad == 0:
            items.append("".join(actual))
            actual = []
        else:
            actual.append(caracter)
    items.append("".join(actual))

    por_alias: dict[str, str] = {}
    for item in items:
        item = " ".join(item.split())
        if not item:
            continue
        alias = re.search(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", item, re.IGNORECASE)
        if alias:
            expresion = item[: alias.start()].strip()
            por_alias[alias.group(1)] = expresion
            continue
        desnuda = re.match(
            r"^(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)$", item
        )
        if desnuda:
            por_alias[desnuda.group(1)] = item
            continue
        return None
    return por_alias or None


def funcion_envolvente(expresion: str) -> str | None:
    """La función agregada más externa de una expresión, si la hay.

    Devuelve `COUNT DISTINCT`, `COUNT`, `SUM`, `MIN`, `MAX` o `None`. Se ignora
    lo que venga después (`FILTER (...)`, un cast, `::NUMERIC`), porque no
    cambia lo que la medida es.
    """
    limpia = expresion.strip()
    coincidencia = re.match(r"^([A-Za-z_]+)\s*\(", limpia)
    if coincidencia is None:
        return None
    funcion = coincidencia.group(1).upper()
    if funcion not in ("COUNT", "SUM", "MIN", "MAX", "AVG"):
        return None
    if funcion == "COUNT" and re.match(r"^COUNT\s*\(\s*DISTINCT\b", limpia, re.I):
        return "COUNT DISTINCT"
    return funcion


#: Lo que cada función admite como `agregacion`. Solo se listan las funciones
#: cuyo veredicto es inequívoco: `SUM` y `COUNT` sin DISTINCT sí se pueden
#: seguir sumando entre grupos disjuntos, y por eso no se restringen.
AGREGACION_PROHIBIDA = {
    # Un recuento de distintos NO se suma: la misma factura repartida entre tres
    # obras aparece en tres filas con valor 1, y sumarlas da tres facturas donde
    # hay una.
    "COUNT DISTINCT": {"suma", "suma_solo_dentro_del_mes"},
    # Un mínimo o un máximo tampoco: sumarlos no significa nada.
    "MIN": {"suma", "suma_solo_dentro_del_mes"},
    "MAX": {"suma", "suma_solo_dentro_del_mes"},
    "AVG": {"suma", "suma_solo_dentro_del_mes"},
}


def _objetos_con_proyeccion():
    """Fichas con columnas que se leen de una proyección, y su SQL."""
    for ficha in _diccionario().fichas:
        if not ficha.columnas or ficha.nombre in TABLAS_CON_DDL_EXPLICITO:
            continue
        if ficha.nombre in CREADAS_CON_SQL_DINAMICO:
            continue
        sql = (DIR_SQL / _origen_por_objeto()[ficha.nombre]).read_text(encoding="utf-8")
        cuerpo = cuerpo_de_vista(sql, ficha.esquema, ficha.objeto)
        if cuerpo is None:
            continue
        yield ficha, cuerpo


def test_f006_r7_control_el_detector_de_funciones_distingue_lo_que_importa() -> None:
    """Si esto fallara, el test de abajo pasaría en falso sobre todo."""
    assert funcion_envolvente("COUNT(DISTINCT documento_id)") == "COUNT DISTINCT"
    assert funcion_envolvente("COUNT(*) FILTER (WHERE estado = 'VIVA')") == "COUNT"
    assert funcion_envolvente("SUM(importe) FILTER (WHERE importe > 0)") == "SUM"
    assert funcion_envolvente("MIN(fecha_prevista_devolucion)") == "MIN"
    assert funcion_envolvente("l.importe") is None
    assert funcion_envolvente("ROUND(a * 100.0 / b, 2)") is None


@pytest.mark.parametrize(
    "nombre", sorted(f.nombre for f, _ in _objetos_con_proyeccion())
)
def test_f006_r7_la_agregacion_declarada_case_con_la_funcion_del_sql(
    nombre: str,
) -> None:
    """`COUNT(DISTINCT …)` no puede ser `suma`, y `MIN`/`MAX` tampoco.

    `agregacion` es el campo que el MCP traduce a «esta columna se suma»: si
    miente, el agente suma lo que no se suma y el número sale plausible.
    """
    ficha, cuerpo = next(
        (f, c) for f, c in _objetos_con_proyeccion() if f.nombre == nombre
    )
    proyeccion = proyeccion_por_alias(cuerpo)
    if proyeccion is None:
        pytest.skip("la proyección de este objeto no se deja leer")

    problemas = []
    for columna in ficha.columnas:
        expresion = proyeccion.get(columna.nombre)
        if expresion is None or columna.agregacion is None:
            continue
        funcion = funcion_envolvente(expresion)
        if columna.agregacion in AGREGACION_PROHIBIDA.get(funcion, set()):
            problemas.append(
                f"{columna.nombre}: el SQL es {funcion} y la ficha dice "
                f"`agregacion: {columna.agregacion}`"
            )

    assert not problemas, "; ".join(problemas)


def columnas_del_group_by(cuerpo: str, proyeccion: dict[str, str]) -> set[str] | None:
    """Los ALIAS por los que agrupa el `SELECT` final, o `None` si no se sabe.

    Devolver `None` en vez de una lista a medias es deliberado, y hay tres
    casos en los que se hace:

    * la vista tiene `UNION`: el `GROUP BY` que se encuentra pertenece a una
      rama, no al grano de la vista;
    * el `GROUP BY` es POSICIONAL (`GROUP BY 1, 2`), que es legítimo y frecuente
      dentro de las CTE;
    * alguna expresión agrupada no casa con ningún alias proyectado.

    En los tres, una respuesta a medias convertiría la comprobación en un
    colador o en una fuente de falsos positivos.
    """
    limpio = re.sub(r"--[^\n]*", " ", cuerpo)
    if re.search(r"^\s*UNION\b", limpio, re.MULTILINE | re.IGNORECASE):
        return None

    # Se busca el `GROUP BY` de nivel 0 y se lee HASTA EL `;`, no hasta el
    # final de su linea: los `GROUP BY` largos se parten en varias, y cortar por
    # linea dejaba fuera la ultima columna. Se detecto con
    # `compras.v_pbi_proveedor_obra`, cuyo `anio` quedaba invisible.
    coincidencia = re.search(r"^GROUP\s+BY\s+", limpio, re.MULTILINE | re.IGNORECASE)
    if coincidencia is None:
        return None

    crudo = limpio[coincidencia.end():].split(";")[0]
    crudo = re.split(r"^(HAVING|ORDER)\b", crudo, flags=re.MULTILINE | re.IGNORECASE)[0]
    expresiones = [e.strip() for e in crudo.split(",") if e.strip()]
    if not expresiones or any(e.isdigit() for e in expresiones):
        return None

    por_expresion = {" ".join(v.split()): k for k, v in proyeccion.items()}
    alias: set[str] = set()
    for expresion in expresiones:
        normalizada = " ".join(expresion.split())
        if normalizada in proyeccion:          # agrupa por el propio alias
            alias.add(normalizada)
        elif normalizada in por_expresion:     # agrupa por la expresión fuente
            alias.add(por_expresion[normalizada])
        else:
            return None
    return alias


def test_f006_r2_control_el_group_by_se_lee_donde_se_puede_leer() -> None:
    """Control del alcance: si no leyera ninguno, el test de abajo no probaría
    nada; si los leyera todos, es que no está descartando los casos dudosos."""
    leidos = {
        f.nombre
        for f, c in _objetos_con_proyeccion()
        if (p := proyeccion_por_alias(c)) and columnas_del_group_by(c, p) is not None
    }

    assert "compras.v_pbi_proveedor_obra" in leidos
    assert "compras.v_pbi_partida_coste" in leidos
    assert "retenciones.v_pbi_retencion_entidad" in leidos
    # Y este NO, porque tiene UNION y su `GROUP BY` es de una rama.
    assert "mart.v_fact_periodificado" not in leidos


@pytest.mark.parametrize(
    "nombre", sorted(f.nombre for f, _ in _objetos_con_proyeccion())
)
def test_f006_r2_la_clave_de_negocio_cabe_en_el_group_by(nombre: str) -> None:
    """Una columna de la clave que no está en el `GROUP BY` puede repetirse.

    Es la mitad derivable del problema: si la clave nombra algo por lo que la
    vista no agrupa, hay varias filas con el mismo valor de clave y el JOIN por
    ella multiplica.
    """
    ficha, cuerpo = next(
        (f, c) for f, c in _objetos_con_proyeccion() if f.nombre == nombre
    )
    proyeccion = proyeccion_por_alias(cuerpo)
    if proyeccion is None:
        pytest.skip("la proyección de este objeto no se deja leer")
    agrupadas = columnas_del_group_by(cuerpo, proyeccion)
    if agrupadas is None:
        pytest.skip("el `GROUP BY` de este objeto no es derivable; ver docstring")

    sobran = sorted(set(ficha.clave_negocio) - agrupadas)

    assert not sobran, (
        f"{sobran} están en `clave_negocio` y no en el `GROUP BY`: la vista "
        f"puede tener varias filas con el mismo valor"
    )


def pk_declarada(sql: str, esquema: str, objeto: str) -> list[str] | None:
    """Las columnas de la PK que el DDL declara con `ALTER TABLE`, si la hay."""
    coincidencia = re.search(
        rf"ALTER\s+TABLE\s+{re.escape(esquema)}\.{re.escape(objeto)}\s+"
        rf"ADD\s+PRIMARY\s+KEY\s*\(([^)]*)\)",
        re.sub(r"--[^\n]*", " ", sql),
        re.IGNORECASE,
    )
    if coincidencia is None:
        return None
    return [c.strip() for c in coincidencia.group(1).split(",") if c.strip()]


def test_f006_r2_control_hay_tablas_con_pk_declarada() -> None:
    sql = (DIR_SQL / "compras/01_documentos.sql").read_text(encoding="utf-8")

    assert pk_declarada(sql, "compras", "contratos") == ["contrato_id"]
    assert pk_declarada(sql, "compras", "albaran_lineas") == ["linea_id"]

    sin_pk = (DIR_SQL / "compras/02_fact_linea.sql").read_text(encoding="utf-8")
    assert pk_declarada(sin_pk, "compras", "fact_compras_linea") is None


@pytest.mark.parametrize(
    "nombre", sorted(f.nombre for f in _diccionario().fichas if f.tipo == "tabla")
)
def test_f006_r2_la_clave_de_negocio_casa_con_la_pk_declarada(nombre: str) -> None:
    """Si el DDL declara una PK, la clave de negocio tiene que ser esa.

    Salvo que la PK sea una clave sustituta —un `BIGSERIAL` que cambia en cada
    build—, que es el caso de las tablas de hecho y se deja fuera a propósito:
    ahí la clave de negocio es OTRA cosa y así se documenta.
    """
    ficha = _diccionario().por_nombre[nombre]
    origen = _origen_por_objeto()[nombre]
    if origen == "config/tables_sigrid.yaml":
        pytest.skip("las tablas de `raw` no tienen DDL en el repositorio (DA-2)")

    sql = (DIR_SQL / origen).read_text(encoding="utf-8")
    pk = pk_declarada(sql, ficha.esquema, ficha.objeto)
    if pk is None:
        pytest.skip("el DDL no declara clave primaria para este objeto")

    sustitutas = {
        c.nombre for c in ficha.columnas if c.agregacion == "clave_sustituta"
    }
    if set(pk) <= sustitutas:
        pytest.skip("la PK es una clave sustituta; la de negocio es otra cosa")

    assert set(ficha.clave_negocio) == set(pk), (
        f"la PK del DDL es {pk} y la ficha declara {list(ficha.clave_negocio)}"
    )
