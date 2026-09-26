# tests/test_f056_contabilidad.py
"""
F-056 · El mayor y el plan de cuentas como arbol: el esquema `contabilidad`,
comprobado OFFLINE (R36).

Ningun test toca red ni base de datos: las tres tablas se construyen contra el
PostgreSQL compartido con `albaranes` y `partes` EN PRODUCCION, asi que
construirlas desde la suite seria escribir en produccion. Se fija por escrito,
sobre el TEXTO del SQL (sin comentarios `--`), el YAML del diccionario y el
cableado del step y de `main.py`, lo que la spec decidio midiendo el
2026-09-26. Las cifras contra la base (641 apuntes de `1-4308000197`, el saldo
5.345.557,80 de la 434 en 2026, el recuento = `raw.apu`) son verificacion
MANUAL del humano (T22-T24, consultas C1-C4 de `progress/spec_F-056.md`).

Mismo estilo que `tests/test_f095_retenciones_contables.py` y
`tests/test_f057_personal.py`. Los helpers se COPIAN y no se importan: la suite
de otra feature no es una API.

Cuatro familias:
1. El SQL de los tres `CREATE TABLE`, requisito a requisito (R6-R26).
2. El contrato expresion a expresion de esos tres `CREATE` (lo que mata los
   mutantes de la campana sistematica: la formula, no solo el alias).
3. La propagacion del esquema nuevo (R1-R5, R31-R32): step, DAG, `main.py`,
   esquemas de consumo, `ESQUEMAS_DEL_DATAMART`, `check-declarados`.
4. El diccionario (R27-R30): tres fichas, la regla dura y las fichas de `raw`
   que decian cosas falsas.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_CON = DIR_SQL / "contabilidad"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
RUTA_PENDIENTES = RAIZ / "config" / "objetos_pendientes.yaml"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_CLAUDE = RAIZ / "CLAUDE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

SETUP = "00_setup.sql"
PLAN = "01_plan_cuentas.sql"
MAYOR = "02_mayor.sql"
SALDOS = "03_saldos_cuenta_mes.sql"
FICHEROS = [SETUP, PLAN, MAYOR, SALDOS]

TABLAS = ("plan_cuentas", "mayor", "saldos_cuenta_mes")

#: Las columnas de cada tabla, EN ORDEN. Son el contrato con el consumidor y con
#: las fichas del diccionario (R27): una columna nueva o renombrada obliga a
#: tocar esto delante del reviewer.
COLUMNAS = {
    "plan_cuentas": [
        "cuenta_id", "empresa_id", "empresa_nombre", "codigo_cuenta",
        "clave_cuenta", "nombre_cuenta", "nivel", "nombre_nivel",
        "es_imputable", "grupo_pgc", "cuenta_padre_id",
        "cuenta_padre_declarada_id", "padre_declarado_difiere", "grupo_id",
        "subgrupo_id", "cuenta_3_id", "subcuenta_id", "ruta_codigos",
        "fecha_baja", "es_activa",
    ],
    "mayor": [
        "apunte_id", "asiento_id", "codigo_asiento", "posicion", "fecha",
        "fecha_asiento", "fecha_difiere", "ejercicio", "mes", "empresa_id",
        "cuenta_id", "codigo_cuenta", "nombre_cuenta", "clave_cuenta",
        "concepto", "documento", "punteo", "clase_origen", "clase_asiento",
        "debe", "haber", "importe", "importe_saldo", "saldo_acumulado",
        "centro_coste_id", "obra_id", "codigo_obra", "clave_obra",
        "tercero_id", "tercero_nombre",
    ],
    "saldos_cuenta_mes": [
        "cuenta_id", "empresa_id", "ejercicio", "mes", "num_apuntes", "debe",
        "haber", "importe_apertura", "importe_movimiento",
        "importe_regularizacion", "importe_cierre", "importe_saldo",
        "saldo_acumulado",
    ],
}


@cache
def _crudo(nombre: str) -> str:
    ruta = DIR_CON / nombre
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _sql(nombre: str) -> str:
    """El SQL sin comentarios `--` y con los blancos colapsados."""
    sin_comentarios = "\n".join(
        linea.split("--", 1)[0] for linea in _crudo(nombre).splitlines()
    )
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _bloque(nombre: str, desde: str, hasta: str | None = None) -> str:
    """El trozo del SQL entre dos marcas (la segunda excluida)."""
    texto = _sql(nombre)
    assert desde in texto, f"no encuentro «{desde}» en {nombre}"
    trozo = texto.split(desde, 1)[1]
    if hasta is not None:
        assert hasta in trozo, f"no encuentro «{hasta}» detras de «{desde}» en {nombre}"
        trozo = trozo.split(hasta, 1)[0]
    return trozo


def _create(nombre: str, tabla: str) -> str:
    """El `CREATE TABLE contabilidad.<tabla> AS ...` hasta su `;`."""
    return _bloque(nombre, f"CREATE TABLE contabilidad.{tabla} AS", ";")


def _cte(nombre: str, cte: str) -> str:
    """El cuerpo de un CTE, con los parentesis equilibrados."""
    texto = _sql(nombre)
    marca = re.search(rf"(?<![\w.]){cte} AS \(", texto)
    assert marca, f"no encuentro el CTE «{cte}» en {nombre}"
    nivel = 1
    for pos in range(marca.end(), len(texto)):
        if texto[pos] == "(":
            nivel += 1
        elif texto[pos] == ")":
            nivel -= 1
            if nivel == 0:
                return texto[marca.end():pos]
    raise AssertionError(f"el CTE «{cte}» de {nombre} no cierra")


def _final(nombre: str, tabla: str) -> str:
    """El SELECT final del CREATE: el unico SELECT de nivel 0 (los CTE van dentro)."""
    cuerpo = _create(nombre, tabla)
    prof = _profundidades(cuerpo)
    nivel_0 = [m.start() for m in re.finditer(r"(?<![\w.])SELECT ", cuerpo) if prof[m.start()] == 0]
    assert nivel_0, f"{tabla}: no encuentro el SELECT final"
    return cuerpo[nivel_0[-1]:].strip()


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(objeto: str) -> dict:
    return _yaml("contabilidad.yaml")["objetos"][objeto]


def _texto_ficha(ficha: dict) -> str:
    return yaml.safe_dump(ficha, allow_unicode=True, width=10_000)


def _settings_falso() -> SimpleNamespace:
    """Lo minimo que miran los constructores de los steps del pipeline."""
    return SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        )
    )


# ===========================================================================
# R1-R5 · el esquema y el paso
# ===========================================================================


def test_f056_r1_esquema_y_paso_propio() -> None:
    from etl_sigrid.application.steps import build_contabilidad_step
    from etl_sigrid.application.steps.build_contabilidad_step import BuildContabilidadStep

    assert "CREATE SCHEMA IF NOT EXISTS contabilidad;" in _sql(SETUP)
    paso = BuildContabilidadStep(SimpleNamespace())
    assert paso.name == "build_contabilidad"
    assert paso.stage == "build_aux"
    assert paso.depends_on == ["ingest_raw"], (
        "la vista maestro.centros_coste es SQL puro sobre raw: declarar "
        "build_maestros ataria la contabilidad a otro esquema (design)"
    )
    assert [s.sql_file for s in build_contabilidad_step.SUB_PASOS] == FICHEROS
    for sub in build_contabilidad_step.SUB_PASOS:
        assert (DIR_CON / sub.sql_file).exists(), f"{sub.sql_file} declarado y no existe"


def test_f056_r1_orden_en_run_all() -> None:
    import main

    nombres = [p.name for p in main.build_pipeline_steps(_settings_falso())]
    assert "build_contabilidad" in nombres, "run-all construye la contabilidad (R1)"
    assert nombres.index("build_personal") < nombres.index("build_contabilidad")
    assert nombres.index("build_contabilidad") < nombres.index("build_cierre")


def test_f056_r1_fn_fecha_misma_forma_que_las_demas() -> None:
    texto = _sql(SETUP)
    assert "CREATE OR REPLACE FUNCTION contabilidad.fn_fecha(d BIGINT) RETURNS DATE" in texto
    assert "IF d IS NULL OR d = 0 THEN RETURN NULL; END IF;" in texto
    assert "RETURN to_date(d::TEXT, 'YYYYMMDD'); EXCEPTION WHEN OTHERS THEN RETURN NULL;" in texto


def test_f056_r2_solo_raw_y_el_puente() -> None:
    for nombre in FICHEROS:
        texto = _sql(nombre)
        esquemas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)\.\w+", texto))
        assert esquemas <= {"raw", "contabilidad", "maestro"}, f"{nombre} lee {sorted(esquemas)}"
        assert set(re.findall(r"(?<![\w])maestro\.(\w+)", texto)) <= {"centros_coste"}
        for vetado in ("stg.", "mart.", "cierre.", "compras.", "retenciones.", "personal."):
            assert not re.search(rf"(?<![\w]){re.escape(vetado)}", texto), f"{nombre} nombra {vetado}"
    assert set(re.findall(r"maestro\.(\w+)", _sql(MAYOR))) == {"centros_coste"}


def test_f056_r3_un_fallo_sale_con_su_nombre_y_para(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_contabilidad_step
    from etl_sigrid.application.steps.build_contabilidad_step import BuildContabilidadStep
    from etl_sigrid.domain.entities import StepStatus

    class _PgQueFalla:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []

        def execute_sql_file(self, path: Path) -> None:
            self.ejecutados.append(path.name)
            if path.name == MAYOR:
                raise RuntimeError("mayor: contabilidad.mayor tiene 1 filas y raw.apu tiene 2")

        def count_rows(self, schema: str, table: str) -> int:
            return 1

    pg = _PgQueFalla()
    monkeypatch.setattr(build_contabilidad_step, "build_postgres_client", lambda _s: pg)
    resultado = BuildContabilidadStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en mayor:")
    assert "raw.apu tiene 2" in resultado.error_message
    assert pg.ejecutados == [SETUP, PLAN, MAYOR], "tras el fallo no se ejecuta nada mas"
    assert resultado.finished_at is not None


def test_f056_r3_falta_el_fichero_y_sale_con_su_nombre(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from etl_sigrid.application.steps import build_contabilidad_step
    from etl_sigrid.application.steps.build_contabilidad_step import (
        BuildContabilidadStep,
        _SubStep,
    )
    from etl_sigrid.domain.entities import StepStatus

    class _PgFalso:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []

        def execute_sql_file(self, path: Path) -> None:
            self.ejecutados.append(path.name)

        def count_rows(self, schema: str, table: str) -> int:
            return 1

    pg = _PgFalso()
    monkeypatch.setattr(build_contabilidad_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(
        build_contabilidad_step,
        "SUB_PASOS",
        (
            _SubStep(name="setup", sql_file=SETUP),
            _SubStep(name="fantasma", sql_file="99_no_existe.sql"),
            _SubStep(name="saldos_cuenta_mes", sql_file=SALDOS),
        ),
    )
    resultado = BuildContabilidadStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en fantasma:")
    assert "99_no_existe.sql" in resultado.error_message
    assert pg.ejecutados == [SETUP], "sin fichero, no se sigue"
    assert resultado.finished_at is not None


def test_f056_r3_el_step_encadena_y_cuenta(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_contabilidad_step
    from etl_sigrid.application.steps.build_contabilidad_step import BuildContabilidadStep
    from etl_sigrid.domain.entities import StepStatus

    class _PgFalso:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []
            self.contados: list[tuple[str, str]] = []

        def execute_sql_file(self, path: Path) -> None:
            self.ejecutados.append(path.name)

        def count_rows(self, schema: str, table: str) -> int:
            self.contados.append((schema, table))
            return {"plan_cuentas": 5, "mayor": 7, "saldos_cuenta_mes": 11}[table]

    pg = _PgFalso()
    monkeypatch.setattr(build_contabilidad_step, "build_postgres_client", lambda _s: pg)
    resultado = BuildContabilidadStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS
    assert pg.contados == [("contabilidad", t) for t in TABLAS]
    assert resultado.rows_processed == 23
    assert resultado.finished_at is not None
    assert resultado.error_message is None


def test_f056_r3_sub_pasos_y_sus_tablas() -> None:
    from etl_sigrid.application.steps import build_contabilidad_step

    declarados = [
        (s.name, s.sql_file, s.target_schema, s.target_table)
        for s in build_contabilidad_step.SUB_PASOS
    ]
    assert declarados == [
        ("setup", SETUP, None, None),
        ("plan_cuentas", PLAN, "contabilidad", "plan_cuentas"),
        ("mayor", MAYOR, "contabilidad", "mayor"),
        ("saldos_cuenta_mes", SALDOS, "contabilidad", "saldos_cuenta_mes"),
    ]


def test_f056_r4_comando_suelto_marca_huerfanas_y_no_publica() -> None:
    import main

    assert "build-contabilidad" in main.cli.commands
    fuente = Path(main.__file__).read_text(encoding="utf-8")
    inicio = fuente.index('@cli.command("build-contabilidad")')
    fin = fuente.index("@cli.command(", inicio + 10)
    comando = fuente[inicio:fin]
    assert "ejecucion = _arrancar_ejecucion(pg)" in comando, "R4 de F-024: huerfanas antes de escribir"
    assert "_ejecutar_paso(BuildContabilidadStep(settings), pg, ejecucion)" in comando
    assert "PublicarDiccionarioStep" not in comando, "el comando suelto NO publica (DA-1 de F-006)"


def test_f056_r4_comando_que_escribe_en_la_lista_de_f024() -> None:
    from tests.test_f024_cli import COMANDOS_QUE_ESCRIBEN, STEPS_POR_COMANDO

    assert "build-contabilidad" in COMANDOS_QUE_ESCRIBEN
    assert STEPS_POR_COMANDO["build-contabilidad"] == (
        "BuildContabilidadStep", "build_contabilidad", "build_aux"
    )


def test_f056_r5_nadie_depende_de_build_contabilidad() -> None:
    import main
    from etl_sigrid.application.orchestrator import Orchestrator

    pasos = main.build_pipeline_steps(_settings_falso())
    ordenados = [p.name for p in Orchestrator(pasos)._topological_sort()]
    assert ordenados.index("ingest_raw") < ordenados.index("build_contabilidad")
    for paso in pasos:
        assert "build_contabilidad" not in paso.depends_on, (
            f"`{paso.name}` depende de `build_contabilidad`: un fallo de la "
            "contabilidad tumbaria la noche (R5)"
        )


def test_f056_r5_r_frescura_avisa_de_contabilidad() -> None:
    reglas = {r["codigo"]: r for r in _yaml("00_global.yaml")["reglas"]}
    frescura = reglas["R-FRESCURA"]
    assert "contabilidad" in frescura["ambito"]
    assert "build_contabilidad" in frescura["regla"]


# ===========================================================================
# R6-R12 · contabilidad.plan_cuentas
# ===========================================================================


def test_f056_r6_dos_ramas_grupos_y_auxiliares_sin_filtrar() -> None:
    nodos = _cte(PLAN, "nodos")
    ramas = nodos.split(" UNION ALL ")
    assert len(ramas) == 2, "grupos (tip 16) UNION ALL auxiliares (cua)"
    assert ramas[0].strip().endswith("FROM raw.con c WHERE c.tip = 16"), (
        "los grupos son TODOS los con.tip = 16, sin otro filtro (R6)"
    )
    assert ramas[1].strip().endswith("FROM raw.cua cu JOIN raw.con c ON c.ide = cu.ide"), (
        "las auxiliares son TODAS las de cua, sin filtrar altas ni bajas (R6)"
    )
    final = _final(PLAN, "plan_cuentas")
    assert " WHERE " not in final, "el plan no filtra empresas ni bajas (D1)"


def test_f056_r7_clave_primaria_unica_por_empresa_y_clave_legible() -> None:
    texto = _sql(PLAN)
    assert "ALTER TABLE contabilidad.plan_cuentas ADD PRIMARY KEY (cuenta_id);" in texto
    assert (
        "CREATE UNIQUE INDEX uq_con_plan_empresa_codigo ON contabilidad.plan_cuentas "
        "(empresa_id, codigo_cuenta);"
    ) in texto
    assert "CREATE INDEX idx_con_plan_padre ON contabilidad.plan_cuentas (cuenta_padre_id);" in texto
    assert "n.empresa_id::TEXT || '-' || n.codigo_cuenta AS clave_cuenta" in _final(PLAN, "plan_cuentas")
    assert "c.ide AS cuenta_id" in _cte(PLAN, "nodos"), "cuenta_id es el con.ide (R7)"


def test_f056_r8_nivel_por_la_forma_del_codigo() -> None:
    nodos = _cte(PLAN, "nodos")
    grupos, auxiliares = nodos.split(" UNION ALL ")
    assert "LENGTH(c.cod) AS nivel" in grupos
    assert re.search(r"c\.fecbaj, 5, NULLIF\(cu\.padide, 0\)", auxiliares), "la auxiliar es nivel 5"
    final = _final(PLAN, "plan_cuentas")
    assert (
        "CASE n.nivel WHEN 1 THEN 'GRUPO' WHEN 2 THEN 'SUBGRUPO' WHEN 3 THEN 'CUENTA' "
        "WHEN 4 THEN 'SUBCUENTA' WHEN 5 THEN 'CUENTA_AUXILIAR' END AS nombre_nivel"
    ) in final
    assert "n.nivel = 5 AS es_imputable" in final, "solo la auxiliar es imputable (R8)"


def test_f056_r9_padre_por_prefijo_dentro_de_la_empresa() -> None:
    final = _final(PLAN, "plan_cuentas")
    assert "pad.ide AS cuenta_padre_id" in final
    assert (
        "LEFT JOIN grupos pad ON pad.emp = n.empresa_id AND pad.cod = CASE WHEN n.nivel = 5 "
        "THEN LEFT(n.codigo_cuenta, 4) WHEN n.nivel > 1 THEN LEFT(n.codigo_cuenta, n.nivel - 1) END"
    ) in final, "padre = prefijo inmediato (nivel 5: 4 digitos), en la MISMA empresa (R9)"
    assert _cte(PLAN, "grupos").strip() == "SELECT g.ide, g.emp, g.cod FROM raw.con g WHERE g.tip = 16"
    assert "RECURSIVE" not in _sql(PLAN).upper(), "sin WITH RECURSIVE (design)"


def test_f056_r10_padre_declarado_aparte() -> None:
    nodos = _cte(PLAN, "nodos")
    grupos, auxiliares = nodos.split(" UNION ALL ")
    assert "NULL::INT AS cuenta_padre_declarada_id" in grupos, "los grupos no declaran padre aqui"
    assert "NULLIF(cu.padide, 0)" in auxiliares, "padide = 0 es NULL (R10)"
    final = _final(PLAN, "plan_cuentas")
    assert "n.cuenta_padre_declarada_id," in final
    assert (
        "(n.cuenta_padre_declarada_id IS NOT NULL AND n.cuenta_padre_declarada_id "
        "IS DISTINCT FROM pad.ide) AS padre_declarado_difiere"
    ) in final


def test_f056_r11_ruta_ancestros_y_grupo_pgc() -> None:
    final = _final(PLAN, "plan_cuentas")
    for n, alias in enumerate(("grupo_id", "subgrupo_id", "cuenta_3_id", "subcuenta_id"), 1):
        assert f"g{n}.ide AS {alias}" in final
        cond_nivel = "" if n == 1 else f" AND n.nivel >= {n}"
        assert (
            f"LEFT JOIN grupos g{n} ON g{n}.emp = n.empresa_id{cond_nivel} "
            f"AND g{n}.cod = LEFT(n.codigo_cuenta, {n})"
        ) in final, f"el ancestro de nivel {n} es de la misma empresa y por prefijo (R11)"
    assert (
        "CONCAT_WS(' > ', g1.cod, g2.cod, g3.cod, g4.cod, CASE WHEN n.nivel = 5 "
        "THEN n.codigo_cuenta END) AS ruta_codigos"
    ) in final
    assert "LEFT(n.codigo_cuenta, 1) AS grupo_pgc" in final


def test_f056_r12_empresa_nombre_baja_y_activa() -> None:
    final = _final(PLAN, "plan_cuentas")
    assert "em.empresa_nombre," in final
    assert "LEFT JOIN empresas em ON em.empresa_id = n.empresa_id" in final
    assert _cte(PLAN, "empresas").strip() == (
        "SELECT e.numemp AS empresa_id, MIN(e.res) AS empresa_nombre FROM raw.auxemp e "
        "GROUP BY e.numemp"
    ), "empresa pre-agregada por numemp: una fila por empresa (R12, R24)"
    grupos = _cte(PLAN, "nodos").split(" UNION ALL ")[0]
    for expresion in ("c.emp AS empresa_id", "c.res AS nombre_cuenta", "c.fecbaj AS fecbaj",
                      "c.cod AS codigo_cuenta"):
        assert expresion in grupos
    assert "contabilidad.fn_fecha(n.fecbaj) AS fecha_baja" in final
    assert "COALESCE(n.fecbaj, 0) = 0 AS es_activa" in final


# ===========================================================================
# R13-R24 · contabilidad.mayor
# ===========================================================================


def test_f056_r13_una_fila_por_apunte_sin_filtrar() -> None:
    apuntes = _cte(MAYOR, "apuntes")
    assert apuntes.strip().endswith("FROM raw.apu a LEFT JOIN raw.con asi ON asi.ide = a.asiide"), (
        "ni WHERE ni JOIN que filtre: un apunte sin asiento sigue dentro (R13)"
    )
    assert "a.ide AS apunte_id" in apuntes
    assert "ALTER TABLE contabilidad.mayor ADD PRIMARY KEY (apunte_id);" in _sql(MAYOR)
    for cte in ("fechados", "clasificados", "saldos"):
        assert " WHERE " not in _cte(MAYOR, cte), f"el CTE {cte} filtra apuntes"
    assert " WHERE " not in _final(MAYOR, "mayor")


def test_f056_r14_guarda_de_recuento_con_las_dos_cifras() -> None:
    texto = _sql(MAYOR)
    guarda = _bloque(MAYOR, "DO $$", "END $$;")
    assert texto.index("DO $$") > texto.index("CREATE TABLE contabilidad.mayor AS"), (
        "es una POSTcondicion: va detras del CREATE"
    )
    assert "SELECT count(*) INTO v_mayor FROM contabilidad.mayor;" in guarda
    assert "SELECT count(*) INTO v_apu FROM raw.apu;" in guarda
    assert "IF v_mayor <> v_apu THEN RAISE EXCEPTION 'mayor: " in guarda
    assert "tiene % filas y raw.apu tiene %" in guarda and "v_mayor, v_apu;" in guarda, (
        "el mensaje da LAS DOS cifras (R14)"
    )


def test_f056_r15_las_dos_fechas_y_la_marca() -> None:
    apuntes = _cte(MAYOR, "apuntes")
    assert "contabilidad.fn_fecha(a.fec) AS fecha" in apuntes, "fecha = apu.fec (D6)"
    assert "contabilidad.fn_fecha(asi.fec) AS fecha_asiento" in apuntes, "la del asiento, por los dos saltos"
    fechados = _cte(MAYOR, "fechados")
    assert "EXTRACT(YEAR FROM ap.fecha)::INT AS ejercicio" in fechados
    assert "EXTRACT(MONTH FROM ap.fecha)::INT AS mes" in fechados
    assert "(s.fecha IS DISTINCT FROM s.fecha_asiento) AS fecha_difiere" in _final(MAYOR, "mayor")


def test_f056_r16_empresa_del_asiento_y_cuenta_del_plan() -> None:
    apuntes = _cte(MAYOR, "apuntes")
    assert "asi.emp AS empresa_id" in apuntes, "la empresa es la del ASIENTO (R16)"
    assert "NULLIF(a.cueide, 0) AS cuenta_id" in apuntes, "cueide = 0 -> cuenta NULL, apunte dentro"
    final = _final(MAYOR, "mayor")
    assert "LEFT JOIN contabilidad.plan_cuentas pc ON pc.cuenta_id = s.cuenta_id" in final
    for col in ("codigo_cuenta", "nombre_cuenta", "clave_cuenta"):
        assert f"pc.{col}," in final, f"{col} sale del plan (R16)"


def test_f056_r17_importes_numeric_y_signo_deudor() -> None:
    apuntes = _cte(MAYOR, "apuntes")
    assert "COALESCE(a.deb, 0)::NUMERIC(18, 2) AS debe" in apuntes
    assert "COALESCE(a.hab, 0)::NUMERIC(18, 2) AS haber" in apuntes
    assert "(COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2) AS importe" in apuntes, (
        "importe = debe - haber: positivo es saldo deudor (R17)"
    )


def test_f056_r18_clase_en_orden_sin_distinguir_mayusculas() -> None:
    apuntes = _cte(MAYOR, "apuntes")
    assert (
        "CASE WHEN a.cla = 3 OR a.res ILIKE 'asiento de cierre%' THEN 'CIERRE' "
        "WHEN a.cla = -1 OR a.res ILIKE 'asiento de apertura%' THEN 'APERTURA' "
        "WHEN a.cla = 1 OR a.res ILIKE 'asiento de regulariz%' THEN 'REGULARIZACION' "
        "ELSE 'NORMAL' END AS clase_bruta"
    ) in apuntes, "el orden y los literales de R18"
    assert " LIKE '" not in _sql(MAYOR).replace(" ILIKE '", ""), "124 aperturas en mayusculas escapan a LIKE"
    assert not re.search(r"\.ori\b", _sql(MAYOR)), "asi.ori vale 0 en 788.326 de 788.328 (R18)"


def test_f056_r18_saldo_inicial_por_anti_join_de_cierres() -> None:
    assert _cte(MAYOR, "cierres").strip() == (
        "SELECT DISTINCT f.cuenta_id, f.ejercicio FROM fechados f WHERE f.clase_bruta = 'CIERRE'"
    )
    clasificados = _cte(MAYOR, "clasificados")
    assert (
        "CASE WHEN f.clase_bruta = 'APERTURA' AND ci.cuenta_id IS NULL THEN 'SALDO_INICIAL' "
        "ELSE f.clase_bruta END AS clase_asiento"
    ) in clasificados
    assert (
        "LEFT JOIN cierres ci ON ci.cuenta_id = f.cuenta_id AND ci.ejercicio = f.ejercicio - 1"
    ) in clasificados, "el cierre de ESA cuenta el ejercicio ANTERIOR"
    assert "NOT EXISTS" not in _sql(MAYOR), "anti-join: un NOT EXISTS correlacionado no se hashea"


def test_f056_r19_importe_saldo_sin_cierre_ni_apertura() -> None:
    assert (
        "CASE WHEN c.clase_asiento IN ('CIERRE', 'APERTURA') THEN 0::NUMERIC(18, 2) "
        "ELSE c.importe END AS importe_saldo"
    ) in _cte(MAYOR, "saldos")


def test_f056_r20_saldo_acumulado_por_cuenta_y_en_orden() -> None:
    assert (
        "SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id ORDER BY s.fecha, "
        "s.codigo_asiento, s.posicion, s.apunte_id )::NUMERIC(18, 2) AS saldo_acumulado"
    ) in _final(MAYOR, "mayor")


def test_f056_r21_obra_solo_por_el_centro_del_apunte() -> None:
    apuntes = _cte(MAYOR, "apuntes")
    assert "NULLIF(a.cenide, 0) AS centro_coste_id" in apuntes
    final = _final(MAYOR, "mayor")
    assert "LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = s.centro_coste_id" in final
    for expresion in ("s.centro_coste_id,", "cc.obra_id,", "cc.codigo_obra,",
                      "cc.empresa::TEXT || '-' || cc.codigo_obra AS clave_obra"):
        assert expresion in final
    texto = _sql(MAYOR)
    assert not re.search(r"\.obr\b", texto), "apu.obr (142 filas) esta vetado (R21)"
    assert not re.search(r"\bobride\b", texto), "el campo de obra de cen (a 0) esta vetado (R21)"
    assert "raw.cen" not in texto and "raw.obr" not in texto, "no se busca la obra por otra via"


def test_f056_r22_tercero() -> None:
    assert "NULLIF(a.empide, 0) AS tercero_id" in _cte(MAYOR, "apuntes")
    final = _final(MAYOR, "mayor")
    assert "LEFT JOIN raw.con ter ON ter.ide = s.tercero_id" in final
    assert "ter.res AS tercero_nombre" in final


def test_f056_r23_columnas_del_apunte() -> None:
    apuntes = _cte(MAYOR, "apuntes")
    for expresion in ("asi.cod AS codigo_asiento", "a.pos AS posicion", "a.res AS concepto",
                      "a.doc AS documento", "a.pun AS punteo", "a.cla AS clase_origen",
                      "a.asiide AS asiento_id"):
        assert expresion in apuntes, f"falta «{expresion}» (R23)"


def test_f056_r24_ninguna_union_multiplica() -> None:
    """Cada JOIN del mayor va por PK o contra un conjunto con una fila por clave."""
    uniones = {
        c for _, _, clausulas in _contrato_real("contabilidad.mayor")
        for c in clausulas if "JOIN " in c.split(" ON ", 1)[0]
    }
    assert uniones == {
        "LEFT JOIN raw.con asi ON asi.ide = a.asiide",
        "LEFT JOIN cierres ci ON ci.cuenta_id = f.cuenta_id AND ci.ejercicio = f.ejercicio - 1",
        "LEFT JOIN contabilidad.plan_cuentas pc ON pc.cuenta_id = s.cuenta_id",
        "LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = s.centro_coste_id",
        "LEFT JOIN raw.con ter ON ter.ide = s.tercero_id",
    }, "cada union por PK (asiento, cuenta, tercero), centro unico (F-073) o conjunto DISTINCT"
    assert "SELECT DISTINCT" in _cte(MAYOR, "cierres"), "el conjunto de cierres es DISTINCT"
    for indice in (
        "CREATE INDEX idx_con_mayor_empresa_cuenta_fecha ON contabilidad.mayor (empresa_id, codigo_cuenta, fecha);",
        "CREATE INDEX idx_con_mayor_cuenta_fecha ON contabilidad.mayor (cuenta_id, fecha);",
        "CREATE INDEX idx_con_mayor_asiento ON contabilidad.mayor (asiento_id);",
        "CREATE INDEX idx_con_mayor_obra ON contabilidad.mayor (obra_id);",
        "CREATE INDEX idx_con_mayor_tercero ON contabilidad.mayor (tercero_id);",
    ):
        assert indice in _sql(MAYOR), f"falta el indice: {indice}"


# ===========================================================================
# R25-R26 · contabilidad.saldos_cuenta_mes
# ===========================================================================


def test_f056_r25_desde_el_mayor_con_el_importe_por_clase() -> None:
    mensual = _cte(SALDOS, "mensual")
    assert mensual.strip().endswith(
        "FROM contabilidad.mayor m GROUP BY COALESCE(m.cuenta_id, 0), m.empresa_id, m.ejercicio, m.mes"
    )
    assert set(re.findall(r"(?:FROM|JOIN)\s+(\w+\.\w+)", _sql(SALDOS))) == {"contabilidad.mayor"}
    for expresion in (
        "COALESCE(m.cuenta_id, 0) AS cuenta_id",
        "COUNT(*) AS num_apuntes",
        "SUM(m.debe)::NUMERIC(18, 2) AS debe",
        "SUM(m.haber)::NUMERIC(18, 2) AS haber",
        "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento IN ('APERTURA', 'SALDO_INICIAL')), 0)"
        "::NUMERIC(18, 2) AS importe_apertura",
        "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'NORMAL'), 0)::NUMERIC(18, 2) "
        "AS importe_movimiento",
        "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'REGULARIZACION'), 0)"
        "::NUMERIC(18, 2) AS importe_regularizacion",
        "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'CIERRE'), 0)::NUMERIC(18, 2) "
        "AS importe_cierre",
        "SUM(m.importe_saldo)::NUMERIC(18, 2) AS importe_saldo",
    ):
        assert expresion in mensual, f"falta «{expresion}» (R25)"
    texto = _sql(SALDOS)
    assert (
        "ALTER TABLE contabilidad.saldos_cuenta_mes ADD PRIMARY KEY (cuenta_id, empresa_id, ejercicio, mes);"
    ) in texto, "la empresa va en la clave: los apuntes sin cuenta caen en varias el mismo mes"
    assert (
        "CREATE INDEX idx_con_saldos_empresa_ejercicio ON contabilidad.saldos_cuenta_mes "
        "(empresa_id, ejercicio, mes);"
    ) in texto


def test_f056_r26_saldo_acumulado_a_fin_de_mes() -> None:
    final = _final(SALDOS, "saldos_cuenta_mes")
    assert (
        "SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id, s.empresa_id ORDER BY s.ejercicio, "
        "s.mes )::NUMERIC(18, 2) AS saldo_acumulado"
    ) in final
    assert "s.importe_saldo," in final
    assert "FROM mensual s" in final and " WHERE " not in final, "ningun mes se pierde (R26)"


@pytest.mark.parametrize("nombre", FICHEROS)
def test_f056_r2_ficheros_con_cabecera_y_ruta(nombre: str) -> None:
    primera = _crudo(nombre).splitlines()[0]
    assert primera == f"-- etl_sigrid/infrastructure/postgres/sql/contabilidad/{nombre}"


@pytest.mark.parametrize(("nombre", "tabla"), [(PLAN, "plan_cuentas"), (MAYOR, "mayor"),
                                                 (SALDOS, "saldos_cuenta_mes")])
def test_f056_r13_tablas_idempotentes(nombre: str, tabla: str) -> None:
    texto = _sql(nombre)
    assert f"DROP TABLE IF EXISTS contabilidad.{tabla} CASCADE;" in texto
    assert texto.index(f"DROP TABLE IF EXISTS contabilidad.{tabla}") < texto.index(
        f"CREATE TABLE contabilidad.{tabla} AS"
    )
    assert f"COMMENT ON TABLE contabilidad.{tabla} IS" in texto


# ===========================================================================
# EL CONTRATO DEL SQL, EXPRESION A EXPRESION
# ===========================================================================
#
# Lo que exigio el reviewer en F-095: fijar la FORMULA y no solo el alias. Para
# cada SELECT de los tres CREATE (CTE incluidos, en orden de aparicion; una
# rama de UNION ALL es su propio SELECT): si lleva DISTINCT, cada expresion
# proyectada tal cual y cada clausula de su FROM (JOIN con su ON, WHERE, GROUP
# BY, HAVING). Cambiar una formula obliga a cambiar esta tabla delante del
# reviewer. Revisada contra la spec linea a linea: R6-R12 (plan), R13-R24
# (mayor) y R25-R26 (saldos).

_CLAUSULAS = ("WHERE ", "GROUP BY ", "HAVING ", "LEFT JOIN ", "FULL JOIN ",
              "CROSS JOIN ", "JOIN ", "ORDER BY ")


def _profundidades(texto: str) -> list[int]:
    nivel, prof, cadena = 0, [], False
    for c in texto:
        if c == "'":
            cadena = not cadena
        if not cadena and c == "(":
            prof.append(nivel)
            nivel += 1
        elif not cadena and c == ")":
            nivel -= 1
            prof.append(nivel)
        else:
            prof.append(nivel if not cadena else -1)
    return prof


def _trocear(texto: str, ini: int, fin: int, prof: list[int], nivel: int) -> list[str]:
    trozos, a = [], ini
    for i in range(ini, fin):
        if prof[i] == nivel and texto[i] == ",":
            trozos.append(texto[a:i])
            a = i + 1
    trozos.append(texto[a:fin])
    return [t.strip() for t in trozos if t.strip()]


def _consultas_de(texto: str, ini: int, fin: int) -> list[tuple[bool, list[str], list[str]]]:
    """(DISTINCT, expresiones, clausulas) de cada SELECT del tramo, en orden.

    Una consulta acaba en el `)` que baja de su nivel o en un `UNION ALL` de su
    mismo nivel (la rama siguiente es otro SELECT).
    """
    prof = _profundidades(texto)
    res = []
    for m in re.finditer(r"(?<![\w.])SELECT ", texto[ini:fin]):
        s = ini + m.start()
        nivel = prof[s]
        q_fin = s
        while q_fin < fin and not (texto[q_fin] == ")" and prof[q_fin] < nivel) and not (
            prof[q_fin] == nivel and texto.startswith(" UNION ALL ", q_fin)
        ):
            q_fin += 1
        desde = next((k for k in range(s + 7, q_fin)
                      if prof[k] == nivel and texto.startswith(" FROM ", k)), None)
        lista = s + 7
        distinct = texto.startswith("DISTINCT ", lista)
        if distinct:
            lista += 9
        items = _trocear(texto, lista, desde if desde is not None else q_fin, prof, nivel)
        clausulas: list[str] = []
        if desde is not None:
            marcas = []
            for k in range(desde + 6, q_fin):
                if prof[k] != nivel or texto[k - 1] != " ":
                    continue
                for kw in _CLAUSULAS:
                    if texto.startswith(kw, k) and not (
                        kw == "JOIN " and texto[k - 5:k] in ("LEFT ", "FULL ", "ROSS ")
                    ):
                        marcas.append(k)
                        break
            for i, k in enumerate(marcas):
                hasta = marcas[i + 1] if i + 1 < len(marcas) else q_fin
                clausulas.append(texto[k:hasta].strip())
        res.append((distinct, items, clausulas))
    return res


def _contrato_real(objeto: str) -> list[tuple[bool, list[str], list[str]]]:
    for nombre in (PLAN, MAYOR, SALDOS):
        texto = _sql(nombre)
        m = re.search(rf"CREATE TABLE {re.escape(objeto)} AS ", texto)
        if m:
            return _consultas_de(texto, m.end(), texto.index(";", m.end()))
    raise AssertionError(f"{objeto} no se crea en ningun fichero de F-056")


def _columnas_de(objeto: str) -> list[str]:
    """Los nombres de columna del SELECT final, sacados del contrato real."""
    items = _contrato_real(objeto)[-1][1]
    return [re.split(r" AS |\.", i)[-1].strip() for i in items]


CONTRATO_SQL: dict[str, list[tuple[bool, list[str], list[str]]]] = {
    'contabilidad.plan_cuentas': [
        (
            False,
            [
                'g.ide',
                'g.emp',
                'g.cod',
            ],
            [
                'WHERE g.tip = 16',
            ],
        ),
        (
            False,
            [
                'e.numemp AS empresa_id',
                'MIN(e.res) AS empresa_nombre',
            ],
            [
                'GROUP BY e.numemp',
            ],
        ),
        (
            False,
            [
                'c.ide AS cuenta_id',
                'c.emp AS empresa_id',
                'c.cod AS codigo_cuenta',
                'c.res AS nombre_cuenta',
                'c.fecbaj AS fecbaj',
                'LENGTH(c.cod) AS nivel',
                'NULL::INT AS cuenta_padre_declarada_id',
            ],
            [
                'WHERE c.tip = 16',
            ],
        ),
        (
            False,
            [
                'c.ide',
                'c.emp',
                'c.cod',
                'c.res',
                'c.fecbaj',
                '5',
                'NULLIF(cu.padide, 0)',
            ],
            [
                'JOIN raw.con c ON c.ide = cu.ide',
            ],
        ),
        (
            False,
            [
                'n.cuenta_id',
                'n.empresa_id',
                'em.empresa_nombre',
                'n.codigo_cuenta',
                "n.empresa_id::TEXT || '-' || n.codigo_cuenta AS clave_cuenta",
                'n.nombre_cuenta',
                'n.nivel',
                "CASE n.nivel WHEN 1 THEN 'GRUPO' WHEN 2 THEN 'SUBGRUPO' WHEN 3 THEN 'CUENTA' WHEN 4 THEN 'SUBCUENTA' WHEN 5 THEN 'CUENTA_AUXILIAR' END AS nombre_nivel",
                'n.nivel = 5 AS es_imputable',
                'LEFT(n.codigo_cuenta, 1) AS grupo_pgc',
                'pad.ide AS cuenta_padre_id',
                'n.cuenta_padre_declarada_id',
                '(n.cuenta_padre_declarada_id IS NOT NULL AND n.cuenta_padre_declarada_id IS DISTINCT FROM pad.ide) AS padre_declarado_difiere',
                'g1.ide AS grupo_id',
                'g2.ide AS subgrupo_id',
                'g3.ide AS cuenta_3_id',
                'g4.ide AS subcuenta_id',
                "CONCAT_WS(' > ', g1.cod, g2.cod, g3.cod, g4.cod, CASE WHEN n.nivel = 5 THEN n.codigo_cuenta END) AS ruta_codigos",
                'contabilidad.fn_fecha(n.fecbaj) AS fecha_baja',
                'COALESCE(n.fecbaj, 0) = 0 AS es_activa',
            ],
            [
                'LEFT JOIN empresas em ON em.empresa_id = n.empresa_id',
                'LEFT JOIN grupos pad ON pad.emp = n.empresa_id AND pad.cod = CASE WHEN n.nivel = 5 THEN LEFT(n.codigo_cuenta, 4) WHEN n.nivel > 1 THEN LEFT(n.codigo_cuenta, n.nivel - 1) END',
                'LEFT JOIN grupos g1 ON g1.emp = n.empresa_id AND g1.cod = LEFT(n.codigo_cuenta, 1)',
                'LEFT JOIN grupos g2 ON g2.emp = n.empresa_id AND n.nivel >= 2 AND g2.cod = LEFT(n.codigo_cuenta, 2)',
                'LEFT JOIN grupos g3 ON g3.emp = n.empresa_id AND n.nivel >= 3 AND g3.cod = LEFT(n.codigo_cuenta, 3)',
                'LEFT JOIN grupos g4 ON g4.emp = n.empresa_id AND n.nivel >= 4 AND g4.cod = LEFT(n.codigo_cuenta, 4)',
            ],
        ),
    ],
    'contabilidad.mayor': [
        (
            False,
            [
                'a.ide AS apunte_id',
                'a.asiide AS asiento_id',
                'asi.cod AS codigo_asiento',
                'a.pos AS posicion',
                'contabilidad.fn_fecha(a.fec) AS fecha',
                'contabilidad.fn_fecha(asi.fec) AS fecha_asiento',
                'asi.emp AS empresa_id',
                'NULLIF(a.cueide, 0) AS cuenta_id',
                'a.res AS concepto',
                'a.doc AS documento',
                'a.pun AS punteo',
                'a.cla AS clase_origen',
                'COALESCE(a.deb, 0)::NUMERIC(18, 2) AS debe',
                'COALESCE(a.hab, 0)::NUMERIC(18, 2) AS haber',
                '(COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2) AS importe',
                "CASE WHEN a.cla = 3 OR a.res ILIKE 'asiento de cierre%' THEN 'CIERRE' WHEN a.cla = -1 OR a.res ILIKE 'asiento de apertura%' THEN 'APERTURA' WHEN a.cla = 1 OR a.res ILIKE 'asiento de regulariz%' THEN 'REGULARIZACION' ELSE 'NORMAL' END AS clase_bruta",
                'NULLIF(a.cenide, 0) AS centro_coste_id',
                'NULLIF(a.empide, 0) AS tercero_id',
            ],
            [
                'LEFT JOIN raw.con asi ON asi.ide = a.asiide',
            ],
        ),
        (
            False,
            [
                'ap.*',
                'EXTRACT(YEAR FROM ap.fecha)::INT AS ejercicio',
                'EXTRACT(MONTH FROM ap.fecha)::INT AS mes',
            ],
            [],
        ),
        (
            True,
            [
                'f.cuenta_id',
                'f.ejercicio',
            ],
            [
                "WHERE f.clase_bruta = 'CIERRE'",
            ],
        ),
        (
            False,
            [
                'f.*',
                "CASE WHEN f.clase_bruta = 'APERTURA' AND ci.cuenta_id IS NULL THEN 'SALDO_INICIAL' ELSE f.clase_bruta END AS clase_asiento",
            ],
            [
                'LEFT JOIN cierres ci ON ci.cuenta_id = f.cuenta_id AND ci.ejercicio = f.ejercicio - 1',
            ],
        ),
        (
            False,
            [
                'c.*',
                "CASE WHEN c.clase_asiento IN ('CIERRE', 'APERTURA') THEN 0::NUMERIC(18, 2) ELSE c.importe END AS importe_saldo",
            ],
            [],
        ),
        (
            False,
            [
                's.apunte_id',
                's.asiento_id',
                's.codigo_asiento',
                's.posicion',
                's.fecha',
                's.fecha_asiento',
                '(s.fecha IS DISTINCT FROM s.fecha_asiento) AS fecha_difiere',
                's.ejercicio',
                's.mes',
                's.empresa_id',
                's.cuenta_id',
                'pc.codigo_cuenta',
                'pc.nombre_cuenta',
                'pc.clave_cuenta',
                's.concepto',
                's.documento',
                's.punteo',
                's.clase_origen',
                's.clase_asiento',
                's.debe',
                's.haber',
                's.importe',
                's.importe_saldo',
                'SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id ORDER BY s.fecha, s.codigo_asiento, s.posicion, s.apunte_id )::NUMERIC(18, 2) AS saldo_acumulado',
                's.centro_coste_id',
                'cc.obra_id',
                'cc.codigo_obra',
                "cc.empresa::TEXT || '-' || cc.codigo_obra AS clave_obra",
                's.tercero_id',
                'ter.res AS tercero_nombre',
            ],
            [
                'LEFT JOIN contabilidad.plan_cuentas pc ON pc.cuenta_id = s.cuenta_id',
                'LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = s.centro_coste_id',
                'LEFT JOIN raw.con ter ON ter.ide = s.tercero_id',
            ],
        ),
    ],
    'contabilidad.saldos_cuenta_mes': [
        (
            False,
            [
                'COALESCE(m.cuenta_id, 0) AS cuenta_id',
                'm.empresa_id',
                'm.ejercicio',
                'm.mes',
                'COUNT(*) AS num_apuntes',
                'SUM(m.debe)::NUMERIC(18, 2) AS debe',
                'SUM(m.haber)::NUMERIC(18, 2) AS haber',
                "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento IN ('APERTURA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS importe_apertura",
                "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'NORMAL'), 0)::NUMERIC(18, 2) AS importe_movimiento",
                "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'REGULARIZACION'), 0)::NUMERIC(18, 2) AS importe_regularizacion",
                "COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'CIERRE'), 0)::NUMERIC(18, 2) AS importe_cierre",
                'SUM(m.importe_saldo)::NUMERIC(18, 2) AS importe_saldo',
            ],
            [
                'GROUP BY COALESCE(m.cuenta_id, 0), m.empresa_id, m.ejercicio, m.mes',
            ],
        ),
        (
            False,
            [
                's.cuenta_id',
                's.empresa_id',
                's.ejercicio',
                's.mes',
                's.num_apuntes',
                's.debe',
                's.haber',
                's.importe_apertura',
                's.importe_movimiento',
                's.importe_regularizacion',
                's.importe_cierre',
                's.importe_saldo',
                'SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id, s.empresa_id ORDER BY s.ejercicio, s.mes )::NUMERIC(18, 2) AS saldo_acumulado',
            ],
            [],
        ),
    ],
}


@pytest.mark.parametrize("objeto", sorted(f"contabilidad.{t}" for t in TABLAS))
def test_f056_contrato_expresion_a_expresion(objeto: str) -> None:
    real = _contrato_real(objeto)
    esperado = CONTRATO_SQL[objeto]
    assert len(real) == len(esperado), f"{objeto}: cambio el numero de SELECT (CTE)"
    for n, ((d_r, i_r, c_r), (d_e, i_e, c_e)) in enumerate(zip(real, esperado, strict=True), 1):
        assert d_r == d_e, f"{objeto}, SELECT {n}: cambio el DISTINCT"
        assert i_r == i_e, f"{objeto}, SELECT {n}: cambio una expresion proyectada"
        assert c_r == c_e, f"{objeto}, SELECT {n}: cambio un JOIN, WHERE, GROUP BY o HAVING"


def test_f056_contrato_control_el_parser_ve_lo_que_debe() -> None:
    """Si el parser dejara de ver expresiones, el contrato pasaria en vacio."""
    total = sum(len(i) for q in CONTRATO_SQL.values() for _, i, _ in q)
    clausulas = sum(len(c) for q in CONTRATO_SQL.values() for _, _, c in q)
    assert total >= 100 and clausulas >= 15
    plan = _contrato_real("contabilidad.plan_cuentas")
    assert len(plan) == 5, "grupos, empresas, las dos ramas de nodos y el final"
    assert plan[3][2] == ["JOIN raw.con c ON c.ide = cu.ide"], "la rama de cua es su propio SELECT"


@pytest.mark.parametrize("tabla", TABLAS)
def test_f056_contrato_columnas_publicadas(tabla: str) -> None:
    assert _columnas_de(f"contabilidad.{tabla}") == COLUMNAS[tabla]


# ===========================================================================
# R27-R30 · el diccionario
# ===========================================================================


@pytest.mark.parametrize("tabla", TABLAS)
def test_f056_r27_fichas_con_grano_claves_y_columnas(tabla: str) -> None:
    ficha = _ficha(tabla)
    assert ficha["tipo"] == "tabla"
    assert ficha["grano"] and ficha["descripcion"]
    assert ficha["paso_etl"] == "build_contabilidad"
    assert ficha["refresco"] == "nocturno"
    assert list(ficha["columnas"]) == COLUMNAS[tabla], (
        f"las columnas de la ficha de {tabla} no son las del SQL (R27)"
    )
    for nombre, columna in ficha["columnas"].items():
        assert columna.get("significado"), f"{tabla}.{nombre} sin significado"


def test_f056_r27_claves_de_negocio_y_alternativas() -> None:
    assert _ficha("plan_cuentas")["clave_negocio"] == ["cuenta_id"]
    assert _ficha("plan_cuentas")["claves_alternativas"] == [
        ["empresa_id", "codigo_cuenta"], ["clave_cuenta"]
    ]
    assert _ficha("mayor")["clave_negocio"] == ["apunte_id"]
    assert _ficha("saldos_cuenta_mes")["clave_negocio"] == [
        "cuenta_id", "empresa_id", "ejercicio", "mes"
    ]
    recomendados = {t for t in TABLAS if _ficha(t)["consumo_recomendado"]}
    assert recomendados == set(TABLAS), "D3: los tres objetos se publican para consumo"


def test_f056_r27_relaciones() -> None:
    def destinos(tabla: str) -> set[tuple[str, str]]:
        return {(r["de"], r["a"]) for r in _ficha(tabla).get("relaciones", [])}

    plan = "contabilidad.plan_cuentas.cuenta_id"
    assert {("cuenta_id", plan), ("obra_id", "maestro.obras.obra_id"),
            ("centro_coste_id", "maestro.centros_coste.centro_coste_id")} <= destinos("mayor")
    assert ("cuenta_id", plan) in destinos("saldos_cuenta_mes")
    for col in ("cuenta_padre_id", "grupo_id", "subgrupo_id", "cuenta_3_id", "subcuenta_id"):
        assert (col, plan) in destinos("plan_cuentas"), f"{col} -> plan_cuentas (R27)"


def test_f056_r27_la_funcion_tiene_ficha() -> None:
    ficha = _ficha("fn_fecha")
    assert ficha["tipo"] == "funcion" and ficha["paso_etl"] == "build_contabilidad"
    from tests.test_f079_stg_consultable import GRUPO_B_FUNCIONES

    assert "contabilidad.fn_fecha" in GRUPO_B_FUNCIONES


def test_f056_r28_las_advertencias_con_cifra() -> None:
    plan = _texto_ficha(_ficha("plan_cuentas"))
    mayor = _texto_ficha(_ficha("mayor"))
    saldos = _texto_ficha(_ficha("saldos_cuenta_mes"))
    cabecera = (DIR_DICCIONARIO / "contabilidad.yaml").read_text(encoding="utf-8")
    # el plan FINANCIERO no es el analitico
    assert "maestro.cuentas_analiticas" in plan and "44.778" in plan and "34.196" in plan
    # contabilidad y analitica persiguen cosas distintas (F-063)
    assert "F-063" in mayor
    # una operacion deja varios apuntes: factura, remesa, totales
    assert "remesa" in mayor and "totales" in mayor
    # sumar CIERRE o APERTURA duplica, con cifra
    for dato in ("CIERRE", "APERTURA", "7.742.538,38", "1.189.275,13", "1.433", "297"):
        assert dato in mayor, f"la ficha del mayor no dice «{dato}»"
    assert "CIERRE" in saldos and "APERTURA" in saldos
    # la cobertura de obra por grupo del PGC
    for dato in ("90,3", "61,4", "46,8"):
        assert dato in mayor, f"la ficha del mayor no da la cobertura de obra «{dato}»"
    assert "R-SALDO-CONTABLE" in cabecera


def test_f056_r29_global_esquema_regla_y_version() -> None:
    glob = _yaml("00_global.yaml")
    assert glob["version"] == 36
    esquema = glob["esquemas"]["contabilidad"]
    assert esquema["pasos_etl"] == ["build_contabilidad"]
    assert esquema["refresco"] == "nocturno" and esquema["consumo_recomendado"] is True
    reglas = {r["codigo"]: r for r in glob["reglas"]}
    regla = reglas["R-SALDO-CONTABLE"]
    assert regla["severidad"] == "bloqueante"
    assert set(regla["ambito"]) == {f"contabilidad.{t}" for t in TABLAS}
    texto = regla["regla"] + regla["motivo"]
    for termino in ("importe_saldo", "saldo_acumulado", "CIERRE", "APERTURA", "REGULARIZACION"):
        assert termino in texto, f"R-SALDO-CONTABLE no dice «{termino}»"
    assert glob["pendientes"] == []


def test_f056_r30_fichas_de_raw_corregidas() -> None:
    raw = _yaml("raw.yaml")["objetos"]
    for tabla in ("asi", "apu"):
        texto = _texto_ficha(raw[tabla])
        assert "hacen falta dos saltos" not in texto, f"raw.{tabla} sigue diciendo que hacen falta dos saltos"
        assert "297" in texto and "contabilidad.mayor" in texto
    cua = _texto_ficha(raw["cua"])
    assert "nivel 5 frente a" not in cua
    assert "tip = 17" in cua and "tip = 16" in cua and "contabilidad.plan_cuentas" in cua
    apa = _texto_ficha(raw["apa"])
    assert "caa" in apa and "F-061" in apa and "contabilidad.mayor" in apa


# ===========================================================================
# R31-R32 · la propagacion y la documentacion
# ===========================================================================


def test_f056_r31_esquemas_de_consumo_y_del_datamart() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    assert "contabilidad" in ESQUEMAS_DEL_DATAMART
    assert "contabilidad" in DEFAULT_CONSUMPTION_SCHEMAS.split(",")
    entorno = (RAIZ / ".env.example").read_text(encoding="utf-8")
    linea = next(f for f in entorno.splitlines() if f.startswith("PG_CONSUMPTION_SCHEMAS="))
    assert "contabilidad" in linea.split("=", 1)[1].split(",")


def test_f056_r31_apply_grants_sin_lista_a_mano() -> None:
    from etl_sigrid.application.steps import apply_grants_step

    fuente = Path(apply_grants_step.__file__).read_text(encoding="utf-8")
    ejecutable = "\n".join(f for f in fuente.splitlines() if not f.lstrip().startswith("#"))
    assert "consumption_schema_list" in ejecutable
    assert '"contabilidad"' not in ejecutable


def test_f056_r31_check_declarados_ve_el_esquema() -> None:
    from etl_sigrid.domain.inventario import objetos_de_sql

    textos = {
        f"contabilidad/{f.name}": f.read_text(encoding="utf-8")
        for f in sorted(DIR_CON.glob("*.sql"))
    }
    declarados = {(o.esquema, o.objeto) for o in objetos_de_sql(textos)}
    assert declarados >= {("contabilidad", t) for t in TABLAS} | {("contabilidad", "fn_fecha")}
    pendientes = yaml.safe_load(RUTA_PENDIENTES.read_text(encoding="utf-8"))
    assert pendientes["pendientes"] == []


def test_f056_r32_documentacion() -> None:
    arquitectura = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for termino in ("contabilidad.plan_cuentas", "contabilidad.mayor",
                    "contabilidad.saldos_cuenta_mes", "build_contabilidad", "prefijo",
                    "SALDO_INICIAL"):
        assert termino in arquitectura, f"ARCHITECTURE.md no dice «{termino}»"
    claude = DOC_CLAUDE.read_text(encoding="utf-8")
    assert "`contabilidad/`" in claude, "el mapa de sql/ de CLAUDE.md gana contabilidad/"
    import main

    documentacion = main.run_all.__doc__ or ""
    assert "seis build" in documentacion and "contabilidad" in documentacion
    assert "seis build" in (main.build_pipeline_steps.__doc__ or "") or "sexto" in (
        main.build_pipeline_steps.__doc__ or ""
    )
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("F-056", "build_contabilidad", *(f"contabilidad.{t}" for t in TABLAS)):
        assert termino in texto, f"azure-apps no dice «{termino}» (R32)"


def test_f056_r36_un_test_por_requisito() -> None:
    nombres = [n for n in globals() if n.startswith("test_f056_r")]
    for n in range(1, 33):
        assert any(x.startswith(f"test_f056_r{n}_") for x in nombres), f"R{n} sin test"
