# tests/test_f073_diccionario.py
"""
F-073 · Las fichas de los objetos nuevos y de las columnas nuevas (R6, R11,
R12, R15, R20, R22, R28).

`config/diccionario/` no es documentación de cortesía: es lo que el MCP lee por
SQL antes de contestar, y quien lo lee es un agente que no puede preguntar. Una
ficha que describe el objeto de antes no es documentación incompleta, es una
afirmación falsa.

Esta feature publica tres objetos nuevos y once columnas nuevas en
`maestro.obras`, y **cada una trae una trampa medida** que la ficha tiene que
declarar: el puente resuelve 683 de 804, la dirección solo la tiene un tercio
de las obras, `tiene_seguimiento` es superconjunto del hecho en 19 obras, el
estado de documento solo se traduce con su tipo, y `plazo_formula` no es un
número de días.

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

#: Las once columnas que F-073 añade a `maestro.obras`.
COLUMNAS_NUEVAS_DE_OBRAS = (
    "estado",
    "dir1",
    "dir2",
    "codigo_postal",
    "direccion_completa",
    "municipio_id",
    "municipio",
    "provincia_id",
    "provincia",
    "tiene_presupuesto",
    "tiene_seguimiento",
)


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
# Los tres objetos nuevos tienen ficha
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "objeto",
    ["maestro.centros_coste", "maestro.estados_documento", "compras.formas_pago"],
)
def test_f073_r28_cada_objeto_nuevo_tiene_su_ficha(objeto: str) -> None:
    ficha = _ficha(objeto)

    assert ficha is not None, (
        f"{objeto} se publica en la base y no tiene ficha: el agente lo verá en "
        "el catálogo y se inventará su significado (R28)"
    )
    assert ficha.consumo_recomendado, (
        f"{objeto} es una dimensión para consultar: si no se recomienda, no se "
        "publica"
    )


@pytest.mark.parametrize(
    ("objeto", "columnas"),
    [
        (
            "maestro.centros_coste",
            (
                "centro_coste_id",
                "codigo_centro",
                "nombre_centro",
                "empresa",
                "obra_id",
                "codigo_obra",
                "nombre_obra",
            ),
        ),
        (
            "maestro.estados_documento",
            (
                "estado_documento_id",
                "tipo_documento",
                "estado_id",
                "codigo_estado",
                "estado",
            ),
        ),
        (
            "compras.formas_pago",
            (
                "forma_pago_id",
                "codigo",
                "nombre",
                "plazo_formula",
                "medio_pago_id",
                "medio_pago",
                "clase_medio",
            ),
        ),
    ],
)
def test_f073_r28_la_ficha_describe_todas_las_columnas(
    objeto: str, columnas: tuple[str, ...]
) -> None:
    ficha = _ficha(objeto)
    assert ficha is not None, f"no hay ficha de {objeto}"

    assert tuple(c.nombre for c in ficha.columnas) == columnas, (
        f"la ficha de {objeto} tiene que describir sus columnas, en el orden "
        "en que la vista las publica"
    )


# ---------------------------------------------------------------------------
# R6 · el puente, con sus dos cifras y su trampa
# ---------------------------------------------------------------------------


def test_f073_r6_la_ficha_del_puente_declara_cuantos_resuelven() -> None:
    texto = _texto_de(_ficha("maestro.centros_coste"))

    assert "683" in texto and "804" in texto, (
        "la ficha tiene que decir que 683 de 804 centros resuelven a obra: sin "
        "eso, un COUNT sobre la vista parece un censo de obras (R6)"
    )
    assert "1:1" in texto, "la relación es 1:1 y sin ambigüedad (R6)"


def test_f073_r6_la_ficha_del_puente_avisa_de_que_obride_no_sirve() -> None:
    """Está a 0 en las 804 filas: es el campo que parece el puente y no lo es."""
    texto = _texto_de(_ficha("maestro.centros_coste"))

    assert "obride" in texto, (
        "quien vaya a rehacer este puente mirará `cen.obride` primero: la ficha "
        "tiene que decirle que está a 0 en las 804 filas (R6)"
    )


# ---------------------------------------------------------------------------
# R11 y R12 · la dirección se publica CON su porcentaje
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("columna", COLUMNAS_NUEVAS_DE_OBRAS)
def test_f073_r28_cada_columna_nueva_de_obras_tiene_ficha(columna: str) -> None:
    assert _columna("maestro.obras", columna) is not None, (
        f"maestro.obras publica {columna} y la ficha no la describe (R28)"
    )


@pytest.mark.parametrize(
    ("columna", "porcentaje"),
    [
        ("dir1", "33,1"),
        ("dir2", "5,1"),
        ("codigo_postal", "32,9"),
        ("direccion_completa", "29,5"),
        ("municipio", "31,9"),
        ("provincia", "33,2"),
    ],
)
def test_f073_r12_cada_columna_de_direccion_declara_su_cobertura(
    columna: str, porcentaje: str
) -> None:
    """El porcentaje MEDIDO en esta feature, no uno redondeado de memoria."""
    ficha_columna = _columna("maestro.obras", columna)
    assert ficha_columna is not None, f"falta la ficha de {columna}"
    texto = normalizado(
        (ficha_columna.significado or "") + " " + (ficha_columna.nulo_significa or "")
    )

    assert porcentaje in texto, (
        f"la ficha de {columna} tiene que declarar el {porcentaje} % medido: sin "
        "el porcentaje, un NULL parece un fallo del ETL y no un «no consta» "
        "(R12)"
    )


def test_f073_r11_la_ficha_dice_que_no_consta_es_la_respuesta_correcta() -> None:
    texto = _texto_de(_ficha("maestro.obras"))

    assert "no consta" in texto.lower(), (
        "para dos de cada tres obras «no consta» es la respuesta CORRECTA, y la "
        "ficha lo tiene que decir con esas palabras (R11)"
    )


# ---------------------------------------------------------------------------
# R15 · la marca que es superconjunto del hecho
# ---------------------------------------------------------------------------


def test_f073_r15_tiene_seguimiento_declara_que_se_mide_en_stg() -> None:
    columna = _columna("maestro.obras", "tiene_seguimiento")
    assert columna is not None
    texto = normalizado(columna.significado or "")

    assert "stg.plan_mensual" in texto, "hay que decir dónde se mide (R15)"
    assert "368" in texto and "349" in texto and "19" in texto, (
        "368 obras con plan frente a 349 con hecho, 19 de diferencia: sin esas "
        "tres cifras, quien cruce la marca con el hecho creerá que faltan datos "
        "(R15)"
    )


def test_f073_r13_las_dos_marcas_declaran_que_nunca_son_nulas() -> None:
    for nombre in ("tiene_presupuesto", "tiene_seguimiento"):
        columna = _columna("maestro.obras", nombre)
        assert columna is not None
        assert columna.nulo_significa is None, (
            f"{nombre} es NOT NULL por construcción (un EXISTS): declarar qué "
            "significa su NULL sería describir un caso imposible (R13)"
        )


# ---------------------------------------------------------------------------
# R20 y R22 · las dos trampas de las dimensiones
# ---------------------------------------------------------------------------


def test_f073_r20_la_ficha_de_estados_avisa_de_que_va_por_tipo() -> None:
    texto = _texto_de(_ficha("maestro.estados_documento")).lower()

    assert "tipo de documento" in texto
    assert "193" in texto, "las 193 filas, para que se note que no es solo obra"
    assert "42" in texto and "15" in texto, (
        "hay que nombrar al menos dos tipos —obra 42 y factura 15— para que se "
        "vea que la misma cifra significa cosas distintas (R20)"
    )


def test_f073_r22_la_ficha_dice_que_el_plazo_no_es_un_numero() -> None:
    columna = _columna("compras.formas_pago", "plazo_formula")
    assert columna is not None
    texto = normalizado(columna.significado or "")

    assert "30 450R" in texto, (
        "el valor real del catálogo es el argumento: sin él, «no es un número de "
        "días» suena a exceso de celo (R22)"
    )
    assert "no es" in texto.lower() and "dias" in texto.lower().replace("í", "i"), (
        "la ficha tiene que decir explícitamente que NO es un número de días (R22)"
    )


def test_f073_r21_la_ficha_del_medio_de_pago_no_promete_lo_que_no_hay() -> None:
    """`auxefp.est` está vacío: la ficha describe `res`, que es lo que se publica."""
    columna = _columna("compras.formas_pago", "medio_pago")
    assert columna is not None
    assert normalizado(columna.significado or "").strip(), (
        "medio_pago necesita significado (R21)"
    )


# ---------------------------------------------------------------------------
# R28 · la versión sube
# ---------------------------------------------------------------------------


def test_f073_r28_el_diccionario_sube_a_la_version_19() -> None:
    assert str(_diccionario().version) == "19", (
        "el contenido del diccionario cambia, así que `version` sube: es lo que "
        "lee una persona para saber si lo publicado es esto (R28)"
    )
