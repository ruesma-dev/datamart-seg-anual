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
from pathlib import Path

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: Columnas de instrumentación del ETL: se documentan, pero el MCP las oculta.
TECNICAS = ("_built_at", "_ingested_at", "_source_tiemod")


def _diccionario():
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


def _origen_por_objeto() -> dict[str, str]:
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

    assert str(total) in texto
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
    """El texto del `CREATE VIEW` de ESA vista y solo de esa."""
    patron = re.compile(
        rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+"
        rf"{re.escape(esquema)}\.{re.escape(objeto)}\s+AS",
        re.IGNORECASE,
    )
    coincidencia = patron.search(sql)
    if coincidencia is None:
        return None
    resto = sql[coincidencia.end() :]
    corte = re.search(r"^(CREATE|COMMENT|DROP)\b", resto, re.MULTILINE)
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
    return [f for f in _diccionario().fichas if f.tipo == "vista"]


def test_f006_r26_todas_las_vistas_se_dejan_leer() -> None:
    """Control: si la extracción dejara de funcionar, el test de abajo pasaría
    en falso sobre cero vistas."""
    ilegibles = []
    for ficha in _vistas_del_diccionario():
        sql = (DIR_SQL / _origen_por_objeto()[ficha.nombre]).read_text(encoding="utf-8")
        cuerpo = cuerpo_de_vista(sql, ficha.esquema, ficha.objeto)
        if cuerpo is None or columnas_proyectadas(cuerpo) is None:
            ilegibles.append(ficha.nombre)

    assert not ilegibles, f"no se pudo leer la proyección de {ilegibles}"
    assert len(_vistas_del_diccionario()) >= 19


@pytest.mark.parametrize("nombre", sorted(f.nombre for f in _vistas_del_diccionario()))
def test_f006_r26_las_vistas_documentan_exactamente_su_proyeccion(nombre: str) -> None:
    """Ni una columna de menos (hueco) ni una de más (humo o columna ajena)."""
    ficha = _diccionario().por_nombre[nombre]
    sql = (DIR_SQL / _origen_por_objeto()[nombre]).read_text(encoding="utf-8")

    proyectadas = columnas_proyectadas(cuerpo_de_vista(sql, ficha.esquema, ficha.objeto))
    documentadas = [c.nombre for c in ficha.columnas]

    assert set(documentadas) == set(proyectadas), (
        f"faltan: {sorted(set(proyectadas) - set(documentadas))}; "
        f"sobran: {sorted(set(documentadas) - set(proyectadas))}"
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
