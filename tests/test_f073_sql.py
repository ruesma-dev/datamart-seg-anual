# tests/test_f073_sql.py
"""
F-073 · El SQL nuevo y el ampliado, comprobado sobre su TEXTO.

Ninguna de estas vistas se puede ejecutar aquí: `CREATE OR REPLACE VIEW` escribe
en un Postgres compartido con `albaranes` y `partes` **en producción**, y la
convención del proyecto es que los unit tests no toquen red ni BBDD. Lo que sí
se puede es fijar por escrito las decisiones que el diseño tomó midiendo contra
la base, de modo que un refactor que se lleve por delante cualquiera de ellas
rompa la suite y no la nocturna. Mismo criterio que `tests/test_f052_sql.py` y
`tests/test_f042_sql.py`.

Los nombres de columna de origen NO se suponen: están medidos en la T1 y
anotados en `progress/impl_F-073.md` (`conest.tip/est/res`, `auxefp.res` —y no
`auxefp.est`, que está vacío—, y los cuatro campos de dirección de `raw.obr`).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
)
RUTA_CENTROS = DIRECTORIO_SQL / "maestro" / "04_centros_coste.sql"


@lru_cache(maxsize=None)
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto ejecutable: sin las líneas `--` de comentario."""
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    """Una sola línea, espacios colapsados: para buscar expresiones SQL."""
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


# ---------------------------------------------------------------------------
# R1 · la vista existe y expone las siete columnas del puente
# ---------------------------------------------------------------------------


def test_f073_r1_la_vista_de_centros_de_coste_se_crea_como_vista() -> None:
    assert "CREATE OR REPLACE VIEW maestro.centros_coste" in _compacto(
        _sql(RUTA_CENTROS)
    )


@pytest.mark.parametrize(
    "columna",
    [
        "centro_coste_id",
        "codigo_centro",
        "nombre_centro",
        "empresa",
        "obra_id",
        "codigo_obra",
        "nombre_obra",
    ],
)
def test_f073_r1_expone_las_siete_columnas_del_puente(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _compacto(_sql(RUTA_CENTROS))), (
        f"maestro.centros_coste debe exponer {columna} (R1)"
    )


def test_f073_r1_una_fila_por_fila_de_raw_cen() -> None:
    """El grano es `raw.cen`: la tabla de la que se parte, sin filtro."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "FROM raw.cen" in compacto
    assert "WHERE" not in compacto.split("FROM raw.cen")[1].split("LEFT JOIN LATERAL")[0]


# ---------------------------------------------------------------------------
# R2 · el puente resuelve por misma empresa y mismo código en `raw.con`
# ---------------------------------------------------------------------------


def test_f073_r2_el_puente_cruza_por_empresa_y_codigo() -> None:
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "co.emp = cc.emp" in compacto, "falta el cruce por empresa (R2)"
    assert "co.cod = cc.cod" in compacto, "falta el cruce por código (R2)"


def test_f073_r2_el_lateral_exige_ficha_de_obra() -> None:
    """`JOIN raw.obr` dentro del lateral: descarta la propia fila `con` del centro."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    lateral = compacto[compacto.index("LEFT JOIN LATERAL") :]
    assert "raw.obr" in lateral, (
        "el lateral debe unir a raw.obr o resolvería contra el propio centro (R2)"
    )


def test_f073_r2_el_centro_toma_codigo_nombre_y_empresa_de_raw_con() -> None:
    """`raw.cen` no tiene `cod`, `res` ni `emp`: salen de su `raw.con` (T1)."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "JOIN raw.con" in compacto
    assert "cc.ide = n.ide" in compacto or "n.ide = cc.ide" in compacto


# ---------------------------------------------------------------------------
# R3 · ni `cen.obride` ni aritmética sobre el `ide`
# ---------------------------------------------------------------------------


def test_f073_r3_no_usa_cen_obride() -> None:
    """Está a 0 en las 804 filas (medido en T1): usarlo daría NULL siempre."""
    assert "obride" not in _sin_comentarios(_sql(RUTA_CENTROS)), (
        "cen.obride está a 0 en las 804 filas y no puede resolver el puente (R3)"
    )


def test_f073_r3_no_hace_aritmetica_sobre_el_ide() -> None:
    """`obride + 1` acertaba el 64 %: una coincidencia, no una relación."""
    ejecutable = _sin_comentarios(_sql(RUTA_CENTROS))
    assert not re.search(r"ide\s*[+-]\s*\d", ejecutable), (
        "la aritmética sobre el ide acierta el 64 %: no es el puente (R3)"
    )


# ---------------------------------------------------------------------------
# R4 · los 121 centros que no son obra se publican igual, con `obra_id` NULL
# ---------------------------------------------------------------------------


def test_f073_r4_el_lateral_es_left_join_y_no_join() -> None:
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "LEFT JOIN LATERAL" in compacto, (
        "con JOIN LATERAL se perderían los 121 centros sin obra (R4)"
    )
    assert re.search(r"LEFT JOIN LATERAL \(.*\) \w+ ON TRUE", compacto), (
        "el lateral debe colgar con ON TRUE para no filtrar (R4)"
    )


def test_f073_r4_no_filtra_los_centros_sin_obra() -> None:
    """Ningún `WHERE` fuera del lateral: no se descarta ninguna fila de `raw.cen`."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    tras_lateral = compacto[compacto.index(") o ON TRUE") :]
    assert "WHERE" not in tras_lateral, (
        "un WHERE final filtraría los 121 centros de estructura y servicios (R4)"
    )


# ---------------------------------------------------------------------------
# R5 · `centro_coste_id` es único POR CONSTRUCCIÓN
# ---------------------------------------------------------------------------


def test_f073_r5_el_lateral_no_puede_multiplicar_filas() -> None:
    """Hoy el puente es 1:1 sobre 683 pares; la vista no puede depender de eso."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    lateral = compacto[
        compacto.index("LEFT JOIN LATERAL") : compacto.index(") o ON TRUE")
    ]
    assert "LIMIT 1" in lateral, (
        "sin LIMIT 1 la vista multiplicaría filas el día que el origen deje de "
        "ser 1:1 (R5)"
    )
    assert "ORDER BY" in lateral, (
        "LIMIT 1 sin ORDER BY declarado elige una fila al azar (R5)"
    )


# ===========================================================================
# `maestro.estados_documento` (05) · R19 y R20
# ===========================================================================

RUTA_ESTADOS = DIRECTORIO_SQL / "maestro" / "05_estados_documento.sql"


def test_f073_r19_la_vista_de_estados_se_crea_como_vista() -> None:
    assert "CREATE OR REPLACE VIEW maestro.estados_documento" in _compacto(
        _sql(RUTA_ESTADOS)
    )


@pytest.mark.parametrize(
    "columna",
    ["estado_documento_id", "tipo_documento", "estado_id", "codigo_estado", "estado"],
)
def test_f073_r19_expone_tipo_codigo_y_nombre(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _compacto(_sql(RUTA_ESTADOS))), (
        f"maestro.estados_documento debe exponer {columna} (R19)"
    )


def test_f073_r19_lee_de_raw_conest_con_los_nombres_medidos() -> None:
    """T1: `tip` es el tipo, `est` el código del estado y `res` el nombre."""
    compacto = _compacto(_sql(RUTA_ESTADOS))
    assert "FROM raw.conest" in compacto
    for origen in ("tip", "est", "res"):
        assert re.search(rf"\.{origen}\s+AS ", compacto), (
            f"conest.{origen} no se proyecta (R19)"
        )


def test_f073_r19_no_filtra_por_tipo_de_documento() -> None:
    """Las 193 filas, no las 14 de obra: es una dimensión, no un lookup."""
    compacto = _compacto(_sql(RUTA_ESTADOS))
    cuerpo = compacto[
        compacto.index("CREATE OR REPLACE VIEW maestro.estados_documento") :
    ].split(";")[0]
    assert "WHERE" not in cuerpo, (
        "filtrar por tipo dejaría fuera contratos, facturas y comparativos (R19)"
    )
    assert "42" not in cuerpo, "el tipo de obra no se cablea aquí (R19)"


def test_f073_r20_el_comment_avisa_de_que_la_traduccion_va_por_tipo() -> None:
    """La misma cifra significa cosas distintas en un contrato y en una factura."""
    comentario = _sql(RUTA_ESTADOS)
    comentario = comentario[comentario.index("COMMENT ON VIEW maestro.estados_documento") :]
    assert "tipo de documento" in comentario.lower(), (
        "el COMMENT debe advertir de que la traducción va por tipo (R20)"
    )


# ===========================================================================
# `maestro.obras` (01, ampliada) · R7-R11, R13, R14, R16, R17 y R18
# ===========================================================================

RUTA_OBRAS = DIRECTORIO_SQL / "maestro" / "01_obras.sql"
RUTA_PROVEEDORES = DIRECTORIO_SQL / "maestro" / "02_proveedores.sql"

#: Las columnas que `maestro.obras` publicaba ANTES de F-073. Ninguna se puede
#: caer ni renombrar: hay consumo externo colgando de ellas (R18).
COLUMNAS_DE_SIEMPRE = (
    "obra_id",
    "codigo_obra",
    "nombre_obra",
    "estado_id",
    "fecha_alta",
    "fecha_baja",
    "es_activa",
    "cliente_id",
    "codigo_cliente",
    "nombre_cliente",
)

#: El vocabulario de dirección, que NO se inventa: es el que ya usa
#: `maestro.proveedores`. Preguntar «dónde está» tiene que escribirse igual
#: para una obra y para un proveedor (R7).
COLUMNAS_DE_DIRECCION = (
    "dir1",
    "dir2",
    "codigo_postal",
    "provincia",
    "municipio",
    "direccion_completa",
)


def _troceado_en_profundidad_cero(texto: str, separador: str) -> list[str]:
    """Trocea por `separador`, ignorando lo que caiga dentro de paréntesis."""
    piezas: list[str] = []
    actual: list[str] = []
    profundidad = 0
    i = 0
    while i < len(texto):
        caracter = texto[i]
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        if profundidad == 0 and texto.startswith(separador, i):
            piezas.append("".join(actual))
            actual = []
            i += len(separador)
            continue
        actual.append(caracter)
        i += 1
    piezas.append("".join(actual))
    return piezas


def _columnas_publicadas(ruta: Path) -> set[str]:
    """Los nombres que la vista EXPONE, con `AS` explícito o sin él.

    Sin esto el barrido se quedaría corto: `maestro.proveedores` publica `dir1`
    y `dir2` **sin alias**, y un barrido que solo mirase los `AS` no los
    vería. Se
    ignoran los paréntesis para que ni el `WITH` de proveedores ni los `EXISTS`
    de las marcas de obra cuenten como columnas.
    """
    compacto = _compacto(_sql(ruta))
    cuerpo = compacto[compacto.index("CREATE OR REPLACE VIEW") :]
    cuerpo = _troceado_en_profundidad_cero(cuerpo, ";")[0]
    seleccion = _troceado_en_profundidad_cero(cuerpo, " SELECT ")[1]
    seleccion = _troceado_en_profundidad_cero(seleccion, " FROM ")[0]

    nombres: set[str] = set()
    for pieza in _troceado_en_profundidad_cero(seleccion, ","):
        pieza = pieza.strip()
        if not pieza:
            continue
        if " AS " in pieza:
            nombres.add(pieza.rsplit(" AS ", 1)[1].strip())
        else:
            nombres.add(pieza.rsplit(".", 1)[-1].strip())
    return nombres


# --- R7 · el mismo vocabulario que `maestro.proveedores` -------------------


@pytest.mark.parametrize("columna", COLUMNAS_DE_DIRECCION)
def test_f073_r7_la_obra_usa_el_vocabulario_de_proveedores(columna: str) -> None:
    assert columna in _columnas_publicadas(RUTA_PROVEEDORES), (
        f"{columna} debería existir ya en maestro.proveedores; si cambió allí, "
        "este test está avisando de que las dos vistas se han separado (R7)"
    )
    assert columna in _columnas_publicadas(RUTA_OBRAS), (
        f"maestro.obras debe publicar {columna} con el mismo nombre (R7)"
    )


# --- R8 y R9 · de dónde sale la dirección, y de dónde NO ------------------


@pytest.mark.parametrize("campo", ["dir1", "dir2", "dircpo", "dir"])
def test_f073_r8_la_direccion_sale_de_los_cuatro_campos_de_obr(campo: str) -> None:
    assert re.search(rf"o\.{campo}\b", _compacto(_sql(RUTA_OBRAS))), (
        f"obr.{campo} es uno de los cuatro campos de dirección de la obra (R8)"
    )


@pytest.mark.parametrize(
    ("campo", "que_es"),
    [
        ("diride", "el director de obra"),
        ("perdir", "la persona de contacto del director"),
        ("entdiride", "la dirección del cliente"),
    ],
)
def test_f073_r9_no_publica_como_direccion_lo_que_no_lo_es(
    campo: str, que_es: str
) -> None:
    """Los tres suenan a dirección de la obra y ninguno lo es (F-071, medido)."""
    assert campo not in _sin_comentarios(_sql(RUTA_OBRAS)), (
        f"obr.{campo} es {que_es}, no la dirección de la obra (R9)"
    )


# --- R10 · municipio y provincia como ejes de agrupación -------------------


@pytest.mark.parametrize(
    "columna", ["municipio", "municipio_id", "provincia", "provincia_id"]
)
def test_f073_r10_publica_los_dos_ejes_con_su_identificador(columna: str) -> None:
    assert columna in _columnas_publicadas(RUTA_OBRAS), (
        f"agrupar por {columna} no puede depender del literal (R10)"
    )


def test_f073_r10_el_nombre_legible_viene_de_los_catalogos() -> None:
    compacto = _compacto(_sql(RUTA_OBRAS))
    assert "raw.auxmun" in compacto and "raw.auxpro" in compacto, (
        "el nombre del municipio y el de la provincia salen de auxmun/auxpro (R10)"
    )
    assert "NULLIF(o.munide, 0)" in compacto, (
        "munide a 0 es «no consta»: sin NULLIF uniría contra un catálogo falso (R10)"
    )
    assert "NULLIF(o.proide, 0)" in compacto, (
        "proide a 0 es «no consta»: sin NULLIF uniría contra un catálogo falso (R10)"
    )


# --- R13 y R14 · las dos marcas -------------------------------------------


@pytest.mark.parametrize("marca", ["tiene_presupuesto", "tiene_seguimiento"])
def test_f073_r13_publica_las_dos_marcas(marca: str) -> None:
    assert marca in _columnas_publicadas(RUTA_OBRAS), f"falta la marca {marca} (R13)"


@pytest.mark.parametrize(
    ("marca", "tabla"),
    [
        ("tiene_presupuesto", "stg.presupuesto"),
        ("tiene_seguimiento", "stg.plan_mensual"),
    ],
)
def test_f073_r14_cada_marca_es_un_exists_sobre_su_tabla_de_stg(
    marca: str, tabla: str
) -> None:
    """`EXISTS` y no `COUNT`: 921 sondas por índice, y nunca devuelve NULL (R13)."""
    compacto = _compacto(_sql(RUTA_OBRAS))
    patron = rf"EXISTS \(\s*SELECT 1 FROM {re.escape(tabla)} [^)]*\) AS {marca}"
    assert re.search(patron, compacto), (
        f"{marca} debe ser EXISTS sobre {tabla} (R14); el patrón buscado es "
        f"«EXISTS (SELECT 1 FROM {tabla} …) AS {marca}»"
    )


def test_f073_r14_las_marcas_leen_de_stg_y_nunca_de_mart() -> None:
    """DA-1: `mart/01_ddl.sql` dropea con CASCADE y destruiría esta vista."""
    assert "mart." not in _sin_comentarios(_sql(RUTA_OBRAS)), (
        "una vista de maestro colgada de mart la destruye la nocturna siguiente "
        "(el incidente de F-047): las marcas leen de stg (R14, DA-1)"
    )


# --- R16 y R17 · el estado, con nombre y sin multiplicar ------------------


def test_f073_r16_publica_el_nombre_del_estado_junto_al_codigo() -> None:
    alias = _columnas_publicadas(RUTA_OBRAS)
    assert "estado" in alias, "falta el nombre del estado (R16)"
    assert "estado_id" in alias, "el código interno se conserva (R16, R18)"


def test_f073_r16_traduce_filtrando_el_tipo_de_documento_de_obra() -> None:
    """Sin `tip = 42` traduciría contra estados de factura o de contrato."""
    compacto = _compacto(_sql(RUTA_OBRAS))
    assert "raw.conest" in compacto
    assert re.search(r"\.tip = 42\b", compacto), (
        "la traducción del estado va por tipo de documento, y el de obra es 42 (R16)"
    )


def test_f073_r17_la_traduccion_del_estado_no_puede_multiplicar_filas() -> None:
    """921 filas, ni una más: la guarda es del SQL, no del contenido de hoy."""
    compacto = _compacto(_sql(RUTA_OBRAS))
    bloque = compacto[compacto.index("raw.conest") :]
    assert "LIMIT 1" in bloque or "DISTINCT ON" in bloque, (
        "un LEFT JOIN desnudo a conest multiplica el día que (tip, est) deje de "
        "ser único (R17)"
    )
    assert "ORDER BY" in bloque, "LIMIT 1 sin ORDER BY no es determinista (R17)"


# --- R18 · no se pierde ni se renombra nada ------------------------------


@pytest.mark.parametrize("columna", COLUMNAS_DE_SIEMPRE)
def test_f073_r18_conserva_todas_las_columnas_de_antes(columna: str) -> None:
    assert columna in _columnas_publicadas(RUTA_OBRAS), (
        f"maestro.obras publicaba {columna} antes de F-073 y tiene que seguir "
        "publicándola con el mismo nombre (R18)"
    )


def test_f073_r18_el_significado_de_es_activa_no_cambia() -> None:
    compacto = _compacto(_sql(RUTA_OBRAS))
    assert "(c.fecbaj IS NULL OR c.fecbaj = 0) AS es_activa" in compacto, (
        "es_activa se calcula igual que antes de F-073 (R18)"
    )


def test_f073_r11_la_cabecera_ya_no_afirma_que_las_obras_no_tienen_direccion() -> None:
    """La cabecera de antes daba por hecho que la obra no tiene emplazamiento.

    Es falso y lo desmiente el censo. El veto es sobre el FICHERO ENTERO, así que
    ni siquiera la nota que corrige el error puede citar la frase textualmente:
    lo que no está escrito no se puede copiar y pegar de vuelta dentro de un año.
    """
    cabecera = _sql(RUTA_OBRAS).lower()
    assert "las obras no tienen dirección" not in cabecera
    assert "sin dirección" not in cabecera


# ===========================================================================
# `compras.formas_pago` (04) · R21 y R22
# ===========================================================================

RUTA_FORMAS_PAGO = DIRECTORIO_SQL / "compras" / "04_formas_pago.sql"


def test_f073_r21_la_vista_de_formas_de_pago_se_crea_como_vista() -> None:
    assert "CREATE OR REPLACE VIEW compras.formas_pago" in _compacto(
        _sql(RUTA_FORMAS_PAGO)
    )


@pytest.mark.parametrize(
    "columna",
    [
        "forma_pago_id",
        "codigo",
        "nombre",
        "plazo_formula",
        "medio_pago_id",
        "medio_pago",
        "clase_medio",
    ],
)
def test_f073_r21_expone_codigo_nombre_medio_y_clase(columna: str) -> None:
    assert columna in _columnas_publicadas(RUTA_FORMAS_PAGO), (
        f"compras.formas_pago debe exponer {columna} (R21)"
    )


def test_f073_r21_resuelve_el_medio_desde_auxefp_sin_perder_filas() -> None:
    """69 formas de pago y 10 medios: el `LEFT JOIN` conserva las 69."""
    compacto = _compacto(_sql(RUTA_FORMAS_PAGO))
    assert "FROM raw.auxpag" in compacto
    assert "LEFT JOIN raw.auxefp" in compacto, (
        "con JOIN se perderían las formas de pago sin medio (R21)"
    )
    assert "efeide" in compacto, "auxpag.efeide es la clave hacia auxefp (R21)"


def test_f073_r21_el_nombre_del_medio_sale_de_res_y_no_de_est() -> None:
    """MEDIDO en la T1: `auxefp.est` está vacío o a NULL en las 10 filas.

    `config/tables_sigrid.yaml` decía que el nombre del medio era `est`; es
    falso, y el que trae CHEQUE, EFECTIVO o TRANSFERENCIA es `res`. Este test
    existe porque el error estaba escrito en el árbol y parecía la fuente buena.
    """
    compacto = _compacto(_sql(RUTA_FORMAS_PAGO))
    assert re.search(r"\w+\.res\s+AS medio_pago", compacto), (
        "el nombre del medio de pago es auxefp.res (R21, medido en T1)"
    )
    assert not re.search(r"\w+\.est\s+AS medio_pago", compacto), (
        "auxefp.est está vacío en las 10 filas: publicarlo daría una columna "
        "vacía con nombre convincente (R21)"
    )


def test_f073_r21_no_filtra_ninguna_de_las_69_formas_de_pago() -> None:
    compacto = _compacto(_sql(RUTA_FORMAS_PAGO))
    cuerpo = _troceado_en_profundidad_cero(
        compacto[compacto.index("CREATE OR REPLACE VIEW compras.formas_pago") :], ";"
    )[0]
    assert "WHERE" not in cuerpo, "las 69 se publican enteras, bajas incluidas (R21)"


def test_f073_r22_el_plazo_se_publica_verbatim() -> None:
    """`30 450R` es un valor REAL del catálogo: no es un número de días."""
    compacto = _compacto(_sql(RUTA_FORMAS_PAGO))
    assert re.search(r"\w+\.formul\s+AS plazo_formula", compacto), (
        "auxpag.formul se publica tal cual, sin transformar (R22)"
    )
    ejecutable = _sin_comentarios(_sql(RUTA_FORMAS_PAGO))
    assert "dias_pago" not in ejecutable, (
        "publicar un dias_pago numérico sería inventar precisión (R22, DA-5)"
    )
    for parseo in ("::int", "::numeric", "to_number", "regexp_", "CAST("):
        assert parseo not in ejecutable, (
            f"{parseo} sobre formul lo estaría interpretando, y no se puede (R22)"
        )


def test_f073_r22_el_comment_avisa_de_que_el_plazo_no_es_un_numero() -> None:
    comentario = _sql(RUTA_FORMAS_PAGO)
    comentario = comentario[comentario.index("COMMENT ON VIEW compras.formas_pago") :]
    assert "no es" in comentario.lower() and "dias" in comentario.lower(), (
        "el COMMENT debe decir que plazo_formula NO es un número de días (R22)"
    )


# ===========================================================================
# Lo que F-073 NO puede tocar · R23, R24, R25 y R26
# ===========================================================================
#
# Tripwires por hash, con el mismo idioma que `tests/test_f042_sql.py`: si el
# fichero cambia, la suite lo dice y obliga a que el cambio sea deliberado y de
# otra feature. Recalcular un hash es una línea; hacerlo sin querer, imposible.

#: `sql/compras/01_documentos.sql` tal como está al entrar F-073. Lo reescribe
#: entera **F-067**, y es ahí donde se recalcula este hash, no aquí (R23).
HASH_01_DOCUMENTOS = "0a3ab862b18a95f8f896ed0f982b78e3af012e7d815b100f86b05094e093f890"

#: Los dos ficheros del SELLO. Tocar una coma fuerza la reconstrucción completa
#: de las 921 obras la noche siguiente (R25).
HASH_06_PRESUPUESTO = "4d89e4b03b99738ace601092cf07764663a9fbc1a1e9761bcca1d0242178270d"
HASH_08_PLAN_MENSUAL = "86f388ed3962932970aae234a55dcdd3730a9f47b83ebbd00f4188556e966361"


def _hash(ruta: Path) -> str:
    import hashlib

    texto = ruta.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_f073_r23_no_toca_el_sql_de_documentos_de_compra() -> None:
    """El cableado de estado y forma de pago a `compras.contratos` es F-067."""
    assert _hash(DIRECTORIO_SQL / "compras" / "01_documentos.sql") == (
        HASH_01_DOCUMENTOS
    ), (
        "F-073 publica la DIMENSIÓN y no hace el cableado: si este fichero "
        "cambia es porque lo está tocando F-067, y el hash se recalcula allí "
        "(R23)"
    )


@pytest.mark.parametrize(
    ("fichero", "esperado"),
    [
        ("06_presupuesto.sql", "HASH_06_PRESUPUESTO"),
        ("08_plan_mensual.sql", "HASH_08_PLAN_MENSUAL"),
    ],
)
def test_f073_r25_no_toca_los_ficheros_del_sello(fichero: str, esperado: str) -> None:
    """Cambiar una coma aquí reconstruye las 921 obras la noche siguiente."""
    assert _hash(DIRECTORIO_SQL / "stg" / fichero) == globals()[esperado], (
        f"{fichero} es del SELLO (FICHEROS_DEL_SELLO en build_stg_step.py). "
        "F-073 lo LEE desde una vista, y leer no cambia su texto (R25)"
    )


def test_f073_r26_no_toca_el_desempate_de_stg_obras() -> None:
    """El `rn = 1` de `03_obras.sql` es de F-053."""
    texto = _sql(DIRECTORIO_SQL / "stg" / "03_obras.sql")
    assert "rn = 1" in texto, "el desempate de F-053 sigue donde estaba (R26)"


@pytest.mark.parametrize(
    "ruta",
    [
        "maestro/01_obras.sql",
        "maestro/04_centros_coste.sql",
        "maestro/05_estados_documento.sql",
        "compras/04_formas_pago.sql",
    ],
)
def test_f073_r24_ningun_sql_de_la_feature_borra_ni_vacia_nada(ruta: str) -> None:
    """R24: solo se AÑADE información. Las 472.890 huérfanas siguen donde están."""
    ejecutable = _sin_comentarios(_sql(DIRECTORIO_SQL / ruta)).upper()
    for verbo in ("DELETE ", "TRUNCATE ", "DROP ", "INSERT ", "UPDATE "):
        assert verbo not in ejecutable, (
            f"F-073 no escribe: {ruta} contiene {verbo.strip()} (R24)"
        )
