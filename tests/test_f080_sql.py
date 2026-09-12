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
# `compras.vencimientos` (05) · R7-R12, R38, R39, R40 y R41
# ===========================================================================

#: Lo que la rejilla de la pestaña «Vencimientos» enseña por efecto, más la
#: factura de la que cuelga y la retención (R8).
COLUMNAS_DEL_EFECTO = (
    "vencimiento_id",
    "factura_id",
    "codigo_factura",
    "codigo_efecto",
    "descripcion_efecto",
    "serie_efecto",
    "fecha_emision",
    "fecha_vencimiento",
    "fecha_real",
    "importe",
    "estado_pago_codigo",
    "estado_pago",
    "efecto_anulado",
    "fecha_anulacion",
    "medio_pago",
    "naturaleza_pago",
    "cuenta_contable",
    "banco",
    "sucursal",
    "retencion_id",
    "remesa_id",
    "codigo_remesa",
    "fecha_remesa",
    "importe_remesa",
)


# --- R7 · el grano y su clave primaria ------------------------------------


def test_f080_r7_los_vencimientos_son_una_TABLA_con_clave_primaria() -> None:
    """Tabla y no vista: la PK hace fallar el build la noche que el grano se rompa.

    Sin ella, una duplicación la descubriría `check-unicidad` un mes después, y
    mientras tanto el importe agregado de `v_facturas_pago` sería falso.
    """
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert "CREATE TABLE compras.vencimientos" in compacto, (
        "`compras.vencimientos` se materializa como tabla (R7)"
    )
    assert "ALTER TABLE compras.vencimientos ADD PRIMARY KEY (vencimiento_id)" in (
        compacto
    ), "la clave primaria va DECLARADA en la tabla, no confiada al origen (R7)"


def test_f080_r7_una_fila_por_fila_de_pag_que_sea_de_factura_de_compra() -> None:
    """195.510 efectos medidos, de los 255.148 de `raw.pag`."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert "FROM raw.pag p" in compacto, "el grano es `raw.pag` (R7)"
    assert re.search(r"(?<!LEFT )JOIN raw\.dcf f ON f\.ide = p\.conide", compacto), (
        "el filtro a factura de compra es el JOIN —no LEFT JOIN— a `raw.dcf` "
        "por `conide`: con LEFT entrarían los efectos de otros documentos, que "
        "son F-037 (R7, R15)"
    )


def test_f080_r15_no_se_asoma_a_los_cobros_ni_a_otros_documentos() -> None:
    """`raw.cob` y la cartera entera son F-037 fase 1, no esta feature."""
    ejecutable = _sin_comentarios(_sql(RUTA_VENCIMIENTOS))
    assert "raw.cob" not in ejecutable, (
        "los efectos de venta son de F-037: aquí solo entra la compra (R15)"
    )
    assert "raw.rco" not in ejecutable, "las remesas de cobro son de F-037 (R41)"


# --- R8 · lo que se expone, y los catálogos a nombre ----------------------


@pytest.mark.parametrize("columna", COLUMNAS_DEL_EFECTO)
def test_f080_r8_expone_lo_que_la_rejilla_ensena(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _ejecutable(RUTA_VENCIMIENTOS)), (
        f"`compras.vencimientos` debe exponer {columna} (R8)"
    )


@pytest.mark.parametrize(
    ("catalogo", "por_que"),
    [
        ("raw.auxefp", "el medio de pago (transferencia, pagaré, confirming)"),
        ("raw.auxnap", "la naturaleza del pago (NOM, EMB, CUO)"),
        ("raw.auxban", "el banco y la sucursal"),
        ("raw.conest", "el estado del efecto"),
    ],
)
def test_f080_r8_cada_catalogo_se_resuelve_a_nombre(catalogo: str, por_que: str) -> None:
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert f"LEFT JOIN {catalogo}" in compacto, (
        f"{por_que} sale de {catalogo}, y con LEFT JOIN para que un código fuera "
        "de catálogo no haga desaparecer el efecto (R8)"
    )


def test_f080_r8_el_banco_y_la_sucursal_se_unen_por_el_ide_de_auxban() -> None:
    """MEDIDO en T1, que es justo lo que «no constaba».

    `pag.banban` y `pag.bansuc` apuntan los dos al **`ide`** de `auxban` —no al
    código de banco—, en dos uniones distintas: casan 110.460 de 110.477 y
    93.273 de 93.273. Unirlos por `cod` daría cero filas resueltas.
    """
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(r"LEFT JOIN raw\.auxban \w+ ON \w+\.ide = NULLIF\(p\.banban, 0\)", compacto), (
        "el banco se resuelve por `auxban.ide` contra `pag.banban` (R8, T1)"
    )
    assert re.search(r"LEFT JOIN raw\.auxban \w+ ON \w+\.ide = NULLIF\(p\.bansuc, 0\)", compacto), (
        "la sucursal es una SEGUNDA unión a `auxban`, por `pag.bansuc` (R8, T1)"
    )


def test_f080_r8_la_cuenta_contable_sale_de_con_y_no_de_cua() -> None:
    """MEDIDO en T1: `raw.cua` no tiene `cod` ni `res`.

    Sus 34.158 filas tienen fila en `raw.con` con `tip = 17`, y ahí viven el
    número de cuenta (`4100006400`) y su nombre. Es la misma trampa de `pag`.
    """
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(r"LEFT JOIN raw\.con \w+ ON \w+\.ide = NULLIF\(p\.cueide, 0\)", compacto), (
        "la cuenta contable del efecto se resuelve contra `raw.con` (R8, T1)"
    )
    assert "raw.cua" not in _sin_comentarios(_sql(RUTA_VENCIMIENTOS)), (
        "unirse a `raw.cua` para sacar el código de cuenta devuelve una columna "
        "vacía: esa tabla no tiene ni `cod` ni `res` (R8, T1)"
    )


# --- R9 · toda fecha entera pasa por `fn_sigrid_date` ---------------------


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        ("p.fecven", "fecha_vencimiento"),
        ("p.fecrea", "fecha_real"),
        ("p.fecreaemi", "fecha_emision"),
    ],
)
def test_f080_r9_las_fechas_del_efecto_se_tipan(origen: str, destino: str) -> None:
    """`fn_sigrid_date` devuelve NULL cuando el entero es 0, que es lo correcto."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert f"compras.fn_sigrid_date({origen}) AS {destino}" in compacto, (
        f"{destino} sale de `compras.fn_sigrid_date({origen})` (R9)"
    )


def test_f080_r9_ninguna_fecha_se_publica_como_entero_crudo() -> None:
    """Un AAAAMMDD suelto se ordena bien y se resta mal."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    for crudo in ("p.fecven AS", "p.fecrea AS", "p.fecreaemi AS", "c.fecbaj AS", "r.fecrem AS"):
        assert crudo not in compacto, (
            f"«{crudo}» publica un entero AAAAMMDD sin tipar (R9)"
        )


# --- R10 y R11 · el estado se LEE, y `fecrea = 0` no es «vivo» ------------


def test_f080_r10_el_estado_sale_de_conest_filtrando_el_tipo_del_efecto() -> None:
    """10 estados medidos para `tip = 25`; el par (tip, est) es único (medido)."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(
        r"LEFT JOIN raw\.conest \w+ ON \w+\.tip = 25 AND \w+\.est = c\.est", compacto
    ), (
        "el estado del efecto se traduce con `raw.conest` filtrando `tip = 25`: "
        "sin el tipo, la misma cifra significa otra cosa en una factura (R10)"
    )
    assert re.search(r"c\.est AS estado_pago_codigo", compacto), (
        "el código del estado se conserva junto al nombre (R10)"
    )


def test_f080_r10_el_estado_NO_se_deriva_de_la_fecha_real() -> None:
    """La 2.ª medición lo tumbó: los dos efectos de `FR26/06051` tienen
    `fecrea = 0` y la pantalla enseña CAR en uno y PDT en el otro."""
    ejecutable = _sin_comentarios(_sql(RUTA_VENCIMIENTOS))
    assert not re.search(r"CASE\s+WHEN[^;]*fecrea", ejecutable, re.I), (
        "derivar el estado de `fecrea` es la hipótesis que la medición tumbó "
        "(DA-8): el estado es `con.est` contra `raw.conest` (R10)"
    )
    assert "p.pun" not in ejecutable, (
        "`pag.pun` vale 0 en los 255.148 efectos: el punteo no distingue nada (R10)"
    )


def test_f080_r11_el_comment_avisa_de_que_fecrea_0_no_significa_vivo() -> None:
    """120.843 de 195.510 efectos de factura (61,8 %) no tienen fecha real.

    Confundirlos con la cartera viva de F-037 (10.607 pagos) da una cifra
    plausible y falsa, así que el aviso viaja con el objeto.
    """
    comentario = _sql(RUTA_VENCIMIENTOS)
    assert "COMMENT ON TABLE compras.vencimientos" in comentario
    comentario = comentario[comentario.index("COMMENT ON TABLE compras.vencimientos"):]
    assert "fecha_real" in comentario and "vivo" in comentario.lower(), (
        "el COMMENT tiene que decir que una fecha real vacía NO significa que el "
        "efecto esté vivo: avisa de la fecha, no del estado (R11)"
    )


# --- R12 · el código y la descripción se LEEN -----------------------------


def test_f080_r12_el_codigo_y_la_descripcion_salen_del_documento_del_efecto() -> None:
    """`FR26/06051_01` y «Pago 1 de 2 …» están ALMACENADOS en `raw.con`."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(r"JOIN raw\.con c ON c\.ide = p\.ide", compacto), (
        "el JOIN al documento DEL EFECTO (`c.ide = p.ide`) es obligatorio: sin "
        "él no hay código, ni descripción, ni estado, ni baja (DA-9)"
    )
    assert "c.cod AS codigo_efecto" in compacto, (
        "`codigo_efecto` es `con.cod` literal, sin componer nada (R12)"
    )
    assert "c.res AS descripcion_efecto" in compacto, (
        "`descripcion_efecto` es `con.res`, la columna «Descripción» de la "
        "rejilla (R12)"
    )


@pytest.mark.parametrize("derivacion", ["row_number", "lpad", "ordinal_efecto"])
def test_f080_r12_no_se_deriva_el_ordinal_del_efecto(derivacion: str) -> None:
    """DA-8: el diseño anterior componía «código de la factura + ordinal». Falso."""
    assert derivacion not in _sin_comentarios(_sql(RUTA_VENCIMIENTOS)).lower(), (
        f"`{derivacion}` reconstruye un código que el origen ya almacena, y "
        "acertaría por casualidad mientras el orden coincidiera (R12, DA-8)"
    )


def test_f080_r12_el_codigo_de_la_factura_sale_de_su_propio_documento() -> None:
    """`cf` es la cabecera; `c` es el efecto. Confundirlos fue el error de DA-9."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(r"LEFT JOIN raw\.con cf ON cf\.ide = f\.ide", compacto)
    assert "cf.cod AS codigo_factura" in compacto


# --- R38 · la serie sale de la función que ya existe ----------------------


def test_f080_r38_la_serie_se_deriva_con_la_funcion_del_repositorio() -> None:
    """`con.serie` existe y vale 0 en los 255.148 efectos (medido).

    La derivación correcta ya está escrita: `compras.fn_serie`, en
    `00_setup.sql`, que usa `01_documentos.sql` desde la tanda C1.
    """
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert "compras.fn_serie(c.cod) AS serie_efecto" in compacto, (
        "`serie_efecto` sale de `compras.fn_serie(c.cod)` (R38)"
    )
    assert "c.serie" not in compacto, (
        "`con.serie` está vacío en los 255.148 efectos: publicarlo daría una "
        "columna de ceros con un nombre convincente (R38, DA-10)"
    )


@pytest.mark.parametrize("parseo", ["substring", "left(", "split_part", "regexp_match"])
def test_f080_r38_no_se_escribe_una_segunda_derivacion_de_la_serie(parseo: str) -> None:
    """Dos derivaciones de la misma cosa divergen; esta ya existe y se reutiliza."""
    assert parseo not in _sin_comentarios(_sql(RUTA_VENCIMIENTOS)).lower(), (
        f"`{parseo}` sobre el código duplicaría `compras.fn_serie` (R38)"
    )


# --- R39 y R40 · la anulación se publica; el origen NO se deduce ----------


def test_f080_r40_la_anulacion_es_la_fecha_de_baja_del_documento() -> None:
    """Medido 8 de 8 contra la captura de `FR25/04222` (T4).

    Los tres efectos que la pantalla pinta en rojo con aspa son exactamente los
    tres con `fecbaj <> 0`, y los cinco vivos suman los 87.854,56 / 92.478,49 de
    la cabecera. El estado NO lo distingue: los tres anulados están «Aprobado».
    """
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(r"\(c\.fecbaj <> 0\) AS efecto_anulado", compacto), (
        "`efecto_anulado` se lee de `con.fecbaj` del documento del efecto (R40)"
    )
    assert "compras.fn_sigrid_date(c.fecbaj) AS fecha_anulacion" in compacto, (
        "la fecha de baja se publica tipada junto a la marca (R40)"
    )


def test_f080_r40_no_se_publica_el_enlace_al_efecto_de_origen() -> None:
    """`pag.padide` vale 0 en los 255.148 efectos: ese enlace no existe."""
    ejecutable = _sin_comentarios(_sql(RUTA_VENCIMIENTOS))
    assert "efecto_origen_id" not in ejecutable, (
        "el enlace hijo → origen no está en el origen, y deducirlo por importes "
        "y fechas no es un dato publicable (R40, DA-10)"
    )
    assert "padide" not in ejecutable, (
        "`pag.padide` está a 0 en toda la tabla: leerlo daría una columna de "
        "ceros (R40)"
    )
    assert not re.search(r"JOIN\s+compras\.vencimientos", ejecutable, re.I), (
        "un autojoin para adivinar el efecto de origen reconstruye una relación "
        "que el origen no tiene (R40)"
    )


def test_f080_r39_el_comment_avisa_de_que_sumarlo_todo_duplica() -> None:
    """76.215 de los 195.510 efectos de factura (39,0 %) están de baja."""
    comentario = _sql(RUTA_VENCIMIENTOS)
    comentario = comentario[comentario.index("COMMENT ON TABLE compras.vencimientos"):]
    assert "efecto_anulado" in comentario, (
        "el COMMENT tiene que decir con qué columna se excluyen los anulados (R39)"
    )
    assert re.search(r"duplic|dos veces|fantasma", comentario, re.I), (
        "sumar los importes de todos los efectos de una factura DUPLICA: nace "
        "con `_01` y `_02`, al dividir el original queda anulado y al remesar se "
        "agrupan. El COMMENT lo tiene que decir (R39)"
    )


# --- R41 · la remesa -------------------------------------------------------


def test_f080_r41_la_remesa_se_resuelve_contra_rpa_por_remide() -> None:
    """40.090 de los 195.510 efectos de factura están en una remesa (medido)."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(r"LEFT JOIN raw\.rpa r ON r\.ide = NULLIF\(p\.remide, 0\)", compacto), (
        "la remesa cuelga de `pag.remide` con LEFT JOIN: los otros 155.420 "
        "efectos salen a NULL y no se pierden (R41)"
    )
    assert "compras.fn_sigrid_date(r.fecrem) AS fecha_remesa" in compacto
    assert re.search(r"r\.imptot[^,]* AS importe_remesa", compacto)


def test_f080_r41_el_codigo_de_la_remesa_se_lee_de_con_porque_rpa_no_lo_tiene() -> None:
    """T1, cuarta vez que asoma la misma trampa: `rpa` es un documento (`tip = 27`).

    Sus 30 columnas medidas no incluyen `cod`. El `RP26/0254` que se ve en
    pantalla vive en `raw.con`, y las 3.919 remesas tienen su fila allí.
    """
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert re.search(r"LEFT JOIN raw\.con \w+ ON \w+\.ide = r\.ide", compacto), (
        "para tener el código de la remesa hay que unir `raw.rpa` con `raw.con` "
        "por el mismo `ide` (R41, T1)"
    )
    assert re.search(r"\w+\.cod AS codigo_remesa", compacto)
    assert not re.search(r"\br\.cod\b", compacto), (
        "`rpa.cod` no existe: leer esa columna no compila (R41, T1)"
    )
