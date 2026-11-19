# tests/test_f104_retenciones_cliente.py
"""
F-104 · La retención de CLIENTE saneada: estado, cuentas, saldo contable y cuadre.

Hasta F-104 `retenciones.movimientos` derivaba el estado de CLIENTE solo de
`cob.fecrea` y publicaba 22,44 M€ «vivos» (2026-11-16). En `cob` el original
agrupado queda en `est 1` con `fecbaj` = fecha del AGR, y el AGR y sus DIV
llevan `retide = 0`: el dinero vivo estaba fuera y el muerto dentro. Con la
precedencia de F-094 y los efectos de las cuentas de retención de cliente, lo
vivo son 10,53 M€; la contabilidad da 16,00 M€ y manda (D4).

Como `test_f094_*` y `test_f095_*`, se fija sobre el TEXTO del SQL y del
diccionario: sin red ni base (`progress/impl_F-104.md` tiene la sandbox).
Mapa requisito -> test: `specs/F-104-retenciones-cliente/design_detalle.md` §3.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from functools import cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_RET = DIR_SQL / "retenciones"
DIR_DICC = RAIZ / "config" / "diccionario"

MOVIMIENTOS = "01_movimientos.sql"
SALDO_CLIENTE = "08_saldo_cliente.sql"

COLUMNAS_CUENTAS = (
    "cuenta_id", "cliente_id", "codigo_cuenta", "nombre_cuenta", "familia", "criterio_seleccion",
)
COLUMNAS_SALDO = (
    "cuenta_id", "cliente_id", "codigo_cuenta", "nombre_cuenta", "familia", "criterio_seleccion",
    "altas", "bajas", "saldo_inicial", "saldo", "saldo_anterior_2016", "num_apuntes",
    "primer_movimiento", "ultimo_movimiento",
)
COLUMNAS_CUADRE = (
    "cuenta_id", "codigo_cuenta", "nombre_cuenta", "cliente_id", "criterio_seleccion",
    "saldo_contable", "viva_efectos", "num_efectos_vivos", "diferencia", "categoria",
)
#: Las dos columnas que F-104 añade AL FINAL de las dos ramas (UNION ALL por posición).
COLUMNAS_NUEVAS_MOVIMIENTOS = ("origen_retencion", "cuenta_id")

CASE_ESTADO_CLIENTE = (
    "CASE WHEN COALESCE(efe.fecbaj, 0) <> 0 OR efe.est IN (14, 15) THEN 'BAJA' "
    "WHEN COALESCE(c.fecrea, 0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA' "
    "ELSE 'VIVA' END"
)


# ---------------------------------------------------------------------------
# Lectura del SQL
# ---------------------------------------------------------------------------


@cache
def _texto(nombre: str) -> str:
    ruta = DIR_RET / nombre
    assert ruta.exists(), f"no existe {ruta.relative_to(RAIZ)}"
    return ruta.read_text(encoding="utf-8")


def _compacto(texto: str) -> str:
    """Una línea, sin comentarios `--` y con los espacios colapsados."""
    sin_comentarios = "\n".join(linea.split("--", 1)[0] for linea in texto.splitlines())
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _sql(nombre: str) -> str:
    return _compacto(_texto(nombre))


def _mitades() -> tuple[str, str]:
    """(PROVEEDOR, CLIENTE) del `UNION ALL` de movimientos (la primera arrastra lo de antes)."""
    partes = _sql(MOVIMIENTOS).split(" UNION ALL ")
    assert len(partes) == 2, "01_movimientos.sql tiene que seguir siendo UN solo UNION ALL"
    return partes[0], partes[1]


def _select_proveedor() -> str:
    proveedor, _ = _mitades()
    inicio = proveedor.index("SELECT 'PROVEEDOR'::VARCHAR(10) AS sentido")
    return proveedor[inicio: proveedor.index(" FROM raw.pag p", inicio)]


def _select_cliente() -> str:
    _, cliente = _mitades()
    return cliente[: cliente.index(" FROM raw.cob c")]


def _alias(select: str) -> list[str]:
    return re.findall(r" AS (\w+)(?=,|$)", select)


def _case_estado(mitad: str) -> str:
    m = re.search(r"(CASE WHEN .*? END)::VARCHAR\(\d+\) AS estado\b", mitad)
    assert m, "no se encuentra el CASE ... AS estado"
    trozo = m.group(1)
    return trozo[trozo.rfind("CASE WHEN "):]


def _bloque(sql: str, cabecera: str, fin: str = ";") -> str:
    assert cabecera in sql, f"falta «{cabecera}»"
    inicio = sql.index(cabecera)
    return sql[inicio: sql.index(fin, inicio)]


def _alias_final(create: str) -> list[str]:
    """Los nombres del SELECT final de un CREATE ... AS (lo que va tras cada ` AS `)."""
    final = create[create.rindex("SELECT "):]
    final = final[: final.index(" FROM ")]
    return re.findall(r" AS (\w+)", final)


def _cuentas_cliente() -> str:
    return _bloque(_sql(MOVIMIENTOS), "CREATE TABLE retenciones.cuentas_cliente AS")


def _saldo_cliente() -> str:
    return _bloque(_sql(SALDO_CLIENTE), "CREATE TABLE retenciones.saldo_contable_cliente AS")


def _cuadre_cliente() -> str:
    return _bloque(_sql(SALDO_CLIENTE), "CREATE VIEW retenciones.v_cuadre_cliente AS")


# ---------------------------------------------------------------------------
# Lectura del diccionario
# ---------------------------------------------------------------------------


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _fichas() -> dict:
    return _yaml("retenciones.yaml")["objetos"]


def _plano(valor: object) -> str:
    return re.sub(r"\s+", " ", str(valor))


# ===========================================================================
# A · estado del efecto de cliente (R1-R3)
# ===========================================================================


def test_f104_r1_estado_de_cliente_con_la_precedencia_de_f094() -> None:
    """BAJA manda: el original agrupado (`est 1` + `fecbaj`) deja de contar como VIVA."""
    proveedor, cliente = _mitades()
    assert _case_estado(cliente) == CASE_ESTADO_CLIENTE
    # Es el MISMO CASE que el de proveedor, con `c.` en vez de `p.`
    assert _case_estado(proveedor).replace("p.fecrea", "c.fecrea") == CASE_ESTADO_CLIENTE
    assert re.search(r"LEFT JOIN raw\.con efe ON efe\.ide = c\.ide\b", cliente)


def test_f104_r2_vencida_solo_si_viva_en_cliente() -> None:
    m = re.search(r"CASE WHEN (.*?) THEN TRUE ELSE FALSE END AS vencida_sin_liquidar", _select_cliente())
    assert m
    condicion = m.group(1).rsplit("CASE WHEN ", 1)[-1]
    for trozo in ("COALESCE(c.fecrea, 0) = 0", "COALESCE(efe.fecbaj, 0) = 0",
                  "COALESCE(efe.est, 0) NOT IN (10, 14, 15)",
                  "retenciones.fn_sigrid_date(c.fecven) < CURRENT_DATE"):
        assert trozo in condicion, trozo


def test_f104_r3_la_cabecera_explica_el_agr_con_el_caso_medido() -> None:
    cabecera = _texto(MOVIMIENTOS).split("DROP TABLE", 1)[0]
    for cosa in ("est 1", "fecbaj", "AGR", "4308001150", "AGR20/0010", "57.973,72", "F-104"):
        assert cosa in cabecera, cosa
    assert "SIGUE: VIVA fecrea = 0" not in cabecera, "la cabecera vieja de CLIENTE sigue ahi"


# ===========================================================================
# B · el universo de cuentas y el dinero agrupado (R4-R8, R10, R23)
# ===========================================================================


def test_f104_r4_cuentas_cliente_es_la_union_de_cueretide_y_43x8() -> None:
    bloque = _cuentas_cliente()
    for cosa in ("FROM raw.cli cl", "cl.cueretide", "pc.tip = 17", "pc.cod ~ '^43[0-9]8'",
                 "FULL JOIN", "'CUERETIDE'", "'PREFIJO_43X8'", "LEFT(cue.cod, 4) AS familia"):
        assert cosa in bloque, cosa
    assert _alias_final(bloque) == list(COLUMNAS_CUENTAS)
    assert "ALTER TABLE retenciones.cuentas_cliente ADD PRIMARY KEY (cuenta_id);" in _sql(MOVIMIENTOS)


def test_f104_r4_cuentas_cliente_va_antes_que_movimientos_y_no_en_setup() -> None:
    sql = _sql(MOVIMIENTOS)
    assert sql.index("CREATE TABLE retenciones.cuentas_cliente AS") < sql.index(
        "CREATE TABLE retenciones.movimientos AS"
    )
    assert "cuentas_cliente" not in _texto("00_setup.sql"), "00_setup.sql lo protege F-040"
    assert "DROP TABLE IF EXISTS retenciones.cuentas_cliente CASCADE;" in sql
    assert "COMMENT ON TABLE retenciones.cuentas_cliente IS" in sql


def test_f104_r5_guarda_de_cuentas_vacia_antes_de_movimientos() -> None:
    """La PK es la guarda de «dos clientes, una cuenta»; la de vacía, un RAISE con el nombre."""
    sql = _sql(MOVIMIENTOS)
    pk = sql.index("ALTER TABLE retenciones.cuentas_cliente ADD PRIMARY KEY (cuenta_id);")
    guarda = _bloque(sql, "DO $$", "END $$;")
    assert pk < sql.index(guarda) < sql.index("DROP TABLE IF EXISTS retenciones.movimientos CASCADE;")
    assert "IF NOT EXISTS (SELECT 1 FROM retenciones.cuentas_cliente)" in guarda
    assert re.search(r"RAISE EXCEPTION '[^']*retenciones\.cuentas_cliente", guarda)


def test_f104_r6_el_universo_de_cliente_incluye_las_cuentas() -> None:
    proveedor, cliente = _mitades()
    assert (
        "WHERE COALESCE(c.retide, 0) <> 0 OR c.cueide IN "
        "(SELECT cuenta_id FROM retenciones.cuentas_cliente)"
    ) in cliente
    assert "NULLIF(c.retide, 0) AS tipo_id" in cliente
    assert "WHERE COALESCE(p.retide, 0) <> 0" in proveedor
    assert "cuentas_cliente" not in proveedor[proveedor.index("SELECT 'PROVEEDOR'"):]


def test_f104_r7_r8_las_dos_columnas_nuevas_al_final_de_las_dos_ramas() -> None:
    proveedor, cliente = _alias(_select_proveedor()), _alias(_select_cliente())
    assert proveedor == cliente, "UNION ALL por posición: mismo orden en las dos ramas"
    assert tuple(proveedor[-2:]) == COLUMNAS_NUEVAS_MOVIMIENTOS
    assert "'EFECTO_RETENCION'::VARCHAR(16) AS origen_retencion" in _select_proveedor()
    assert (
        "CASE WHEN COALESCE(c.retide, 0) <> 0 THEN 'EFECTO_RETENCION' "
        "ELSE 'CUENTA_RETENCION' END::VARCHAR(16) AS origen_retencion"
    ) in _select_cliente()
    assert "NULLIF(p.cueide, 0) AS cuenta_id" in _select_proveedor()
    assert "NULLIF(c.cueide, 0) AS cuenta_id" in _select_cliente()


def test_f104_r10_pk_e_indice_por_cuenta() -> None:
    sql = _sql(MOVIMIENTOS)
    assert "ALTER TABLE retenciones.movimientos ADD PRIMARY KEY (sentido, movimiento_id);" in sql
    assert "CREATE INDEX idx_ret_mov_cuenta ON retenciones.movimientos (sentido, cuenta_id);" in sql


def test_f104_r23_entidad_cif_de_cliente_sigue_null() -> None:
    _, cliente = _mitades()
    assert "NULL::VARCHAR(24) AS entidad_cif" in cliente
    assert "cli.cif" not in cliente and "raw.cli" not in cliente
    ficha = _fichas()["movimientos"]["columnas"]["entidad_cif"]
    assert "ventas.clientes" in _plano(ficha)


def test_f104_el_comment_de_movimientos_dice_el_criterio_nuevo() -> None:
    comentario = _bloque(_sql(MOVIMIENTOS), "COMMENT ON TABLE retenciones.movimientos IS", "';")
    assert "F-104" in comentario and "origen_retencion" in comentario
    assert "en CLIENTE, VIVA = '" not in comentario


# ===========================================================================
# C · saldo contable y cuadre por cuenta (R11-R13)
# ===========================================================================


def test_f104_r11_saldo_contable_cliente_de_raw_apu_con_deb_menos_hab() -> None:
    bloque = _saldo_cliente()
    assert "FROM raw.apu a" in bloque
    assert "JOIN retenciones.cuentas_cliente" in bloque
    assert "(COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2) AS importe" in bloque
    assert _alias_final(bloque) == list(COLUMNAS_SALDO)
    for vetado in ("contabilidad.", "apuntes_contables", "hab, 0) - COALESCE(a.deb"):
        assert vetado not in bloque, vetado
    assert "ALTER TABLE retenciones.saldo_contable_cliente ADD PRIMARY KEY (cuenta_id);" in _sql(
        SALDO_CLIENTE
    )


def test_f104_r11_la_clase_es_la_de_03_en_su_orden() -> None:
    bloque = _saldo_cliente()
    clases = ["'CIERRE'", "'SALDO_INICIAL'", "'APERTURA'", "'ALTA'", "'BAJA'"]
    case = bloque[bloque.index("CASE WHEN ap.concepto LIKE 'Asiento de cierre%'"):]
    posiciones = [case.index(c) for c in clases]
    assert posiciones == sorted(posiciones), "el orden de la clase es el de 03_apuntes_contables.sql"
    # El mismo CASE que proveedor: se REPLICA (apuntes_contables es de proveedor)
    case_03 = re.search(r"CASE WHEN ap\.concepto LIKE 'Asiento de cierre%'.*? END AS clase",
                        _sql("03_apuntes_contables.sql")).group(0)
    case_08 = re.search(r"CASE WHEN ap\.concepto LIKE 'Asiento de cierre%'.*? END AS clase",
                        bloque).group(0)
    assert case_08 == case_03
    assert "COALESCE(SUM(k.importe) FILTER (WHERE k.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')), 0)" \
        "::NUMERIC(18, 2) AS saldo" in bloque


def test_f104_r12_cuadre_por_cuenta_con_la_categoria_de_proveedor() -> None:
    vista = _cuadre_cliente()
    assert _alias_final(vista) == list(COLUMNAS_CUADRE)
    case_prov = re.search(r"CASE WHEN ABS\(x\.saldo_contable - x\.viva_efectos\) < 1 .*? END AS categoria",
                          _sql("06_views_contables.sql")).group(0)
    assert case_prov in vista, "la categoría y su orden son los de v_cuadre_proveedor"
    assert "WHERE ABS(x.saldo_contable) >= 1 OR ABS(x.viva_efectos) >= 1" in vista
    assert "FULL JOIN" in vista
    assert "COMMENT ON VIEW retenciones.v_cuadre_cliente IS" in _sql(SALDO_CLIENTE)
    assert "ventas.retencion_cuenta" in _bloque(_sql(SALDO_CLIENTE),
                                                "COMMENT ON VIEW retenciones.v_cuadre_cliente IS", "';")


def test_f104_r13_el_cuadre_lee_el_estado_sin_recalcularlo() -> None:
    vista = _cuadre_cliente()
    assert "m.sentido = 'CLIENTE' AND m.estado = 'VIVA'" in vista
    for vetado in ("fecbaj", "fecrea", "estado_sigrid", ".est ", "raw.cob"):
        assert vetado not in vista, vetado


# ===========================================================================
# El sub-paso (T4)
# ===========================================================================


def test_f104_paso_saldo_cliente_es_el_ultimo_sub_paso() -> None:
    from etl_sigrid.application.steps import build_retenciones_step as paso

    ultimo = paso.SUB_PASOS[-1]
    assert (ultimo.name, ultimo.sql_file, ultimo.target_schema, ultimo.target_table) == (
        "saldo_cliente", SALDO_CLIENTE, "retenciones", "saldo_contable_cliente"
    )
    assert [s.name for s in paso.SUB_PASOS][-2] == "cuadre_factura"
    assert SALDO_CLIENTE in (paso.__doc__ or "")
    assert (DIR_RET / SALDO_CLIENTE).is_file()


def test_f104_paso_docstring_de_build_retenciones_en_main() -> None:
    import main

    assert SALDO_CLIENTE in (main.build_retenciones.callback.__doc__ or "")


def test_f104_cabecera_de_08_con_ruta_y_lectura() -> None:
    texto = _texto(SALDO_CLIENTE)
    assert texto.splitlines()[0] == f"-- etl_sigrid/infrastructure/postgres/sql/retenciones/{SALDO_CLIENTE}"
    assert "F-104" in texto and "Lee de" in texto
    assert "MANDA LA CONTABILIDAD" in texto


# ===========================================================================
# E · lo que no cambia (R14, R15, R24)
# ===========================================================================


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                          encoding="utf-8", check=False)


def _base_comun() -> str:
    if shutil.which("git") is None:
        pytest.skip("R14: sin git en el entorno, no se puede medir el diff")
    base = _git("merge-base", "main", "HEAD")
    if base.returncode != 0 or not base.stdout.strip():
        pytest.skip(f"R14: sin rama `main` con la que comparar ({base.stderr.strip()})")
    return base.stdout.strip()


def test_f104_r24_tocados_despues_admite_los_dos_de_f104_y_nada_mas() -> None:
    from tests.test_f040_frontera import TOCADOS_DESPUES

    ruta = "etl_sigrid/infrastructure/postgres/sql/retenciones/"
    assert TOCADOS_DESPUES == frozenset({
        ruta + "05_fin_obra.sql",  # F-161
        ruta + MOVIMIENTOS,
        ruta + SALDO_CLIENTE,
    })
    fuente = (RAIZ / "tests" / "test_f040_frontera.py").read_text(encoding="utf-8")
    assert "F-104" in fuente, "cada fichero admitido lleva su motivo"


def test_f104_r14_solo_cambian_01_y_08_en_retenciones_y_nada_en_tesoreria() -> None:
    base = _base_comun()
    diff = _git("diff", "--name-only", base, "--", "etl_sigrid/infrastructure/postgres/sql/retenciones",
                "etl_sigrid/infrastructure/postgres/sql/tesoreria")
    assert diff.returncode == 0, diff.stderr
    cambiados = set(diff.stdout.split())
    ruta = "etl_sigrid/infrastructure/postgres/sql/retenciones/"
    assert cambiados <= {ruta + MOVIMIENTOS, ruta + SALDO_CLIENTE}, sorted(cambiados)


def test_f104_r14_en_ventas_solo_06b_es_nuevo() -> None:
    base = _base_comun()
    diff = _git("diff", "--name-only", base, "--", "etl_sigrid/infrastructure/postgres/sql/ventas")
    assert diff.returncode == 0, diff.stderr
    assert set(diff.stdout.split()) <= {
        "etl_sigrid/infrastructure/postgres/sql/ventas/06b_retencion_cliente.sql"
    }


def test_f104_r15_las_vistas_pbi_siguen_leyendo_viva() -> None:
    vistas = _sql("02_views.sql")
    assert "estado = 'VIVA'" in vistas
    for vetado in ("origen_retencion", "cuenta_id"):
        assert vetado not in vistas, vetado


# ===========================================================================
# F · diccionario (R16-R18) y el comentario de la ingesta (R26)
# ===========================================================================


def test_f104_r16_fichas_de_los_tres_objetos_nuevos() -> None:
    fichas = _fichas()
    esperado = {
        "cuentas_cliente": ("tabla", COLUMNAS_CUENTAS),
        "saldo_contable_cliente": ("tabla", COLUMNAS_SALDO),
        "v_cuadre_cliente": ("vista", COLUMNAS_CUADRE),
    }
    for nombre, (tipo, columnas) in esperado.items():
        assert nombre in fichas, nombre
        assert fichas[nombre]["tipo"] == tipo, nombre
        assert tuple(fichas[nombre]["columnas"]) == columnas, nombre
        assert fichas[nombre]["paso_etl"] == "build_retenciones", nombre
        assert "F-104" in _plano(fichas[nombre]), nombre


def test_f104_r16_movimientos_documenta_las_columnas_nuevas_y_el_estado() -> None:
    ficha = _fichas()["movimientos"]
    columnas = list(ficha["columnas"])
    assert tuple(columnas[-2:]) == COLUMNAS_NUEVAS_MOVIMIENTOS
    assert ficha["columnas"]["origen_retencion"]["valores"] == ["EFECTO_RETENCION", "CUENTA_RETENCION"]
    estado = _plano(ficha["columnas"]["estado"])
    assert "AGR" in estado and "F-104" in estado
    assert "nunca vale BAJA" not in estado and "SIN VERIFICAR" not in _plano(ficha)
    tipo = _plano(ficha["columnas"]["tipo_id"])
    assert "CUENTA_RETENCION" in tipo, "la ficha dice que AGR/DIV no tienen tipo"
    assert "devuelve cero filas siempre" not in tipo


def test_f104_r16_la_contabilidad_manda_tambien_en_cliente() -> None:
    frase = "la retencion viva de cliente la manda la contabilidad"
    for nombre in ("movimientos", "v_cuadre_cliente", "saldo_contable_cliente"):
        assert frase in _plano(_fichas()[nombre]).lower(), nombre


def test_f104_r17_el_orden_de_magnitud_de_cliente_queda_verificado() -> None:
    texto = (DIR_DICC / "00_global.yaml").read_text(encoding="utf-8")
    ordenes = _yaml("00_global.yaml")["ordenes_de_magnitud"]
    valores = {o["valor_aproximado"] for o in ordenes}
    assert 21900000 not in valores
    assert {16000000, 10500000} <= valores
    cliente = [o for o in ordenes if "client" in o["concepto"].lower() and o["unidad"] == "EUR"]
    assert cliente, "no hay orden de magnitud de cliente"
    for orden in cliente:
        assert "SIN VERIFICAR" not in _plano(orden), orden["concepto"]
        assert "F-104" in _plano(orden["fuente"]) and "2026-11-16" in _plano(orden["fuente"])
    assert "SIN VERIFICAR" not in texto.split("ordenes_de_magnitud:", 1)[1].split("convenciones:", 1)[0]


def test_f104_r18_la_version_sube_una_sobre_main() -> None:
    contenido = _yaml("00_global.yaml")
    assert contenido["version"] == 80
    cabecera = (DIR_DICC / "00_global.yaml").read_text(encoding="utf-8").split("\nversion:", 1)[0]
    assert "# version 80 (F-104, 2026-11-" in cabecera


def test_f104_r26_el_comentario_de_cob_dice_el_criterio_nuevo() -> None:
    texto = (RAIZ / "config" / "tables_sigrid.yaml").read_text(encoding="utf-8")
    bloque = texto[texto.index("MÓDULO RETENCIONES"): texto.index("- source_table: pag")]
    assert "sigue saliendo solo de fecrea" not in bloque
    assert "sin verificar" not in bloque.lower()
    assert "F-104" in bloque and "AGR" in bloque
