# tests/test_f150_diccionario.py
"""
F-150 · Diccionario y documentación de la receta (R2-R6, R15, R32).

Sin red ni base: leen los YAML del diccionario y los Markdown del árbol.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_CONVENTIONS = RAIZ / "docs" / "CONVENTIONS.md"
RUTA_ARCHITECTURE = RAIZ / "docs" / "ARCHITECTURE.md"
RUTA_CLAUDE = RAIZ / "CLAUDE.md"


def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


# ===========================================================================
# R6 · la excepción acotada de D1 en las convenciones y la arquitectura
# ===========================================================================


def test_f150_r6_conventions_recoge_la_excepcion_acotada() -> None:
    texto = _texto(RUTA_CONVENTIONS)
    tramo = texto[texto.index("Excepción acotada (F-150, D1)"):]
    tramo = tramo[: tramo.index("## Tests")]
    assert "tesoreria.hipotesis_caja" in tramo
    assert "config/hipotesis_caja.yaml" in tramo, "los valores siguen en el YAML"
    assert "objetos del datamart" in tramo
    assert "PASOS_RECETA" in tramo and "paso_receta" in tramo


def test_f150_r6_architecture_describe_la_receta() -> None:
    texto = _texto(RUTA_ARCHITECTURE)
    tramo = texto[texto.index("**La receta de la caja (F-150"):]
    tramo = tramo[: tramo.index("**`descompuestos` (F-097")]
    for clave in ("D1", "PASOS_RECETA", "paso_receta", "coeficiente_venta", "MEDIA_OBRA",
                  "raw.dvf", "raw.iva", "include_columns", "80 tablas", "stg.presupuesto"):
        assert clave in tramo, clave


def test_f150_r32_docs_dicen_cuantas_hipotesis() -> None:
    n = _n_hipotesis()
    assert f"las {n} (H01-H{n} desde F-150)" in _texto(RUTA_ARCHITECTURE)
    claude = _texto(RUTA_CLAUDE)
    assert f"las {n} hipótesis de `config/hipotesis_caja.yaml`" in claude
    assert "las 23 hipótesis" not in claude
    assert "**la receta**" in claude and "paso_receta" in claude


def _n_hipotesis() -> int:
    """Cuantas hipotesis tiene el catalogo: los textos dicen ESA cifra (N14 y N15 la suben)."""
    import yaml as _yaml

    ruta = Path(__file__).resolve().parents[1] / "config" / "hipotesis_caja.yaml"
    return len(_yaml.safe_load(ruta.read_text(encoding="utf-8"))["hipotesis"])


# ===========================================================================
# R2-R5, R15, R32 · la receta en el diccionario (T12)
# ===========================================================================

import re  # noqa: E402

import yaml  # noqa: E402

from etl_sigrid.domain import proyeccion_caja as dom  # noqa: E402

DICC = RAIZ / "config" / "diccionario"
RUTA_YAML_HIPOTESIS = RAIZ / "config" / "hipotesis_caja.yaml"
DEVENGO = ("tesoreria.devengo_corte_obra", "tesoreria.devengo_pendiente_obra_mes",
           "tesoreria.devengo_pendiente_partida")


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def _fichas_tesoreria() -> dict:
    return yaml.safe_load((DICC / "tesoreria.yaml").read_text(encoding="utf-8"))["objetos"]


def _reglas() -> dict:
    glob = yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))
    return {r["codigo"]: r for r in glob["reglas"]}


def _receta() -> str:
    descripcion = _plano(_fichas_tesoreria()["hipotesis_caja"]["descripcion"])
    assert "LA RECETA: DE DEVENGO A CAJA, EN ESTE ORDEN" in descripcion
    return descripcion[descripcion.index("LA RECETA: DE DEVENGO A CAJA, EN ESTE ORDEN"):]


def _tramos() -> dict[str, str]:
    """El texto de cada paso, de su «n. PASO:» al siguiente. N14: el SALDO es el 0."""
    receta = _receta()
    posiciones = []
    for n, paso in enumerate(dom.PASOS_RECETA, start=0):
        marca = f" {n}. {paso}"
        assert marca in receta, f"falta el paso {n}. {paso}"
        posiciones.append(receta.index(marca))
    assert posiciones == sorted(posiciones), "los pasos en el orden de PASOS_RECETA"
    fines = [*posiciones[1:], len(receta)]
    return {p: receta[i:f] for p, i, f in zip(dom.PASOS_RECETA, posiciones, fines, strict=True)}


def test_f150_r2_cada_paso_nombra_sus_hipotesis_y_solo_las_suyas() -> None:
    from etl_sigrid.infrastructure.config.hipotesis_caja_yaml import cargar_hipotesis_caja

    catalogo = cargar_hipotesis_caja(RUTA_YAML_HIPOTESIS).catalogo
    assert len(catalogo) == _n_hipotesis()
    for paso, tramo in _tramos().items():
        esperados = {h.codigo for h in catalogo if h.paso_receta == paso}
        if paso == "SALDO":
            # N15 (R43): el saldo suma el IVA ya recuperado SEGUN H30 (paso IVA).
            esperados |= {"H30"}
        assert set(re.findall(r"\bH[0-9]{2}\b", tramo)) == esperados, paso


def test_f150_r3_la_receta_nombra_sus_ingredientes() -> None:
    receta = _receta()
    for ingrediente in (*DEVENGO, "condiciones_contrato_compra", "condiciones_contrato_cliente",
                        "tesoreria.efectos", "cartera_emitida_tras_cierre",
                        # N11-N12 (29-10): los albaranes NETOS y la cartera de CP.
                        "tesoreria.albaranes_pendientes_neto", "importe_pendiente_neto",
                        "meses_antiguedad", "tras_cierre", "cartera_viva_coste_proporcional",
                        "cartera_emitida_tras_cierre_coste_proporcional",
                        "importe_pendiente_con_coeficientes",
                        "pendiente_con_coeficientes", "fuente_coeficiente", "importe_iva_contrato",
                        "importe_retencion_contrato", "venta_pendiente_facturar",
                        "iva_pendiente_facturar_contrato", "retencion_pendiente_facturar_contrato"):
        assert ingrediente in receta, ingrediente


def test_f150_r3_la_receta_dice_sus_reglas() -> None:
    receta = _receta()
    for frase in ("COSTE se paga", "VENTA se cobra", "reparten el importe ENTERO",
                  "sobre la base SIN IVA", "Sin IVA", "nunca un coeficiente medio de obra",
                  "H10 solo se aplica a las bases", "H12 solo se aplica a las bases",
                  "Redondea solo al final", "PERFIL_MESES"):
        assert frase in receta, frase


def test_f150_r4_la_receta_avisa_de_lo_que_no_cubre() -> None:
    receta = _receta()
    assert "revision de precios" in receta and "F-040" in receta
    assert "H13 y H14 estan pendientes de validar con Administracion" in receta
    assert "`facturado_por_delante` NO se cobra" in receta
    assert "las de `meses_antiguedad` mayor que H27 (o sin mes) NO son caja" in receta
    assert "declara su importe" in receta
    # N11: el objeto ya excluye las lineas de R-ALBARAN-ABSURDO; la receta no la cita.
    assert "R-ALBARAN-ABSURDO" not in receta
    # N12: el CP tampoco es caja de la obra.
    assert "el coste PROPORCIONAL (`categoria` = `CP`, estructura) NO es caja de la obra" in receta


def test_f150_r5_el_resumen_de_r_caja_hipotesis() -> None:
    regla = _reglas()["R-CAJA-HIPOTESIS"]
    resumen = _plano(regla["resumen"]).strip()
    assert len(resumen) <= 230
    for dato in ("receta", "`tesoreria.hipotesis_caja`", "`tesoreria.hipotesis_caja_obra`",
                 "cartera", "DEFECTO", "OBRA", "USUARIO"):
        assert dato in resumen, dato
    assert _plano(regla["regla"]).startswith(
        "Sigue la RECETA de la ficha de `tesoreria.hipotesis_caja`, en su orden")
    assert "F-150" in _plano(regla["motivo"])


def test_f150_r15_r_venta_coeficientes_cubre_el_devengo() -> None:
    regla = _reglas()["R-VENTA-COEFICIENTES"]
    assert set(DEVENGO) <= set(regla["ambito"])
    fichas = _fichas_tesoreria()
    for nombre in DEVENGO:
        texto = _plano(fichas[nombre.split(".")[1]]["descripcion"])
        assert "R-VENTA-COEFICIENTES" in texto, nombre
        assert "NO se suma ni se compara con el coste, lo ejecutado ni la venta sin ellos" in texto, nombre


def test_f150_r32_fichas_al_dia_y_version_63() -> None:
    fichas = _fichas_tesoreria()
    hip = fichas["hipotesis_caja"]
    n = _n_hipotesis()
    assert f"las {n} hipotesis (H01-H{n})" in _plano(hip["descripcion"])
    assert _plano(hip["grano"]).endswith(f"({n}).")
    assert hip["ejemplos_preguntas"][0] == "Como se pasa paso a paso el devengo de una obra a caja"
    obra = fichas["hipotesis_caja_obra"]
    assert f"las {n} hipotesis del catalogo" in _plano(obra["grano"])
    assert "H12" in _plano(obra["descripcion"]) and "ficha de la obra" in _plano(obra["descripcion"])
    glob = yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))
    assert int(glob["version"]) >= 63, "la v63 de F-150; el ajuste del 29-10 la sube (r32_v64)"
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 63 (F-150, 2026-10-28)" in texto


# ===========================================================================
# R3, R4, R36, R37 · el ajuste del 29-10 (N11-N13, T22)
# ===========================================================================


def test_f150_r36_paso_1_y_paso_7_sacan_el_cp() -> None:
    tramos = _tramos()
    assert "exclúyelo y declara su importe" in tramos["DEVENGO"]
    for columna in ("cartera_viva_coste_proporcional",
                    "cartera_emitida_tras_cierre_coste_proporcional"):
        assert columna in tramos["CARTERA"], columna


def test_f150_r36_las_fichas_del_devengo_dicen_que_el_cp_no_es_caja() -> None:
    fichas = _fichas_tesoreria()
    for nombre in DEVENGO:
        assert "`CP` no es caja de la obra" in _plano(fichas[nombre.split(".")[1]]["descripcion"])


def test_f150_r37_el_personal_va_por_el_devengo_del_recurso() -> None:
    tramos = _tramos()
    assert "El PERSONAL de la obra ya está aquí, como coste del RECURSO" in tramos["DEVENGO"]
    assert "NO sumes pagos de personal de la cartera" in tramos["DEVENGO"]
    # N13-b: el plazo del personal va con H02 `CI` y un aviso.
    assert "el personal de la obra va en CI y se paga con H02 `CI`" in tramos["PLAZO"]
    fichas = _fichas_tesoreria()
    for nombre in ("efectos", "efectos_restringidos_mes"):
        texto = _plano(fichas[nombre]["descripcion"])
        assert "el personal va por el devengo del recurso: no es lo que falta" in texto, nombre


def test_f150_r37_la_regla_de_caja_dice_cp_personal_y_albaranes_netos() -> None:
    regla = _reglas()["R-CAJA-HIPOTESIS"]
    texto = _plano(regla["regla"])
    assert "el CP no es caja de la obra" in texto
    assert "no sumes nominas de la cartera" in texto
    assert "los albaranes, netos por proveedor" in texto
    assert "tesoreria.albaranes_pendientes_neto" in regla["ambito"]


def test_f150_r34_ficha_de_los_albaranes_netos() -> None:
    ficha = _fichas_tesoreria()["albaranes_pendientes_neto"]
    assert ficha["tipo"] == "tabla" and ficha["consumo_recomendado"] is True
    assert ficha["clave_negocio"] == ["obra_id", "proveedor_id", "contrato_id", "mes_albaran"]
    columnas = ficha["columnas"]
    for importe in ("importe_pendiente_bruto", "importe_sobrefacturado", "importe_compensado",
                    "importe_pendiente_neto"):
        assert columnas[importe]["agregacion"] == "suma", importe
    assert columnas["meses_antiguedad"]["agregacion"] == "no_sumable"
    descripcion = _plano(ficha["descripcion"])
    assert "Σ `importe_sobrefacturado` \u2212 Σ `importe_compensado`" in descripcion, "el residuo"
    assert ficha["ejemplos_preguntas"][:2] == [
        "Cuanto queda de verdad por facturar de albaranes en la obra X",
        "Cuando se pagaran los albaranes pendientes de la obra X",
    ]


def test_f150_r34_la_vista_de_compras_avisa_del_neto() -> None:
    compras = yaml.safe_load((DICC / "compras.yaml").read_text(encoding="utf-8"))["objetos"]
    texto = _plano(compras["v_pbi_albaranes_sin_facturar"]["descripcion"])
    assert "solo las lineas > 0" in texto
    assert "el pendiente real es el neto por proveedor" in texto
    assert "`tesoreria.albaranes_pendientes_neto`" in texto


def test_f150_r32_version_64_con_su_nota() -> None:
    glob = yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))
    assert int(glob["version"]) >= 64
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 64 (F-150, 2026-10-29)" in texto


def test_f150_r32_docs_dicen_albaranes_netos_cp_y_personal() -> None:
    """T23 (N11-N13): ARCHITECTURE explica la copia deliberada de `raw` y CLAUDE.md
    el mapa (albaranes netos, el CP fuera con F-154, el personal por el recurso)."""
    arquitectura = _texto(RUTA_ARCHITECTURE)
    tramo = arquitectura[arquitectura.index("**Los albaranes netos por proveedor** (N11"):]
    tramo = tramo[: tramo.index("**`descompuestos` (F-097")]
    for clave in ("raw.dcapro", "raw.dcfpro", "copia deliberada", "neto_fifo", "F-154"):
        assert clave in tramo, clave
    claude = _texto(RUTA_CLAUDE)
    assert "`tesoreria.albaranes_pendientes_neto`" in claude
    assert "F-154" in claude and "devengo del recurso" in claude


# ===========================================================================
# R40 · el saldo de partida en la receta (N14, T30)
# ===========================================================================


def test_f150_r40_el_paso_0_da_la_formula_del_saldo() -> None:
    tramo = _plano(_tramos()["SALDO"])
    assert tramo.startswith(" 0. SALDO")
    for pieza in ("`tesoreria.saldo_partida_obra`", "CON IVA", "`cobrado_realizado`",
                  "`pagado_realizado_sin_agr`", "`agrupados_vencidos`", "`pagado_agr_con_obra`",
                  "`pagado_coste_proporcional`", "`agrupados_vencidos_coste_proporcional`",
                  "`personal_coste_partes`", "`fecha_corte`"):
        assert pieza in tramo, pieza
    assert ("saldo = `cobrado_realizado` \u2212 (`pagado_realizado_sin_agr` + [H29 `ORIGINALES`: "
            "`agrupados_vencidos` | `AGR`: `pagado_agr_con_obra`] \u2212 CP) \u2212 "
            "`personal_coste_partes`") in tramo
    assert "con `SIN_SALDO`, 0" in tramo


def test_f150_r40_h29_es_hipotesis_que_rompe_r_tesoreria_estado() -> None:
    tramo = _plano(_tramos()["SALDO"])
    assert "H29 es una HIPOTESIS que rompe `R-TESORERIA-ESTADO` a proposito" in tramo
    assert "las retenciones entran al cobrarse o pagarse" in tramo


def test_f150_r40_el_paso_7_con_los_originales_pendientes_y_sin_los_agr() -> None:
    tramo = _plano(_tramos()["CARTERA"])
    assert "`agrupados_pendientes`" in tramo and "a su vencimiento" in tramo
    assert "resta `cartera_viva_agr_con_obra`" in tramo


def test_f150_r40_la_regla_y_la_ficha_cuentan_el_saldo() -> None:
    regla = _reglas()["R-CAJA-HIPOTESIS"]
    assert "tesoreria.saldo_partida_obra" in regla["ambito"]
    texto = _plano(regla["regla"])
    assert "(ocho pasos;" in texto and "siete pasos" not in texto
    assert "el saldo de partida (paso 0) va CON IVA" in texto
    fichas = _fichas_tesoreria()
    assert "SALDO" in fichas["hipotesis_caja"]["columnas"]["paso_receta"]["valores"]
    ficha = fichas["saldo_partida_obra"]
    assert ficha["clave_negocio"] == ["obra_id"] and ficha["consumo_recomendado"] is True


def test_f150_r32_version_65_con_su_nota() -> None:
    glob = yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))
    assert int(glob["version"]) >= 65
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 65 (F-150, 2026-10-30)" in texto


def test_f150_r43_el_paso_0_suma_el_iva_neto_ya_recuperado() -> None:
    tramo = _plano(_tramos()["SALDO"])
    assert "+ el IVA neto ya recuperado (`iva_soportado_pagado` \u2212 `iva_repercutido_cobrado`" in tramo
    for opcion, columnas in (("MENSUAL_REDEME", "_hasta_4m"), ("COMPENSA_EMPRESA", "todo"),
                             ("ANUAL", "_hasta_4t")):
        assert f"`{opcion}`: {columnas}" in tramo, opcion
    assert "H30" in tramo


def test_f150_r43_el_paso_6_con_el_h13_de_la_obra() -> None:
    tramo = _plano(_tramos()["IVA"])
    assert "H13 DE LA OBRA" in tramo and "H30" in tramo


def test_f150_r32_version_66_con_su_nota() -> None:
    glob = yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))
    assert int(glob["version"]) >= 66
    assert "# version 66 (F-150, 2026-10-30)" in (DICC / "00_global.yaml").read_text(encoding="utf-8")
