# tests/test_f084_sql.py
"""
F-084 · El estado del CONTRATO, comprobado sobre el TEXTO del SQL.

`sql/compras/01_documentos.sql` construye tablas en un Postgres **compartido
con produccion**, asi que aqui no se ejecuta: se lee. Mismo criterio que
`tests/test_f073_sql.py`, `tests/test_f080_sql.py` y `tests/test_f083_sql.py`.

LO QUE ESTE FICHERO DEFIENDE. `compras.contratos` **ya existe y la consume
Negocio**: doce columnas, 18.978 filas medidas el 2026-09-16. F-084 le anade
tres —`estado_id`, `estado_codigo` y `estado`— y no toca ninguna de las doce.

Y LA TRADUCCION VA POR LA PAREJA `(tipo de documento, estado)`. El mismo
`estado_id` significa cosas distintas en un contrato (tipo 44), una factura
(15) o una obra (42): unir solo por `estado_id` traduce con el diccionario
equivocado y el build no se entera. El estado 7 es «Firmado» en un contrato;
en el catalogo de facturas ese numero es otra cosa.

EL CRITERIO 6 ES LO QUE DA FORMA A ESTE FICHERO. F-083 dejo el lateral de la
traduccion escrito a mano dentro del bloque FACTURAS. Copiarlo al bloque
CONTRATOS habria dado dos copias del mismo `WHERE`, dos `LIMIT 1` que
mantener y dos sitios donde olvidar el tipo. En vez de eso, la traduccion vive
UNA VEZ en `compras.fn_estado_documento(p_tip, p_est)`, en `00_setup.sql`
—donde ya viven `fn_serie`, `fn_sigrid_date` y `fn_tipo_documento`— y los dos
bloques la llaman. La ganancia no es de lineas: **el tipo de documento pasa a
ser un argumento obligatorio de la firma**, asi que la union «solo por
estado_id» que el criterio 1 manda vigilar deja de poder escribirse.
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
RUTA_SETUP = DIRECTORIO_SQL / "compras" / "00_setup.sql"
RUTA_DOCUMENTOS = DIRECTORIO_SQL / "compras" / "01_documentos.sql"

#: El nombre de la funcion que factoriza la traduccion (criterio 6).
FUNCION = "compras.fn_estado_documento"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


@cache
def _bloque_contratos() -> str:
    """El texto ejecutable del bloque que construye `compras.contratos`.

    Acotado a proposito: `01_documentos.sql` construye ademas albaranes,
    facturas y las lineas de los tres, y un `in` sobre el fichero entero daria
    verde por una coincidencia en el bloque de al lado. Ya paso en F-006, con
    el guardian de nulos acusando a `compras.albaranes` de lo que leia en
    `compras.contratos`.
    """
    texto = _texto(RUTA_DOCUMENTOS)
    inicio = texto.index("DROP TABLE IF EXISTS compras.contratos")
    fin = texto.index("ALTER TABLE compras.contratos ADD PRIMARY KEY")
    return _compacto(texto[inicio:fin])


@cache
def _bloque_facturas() -> str:
    """El bloque hermano, el de F-083: aqui solo para el criterio 6."""
    texto = _texto(RUTA_DOCUMENTOS)
    inicio = texto.index("DROP TABLE IF EXISTS compras.facturas")
    fin = texto.index("ALTER TABLE compras.facturas ADD PRIMARY KEY")
    return _compacto(texto[inicio:fin])


@cache
def _cuerpo_de_la_funcion() -> str:
    """La definicion de `compras.fn_estado_documento`, acotada y compactada."""
    texto = _sin_comentarios(_texto(RUTA_SETUP))
    marca = f"CREATE OR REPLACE FUNCTION {FUNCION}"
    assert marca in texto, (
        f"`{FUNCION}` no esta definida en `compras/00_setup.sql`: sin ella la "
        "traduccion del estado tendria que copiarse en cada bloque, que es "
        "justo lo que el criterio 6 prohibe"
    )
    inicio = texto.index(marca)
    fin = texto.index("$$;", texto.index("AS $$", inicio))
    return re.sub(r"\s+", " ", texto[inicio:fin])


def _llamada_del_estado(bloque: str) -> str:
    """La llamada a la funcion dentro de un bloque, con su `LEFT JOIN`."""
    assert FUNCION in bloque, (
        f"el bloque no llama a `{FUNCION}`: sin la llamada no hay estado "
        "publicado (criterio 1)"
    )
    inicio = bloque.index("LEFT JOIN LATERAL")
    return bloque[inicio : bloque.index("ON TRUE", inicio) + len("ON TRUE")]


def _columnas_publicadas(bloque: str) -> list[str]:
    """Los alias `AS <columna>` del SELECT, en orden."""
    return re.findall(r"\bAS ([a-z_]+)\b", bloque)


#: Las doce columnas que `compras.contratos` publica desde F-067, EN SU ORDEN.
#: Ninguna puede desaparecer, renombrarse ni cambiar de posicion (criterio 2).
#: Comprobadas contra `information_schema` el 2026-09-16: son exactamente estas
#: y en este orden.
COLUMNAS_DE_SIEMPRE = (
    "contrato_id",
    "codigo_contrato",
    "serie",
    "descripcion",
    "fecha",
    "obra_id",
    "codigo_obra",
    "nombre_obra",
    "proveedor_id",
    "proveedor_nombre",
    "proveedor_cif",
    "comparativo_id",
)

#: Lo que anade F-084, y va DETRAS de las doce de siempre.
COLUMNAS_NUEVAS = ("estado_id", "estado_codigo", "estado")


# ===========================================================================
# Criterio 2 · el grano y las columnas de siempre, intactos
# ===========================================================================


@pytest.mark.parametrize("columna", COLUMNAS_DE_SIEMPRE)
def test_f084_c2_ninguna_columna_de_siempre_desaparece(columna: str) -> None:
    assert columna in _columnas_publicadas(_bloque_contratos()), (
        f"`compras.contratos` dejaria de publicar `{columna}`: la consumen "
        "Power BI y el MCP, y el criterio 2 prohibe que ninguna columna actual "
        "desaparezca ni se renombre"
    )


def test_f084_c2_las_columnas_de_siempre_van_primero_y_en_su_orden() -> None:
    """Las nuevas se anaden AL FINAL, no intercaladas.

    `compras.contratos` es una tabla, no una vista, asi que PostgreSQL no lo
    impide: lo impide el consumidor. Un `SELECT *` de Power BI recibe las
    columnas por posicion, y meter `estado` entre `descripcion` y `fecha`
    —que es donde se lee mejor— reordena una tabla que ya esta en produccion.
    Misma disciplina que F-073 en `maestro.obras` y F-083 en
    `compras.facturas`.
    """
    publicadas = _columnas_publicadas(_bloque_contratos())
    assert tuple(publicadas[: len(COLUMNAS_DE_SIEMPRE)]) == COLUMNAS_DE_SIEMPRE, (
        "las doce columnas de siempre tienen que seguir siendo las doce "
        f"primeras y en su orden; hoy son {publicadas[:12]}"
    )


def test_f084_c2_el_universo_de_contratos_no_se_filtra() -> None:
    """Ni un WHERE en la consulta externa: los 18.978 contratos siguen estando.

    Publicar el estado no puede dejar fuera a los contratos cuyo estado no case
    con el catalogo: se publican igual, con el literal a NULL.
    """
    bloque = _bloque_contratos()
    desde_el_from = bloque.split("FROM raw.ctr c")[1]
    assert " WHERE " not in desde_el_from, (
        "ha aparecido un WHERE en el FROM de `compras.contratos`: eso cambia "
        "el grano, que es justo lo que el criterio 2 prohibe"
    )


def test_f084_c2_la_traduccion_del_estado_no_puede_multiplicar_filas() -> None:
    """La guarda anti-multiplicacion del criterio 2.

    Hoy `(tip, est)` es unico —7 de 7 en el tipo 44 y ni un par repetido en las
    193 filas del catalogo, medido el 2026-09-16— pero una tabla que ya consume
    Negocio no puede depender de un dato de origen que nadie controla. La
    guarda no vive en la llamada sino DENTRO de la funcion, que es la ventaja
    de haberla factorizado: se escribe una vez y protege a los dos bloques.
    """
    cuerpo = _cuerpo_de_la_funcion()
    assert "LIMIT 1" in cuerpo, (
        "sin `LIMIT 1`, el dia en que el catalogo traiga dos filas para el "
        f"mismo `(tip, est)` `{FUNCION}` devolveria dos y los laterales "
        "duplicarian contratos y facturas en silencio"
    )
    assert "ORDER BY" in cuerpo, (
        "`LIMIT 1` sin `ORDER BY` elige una fila al azar: el literal publicado "
        "cambiaria de una noche a otra sin que nadie lo note"
    )


def test_f084_c2_el_lateral_del_estado_es_left_y_no_pierde_contratos() -> None:
    llamada = _llamada_del_estado(_bloque_contratos())
    assert llamada.startswith("LEFT JOIN LATERAL"), (
        "con `JOIN LATERAL` se perderian los contratos cuyo estado no case "
        "con el catalogo; hoy no le pasa a ninguno (0 huerfanos de 18.978), y "
        "por eso mismo un JOIN pareceria inocente"
    )
    assert llamada.endswith("ON TRUE"), (
        "el lateral tiene que cerrarse con `ON TRUE`, como en `maestro.obras` "
        "y en `compras.facturas`"
    )


def test_f084_c2_el_contrato_conserva_su_clave_e_indices() -> None:
    # Compactado: la alineacion en columnas de los `CREATE INDEX` es estilo del
    # fichero, no contrato, y un test que se rompa al alinear una linea manda
    # el mensaje equivocado.
    texto = _compacto(_texto(RUTA_DOCUMENTOS))
    assert "ALTER TABLE compras.contratos ADD PRIMARY KEY (contrato_id)" in texto, (
        "`contrato_id` sigue siendo la clave primaria: es el grano y no cambia"
    )
    assert "CREATE INDEX idx_com_ctr_est ON compras.contratos (estado_id)" in texto, (
        "la pregunta de Compras filtra por estado sobre 18.978 contratos: sin "
        "indice por `estado_id` cada consulta del MCP recorre la tabla entera"
    )


# ===========================================================================
# Criterio 1 · el estado, leido de `con.est` y traducido por la PAREJA
# ===========================================================================


@pytest.mark.parametrize("columna", COLUMNAS_NUEVAS)
def test_f084_c1_publica_el_estado_del_contrato(columna: str) -> None:
    assert columna in _columnas_publicadas(_bloque_contratos()), (
        f"`compras.contratos` no publica `{columna}`: sin el estado, Compras "
        "no puede ver que contratos llevan semanas enviados sin firmar, que es "
        "la pregunta que origino la feature (criterio 1)"
    )


def test_f084_c1_el_estado_id_se_lee_de_la_superclase_con() -> None:
    """No esta en `ctr`: esta en `con.est`. Es la leccion de F-080 y F-083."""
    assert "con.est AS estado_id" in _bloque_contratos(), (
        "`estado_id` tiene que leerse de `con.est`, la superclase de "
        "documentos de Sigrid, y no de `raw.ctr` (criterio 1)"
    )


def test_f084_c1_la_traduccion_filtra_el_tipo_de_documento_de_contrato() -> None:
    """El 44 va escrito en la llamada, que es donde se puede equivocar.

    Sin el tipo correcto se traduciria con el diccionario de otro documento y
    el build no diria nada: el estado 7 es «Firmado» en el catalogo del
    contrato, y en el de la factura ese numero es otro estado distinto.
    """
    llamada = _llamada_del_estado(_bloque_contratos())
    assert f"{FUNCION}(44, con.est)" in llamada, (
        "`compras.contratos` tiene que traducir su estado con el tipo de "
        f"documento 44: hoy la llamada es «{llamada.strip()}» (criterio 1)"
    )


def test_f084_c1_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id() -> None:
    """El test que el criterio 1 pide por su nombre, y esta escrito dos veces.

    Se comprueba en los DOS sitios donde se podria perder la mitad de la
    pareja:

    1. **Dentro de la funcion**, que es donde vive el `WHERE`. Si alguien
       «simplifica» el cuerpo a `WHERE ce.est = p_est`, el build sigue
       funcionando y `compras.contratos` publica el literal equivocado.
    2. **En la firma**, que es la defensa que da haberlo factorizado: el tipo
       es un argumento obligatorio, asi que la llamada no puede omitirlo sin
       que PostgreSQL falle al construir. Eso lo garantiza la base; lo que este
       test vigila es que la firma siga teniendo los dos parametros.
    """
    cuerpo = _cuerpo_de_la_funcion()
    condicion = cuerpo.split(" WHERE ")[1].split(" ORDER BY ")[0]
    assert re.search(r"\.tip = p_tip\b", condicion) and re.search(
        r"\.est = p_est\b", condicion
    ), (
        "la union al catalogo tiene que ir por la PAREJA (tipo, estado): hoy "
        f"la condicion es «{condicion.strip()}»"
    )
    assert " AND " in condicion, (
        "una sola condicion en el WHERE significa que se esta uniendo solo por "
        "`estado_id`, que es lo que el criterio 1 prohibe"
    )
    assert re.search(
        rf"FUNCTION {re.escape(FUNCION)}\(\s*p_tip [A-Z]+, ?p_est [A-Z]+\s*\)", cuerpo
    ), (
        "la firma tiene que seguir pidiendo el TIPO y el ESTADO: si el tipo "
        "deja de ser argumento, la traduccion vuelve a poder hacerse a ciegas"
    )


def test_f084_c1_la_funcion_lee_el_catalogo_de_estados_de_sigrid() -> None:
    cuerpo = _cuerpo_de_la_funcion()
    assert "raw.conest" in cuerpo, (
        f"`{FUNCION}` traduce contra `raw.conest`, el catalogo de estados de "
        "Sigrid (193 filas, 7 del tipo 44)"
    )
    assert "STABLE" in cuerpo, (
        "la funcion lee una tabla, asi que es STABLE y no IMMUTABLE: "
        "declararla IMMUTABLE autoriza a PostgreSQL a cachear un literal que "
        "manana cambia en el origen"
    )


# ===========================================================================
# Criterio 6 · el SQL del estado NO se duplica respecto a F-083
# ===========================================================================


def test_f084_c6_la_traduccion_del_estado_esta_definida_una_sola_vez() -> None:
    texto = _sin_comentarios(_texto(RUTA_SETUP))
    assert texto.count(f"CREATE OR REPLACE FUNCTION {FUNCION}") == 1, (
        f"`{FUNCION}` tiene que estar definida exactamente una vez: dos "
        "definiciones en el mismo fichero son dos comportamientos y gana la "
        "ultima"
    )


def test_f084_c6_los_dos_bloques_llaman_a_la_misma_funcion() -> None:
    """Contratos (44) y facturas (15) comparten la traduccion, con su tipo.

    Es el criterio 6 literal: el SQL del estado se repetia respecto a F-083 y
    se factoriza en vez de duplicarse. Si alguien vuelve a escribir el lateral
    a mano en uno de los dos bloques, este test lo ve.
    """
    assert f"{FUNCION}(44, con.est)" in _bloque_contratos(), (
        "el bloque CONTRATOS tiene que traducir con la funcion compartida"
    )
    assert f"{FUNCION}(15, con.est)" in _bloque_facturas(), (
        "el bloque FACTURAS tenia el lateral escrito a mano desde F-083 y "
        "ahora llama a la funcion compartida: es lo que pide el criterio 6"
    )


def test_f084_c6_el_catalogo_no_se_vuelve_a_leer_a_mano_en_documentos() -> None:
    """`01_documentos.sql` ya no nombra `raw.conest` en su SQL ejecutable.

    Es la comprobacion que distingue «factorizado» de «factorizado y ademas
    copiado»: mientras exista una lectura suelta del catalogo en este fichero,
    hay un segundo sitio donde olvidar el tipo o la guarda de grano.
    """
    ejecutable = _sin_comentarios(_texto(RUTA_DOCUMENTOS))
    assert "raw.conest" not in ejecutable, (
        "`01_documentos.sql` vuelve a leer `raw.conest` por su cuenta: la "
        f"traduccion del estado vive en `{FUNCION}` y se llama desde ahi "
        "(criterio 6)"
    )


# ===========================================================================
# La cabecera del fichero avisa de lo que costo descubrir
# ===========================================================================


def test_f084_c5_la_cabecera_avisa_de_que_las_firmas_no_sirven() -> None:
    """Medido: de las 70.308 firmas de `raw.confir`, CERO son de contrato.

    Es el hallazgo que justifica la feature, y va escrito donde lo lee quien
    toque el SQL: la via natural para «enviado sin firmar» parecia el circuito
    de firma y no existe para este documento.
    """
    texto = _texto(RUTA_DOCUMENTOS)
    cabecera = texto[: texto.index("DROP TABLE IF EXISTS compras.contratos")]
    plano = re.sub(r"\s+", " ", cabecera).lower()
    assert "confir" in plano and "cero" in plano, (
        "la cabecera de `01_documentos.sql` tiene que decir que el circuito de "
        "firma (`raw.confir`) NO tiene ni una firma de contrato, o el "
        "siguiente que busque «enviado sin firmar» volvera a ir alli"
    )
