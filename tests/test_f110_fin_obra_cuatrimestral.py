# tests/test_f110_fin_obra_cuatrimestral.py
"""
F-110 · Sin inicio de garantia, el fin de obra es el ultimo mes planificado de
la ULTIMA version cuatrimestral de la obra + 1 mes (sustituye al ultimo cierre
con movimiento + 1 mes de F-095).

Decision del humano del 2026-09-25 (cambia H1 de F-095): el fin de obra es
(1) el inicio del periodo de garantia; (2) si no lo hay, el ultimo mes con
importe planificado de la ultima `Cuatrimestral` + 1 mes, al ultimo dia del mes
siguiente; (3) si tampoco, SIN FECHA. `ultimo_cierre` se queda como columna
INFORMATIVA (D5) y ya no interviene. Ejemplo literal del humano: «el
cuatrimestral de junio 26 puede tener planificada la obra hasta marzo 28;
entonces el dia a partir del que contar las retenciones seria el 30 de abril».

Suite offline (R22): texto del SQL sin comentarios `--`, YAML del diccionario,
cableado del step y orden topologico de la composicion real. Las cifras
(32 obras / 2.960.583,38 EUR, 50 / 260.028,59 sin fecha...) son verificacion
MANUAL tras el build: aqui no hay red ni BBDD.
"""

from __future__ import annotations

import inspect
import re
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from tests.test_f095_retenciones_contables import (
    DIR_DICCIONARIO,
    DIR_RET,
    DOC_ARQUITECTURA,
    DOC_AZURE_APPS,
    FIN_OBRA,
    VISTAS,
    _bloque,
    _crudo,
    _cte,
    _ficha,
    _sql,
    _texto_ficha,
    _yaml,
)

FUENTES = ["INICIO_GARANTIA", "ULTIMO_CUATRIMESTRAL_MAS_1_MES"]

FIN_OBRA_ESPERADO = (
    "CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia "
    "WHEN b.ultimo_mes_planificado IS NOT NULL THEN "
    "(b.ultimo_mes_planificado + INTERVAL '2 months' - INTERVAL '1 day')::DATE "
    "END AS fecha_fin_obra"
)
FUENTE_ESPERADA = (
    "CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA' "
    "WHEN b.ultimo_mes_planificado IS NOT NULL THEN 'ULTIMO_CUATRIMESTRAL_MAS_1_MES' "
    "END AS fuente_fin_obra"
)


def _guarda() -> str:
    return _bloque(FIN_OBRA, "DO $$", "END $$;")


def _mas_un_mes(mes: date) -> date:
    """Aplica a `mes` la aritmetica QUE ESTA ESCRITA en el SQL del fin de obra.

    Lee del texto de `05_fin_obra.sql` los dos INTERVAL de la rama del
    cuatrimestral y los ejecuta en Python: si alguien cambia '2 months' o
    '1 day', el ejemplo del humano deja de dar el 30 de abril.
    """
    calculo = _cte(FIN_OBRA, "fin")
    m = re.search(
        r"\(b\.ultimo_mes_planificado \+ INTERVAL '(\d+) months?' - INTERVAL '(\d+) days?'\)::DATE",
        calculo,
    )
    assert m, "no encuentro la aritmetica del +1 mes sobre ultimo_mes_planificado (D3)"
    meses, dias = int(m.group(1)), int(m.group(2))
    total = mes.year * 12 + (mes.month - 1) + meses
    return date(total // 12, total % 12 + 1, mes.day) - timedelta(days=dias)


# ===========================================================================
# R1-R4 · la version cuatrimestral
# ===========================================================================


def test_f110_r1_la_ultima_cuatrimestral_por_numero() -> None:
    cuat = _cte(FIN_OBRA, "cuatrimestral")
    assert "SELECT v.obra_id, MAX(v.version) AS version_cuatrimestral" in cuat, (
        "la de MAYOR numero de version (D1)"
    )
    assert "FROM mart.master_versiones_tipadas v" in cuat
    assert "WHERE v.tipo_master = 'Cuatrimestral'" in cuat
    assert "GROUP BY v.obra_id" in cuat
    assert "ambito_id" not in cuat, "en cualquiera de los dos ambitos master (8 y 11)"
    for vetado in ("version_fec_efectiva", "version_fec_creacion", "MIN("):
        assert vetado not in cuat, f"`{vetado}`: la version se elige por numero (D1)"


def test_f110_r2_no_reclasifica_versiones() -> None:
    texto = _sql(FIN_OBRA)
    for vetado in ("version_tex", "LIKE", "UPPER(", "version_master_vigente", "Sin clasificar"):
        assert vetado not in texto, f"`{vetado}`: el tipo de version lo decide F-078, no este fichero (R2)"
    assert texto.count("tipo_master") == 2, "solo el filtro de la guarda y el del CTE"


def test_f110_r3_solo_por_obra_id() -> None:
    texto = _sql(FIN_OBRA)
    plan = _cte(FIN_OBRA, "plan")
    assert (
        "LEFT JOIN stg.plan_mensual pm ON pm.obra_id = c.obra_id "
        "AND pm.version = c.version_cuatrimestral AND pm.ambito_id IN (8, 11)"
    ) in plan
    assert "LEFT JOIN plan pl ON pl.obra_id = obr.ide" in _cte(FIN_OBRA, "base")
    for cte in ("cuatrimestral", "plan"):
        cuerpo = _cte(FIN_OBRA, cte)
        for vetado in ("codigo_obra", "clave_obra", "con.cod", "raw.con"):
            assert vetado not in cuerpo, f"`{vetado}` en `{cte}`: se empareja por obra_id (R-CODIGO-POR-EMPRESA)"
    assert "obra_principal" not in texto and "maestro." not in texto


def test_f110_r4_publica_version_cuatrimestral() -> None:
    base = _cte(FIN_OBRA, "base")
    assert "pl.version_cuatrimestral AS version_cuatrimestral" in base
    assert "c.version_cuatrimestral" in _cte(FIN_OBRA, "plan")
    final = _bloque(FIN_OBRA, "FROM base b )", "FROM fin f;")
    assert "f.version_cuatrimestral" in final


# ===========================================================================
# R5-R7 · el ultimo mes planificado
# ===========================================================================


def test_f110_r5_ultimo_mes_con_importe_planificado() -> None:
    plan = _cte(FIN_OBRA, "plan")
    assert (
        "SELECT c.obra_id, c.version_cuatrimestral, "
        "MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0) AS ultimo_mes_planificado"
    ) in plan, "el ultimo mes con importe planificado, de coste o de venta (D2)"
    assert "FROM cuatrimestral c" in plan
    assert "GROUP BY c.obra_id, c.version_cuatrimestral" in plan
    assert "pl.ultimo_mes_planificado AS ultimo_mes_planificado" in _cte(FIN_OBRA, "base")
    final = _bloque(FIN_OBRA, "FROM base b )", "FROM fin f;")
    assert "f.ultimo_mes_planificado" in final


def test_f110_r5_ejemplo_del_humano() -> None:
    """«hasta marzo 28 ... el dia a partir del que contar seria el 30 de abril»."""
    assert _mas_un_mes(date(2028, 3, 1)) == date(2028, 4, 30)
    # y la convencion vale en cualquier mes: febrero bisiesto, fin de ano
    assert _mas_un_mes(date(2028, 1, 1)) == date(2028, 2, 29)
    assert _mas_un_mes(date(2026, 11, 1)) == date(2026, 12, 31)
    assert _mas_un_mes(date(2026, 12, 1)) == date(2027, 1, 31)
    texto = _texto_ficha(_ficha("fin_obra"))
    assert "marzo 28" in texto and "30 de abril" in texto, "la ficha trae el ejemplo literal"


def test_f110_r6_sin_mes_planificado_no_toma_fecha() -> None:
    plan = _cte(FIN_OBRA, "plan")
    assert "LEFT JOIN stg.plan_mensual pm" in plan, (
        "una cuatrimestral sin filas de plan sigue publicando su version, con mes NULL"
    )
    assert "WHERE" not in plan.replace("FILTER (WHERE", ""), (
        "el filtro de importe va en el FILTER: si todo es cero, el mes queda NULL (R6)"
    )
    assert "WHEN b.ultimo_mes_planificado IS NOT NULL THEN" in _cte(FIN_OBRA, "fin")


def test_f110_r7_la_cola_a_cero_no_es_plan() -> None:
    plan = _cte(FIN_OBRA, "plan")
    assert "FILTER (WHERE pm.importe_mes <> 0)" in plan
    assert "MAX(pm.anio_mes) AS" not in plan, "la ultima FILA no es el ultimo mes planificado (R7)"
    for vetado in ("importe_mes > 0", "importe_origen", "pct_", "can_mes"):
        assert vetado not in plan, f"`{vetado}`: el criterio es importe_mes <> 0 (D2)"


# ===========================================================================
# R8-R13 · el fin de obra, el ultimo cierre informativo y lo que no cambia
# ===========================================================================


def test_f110_r8_fin_de_obra() -> None:
    assert FIN_OBRA_ESPERADO in _cte(FIN_OBRA, "fin"), (
        "garantia; si no, ultimo dia del mes siguiente al ultimo mes planificado; si no, NULL"
    )


def test_f110_r9_fuente_del_fin_de_obra() -> None:
    assert FUENTE_ESPERADA in _cte(FIN_OBRA, "fin")
    assert "ULTIMO_CIERRE_MAS_1_MES" not in _sql(FIN_OBRA), "ese valor deja de existir (R9)"
    valores = set(re.findall(r"'([A-Z_]+_[A-Z_]+)'", _cte(FIN_OBRA, "fin")))
    assert valores == set(FUENTES), "sin mas valores"
    assert _ficha("fin_obra")["columnas"]["fuente_fin_obra"]["valores"] == FUENTES
    assert _ficha("v_retencion_contable_obra")["columnas"]["fuente_fin_obra"]["valores"] == FUENTES


def test_f110_r10_ultimo_cierre_informativo() -> None:
    cierres = _cte(FIN_OBRA, "cierres")
    assert "SELECT f.obra_id, MAX(f.anio_mes) AS ultimo_cierre" in cierres, "regla de F-095 (D5)"
    assert "FROM cierre.fact_cierre_mensual f WHERE f.ejecutado_mes <> 0" in cierres
    assert "ci.ultimo_cierre AS ultimo_cierre" in _cte(FIN_OBRA, "base")
    assert "f.ultimo_cierre" in _bloque(FIN_OBRA, "FROM base b )", "FROM fin f;")
    assert set(re.findall(r"(?<![\w])cierre\.(\w+)", _sql(FIN_OBRA))) == {"fact_cierre_mensual"}
    columna = _texto_ficha(_ficha("fin_obra")["columnas"]["ultimo_cierre"])
    assert "INFORMATIVA" in columna, "la ficha dice que ya no interviene"


def test_f110_r10_ultimo_cierre_no_interviene() -> None:
    """R10 y R12: `ultimo_cierre` no entra ni en el fin, ni en la fuente, ni en el vencimiento."""
    assert "ultimo_cierre" not in _cte(FIN_OBRA, "fin")
    vencimiento = _bloque(FIN_OBRA, "f.fuente_plazo, (", "AS fecha_vencimiento")
    assert "ultimo_cierre" not in vencimiento
    terminada = _bloque(FIN_OBRA, "f.fuente_fin_obra, (", "AS terminada_sin_fin_obra")
    assert "ultimo_cierre" not in terminada


def test_f110_r11_sin_fecha_no_se_inventa() -> None:
    texto = _sql(FIN_OBRA)
    assert "ELSE" not in _cte(FIN_OBRA, "fin"), "sin garantia ni cuatrimestral con plan, NULL (R11)"
    assert (
        "(f.fecha_fin_obra IS NULL AND COALESCE(f.estado_obra, 0) IN (19, 21, 23, 25)) "
        "AS terminada_sin_fin_obra"
    ) in texto


def test_f110_r12_informativas_fuera_del_fin_de_obra() -> None:
    calculo = _cte(FIN_OBRA, "fin")
    vencimiento = _bloque(FIN_OBRA, "f.fuente_plazo, (", "AS fecha_vencimiento")
    for informativa in ("fecha_fin_real", "fecha_recepcion_provisional", "fecha_fin_prevista"):
        assert informativa not in calculo, f"`{informativa}` es solo informativa (R12)"
        assert informativa not in vencimiento


def test_f110_r13_plazo_y_vencimiento_como_en_f095() -> None:
    texto = _sql(FIN_OBRA)
    assert "constantes AS ( SELECT 12 AS plazo_fijo_meses )" in texto
    assert len(re.findall(r"(?<![\w.])12(?![\w.])", texto)) == 1, "el 12 en UNA constante"
    assert (
        "COALESCE(oc.plazo_retencion, oc.plazo_garantia, k.plazo_fijo_meses)::INT AS plazo_meses"
    ) in texto
    assert (
        "CASE WHEN oc.plazo_retencion IS NOT NULL THEN 'PLAZO_RETENCION_CLIENTE' "
        "WHEN oc.plazo_garantia IS NOT NULL THEN 'PLAZO_GARANTIA_CLIENTE' "
        "ELSE 'PLAZO_FIJO_12' END AS fuente_plazo"
    ) in texto
    assert (
        "(f.fecha_fin_obra + make_interval(months => f.plazo_meses))::DATE AS fecha_vencimiento"
    ) in texto
    for vetado in ("fecven", "fecha_documento", "fecha_prevista_devolucion", "CURRENT_DATE"):
        assert vetado not in texto, f"`{vetado}`: la fecha de la factura no interviene (R13)"


# ===========================================================================
# R14-R17 · la guarda y la dependencia del paso
# ===========================================================================


def test_f110_r14_guarda_antes_del_drop() -> None:
    texto = _sql(FIN_OBRA)
    guarda = _guarda()
    assert guarda.count("RAISE EXCEPTION 'fin_obra: ") == 4, "cuatro fallos, todos con el nombre del sub-paso"
    assert guarda.count("RAISE EXCEPTION") == 4
    assert texto.index("DO $$") < texto.index("DROP TABLE IF EXISTS retenciones.fin_obra"), (
        "la guarda va ANTES de dropear la tabla publicada (R14)"
    )


def test_f110_r14_guarda_de_la_version_y_del_plan() -> None:
    guarda = _guarda()
    assert (
        "IF to_regclass('mart.master_versiones_tipadas') IS NULL THEN "
        "RAISE EXCEPTION 'fin_obra: no existe la tabla mart.master_versiones_tipadas; "
        "lanza build-mart antes de build-retenciones';"
    ) in guarda
    assert (
        "IF NOT EXISTS (SELECT 1 FROM mart.master_versiones_tipadas "
        "WHERE tipo_master = 'Cuatrimestral') THEN RAISE EXCEPTION 'fin_obra: "
    ) in guarda
    assert (
        "IF NOT EXISTS (SELECT 1 FROM stg.plan_mensual WHERE ambito_id IN (8, 11)) THEN "
        "RAISE EXCEPTION 'fin_obra: "
    ) in guarda


def test_f110_r14_guarda_del_cierre_solo_de_existencia() -> None:
    guarda = _guarda()
    assert (
        "IF to_regclass('cierre.fact_cierre_mensual') IS NULL THEN "
        "RAISE EXCEPTION 'fin_obra: "
    ) in guarda, "la de existencia de F-095 se conserva"
    assert "SELECT 1 FROM cierre.fact_cierre_mensual" not in guarda, (
        "una tabla del cierre VACIA ya no tumba el vencimiento: solo deja ultimo_cierre a NULL"
    )
    assert "esta vacia" not in guarda


def test_f110_r15_depends_on_intacto() -> None:
    from etl_sigrid.application.steps.build_retenciones_step import BuildRetencionesStep

    assert BuildRetencionesStep(SimpleNamespace()).depends_on == ["ingest_raw"], (
        "D4: un fallo de stg, mart o cierre no deja la noche sin retenciones"
    )


def test_f110_r16_orden_topologico() -> None:
    import main
    from etl_sigrid.application.orchestrator import Orchestrator

    ajustes = SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        )
    )
    orden = [p.name for p in Orchestrator(main.build_pipeline_steps(ajustes))._topological_sort()]
    assert orden.index("build_stg") < orden.index("build_retenciones"), (
        "stg.plan_mensual de la MISMA noche (D4)"
    )
    assert orden.index("build_mart") < orden.index("build_retenciones"), (
        "mart.master_versiones_tipadas de la MISMA noche (D4)"
    )


def test_f110_r17_step_documenta_las_tres_lecturas() -> None:
    from etl_sigrid.application.steps import build_retenciones_step
    from etl_sigrid.application.steps.build_retenciones_step import BuildRetencionesStep

    doc = build_retenciones_step.__doc__ or ""
    comentario = inspect.getsource(BuildRetencionesStep.depends_on.fget)
    for texto in (doc, comentario):
        for lectura in ("mart.master_versiones_tipadas", "stg.plan_mensual", "cierre.fact_cierre_mensual"):
            assert lectura in texto, f"el step no cita `{lectura}` (R17)"
        assert "F-110" in texto
        assert "informativ" in texto
    assert "No necesita `stg` ni `mart`" not in doc, "ya los necesita (de la misma noche)"
    paso = BuildRetencionesStep(SimpleNamespace())
    assert (paso.name, paso.stage) == ("build_retenciones", "build_retenciones")
    assert [s.name for s in build_retenciones_step.SUB_PASOS] == [
        "setup", "movimientos", "views", "apuntes", "saldo", "fin_obra", "views_contables",
    ]


# ===========================================================================
# R18-R20 · la vista y el diccionario
# ===========================================================================


def test_f110_r18_vista_sin_cambio_de_sql() -> None:
    vista = _bloque(VISTAS, "CREATE VIEW retenciones.v_retencion_contable_obra AS", ";")
    assert (
        "CASE WHEN s.obra_id IS NULL THEN 'SIN_OBRA' "
        "WHEN f.fecha_vencimiento IS NULL THEN 'SIN_FIN_OBRA' "
        "WHEN f.fecha_vencimiento < CURRENT_DATE THEN 'VENCIDA' "
        "ELSE 'PENDIENTE' END AS estado_vencimiento"
    ) in vista
    assert "FROM retenciones.saldo_contable s LEFT JOIN retenciones.fin_obra f ON f.obra_id = s.obra_id" in vista
    cabecera = _crudo(VISTAS).split("DROP ", 1)[0]
    assert "SIN_FIN_OBRA  la obra no tiene ni inicio de garantia ni cuatrimestral con plan" in cabecera
    ficha = _ficha("v_retencion_contable_obra")["descripcion"]
    assert "ni inicio de garantia ni cuatrimestral con plan" in ficha
    assert "cierre con movimiento" not in ficha


def test_f110_r19_la_ficha_de_fin_obra() -> None:
    ficha = _ficha("fin_obra")
    descripcion = ficha["descripcion"]
    for dato in (
        "F-110", "2026-09-25", "ultimo mes planificado", "Cuatrimestral", "ultimo dia del mes siguiente",
        "marzo 28", "30 de abril", "ULTIMO_CUATRIMESTRAL_MAS_1_MES", "INFORMATIVA",
        "mart.master_versiones_tipadas", "stg.plan_mensual",
    ):
        assert dato in descripcion, f"la descripcion de fin_obra no dice «{dato}» (R19)"
    # cifras antes y despues (design.md §Medidas)
    for dato in (
        "5.026.655,18", "3.120.260,42", "2.960.583,38", "100.351,55", "260.028,59",
        "159.677,04", "15 de 117", "1-0692", "43.476,54",
    ):
        assert dato in descripcion, f"la ficha de fin_obra no trae la cifra «{dato}» (R19)"
    assert "2026-09-22" in descripcion, "las de F-095 quedan como historicas y con fecha"
    columnas = ficha["columnas"]
    assert list(columnas).index("version_cuatrimestral") == list(columnas).index("ultimo_cierre") + 1
    assert list(columnas).index("ultimo_mes_planificado") == list(columnas).index("ultimo_cierre") + 2
    assert "nulo_significa" in columnas["version_cuatrimestral"]
    assert "nulo_significa" in columnas["ultimo_mes_planificado"]
    assert "cuatrimestral" in _texto_ficha(columnas["fecha_fin_obra"])
    assert "ultimo cierre" not in _texto_ficha(columnas["fecha_fin_obra"])


def test_f110_r20_version_del_diccionario() -> None:
    from etl_sigrid.domain.inventario import objetos_de_sql

    assert int(_yaml("00_global.yaml")["version"]) >= 34
    cabecera = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "version 34 (F-110" in cabecera
    textos = {f"retenciones/{f.name}": f.read_text(encoding="utf-8") for f in sorted(DIR_RET.glob("*.sql"))}
    assert ("retenciones", "fin_obra") in {(o.esquema, o.objeto) for o in objetos_de_sql(textos)}
    assert _ficha("fin_obra")["clave_negocio"] == ["obra_id"], "check-unicidad la cubre sin tocar su codigo"


# ===========================================================================
# R21-R23 · pruebas y propagacion
# ===========================================================================

REESCRITOS = (
    "test_f095_r19_fin_obra_y_fuente",
    "test_f095_r20_sin_fecha_no_se_inventa",
    "test_f095_r21_guarda_cierre_vacio",
    "test_f095_r21_un_fallo_en_fin_obra_sale_con_su_nombre",
    "test_f095_d7_solo_fact_cierre",
    "test_f095_r28_las_fichas_traen_las_cifras_medidas",
)


@pytest.mark.parametrize("nombre", REESCRITOS)
def test_f110_r21_los_de_f095_reescritos_citan_f110(nombre: str) -> None:
    from tests import test_f095_retenciones_contables as f095

    funcion = getattr(f095, nombre, None)
    assert funcion is not None, f"{nombre} se reescribe, no se borra (R21)"
    assert "F-110" in (funcion.__doc__ or ""), f"{nombre} no cita F-110 en su docstring"


def test_f110_r22_sin_red_ni_bbdd() -> None:
    fuente = inspect.getsource(inspect.getmodule(test_f110_r22_sin_red_ni_bbdd))
    for vetado in ("psycopg", "requests", "httpx", "build_postgres_client(", "PostgresClient"):
        assert vetado not in fuente.replace(f'"{vetado}"', ""), f"`{vetado}`: la suite es offline (R22)"


def test_f110_r23_arquitectura() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    parrafo = texto.split("El vencimiento cuenta desde el **fin de obra**", 1)[1].split("\n\n", 1)[0]
    for termino in ("F-110", "cuatrimestral", "mart.master_versiones_tipadas", "stg.plan_mensual",
                    "misma noche", "informativ", "una noche de desfase"):
        assert termino in parrafo, f"ARCHITECTURE.md no dice «{termino}» en la vineta de la retencion"


def test_f110_r23_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("F-110", "mart.master_versiones_tipadas", "stg.plan_mensual",
                    "ULTIMO_CUATRIMESTRAL_MAS_1_MES", "informativ"):
        assert termino in texto, f"azure-apps no dice «{termino}» (R23)"
    fila = next(linea for linea in texto.splitlines() if linea.startswith("| `retenciones.fin_obra`"))
    assert "cuatrimestral" in fila and "último cierre + 1 mes" not in fila
