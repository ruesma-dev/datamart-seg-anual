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
* Para las **vistas** es más débil —haría falta un parser de SQL— y se limita a
  exigir que cada columna documentada aparezca literalmente en el fichero que
  crea la vista. Caza los nombres inventados y las erratas, que es el 90 % de
  los casos, y no caza un alias mal atribuido. Para eso está
  `python main.py check-diccionario` contra el catálogo real (R28).

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


@pytest.mark.parametrize(
    "nombre", sorted(f.nombre for f in _fichas_con_columnas())
)
def test_f006_r26_ninguna_columna_documentada_esta_inventada(nombre: str) -> None:
    """Una columna que no existe es un `SELECT` que revienta, y eso con suerte:
    lo malo es la columna que existe y significa otra cosa."""
    ficha = _diccionario().por_nombre[nombre]
    origen = _origen_por_objeto()[nombre]
    if origen == "config/tables_sigrid.yaml":
        pytest.skip("las tablas de `raw` no tienen SQL que leer (DA-2)")

    sql = (DIR_SQL / origen).read_text(encoding="utf-8")

    inventadas = [
        c.nombre
        for c in ficha.columnas
        if not re.search(rf"\b{re.escape(c.nombre)}\b", sql)
    ]

    assert not inventadas, f"{nombre}: {inventadas} no aparecen en {origen}"


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
