# tests/test_f085_sql.py
"""
F-085 · La ingesta (`rac` sin filtro, `usu` sin credenciales), el SQL de
`compras.documento_procesos` y de `personal.usuarios_sigrid`, y los sub-pasos,
sobre su TEXTO.

Los SQL construyen objetos en un Postgres **compartido con producción**, así
que aquí no se ejecutan: se leen. Mismo criterio que `tests/test_f067_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Ninguna credencial de `usu` entra en el datamart** (R2, R3, R20): ni en la
   ingesta ni en el SQL de `personal`. La lista vive una vez, en el dominio.
2. **Los literales del SQL son los del dominio**
   (`domain/documento_procesos.py`): las familias, el orden de la cadena, la
   normalización del login, la hora válida y la empresa preferente.
3. **Quitar el filtro de `raw.rac` no cambia `retenciones`** (R5): su SQL ya
   filtra `asiide <> 0`.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain.documento_procesos import (
    COLUMNAS_CREDENCIALES_USU,
    EMPRESA_PREFERENTE,
    FAMILIAS,
)

RAIZ = Path(__file__).resolve().parents[1]
DIRECTORIO_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RUTA_PROCESOS = DIRECTORIO_SQL / "compras" / "12_documento_procesos.sql"
RUTA_SETUP_PERSONAL = DIRECTORIO_SQL / "personal" / "00_setup.sql"
RUTA_USUARIOS = DIRECTORIO_SQL / "personal" / "06_usuarios_sigrid.sql"
RUTA_APUNTES = DIRECTORIO_SQL / "retenciones" / "03_apuntes_contables.sql"
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
RUTA_SETTINGS = RAIZ / "config" / "settings.py"

#: Las diez columnas de `usu` que no se ingieren (R2): las seis credenciales
#: del dominio, el DNI (vacío en las 233 filas), el correo y dos textos libres.
EXCLUIDAS_USU = COLUMNAS_CREDENCIALES_USU | {"dni", "ele", "com", "resdes"}


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(
        re.sub(r"--.*$", "", linea) for linea in texto.splitlines()
    )


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


@cache
def _tablas() -> dict[str, dict]:
    datos = yaml.safe_load(_texto(RUTA_TABLAS))
    return {t["source_table"]: t for t in datos["tables"]}


def _comentario_de(tabla: str, largo: int = 4000) -> str:
    """El bloque de texto (comentarios incluidos) de una entrada del YAML."""
    trozo = _texto(RUTA_TABLAS).split(f"source_table: {tabla}\n", 1)[1]
    cortes = [i for i in (trozo.find("- source_table:"), trozo.find("# ====")) if i >= 0]
    return trozo[: min(cortes) if cortes else largo]


# ===========================================================================
# A · La ingesta: R1-R5
# ===========================================================================


def test_f085_r1_rac_se_ingiere_sin_filtro_y_sin_tex() -> None:
    rac = _tablas()["rac"]
    assert rac["where"] is None, "D1: `rac` sin el filtro `asiide <> 0`"
    assert rac["exclude_columns"] == ["tex"], "D3: `rac.tex` sigue fuera"
    assert rac["id_column"] == "ide"
    assert rac["incremental_column"] is None


def test_f085_r1_el_comentario_de_rac_explica_por_que_ya_no_va_filtrada() -> None:
    comentario = _comentario_de("rac")
    for dato in ("F-085", "2.517.791", "758.927", "min"):
        assert dato in comentario, f"el comentario de `rac` no dice «{dato}» (R1)"


def test_f085_r2_usu_se_declara_sin_filtro_y_sin_tiemod() -> None:
    usu = _tablas()["usu"]
    assert usu["target_table"] == "usu"
    assert usu["id_column"] == "ide"
    assert usu["incremental_column"] is None, "`usu` no tiene tiemod"
    assert usu["where"] is None


def test_f085_r2_usu_excluye_exactamente_las_diez() -> None:
    excluidas = _tablas()["usu"]["exclude_columns"]
    assert len(excluidas) == len(set(excluidas)), "columna repetida (R2)"
    assert set(excluidas) == EXCLUIDAS_USU, (
        f"`usu` excluye {sorted(excluidas)}; lo decidido es {sorted(EXCLUIDAS_USU)} (R2)"
    )


def test_f085_r3_ninguna_credencial_de_usu_se_ingiere() -> None:
    """La lista del dominio manda: añadir una credencial a la ingesta rompe aquí."""
    excluidas = set(_tablas()["usu"]["exclude_columns"])
    faltan = COLUMNAS_CREDENCIALES_USU - excluidas
    assert faltan == set(), f"credenciales de `usu` que SE INGIEREN: {sorted(faltan)} (R3)"


def test_f085_r2_el_comentario_de_usu_da_el_motivo_de_cada_exclusion() -> None:
    comentario = _comentario_de("usu").lower()
    for columna in sorted(EXCLUIDAS_USU):
        assert re.search(rf"- {columna}\b[^\n]*#", comentario), (
            f"la exclusión de `{columna}` no lleva su motivo al lado (R2)"
        )
    for motivo in ("contrasena", "firma digital", "correo", "f-085", "d4"):
        assert motivo in comentario, f"el comentario de `usu` no dice «{motivo}» (R2)"


def test_f085_r4_el_censo_pasa_a_72_sin_conpro_rol_ni_log() -> None:
    assert len(_tablas()) == 72
    assert "usu" in _tablas()
    for tabla in ("conpro", "rol", "log"):
        assert tabla not in _tablas(), f"`{tabla}` no se da de alta (D5, D8)"


def test_f085_r5_retenciones_sigue_filtrando_el_asiento_en_su_sql() -> None:
    compacto = _compacto(_texto(RUTA_APUNTES))
    assert re.search(
        r"rac_asiento AS \( SELECT r\.asiide AS asiento_id, MIN\(r\.conide\) AS "
        r"documento_id FROM raw\.rac r WHERE r\.asiide <> 0 AND r\.conide <> 0 "
        r"GROUP BY r\.asiide \)",
        compacto,
    ), "`retenciones` tiene que filtrar `asiide <> 0` en su SQL (R5)"


def test_f085_r28_el_bloque_de_lo_que_sigrid_no_guarda_esta_corregido() -> None:
    texto = _texto(RUTA_TABLAS)
    bloque = texto.split("LO QUE SIGRID NO GUARDA", 1)[1][:2500]
    assert "no hay historico de cambios de estado" not in bloque
    assert "`rac`" in bloque and "F-085" in bloque
    assert "compras.documento_procesos" in bloque


# ===========================================================================
# B · `compras.documento_procesos`: R6-R16
# ===========================================================================


def _procesos() -> str:
    return _compacto(_texto(RUTA_PROCESOS))


def test_f085_r6_se_reconstruye_cada_noche() -> None:
    compacto = _procesos()
    assert "DROP TABLE IF EXISTS compras.documento_procesos CASCADE;" in compacto
    assert "CREATE TABLE compras.documento_procesos AS" in compacto


def test_f085_r6_las_familias_del_in_son_las_del_dominio() -> None:
    hallazgo = re.search(r"WHERE c\.tip IN \(([\d, ]+)\)", _procesos())
    assert hallazgo, "falta el filtro de familias (R6)"
    tipos = [int(t) for t in hallazgo.group(1).split(",")]
    assert sorted(tipos) == sorted(FAMILIAS), "el IN y `FAMILIAS` no coinciden (R6)"


def test_f085_r6_el_case_de_familia_es_el_del_dominio() -> None:
    hallazgo = re.search(
        r"CASE o\.tipo_documento_codigo (.*?) END(?:::TEXT)? AS familia", _procesos()
    )
    assert hallazgo, "falta el CASE de `familia` (R6)"
    parejas = dict(
        (int(t), n) for t, n in re.findall(r"WHEN (\d+) THEN '(\w+)'", hallazgo.group(1))
    )
    assert parejas == FAMILIAS
    assert "ELSE" not in hallazgo.group(1), "el IN ya filtra: un ELSE es código muerto"


def test_f085_r7_las_columnas_en_su_orden() -> None:
    compacto = _procesos()
    select_final = compacto[compacto.rindex(") SELECT ") : compacto.index(" FROM ordenados o")]
    select_final += " FROM"
    alias = re.findall(r"(?:AS (\w+)|o\.(\w+))\s*(?:,|FROM)", select_final)
    columnas = [a or b for a, b in alias]
    assert columnas == [
        "paso_id", "documento_id", "tipo_documento_codigo", "familia",
        "codigo_documento", "proceso_id", "proceso",
        "estado_origen_id", "estado_origen_codigo", "estado_origen",
        "estado_destino_id", "estado_destino_codigo", "estado_destino",
        "usuario", "nombre_usuario", "fecha", "hora", "momento", "asiento_id",
        "orden", "es_ultimo", "encaja_con_anterior", "dias_desde_anterior",
    ]


def test_f085_r7_clave_e_indices() -> None:
    compacto = _procesos()
    assert "ALTER TABLE compras.documento_procesos ADD PRIMARY KEY (paso_id);" in compacto
    for indice in (
        "ON compras.documento_procesos (documento_id, orden);",
        "ON compras.documento_procesos (usuario);",
        "ON compras.documento_procesos (fecha);",
    ):
        assert indice in compacto, f"falta el índice {indice} (R7)"


def test_f085_r8_los_estados_se_traducen_por_la_pareja_tipo_estado() -> None:
    compacto = _procesos()
    llamadas = re.findall(r"compras\.fn_estado_documento\(([^)]*)\)", compacto)
    assert llamadas == [
        "o.tipo_documento_codigo, o.estado_origen_id",
        "o.tipo_documento_codigo, o.estado_destino_id",
    ], "dos traducciones, el tipo primero (R8)"
    assert "raw.conest" not in compacto, "nunca se une `conest` solo por el estado (R8)"


def test_f085_r9_proceso_y_asiento() -> None:
    compacto = _procesos()
    assert "NULLIF(r.conproide, 0) AS proceso_id" in compacto
    assert "BTRIM(r.res) AS proceso" in compacto
    assert "NULLIF(r.asiide, 0) AS asiento_id" in compacto


def test_f085_r10_fecha_hora_y_momento() -> None:
    compacto = _procesos()
    assert "compras.fn_sigrid_date(r.fec) AS fecha" in compacto
    assert re.search(
        r"CASE WHEN r\.hor BETWEEN 1 AND 235959 AND \(r\.hor / 100\) % 100 < 60 "
        r"AND r\.hor % 100 < 60 THEN make_time\(",
        compacto,
    ), "la hora válida es la de `hora_sigrid` (R10)"
    assert "p.fecha + p.hora AS momento" in compacto


def test_f085_r11_el_orden_de_la_cadena_es_el_del_dominio() -> None:
    compacto = _procesos()
    assert (
        "WINDOW w AS (PARTITION BY p.documento_id "
        "ORDER BY p.fecha NULLS LAST, p.hora NULLS LAST, p.paso_id)"
    ) in compacto, "el orden y el desempate de `encadenar` (R11)"
    assert "ROW_NUMBER() OVER w AS orden" in compacto
    assert "COUNT(*) OVER (PARTITION BY p.documento_id) AS n_pasos" in compacto
    assert "(o.orden = o.n_pasos) AS es_ultimo" in compacto


def test_f085_r12_encaja_con_el_destino_anterior() -> None:
    compacto = _procesos()
    assert "LAG(p.estado_destino_id) OVER w AS destino_anterior" in compacto
    assert (
        "CASE WHEN o.orden = 1 THEN NULL ELSE o.estado_origen_id "
        "IS NOT DISTINCT FROM o.destino_anterior END AS encaja_con_anterior"
    ) in compacto


def test_f085_r13_dias_con_dos_decimales() -> None:
    compacto = _procesos()
    assert "LAG(p.fecha + p.hora) OVER w AS momento_anterior" in compacto
    assert (
        "ROUND(EXTRACT(EPOCH FROM (o.momento - o.momento_anterior))::NUMERIC / 86400, 2) "
        "AS dias_desde_anterior"
    ) in compacto


def test_f085_r14_el_login_casa_normalizado_por_los_dos_lados() -> None:
    compacto = _procesos()
    assert "SELECT UPPER(BTRIM(u.cod)) AS login_norm" in compacto
    assert "GROUP BY UPPER(BTRIM(u.cod))" in compacto, "agrupado: nunca multiplica (R14)"
    assert "LEFT JOIN usuarios us ON us.login_norm = UPPER(BTRIM(r.usu))" in compacto
    assert "r.usu AS usuario" in compacto, "el login se publica tal cual (R14)"
    assert "NULLIF(BTRIM(us.nombre), '') AS nombre_usuario" in compacto


def test_f085_r16_sin_documento_no_entra() -> None:
    compacto = _procesos()
    assert re.search(r"FROM raw\.rac r JOIN raw\.con c ON c\.ide = r\.conide", compacto)
    assert "LEFT JOIN raw.con" not in compacto, "R16: JOIN, no LEFT JOIN"


def test_f085_d4_compras_no_publica_dni_ni_empleado() -> None:
    # El COMMENT ON TABLE dice, a propósito, dónde está el DNI: se mira el resto.
    compacto = _procesos().split("COMMENT ON TABLE")[0].lower()
    for prohibido in ("dni", "raw.emp", "codemp", "empleado"):
        assert prohibido not in compacto, f"`{prohibido}` va solo en `personal` (D4)"


def test_f085_r3_compras_no_lee_ninguna_columna_excluida_de_usu() -> None:
    usadas = set(re.findall(r"\bu\.(\w+)", _procesos()))
    assert usadas == {"cod", "res"}, f"`raw.usu` solo aporta login y nombre: {usadas}"


# ===========================================================================
# C · `personal.usuarios_sigrid`: R17-R21
# ===========================================================================


def _usuarios() -> str:
    """El SQL ejecutable de `06`, sin el COMMENT ON TABLE (que es prosa)."""
    return _compacto(_texto(RUTA_USUARIOS)).split("COMMENT ON TABLE")[0]


def test_f085_r17_la_tabla_se_crea_en_el_setup_sin_drop() -> None:
    compacto = _compacto(_texto(RUTA_SETUP_PERSONAL))
    hallazgo = re.search(
        r"CREATE TABLE IF NOT EXISTS personal\.usuarios_sigrid \((.*?)\);", compacto
    )
    assert hallazgo, "la tabla la crea `00_setup.sql` (R17)"
    columnas = [c.strip().split()[0] for c in hallazgo.group(1).split(",")]
    assert columnas == [
        "usuario_id", "login", "nombre", "desactivado",
        "codigo_empleado", "empleado_id", "dni",
    ]
    assert "usuario_id INTEGER PRIMARY KEY" in hallazgo.group(1)
    assert "DROP TABLE" not in compacto.upper(), "en `personal` nunca DROP: los GRANT"


def test_f085_r20_el_login_es_unico_sin_distinguir_mayusculas() -> None:
    compacto = _compacto(_texto(RUTA_SETUP_PERSONAL))
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+ ON personal\.usuarios_sigrid \(UPPER\(login\)\);",
        compacto,
    )


def test_f085_r17_una_fila_por_usuario() -> None:
    compacto = _usuarios()
    assert "TRUNCATE TABLE personal.usuarios_sigrid;" in compacto
    assert "INSERT INTO personal.usuarios_sigrid (" in compacto
    exterior = compacto[compacto.index("FROM raw.usu u") :]
    assert " WHERE " not in exterior, "ni un filtro: una fila por fila de `raw.usu` (R17)"
    assert "LEFT JOIN empleados em" in exterior and "LEFT JOIN raw.emp e" in exterior


def test_f085_r17_las_columnas() -> None:
    compacto = _usuarios()
    for fragmento in (
        "u.ide AS usuario_id",
        "BTRIM(u.cod) AS login",
        "NULLIF(BTRIM(u.res), '') AS nombre",
        "(COALESCE(u.tipdes, 0) <> 0) AS desactivado",
        "NULLIF(BTRIM(u.codemp), '') AS codigo_empleado",
        "em.empleado_id AS empleado_id",
        "NULLIF(BTRIM(e.dni), '') AS dni",
    ):
        assert fragmento in compacto, f"falta «{fragmento}» (R17-R19)"


def test_f085_r18_el_empleado_es_la_regla_del_dominio() -> None:
    compacto = _usuarios()
    hallazgo = re.search(r"WITH empleados AS \((.*?)\) SELECT", compacto)
    assert hallazgo, "falta el CTE de empleados (R18)"
    cuerpo = hallazgo.group(1)
    assert "FROM raw.con c WHERE c.tip = 43 GROUP BY BTRIM(c.cod)" in cuerpo
    assert "WHEN COUNT(*) = 1 THEN MIN(c.ide)" in cuerpo
    assert (
        f"WHEN COUNT(*) FILTER (WHERE c.emp = {EMPRESA_PREFERENTE}) = 1 "
        f"THEN MIN(c.ide) FILTER (WHERE c.emp = {EMPRESA_PREFERENTE})"
    ) in cuerpo
    assert "ELSE" not in cuerpo, "sin una única de la empresa preferente: NULL (R18)"
    assert "LEFT JOIN empleados em ON em.codigo = NULLIF(BTRIM(u.codemp), '')" in compacto


def test_f085_r19_de_raw_emp_solo_el_dni() -> None:
    compacto = _usuarios()
    assert len(re.findall(r"\braw\.emp\b", compacto)) == 1
    assert "LEFT JOIN raw.emp e ON e.ide = em.empleado_id" in compacto
    assert set(re.findall(r"\be\.(\w+)", compacto)) == {"ide", "dni"}


def test_f085_r20_ninguna_credencial_ni_contacto_en_personal() -> None:
    usadas = set(re.findall(r"\bu\.(\w+)", _usuarios()))
    assert usadas == {"ide", "cod", "res", "tipdes", "codemp"}, usadas
    assert not usadas & EXCLUIDAS_USU
    setup = _compacto(_texto(RUTA_SETUP_PERSONAL)).lower()
    tabla = setup.split("personal.usuarios_sigrid (", 1)[1].split(");", 1)[0]
    for columna in ("clave", "password", "correo", "email", "firma", "cla ", "ele "):
        assert columna not in tabla, f"`{columna}` en `personal.usuarios_sigrid` (R20)"


def test_f085_r21_no_toca_la_configuracion_de_permisos() -> None:
    texto = _texto(RUTA_SETTINGS)
    assert "usuarios_sigrid" not in texto and "raw.usu" not in texto


# ===========================================================================
# Los sub-pasos: compras acaba en `12`, personal en `06`
# ===========================================================================


def test_f085_r6_compras_acaba_en_documento_procesos() -> None:
    from etl_sigrid.application.steps import build_compras_step

    subs = build_compras_step.SUB_PASOS
    # Desde F-132 la vista `13_estado_documentos.sql` va detrás (lo fija
    # `tests/test_f132_sql.py`): `12` es el último que cuenta filas. Delante
    # iba la foto diaria de F-067 (`11`), que la Fase B de F-132 retiró.
    assert [s.sql_file for s in subs[-3:-1]] == [
        "10_necesidades.sql", "12_documento_procesos.sql",
    ]
    assert (subs[-2].target_schema, subs[-2].target_table) == (
        "compras", "documento_procesos",
    )


def test_f085_r17_personal_acaba_en_usuarios_sigrid() -> None:
    from etl_sigrid.application.steps import build_personal_step

    ultimo = build_personal_step.SUB_PASOS[-1]
    assert ultimo.sql_file == "06_usuarios_sigrid.sql"
    assert (ultimo.target_schema, ultimo.target_table) == ("personal", "usuarios_sigrid")


# ===========================================================================
# R15 · la regla vive UNA vez, en el dominio, y el SQL la cita
# ===========================================================================


def test_f085_r15_los_dos_sql_remiten_a_su_oraculo_del_dominio() -> None:
    """Los literales los fijan los tests `r6`, `r11`, `r14` y `r18` contra las
    constantes del dominio; aquí, que cada SQL dice de dónde salen, para que
    quien lo toque sepa qué oráculo mover con él."""
    procesos = _texto(RUTA_PROCESOS)
    usuarios = _texto(RUTA_USUARIOS)
    assert "domain/documento_procesos.py" in procesos and "FAMILIAS" in procesos
    assert "LOS LITERALES SON LOS DEL DOMINIO" in procesos
    assert "empleado_de_usuario" in usuarios and "EMPRESA_PREFERENTE" in usuarios
