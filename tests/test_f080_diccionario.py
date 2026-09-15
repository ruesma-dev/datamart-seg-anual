# tests/test_f080_diccionario.py
"""
F-080 · Las fichas de los cinco objetos nuevos de `compras` (R31, R32, R35).

`config/diccionario/` es lo que el MCP lee por SQL antes de contestar, y quien
lo lee es un agente que **no puede preguntar**. Una ficha que no declara la
trampa de su objeto no es documentación incompleta: es la garantía de que
alguien dará una cifra plausible y falsa con toda la confianza del mundo.

Y esta feature tiene la trampa más cara del datamart hasta la fecha: **sumar
los importes de todos los efectos de una factura los cuenta hasta tres veces**,
porque el efecto original que se dividió sigue en la tabla, anulado, junto a sus
hijos. Sobre `FR25/04222` son 288.123,92 contra los 92.478,49 que Sigrid enseña.
Los dos números son igual de creíbles y solo uno es cierto.

Ningún test toca red ni BBDD: se lee el YAML del árbol.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from tests._texto import normalizado

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: Las columnas de cada objeto nuevo, EN EL ORDEN en que las publica su SQL.
#: La lista completa a propósito: R31 exige el significado de **cada** columna,
#: y una columna sin ficha es una columna que el agente interpretará a ojo.
COLUMNAS_PUBLICADAS = {
    "compras.vencimientos": (
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
        "medio_pago_id",
        "medio_pago",
        "naturaleza_pago_id",
        "naturaleza_pago",
        "cuenta_contable_id",
        "cuenta_contable",
        "cuenta_contable_nombre",
        "banco_id",
        "banco",
        "sucursal_id",
        "sucursal",
        "retencion_id",
        "centro_coste_id",
        "remesa_id",
        "codigo_remesa",
        "fecha_remesa",
        "importe_remesa",
    ),
    "compras.v_facturas_pago": (
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
        "importe_efectos_pagados",
    ),
    "compras.v_control_forma_pago": (
        "factura_id",
        "codigo_factura",
        "fecha_factura",
        "contrato_id",
        "codigo_contrato",
        "obra_id",
        "codigo_obra",
        "proveedor_id",
        "proveedor_nombre",
        "forma_pago_factura_id",
        "forma_pago_factura",
        "plazo_formula_factura",
        "forma_pago_contrato_id",
        "forma_pago_contrato",
        "plazo_formula_contrato",
        "forma_pago_comparable",
        "forma_pago_coincide",
    ),
    "compras.documento_texto": (
        "documento_id",
        "tipo_documento_codigo",
        "tipo_documento",
        "codigo_documento",
        "texto",
        "bytes",
        "num_comentarios",
    ),
    "compras.documento_comentarios": (
        "documento_id",
        "orden",
        "sello_reconocido",
        "fecha",
        "hora",
        "usuario",
        "cuerpo",
        "bloque",
        "bytes",
    ),
}

#: Las tres tablas que F-080 dio de alta en la ingesta (T6, R3 y R6).
TABLAS_RAW_NUEVAS = ("raw.auxnap", "raw.auxban", "raw.rpa")


@lru_cache(maxsize=1)
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _ficha(nombre: str):
    for ficha in _diccionario().fichas:
        if ficha.nombre == nombre:
            return ficha
    return None


def _columna(nombre_objeto: str, nombre_columna: str):
    ficha = _ficha(nombre_objeto)
    assert ficha is not None, f"no hay ficha de {nombre_objeto}"
    for columna in ficha.columnas:
        if columna.nombre == nombre_columna:
            return columna
    return None


def _texto_de(ficha) -> str:
    """Todo lo que la ficha dice, en una sola cadena normalizada."""
    partes = [ficha.descripcion, ficha.grano or ""]
    partes += [c.significado or "" for c in ficha.columnas]
    partes += [c.nulo_significa or "" for c in ficha.columnas]
    return normalizado(" ".join(partes))


# ---------------------------------------------------------------------------
# R31 · los cinco objetos, con clave declarada y todas sus columnas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("objeto", sorted(COLUMNAS_PUBLICADAS))
def test_f080_r31_cada_objeto_nuevo_tiene_ficha_con_clave_y_grano(objeto: str) -> None:
    ficha = _ficha(objeto)

    assert ficha is not None, (
        f"{objeto} se publica en la base y no tiene ficha: el agente lo verá en "
        "el catálogo y se inventará su significado (R31)"
    )
    assert ficha.clave_negocio, (
        f"la ficha de {objeto} tiene que DECLARAR su clave: sin ella, nadie "
        "sabe si contar filas cuenta facturas, efectos o pares (R31)"
    )
    assert normalizado(ficha.grano or "").strip(), (
        f"{objeto} necesita declarar su grano por escrito (R31)"
    )
    assert ficha.consumo_recomendado, (
        f"{objeto} se publica para ser consultado: si no se recomienda, no se "
        "publica"
    )


@pytest.mark.parametrize(
    ("objeto", "columnas"), sorted((k, v) for k, v in COLUMNAS_PUBLICADAS.items())
)
def test_f080_r31_la_ficha_describe_TODAS_sus_columnas(
    objeto: str, columnas: tuple[str, ...]
) -> None:
    ficha = _ficha(objeto)
    assert ficha is not None, f"no hay ficha de {objeto}"

    assert tuple(c.nombre for c in ficha.columnas) == columnas, (
        f"la ficha de {objeto} tiene que describir sus columnas, todas y en el "
        "orden en que el SQL las publica"
    )
    sin_significado = [
        c.nombre for c in ficha.columnas if not normalizado(c.significado or "").strip()
    ]
    assert not sin_significado, (
        f"columnas de {objeto} con nombre y sin significado: {sin_significado}"
    )


@pytest.mark.parametrize("tabla", TABLAS_RAW_NUEVAS)
def test_f080_r6_las_tres_tablas_nuevas_de_raw_tienen_ficha_con_clave(tabla: str) -> None:
    """T6 las dio de alta en la ingesta; sin ficha, `raw` crece a escondidas."""
    ficha = _ficha(tabla)

    assert ficha is not None, f"{tabla} se ingiere y no tiene ficha (R6)"
    assert ficha.clave_negocio, f"la ficha de {tabla} no declara su clave (R6)"


# ---------------------------------------------------------------------------
# R10 y R11 · el estado se LEE, y una fecha real vacía no es «vivo»
# ---------------------------------------------------------------------------


def test_f080_r10_la_ficha_dice_que_el_estado_se_lee_de_conest_con_su_tipo() -> None:
    """La 2.ª medición tumbó la derivación desde `fecrea`: los dos efectos de
    `FR26/06051` la tienen a 0 y la pantalla enseña CAR en uno y PDT en otro."""
    columna = _columna("compras.vencimientos", "estado_pago")
    assert columna is not None
    texto = normalizado(columna.significado or "")

    assert "conest" in texto, "hay que decir de dónde se lee el estado (R10)"
    assert "25" in texto, (
        "y con qué tipo se traduce: sin `tip = 25`, la misma cifra significa "
        "otra cosa en una factura (R10)"
    )
    assert "10" in texto, "los 10 estados medidos (R10)"


def test_f080_r11_la_ficha_avisa_de_que_fecha_real_vacia_no_es_vivo() -> None:
    """120.843 de 195.510 efectos de factura (61,8 %) no tienen fecha real, y la
    cartera viva que midió F-037 son 10.607 pagos. Confundirlos da una cifra
    plausible y falsa, doce veces mayor que la verdadera."""
    columna = _columna("compras.vencimientos", "fecha_real")
    assert columna is not None
    texto = normalizado((columna.significado or "") + " " + (columna.nulo_significa or ""))

    assert "120.843" in texto, "la cifra medida de efectos sin fecha real (R11)"
    assert "10.607" in texto, (
        "y la de la cartera viva de F-037, que es con la que se va a confundir "
        "(R11)"
    )
    assert "vivo" in texto.lower(), (
        "la ficha tiene que decir con esas palabras que NO significa «vivo» (R11)"
    )


# ---------------------------------------------------------------------------
# R39 y R40 · la trampa que duplica, y el enlace que no se publica
# ---------------------------------------------------------------------------


def test_f080_r39_la_ficha_avisa_de_que_sumar_todos_los_efectos_duplica() -> None:
    texto = _texto_de(_ficha("compras.vencimientos"))

    assert "89.228" in texto and "255.148" in texto, (
        "las dos cifras de la anulación, medidas el 2026-09-11: 89.228 de "
        "255.148 efectos están de baja (R39)"
    )
    assert "76.215" in texto and "195.510" in texto, (
        "y las de los efectos de FACTURA, que es el grano de esta tabla: 76.215 "
        "de 195.510, el 39 % (R39)"
    )
    assert "efecto_anulado" in texto, (
        "hay que decir CON QUÉ COLUMNA se excluyen, no solo que hay que "
        "excluirlos (R39, R40)"
    )
    assert any(p in texto.lower() for p in ("duplic", "dos veces", "tres veces")), (
        "y que sumarlos todos duplica: el porqué va con la instrucción (R39)"
    )


def test_f080_r40_la_ficha_explica_por_que_no_hay_enlace_al_efecto_de_origen() -> None:
    """Sin esta frase, el siguiente que mire la tabla buscará ese enlace, lo
    deducirá por importes y fechas, y publicará una reconstrucción como dato."""
    texto = _texto_de(_ficha("compras.vencimientos"))

    assert "padide" in texto, (
        "el campo que promete y no cumple se nombra: `pag.padide` (R40, DA-10)"
    )
    assert "0" in texto and "no se publica" in texto.lower(), (
        "y se dice que por eso NO SE PUBLICA el enlace al efecto de origen (R40)"
    )


def test_f080_r38_la_ficha_de_la_serie_dice_de_donde_sale() -> None:
    """`con.serie` existe y vale 0 en los 255.148 efectos: quien lo mire creerá
    que es esa columna."""
    columna = _columna("compras.vencimientos", "serie_efecto")
    assert columna is not None
    texto = normalizado(columna.significado or "")

    assert "fn_serie" in texto, "la serie se deriva con `compras.fn_serie` (R38)"
    assert "serie" in texto and "0" in texto, (
        "y hay que decir que la columna de serie del origen está vacía, o el "
        "siguiente la usará (R38, DA-10)"
    )


# ---------------------------------------------------------------------------
# R28 y R30 · el grano del control y las facturas que quedan fuera
# ---------------------------------------------------------------------------


def test_f080_r28_la_ficha_del_control_declara_que_el_grano_es_el_par() -> None:
    """Una factura con líneas de dos contratos sale dos veces: contar filas de
    esta vista NO cuenta facturas."""
    ficha = _ficha("compras.v_control_forma_pago")
    assert ficha is not None
    assert [c.lower() for c in ficha.clave_negocio] == ["factura_id", "contrato_id"], (
        "la clave declarada es el PAR (factura, contrato) (R28)"
    )
    texto = normalizado(ficha.grano or "")
    assert "par" in texto.lower(), "y el grano lo dice con esa palabra (R28)"


def test_f080_r30_la_ficha_del_control_dice_cuantas_facturas_se_quedan_fuera() -> None:
    """85.324 de 165.759 facturas de compra (51,5 %) no cuelgan de ningún
    contrato. Sin esa cifra, esta vista parece el censo de la compra y es la
    mitad."""
    texto = _texto_de(_ficha("compras.v_control_forma_pago"))

    assert "85.324" in texto and "165.759" in texto, (
        "las dos cifras medidas de las facturas sin contrato (R30)"
    )
    assert "51,5" in texto, "y el porcentaje, que es lo que se recuerda (R30)"


def test_f080_r29_la_ficha_dice_que_la_vista_no_filtra_las_que_cuadran() -> None:
    texto = _texto_de(_ficha("compras.v_control_forma_pago")).lower()

    assert "no filtra" in texto or "no se filtra" in texto, (
        "quien la use para contar discrepancias tiene que saber que el "
        "denominador está dentro (R29)"
    )


def test_f080_r17_el_plazo_de_la_factura_sigue_sin_ser_un_numero() -> None:
    """La trampa de F-073 viaja con el dato: si `v_facturas_pago` no la repite,
    quien lea esta vista no verá nunca la ficha del catálogo."""
    columna = _columna("compras.v_facturas_pago", "plazo_formula")
    assert columna is not None
    texto = normalizado(columna.significado or "")

    assert "30 450R" in texto, "el valor real del catálogo es el argumento (R17)"
    assert "no es" in texto.lower(), (
        "hay que decir explícitamente que NO es un número de días (R17)"
    )


def test_f080_r19_la_ficha_dice_que_los_importes_agregados_ya_filtran() -> None:
    """Y, sobre todo, que `num_efectos` NO filtra: son criterios distintos en la
    misma fila, y confundirlos hace que la resta no cuadre."""
    ficha = _ficha("compras.v_facturas_pago")
    assert ficha is not None
    vivos = _columna("compras.v_facturas_pago", "importe_efectos_vivos")
    assert vivos is not None
    assert "efecto_anulado" in normalizado(vivos.significado or ""), (
        "el importe agregado tiene que decir que excluye los anulados (R19)"
    )
    total = _columna("compras.v_facturas_pago", "num_efectos")
    assert total is not None
    assert "anulad" in normalizado(total.significado or "").lower(), (
        "y el recuento, que los cuenta TODOS: si los dos criterios no se "
        "declaran, la resta entre ellos no cuadra y parece un error del ETL (R19)"
    )


# ---------------------------------------------------------------------------
# R23 y R25 · la tabla de comentarios
# ---------------------------------------------------------------------------


def test_f080_r23_la_ficha_dice_que_el_orden_1_es_el_mas_reciente() -> None:
    columna = _columna("compras.documento_comentarios", "orden")
    assert columna is not None
    texto = normalizado(columna.significado or "").lower()

    assert "1" in texto and "recient" in texto, (
        "«el último comentario» se lee como el `orden` más alto, que es el más "
        "VIEJO: la ficha lo tiene que decir (R23)"
    )


def test_f080_r23_la_ficha_dice_que_es_una_tabla_materializada_de_la_nocturna() -> None:
    ficha = _ficha("compras.documento_comentarios")
    assert ficha is not None

    assert ficha.tipo == "tabla", (
        "es una tabla de la carga nocturna, no una vista que parta el memo en "
        "cada lectura (R23, DA-6)"
    )
    assert ficha.paso_etl == "build_compras" and ficha.refresco == "nocturno", (
        "y hay que decir quién la construye y cada cuánto (R23)"
    )


def test_f080_r25_la_ficha_explica_que_pasa_con_lo_que_no_casa() -> None:
    """Lo que no casa es lo más interesante: el comentario que alguien escribió
    fuera del formulario. La ficha tiene que decir que sale igual."""
    texto = _texto_de(_ficha("compras.documento_comentarios"))

    assert "sello_reconocido" in texto, (
        "la columna que avisa de que el bloque no casó con la plantilla (R25)"
    )
    assert "null" in texto.lower(), (
        "y que fecha, hora y usuario van a NULL, no a un valor inventado (R25)"
    )
    assert "entero" in texto.lower(), (
        "el bloque se publica ENTERO: nada se descarta por no casar (R25, DA-2)"
    )


def test_f080_r22_la_ficha_del_memo_dice_que_sale_de_con_tex() -> None:
    """R2 medido: `dcf.tex` está informado en el 0,3 % de las facturas y
    `con.tex` en el 65,5 %. Quien busque el texto en la tabla del documento
    concluirá que las facturas no tienen comentarios."""
    texto = _texto_de(_ficha("compras.documento_texto"))

    assert "con.tex" in texto, "de dónde sale el memo (R22)"
    assert "dcf.tex" in texto, (
        "y de dónde NO, que es donde todo el mundo lo busca primero (R2, R22)"
    )
    assert "65,5" in texto, "el porcentaje medido de facturas con memo (R22)"


# ---------------------------------------------------------------------------
# R35 · la deuda con F-037, declarada en la ficha
# ---------------------------------------------------------------------------


def test_f080_r35_la_ficha_de_los_vencimientos_declara_la_deuda_con_f037() -> None:
    """`compras.vencimientos` es la pata de compra de lo que F-037 hará entero.
    Si la deuda no está escrita en las dos partes, F-037 levantará una segunda
    tabla de efectos y nadie recordará por qué hay dos."""
    texto = _texto_de(_ficha("compras.vencimientos"))

    assert "F-037" in texto, (
        "la ficha tiene que nombrar a F-037 y decir qué se decide cuando llegue "
        "(R35)"
    )


# ---------------------------------------------------------------------------
# R32 · la versión sube a 21
# ---------------------------------------------------------------------------


def test_f080_r32_el_diccionario_sube_al_menos_a_la_version_21() -> None:
    """F-073 reservó la 19 y **F-081 gastó la 20** el 2026-09-11 corrigiendo la
    mentira de `auxefp`, así que a F-080 le toca la 21.

    «Al menos» y no «exactamente», por la lección que dejó el test equivalente
    de F-073: una igualdad exacta convierte el test en un candado y obliga a la
    siguiente feature a elegir entre publicar con la etiqueta de ayer o tocar
    este fichero.
    """
    assert int(_diccionario().version) >= 21, (
        "el contenido del diccionario cambia con cinco objetos nuevos, así que "
        "`version` sube: es lo que lee una persona para saber si lo publicado "
        "es esto (R32)"
    )
