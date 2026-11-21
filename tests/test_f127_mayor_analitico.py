# tests/test_f127_mayor_analitico.py
"""
F-127 · El mayor analítico (`raw.apa`) en dos esquemas, como F-135.

`contabilidad_restringida` lleva el mayor analítico COMPLETO y sus saldos (08,
09); `contabilidad`, el GENERAL sin lo restringido (10, 11) y solo RECUENTOS de
lo que falta (12). Qué fila analítica es restringida lo dice el oráculo de
`etl_sigrid/domain/restriccion_personal.py` (R7-R9), y el SQL lleva sus mismos
literales (R10).

Ningún test de este fichero abre red ni BBDD: se comprueba el dominio y el
TEXTO del SQL. La ejecución real de los SELECT contra el `raw` de Azure, en una
transacción de solo lectura, está en `progress/impl_F-127.md`.
"""

from __future__ import annotations

import re

import pytest

from etl_sigrid.domain.restriccion_personal import (
    MOTIVO_APUNTE_RESTRINGIDO,
    MOTIVO_APUNTE_SIN_RESOLVER,
    CODIGO_CENTRO_CONTRAPARTIDA,
    MOTIVO_ASIENTO_PERSONAL,
    MOTIVO_CONTRAPARTIDA,
    PATRON_CONCEPTO_NOMINA,
    REGEX_CUENTA_RESTRINGIDA,
    TIPO_ASIENTO_ANALITICO,
    TIPO_ASIENTO_CONTABLE,
    TIPO_ASIENTO_OTRO,
    TIPO_CON_ASIENTO,
    TIPO_CON_ASIENTO_ANALITICO,
    FilaAnalitica,
    centros_de_contrapartida,
    es_apunte_analitico_restringido,
    es_cuenta_contrapartida,
    motivo_apunte_analitico,
    obra_imputada,
    tipo_asiento,
)

# Los ayudantes de lectura del SQL son los de F-135 (mismo directorio): el SQL
# sin comentarios `--` y con los blancos colapsados, sus CTE, sus SELECT y su
# guarda `DO $$`.
from tests.test_f135_sql import (
    DIR_CON,
    _columnas,
    _consultas,
    _crudo,
    _cte,
    _guarda,
    _sql,
)


def _fila(
    apunte_id: int | None = None,
    resuelto: bool = False,
    restringido: bool = False,
    personal: bool = False,
    cp: bool = False,
) -> FilaAnalitica:
    return FilaAnalitica(
        apunte_id=apunte_id,
        apunte_resuelto=resuelto,
        apunte_restringido=restringido,
        asiento_personal=personal,
        cuenta_es_contrapartida=cp,
    )


# ===========================================================================
# R3 · el tipo del asiento (`con.tip`)
# ===========================================================================


def test_f127_r3_los_literales_de_con_tip() -> None:
    """Escritos A MANO: 20 es el asiento contable y 32 el analítico puro."""
    assert (TIPO_CON_ASIENTO, TIPO_CON_ASIENTO_ANALITICO) == (20, 32)
    assert (TIPO_ASIENTO_CONTABLE, TIPO_ASIENTO_ANALITICO, TIPO_ASIENTO_OTRO) == (
        "CONTABLE", "ANALITICO", "OTRO",
    )


@pytest.mark.parametrize(
    ("tip", "esperado"),
    [(20, "CONTABLE"), (32, "ANALITICO"), (16, "OTRO"), (19, "OTRO"), (0, "OTRO"),
     (None, "OTRO"), (21, "OTRO"), (31, "OTRO"), (33, "OTRO")],
)
def test_f127_r3_tipo_de_asiento(tip: int | None, esperado: str) -> None:
    assert tipo_asiento(tip) == esperado


# ===========================================================================
# R7 · qué fila analítica es restringida (C1, C2, C3)
# ===========================================================================


def test_f127_r7_una_fila_sin_nada_es_visible() -> None:
    assert not es_apunte_analitico_restringido(_fila())
    assert not es_apunte_analitico_restringido(_fila(apunte_id=7, resuelto=True))


def test_f127_r7_c1_apunte_restringido() -> None:
    assert es_apunte_analitico_restringido(_fila(apunte_id=7, resuelto=True, restringido=True))


def test_f127_r7_c2_asiento_de_personal() -> None:
    assert es_apunte_analitico_restringido(_fila(apunte_id=7, resuelto=True, personal=True))


def test_f127_r7_c3_cuenta_de_contrapartida() -> None:
    """También sin apunte financiero: el abono de los asientos `ANALITICO`."""
    assert es_apunte_analitico_restringido(_fila(cp=True))


@pytest.mark.parametrize("cp", [False, True])
@pytest.mark.parametrize("personal", [False, True])
@pytest.mark.parametrize("restringido", [False, True])
def test_f127_r7_cualquiera_de_las_tres_restringe(cp: bool, personal: bool, restringido: bool) -> None:
    fila = _fila(apunte_id=7, resuelto=True, restringido=restringido, personal=personal, cp=cp)
    assert es_apunte_analitico_restringido(fila) == (cp or personal or restringido)


# --- C3 con D7-b: la CP actual del recurso o una cuenta antigua de su centro ---


def test_f127_r7_c3_la_cp_actual_del_recurso() -> None:
    assert es_cuenta_contrapartida(
        10, centro_coste_id=None, abonada_en_analitico=False,
        contrapartidas={10, 11}, centros_contrapartida=frozenset(),
    )


def test_f127_r7_c3_d7_cuenta_antigua_del_centro_de_cp_con_abono_analitico() -> None:
    """D7-b: una cuenta de un centro de CP con abono en un asiento `ANALITICO`
    es una CP de antes que el recurso ya no declara: falla cerrado."""
    assert es_cuenta_contrapartida(
        99, centro_coste_id=5, abonada_en_analitico=True,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
    )


@pytest.mark.parametrize(
    ("centro", "abonada"),
    [(5, False), (6, True), (None, True), (None, False)],
    ids=["centro-cp-sin-abono", "centro-de-obra", "sin-centro", "nada"],
)
def test_f127_r7_c3_d7_no_alcanza_a_otras_cuentas(centro: int | None, abonada: bool) -> None:
    """Sin abono analítico, o en un centro de obra (los 9 cargos corregidos de
    D7), o sin centro: no es CP."""
    assert not es_cuenta_contrapartida(
        99, centro_coste_id=centro, abonada_en_analitico=abonada,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
    )


def test_f127_r7_c3_d9_toda_cuenta_del_centro_cp_es_cp() -> None:
    """D9 (c1, enmienda 2026-11-21): una cuenta del centro `CP` es CP aunque no
    sea la de ningún recurso ni tenga abono analítico (las tres de la review)."""
    assert es_cuenta_contrapartida(
        99, centro_coste_id=7, abonada_en_analitico=False,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
        en_centro_contrapartida=True,
    )


def test_f127_r7_c3_d9_el_centro_cp_es_el_de_codigo_cp() -> None:
    assert CODIGO_CENTRO_CONTRAPARTIDA == "CP"


def test_f127_r7_c3_d9_sin_cuenta_no_es_cp_ni_en_el_centro_cp() -> None:
    assert not es_cuenta_contrapartida(
        None, centro_coste_id=7, abonada_en_analitico=True,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
        en_centro_contrapartida=True,
    )


def test_f127_r7_c3_sin_cuenta_no_es_cp() -> None:
    """`cueide = 0` (NULL): no es CP aunque su centro lo sea."""
    assert not es_cuenta_contrapartida(
        None, centro_coste_id=5, abonada_en_analitico=True,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
    )


def test_f127_r7_c3_los_centros_de_cp_son_los_de_las_cp_actuales() -> None:
    centro_de_cuenta = {10: 5, 11: 5, 12: 8, 13: None, 20: 6}
    assert centros_de_contrapartida({10, 11, 12, 13, 14}, centro_de_cuenta) == frozenset({5, 8})


def test_f127_r7_c3_sin_cp_no_hay_centros() -> None:
    assert centros_de_contrapartida(set(), {10: 5}) == frozenset()


# ===========================================================================
# R8 · la precedencia del motivo
# ===========================================================================


def test_f127_r8_visible_no_tiene_motivo() -> None:
    assert motivo_apunte_analitico(_fila(apunte_id=7, resuelto=True)) is None
    assert motivo_apunte_analitico(_fila()) is None


@pytest.mark.parametrize(
    ("fila", "motivo"),
    [
        (_fila(apunte_id=7, resuelto=True, restringido=True, personal=True, cp=True), "CONTRAPARTIDA"),
        (_fila(apunte_id=7, resuelto=False, personal=True, cp=True), "CONTRAPARTIDA"),
        (_fila(apunte_id=7, resuelto=False, personal=True), "APUNTE_SIN_RESOLVER"),
        (_fila(apunte_id=7, resuelto=True, restringido=True, personal=True), "APUNTE_RESTRINGIDO"),
        (_fila(apunte_id=7, resuelto=True, restringido=True), "APUNTE_RESTRINGIDO"),
        (_fila(apunte_id=7, resuelto=True, personal=True), "ASIENTO_PERSONAL"),
        (_fila(personal=True), "ASIENTO_PERSONAL"),
        (_fila(cp=True), "CONTRAPARTIDA"),
    ],
)
def test_f127_r8_precedencia(fila: FilaAnalitica, motivo: str) -> None:
    """CONTRAPARTIDA > APUNTE_SIN_RESOLVER > APUNTE_RESTRINGIDO > ASIENTO_PERSONAL."""
    assert motivo_apunte_analitico(fila) == motivo


def test_f127_r8_los_literales_de_motivo() -> None:
    assert (
        MOTIVO_CONTRAPARTIDA, MOTIVO_APUNTE_SIN_RESOLVER, MOTIVO_APUNTE_RESTRINGIDO,
        MOTIVO_ASIENTO_PERSONAL,
    ) == ("CONTRAPARTIDA", "APUNTE_SIN_RESOLVER", "APUNTE_RESTRINGIDO", "ASIENTO_PERSONAL")


# ===========================================================================
# R9 · falla cerrado: el apunte que no está en el mayor completo
# ===========================================================================


def test_f127_r9_apunte_sin_resolver_es_restringido() -> None:
    fila = _fila(apunte_id=7, resuelto=False)
    assert motivo_apunte_analitico(fila) == MOTIVO_APUNTE_SIN_RESOLVER
    assert es_apunte_analitico_restringido(fila)


def test_f127_r9_sin_apunte_financiero_no_es_sin_resolver() -> None:
    """`apuide = 0` (los asientos `ANALITICO`): no hay apunte que resolver."""
    assert motivo_apunte_analitico(_fila(apunte_id=None, resuelto=False)) is None


# ===========================================================================
# R6 · la obra imputada de un asiento ANALITICO (D4)
# ===========================================================================


@pytest.mark.parametrize(
    ("obras", "esperada"),
    [
        ([4, 4, 4], 4),
        ([4, None, 4], 4),
        ([4], 4),
        ([4, 5], None),
        ([None, None], None),
        ([], None),
    ],
    ids=["una", "una-y-sin-obra", "sola", "dos", "ninguna", "vacio"],
)
def test_f127_r6_la_unica_obra_de_cargo(obras: list[int | None], esperada: int | None) -> None:
    assert obra_imputada(obras) == esperada


# ===========================================================================
# El SQL
# ===========================================================================

RESTR = "contabilidad_restringida"
MAYOR_ANA = "08_mayor_analitico.sql"
SALDOS_ANA = "09_saldos_analitica.sql"
MAYOR_ANA_GEN = "10_mayor_analitico_general.sql"
SALDOS_ANA_GEN = "11_saldos_analitica_general.sql"
RECUENTO_ANA = "12_apuntes_analiticos_restringidos_mes.sql"
FICHEROS_F127 = [MAYOR_ANA, SALDOS_ANA, MAYOR_ANA_GEN, SALDOS_ANA_GEN, RECUENTO_ANA]

#: Las columnas del mayor analítico completo, EN ORDEN (design §4).
COLUMNAS_MAYOR_ANA = [
    "apunte_analitico_id", "asiento_id", "tipo_asiento", "codigo_asiento", "posicion",
    "fecha", "ejercicio", "mes", "empresa_id", "centro_coste_id", "codigo_centro",
    "obra_id", "codigo_obra", "clave_obra", "cuenta_analitica_id",
    "codigo_cuenta_analitica", "descripcion_cuenta_analitica",
    "es_contrapartida_recurso", "concepto", "documento", "punteo", "debe", "haber",
    "importe", "saldo_acumulado", "apunte_id", "cuenta_id", "codigo_cuenta",
    "obra_imputada_id", "clave_obra_imputada", "restringido", "motivo_restriccion",
    "saldo_acumulado_visible",
]

#: Lo que el general NO publica (R14).
SOLO_COMPLETO = ["es_contrapartida_recurso", "restringido", "motivo_restriccion",
                 "saldo_acumulado_visible"]
COLUMNAS_MAYOR_ANA_GEN = [c for c in COLUMNAS_MAYOR_ANA if c not in SOLO_COMPLETO]

VENTANA = (
    "( PARTITION BY s.cuenta_analitica_id ORDER BY s.fecha, s.codigo_asiento, "
    "s.posicion, s.apunte_analitico_id )"
)

#: El conjunto CP (C3 con D7-b), tal cual lo llevan 08 y la guarda de 10.
CP_RECURSO = (
    "SELECT DISTINCT r.caaconide AS cuenta_analitica_id FROM raw.res r WHERE r.caaconide <> 0"
)
CENTROS_CP = (
    "SELECT DISTINCT caa.cenide AS centro_coste_id FROM raw.caa caa JOIN cp_recurso c "
    "ON c.cuenta_analitica_id = caa.ide WHERE caa.cenide <> 0"
)
CENTRO_CP = (
    "SELECT n.ide AS centro_coste_id FROM raw.cen n JOIN raw.con ccp ON ccp.ide = n.ide "
    f"WHERE ccp.cod = '{CODIGO_CENTRO_CONTRAPARTIDA}'"
)
CP = (
    "SELECT c.cuenta_analitica_id FROM cp_recurso c UNION SELECT a.cueide FROM raw.apa a "
    "JOIN raw.con asi ON asi.ide = a.conide JOIN raw.caa caa ON caa.ide = a.cueide "
    "JOIN centros_cp cc ON cc.centro_coste_id = caa.cenide "
    f"WHERE asi.tip = {TIPO_CON_ASIENTO_ANALITICO} AND COALESCE(a.hab, 0) <> 0 "
    "UNION SELECT caa.ide FROM raw.caa caa JOIN centro_cp k ON k.centro_coste_id = caa.cenide"
)


def _final(nombre: str, objeto: str) -> list[str]:
    return _consultas(nombre, objeto)[-1][1]


def _base() -> list[str]:
    """Las expresiones del CTE `base` (el único SELECT con `a.ide`)."""
    consultas = _consultas(MAYOR_ANA, f"{RESTR}.mayor_analitico")
    return next(items for _, items, _ in consultas if "a.ide AS apunte_analitico_id" in items)


# ===========================================================================
# R1, R2 · una fila por fila de raw.apa, con su guarda
# ===========================================================================


def test_f127_r1_el_completo_es_una_tabla_del_esquema_restringido() -> None:
    texto = _sql(MAYOR_ANA)
    assert texto.index(f"DROP TABLE IF EXISTS {RESTR}.mayor_analitico CASCADE;") < texto.index(
        f"CREATE TABLE {RESTR}.mayor_analitico AS"
    )
    assert f"ALTER TABLE {RESTR}.mayor_analitico ADD PRIMARY KEY (apunte_analitico_id);" in texto
    assert f"COMMENT ON TABLE {RESTR}.mayor_analitico IS" in texto
    assert "CREATE VIEW" not in texto.upper(), "materializada: el MCP corta a 30 s"


def test_f127_r1_sin_filtrar_ninguna_fila() -> None:
    """`raw.apa` entra en `base` sin WHERE y todo lo demás va con LEFT JOIN."""
    base = _cte(MAYOR_ANA, "base")
    assert "FROM raw.apa a LEFT JOIN raw.con asi ON asi.ide = a.conide" in base
    assert " WHERE " not in base and " JOIN " not in base.replace("LEFT JOIN", "")
    for cte, origen in (("marcados", "FROM base b "), ("clasificadas", "FROM marcados mk")):
        texto = _cte(MAYOR_ANA, cte)
        assert origen in texto
        assert " WHERE " not in texto and " GROUP BY " not in texto
        assert re.findall(r"(?<!LEFT) JOIN ", texto) == [], f"{cte}: un JOIN sería un filtro"
    final = _sql(MAYOR_ANA).split(f"CREATE TABLE {RESTR}.mayor_analitico AS", 1)[1].split(";")[0]
    cola = final.rsplit("FROM clasificadas s", 1)[1]
    assert cola.strip() == (
        "LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = s.centro_coste_id"
    )


@pytest.mark.parametrize(
    "union",
    [
        "LEFT JOIN raw.con ca ON ca.ide = b.cuenta_analitica_id",
        f"LEFT JOIN {RESTR}.mayor m ON m.apunte_id = b.apunte_id",
        "LEFT JOIN cp ON cp.cuenta_analitica_id = b.cuenta_analitica_id",
        "LEFT JOIN asientos_personal ap ON ap.asiento_id = b.asiento_id",
        "LEFT JOIN ana_obra ao ON ao.asiento_id = b.asiento_id",
    ],
)
def test_f127_r1_nada_multiplica(union: str) -> None:
    """Cada unión va por clave primaria (`raw.con`, el mayor) o contra un
    conjunto agrupado o DISTINCT (cp, asientos_personal, ana_obra)."""
    assert union in _cte(MAYOR_ANA, "marcados")


def test_f127_r1_los_conjuntos_unidos_no_repiten_clave() -> None:
    assert _cte(MAYOR_ANA, "cp_recurso").strip().startswith("SELECT DISTINCT ")
    assert " UNION " in _cte(MAYOR_ANA, "cp") and " UNION ALL " not in _cte(MAYOR_ANA, "cp")
    assert " GROUP BY m.asiento_id HAVING " in _cte(MAYOR_ANA, "asientos_personal")
    assert _cte(MAYOR_ANA, "ana_obra").strip().endswith(" GROUP BY a.conide")


def test_f127_r2_la_guarda_de_recuento() -> None:
    guarda = _guarda(MAYOR_ANA)
    assert f"SELECT count(*) INTO v_mayor FROM {RESTR}.mayor_analitico;" in guarda
    assert "SELECT count(*) INTO v_apa FROM raw.apa;" in guarda
    assert "IF v_mayor <> v_apa THEN RAISE EXCEPTION" in guarda
    mensaje = guarda.split("RAISE EXCEPTION", 1)[1].split("; END IF;", 1)[0]
    assert mensaje.count("%") == 2 and mensaje.rstrip().endswith("v_mayor, v_apa"), (
        "las dos cifras en el mensaje"
    )
    assert mensaje.strip().startswith("'mayor_analitico:"), "el sub-paso, en el mensaje"
    texto = _sql(MAYOR_ANA)
    assert texto.index("DO $$") > texto.index(f"CREATE TABLE {RESTR}.mayor_analitico AS")


# ===========================================================================
# R3, R4 · las columnas y de dónde sale cada una
# ===========================================================================


def test_f127_r3_columnas_en_orden() -> None:
    assert _columnas(MAYOR_ANA, f"{RESTR}.mayor_analitico") == COLUMNAS_MAYOR_ANA


@pytest.mark.parametrize(
    "expresion",
    [
        "a.ide AS apunte_analitico_id",
        "NULLIF(a.conide, 0) AS asiento_id",
        "asi.tip AS tipo_con",
        "asi.cod AS codigo_asiento",
        "a.pos AS posicion",
        "contabilidad.fn_fecha(a.fec) AS fecha",
        "EXTRACT(YEAR FROM contabilidad.fn_fecha(a.fec))::INT AS ejercicio",
        "EXTRACT(MONTH FROM contabilidad.fn_fecha(a.fec))::INT AS mes",
        "asi.emp AS empresa_id",
        "NULLIF(a.cenide, 0) AS centro_coste_id",
        "NULLIF(a.cueide, 0) AS cuenta_analitica_id",
        "a.res AS concepto",
        "a.doc AS documento",
        "a.pun AS punteo",
        "COALESCE(a.deb, 0)::NUMERIC(18, 2) AS debe",
        "COALESCE(a.hab, 0)::NUMERIC(18, 2) AS haber",
        "(COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2) AS importe",
        "NULLIF(a.apuide, 0) AS apunte_id",
    ],
)
def test_f127_r3_la_base_sale_de_apa_y_su_asiento(expresion: str) -> None:
    assert expresion in _base()


@pytest.mark.parametrize("nombre", FICHEROS_F127)
def test_f127_r3_sin_round_de_double(nombre: str) -> None:
    """`ROUND(double, 2)` no existe en PostgreSQL: se castea a NUMERIC."""
    assert "ROUND(" not in _sql(nombre).upper()


@pytest.mark.parametrize(
    "expresion",
    [
        "ca.cod AS codigo_cuenta_analitica",
        "ca.res AS descripcion_cuenta_analitica",
        "m.cuenta_id",
        "m.codigo_cuenta",
        "ao.obra_imputada_id",
        "ao.clave_obra_imputada",
    ],
)
def test_f127_r3_cuenta_analitica_y_apunte_financiero(expresion: str) -> None:
    assert expresion in _cte(MAYOR_ANA, "marcados")


def test_f127_r3_tipo_de_asiento_con_los_literales_del_dominio() -> None:
    assert (
        f"CASE WHEN s.tipo_con = {TIPO_CON_ASIENTO} THEN '{TIPO_ASIENTO_CONTABLE}' "
        f"WHEN s.tipo_con = {TIPO_CON_ASIENTO_ANALITICO} THEN '{TIPO_ASIENTO_ANALITICO}' "
        f"ELSE '{TIPO_ASIENTO_OTRO}' END AS tipo_asiento"
    ) in _final(MAYOR_ANA, f"{RESTR}.mayor_analitico")


@pytest.mark.parametrize(
    "expresion",
    [
        "cc.codigo_centro",
        "cc.obra_id",
        "cc.codigo_obra",
        "cc.empresa::TEXT || '-' || cc.codigo_obra AS clave_obra",
        "s.es_contrapartida AS es_contrapartida_recurso",
    ],
)
def test_f127_r3_centro_obra_y_marca_de_cp(expresion: str) -> None:
    assert expresion in _final(MAYOR_ANA, f"{RESTR}.mayor_analitico")


@pytest.mark.parametrize("nombre", FICHEROS_F127)
def test_f127_r4_no_lee_los_campos_vetados_de_apa(nombre: str) -> None:
    """La obra sale solo del centro (`maestro.centros_coste`)."""
    vetados = re.findall(r"\b\w+\.(obride|obr|ori|canal|delo|del)\b", _sql(nombre))
    assert vetados == [], f"{nombre} lee {vetados}"


def test_f127_r4_la_obra_solo_por_el_centro() -> None:
    assert set(re.findall(r"maestro\.(\w+)", _sql(MAYOR_ANA))) == {"centros_coste"}
    assert (
        "LEFT JOIN maestro.centros_coste o ON o.centro_coste_id = NULLIF(a.cenide, 0)"
        in _cte(MAYOR_ANA, "ana_obra")
    )


# ===========================================================================
# R5 · el acumulado
# ===========================================================================


def test_f127_r5_saldo_acumulado_por_cuenta_analitica() -> None:
    assert (
        f"SUM(s.importe) OVER {VENTANA}::NUMERIC(18, 2) AS saldo_acumulado"
    ) in _final(MAYOR_ANA, f"{RESTR}.mayor_analitico")


# ===========================================================================
# R6 · la obra imputada de un asiento ANALITICO (D4)
# ===========================================================================


def test_f127_r6_la_obra_imputada_es_la_unica_de_las_filas_no_cp() -> None:
    cte = _cte(MAYOR_ANA, "ana_obra")
    assert (
        "CASE WHEN COUNT(DISTINCT o.obra_id) = 1 THEN MAX(o.obra_id) END AS obra_imputada_id"
    ) in cte
    assert (
        "CASE WHEN COUNT(DISTINCT o.obra_id) = 1 THEN MAX(o.empresa::TEXT || '-' || "
        "o.codigo_obra) END AS clave_obra_imputada"
    ) in cte
    assert "JOIN raw.con asi ON asi.ide = a.conide" in cte
    assert "LEFT JOIN cp ON cp.cuenta_analitica_id = a.cueide" in cte
    assert (
        f"WHERE asi.tip = {TIPO_CON_ASIENTO_ANALITICO} AND cp.cuenta_analitica_id IS NULL "
        "GROUP BY a.conide"
    ) in cte


# ===========================================================================
# R7-R11 · el criterio en SQL, con los literales del dominio
# ===========================================================================


@pytest.mark.parametrize(
    ("cte", "texto"),
    [("cp_recurso", CP_RECURSO), ("centros_cp", CENTROS_CP), ("centro_cp", CENTRO_CP),
     ("cp", CP)],
)
def test_f127_r7_c3_el_conjunto_cp_con_d7(cte: str, texto: str) -> None:
    assert _cte(MAYOR_ANA, cte).strip() == texto


def test_f127_r7_c2_el_asiento_de_personal() -> None:
    assert _cte(MAYOR_ANA, "asientos_personal").strip() == (
        f"SELECT m.asiento_id FROM {RESTR}.mayor m WHERE m.asiento_id IS NOT NULL "
        "GROUP BY m.asiento_id HAVING bool_and(m.clase_asiento = 'NORMAL') "
        "AND bool_or(m.restringido)"
    )


@pytest.mark.parametrize(
    "expresion",
    [
        "(cp.cuenta_analitica_id IS NOT NULL) AS es_contrapartida",
        "(b.apunte_id IS NOT NULL AND m.apunte_id IS NULL) AS es_apunte_sin_resolver",
        "COALESCE(m.restringido, FALSE) AS es_apunte_restringido",
        "(ap.asiento_id IS NOT NULL) AS es_asiento_personal",
    ],
)
def test_f127_r7_r9_las_cuatro_marcas_nunca_nulas(expresion: str) -> None:
    assert expresion in _cte(MAYOR_ANA, "marcados")


def test_f127_r7_restringido_es_cualquiera_de_las_cuatro() -> None:
    assert (
        "(mk.es_contrapartida OR mk.es_apunte_sin_resolver OR mk.es_apunte_restringido "
        "OR mk.es_asiento_personal) AS restringido"
    ) in _cte(MAYOR_ANA, "clasificadas")
    assert "s.restringido" in _final(MAYOR_ANA, f"{RESTR}.mayor_analitico")


def test_f127_r8_motivo_en_su_precedencia() -> None:
    assert (
        f"CASE WHEN s.es_contrapartida THEN '{MOTIVO_CONTRAPARTIDA}' "
        f"WHEN s.es_apunte_sin_resolver THEN '{MOTIVO_APUNTE_SIN_RESOLVER}' "
        f"WHEN s.es_apunte_restringido THEN '{MOTIVO_APUNTE_RESTRINGIDO}' "
        f"WHEN s.es_asiento_personal THEN '{MOTIVO_ASIENTO_PERSONAL}' END AS motivo_restriccion"
    ) in _final(MAYOR_ANA, f"{RESTR}.mayor_analitico")


@pytest.mark.parametrize("nombre", FICHEROS_F127)
def test_f127_r10_los_literales_del_sql_son_los_del_dominio(nombre: str) -> None:
    """Todo `tip = N` es 20 o 32, todo literal en mayúsculas es un motivo o un
    tipo del dominio, y ningún fichero de F-127 lleva la regex de cuentas ni el
    patrón de nómina: hereda el criterio del mayor completo, no lo recalcula."""
    conocidos = {
        MOTIVO_CONTRAPARTIDA, MOTIVO_APUNTE_SIN_RESOLVER, MOTIVO_APUNTE_RESTRINGIDO,
        MOTIVO_ASIENTO_PERSONAL, TIPO_ASIENTO_CONTABLE, TIPO_ASIENTO_ANALITICO,
        TIPO_ASIENTO_OTRO, "NORMAL",
    }
    sql = re.sub(r"COMMENT ON TABLE .*? IS '[^']*';", "", _sql(nombre))
    tips = set(re.findall(r"tip(?:o_con)? = (\d+)", sql))
    assert tips <= {str(TIPO_CON_ASIENTO), str(TIPO_CON_ASIENTO_ANALITICO)}, tips
    citados = set(re.findall(r"'([A-Z_]{4,})'", sql))
    assert citados <= conocidos, f"literales {citados - conocidos}"
    cortos = set(re.findall(r"= '([A-Z]{1,3})'", sql))
    assert cortos <= {CODIGO_CENTRO_CONTRAPARTIDA}, f"códigos {cortos}"
    if nombre in (MAYOR_ANA, MAYOR_ANA_GEN):
        assert f"ccp.cod = '{CODIGO_CENTRO_CONTRAPARTIDA}'" in sql, "D9: el centro CP"
    assert REGEX_CUENTA_RESTRINGIDA not in sql and PATRON_CONCEPTO_NOMINA not in sql
    if nombre in (MAYOR_ANA, MAYOR_ANA_GEN):
        assert f"tip = {TIPO_CON_ASIENTO_ANALITICO}" in sql, "D7-b mira los asientos ANALITICO"


def test_f127_r11_el_acumulado_visible() -> None:
    assert _final(MAYOR_ANA, f"{RESTR}.mayor_analitico")[-1] == (
        "CASE WHEN s.restringido THEN NULL ELSE SUM(s.importe) FILTER ( WHERE NOT s.restringido ) "
        f"OVER {VENTANA} END::NUMERIC(18, 2) AS saldo_acumulado_visible"
    )


@pytest.mark.parametrize(
    "indice",
    [
        "idx_con_mana_cuenta_fecha ON {e}.mayor_analitico (cuenta_analitica_id, fecha);",
        "idx_con_mana_empresa_cuenta_fecha ON {e}.mayor_analitico "
        "(empresa_id, codigo_cuenta_analitica, fecha);",
        "idx_con_mana_obra ON {e}.mayor_analitico (obra_id);",
        "idx_con_mana_obra_imputada ON {e}.mayor_analitico (obra_imputada_id);",
        "idx_con_mana_apunte ON {e}.mayor_analitico (apunte_id);",
        "idx_con_mana_asiento ON {e}.mayor_analitico (asiento_id);",
    ],
)
def test_f127_r1_indices_del_completo(indice: str) -> None:
    assert "CREATE INDEX " + indice.format(e=RESTR) in _sql(MAYOR_ANA)


def test_f127_r11_indice_parcial_de_restringidos() -> None:
    assert (
        f"CREATE INDEX idx_con_mana_restringido ON {RESTR}.mayor_analitico (restringido) "
        "WHERE restringido;"
    ) in _sql(MAYOR_ANA)


@pytest.mark.parametrize("nombre", FICHEROS_F127)
def test_f127_ficheros_con_cabecera_ruta_y_sin_permisos(nombre: str) -> None:
    assert (DIR_CON / nombre).exists(), f"falta {nombre}"
    assert _crudo(nombre).splitlines()[0] == (
        f"-- etl_sigrid/infrastructure/postgres/sql/contabilidad/{nombre}"
    )
    sql = _sql(nombre).upper()
    assert "GRANT " not in sql and "REVOKE " not in sql, "los permisos los da apply_grants"


# ===========================================================================
# R12 · los saldos por cuenta analítica, centro y mes (completos)
# ===========================================================================

COLUMNAS_SALDOS_ANA = [
    "cuenta_analitica_id", "centro_coste_id", "empresa_id", "ejercicio", "mes",
    "num_apuntes", "debe", "haber", "importe", "saldo_acumulado",
]
CLAVE_SALDOS_ANA = "(cuenta_analitica_id, centro_coste_id, empresa_id, ejercicio, mes)"
AGRUPACION_ANA = (
    "GROUP BY COALESCE(m.cuenta_analitica_id, 0), COALESCE(m.centro_coste_id, 0), "
    "m.empresa_id, m.ejercicio, m.mes"
)
VENTANA_MES = (
    "SUM(s.importe) OVER ( PARTITION BY s.cuenta_analitica_id, s.centro_coste_id, "
    "s.empresa_id ORDER BY s.ejercicio, s.mes )::NUMERIC(18, 2) AS saldo_acumulado"
)


def test_f127_r12_saldos_completos_desde_el_mayor_analitico() -> None:
    texto = _sql(SALDOS_ANA)
    assert texto.index(
        f"DROP TABLE IF EXISTS {RESTR}.saldos_cuenta_analitica_mes CASCADE;"
    ) < texto.index(f"CREATE TABLE {RESTR}.saldos_cuenta_analitica_mes AS")
    assert f"COMMENT ON TABLE {RESTR}.saldos_cuenta_analitica_mes IS" in texto
    assert (
        f"ALTER TABLE {RESTR}.saldos_cuenta_analitica_mes ADD PRIMARY KEY {CLAVE_SALDOS_ANA};"
    ) in texto
    leidas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+\.\w+)", texto))
    assert leidas == {f"{RESTR}.mayor_analitico"}, f"09 lee {leidas}"


def test_f127_r12_columnas_y_agregados() -> None:
    assert _columnas(SALDOS_ANA, f"{RESTR}.saldos_cuenta_analitica_mes") == COLUMNAS_SALDOS_ANA
    mensual = _cte(SALDOS_ANA, "mensual")
    for expresion in (
        "COALESCE(m.cuenta_analitica_id, 0) AS cuenta_analitica_id",
        "COALESCE(m.centro_coste_id, 0) AS centro_coste_id",
        "COUNT(*) AS num_apuntes",
        "SUM(m.debe)::NUMERIC(18, 2) AS debe",
        "SUM(m.haber)::NUMERIC(18, 2) AS haber",
        "SUM(m.importe)::NUMERIC(18, 2) AS importe",
    ):
        assert expresion in mensual, f"falta «{expresion}»"
    assert mensual.strip().endswith(f"FROM {RESTR}.mayor_analitico m {AGRUPACION_ANA}")
    assert " WHERE " not in mensual and "FILTER" not in mensual, "el completo no filtra nada"


def test_f127_r12_acumulado_a_fin_de_mes() -> None:
    assert VENTANA_MES in _final(SALDOS_ANA, f"{RESTR}.saldos_cuenta_analitica_mes")


def test_f127_r12_sin_columnas_por_clase() -> None:
    """No hay cierres ni aperturas en la analítica: ni importe_saldo ni clase."""
    texto = _sql(SALDOS_ANA)
    for prohibido in ("clase_asiento", "importe_saldo", "importe_apertura", "importe_cierre"):
        assert prohibido not in texto, prohibido


# ===========================================================================
# R14, R15 · el mayor analítico general y su guarda
# ===========================================================================


def test_f127_r14_el_general_son_los_no_restringidos() -> None:
    consultas = _consultas(MAYOR_ANA_GEN, "contabilidad.mayor_analitico")
    assert len(consultas) == 1
    _, items, clausulas = consultas[0]
    assert _columnas(MAYOR_ANA_GEN, "contabilidad.mayor_analitico") == COLUMNAS_MAYOR_ANA_GEN
    assert clausulas == ["WHERE NOT r.restringido"]
    assert f"FROM {RESTR}.mayor_analitico r WHERE NOT r.restringido" in _sql(MAYOR_ANA_GEN)
    copiadas = [i for i in items if i != "r.saldo_acumulado_visible AS saldo_acumulado"]
    assert copiadas == [f"r.{c}" for c in COLUMNAS_MAYOR_ANA_GEN if c != "saldo_acumulado"]
    assert "r.saldo_acumulado_visible AS saldo_acumulado" in items


def test_f127_r14_tabla_idempotente_con_indices() -> None:
    texto = _sql(MAYOR_ANA_GEN)
    assert texto.index("DROP TABLE IF EXISTS contabilidad.mayor_analitico CASCADE;") < texto.index(
        "CREATE TABLE contabilidad.mayor_analitico AS"
    )
    assert "COMMENT ON TABLE contabilidad.mayor_analitico IS" in texto
    assert "ALTER TABLE contabilidad.mayor_analitico ADD PRIMARY KEY (apunte_analitico_id);" in texto
    for indice in (
        "idx_con_mana_cuenta_fecha ON contabilidad.mayor_analitico (cuenta_analitica_id, fecha);",
        "idx_con_mana_empresa_cuenta_fecha ON contabilidad.mayor_analitico "
        "(empresa_id, codigo_cuenta_analitica, fecha);",
        "idx_con_mana_obra ON contabilidad.mayor_analitico (obra_id);",
        "idx_con_mana_obra_imputada ON contabilidad.mayor_analitico (obra_imputada_id);",
        "idx_con_mana_apunte ON contabilidad.mayor_analitico (apunte_id);",
        "idx_con_mana_asiento ON contabilidad.mayor_analitico (asiento_id);",
    ):
        assert "CREATE INDEX " + indice in texto, indice
    assert "WHERE restringido;" not in texto, "sin índice parcial: aquí no hay restringidas"


def test_f127_r15_guarda_sin_cp() -> None:
    """La guarda recalcula el conjunto CP IGUAL que 08 (con D7-b), desde raw."""
    guarda = _guarda(MAYOR_ANA_GEN)
    for cte, texto in (("cp_recurso", CP_RECURSO), ("centros_cp", CENTROS_CP),
                       ("centro_cp", CENTRO_CP), ("cp", CP)):
        assert f"{cte} AS ( {texto} )" in guarda, f"la guarda no recalcula {cte} como 08"
    assert (
        "SELECT count(*) INTO v_cp FROM contabilidad.mayor_analitico g "
        "JOIN cp ON cp.cuenta_analitica_id = g.cuenta_analitica_id;"
    ) in guarda
    assert "IF v_cp <> 0 THEN RAISE EXCEPTION" in guarda


def test_f127_r15_guarda_sin_apunte_restringido_ni_sin_resolver() -> None:
    guarda = _guarda(MAYOR_ANA_GEN)
    assert (
        "SELECT count(*) INTO v_apunte FROM contabilidad.mayor_analitico g "
        "WHERE g.apunte_id IS NOT NULL AND NOT EXISTS ( SELECT 1 FROM "
        f"{RESTR}.mayor m WHERE m.apunte_id = g.apunte_id AND NOT m.restringido );"
    ) in guarda
    assert "IF v_apunte <> 0 THEN RAISE EXCEPTION" in guarda


def test_f127_r15_d9_guarda_sin_asientos_de_personal() -> None:
    """Enmienda 2026-11-21 (D9, cambio 3 de la review): la cuarta comprobación,
    con el mismo criterio de asiento de personal que 08 (C2)."""
    guarda = _guarda(MAYOR_ANA_GEN)
    assert (
        "SELECT count(*) INTO v_personal FROM contabilidad.mayor_analitico g "
        "WHERE g.asiento_id IN ( SELECT m.asiento_id FROM "
        f"{RESTR}.mayor m WHERE m.asiento_id IS NOT NULL GROUP BY m.asiento_id "
        "HAVING bool_and(m.clase_asiento = 'NORMAL') AND bool_or(m.restringido) );"
    ) in guarda
    assert "IF v_personal <> 0 THEN RAISE EXCEPTION" in guarda


def test_f127_r15_guarda_general_mas_restringidas_igual_a_completo() -> None:
    guarda = _guarda(MAYOR_ANA_GEN)
    assert "SELECT count(*) INTO v_general FROM contabilidad.mayor_analitico;" in guarda
    assert (
        "SELECT count(*), count(*) FILTER (WHERE restringido) INTO v_completo, v_restringidas "
        f"FROM {RESTR}.mayor_analitico;"
    ) in guarda
    assert "IF v_general + v_restringidas <> v_completo THEN RAISE EXCEPTION" in guarda
    texto = _sql(MAYOR_ANA_GEN)
    assert texto.index("DO $$") > texto.index("CREATE TABLE contabilidad.mayor_analitico AS")
    for mensaje in re.findall(r"RAISE EXCEPTION '([^']*)'", guarda):
        assert mensaje.startswith("mayor_analitico_general:"), mensaje


def test_f127_r15_la_tabla_solo_lee_el_completo() -> None:
    antes = _sql(MAYOR_ANA_GEN).split("DO $$")[0]
    leidas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+\.\w+)", antes))
    assert leidas == {f"{RESTR}.mayor_analitico"}, leidas


# ===========================================================================
# R16 · los saldos generales, solo de lo visible
# ===========================================================================


def test_f127_r16_saldos_generales_solo_de_lo_visible() -> None:
    mensual = _cte(SALDOS_ANA_GEN, "mensual")
    assert mensual.strip().endswith(
        f"FROM {RESTR}.mayor_analitico m {AGRUPACION_ANA} "
        "HAVING COUNT(*) FILTER (WHERE NOT m.restringido) > 0"
    )
    for expresion in (
        "COUNT(*) FILTER (WHERE NOT m.restringido) AS num_apuntes",
        "SUM(m.debe) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2) AS debe",
        "SUM(m.haber) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2) AS haber",
        "SUM(m.importe) FILTER (WHERE NOT m.restringido)::NUMERIC(18, 2) AS importe",
        "COUNT(*) FILTER (WHERE m.restringido) AS num_apuntes_restringidos",
    ):
        assert expresion in mensual, f"falta «{expresion}»"
    for agregado in re.findall(r"SUM\([^)]*\)(?: FILTER \([^)]*\))?", mensual):
        assert "NOT m.restringido" in agregado, f"agregado sin filtrar: {agregado}"


def test_f127_r16_columnas_recuento_al_final() -> None:
    assert _columnas(SALDOS_ANA_GEN, "contabilidad.saldos_cuenta_analitica_mes") == (
        [*COLUMNAS_SALDOS_ANA, "num_apuntes_restringidos", "incompleto"]
    )
    final = _final(SALDOS_ANA_GEN, "contabilidad.saldos_cuenta_analitica_mes")
    assert "s.num_apuntes_restringidos > 0 AS incompleto" in final
    assert VENTANA_MES in final
    texto = _sql(SALDOS_ANA_GEN)
    assert (
        f"ALTER TABLE contabilidad.saldos_cuenta_analitica_mes ADD PRIMARY KEY {CLAVE_SALDOS_ANA};"
    ) in texto
    assert texto.index(
        "DROP TABLE IF EXISTS contabilidad.saldos_cuenta_analitica_mes CASCADE;"
    ) < texto.index("CREATE TABLE contabilidad.saldos_cuenta_analitica_mes AS")
    assert "COMMENT ON TABLE contabilidad.saldos_cuenta_analitica_mes IS" in texto


# ===========================================================================
# R17 · cuánto falta, sin importes
# ===========================================================================


def test_f127_r17_recuentos_por_motivo_sin_importes() -> None:
    consultas = _consultas(RECUENTO_ANA, "contabilidad.apuntes_analiticos_restringidos_mes")
    assert len(consultas) == 1
    _, items, clausulas = consultas[0]
    assert items == [
        "m.empresa_id", "m.ejercicio", "m.mes",
        "COUNT(*) AS num_apuntes", "COUNT(DISTINCT m.asiento_id) AS num_asientos",
        f"COUNT(*) FILTER (WHERE m.motivo_restriccion = '{MOTIVO_CONTRAPARTIDA}') AS num_contrapartida",
        f"COUNT(*) FILTER (WHERE m.motivo_restriccion = '{MOTIVO_APUNTE_RESTRINGIDO}') "
        "AS num_apunte_restringido",
        f"COUNT(*) FILTER (WHERE m.motivo_restriccion = '{MOTIVO_ASIENTO_PERSONAL}') "
        "AS num_asiento_personal",
        f"COUNT(*) FILTER (WHERE m.motivo_restriccion = '{MOTIVO_APUNTE_SIN_RESOLVER}') "
        "AS num_apunte_sin_resolver",
    ]
    assert clausulas == ["WHERE m.restringido", "GROUP BY m.empresa_id, m.ejercicio, m.mes"]
    assert f"FROM {RESTR}.mayor_analitico m" in _sql(RECUENTO_ANA)


def test_f127_r17_ni_debe_ni_haber_ni_importe() -> None:
    """D5 de F-135: el importe restringido por mes sería la masa salarial."""
    sql = _sql(RECUENTO_ANA).split("COMMENT ON")[0]
    for prohibido in ("debe", "haber", "importe", "SUM(", "saldo"):
        assert prohibido not in sql, f"12 nombra {prohibido}"
    assert (
        "ALTER TABLE contabilidad.apuntes_analiticos_restringidos_mes "
        "ADD PRIMARY KEY (empresa_id, ejercicio, mes);"
    ) in sql
    assert sql.index(
        "DROP TABLE IF EXISTS contabilidad.apuntes_analiticos_restringidos_mes CASCADE;"
    ) < sql.index("CREATE TABLE contabilidad.apuntes_analiticos_restringidos_mes AS")
    assert "COMMENT ON TABLE contabilidad.apuntes_analiticos_restringidos_mes IS" in _sql(
        RECUENTO_ANA
    )


@pytest.mark.parametrize("nombre", [SALDOS_ANA_GEN, RECUENTO_ANA])
def test_f127_r16_r17_las_generales_solo_leen_el_completo(nombre: str) -> None:
    leidas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+\.\w+)", _sql(nombre)))
    assert leidas == {f"{RESTR}.mayor_analitico"}, f"{nombre} lee {leidas}"


# ===========================================================================
# R18 · los cinco sub-pasos, detrás de los ocho de F-056/F-135
# ===========================================================================

#: Los ocho de hoy, escritos A MANO: F-127 no cambia ninguno.
OCHO_DE_ANTES = [
    ("setup", "00_setup.sql", None, None),
    ("plan_cuentas", "01_plan_cuentas.sql", RESTR, "plan_cuentas"),
    ("mayor", "02_mayor.sql", RESTR, "mayor"),
    ("saldos_cuenta_mes", "03_saldos_cuenta_mes.sql", RESTR, "saldos_cuenta_mes"),
    ("plan_cuentas_general", "04_plan_cuentas_general.sql", "contabilidad", "plan_cuentas"),
    ("mayor_general", "05_mayor_general.sql", "contabilidad", "mayor"),
    ("saldos_general", "06_saldos_general.sql", "contabilidad", "saldos_cuenta_mes"),
    ("apuntes_restringidos_mes", "07_apuntes_restringidos_mes.sql", "contabilidad",
     "apuntes_restringidos_mes"),
]
CINCO_DE_F127 = [
    ("mayor_analitico", MAYOR_ANA, RESTR, "mayor_analitico"),
    ("saldos_analitica", SALDOS_ANA, RESTR, "saldos_cuenta_analitica_mes"),
    ("mayor_analitico_general", MAYOR_ANA_GEN, "contabilidad", "mayor_analitico"),
    ("saldos_analitica_general", SALDOS_ANA_GEN, "contabilidad", "saldos_cuenta_analitica_mes"),
    ("apuntes_analiticos_restringidos_mes", RECUENTO_ANA, "contabilidad",
     "apuntes_analiticos_restringidos_mes"),
]


def _declarados() -> list[tuple[str, str, str | None, str | None]]:
    from etl_sigrid.application.steps import build_contabilidad_step

    return [
        (s.name, s.sql_file, s.target_schema, s.target_table)
        for s in build_contabilidad_step.SUB_PASOS
    ]


def test_f127_r18_los_ocho_de_antes_no_cambian() -> None:
    assert _declarados()[:8] == OCHO_DE_ANTES


def test_f127_r18_los_cinco_nuevos_al_final_y_en_orden() -> None:
    assert _declarados()[8:] == CINCO_DE_F127
    for _, fichero, _, _ in _declarados():
        assert (DIR_CON / fichero).exists(), f"{fichero} declarado y no existe"
    assert sorted(f.name for f in DIR_CON.glob("*.sql")) == [d[1] for d in _declarados()], (
        "los trece ficheros del directorio son los trece sub-pasos"
    )


def test_f127_r18_depends_on_no_cambia() -> None:
    from types import SimpleNamespace

    from etl_sigrid.application.steps.build_contabilidad_step import BuildContabilidadStep

    paso = BuildContabilidadStep(SimpleNamespace())
    assert paso.depends_on == ["ingest_raw"]
    assert (paso.name, paso.stage) == ("build_contabilidad", "build_aux")


def test_f127_r18_el_paso_ejecuta_los_trece_y_cuenta(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from etl_sigrid.application.steps import build_contabilidad_step
    from etl_sigrid.domain.entities import StepStatus

    class _PgFalso:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []
            self.contados: list[tuple[str, str]] = []

        def execute_sql_file(self, path) -> None:
            self.ejecutados.append(path.name)

        def count_rows(self, schema: str, table: str) -> int:
            self.contados.append((schema, table))
            return 1

    pg = _PgFalso()
    monkeypatch.setattr(build_contabilidad_step, "build_postgres_client", lambda _s: pg)
    resultado = build_contabilidad_step.BuildContabilidadStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == [d[1] for d in OCHO_DE_ANTES + CINCO_DE_F127]
    assert pg.contados[-5:] == [(d[2], d[3]) for d in CINCO_DE_F127]
    assert resultado.rows_processed == 12


def test_f127_r18_el_docstring_cita_los_trece() -> None:
    from etl_sigrid.application.steps import build_contabilidad_step

    doc = build_contabilidad_step.__doc__ or ""
    for _, fichero, _, _ in OCHO_DE_ANTES + CINCO_DE_F127:
        assert fichero in doc, f"el docstring no cita {fichero}"
    assert "F-127" in doc
    cabecera = _crudo("00_setup.sql")
    for fichero in FICHEROS_F127:
        assert fichero in cabecera, f"la cabecera de 00_setup.sql no cita {fichero}"


# ===========================================================================
# R19 · ningún objeto del mayor analítico para el perfil restringido ni el de
# postventa (D3: por el veto de esquema de F-146, no por la lista de excluidos)
# ===========================================================================


def _lista(texto: str) -> list[str]:
    return [e.strip() for e in texto.split(",") if e.strip()]


@pytest.mark.parametrize("perfil", ["DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS",
                                    "DEFAULT_PERFIL_POSTVENTA_SCHEMAS"])
def test_f127_r19_ni_contabilidad_ni_la_restringida_en_los_perfiles(perfil: str) -> None:
    import config.settings as ajustes

    esquemas = _lista(getattr(ajustes, perfil))
    assert esquemas, f"{perfil} vacía: el test no vería nada"
    assert "contabilidad" not in esquemas and RESTR not in esquemas, (
        f"{perfil} lee {sorted({'contabilidad', RESTR} & set(esquemas))}"
    )


def test_f127_r19_la_lista_de_excluidos_sigue_vacia() -> None:
    """D3: añadir el mayor analítico aquí haría FALLAR la nocturna (R7 de F-141
    rechaza excluir un objeto de un esquema que el perfil no ve)."""
    from pathlib import Path

    import config.settings as ajustes

    assert ajustes.DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES == ""
    fuente = Path(ajustes.__file__).read_text(encoding="utf-8")
    assert re.search(
        r"perfil_restringido_excluded_tables: str = Field\(\s+"
        r"DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES,",
        fuente,
    ), "el campo toma su valor por defecto de la constante vacía"


def test_f127_r19_el_completo_vive_en_un_esquema_vetado_y_restringido() -> None:
    from config.settings import (
        DEFAULT_CONSUMPTION_SCHEMAS,
        DEFAULT_RESTRICTED_SCHEMAS,
        DEFAULT_VETOED_SCHEMAS,
    )

    assert RESTR in _lista(DEFAULT_VETOED_SCHEMAS)
    assert RESTR in _lista(DEFAULT_RESTRICTED_SCHEMAS)
    assert RESTR not in _lista(DEFAULT_CONSUMPTION_SCHEMAS)
    assert "contabilidad" in _lista(DEFAULT_CONSUMPTION_SCHEMAS), "el estándar lee el general"


def test_f127_r19_el_comentario_del_perfil_dice_donde_nacio_f127() -> None:
    from pathlib import Path

    import config.settings as ajustes

    fuente = Path(ajustes.__file__).read_text(encoding="utf-8")
    bloque = fuente.split("DEFAULT_PERFIL_RESTRINGIDO_GROUP =", 1)[0].rsplit(
        "# El perfil RESTRINGIDO del MCP", 1
    )[1]
    assert "F-127 nació en `contabilidad`" in bloque, "D3: el comentario dice dónde nació"
    assert "si nace ahí" not in bloque, "ya no es una hipótesis"


# ===========================================================================
# R21-R23 · el diccionario
# ===========================================================================

DIR_DICC = DIR_CON.parents[4] / "config" / "diccionario"

#: Las cinco fichas: (fichero, objeto, SQL, columnas, clave).
FICHAS_F127 = [
    ("contabilidad_restringida.yaml", "mayor_analitico", MAYOR_ANA, COLUMNAS_MAYOR_ANA,
     ["apunte_analitico_id"]),
    ("contabilidad_restringida.yaml", "saldos_cuenta_analitica_mes", SALDOS_ANA,
     COLUMNAS_SALDOS_ANA, ["cuenta_analitica_id", "centro_coste_id", "empresa_id",
                           "ejercicio", "mes"]),
    ("contabilidad.yaml", "mayor_analitico", MAYOR_ANA_GEN, COLUMNAS_MAYOR_ANA_GEN,
     ["apunte_analitico_id"]),
    ("contabilidad.yaml", "saldos_cuenta_analitica_mes", SALDOS_ANA_GEN,
     [*COLUMNAS_SALDOS_ANA, "num_apuntes_restringidos", "incompleto"],
     ["cuenta_analitica_id", "centro_coste_id", "empresa_id", "ejercicio", "mes"]),
    ("contabilidad.yaml", "apuntes_analiticos_restringidos_mes", RECUENTO_ANA,
     ["empresa_id", "ejercicio", "mes", "num_apuntes", "num_asientos", "num_contrapartida",
      "num_apunte_restringido", "num_asiento_personal", "num_apunte_sin_resolver"],
     ["empresa_id", "ejercicio", "mes"]),
]


def _dicc(nombre: str) -> dict:
    import yaml

    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _ficha(fichero: str, objeto: str) -> dict:
    return _dicc(fichero)["objetos"][objeto]


def _texto_ficha(fichero: str, objeto: str) -> str:
    import yaml

    return yaml.safe_dump(_ficha(fichero, objeto), allow_unicode=True, width=10_000)


@pytest.mark.parametrize(
    ("fichero", "objeto", "sql", "columnas", "clave"), FICHAS_F127,
    ids=[f"{f.split('.')[0]}.{o}" for f, o, *_ in FICHAS_F127],
)
def test_f127_r21_ficha_con_las_columnas_del_sql(
    fichero: str, objeto: str, sql: str, columnas: list[str], clave: list[str]
) -> None:
    ficha = _ficha(fichero, objeto)
    esquema = fichero.removesuffix(".yaml")
    assert list(ficha["columnas"]) == columnas == _columnas(sql, f"{esquema}.{objeto}")
    assert ficha["clave_negocio"] == clave
    assert (ficha["tipo"], ficha["paso_etl"], ficha["refresco"]) == (
        "tabla", "build_contabilidad", "nocturno",
    )
    assert ficha["consumo_recomendado"] is True and ficha["ejemplos_preguntas"]
    for columna, datos in ficha["columnas"].items():
        assert datos.get("significado"), f"{esquema}.{objeto}.{columna} sin significado"


@pytest.mark.parametrize(
    ("fichero", "objeto"), [(f, o) for f, o, *_ in FICHAS_F127],
    ids=[f"{f.split('.')[0]}.{o}" for f, o, *_ in FICHAS_F127],
)
def test_f127_r21_cada_ficha_empieza_por_su_aviso_de_acceso(fichero: str, objeto: str) -> None:
    descripcion = _ficha(fichero, objeto)["descripcion"]
    if fichero == "contabilidad_restringida.yaml":
        assert descripcion.startswith("**ACCESO RESTRINGIDO: solo el perfil total del MCP.**")
        assert "sigrid_dm_autorizado_ro" in descripcion
    else:
        assert descripcion.startswith("**No disponible para el perfil restringido**")


def _relaciones(fichero: str, objeto: str) -> set[tuple[str, str, str]]:
    return {
        (r["de"], r["a"], r["cardinalidad"]) for r in _ficha(fichero, objeto)["relaciones"]
    }


def test_f127_r21_relaciones_del_completo() -> None:
    assert _relaciones("contabilidad_restringida.yaml", "mayor_analitico") >= {
        ("cuenta_analitica_id", "maestro.cuentas_analiticas.cuenta_analitica_id", "N:1"),
        ("centro_coste_id", "maestro.centros_coste.centro_coste_id", "N:1"),
        ("obra_id", "maestro.obras.obra_id", "N:1"),
        ("obra_imputada_id", "maestro.obras.obra_id", "N:1"),
        ("apunte_id", f"{RESTR}.mayor.apunte_id", "N:1"),
        ("cuenta_analitica_id", "personal.recursos.cuenta_analitica_contrapartida_id", "N:N"),
    }
    assert _relaciones("contabilidad_restringida.yaml", "saldos_cuenta_analitica_mes") >= {
        ("cuenta_analitica_id", "maestro.cuentas_analiticas.cuenta_analitica_id", "N:1"),
    }


def test_f127_r21_relaciones_del_general() -> None:
    relaciones = _relaciones("contabilidad.yaml", "mayor_analitico")
    assert relaciones >= {
        ("cuenta_analitica_id", "maestro.cuentas_analiticas.cuenta_analitica_id", "N:1"),
        ("centro_coste_id", "maestro.centros_coste.centro_coste_id", "N:1"),
        ("obra_id", "maestro.obras.obra_id", "N:1"),
        ("apunte_id", "contabilidad.mayor.apunte_id", "N:1"),
    }
    assert not any(RESTR in a or "personal." in a for _, a, _ in relaciones), (
        "el general no señala al completo ni a las CP de `personal`"
    )


def test_f127_r21_version_del_diccionario() -> None:
    assert _dicc("00_global.yaml")["version"] == 81, "F-104 publicó la 80; F-127 sube a 81"


def test_f127_r21_el_diccionario_del_arbol_valida() -> None:
    from etl_sigrid.domain.diccionario import formatear_errores, validar
    from tests.test_f006_frescura import PASOS_NOCTURNOS
    from tests.test_f006_publicacion import DIR_DICCIONARIO, cargar_diccionario

    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    errores = validar(dicc, PASOS_NOCTURNOS)
    assert not errores, formatear_errores(errores)
    nombres = {f.nombre for f in dicc.fichas}
    for fichero, objeto, *_ in FICHAS_F127:
        assert f"{fichero.removesuffix('.yaml')}.{objeto}" in nombres


def test_f127_r22_las_fichas_dicen_las_cuatro_cosas() -> None:
    completo = _texto_ficha("contabilidad_restringida.yaml", "mayor_analitico")
    general = _texto_ficha("contabilidad.yaml", "mayor_analitico")
    for texto in (completo, general):
        assert "debe - haber" in texto and "0 de 639.034" in texto, "el saldo SÍ se suma"
        assert "No se suma con `contabilidad" in texto, "el analítico no se suma con el mayor"
        assert "marzo de 2026" in texto and "abril de 2026" in texto, "la nómina en las CP"
        assert "agosto de 2026" in texto, "la imputación de partes"
        assert "722.704" in texto and "181.804" in texto, "las cifras medidas (2.ª pasada, D9)"
        assert "centro `CP`" in texto, "D9: toda cuenta del centro CP es restringida"
    assert "540.900" in general and "1.000 cuentas" in completo
    assert "perfil restringido" in completo and "perfil restringido" in general


#: La fuente de la respuesta a las preguntas de D8, tal como pidió el líder.
FUENTE_D8 = "Juan Romero, Control de Costes, correo del 2026-11-20"


@pytest.mark.parametrize("objeto", ["mayor_analitico", "saldos_cuenta_analitica_mes"])
def test_f127_r22_d8_contestada_en_las_fichas_de_las_cp(objeto: str) -> None:
    """D8 contestada: la nómina por trabajador en las CP solo hasta marzo de
    2026 (Cegid desde abril), el abono de los partes solo con el parte en IMP,
    y el saldo de una CP es «nómina menos partes» solo hasta marzo de 2026."""
    texto = _texto_ficha("contabilidad_restringida.yaml", objeto)
    assert FUENTE_D8 in texto
    for termino in ("Cegid", "marzo de 2026", "abril de 2026", "IMP", "CER",
                    "nomina menos partes"):
        assert termino in texto, f"{objeto} no dice «{termino}»"
    assert "pendiente de confirmar" not in texto


def test_f127_r22_las_reglas_dicen_la_frontera() -> None:
    reglas = {r["codigo"]: r for r in _dicc("00_global.yaml")["reglas"]}
    assert "contabilidad_restringida.mayor_analitico" in reglas["R-PERFILES"]["regla"]
    saldo = reglas["R-SALDO-CONTABLE"]
    assert "mayor_analitico" in saldo["regla"] and "mayor_analitico" not in saldo["resumen"], (
        "D6: una línea en la `regla`, no en el `resumen` que se sirve siempre"
    )


def test_f127_r22_raw_apa_dice_que_lo_publica_f127() -> None:
    apa = _texto_ficha("raw.yaml", "apa")
    assert "F-127" in apa and f"{RESTR}.mayor_analitico" in apa and "`con.tip = 32`" in apa


def test_f127_r23_la_receta_de_la_cp_del_trabajador() -> None:
    completo = _ficha("contabilidad_restringida.yaml", "mayor_analitico")["descripcion"]
    for termino in (
        "personal.recursos", "cuenta_analitica_contrapartida_id", "personal.partes_lineas",
        "obra_imputada_id", "tipo_asiento = 'ANALITICO'", "compartid", "saldo_acumulado",
    ):
        assert termino in completo, f"la receta de R23 no dice «{termino}»"
    preguntas = " ".join(_ficha("contabilidad_restringida.yaml", "mayor_analitico")[
        "ejemplos_preguntas"
    ])
    assert "contrapartida" in preguntas.lower()


@pytest.mark.parametrize(
    ("fichero", "objeto"), [(f, o) for f, o, *_ in FICHAS_F127],
    ids=[f"{f.split('.')[0]}.{o}" for f, o, *_ in FICHAS_F127],
)
def test_f127_r22_ningun_nombre_de_persona(fichero: str, objeto: str) -> None:
    """Las fichas nuevas hablan de cuentas y recuentos, nunca de personas. La
    única excepción es la fuente citada de D8 (petición del líder, 2.ª pasada)."""
    texto = _texto_ficha(fichero, objeto).replace(FUENTE_D8, "")
    assert "Juan" not in texto and "Romero" not in texto


# ===========================================================================
# R24 · la documentación
# ===========================================================================

RAIZ_REPO = DIR_CON.parents[4]


def test_f127_r24_architecture_describe_los_objetos_y_quien_los_lee() -> None:
    texto = (RAIZ_REPO / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for termino in (
        "Desde F-127", f"{RESTR}.mayor_analitico", f"{RESTR}.saldos_cuenta_analitica_mes",
        "contabilidad.mayor_analitico", "contabilidad.saldos_cuenta_analitica_mes",
        "contabilidad.apuntes_analiticos_restringidos_mes", "CONTRAPARTIDA", "D7-b",
        "perfil restringido y el de postventa",
    ):
        assert termino in texto, f"ARCHITECTURE.md no dice «{termino}»"
    assert "Hoy no está publicado (es `raw.apa`" not in texto, "ya no es verdad"


def test_f127_r24_tables_sigrid_dice_que_lo_publica_f127() -> None:
    texto = (RAIZ_REPO / "config" / "tables_sigrid.yaml").read_text(encoding="utf-8")
    bloque = texto.split("source_table: apa", 1)[1].split("source_table:", 1)[0]
    assert "F-127" in bloque and "contabilidad.mayor_analitico" in bloque


def test_f127_r24_azure_apps_describe_los_objetos() -> None:
    ruta = RAIZ_REPO.parent / "azure-apps" / "datamart_seg_anual.md"
    if not ruta.exists():
        pytest.skip("azure-apps no está junto a este repositorio")
    texto = ruta.read_text(encoding="utf-8")
    for termino in ("F-127", "contabilidad.mayor_analitico", f"{RESTR}.mayor_analitico",
                    "apuntes_analiticos_restringidos_mes"):
        assert termino in texto, f"azure-apps no dice «{termino}»"
