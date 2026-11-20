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
    "SELECT DISTINCT ca.cenide AS centro_coste_id FROM raw.caa ca JOIN cp_recurso c "
    "ON c.cuenta_analitica_id = ca.ide WHERE ca.cenide <> 0"
)
CP = (
    "SELECT c.cuenta_analitica_id FROM cp_recurso c UNION SELECT a.cueide FROM raw.apa a "
    "JOIN raw.con asi ON asi.ide = a.conide JOIN raw.caa ca ON ca.ide = a.cueide "
    "JOIN centros_cp cc ON cc.centro_coste_id = ca.cenide "
    f"WHERE asi.tip = {TIPO_CON_ASIENTO_ANALITICO} AND COALESCE(a.hab, 0) <> 0"
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
    [("cp_recurso", CP_RECURSO), ("centros_cp", CENTROS_CP), ("cp", CP)],
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
