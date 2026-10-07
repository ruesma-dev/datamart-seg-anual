# tests/test_f038_diccionario.py
"""
F-038 · Las fichas del comparativo de ofertas (R14, R17, R22, R24).

`config/diccionario/` es lo que el MCP lee por SQL antes de contestar, y quien
lo lee es un agente que **no puede preguntar**. El comparativo tiene cuatro
importes que no cuadran entre sí, un adjudicado con 52 atípicos que son la
mitad del total, ofertas inventadas mezcladas con las reales y una fecha de
aprobación que fuera de los estados de firma no existe: sin ficha, cada una de
esas cosas es una cifra plausible y falsa.

Las cifras que se exigen son las medidas el 2026-10-04 en
`progress/spec_F-038.md`. Ningún test toca red ni BBDD: se lee el YAML.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest
import yaml

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from tests._texto import contiene, normalizado
from tests.test_f038_sql import (
    COLUMNAS_COMPARATIVOS,
    COLUMNAS_FIRMAS,
    COLUMNAS_LINEAS,
    COLUMNAS_OBJETIVO,
    COLUMNAS_OFERTA_LINEAS,
    COLUMNAS_OFERTAS,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"


@lru_cache(maxsize=1)
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


@lru_cache(maxsize=1)
def _global() -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8"))


def _ficha(nombre: str):
    for ficha in _diccionario().fichas:
        if ficha.nombre == nombre:
            return ficha
    raise AssertionError(f"no hay ficha de {nombre}")


def _columna(ficha_nombre: str, columna: str):
    for c in _ficha(ficha_nombre).columnas:
        if c.nombre == columna:
            return c
    raise AssertionError(f"{ficha_nombre} no documenta `{columna}`")


def _texto(nombre: str) -> str:
    ficha = _ficha(nombre)
    partes = [ficha.descripcion, ficha.grano or ""]
    partes += [c.significado or "" for c in ficha.columnas]
    partes += [c.nulo_significa or "" for c in ficha.columnas]
    partes += [r.porque for r in ficha.relaciones]
    partes += list(ficha.ejemplos_preguntas or [])
    return normalizado(" ".join(partes))


# ===========================================================================
# R24 · una ficha por objeto, con su grano, su clave y sus columnas
# ===========================================================================


@pytest.mark.parametrize(
    ("nombre", "clave", "columnas"),
    [
        ("compras.comparativos", ("comparativo_id",), COLUMNAS_COMPARATIVOS),
        ("compras.comparativo_ofertas", ("oferta_id",), COLUMNAS_OFERTAS),
    ],
)
def test_f038_r24_ficha_con_grano_clave_y_todas_sus_columnas(
    nombre: str, clave: tuple[str, ...], columnas: tuple[str, ...]
) -> None:
    ficha = _ficha(nombre)
    assert ficha.tipo == "tabla" and ficha.capa == "consumo"
    assert ficha.paso_etl == "build_compras" and ficha.refresco == "nocturno"
    assert ficha.clave_negocio == clave
    assert ficha.grano and ficha.ejemplos_preguntas
    assert tuple(c.nombre for c in ficha.columnas) == columnas


@pytest.mark.parametrize(
    "nombre", ["compras.fn_normalizar_nombre", "compras.fn_familia_ficticia"]
)
def test_f038_r24_las_dos_funciones_tienen_ficha(nombre: str) -> None:
    ficha = _ficha(nombre)
    assert ficha.tipo == "funcion" and ficha.capa == "operacion"
    assert "etl_sigrid/domain/comparativos.py" in normalizado(ficha.descripcion)


def test_f038_r14_ninguna_columna_se_llama_importe_a_secas() -> None:
    for nombre in ("compras.comparativos", "compras.comparativo_ofertas"):
        assert "importe" not in {c.nombre for c in _ficha(nombre).columnas}, nombre


def test_f038_r24_los_importes_llevan_unidad_y_agregacion() -> None:
    for nombre in ("compras.comparativos", "compras.comparativo_ofertas"):
        for columna in _ficha(nombre).columnas:
            if columna.nombre.startswith(("importe_", "oferta_real_", "ahorro_")):
                assert columna.unidad == "EUR", f"{nombre}.{columna.nombre}"
                assert columna.agregacion, f"{nombre}.{columna.nombre}"


# ===========================================================================
# R24 · lo que la ficha de `comparativos` TIENE que decir
# ===========================================================================


@pytest.mark.parametrize(
    "frase",
    [
        # Las cuatro magnitudes y su cuadre medido, sin IVA
        "99,6 %", "89,8 %", "41 %", "SIN IVA", "totbas",
        # El adjudicado atípico y el saneado
        "52", "602,5 M€", "1.246,2 M€", "641,0 M€", "14.585", "4.206",
        # El ahorro del concurso, solo con reales
        "6.904", "72,7 M€",
        # Las siete fechas y los cinco campos de `com` vacíos en origen
        "fecent", "feclim", "fecsum", "feccon", "fecinirec", "fecfinrec", "fecdiv",
        "ppoide", "prmide", "pexide", "tipsub", "horlim",
        # Las dos trampas de dbo.log
        "dbo.log", "log.ide", "log.res",
    ],
)
def test_f038_r24_la_ficha_de_comparativos_lo_dice(frase: str) -> None:
    assert frase in _texto("compras.comparativos"), frase


def test_f038_r17_el_contratado_es_del_contrato_y_no_se_suma() -> None:
    columna = _columna("compras.comparativos", "importe_contratado")
    texto = normalizado(columna.significado)
    assert columna.agregacion == "no_sumable"
    assert "3.960" in texto and "contrato_id" in texto and "DISTINTO" in texto


def test_f038_r16_el_atipico_dice_su_corte_y_su_nulo() -> None:
    columna = _columna("compras.comparativos", "adjudicado_atipico")
    texto = normalizado(f"{columna.significado} {columna.nulo_significa}")
    assert "10 veces" in texto and "100.000" in texto
    assert columna.nulo_significa, "NULL = sin oferta con importe con que comparar"


def test_f038_r19_el_ahorro_declara_que_no_lleva_ficticias() -> None:
    columna = _columna("compras.comparativos", "ahorro_concurso")
    texto = normalizado(f"{columna.significado} {columna.nulo_significa}")
    assert "ficticia" in texto.lower() and "dos" in texto
    assert columna.nulo_significa


def test_f038_r23_la_fecha_de_aprobacion_no_existe_fuera_de_las_firmas() -> None:
    columna = _columna("compras.comparativos", "fecha_aprobacion")
    texto = normalizado(f"{columna.significado} {columna.nulo_significa}")
    assert "estfin" in texto and "NO EXISTE" in texto


# ===========================================================================
# R24 · lo que la ficha de `comparativo_ofertas` TIENE que decir
# ===========================================================================


@pytest.mark.parametrize(
    "frase",
    [
        "A99999999", "A00000000", "30 %", "172", "32.896", "1.298,8 M€",
        "totbas", "totdoc", "entide", "prvide", "18 %",
        "etl_sigrid/domain/comparativos.py",
    ],
)
def test_f038_r24_la_ficha_de_ofertas_lo_dice(frase: str) -> None:
    assert frase in _texto("compras.comparativo_ofertas"), frase


def test_f038_r24_la_familia_enumera_sus_valores() -> None:
    columna = _columna("compras.comparativo_ofertas", "familia_ficticia")
    assert columna.valores == (
        "OBJETIVO", "OFICINA_TECNICA", "CUATRIMESTRAL", "FASE_0", "ABC",
        "PLANIFICACION",
    )


# ===========================================================================
# Relaciones y R22
# ===========================================================================


@pytest.mark.parametrize(
    ("ficha", "de", "a", "cardinalidad"),
    [
        ("compras.comparativo_ofertas", "comparativo_id",
         "compras.comparativos.comparativo_id", "N:1"),
        ("compras.comparativos", "comparativo_id",
         "compras.comparativo_ofertas.comparativo_id", "1:N"),
        ("compras.comparativos", "contrato_id", "compras.contratos.contrato_id", "N:1"),
        ("compras.comparativos", "obra_id", "maestro.obras.obra_id", "N:1"),
        ("compras.contratos", "comparativo_id",
         "compras.comparativos.comparativo_id", "N:1"),
        ("compras.albaranes", "comparativo_id",
         "compras.comparativos.comparativo_id", "N:1"),
    ],
)
def test_f038_r24_relaciones(ficha: str, de: str, a: str, cardinalidad: str) -> None:
    relaciones = {(r.de, r.a): r.cardinalidad for r in _ficha(ficha).relaciones}
    assert relaciones.get((de, a)) == cardinalidad, (ficha, de, a)


def test_f038_r22_contratos_comparativo_id_remite_al_objeto_nuevo() -> None:
    columna = _columna("compras.contratos", "comparativo_id")
    texto = normalizado(columna.significado)
    assert "ctr.comide" in texto and "56 %" in texto
    assert "compras.comparativos.contrato_id" in texto
    assert not contiene(texto, "No esta modelado")
    assert not contiene(texto, "NO esta modelado")


def test_f038_r22_albaranes_comparativo_id_ya_no_dice_no_modelado() -> None:
    columna = _columna("compras.albaranes", "comparativo_id")
    assert not contiene(columna.significado, "No esta modelado")
    assert contiene(columna.significado, "compras.comparativos")


# ===========================================================================
# 00_global.yaml · versión, P5 y las cuatro preguntas del acceptance 13
# ===========================================================================


def test_f038_r24_la_version_sube() -> None:
    """42 con la Fase 1 (publicada el 2026-10-05); 43 con la Fase 2 (T17).
    Despues solo puede subir: F-067 la lleva a 44 (2026-10-06)."""
    assert _global()["version"] >= 43


def test_f038_r24_p5_pasa_a_respondible() -> None:
    p5 = next(p for p in _global()["preguntas_aceptacion"] if p["id"] == "P5")
    assert p5["estado"] == "respondible"
    assert "bloqueada_por" not in p5
    assert "compras.comparativos" in p5["objetos_esperados"]


@pytest.mark.parametrize(
    ("id_", "clave"),
    [
        ("P19", "actividad"),
        ("P20", "ahorro_concurso"),
        ("P21", "aprobado_por"),
        ("P22", "contrato_id"),
    ],
)
def test_f038_r24_las_cuatro_preguntas_del_acceptance_13(id_: str, clave: str) -> None:
    pregunta = next(
        (p for p in _global()["preguntas_aceptacion"] if p["id"] == id_), None
    )
    assert pregunta is not None, f"falta {id_}"
    assert pregunta["estado"] == "respondible"
    assert pregunta["objetos_esperados"] == ["compras.comparativos"]
    assert clave in pregunta["respuesta_correcta"]
    assert "build_compras" in pregunta["respuesta_correcta"], (
        "la respuesta cita la frescura de `build_compras` (T24)"
    )
    assert "R-FRESCURA" in pregunta["reglas_implicadas"]


# ===========================================================================
# FASE 2 · R28, R31, R34, R35 · las fichas de los cuatro objetos del detalle
# ===========================================================================


@pytest.mark.parametrize(
    ("nombre", "clave", "columnas"),
    [
        ("compras.comparativo_lineas", ("linea_id",), COLUMNAS_LINEAS),
        (
            "compras.comparativo_oferta_lineas",
            ("linea_oferta_id",),
            COLUMNAS_OFERTA_LINEAS,
        ),
        ("compras.comparativo_objetivo", ("comparativo_id",), COLUMNAS_OBJETIVO),
        ("compras.comparativo_firmas", ("firma_id",), COLUMNAS_FIRMAS),
    ],
)
def test_f038_r35_ficha_con_grano_clave_y_todas_sus_columnas(
    nombre: str, clave: tuple[str, ...], columnas: tuple[str, ...]
) -> None:
    ficha = _ficha(nombre)
    assert ficha.tipo == "tabla" and ficha.capa == "consumo"
    assert ficha.paso_etl == "build_compras" and ficha.refresco == "nocturno"
    assert ficha.clave_negocio == clave
    assert ficha.grano and ficha.ejemplos_preguntas and ficha.relaciones
    assert tuple(c.nombre for c in ficha.columnas) == columnas


def test_f038_r27_la_funcion_del_dto_tiene_ficha() -> None:
    ficha = _ficha("compras.fn_porcentaje_dto")
    assert ficha.tipo == "funcion" and ficha.capa == "operacion"
    assert "etl_sigrid/domain/comparativos.py" in normalizado(ficha.descripcion)


def test_f038_r14_fase_2_ninguna_columna_se_llama_importe_a_secas() -> None:
    for nombre in (
        "compras.comparativo_lineas", "compras.comparativo_oferta_lineas",
        "compras.comparativo_objetivo", "compras.comparativo_firmas",
    ):
        assert "importe" not in {c.nombre for c in _ficha(nombre).columnas}, nombre


def test_f038_r35_los_importes_y_precios_llevan_unidad_y_agregacion() -> None:
    for nombre in (
        "compras.comparativo_lineas", "compras.comparativo_oferta_lineas",
        "compras.comparativo_objetivo",
    ):
        for columna in _ficha(nombre).columnas:
            if columna.nombre.startswith(("importe_", "precio")):
                assert columna.unidad == "EUR", f"{nombre}.{columna.nombre}"
                assert columna.agregacion, f"{nombre}.{columna.nombre}"


@pytest.mark.parametrize(
    "frase",
    [
        # R28: el dto es texto con coma decimal, el precio ya es neto, negativos
        "TEXTO", "coma decimal", "revienta", "neto", "recargo",
        # La base del objetivo y su cobertura de D4
        "D4", "primera ABC", "ANTERIOR", "posterior", "Estudios",
        "24.263", "83.329", "29,1 %", "12.351", "21.789",
        # La cifra con la regla PUBLICADA (review de la Fase 2, cambio 3)
        "24.425", "84.084", "29,0 %", "59.570", "2026-10-05",
        # Lee `descompuestos` de la noche anterior
        "descompuestos.lineas", "noche anterior", "build_descompuestos",
    ],
)
def test_f038_r28_r30_la_ficha_de_las_lineas_de_oferta_lo_dice(frase: str) -> None:
    assert frase in _texto("compras.comparativo_oferta_lineas"), frase


@pytest.mark.parametrize(
    "frase",
    ["29,1 %", "24.263", "noche anterior", "descompuestos", "D4", "12.259", "1.126",
     "24.425", "84.084", "29,0 %"],
)
def test_f038_r31_la_ficha_del_objetivo_da_las_cifras_y_el_desfase(frase: str) -> None:
    assert frase in _texto("compras.comparativo_objetivo"), frase


@pytest.mark.parametrize("frase", ["5.375", "rechazo", "`ord`", "F-085", "6.498"])
def test_f038_r34_la_ficha_de_firmas_lo_dice(frase: str) -> None:
    assert frase in _texto("compras.comparativo_firmas"), frase


def test_f038_r28_descuento_texto_y_porcentaje() -> None:
    texto = normalizado(_columna("compras.comparativo_oferta_lineas", "descuento_texto").significado)
    assert "TEXTO" in texto and "coma" in texto
    porcentaje = _columna("compras.comparativo_oferta_lineas", "porcentaje_descuento")
    assert porcentaje.agregacion == "no_sumable" and porcentaje.nulo_significa


def test_f038_r30_casa_base_nulo_solo_sin_descompuesto_en_ninguna_version() -> None:
    columna = _columna("compras.comparativo_oferta_lineas", "casa_base")
    assert "NINGUNA version" in normalizado(columna.nulo_significa)
    assert "la admita la regla o no" in normalizado(columna.significado)


def test_f038_r30_las_columnas_de_la_base_dicen_su_nulo() -> None:
    for columna in ("base_regla", "precio_base", "origen_base", "casa_base"):
        assert _columna("compras.comparativo_oferta_lineas", columna).nulo_significa, columna
    assert _columna("compras.comparativo_oferta_lineas", "base_regla").valores == (
        "ABC", "ESTUDIOS",
    )
    assert _columna("compras.comparativo_objetivo", "base_regla").valores == (
        "ABC", "ESTUDIOS",
    )


@pytest.mark.parametrize(
    ("ficha", "de", "a", "cardinalidad"),
    [
        ("compras.comparativo_lineas", "comparativo_id",
         "compras.comparativos.comparativo_id", "N:1"),
        ("compras.comparativo_lineas", "contrato_id",
         "compras.contratos.contrato_id", "N:1"),
        ("compras.comparativo_lineas", "partida_id",
         "descompuestos.lineas.partida_id", "N:N"),
        ("compras.comparativo_oferta_lineas", "oferta_id",
         "compras.comparativo_ofertas.oferta_id", "N:1"),
        ("compras.comparativo_oferta_lineas", "comparativo_linea_id",
         "compras.comparativo_lineas.linea_id", "N:1"),
        ("compras.comparativo_objetivo", "comparativo_id",
         "compras.comparativos.comparativo_id", "1:1"),
        ("compras.comparativo_objetivo", "oferta_objetivo_id",
         "compras.comparativo_ofertas.oferta_id", "N:1"),
        ("compras.comparativo_firmas", "comparativo_id",
         "compras.comparativos.comparativo_id", "N:1"),
        ("compras.comparativos", "comparativo_id",
         "compras.comparativo_lineas.comparativo_id", "1:N"),
        ("compras.comparativos", "comparativo_id",
         "compras.comparativo_objetivo.comparativo_id", "1:1"),
        ("compras.comparativos", "comparativo_id",
         "compras.comparativo_firmas.comparativo_id", "1:N"),
    ],
)
def test_f038_r35_relaciones_de_la_fase_2(
    ficha: str, de: str, a: str, cardinalidad: str
) -> None:
    relaciones = {(r.de, r.a): r.cardinalidad for r in _ficha(ficha).relaciones}
    assert relaciones.get((de, a)) == cardinalidad, (ficha, de, a)


def test_f038_r33_aprobado_por_remite_a_las_firmas() -> None:
    texto = normalizado(_columna("compras.comparativos", "aprobado_por").significado)
    assert "compras.comparativo_firmas" in texto
    assert "Fase 2" not in texto
