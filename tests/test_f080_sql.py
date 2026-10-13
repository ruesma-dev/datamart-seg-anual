# tests/test_f080_sql.py
"""
F-080 · El SQL nuevo, comprobado sobre su TEXTO.

Ninguno de estos ficheros se puede ejecutar aquí: construyen tablas en un
Postgres **compartido con producción**, y la convención del proyecto es que los
unit tests no toquen red ni BBDD. Lo que sí se puede es fijar por escrito las
decisiones que el diseño tomó midiendo contra Sigrid, de modo que un refactor
que se lleve por delante cualquiera de ellas rompa la suite y no la nocturna.
Mismo criterio que `tests/test_f073_sql.py` y `tests/test_f052_sql.py`.

EL TITULAR QUE SOSTIENE ESTE FICHERO, y que en la exploración se falló dos
veces: **el efecto de pago ES un documento**. `raw.pag` son «Propiedades de
`con`» (`tip = 25`, medido: 0 de 255.148 efectos con otro tipo), así que su
código, su descripción, su estado y su marca de baja se **leen** de `raw.con` /
`raw.conest`; no se derivan. Lo mismo vale para la remesa (`rpa`, `tip = 27`) y
para la cuenta contable (`cua`, `tip = 17`), medidos en la T1 de esta feature.

Los nombres de columna NO se suponen: están medidos el 2026-09-11 en solo
lectura y anotados en `progress/impl_F-080.md`.
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
RUTA_VENCIMIENTOS = DIRECTORIO_SQL / "compras" / "05_vencimientos.sql"


@cache
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


def _ejecutable(ruta: Path) -> str:
    return _compacto(_sql(ruta))


# ===========================================================================
# `compras.vencimientos` (05) · desde F-037, VISTA de `tesoreria.efectos`
#
# La SEMÁNTICA del efecto que estos tests fijaban sobre 05 (R7-R12, R38, R40,
# R41: el efecto es un documento, el estado de `conest` con `tip = 25`, la
# remesa de `rpa` + `con`, la cuenta de `con` y no de `cua`, las fechas tipadas,
# la serie con la función del repositorio...) se mudó con el SQL a
# `tesoreria/01_efectos_completo.sql`, y sus aserciones a
# `tests/test_f037_sql.py` (T5 de F-037). Aquí queda lo que es de la VISTA: que
# lo es, que publica EXACTAMENTE las columnas de la tabla de F-080 y que su
# COMMENT conserva las dos trampas.
# ===========================================================================

#: Las columnas, nombres, orden y TIPOS de la tabla `compras.vencimientos` de
#: F-080, leídos del catálogo de Azure el 2026-10-13 (solo lectura). La vista
#: de F-037 tiene que publicar esta lista tal cual (R15 de F-037): quien la lee
#: hoy —`06_pago_factura.sql`, Power BI, el MCP— no puede notar el cambio.
COLUMNAS_TABLA_F080: tuple[tuple[str, str], ...] = (
    ("vencimiento_id", "integer"),
    ("factura_id", "integer"),
    ("codigo_factura", "character varying(24)"),
    ("codigo_efecto", "character varying(24)"),
    ("descripcion_efecto", "character varying(128)"),
    ("serie_efecto", "text"),
    ("fecha_emision", "date"),
    ("fecha_vencimiento", "date"),
    ("fecha_real", "date"),
    ("importe", "numeric(18,2)"),
    ("estado_pago_codigo", "integer"),
    ("estado_pago", "character varying(48)"),
    ("efecto_anulado", "boolean"),
    ("fecha_anulacion", "date"),
    ("medio_pago_id", "integer"),
    ("medio_pago", "character varying(48)"),
    ("naturaleza_pago_id", "integer"),
    ("naturaleza_pago", "character varying(48)"),
    ("cuenta_contable_id", "integer"),
    ("cuenta_contable", "character varying(24)"),
    ("cuenta_contable_nombre", "character varying(128)"),
    ("banco_id", "integer"),
    ("banco", "character varying(48)"),
    ("sucursal_id", "integer"),
    ("sucursal", "character varying(48)"),
    ("retencion_id", "integer"),
    ("centro_coste_id", "integer"),
    ("remesa_id", "integer"),
    ("codigo_remesa", "character varying(24)"),
    ("fecha_remesa", "date"),
    ("importe_remesa", "numeric"),
)

#: Lo que la rejilla de la pestaña «Vencimientos» enseña por efecto (R8 de F-080).
COLUMNAS_DEL_EFECTO = tuple(nombre for nombre, _tipo in COLUMNAS_TABLA_F080)


def _columnas_de_la_vista() -> list[str]:
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    m = re.search(r"CREATE VIEW compras\.vencimientos AS SELECT (.*?) FROM tesoreria\.efectos", compacto)
    assert m, "05 crea la vista `compras.vencimientos` sobre `tesoreria.efectos`"
    return [trozo.strip().split(" AS ")[-1] for trozo in m.group(1).split(",")]


def test_f080_r7_los_vencimientos_son_una_vista_de_la_cartera_de_f037() -> None:
    """D1 de F-037: la tabla de F-080 pasa a vista; la lógica vive una vez."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert "CREATE VIEW compras.vencimientos AS" in compacto
    assert "CREATE TABLE compras.vencimientos" not in compacto
    assert "FROM tesoreria.efectos WHERE sentido = 'PAGO' AND es_factura_compra;" in compacto


def test_f080_r8_la_vista_publica_las_columnas_de_la_tabla_en_su_orden() -> None:
    assert _columnas_de_la_vista() == list(COLUMNAS_DEL_EFECTO)


@pytest.mark.parametrize("columna", COLUMNAS_DEL_EFECTO)
def test_f080_r8_expone_lo_que_la_rejilla_ensena(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _ejecutable(RUTA_VENCIMIENTOS)), (
        f"`compras.vencimientos` debe exponer {columna} (R8)"
    )


def test_f080_r15_no_se_asoma_a_los_cobros_ni_a_otros_documentos() -> None:
    """La vista es solo la pata de compra: ni cobros ni otros documentos."""
    ejecutable = _sin_comentarios(_sql(RUTA_VENCIMIENTOS))
    assert "raw.cob" not in ejecutable
    assert "raw.rco" not in ejecutable
    assert "sentido = 'PAGO'" in ejecutable and "es_factura_compra" in ejecutable


def test_f080_r11_el_comment_avisa_de_que_fecrea_0_no_significa_vivo() -> None:
    """Confundir «sin fecha real» con «vivo» da una cifra plausible y falsa."""
    comentario = _sql(RUTA_VENCIMIENTOS)
    assert "COMMENT ON VIEW compras.vencimientos" in comentario
    comentario = comentario[comentario.index("COMMENT ON VIEW compras.vencimientos"):]
    assert "fecha_real" in comentario and "vivo" in comentario.lower(), (
        "el COMMENT tiene que decir que una fecha real vacía NO significa que el "
        "efecto esté vivo: avisa de la fecha, no del estado (R11)"
    )


def test_f080_r39_el_comment_avisa_de_que_sumarlo_todo_duplica() -> None:
    comentario = _sql(RUTA_VENCIMIENTOS)
    comentario = comentario[comentario.index("COMMENT ON VIEW compras.vencimientos"):]
    assert "efecto_anulado" in comentario
    assert re.search(r"duplic|dos veces|fantasma", comentario, re.I)


def test_f080_r40_no_se_publica_el_enlace_al_efecto_de_origen() -> None:
    """`pag.padide` vale 0 en todos los efectos: ese enlace no existe."""
    ejecutable = _sin_comentarios(_sql(RUTA_VENCIMIENTOS))
    assert "efecto_origen_id" not in ejecutable
    assert "padide" not in ejecutable
    assert not re.search(r"JOIN\s+compras\.vencimientos", ejecutable, re.I)

# ===========================================================================
# `compras.v_facturas_pago` (06) · R16-R19
# ===========================================================================

RUTA_PAGO_FACTURA = DIRECTORIO_SQL / "compras" / "06_pago_factura.sql"
RUTA_VIEWS_F067 = DIRECTORIO_SQL / "compras" / "03_views.sql"


#: Lo que la cabecera de la factura enseña sobre su pago, más el resumen de
#: sus efectos (R16-R19). `plazo_formula` sale de F-073 tal cual.
COLUMNAS_DEL_PAGO = (
    "factura_id",
    "codigo_factura",
    "fecha_factura",
    "proveedor_id",
    "proveedor_nombre",
    "forma_pago_id",
    "codigo_forma_pago",
    "forma_pago",
    "plazo_formula",
    "formula_pago_documento",
    "condiciones_pago",
    "medio_pago_id",
    "medio_pago",
    "naturaleza_pago",
    "cuenta_contable",
    "cuenta_transferencia_id",
    "banco",
    "sucursal",
    "num_efectos",
    "num_efectos_anulados",
    "num_efectos_pagados",
    "primer_vencimiento",
    "ultimo_vencimiento",
    "importe_efectos_vivos",
    # T13: era `importe_retenido_vivo`, y lo escribió este mismo fichero en su
    # fase RED. Se retira porque NO se ha medido qué significa `pag.retide`
    # —si marca el efecto que ES la retención o el que la tiene—, y publicar un
    # «importe retenido» sobre esa suposición es la cuarta versión del error que
    # esta feature lleva corrigiendo (DA-10). Lo que sí está medido es el estado
    # 10 «Pagado» de `raw.conest`, así que el segundo agregado es ese.
    "importe_efectos_pagados",
)


def test_f080_r16_el_pago_de_la_factura_es_una_vista_por_factura() -> None:
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    assert "CREATE OR REPLACE VIEW compras.v_facturas_pago" in compacto, (
        "el pago de la factura es una VISTA: no hay nada que materializar, la "
        "tabla pesada es `compras.vencimientos` (R16)"
    )
    assert re.search(r"FROM compras\.facturas \w+", compacto), (
        "una fila por factura significa arrancar de `compras.facturas`, no de "
        "sus líneas ni de sus efectos (R16)"
    )


def test_f080_r16_la_forma_de_pago_se_lee_de_la_dimension_de_f073() -> None:
    """R20/DA-7: la dimensión ya existe; levantar una segunda desde `raw.auxpag`
    es exactamente la duplicación que F-073 vino a evitar."""
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    assert re.search(
        r"LEFT JOIN compras\.formas_pago \w+ ON \w+\.forma_pago_id = "
        r"NULLIF\(f\.pagide, 0\)",
        compacto,
    ), "la forma de pago de la factura es `dcf.pagide` contra la dimension (R16)"
    assert "raw.auxpag" not in _sin_comentarios(_sql(RUTA_PAGO_FACTURA)), (
        "`raw.auxpag` es la fuente de `compras.formas_pago` (F-073): leerla "
        "aquí otra vez duplica la dimensión (R16, R20)"
    )


def test_f080_r17_el_plazo_va_verbatim_y_no_se_convierte_en_dias() -> None:
    """`30 450R` es un valor real del catálogo: no es un número de días."""
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    assert re.search(r"\w+\.plazo_formula\s+AS plazo_formula", compacto), (
        "`plazo_formula` se arrastra tal cual desde `compras.formas_pago` (R17)"
    )
    ejecutable = _sin_comentarios(_sql(RUTA_PAGO_FACTURA)).lower()
    for derivacion in ("dias_pago", "plazo_dias", "dias_plazo"):
        assert derivacion not in ejecutable, (
            f"`{derivacion}` inventa precisión sobre una fórmula de Sigrid que "
            "no es un número (R17)"
        )
    assert "plazo_formula::" not in ejecutable, (
        "castear la fórmula a número falla o miente: `30 450R` es real (R17)"
    )


@pytest.mark.parametrize("columna", COLUMNAS_DEL_PAGO)
def test_f080_r18_expone_el_pago_de_la_factura(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _ejecutable(RUTA_PAGO_FACTURA)), (
        f"`compras.v_facturas_pago` debe exponer {columna} (R18, R19)"
    )


@pytest.mark.parametrize(
    ("origen", "catalogo"),
    [
        ("f.cypnatide", "raw.auxnap"),   # naturaleza del pago (NOM, EMB, CUO)
        ("f.efeide", "raw.auxefp"),      # medio de pago
        ("f.banban", "raw.auxban"),      # banco
        ("f.bansuc", "raw.auxban"),      # sucursal
        ("f.cueide", "raw.con"),         # cuenta contable: es un documento
    ],
)
def test_f080_r18_cada_catalogo_de_la_factura_se_resuelve_a_nombre(
    origen: str, catalogo: str
) -> None:
    """Los mismos catálogos que el efecto, y por la misma clave medida en T1."""
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    patron = (
        rf"LEFT JOIN {re.escape(catalogo)} \w+ ON \w+\.ide = "
        rf"NULLIF\({re.escape(origen)}, 0\)"
    )
    assert re.search(patron, compacto), (
        f"{origen} se resuelve contra {catalogo} por su `ide`, con LEFT JOIN "
        "para no perder la factura si el código está fuera de catálogo (R18)"
    )


def test_f080_r18_las_condiciones_y_la_formula_del_documento_van_tal_cual() -> None:
    """F-066 ya ingirió `dcf.pagtex`: son las condiciones escritas a mano.

    «Tal cual» y `NULLIF(x, '')` no se contradicen: el `NULLIF` no recorta ni
    reescribe ningún valor, solo manda la cadena vacía a NULL. Se exige, y no
    solo se tolera, porque las dos fichas declaran `nulo_significa` y
    `raw.dcf` entra por `JOIN` —no por `LEFT JOIN`—: sin él, el guardián de
    nulos de F-006 (`test_f006_r2_un_nulo_declarado_tiene_que_ser_posible`)
    prueba que la ficha promete un NULL que nunca llega.
    """
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    assert re.search(r"NULLIF\(f\.pagfor, ''\) AS formula_pago_documento", compacto), (
        "la fórmula que la propia factura guarda (`dcf.pagfor`) se publica "
        "aparte de la del catálogo: pueden no coincidir (R18)"
    )
    assert re.search(r"NULLIF\(f\.pagtex, ''\) AS condiciones_pago", compacto), (
        "`dcf.pagtex` son las condiciones de pago del documento (R18)"
    )


def test_f080_r19_el_resumen_de_efectos_agrega_ANTES_de_unir() -> None:
    """Unir primero y agregar después multiplica la cabecera por sus efectos:
    una factura con 16 efectos (el máximo medido) saldría 16 veces."""
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    assert re.search(r"WITH \w+ AS \( SELECT factura_id", compacto), (
        "el resumen entra por un CTE que arranca agrupando por `factura_id` (R19)"
    )
    assert "FROM compras.vencimientos GROUP BY factura_id" in compacto, (
        "el CTE agrega `compras.vencimientos` por factura ANTES de unirse a la "
        "cabecera: agregar después rompe el grano (R19)"
    )
    # El `(?: \w+)?` es el alias del CTE, que la primera versión de este assert
    # se dejó fuera (T13): el CTE se une como `LEFT JOIN efectos e ON ...`.
    assert re.search(
        r"LEFT JOIN \w+(?: \w+)? ON \w+\.factura_id = \w+\.factura_id", compacto
    ), (
        "y se une con LEFT JOIN: las facturas sin efectos medidas no se pueden "
        "perder (R19)"
    )


def test_f080_r19_ningun_importe_agregado_suma_los_efectos_de_baja() -> None:
    """LA TRAMPA CARA DE ESTA FEATURE (R39, R40).

    89.228 de 255.148 efectos están de baja, 76.215 de los 195.510 de factura.
    Un `SUM(importe)` sin filtrar suma el original anulado junto con los hijos
    de la división: sobre `FR25/04222` daría 288.123,92 en vez de 92.478,49,
    y los dos números parecen igual de plausibles.
    """
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    sumas = re.findall(r"SUM\(", compacto)
    filtradas = re.findall(r"SUM\([^)]*\) FILTER \(WHERE NOT efecto_anulado", compacto)
    assert sumas, "el resumen tiene que traer importes agregados (R19)"
    assert len(filtradas) == len(sumas), (
        f"{len(sumas) - len(filtradas)} de los {len(sumas)} SUM del resumen no "
        "filtran `NOT efecto_anulado`: ese importe es un fantasma (R19, R39)"
    )


# ===========================================================================
# `compras.v_control_forma_pago` (06) · R28, R29
# ===========================================================================

#: La expresión de enlace factura → contrato, tal y como la escribió F-067 en
#: `compras.v_pbi_contrato_consumo`. NO se reescribe: se copia.
ENLACE_FACTURA_CONTRATO = (
    "COALESCE(fl.contrato_id_directo, alb.contrato_id, alb_l.contrato_id_linea)"
)


def test_f080_r28_el_enlace_a_contrato_es_LITERALMENTE_el_de_f067() -> None:
    """Dos reglas de enlace para la misma cosa divergen, y la segunda siempre
    se descubre cuando las dos cifras ya están en un informe."""
    assert ENLACE_FACTURA_CONTRATO in _ejecutable(RUTA_VIEWS_F067), (
        "el enlace de referencia vive en `03_views.sql`; si ha cambiado de "
        "forma, es ahí donde hay que mirar antes de tocar F-080 (R28)"
    )
    assert ENLACE_FACTURA_CONTRATO in _ejecutable(RUTA_PAGO_FACTURA), (
        "`v_control_forma_pago` usa la MISMA expresión que "
        "`v_pbi_contrato_consumo`, no una nueva (R28)"
    )


def test_f080_r28_el_grano_es_el_par_factura_contrato() -> None:
    """Una factura puede tener líneas de varios contratos: el grano es el par,
    y el DISTINCT es lo que evita una fila por línea."""
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    assert "CREATE OR REPLACE VIEW compras.v_control_forma_pago" in compacto
    assert re.search(r"SELECT DISTINCT \w*\.?factura_id", compacto), (
        "sin DISTINCT el grano son las LÍNEAS de la factura, no el par (R28)"
    )


def test_f080_r28_la_forma_de_pago_del_contrato_se_lee_de_raw_ctr() -> None:
    """`compras.contratos` no la publica: eso es F-067 (R21)."""
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    assert re.search(r"LEFT JOIN raw\.ctr \w+ ON \w+\.ide = ", compacto), (
        "la forma de pago del contrato está en `raw.ctr.pagide` (R28)"
    )
    assert "pagide, 0)" in compacto, (
        "y se resuelve contra `compras.formas_pago` como la de la factura (R28)"
    )


@pytest.mark.parametrize(
    "columna",
    [
        "factura_id",
        "codigo_factura",
        "contrato_id",
        "codigo_contrato",
        "obra_id",
        "proveedor_nombre",
        "forma_pago_factura",
        "forma_pago_contrato",
        "plazo_formula_factura",
        "plazo_formula_contrato",
        "forma_pago_coincide",
    ],
)
def test_f080_r29_el_control_enfrenta_las_dos_formas_de_pago(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _ejecutable(RUTA_PAGO_FACTURA)), (
        f"el control debe exponer {columna} (R28, R29)"
    )


def test_f080_r29_las_que_cuadran_tambien_salen() -> None:
    """Filtrar a las discrepancias convierte la vista en una alarma y deja sin
    respuesta «cuántas cuadran»: el numerador sin denominador no vale.

    ESTE ASSERT SE CORRIGIÓ EN T13, y el motivo vale más que el assert: la
    primera versión buscaba `WHERE[^;]*coincide` sobre el bloque entero, y eso
    lo cumple **cualquier** implementación correcta —el `WHERE ... IS NOT NULL`
    del CTE del enlace queda antes de la columna `forma_pago_coincide` y no hay
    `;` entre los dos—. Era un test que no podía pasar, no una puerta. Se
    sustituye por los filtros concretos que R29 prohíbe.
    """
    compacto = _ejecutable(RUTA_PAGO_FACTURA)
    bloque = compacto[compacto.index("compras.v_control_forma_pago"):]
    for filtro in (
        "WHERE NOT forma_pago_coincide",
        "forma_pago_coincide = false",
        "forma_pago_coincide IS FALSE",
        "HAVING",
    ):
        assert filtro not in bloque, (
            f"«{filtro}» deja fuera las facturas que cuadran: la vista marca la "
            "coincidencia, no la filtra (R29)"
        )
    assert not re.search(r"WHERE[^;]*\w+\.pagide <> \w+\.pagide", bloque), (
        "enfrentar las formas de pago en el WHERE es filtrar por discrepancia "
        "con otro nombre (R29)"
    )


# ===========================================================================
# R21 · lo que F-080 NO toca
# ===========================================================================


@pytest.mark.parametrize(
    "fichero", ["01_documentos.sql", "02_fact_linea.sql", "03_views.sql"]
)
def test_f080_r21_los_ficheros_de_f067_no_publican_nada_de_f080(fichero: str) -> None:
    """F-067 reescribe esos tres ficheros enteros: meter ahí una columna de
    F-080 es programar un conflicto para dentro de dos semanas (R21, DA-7).

    **Mira el SQL EJECUTABLE, no los comentarios** (ajuste de F-083, 2026-09-16).
    Lo que R21 prohíbe es PUBLICAR aquí un objeto de F-080; *nombrarlo en un
    comentario* es lo contrario, y es justo lo que hace falta: el estado que
    F-083 añade a `compras.facturas` solo se entiende diciendo que **no** es el
    `estado_pago` de `compras.vencimientos`, que es la confusión que originó
    esa feature. Un guardián que se dispara con la prosa empuja a callar la
    advertencia para no verlo en rojo, y ahí perdería la suite dos veces.
    """
    texto = _sin_comentarios(_sql(DIRECTORIO_SQL / "compras" / fichero))
    for objeto in (
        "v_facturas_pago",
        "v_control_forma_pago",
        "compras.vencimientos",
        "documento_texto",
        "documento_comentarios",
    ):
        assert objeto not in texto, (
            f"{objeto} es de F-080 y se publica en su propio fichero, no en "
            f"{fichero}, que es de F-067 (R21)"
        )


@pytest.mark.parametrize(
    "objeto", ["compras.facturas", "compras.contratos", "compras.factura_lineas"]
)
def test_f080_r21_f080_no_redefine_las_tablas_de_f067(objeto: str) -> None:
    """Las lee; no las reescribe ni les añade columnas (DA-7)."""
    for ruta in (RUTA_VENCIMIENTOS, RUTA_PAGO_FACTURA):
        ejecutable = _sin_comentarios(_sql(ruta))
        assert f"CREATE TABLE {objeto}" not in ejecutable
        assert f"ALTER TABLE {objeto}" not in ejecutable, (
            f"añadir columnas a {objeto} mete a F-080 dentro de "
            "`01_documentos.sql`, que es de F-067 (R21, DA-7)"
        )


# ===========================================================================
# `compras.documento_texto` y `compras.documento_comentarios` (07) · R22-R25
# ===========================================================================

RUTA_TEXTO = DIRECTORIO_SQL / "compras" / "07_texto.sql"


def test_f080_r22_el_memo_integro_es_una_TABLA_con_su_clave() -> None:
    """Tabla y no vista porque el memo se lee muchas veces y filtrar `raw.con`
    (2,18 M filas) en cada consulta es caro."""
    compacto = _ejecutable(RUTA_TEXTO)
    assert "CREATE TABLE compras.documento_texto AS" in compacto, (
        "`compras.documento_texto` se materializa en la nocturna (R22)"
    )
    assert "ALTER TABLE compras.documento_texto ADD PRIMARY KEY (documento_id)" in (
        compacto
    ), "un documento, una fila: la clave va declarada (R22)"


@pytest.mark.parametrize(
    "columna",
    [
        "documento_id",
        "tipo_documento",
        "codigo_documento",
        "texto",
        "bytes",
        "num_comentarios",
    ],
)
def test_f080_r22_el_memo_se_publica_con_su_tamano_y_su_recuento(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _ejecutable(RUTA_TEXTO)), (
        f"`compras.documento_texto` debe exponer {columna} (R22)"
    )


def test_f080_r22_el_memo_sale_de_con_tex_y_solo_de_facturas_y_contratos() -> None:
    """MEDIDO (R2): la pestaña «Texto» es `con.tex` (65,5 % de las facturas), no
    `dcf.tex` (0,3 %). Y los comparativos (`tip = 46`) son de F-067."""
    compacto = _ejecutable(RUTA_TEXTO)
    assert "FROM raw.con c" in compacto, "el memo vive en la superclase `con` (R22)"
    assert "c.tip IN (15, 44)" in compacto, (
        "solo facturas (15) y contratos (44): los comparativos son de F-067 (R22)"
    )
    ejecutable = _sin_comentarios(_sql(RUTA_TEXTO))
    for tabla in ("raw.dcf", "raw.ctr"):
        assert tabla not in ejecutable, (
            f"`{tabla}.tex` está informado en menos del 4 % de los documentos: "
            "la pestaña se pinta desde `con.tex` (R2, R22)"
        )


def test_f080_r22_los_documentos_sin_texto_no_generan_fila() -> None:
    """2,06 M de documentos no tienen memo: publicarlos daría una tabla con un
    millón de filas vacías y un recuento inútil."""
    compacto = _ejecutable(RUTA_TEXTO)
    assert "c.tex IS NOT NULL" in compacto, (
        "el filtro de texto informado es obligatorio (R22)"
    )
    assert re.search(r"btrim\(c\.tex[^)]*\) <> ''", compacto), (
        "y un memo de solo espacios tampoco es un memo: el mismo criterio que "
        "`partir_memo`, que devuelve lista vacía (R22)"
    )


def test_f080_r23_los_comentarios_son_una_TABLA_y_no_una_vista() -> None:
    """DA-6: son ~110.000 memos; partirlos en cada lectura es trabajo repetido
    para siempre. El humano lo zanjó: «guárdala como tabla y como texto»."""
    compacto = _ejecutable(RUTA_TEXTO)
    assert "CREATE TABLE compras.documento_comentarios AS" in compacto, (
        "`compras.documento_comentarios` se materializa en el build (R23)"
    )
    assert "VIEW compras.documento_comentarios" not in compacto, (
        "era una vista en el diseño anterior y dejó de serlo (R23, DA-6)"
    )
    assert (
        "ALTER TABLE compras.documento_comentarios ADD PRIMARY KEY "
        "(documento_id, orden)" in compacto
    ), "la clave es el par (documento, orden), declarada en la tabla (R23)"


def test_f080_r23_los_comentarios_se_parten_sobre_la_tabla_del_memo() -> None:
    """Volver a `raw.con` sería filtrar 2,18 M de filas dos veces en el mismo
    build, y con dos filtros que pueden divergir."""
    compacto = _ejecutable(RUTA_TEXTO)
    assert "FROM compras.documento_texto" in compacto, (
        "los comentarios se parten desde `compras.documento_texto` (R23)"
    )
    assert "regexp_split_to_table" in compacto and "WITH ORDINALITY" in compacto, (
        "`orden` sale de `WITH ORDINALITY` sobre el corte del memo (R23)"
    )


def test_f080_r23_el_orden_no_se_invierte_en_ningun_sitio() -> None:
    """Sigrid concatena el más reciente arriba y el corte conserva ese orden:
    `orden` 1 es el más nuevo. Un `DESC` por ahí pondría el comentario de alta
    como si fuera el último estado del documento."""
    compacto = _ejecutable(RUTA_TEXTO)
    # `\bDESC\b` y no « DESC»: la primera versión de este assert (T16) buscaba
    # la subcadena, y « DESCENDENTE» del propio COMMENT la contiene. Prohibir la
    # palabra clave es lo que se quería; prohibir el prefijo era prohibir hablar.
    assert not re.search(r"\bDESC\b", compacto.upper()), (
        "ordenar al revés invierte el significado de `orden` (R23)"
    )


def test_f080_r23_el_orden_se_renumera_para_no_dejar_huecos() -> None:
    """`WITH ORDINALITY` numera ANTES de tirar los trozos vacíos, así que un
    memo que empieza por un separador dejaría su primer comentario real en
    `orden` 2 y la tabla no tendría ningún `orden` 1.

    El oráculo (`partir_memo`) numera después de filtrar, y las dos
    implementaciones tienen que coincidir o la comparación no vale de nada.
    """
    compacto = _ejecutable(RUTA_TEXTO)
    assert re.search(r"row_number\(\) OVER \(PARTITION BY \w+\.documento_id", compacto), (
        "el `orden` publicado se renumera por documento sobre el orden del "
        "corte, para que siempre empiece en 1 (R23)"
    )


def test_f080_r23_el_comment_dice_que_el_orden_1_es_el_mas_reciente() -> None:
    """Sin ese aviso, «el último comentario» se lee como el de `orden` más alto,
    que es exactamente el más viejo."""
    comentario = _sql(RUTA_TEXTO)
    assert "COMMENT ON TABLE compras.documento_comentarios" in comentario
    comentario = comentario[
        comentario.index("COMMENT ON TABLE compras.documento_comentarios"):
    ]
    assert re.search(r"orden 1[^.]*recient", comentario, re.I), (
        "el COMMENT tiene que decir que `orden` 1 es el comentario MÁS "
        "RECIENTE (R23)"
    )


# --- R24 · los literales son los del módulo de dominio --------------------


def test_f080_r24_el_sql_usa_LOS_MISMOS_literales_que_el_oraculo() -> None:
    """LA RAZÓN DE SER DE `domain/texto_comentarios.py` (R24, DA-1).

    El parseo se ejecuta en SQL, pero el separador y el sello están escritos
    **una sola vez**, en el módulo de dominio, donde hay tests que los
    ejercitan sobre fixtures. Si el SQL escribiera los suyos, las dos
    implementaciones divergirían y nadie se enteraría: el oráculo seguiría en
    verde mientras la tabla publica otra cosa.
    """
    from etl_sigrid.domain.texto_comentarios import (
        SELLO_COMENTARIO,
        SEPARADOR_BLOQUES,
    )

    sql = _sql(RUTA_TEXTO)
    assert SEPARADOR_BLOQUES in sql, (
        f"el separador del SQL tiene que ser LITERALMENTE {SEPARADOR_BLOQUES!r}, "
        "el del módulo de dominio (R24)"
    )
    assert SELLO_COMENTARIO in sql, (
        f"el sello del SQL tiene que ser LITERALMENTE {SELLO_COMENTARIO!r} (R24)"
    )


def test_f080_r24_el_sql_no_cablea_los_33_guiones_medidos() -> None:
    """DA-3: lo medido son 33 guiones, pero nada lo garantiza. El patrón es
    tolerante (tres o más) y el literal cableado sería una bomba de relojería."""
    ejecutable = _sin_comentarios(_sql(RUTA_TEXTO))
    assert "-" * 10 not in ejecutable, (
        "una tirada de guiones cableada en el SQL ejecutable es el separador "
        "escrito a mano por segunda vez (R24, DA-3)"
    )


# --- R25 · el bloque que no casa se publica igual -------------------------


@pytest.mark.parametrize(
    "columna",
    ["documento_id", "orden", "sello_reconocido", "fecha", "hora", "usuario", "cuerpo", "bloque"],
)
def test_f080_r25_cada_comentario_publica_autoria_y_cuerpo(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _ejecutable(RUTA_TEXTO)), (
        f"`compras.documento_comentarios` debe exponer {columna} (R23, R25)"
    )


def test_f080_r25_sin_sello_se_publica_el_bloque_entero_como_cuerpo() -> None:
    """R25 y DA-2: el sello solo AÑADE columnas, no recorta. Texto escrito a
    mano, la línea automática de la aplicación o un sello a medias salen
    igual, con la autoría a NULL."""
    compacto = _ejecutable(RUTA_TEXTO)
    assert "regexp_match(" in compacto, (
        "el sello se reconoce con `regexp_match`, que devuelve NULL cuando no "
        "casa; eso es la rama de R25"
    )
    assert re.search(r"ELSE \w+\.bloque END AS cuerpo", compacto), (
        "cuando el sello no casa, el CUERPO es el bloque ENTERO (R25)"
    )
    for columna in ("fecha", "hora", "usuario"):
        assert f"END AS {columna}" in compacto, (
            f"`{columna}` sale de una rama condicionada al sello: sin sello va "
            "a NULL, no a un valor inventado (R25)"
        )
    assert "desconocido" not in compacto.lower(), (
        "rellenar el usuario ausente con una etiqueta lo convierte en un dato "
        "falso; NULL dice la verdad (R25)"
    )


def test_f080_r25_una_fecha_imposible_no_cuenta_como_sello() -> None:
    """`31/02/2026` casa con el patrón y no es una fecha.

    El oráculo la descarta con `strptime`; el SQL, con la comprobación de ida y
    vuelta. Publicarla normalizada a marzo sería inventarse el día en que
    alguien escribió el comentario.
    """
    compacto = _ejecutable(RUTA_TEXTO)
    assert re.search(r"to_char\([^;]{0,120}'DD/MM/YYYY'\) = ", compacto), (
        "la validación de ida y vuelta de la fecha del sello es lo que iguala "
        "el SQL con el oráculo de `partir_memo` (R25)"
    )


def test_f080_r26_el_bloque_integro_se_publica_para_poder_reconstruir() -> None:
    """R26: unir los bloques en su orden reproduce el memo original. Si la tabla
    solo publicara el cuerpo recortado, esa verificación sería imposible."""
    compacto = _ejecutable(RUTA_TEXTO)
    assert re.search(r"\w+\.bloque\s+AS bloque", compacto), (
        "el bloque íntegro se publica aparte del cuerpo: es lo que permite la "
        "prueba reconstructiva (R26, DA-2)"
    )
