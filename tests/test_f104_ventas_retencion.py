# tests/test_f104_ventas_retencion.py
"""
F-104 (D10 = b, 2026-11-16) · La conciliación de la retención de cliente por FACTURA, en `ventas`.

`retenciones.v_cuadre_cliente` dice CUÁNTO descuadra cada cuenta de retención
de cliente; `ventas.retencion_factura` dice POR QUÉ, factura a factura: la
retención que la factura manda a una cuenta de retención (D12 = a, los recargos
de `raw.dvfrec` con `cueide` en `retenciones.cuentas_cliente`) frente a los
efectos que la cobran. `ventas.retencion_cuenta` lo suma por cuenta y
`ventas.v_retencion_cliente` por cliente. Lo cobrado por un AGR se explica y
no se atribuye a la factura (D11).

Sobre el TEXTO del SQL y del diccionario, sin red ni base. Mapa requisito ->
test: `specs/F-104-retenciones-cliente/design_detalle.md` §3.
"""

from __future__ import annotations

import inspect
import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain import ventas as dom

RAIZ = Path(__file__).resolve().parents[1]
DIR_V = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "ventas"
DIR_DICC = RAIZ / "config" / "diccionario"
FICHERO = "06b_retencion_cliente.sql"

COLUMNAS_FACTURA = (
    "factura_id", "codigo_factura", "fecha_factura", "cliente_id", "nombre_cliente", "obra_id",
    "codigo_obra", "cuenta_id", "retencion", "retencion_garantia", "retencion_retesp", "efectos",
    "num_efectos", "efectos_viva", "efectos_liquidada", "efectos_agrupada", "diferencia", "motivo",
)
COLUMNAS_CUENTA = (
    "cuenta_id", "codigo_cuenta", "nombre_cuenta", "cliente_id", "criterio_seleccion",
    "saldo_contable", "viva_efectos", "diferencia", "categoria", "retencion_facturas",
    "retencion_sin_efecto", "num_facturas_sin_efecto", "viva_sin_factura",
    "diferencia_sin_explicar",
)
COLUMNAS_CLIENTE = (
    "cliente_id", "nombre_cliente", "num_facturas", "retencion", "efectos",
    "retencion_sin_efecto", "diferencia_facturas", "saldo_contable", "viva_efectos",
    "diferencia", "viva_sin_factura", "diferencia_sin_explicar",
)
MOTIVOS = ("SIN_EFECTO", "EFECTO_SIN_RETENCION", "CUADRA", "DIFIERE", "SIN_CUENTA_RETENCION")
CASE_MOTIVO = (
    "CASE WHEN x.num_efectos = 0 AND x.retencion <> 0 THEN 'SIN_EFECTO' "
    "WHEN x.num_efectos > 0 AND x.retencion = 0 THEN 'EFECTO_SIN_RETENCION' "
    "WHEN x.num_efectos > 0 AND abs(x.retencion - x.efectos) < 0.01 THEN 'CUADRA' "
    "WHEN x.num_efectos > 0 THEN 'DIFIERE' "
    "ELSE 'SIN_CUENTA_RETENCION' END"
)


@cache
def _texto() -> str:
    ruta = DIR_V / FICHERO
    assert ruta.exists(), f"no existe {ruta.relative_to(RAIZ)}"
    return ruta.read_text(encoding="utf-8")


def _sql() -> str:
    sin_comentarios = "\n".join(re.sub(r"--.*$", "", linea) for linea in _texto().splitlines())
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _create(objeto: str, clase: str = "TABLE") -> str:
    sql = _sql()
    cabecera = f"CREATE {clase} {objeto} AS"
    assert cabecera in sql, f"falta «{cabecera}»"
    inicio = sql.index(cabecera)
    return sql[inicio: sql.index(";", inicio)]


def _alias_final(create: str) -> list[str]:
    final = create[create.rindex("SELECT "):]
    final = final[: final.index(" FROM ")]
    return re.findall(r" AS (\w+)", final)


def _cte(create: str, nombre: str) -> str:
    inicio = create.index(f"{nombre} AS (")
    siguiente = re.search(r"\), \w+ AS \(", create[inicio:])
    return create[inicio: inicio + siguiente.start()] if siguiente else create[inicio:]


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _plano(valor: object) -> str:
    return re.sub(r"\s+", " ", str(valor))


# ===========================================================================
# R27-R30 · ventas.retencion_factura
# ===========================================================================


def test_f104_r27_retencion_factura_columnas_en_orden() -> None:
    assert _alias_final(_create("ventas.retencion_factura")) == list(COLUMNAS_FACTURA)
    assert "ALTER TABLE ventas.retencion_factura ADD PRIMARY KEY (factura_id);" in _sql()


def test_f104_r27_universo_de_retencion_factura() -> None:
    create = _create("ventas.retencion_factura")
    assert (
        "WHERE x.retencion <> 0 OR x.retencion_garantia <> 0 OR x.retencion_retesp <> 0 "
        "OR x.num_efectos > 0"
    ) in create
    assert "FROM ventas.facturas f" in create


def test_f104_r28_motivo_con_sus_cinco_valores_en_orden() -> None:
    create = _create("ventas.retencion_factura")
    assert f"({CASE_MOTIVO})::VARCHAR(24) AS motivo" in create
    posiciones = [CASE_MOTIVO.index(f"'{m}'") for m in MOTIVOS]
    assert posiciones == sorted(posiciones)


def test_f104_r29_los_efectos_salen_de_movimientos_por_documento_y_estado() -> None:
    efectos = _cte(_create("ventas.retencion_factura"), "efectos")
    assert "FROM retenciones.movimientos m" in efectos
    assert "m.sentido = 'CLIENTE'" in efectos
    assert "GROUP BY m.documento_id" in efectos
    for estado, columna in (("VIVA", "efectos_viva"), ("LIQUIDADA", "efectos_liquidada"),
                            ("BAJA", "efectos_agrupada")):
        assert f"COALESCE(SUM(m.importe) FILTER (WHERE m.estado = '{estado}'), 0) AS {columna}" in efectos


def test_f104_r29_r30_no_recalcula_estado_ni_clase() -> None:
    sql = _sql()
    for vetado in ("reccla", "fn_clase_recargo", "fecbaj", "fecrea", "raw.cob", "estado_sigrid",
                   "CLASES_GARANTIA"):
        assert vetado not in sql, vetado


def test_f104_r30_garantia_y_retesp_de_ventas_facturas_y_retencion_de_dvfrec() -> None:
    create = _create("ventas.retencion_factura")
    assert "f.retencion_garantia" in create and "f.retencion_retesp" in create
    retencion = _cte(create, "retencion")
    assert "FROM raw.dvfrec r" in retencion
    assert "r.cueide IN (SELECT cuenta_id FROM retenciones.cuentas_cliente)" in retencion
    assert "SUM(r.cuo::NUMERIC(18, 2)) AS retencion" in retencion
    assert "GROUP BY r.docide" in retencion


def test_f104_r30_la_cuenta_es_la_del_recargo_y_si_no_la_del_efecto() -> None:
    assert "COALESCE(rt.cuenta_id, ef.cuenta_id) AS cuenta_id" in _create("ventas.retencion_factura")


# ===========================================================================
# R31 · ventas.retencion_cuenta
# ===========================================================================


def test_f104_r31_retencion_cuenta_columnas_y_lectura() -> None:
    create = _create("ventas.retencion_cuenta")
    assert _alias_final(create) == list(COLUMNAS_CUENTA)
    assert "FROM retenciones.v_cuadre_cliente q" in create
    assert "FULL JOIN" in create
    assert "FROM ventas.retencion_factura rf" in create
    assert "JOIN retenciones.cuentas_cliente cc" in create
    assert "ALTER TABLE ventas.retencion_cuenta ADD PRIMARY KEY (cuenta_id);" in _sql()


def test_f104_r31_sin_factura_y_sin_explicar() -> None:
    create = _create("ventas.retencion_cuenta")
    sin_factura = _cte(create, "sin_factura")
    for cosa in ("m.sentido = 'CLIENTE'", "m.estado = 'VIVA'", "m.documento_id IS NULL"):
        assert cosa in sin_factura, cosa
    assert (
        "CASE WHEN x.categoria = 'CUADRA' THEN NULL "
        "ELSE x.diferencia - (x.retencion_sin_efecto - x.viva_sin_factura) END"
    ) in create
    assert "rf.motivo = 'SIN_EFECTO'" in _cte(create, "por_factura")


# ===========================================================================
# R32 · ventas.v_retencion_cliente
# ===========================================================================


def test_f104_r32_la_vista_de_cliente_lee_solo_las_dos_tablas() -> None:
    vista = _create("ventas.v_retencion_cliente", "VIEW")
    assert _alias_final(vista) == list(COLUMNAS_CLIENTE)
    leidos = set(re.findall(r"\b(?:FROM|JOIN)\s+(\w+\.\w+)", vista))
    assert leidos == {"ventas.retencion_factura", "ventas.retencion_cuenta"}, leidos
    assert "rf.motivo IN ('DIFIERE', 'EFECTO_SIN_RETENCION')" in vista


# ===========================================================================
# R33-R35 · guarda, tablas y nada personal
# ===========================================================================


def test_f104_r33_la_guarda_va_antes_de_ningun_drop() -> None:
    sql = _sql()
    guarda = sql[sql.index("DO $$"): sql.index("END $$;")]
    assert sql.index("DO $$") < sql.index("DROP ")
    assert "to_regclass('retenciones.v_cuadre_cliente')" in guarda
    assert "information_schema.columns" in guarda and "'origen_retencion'" in guarda
    m = re.search(r"RAISE EXCEPTION '([^']*)'", guarda)
    assert m and "retenciones.v_cuadre_cliente" in m.group(1) and "origen_retencion" in m.group(1)


def test_f104_r34_dos_tablas_y_una_vista() -> None:
    sql = _sql()
    assert re.findall(r"CREATE TABLE (\S+) AS", sql) == ["ventas.retencion_factura",
                                                         "ventas.retencion_cuenta"]
    assert re.findall(r"CREATE VIEW (\S+) AS", sql) == ["ventas.v_retencion_cliente"]
    for objeto in ("ventas.retencion_factura", "ventas.retencion_cuenta"):
        assert f"DROP TABLE IF EXISTS {objeto} CASCADE;" in sql
        assert f"COMMENT ON TABLE {objeto} IS" in sql
    assert "COMMENT ON VIEW ventas.v_retencion_cliente IS" in sql


def test_f104_r34_sub_paso_entre_restringida_y_guardas() -> None:
    from etl_sigrid.application.steps import build_ventas_step as paso

    nombres = [s.name for s in paso.SUB_PASOS]
    i = nombres.index("retencion_cliente")
    assert nombres[i - 1: i + 2] == ["restringida", "retencion_cliente", "guardas"]
    sub = paso.SUB_PASOS[i]
    assert (sub.sql_file, sub.target_schema, sub.target_table) == (FICHERO, "ventas",
                                                                   "retencion_factura")
    doc = paso.__doc__ or ""
    assert FICHERO in doc and "retenciones" in doc and "POSICION" in doc.upper().replace("Ó", "O")


def test_f104_r34_depends_on_de_ventas_sin_cambios() -> None:
    from etl_sigrid.application.steps.build_ventas_step import BuildVentasStep

    assert BuildVentasStep(None).depends_on == ["ingest_raw"]  # type: ignore[arg-type]
    assert "F-104" in inspect.getsource(BuildVentasStep.depends_on.fget)


def test_f104_r35_ninguna_columna_personal() -> None:
    columnas = COLUMNAS_FACTURA + COLUMNAS_CUENTA + COLUMNAS_CLIENTE
    for columna in columnas:
        assert not columna.startswith(dom.PREFIJOS_PROHIBIDOS_EN_VENTAS), columna
        assert "cif" not in columna, columna
    assert "cif" not in _sql().lower().replace("especific", "")


def test_f104_cabecera_con_ruta_y_lectura() -> None:
    texto = _texto()
    assert texto.splitlines()[0] == f"-- etl_sigrid/infrastructure/postgres/sql/ventas/{FICHERO}"
    for cosa in ("F-104", "F-040", "Lee de", "D11", "D12", "CASCADE"):
        assert cosa in texto, cosa


# ===========================================================================
# R36 · diccionario de ventas; R25 · las promesas de F-040 se cumplen
# ===========================================================================


def test_f104_r36_fichas_de_los_tres_objetos() -> None:
    fichas = _yaml("ventas.yaml")["objetos"]
    for nombre, tipo, columnas in (("retencion_factura", "tabla", COLUMNAS_FACTURA),
                                   ("retencion_cuenta", "tabla", COLUMNAS_CUENTA),
                                   ("v_retencion_cliente", "vista", COLUMNAS_CLIENTE)):
        ficha = fichas[nombre]
        assert ficha["tipo"] == tipo, nombre
        assert tuple(ficha["columnas"]) == columnas, nombre
        assert ficha["paso_etl"] == "build_ventas", nombre
        assert "F-104" in _plano(ficha), nombre
    assert fichas["retencion_factura"]["columnas"]["motivo"]["valores"] == list(MOTIVOS)
    regla = "la retencion de la factura no es la garantia de `ventas.facturas`"
    assert regla in _plano(fichas["retencion_factura"]).lower()


def test_f104_r25_las_promesas_a_f104_se_cumplen() -> None:
    crudo = (DIR_DICC / "ventas.yaml").read_text(encoding="utf-8")
    cabecera = crudo.split("\nversion:", 1)[0]
    fichas = _yaml("ventas.yaml")["objetos"]
    arquitectura = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    frontera = arquitectura[arquitectura.index("**Frontera con F-104**"):][:900]
    for nombre, texto in (("cabecera", cabecera), ("v_factura_cobro", _plano(fichas["v_factura_cobro"])),
                          ("cobertura_enlace", _plano(fichas["cobertura_enlace"])),
                          ("ARCHITECTURE.md", frontera)):
        plano = _plano(texto)
        assert "F-104" in plano, nombre
        assert "retencion_factura" in plano, nombre
        assert "hasta F-104" not in plano, nombre
        assert "lo explicara F-104" not in plano and "es de F-104" not in plano, nombre
