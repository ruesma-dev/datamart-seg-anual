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


def test_f150_r32_docs_dicen_27_hipotesis() -> None:
    assert "las 27 (H01-H27 desde F-150)" in _texto(RUTA_ARCHITECTURE)
    claude = _texto(RUTA_CLAUDE)
    assert "las 27 hipótesis de `config/hipotesis_caja.yaml`" in claude
    assert "las 23 hipótesis" not in claude
    assert "**la receta**" in claude and "paso_receta" in claude


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
    """El texto de cada paso, de su «n. PASO:» al siguiente."""
    receta = _receta()
    posiciones = []
    for n, paso in enumerate(dom.PASOS_RECETA, start=1):
        marca = f" {n}. {paso}"
        assert marca in receta, f"falta el paso {n}. {paso}"
        posiciones.append(receta.index(marca))
    assert posiciones == sorted(posiciones), "los pasos en el orden de PASOS_RECETA"
    fines = [*posiciones[1:], len(receta)]
    return {p: receta[i:f] for p, i, f in zip(dom.PASOS_RECETA, posiciones, fines, strict=True)}


def test_f150_r2_cada_paso_nombra_sus_hipotesis_y_solo_las_suyas() -> None:
    from etl_sigrid.infrastructure.config.hipotesis_caja_yaml import cargar_hipotesis_caja

    catalogo = cargar_hipotesis_caja(RUTA_YAML_HIPOTESIS).catalogo
    assert len(catalogo) == 27
    for paso, tramo in _tramos().items():
        esperados = {h.codigo for h in catalogo if h.paso_receta == paso}
        assert set(re.findall(r"\bH[0-9]{2}\b", tramo)) == esperados, paso


def test_f150_r3_la_receta_nombra_sus_ingredientes() -> None:
    receta = _receta()
    for ingrediente in (*DEVENGO, "condiciones_contrato_compra", "condiciones_contrato_cliente",
                        "tesoreria.efectos", "cartera_emitida_tras_cierre",
                        "compras.v_pbi_albaranes_sin_facturar", "importe_pendiente_con_coeficientes",
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
    assert "lo de mas de H27 meses NO es caja" in receta and "declara su importe" in receta
    assert "R-ALBARAN-ABSURDO" in receta


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
    assert "las 27 hipotesis (H01-H27)" in _plano(hip["descripcion"])
    assert _plano(hip["grano"]).endswith("(27).")
    assert hip["ejemplos_preguntas"][0] == "Como se pasa paso a paso el devengo de una obra a caja"
    obra = fichas["hipotesis_caja_obra"]
    assert "las 27 hipotesis del catalogo" in _plano(obra["grano"])
    assert "H12" in _plano(obra["descripcion"]) and "ficha de la obra" in _plano(obra["descripcion"])
    glob = yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))
    assert int(glob["version"]) == 63
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 63 (F-150, 2026-10-28)" in texto
