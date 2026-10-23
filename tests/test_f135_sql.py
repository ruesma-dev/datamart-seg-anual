# tests/test_f135_sql.py
"""
F-135 · El SQL de la contabilidad partida en dos esquemas (R4-R14) y su paso.

`contabilidad_restringida` lleva la contabilidad COMPLETA (01-03, la de F-056
con la marca de lo restringido); `contabilidad` la GENERAL (04-07), sin los
apuntes de personal y con solo recuentos de lo que falta.

Lo que aquí se comprueba es el TEXTO del SQL: ningún test abre red ni BBDD. La
ejecución real del SQL sobre un PostgreSQL 16 se hizo en local, en un
contenedor desechable, y su resultado está en `progress/impl_F-135.md`.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain.restriccion_personal import (
    PATRON_CONCEPTO_NOMINA,
    REGEX_CUENTA_RESTRINGIDA,
    TEXTO_CUENTA_ENMASCARADA,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_CON = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "contabilidad"

SETUP = "00_setup.sql"
PLAN = "01_plan_cuentas.sql"
MAYOR = "02_mayor.sql"
SALDOS = "03_saldos_cuenta_mes.sql"
PLAN_GEN = "04_plan_cuentas_general.sql"
MAYOR_GEN = "05_mayor_general.sql"
SALDOS_GEN = "06_saldos_general.sql"
RECUENTO = "07_apuntes_restringidos_mes.sql"
FICHEROS = [SETUP, PLAN, MAYOR, SALDOS, PLAN_GEN, MAYOR_GEN, SALDOS_GEN, RECUENTO]

RESTR = "contabilidad_restringida"
EXTRA_MAYOR = ["restringido", "motivo_restriccion", "saldo_acumulado_visible"]

#: Las columnas de cada tabla de F-056, EN ORDEN: las de hoy. COPIADAS de
#: `tests/test_f056_contabilidad.py` y no importadas (la suite de otra feature
#: no es una API); si alguien cambia una de las dos, el contrato de F-056 y este
#: dejan de casar y uno de los dos falla.
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


# ---------------------------------------------------------------------------
# El parser de SELECT de F-056, COPIADO por el mismo motivo (con el arreglo de
# F-135: un `)` dentro de un literal no cierra la consulta).
# ---------------------------------------------------------------------------

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
        # F-135: un `)` DENTRO de un literal (prof -1, la regex '^(640|...)')
        # no cierra la consulta
        while q_fin < fin and not (texto[q_fin] == ")" and 0 <= prof[q_fin] < nivel) and not (
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


@cache
def _crudo(nombre: str) -> str:
    ruta = DIR_CON / nombre
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _sql(nombre: str) -> str:
    """El SQL sin comentarios `--` y con los blancos colapsados."""
    sin = "\n".join(linea.split("--", 1)[0] for linea in _crudo(nombre).splitlines())
    return re.sub(r"\s+", " ", sin).strip()


def _consultas(nombre: str, objeto: str) -> list[tuple[bool, list[str], list[str]]]:
    texto = _sql(nombre)
    m = re.search(rf"CREATE TABLE {re.escape(objeto)} AS ", texto)
    assert m, f"{nombre} no crea {objeto}"
    return _consultas_de(texto, m.end(), texto.index(";", m.end()))


def _columnas(nombre: str, objeto: str) -> list[str]:
    items = _consultas(nombre, objeto)[-1][1]
    return [re.split(r" AS |\.", i)[-1].strip() for i in items]


def _cte(nombre: str, cte: str) -> str:
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


def _guarda(nombre: str) -> str:
    texto = _sql(nombre)
    assert "DO $$" in texto, f"{nombre} sin guarda"
    return texto.split("DO $$", 1)[1].split("END $$;", 1)[0]


# ===========================================================================
# R4 · los MISMOS literales que el dominio
# ===========================================================================


def test_f135_r4_la_regex_de_cuentas_es_la_del_dominio() -> None:
    """Toda regex de prefijos que lleve el SQL es la del dominio, tal cual."""
    literal = f"'{REGEX_CUENTA_RESTRINGIDA}'"
    esperadas = {MAYOR: 2, PLAN_GEN: 1, MAYOR_GEN: 1}
    for nombre in FICHEROS:
        sql = _sql(nombre)
        regexes = re.findall(r"'\^\([^']*\)'", sql)
        assert all(r == literal for r in regexes), f"{nombre} lleva otra regex: {regexes}"
        assert len(regexes) == esperadas.get(nombre, 0), f"{nombre}: {len(regexes)} regex"


def test_f135_r4_el_patron_de_nomina_es_el_del_dominio() -> None:
    literal = f"~* '{PATRON_CONCEPTO_NOMINA}'"
    assert _sql(MAYOR).count(literal) == 1
    for nombre in FICHEROS:
        assert _sql(nombre).count("~*") == (1 if nombre == MAYOR else 0), nombre


def test_f135_r4_la_cuenta_se_compara_con_tilde_sensible() -> None:
    """El código va con `~` (anclado por `^`), no con `~*` ni `LIKE`."""
    for nombre in (MAYOR, PLAN_GEN, MAYOR_GEN):
        assert f"codigo_cuenta ~ '{REGEX_CUENTA_RESTRINGIDA}'" in _sql(nombre), nombre


# ===========================================================================
# R5-R7 · la contabilidad completa, en el esquema restringido
# ===========================================================================


def test_f135_r5_el_setup_crea_los_dos_esquemas_sin_conceder_nada() -> None:
    texto = _sql(SETUP)
    assert "CREATE SCHEMA IF NOT EXISTS contabilidad;" in texto
    assert f"CREATE SCHEMA IF NOT EXISTS {RESTR};" in texto
    for nombre in FICHEROS:
        sql = _sql(nombre).upper()
        assert "GRANT " not in sql and "REVOKE " not in sql and "DEFAULT PRIVILEGES" not in sql, (
            f"{nombre}: los permisos los da apply_grants, no el build"
        )


@pytest.mark.parametrize(
    ("nombre", "tabla"), [(PLAN, "plan_cuentas"), (MAYOR, "mayor"), (SALDOS, "saldos_cuenta_mes")]
)
def test_f135_r5_los_tres_de_f056_escriben_en_el_esquema_restringido(nombre: str, tabla: str) -> None:
    texto = _sql(nombre)
    assert f"DROP TABLE IF EXISTS {RESTR}.{tabla} CASCADE;" in texto
    assert f"CREATE TABLE {RESTR}.{tabla} AS" in texto
    assert f"COMMENT ON TABLE {RESTR}.{tabla} IS" in texto
    assert not re.search(r"(?<![\w])contabilidad\.(plan_cuentas|mayor|saldos_cuenta_mes)\b", texto), (
        f"{nombre} nombra la contabilidad GENERAL: el completo no puede leer lo filtrado"
    )


@pytest.mark.parametrize("tabla", ["plan_cuentas", "saldos_cuenta_mes"])
def test_f135_r5_plan_y_saldos_completos_tienen_las_columnas_de_hoy(tabla: str) -> None:
    nombre = PLAN if tabla == "plan_cuentas" else SALDOS
    assert _columnas(nombre, f"{RESTR}.{tabla}") == COLUMNAS[tabla]


def test_f135_r5_el_mayor_completo_son_las_de_hoy_mas_tres_al_final() -> None:
    assert _columnas(MAYOR, f"{RESTR}.mayor") == COLUMNAS["mayor"] + EXTRA_MAYOR


def test_f135_r5_el_mayor_completo_lee_el_plan_completo() -> None:
    assert (
        f"LEFT JOIN {RESTR}.plan_cuentas pc ON pc.cuenta_id = s.cuenta_id"
        in _cte(MAYOR, "marcados")
    )
    assert f"LEFT JOIN {RESTR}.plan_cuentas pa ON pa.cuenta_id = f.cuenta_id" in _cte(
        MAYOR, "asientos_personal"
    )


def test_f135_r5_el_acumulado_completo_no_cambia() -> None:
    """`saldo_acumulado` del completo es el de F-056: el admin lee como hasta hoy."""
    final = _consultas(MAYOR, f"{RESTR}.mayor")[-1][1]
    assert (
        "SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id ORDER BY s.fecha, "
        "s.codigo_asiento, s.posicion, s.apunte_id )::NUMERIC(18, 2) AS saldo_acumulado"
    ) in final


def test_f135_r5_el_acumulado_visible_solo_suma_lo_visible() -> None:
    final = _consultas(MAYOR, f"{RESTR}.mayor")[-1][1]
    assert final[-1] == (
        "CASE WHEN s.es_cuenta_restringida OR s.es_asiento_personal THEN NULL "
        "ELSE SUM(s.importe_saldo) FILTER ( WHERE NOT (s.es_cuenta_restringida OR "
        "s.es_asiento_personal) ) OVER ( PARTITION BY s.cuenta_id ORDER BY s.fecha, "
        "s.codigo_asiento, s.posicion, s.apunte_id ) END::NUMERIC(18, 2) AS saldo_acumulado_visible"
    ), "la misma ventana que saldo_acumulado, filtrada a lo visible y NULL en lo restringido (R9)"


def test_f135_r5_el_asiento_de_personal() -> None:
    """R2 en SQL: todos NORMAL y alguno CR (o con cuenta que no resuelve: falla
    cerrado) o con concepto de nómina, por asiento."""
    cte = _cte(MAYOR, "asientos_personal")
    assert cte.strip() == (
        f"SELECT f.asiento_id FROM fechados f LEFT JOIN {RESTR}.plan_cuentas pa "
        "ON pa.cuenta_id = f.cuenta_id WHERE f.asiento_id IS NOT NULL GROUP BY f.asiento_id "
        "HAVING bool_and(f.clase_bruta = 'NORMAL') AND bool_or(COALESCE(pa.codigo_cuenta ~ "
        f"'{REGEX_CUENTA_RESTRINGIDA}', f.cuenta_id IS NOT NULL) OR f.concepto ~* "
        f"'{PATRON_CONCEPTO_NOMINA}')"
    )


def test_f135_r5_la_marca_de_cada_apunte() -> None:
    cte = _cte(MAYOR, "marcados")
    assert (
        f"COALESCE(pc.codigo_cuenta ~ '{REGEX_CUENTA_RESTRINGIDA}', s.cuenta_id IS NOT NULL) "
        "AS es_cuenta_restringida"
    ) in cte, (
        "sin cuenta (cueide = 0) no es CR; con cuenta que no resuelve en el plan, SÍ "
        "(falla cerrado); y la marca nunca es NULL"
    )
    assert "(ap.asiento_id IS NOT NULL) AS es_asiento_personal" in cte
    assert "LEFT JOIN asientos_personal ap ON ap.asiento_id = s.asiento_id" in cte
    final = _consultas(MAYOR, f"{RESTR}.mayor")[-1][1]
    assert "(s.es_cuenta_restringida OR s.es_asiento_personal) AS restringido" in final


def test_f135_r5_indice_parcial_de_restringidos() -> None:
    assert (
        f"CREATE INDEX idx_con_mayor_restringido ON {RESTR}.mayor (restringido) WHERE restringido;"
    ) in _sql(MAYOR)


def test_f135_r6_la_guarda_de_recuento_va_sobre_el_completo() -> None:
    guarda = _guarda(MAYOR)
    assert f"SELECT count(*) INTO v_mayor FROM {RESTR}.mayor;" in guarda
    assert "SELECT count(*) INTO v_apu FROM raw.apu;" in guarda
    assert "IF v_mayor <> v_apu THEN RAISE EXCEPTION" in guarda
    assert _sql(MAYOR).index("DO $$") > _sql(MAYOR).index(f"CREATE TABLE {RESTR}.mayor AS")


def test_f135_r7_la_cuenta_gana_al_asiento() -> None:
    final = _consultas(MAYOR, f"{RESTR}.mayor")[-1][1]
    assert (
        "CASE WHEN s.es_cuenta_restringida AND s.codigo_cuenta IS NULL THEN 'CUENTA_SIN_RESOLVER' "
        "WHEN s.es_cuenta_restringida THEN 'CUENTA' "
        "WHEN s.es_asiento_personal THEN 'ASIENTO_PERSONAL' END AS motivo_restriccion"
    ) in final


# ===========================================================================
# R8-R14 · la contabilidad general, filtrada y materializada
# ===========================================================================


def test_f135_r8_el_mayor_general_son_los_no_restringidos_con_las_columnas_de_hoy() -> None:
    consultas = _consultas(MAYOR_GEN, "contabilidad.mayor")
    assert len(consultas) == 1
    _, items, clausulas = consultas[0]
    assert _columnas(MAYOR_GEN, "contabilidad.mayor") == COLUMNAS["mayor"]
    assert clausulas == ["WHERE NOT r.restringido"]
    assert f"FROM {RESTR}.mayor r WHERE NOT r.restringido" in _sql(MAYOR_GEN)
    copiadas = [i for i in items if i != "r.saldo_acumulado_visible AS saldo_acumulado"]
    assert copiadas == [f"r.{c}" for c in COLUMNAS["mayor"] if c != "saldo_acumulado"], (
        "las demás columnas, copiadas tal cual"
    )


def test_f135_r9_el_acumulado_general_es_el_visible() -> None:
    items = _consultas(MAYOR_GEN, "contabilidad.mayor")[0][1]
    assert "r.saldo_acumulado_visible AS saldo_acumulado" in items
    assert "r.saldo_acumulado," not in _sql(MAYOR_GEN)


def test_f135_r10_guarda_sin_cr_y_con_recuento_cuadrado() -> None:
    guarda = _guarda(MAYOR_GEN)
    assert (
        "SELECT count(*) INTO v_cr FROM contabilidad.mayor WHERE codigo_cuenta ~ "
        f"'{REGEX_CUENTA_RESTRINGIDA}';"
    ) in guarda
    assert "IF v_cr <> 0 THEN RAISE EXCEPTION" in guarda
    assert "SELECT count(*) INTO v_general FROM contabilidad.mayor;" in guarda
    assert (
        "SELECT count(*), count(*) FILTER (WHERE restringido) INTO v_completo, v_restringidos "
        f"FROM {RESTR}.mayor;"
    ) in guarda
    assert "IF v_general + v_restringidos <> v_completo THEN RAISE EXCEPTION" in guarda
    texto = _sql(MAYOR_GEN)
    assert texto.index("DO $$") > texto.index("CREATE TABLE contabilidad.mayor AS"), (
        "postcondición en la misma transacción: si salta, queda la tabla anterior"
    )


def test_f135_r10_la_cuenta_sin_resolver_falla_cerrado() -> None:
    """Review de F-135, pasada 1: un apunte con `cuenta_id` cuya cuenta no está
    en el plan quedaba con `codigo_cuenta` NULL, `restringido = false`, y pasaba
    al general sin que la guarda lo viera. Ahora (1) `02` lo restringe y hace
    AP a su asiento (los dos COALESCE de arriba), y (2) la guarda de `05`, por
    si acaso, para el build si aun así llega uno al general."""
    guarda = _guarda(MAYOR_GEN)
    assert (
        "SELECT count(*) INTO v_sin_resolver FROM contabilidad.mayor "
        "WHERE cuenta_id IS NOT NULL AND codigo_cuenta IS NULL;"
    ) in guarda
    assert "IF v_sin_resolver <> 0 THEN RAISE EXCEPTION" in guarda
    marcados = _cte(MAYOR, "marcados")
    assert "s.cuenta_id IS NOT NULL) AS es_cuenta_restringida" in marcados
    assert ", FALSE)" not in marcados, "el COALESCE a FALSE es el que abría el criterio"
    assert "f.cuenta_id IS NOT NULL) OR f.concepto" in _cte(MAYOR, "asientos_personal")


def test_f135_r11_saldos_generales_solo_de_lo_visible() -> None:
    mensual = _cte(SALDOS_GEN, "mensual")
    assert mensual.strip().endswith(
        f"FROM {RESTR}.mayor m GROUP BY COALESCE(m.cuenta_id, 0), m.empresa_id, m.ejercicio, "
        "m.mes HAVING COUNT(*) FILTER (WHERE NOT m.restringido) > 0"
    ), "se omiten las filas sin ningún apunte visible"
    for expresion in (
        "COUNT(*) FILTER (WHERE NOT m.restringido) AS num_apuntes",
        "SUM(m.debe) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2) AS debe",
        "SUM(m.haber) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2) AS haber",
        "COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento IN "
        "('APERTURA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS importe_apertura",
        "COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento = "
        "'NORMAL'), 0)::NUMERIC(18, 2) AS importe_movimiento",
        "COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento = "
        "'REGULARIZACION'), 0)::NUMERIC(18, 2) AS importe_regularizacion",
        "COALESCE(SUM(m.importe) FILTER (WHERE NOT m.restringido AND m.clase_asiento = "
        "'CIERRE'), 0)::NUMERIC(18, 2) AS importe_cierre",
        "SUM(m.importe_saldo) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2) AS importe_saldo",
        "COUNT(*) FILTER (WHERE m.restringido) AS num_apuntes_restringidos",
    ):
        assert expresion in mensual, f"falta «{expresion}» (R11)"
    assert _columnas(SALDOS_GEN, "contabilidad.saldos_cuenta_mes") == COLUMNAS[
        "saldos_cuenta_mes"
    ] + ["num_apuntes_restringidos", "incompleto"]
    final = _consultas(SALDOS_GEN, "contabilidad.saldos_cuenta_mes")[-1][1]
    assert "s.num_apuntes_restringidos > 0 AS incompleto" in final
    assert (
        "SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id, s.empresa_id ORDER BY "
        "s.ejercicio, s.mes )::NUMERIC(18, 2) AS saldo_acumulado"
    ) in final


def test_f135_r11_la_suma_sin_filtro_no_se_cuela() -> None:
    """Ningún agregado de importes del 06 sin `NOT m.restringido`: sería sumar
    lo restringido en la general."""
    mensual = _cte(SALDOS_GEN, "mensual")
    for agregado in re.findall(r"SUM\([^)]*\)(?: FILTER \([^)]*\))?", mensual):
        assert "NOT m.restringido" in agregado, f"agregado sin filtrar: {agregado}"


def test_f135_r12_plan_general_con_las_cuentas_cr_enmascaradas() -> None:
    marcadas = _cte(PLAN_GEN, "marcadas")
    assert (
        f"COALESCE(r.nivel = 5 AND r.codigo_cuenta ~ '{REGEX_CUENTA_RESTRINGIDA}', FALSE) "
        "AS restringida"
    ) in marcadas, "solo las cuentas auxiliares (nivel 5) CR"
    assert f"FROM {RESTR}.plan_cuentas r" in marcadas
    items = _consultas(PLAN_GEN, "contabilidad.plan_cuentas")[-1][1]
    assert (
        f"CASE WHEN m.restringida THEN '{TEXTO_CUENTA_ENMASCARADA}' ELSE m.nombre_cuenta END "
        "AS nombre_cuenta"
    ) in items
    assert _columnas(PLAN_GEN, "contabilidad.plan_cuentas") == COLUMNAS["plan_cuentas"] + [
        "restringida"
    ]
    assert " WHERE " not in _sql(PLAN_GEN).split("CREATE TABLE contabilidad.plan_cuentas AS")[1].split(";")[0], (
        "el plan general conserva TODOS los nodos"
    )


def test_f135_r13_recuentos_sin_importes() -> None:
    consultas = _consultas(RECUENTO, "contabilidad.apuntes_restringidos_mes")
    assert len(consultas) == 1
    _, items, clausulas = consultas[0]
    assert items == [
        "m.empresa_id", "m.ejercicio", "m.mes",
        "COUNT(*) AS num_apuntes", "COUNT(DISTINCT m.asiento_id) AS num_asientos",
        "COUNT(*) FILTER (WHERE m.motivo_restriccion = 'CUENTA_SIN_RESOLVER') "
        "AS num_apuntes_sin_resolver",
    ]
    assert clausulas == ["WHERE m.restringido", "GROUP BY m.empresa_id, m.ejercicio, m.mes"]
    sql = _sql(RECUENTO)
    for prohibido in ("debe", "haber", "importe", "SUM("):
        assert prohibido not in sql.split("COMMENT ON")[0], f"07 nombra {prohibido} (D5)"
    assert (
        "ALTER TABLE contabilidad.apuntes_restringidos_mes ADD PRIMARY KEY (empresa_id, ejercicio, mes);"
    ) in sql


@pytest.mark.parametrize(
    ("nombre", "indices"),
    [
        (PLAN_GEN, [
            "ALTER TABLE contabilidad.plan_cuentas ADD PRIMARY KEY (cuenta_id);",
            "CREATE UNIQUE INDEX uq_con_plan_empresa_codigo ON contabilidad.plan_cuentas (empresa_id, codigo_cuenta);",
            "CREATE INDEX idx_con_plan_padre ON contabilidad.plan_cuentas (cuenta_padre_id);",
        ]),
        (MAYOR_GEN, [
            "ALTER TABLE contabilidad.mayor ADD PRIMARY KEY (apunte_id);",
            "CREATE INDEX idx_con_mayor_empresa_cuenta_fecha ON contabilidad.mayor (empresa_id, codigo_cuenta, fecha);",
            "CREATE INDEX idx_con_mayor_cuenta_fecha ON contabilidad.mayor (cuenta_id, fecha);",
            "CREATE INDEX idx_con_mayor_asiento ON contabilidad.mayor (asiento_id);",
            "CREATE INDEX idx_con_mayor_obra ON contabilidad.mayor (obra_id);",
            "CREATE INDEX idx_con_mayor_tercero ON contabilidad.mayor (tercero_id);",
        ]),
        (SALDOS_GEN, [
            "ALTER TABLE contabilidad.saldos_cuenta_mes ADD PRIMARY KEY (cuenta_id, empresa_id, ejercicio, mes);",
            "CREATE INDEX idx_con_saldos_empresa_ejercicio ON contabilidad.saldos_cuenta_mes (empresa_id, ejercicio, mes);",
        ]),
    ],
)
def test_f135_r14_generales_materializadas_con_los_indices_de_hoy(
    nombre: str, indices: list[str]
) -> None:
    texto = _sql(nombre)
    assert "CREATE TABLE contabilidad." in texto and "CREATE VIEW" not in texto.upper()
    for indice in indices:
        assert indice in texto, f"{nombre}: falta {indice}"


@pytest.mark.parametrize("nombre", [PLAN_GEN, MAYOR_GEN, SALDOS_GEN, RECUENTO])
def test_f135_r14_las_generales_solo_leen_el_completo(nombre: str) -> None:
    leidas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+\.\w+)", _sql(nombre).split("DO $$")[0]))
    assert leidas <= {f"{RESTR}.plan_cuentas", f"{RESTR}.mayor"}, f"{nombre} lee {leidas}"
    sin_comentario = re.sub(r"COMMENT ON TABLE .*? IS '[^']*';", "", _sql(nombre))
    assert "raw." not in sin_comentario, f"{nombre} no recalcula nada desde raw"


@pytest.mark.parametrize("nombre", FICHEROS)
def test_f135_ficheros_con_cabecera_y_ruta(nombre: str) -> None:
    assert _crudo(nombre).splitlines()[0] == (
        f"-- etl_sigrid/infrastructure/postgres/sql/contabilidad/{nombre}"
    )


@pytest.mark.parametrize(
    ("nombre", "tabla"),
    [(PLAN_GEN, "plan_cuentas"), (MAYOR_GEN, "mayor"), (SALDOS_GEN, "saldos_cuenta_mes"),
     (RECUENTO, "apuntes_restringidos_mes")],
)
def test_f135_generales_idempotentes(nombre: str, tabla: str) -> None:
    texto = _sql(nombre)
    assert texto.index(f"DROP TABLE IF EXISTS contabilidad.{tabla} CASCADE;") < texto.index(
        f"CREATE TABLE contabilidad.{tabla} AS"
    )
    assert f"COMMENT ON TABLE contabilidad.{tabla} IS" in texto


# ===========================================================================
# El paso: los ocho ficheros y su esquema destino
# ===========================================================================


def test_f135_sub_pasos_los_ocho_ficheros_con_su_esquema() -> None:
    from etl_sigrid.application.steps import build_contabilidad_step

    declarados = [
        (s.name, s.sql_file, s.target_schema, s.target_table)
        for s in build_contabilidad_step.SUB_PASOS
    ]
    assert declarados == [
        ("setup", SETUP, None, None),
        ("plan_cuentas", PLAN, RESTR, "plan_cuentas"),
        ("mayor", MAYOR, RESTR, "mayor"),
        ("saldos_cuenta_mes", SALDOS, RESTR, "saldos_cuenta_mes"),
        ("plan_cuentas_general", PLAN_GEN, "contabilidad", "plan_cuentas"),
        ("mayor_general", MAYOR_GEN, "contabilidad", "mayor"),
        ("saldos_general", SALDOS_GEN, "contabilidad", "saldos_cuenta_mes"),
        ("apuntes_restringidos_mes", RECUENTO, "contabilidad", "apuntes_restringidos_mes"),
    ]
    for sub in build_contabilidad_step.SUB_PASOS:
        assert (DIR_CON / sub.sql_file).exists(), f"{sub.sql_file} declarado y no existe"


def test_f135_sub_pasos_el_docstring_dice_que_es_general_y_que_restringido() -> None:
    from etl_sigrid.application.steps import build_contabilidad_step

    doc = build_contabilidad_step.__doc__ or ""
    assert RESTR in doc and "sigrid_dm_autorizado_ro" in doc
    for nombre in FICHEROS:
        assert nombre in doc, f"el docstring no cita {nombre}"


# ===========================================================================
# R21-R22 · el diccionario (T10)
# ===========================================================================

DIR_DICC = RAIZ / "config" / "diccionario"
COLUMNAS_GENERALES = {
    "plan_cuentas": (PLAN_GEN, COLUMNAS["plan_cuentas"] + ["restringida"]),
    "mayor": (MAYOR_GEN, COLUMNAS["mayor"]),
    "saldos_cuenta_mes": (
        SALDOS_GEN, COLUMNAS["saldos_cuenta_mes"] + ["num_apuntes_restringidos", "incompleto"]
    ),
    "apuntes_restringidos_mes": (
        RECUENTO,
        ["empresa_id", "ejercicio", "mes", "num_apuntes", "num_asientos", "num_apuntes_sin_resolver"],
    ),
}


@cache
def _yaml(nombre: str) -> dict:
    import yaml

    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _texto(dato: object) -> str:
    import yaml

    return yaml.safe_dump(dato, allow_unicode=True, width=10_000)


def test_f135_diccionario_el_esquema_restringido_es_del_datamart() -> None:
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    assert RESTR in ESQUEMAS_DEL_DATAMART
    entrada = _yaml("00_global.yaml")["esquemas"][RESTR]
    assert entrada["pasos_etl"] == ["build_contabilidad"]
    assert entrada["refresco"] == "nocturno"
    assert "sigrid_dm_autorizado_ro" in entrada["para_que_sirve"]


@pytest.mark.parametrize(
    ("tabla", "nombre", "esperadas"),
    [
        ("plan_cuentas", PLAN, COLUMNAS["plan_cuentas"]),
        ("mayor", MAYOR, COLUMNAS["mayor"] + EXTRA_MAYOR),
        ("saldos_cuenta_mes", SALDOS, COLUMNAS["saldos_cuenta_mes"]),
    ],
)
def test_f135_diccionario_fichas_del_completo_con_las_columnas_del_sql(
    tabla: str, nombre: str, esperadas: list[str]
) -> None:
    fichero = _yaml("contabilidad_restringida.yaml")
    assert fichero["esquema"] == RESTR
    ficha = fichero["objetos"][tabla]
    assert list(ficha["columnas"]) == esperadas == _columnas(nombre, f"{RESTR}.{tabla}")
    assert ficha["paso_etl"] == "build_contabilidad" and ficha["refresco"] == "nocturno"
    for columna, datos in ficha["columnas"].items():
        assert datos.get("significado"), f"{RESTR}.{tabla}.{columna} sin significado"
    assert "sigrid_dm_autorizado_ro" in ficha["descripcion"]


@pytest.mark.parametrize("tabla", sorted(COLUMNAS_GENERALES))
def test_f135_diccionario_fichas_generales_con_las_columnas_del_sql(tabla: str) -> None:
    nombre, esperadas = COLUMNAS_GENERALES[tabla]
    ficha = _yaml("contabilidad.yaml")["objetos"][tabla]
    assert list(ficha["columnas"]) == esperadas == _columnas(nombre, f"contabilidad.{tabla}")
    for columna, datos in ficha["columnas"].items():
        assert datos.get("significado"), f"contabilidad.{tabla}.{columna} sin significado"


def test_f135_diccionario_la_general_dice_que_le_falta_y_donde_esta() -> None:
    objetos = _yaml("contabilidad.yaml")["objetos"]
    mayor = _texto(objetos["mayor"])
    for termino in ("contabilidad_restringida", "apuntes_restringidos_mes", "55.504", "R-PERFILES"):
        assert termino in mayor, f"la ficha del mayor general no dice «{termino}»"
    assert "SIN FILTRAR NINGUNO" not in objetos["mayor"]["descripcion"], "ya no es verdad"
    acumulado = objetos["mayor"]["columnas"]["saldo_acumulado"]["significado"]
    assert "visible" in acumulado.lower()
    saldos = objetos["saldos_cuenta_mes"]["columnas"]
    assert "importe" not in saldos["num_apuntes_restringidos"].get("unidad", "")
    assert saldos["incompleto"]["significado"]
    plan = objetos["plan_cuentas"]
    assert TEXTO_CUENTA_ENMASCARADA in _texto(plan)
    recuento = objetos["apuntes_restringidos_mes"]
    assert recuento["clave_negocio"] == ["empresa_id", "ejercicio", "mes"]
    assert recuento["paso_etl"] == "build_contabilidad"
    assert all("unidad" not in c for c in recuento["columnas"].values()), "solo recuentos (D5)"


def test_f135_r22_regla_dura_contabilidad_restringida() -> None:
    glob = _yaml("00_global.yaml")
    assert glob["version"] >= 49, "F-090 publicó la 48; F-135 sube a 49"
    reglas = {r["codigo"]: r for r in glob["reglas"]}
    # F-147: la regla de la contabilidad restringida se fundió en `R-PERFILES`
    # (entera); lo propio de la contabilidad pasó a sus fichas.
    regla = reglas["R-PERFILES"]
    assert regla["severidad"] == "bloqueante" and regla["entrega"] == "entera"
    assert {"contabilidad", RESTR} <= set(regla["ambito"])
    texto = " ".join(
        [regla["resumen"], regla["regla"], regla["motivo"]]
        + [_texto(f) for f in _yaml("contabilidad.yaml")["objetos"].values()]
        + [(DIR_DICC / "contabilidad_restringida.yaml").read_text(encoding="utf-8")]
    )
    for termino in (
        "contabilidad_restringida", "sigrid_dm_autorizado_ro", "incompleto",
        "apuntes_restringidos_mes", "num_apuntes_restringidos", "nunca se suman",
        "retenciones", "Juan Romero", "F-135",
    ):
        assert termino in texto, f"ni R-PERFILES ni las fichas dicen «{termino}»"
    assert set(reglas["R-SALDO-CONTABLE"]["ambito"]) >= {
        f"{RESTR}.mayor", f"{RESTR}.saldos_cuenta_mes"
    }, "la trampa del cierre y la apertura vale igual en la completa"
    assert RESTR in reglas["R-FRESCURA"]["ambito"]


def test_f135_r21_retenciones_declara_la_excepcion() -> None:
    texto = (DIR_DICC / "retenciones.yaml").read_text(encoding="utf-8")
    assert "F-135" in texto and "8 apuntes" in texto and "cueretide" in texto


# ===========================================================================
# R24 · la documentación dice qué lee cada rol (T11)
# ===========================================================================

AZURE_APPS = RAIZ.parent / "azure-apps"


@pytest.mark.parametrize(
    "ruta",
    [
        RAIZ / "docs" / "ARCHITECTURE.md",
        AZURE_APPS / "datamart_seg_anual.md",
        AZURE_APPS / "mcp_bbdd.md",
    ],
    ids=["ARCHITECTURE", "azure-apps/datamart", "azure-apps/mcp_bbdd"],
)
def test_f135_docs_dicen_que_lee_cada_rol(ruta: Path) -> None:
    if not ruta.exists():
        pytest.skip(f"{ruta} no está junto a este repositorio")
    texto = ruta.read_text(encoding="utf-8")
    for termino in ("contabilidad_restringida", "sigrid_dm_autorizado_ro", "F-135", "F-087"):
        assert termino in texto, f"{ruta.name} no dice «{termino}»"
    assert "F-008" in texto, f"{ruta.name} no dice que el rol por usuario es de mcp-bbdd (F-008)"


def test_f135_docs_azure_apps_dice_que_raw_queda_fuera() -> None:
    ruta = AZURE_APPS / "datamart_seg_anual.md"
    if not ruta.exists():
        pytest.skip("azure-apps no está junto a este repositorio")
    texto = ruta.read_text(encoding="utf-8")
    assert "PG_VETOED_SCHEMAS" in texto and "apuntes_restringidos_mes" in texto


# ===========================================================================
# R23 · F-127 hereda el criterio (review de F-135, pasada 1, cambio 3)
# ===========================================================================


def test_f135_r23_la_ficha_de_f127_hereda_el_criterio_de_apa() -> None:
    """El mayor analítico NACE RESTRINGIDO: la ficha de F-127 dice con qué
    criterio (las tres vías de un `apa` restringido), con qué rol y con la cifra
    medida, y F-135 no le cambia el estado."""
    import json

    datos = json.loads((RAIZ / "harness" / "features.json").read_text(encoding="utf-8"))
    f127 = next(f for f in datos["features"] if f["id"] == "F-127")
    texto = f127["description"] + " " + " ".join(f127["acceptance"])
    from config.settings import DEFAULT_RESTRICTED_ROLE, NOMBRE_AUTORIZADO_RETIRADO

    for termino in ("apuide", "conide", "cuenta_analitica_contrapartida_id",
                    "contabilidad_restringida"):
        assert termino in texto, f"la ficha de F-127 no dice «{termino}» (R23)"
    # F-141 renombró el grupo autorizado (D6). La ficha es del líder
    # (`features.json`): vale con el nombre nuevo o con el que tenía al escribirse.
    assert DEFAULT_RESTRICTED_ROLE in texto or NOMBRE_AUTORIZADO_RETIRADO in texto, (
        "la ficha de F-127 no dice con qué rol (R23)"
    )
    assert "100.502 de las 716.007" in texto, "la cifra medida (R23)"
    assert f127["status"] == "pending", "F-135 no cambia el estado de F-127"
