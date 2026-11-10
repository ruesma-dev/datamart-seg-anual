# tests/test_f156_ingesta_sql.py
"""
F-156 · La ingesta de postventa (`config/tables_sigrid.yaml`) y el SQL de los
esquemas `postventa` y `postventa_restringida`, sobre su TEXTO.

Los SQL construyen objetos en un Postgres compartido con producción, así que aquí
no se ejecutan: se leen (criterio de `tests/test_f090_ingesta_sql.py`). Lo que
este fichero defiende, por orden de lo que costaría un error:

1. **Ningún dato personal entra en el esquema general** (R3, R11, R24): `per`
   llega con cinco columnas y ningún nombre de columna de `postventa` habla de
   teléfono, correo, DNI, reclamante, contacto ni nombre de propietario.
2. **Los literales del SQL son los del dominio** (R8, R13, R15, R16, R20, R25).
3. **Compras no cambia** (R4): su índice de adjuntos sigue con sus cinco familias.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain import postventa as pv
from etl_sigrid.domain.documento_adjuntos import filtro_gra, filtro_rcg

RAIZ = Path(__file__).resolve().parents[1]
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_PV = DIR_SQL / "postventa"

#: Las 13 tablas nuevas (R1-R3).
NUEVAS = ("upv", "rcp", "rcpint", "tar", "tarres", "obrofc", "auxrcp", "auxtrcp", "auxofc",
          "prmtpl", "auxgra", "log", "per")
ENTERAS = ("upv", "rcp", "rcpint", "obrofc", "auxrcp", "auxtrcp", "auxofc", "prmtpl", "auxgra")


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _lista_tablas() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(_texto(RUTA_TABLAS))["tables"])


def _tablas() -> dict[str, dict]:
    return {t["source_table"]: t for t in _lista_tablas()}


def _comentario_de(tabla: str) -> str:
    """El texto del YAML de la entrada `tabla` y el comentario que la precede."""
    texto = _texto(RUTA_TABLAS)
    fin = texto.index(f"source_table: {tabla}\n")
    inicio = texto.rfind("- source_table:", 0, fin)
    trozo = texto[inicio if inicio >= 0 else 0: fin]
    sigue = texto[fin:]
    corte = sigue.find("- source_table:", 1)
    return trozo + (sigue[:corte] if corte >= 0 else sigue)


def _sin_comentarios(texto: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


def _sql(nombre: str) -> str:
    return _compacto(_texto(DIR_PV / nombre))


def _todo_el_sql() -> str:
    return " ".join(_sql(r.name) for r in sorted(DIR_PV.glob("*.sql")))


def _create(nombre: str, objeto: str, clase: str = "TABLE") -> str:
    """El `CREATE <clase> <objeto> AS ...` hasta su primer `;`."""
    sql = _sql(nombre)
    cabecera = f"CREATE {clase} {objeto} AS"
    assert cabecera in sql, f"falta «{cabecera}» en {nombre}"
    inicio = sql.index(cabecera)
    return sql[inicio: sql.index(";", inicio)]


def _alias_publicados(create: str) -> list[str]:
    """Los nombres que publica el SELECT final (lo que va tras cada ` AS `)."""
    final = create[create.rindex("SELECT "):]
    final = final[: final.index(" FROM ")]
    return re.findall(r" AS (\w+)", final)


# ===========================================================================
# A · Ingesta: R1-R5
# ===========================================================================


def test_f156_r1_las_trece_tablas_declaradas_con_ide() -> None:
    tablas = _tablas()
    for nombre in NUEVAS:
        assert nombre in tablas, f"`{nombre}` no está en tables_sigrid.yaml (R1)"
        entrada = tablas[nombre]
        assert entrada["target_table"] == nombre
        assert entrada["id_column"] == "ide"


def test_f156_r1_las_enteras_no_llevan_where() -> None:
    for nombre in ENTERAS:
        assert _tablas()[nombre]["where"] is None, f"`{nombre}` se trae entera (R1)"


def test_f156_r1_tar_y_tarres_solo_las_de_reclamacion() -> None:
    assert _tablas()["tar"]["where"] == pv.filtro_tar() == "rcpide > 0"
    assert _tablas()["tarres"]["where"] == pv.filtro_tarres()
    assert "dbo.tar" in pv.filtro_tarres() and "rcpide > 0" in pv.filtro_tarres()


def test_f156_r1_cada_tabla_lleva_su_comentario_con_cifras_del_dia() -> None:
    for nombre in NUEVAS:
        comentario = _comentario_de(nombre)
        assert "F-156" in comentario, f"`{nombre}` sin comentario de F-156 (R1)"
        assert "2026-11-03" in comentario, f"`{nombre}` sin la fecha de la medida (R1)"
        assert re.search(r"\d", comentario.split("source_table")[0] + comentario), nombre


def test_f156_r1_ninguna_tiene_columna_incremental() -> None:
    """La nocturna es `--full`: carga completa (D5)."""
    for nombre in NUEVAS:
        assert _tablas()[nombre]["incremental_column"] is None, nombre


def test_f156_r2_log_recortado_sin_res() -> None:
    log = _tablas()["log"]
    assert log["where"] == pv.filtro_log()
    assert "tab = 'con'" in pv.filtro_log() and "tip = 708" in pv.filtro_log()
    assert f"tex LIKE '{pv.TEXTO_CIERRE_APLICACION}%'" in pv.filtro_log()
    columnas = log.get("include_columns") or []
    assert columnas, "`log` va con lista blanca (R2)"
    assert "res" not in columnas, "`log.res` lleva texto libre de la incidencia (R2)"
    for necesaria in ("ide", "emp", "fec", "hor", "usu", "tab", "tip", "cod", "tex"):
        assert necesaria in columnas, f"`log` sin `{necesaria}` (R2)"


def test_f156_r3_per_con_cinco_columnas_y_filtrada() -> None:
    per = _tablas()["per"]
    assert tuple(per["include_columns"]) == pv.COLUMNAS_PER
    assert per["where"] == pv.filtro_per()
    for origen in ("rcp", "recide", "cntide", "upv", "peride"):
        assert origen in pv.filtro_per(), origen


def test_f156_r3_si_entra_un_dato_prohibido_de_per_falla() -> None:
    per = _tablas()["per"]
    entran = set(per["include_columns"])
    assert not entran & pv.COLUMNAS_PER_PROHIBIDAS, (
        f"`per` trae {sorted(entran & pv.COLUMNAS_PER_PROHIBIDAS)}: DNI, credenciales, "
        "direcciones y observaciones nunca entran (R3)"
    )
    assert entran <= set(pv.COLUMNAS_PER)


def test_f156_r4_rcg_y_gra_con_las_ocho_familias() -> None:
    ocho = {12, 14, 15, 44, 46, 707, 708, 47}
    for tabla, filtro in (("rcg", filtro_rcg()), ("gra", filtro_gra())):
        where = _tablas()[tabla]["where"]
        assert where == filtro, tabla
        familias = {int(x) for x in re.search(r"tip IN \(([^)]*)\)", where).group(1).split(",")}
        assert familias == ocho, f"`{tabla}` filtra {sorted(familias)} (R4)"


def test_f156_r4_compras_sigue_con_sus_cinco_familias() -> None:
    sql = _compacto(_texto(DIR_SQL / "compras" / "14_documento_adjuntos.sql"))
    for lista in re.findall(r"tip IN \(([^)]*)\)", sql):
        assert {int(x) for x in lista.split(",")} == {12, 14, 15, 44, 46}, lista


def test_f156_r5_el_censo_pasa_a_93() -> None:
    # F-040: +7 del lado de ingresos
    assert len(_tablas()) == 100
    assert len(_lista_tablas()) == 100, "tabla declarada dos veces"


def test_f156_r4_gra_sigue_detras_de_rcg() -> None:
    orden = [t["source_table"] for t in _lista_tablas()]
    assert orden.index("rcg") < orden.index("gra")


# ===========================================================================
# B · Esquema `postventa`: R6-R13
# ===========================================================================

ARCHIVOS = ("00_setup.sql", "01_unidades.sql", "02_incidencias.sql", "03_tareas.sql",
            "04_procesos.sql", "05_estado.sql", "06_adjuntos.sql", "07_restringida.sql",
            "08_coste_obra.sql")


def test_f156_r6_los_nueve_ficheros_con_su_ruta_en_la_primera_linea() -> None:
    for nombre in ARCHIVOS:
        primera = _texto(DIR_PV / nombre).splitlines()[0]
        assert primera == f"-- etl_sigrid/infrastructure/postgres/sql/postventa/{nombre}", nombre


def test_f156_r6_setup_crea_los_dos_esquemas_y_las_funciones() -> None:
    sql = _sql("00_setup.sql")
    assert "CREATE SCHEMA IF NOT EXISTS postventa;" in sql
    assert "CREATE SCHEMA IF NOT EXISTS postventa_restringida;" in sql
    for funcion in ("fn_fecha", "fn_momento", "fn_enmascarar", "fn_obra_de_partida"):
        assert f"CREATE OR REPLACE FUNCTION postventa.{funcion}(" in sql, funcion


def test_f156_r6_fn_fecha_es_la_de_compras() -> None:
    def cuerpo(sql: str, nombre: str) -> str:
        trozo = sql[sql.index(f"FUNCTION {nombre}("):]
        return trozo[trozo.index("$$"): trozo.index("$$;") + 3]

    compras = _compacto(_texto(DIR_SQL / "compras" / "00_setup.sql"))
    assert cuerpo(_sql("00_setup.sql"), "postventa.fn_fecha") == cuerpo(
        compras, "compras.fn_sigrid_date"
    )


def test_f156_r6_unidades() -> None:
    create = _create("01_unidades.sql", "postventa.unidades")
    assert "FROM raw.upv u JOIN raw.con cu ON cu.ide = u.ide" in create
    for columna in ("unidad_id", "empresa_id", "obra_id", "codigo_obra", "codigo_unidad",
                    "nombre_unidad", "estado_id", "estado_codigo", "estado", "tipologia",
                    "fin_garantia_vicios", "fin_garantia_habitabilidad",
                    "inicio_garantia_estructura", "fecha_escrituracion",
                    "fecha_fin_primer_listado", "fecha_visita_tecnica", "tiene_propietario"):
        assert columna in _alias_publicados(create), f"unidades sin `{columna}` (R6)"
    assert f"postventa.fn_estado({pv.TIPO_UNIDAD}, cu.est)" in create
    for prohibida in ("restel", "resele", "peride", "cliide AS"):
        assert f"u.{prohibida}" not in create.replace("u.cliide, 0) <> 0", ""), prohibida
    assert "ADD PRIMARY KEY (unidad_id)" in _sql("01_unidades.sql")


def test_f156_r9_oficios_obra() -> None:
    create = _create("01_unidades.sql", "postventa.oficios_obra")
    assert "FROM raw.obrofc o" in create and "raw.auxofc" in create
    assert "ADD PRIMARY KEY (oficio_obra_id)" in _sql("01_unidades.sql")


def test_f156_r7_incidencias_solo_con_cabecera_708() -> None:
    create = _create("02_incidencias.sql", "postventa.incidencias")
    assert f"FROM raw.rcp r JOIN raw.con c ON c.ide = r.ide AND c.tip = {pv.TIPO_INCIDENCIA}" in create
    assert "LEFT JOIN postventa.unidades un ON un.unidad_id = r.upvide" in create
    assert not re.search(r"(?<!LEFT )JOIN postventa\.unidades", create), (
        "una incidencia sin unidad publicada no se pierde: LEFT JOIN"
    )
    for columna in ("incidencia_id", "empresa_id", "obra_id", "codigo_obra", "unidad_id",
                    "codigo_incidencia", "fecha_alta", "momento_alta", "estado_id",
                    "estado_codigo", "estado", "clase_codigo", "clase", "tipo", "oficio",
                    "motivo", "forma_comunicacion_codigo", "urgencia", "ubicacion",
                    "descripcion", "descripcion_larga", "referencia_externa",
                    "fin_garantia_clase", "dentro_garantia"):
        assert columna in _alias_publicados(create), f"incidencias sin `{columna}` (R7)"
    assert "postventa.fn_enmascarar(c.res) AS descripcion" in create
    assert "postventa.fn_enmascarar(r.tex) AS descripcion_larga" in create
    assert "'RCPCLI'" in _sql("02_incidencias.sql")
    assert "ADD PRIMARY KEY (incidencia_id)" in _sql("02_incidencias.sql")


def test_f156_r8_fin_de_garantia_por_clase_con_los_literales_del_dominio() -> None:
    create = _create("02_incidencias.sql", "postventa.incidencias")
    casos = re.search(r"CASE BTRIM\(cl\.cod\) (.*?) END AS fin_garantia_clase", create)
    assert casos, "falta el CASE de fin_garantia_clase (R8)"
    pares = dict(re.findall(r"WHEN '(\d+)' THEN postventa\.fn_fecha\(u\.(\w+)\)", casos.group(1)))
    assert pares == pv.CLASE_FIN_GARANTIA, pares
    assert "ELSE" not in casos.group(1), "las demás clases dan NULL (R8)"
    assert "AS dentro_garantia" in create and "<=" in create


def test_f156_r9_intervinientes_sin_huerfanos() -> None:
    create = _create("02_incidencias.sql", "postventa.incidencia_intervinientes")
    assert re.search(r"(?<!LEFT )JOIN postventa\.incidencias i ON i\.incidencia_id = ri\.rcpide",
                     create), "fuera los intervinientes sin incidencia (R9)"
    assert "ri.cauave <> 0" in create and "AS causante" in create


def test_f156_r10_tareas() -> None:
    create = _create("03_tareas.sql", "postventa.tareas")
    assert f"JOIN raw.con ct ON ct.ide = t.ide AND ct.tip = {pv.TIPO_TAREA}" in create
    assert "JOIN postventa.incidencias i ON i.incidencia_id = t.rcpide" in create
    assert "NULLIF(t.empide, 0) AS empleado_id" in create
    assert f"postventa.fn_estado({pv.TIPO_TAREA}, ct.est)" in create
    assert "postventa.fn_enmascarar(t.tex) AS texto" in create
    for columna in ("tarea_id", "incidencia_id", "codigo_tarea", "estado", "oficio",
                    "proveedor", "prioridad", "porcentaje"):
        assert columna in _alias_publicados(create), columna
    assert "ADD PRIMARY KEY (tarea_id)" in _sql("03_tareas.sql")


def _columnas_del_esquema(esquema: str) -> dict[str, list[str]]:
    """Las columnas publicadas de cada tabla o vista de `esquema` en `sql/postventa`."""
    salida: dict[str, list[str]] = {}
    for nombre in ARCHIVOS:
        sql = _sql(nombre)
        for clase, objeto in re.findall(rf"CREATE (TABLE|VIEW) ({esquema}\.\w+) AS", sql):
            salida[objeto] = _alias_publicados(_create(nombre, objeto, clase))
    return salida


def test_f156_r11_ninguna_columna_del_general_es_un_dato_personal() -> None:
    columnas = _columnas_del_esquema("postventa")
    assert len(columnas) >= 10, sorted(columnas)
    for objeto, nombres in columnas.items():
        for nombre in nombres:
            for palabra in pv.PALABRAS_PROHIBIDAS_GENERAL:
                assert palabra not in nombre, f"{objeto}.{nombre} contiene «{palabra}» (R11)"


def test_f156_r11_el_general_no_lee_per() -> None:
    for nombre in ARCHIVOS:
        if nombre == "07_restringida.sql":
            continue
        assert "raw.per" not in _sql(nombre), f"{nombre} lee raw.per (R11)"


def test_f156_r12_guarda_de_cabeceras() -> None:
    sql = _sql("02_incidencias.sql")
    guarda = re.search(r"DO \$\$(.*?)\$\$;", sql)
    assert guarda, "falta la guarda de R12"
    cuerpo = guarda.group(1)
    assert "raw.rcp" in cuerpo and f"c.tip = {pv.TIPO_INCIDENCIA}" in cuerpo
    assert "v_total = 0" in cuerpo and "v_con < v_total * 0.99" in cuerpo
    assert re.search(r"RAISE EXCEPTION 'F-156 R12[^']*', [^;]*v_con", cuerpo), "con la cifra"
    assert sql.index("DO $$") < sql.index("DROP TABLE"), "la guarda va ANTES"


def test_f156_r13_la_mascara_del_sql_es_la_del_dominio() -> None:
    sql = _sql("00_setup.sql")
    funcion = sql[sql.index("FUNCTION postventa.fn_enmascarar("):]
    funcion = funcion[: funcion.index("$$;")]
    for patron, marca in (
        (pv.PATRON_CORREO, pv.MARCA_CORREO),
        (pv.PATRON_TELEFONO, pv.MARCA_TELEFONO),
        (pv.PATRON_TELEFONO_GRUPOS, pv.MARCA_TELEFONO),
    ):
        assert f"'{patron}', '{marca}', 'g'" in funcion, patron
    assert funcion.index(pv.PATRON_CORREO) < funcion.index(pv.PATRON_TELEFONO), (
        "el correo se enmascara antes que el teléfono, como en el dominio"
    )


# ===========================================================================
# C · Histórico: R14-R16
# ===========================================================================


def test_f156_r14_procesos_de_rac_y_de_los_cierres_de_la_aplicacion() -> None:
    create = _create("04_procesos.sql", "postventa.incidencia_procesos")
    tipos = ", ".join(str(t) for t in pv.TIPOS_POSTVENTA)
    assert f"JOIN raw.con c ON c.ide = r.conide AND c.tip IN ({tipos})" in create
    assert "'RAC' AS origen" in create and "'CIERRE_APLICACION'" in create
    assert "'RAC-' || r.ide" in create and "'LOG-' || l.ide" in create
    assert "FROM raw.log l" in create
    assert f"l.tex LIKE '{pv.TEXTO_CIERRE_APLICACION}%'" in create
    assert f"{pv.ESTADO_CERRADA} AS estado_destino_id" in create
    for columna in ("paso_id", "origen", "documento_id", "tipo_documento_codigo", "proceso",
                    "estado_origen_id", "estado_origen_codigo", "estado_origen",
                    "estado_destino_id", "estado_destino_codigo", "estado_destino", "fecha",
                    "momento", "usuario", "usuario_nombre", "es_ultimo"):
        assert columna in _alias_publicados(create) or f"{columna}," in create, columna
    assert "raw.usu" in create
    assert "ADD PRIMARY KEY (paso_id)" in _sql("04_procesos.sql")


def test_f156_r14_los_estados_por_la_pareja_tipo_estado() -> None:
    assert "WHERE ce.tip = p_tip AND ce.est = p_est" in _sql("00_setup.sql")
    create = _create("04_procesos.sql", "postventa.incidencia_procesos")
    assert "postventa.fn_estado(p.tipo_documento_codigo, p.estado_origen_id)" in create
    assert "postventa.fn_estado(p.tipo_documento_codigo, p.estado_destino_id)" in create


def test_f156_r15_vista_de_estado_con_los_origenes_del_dominio_en_su_orden() -> None:
    create = _create("05_estado.sql", "postventa.v_estado_incidencias", "VIEW")
    casos = re.search(r"CASE (WHEN .*?) END AS origen_fecha", create)
    assert casos, "falta el CASE de origen_fecha (R15)"
    literales = re.findall(r"THEN '(\w+)'", casos.group(1))
    literales += re.findall(r"ELSE '(\w+)'", casos.group(1))
    assert tuple(literales) == pv.ORIGENES_FECHA, literales
    assert f"i.estado_id = {pv.ESTADO_CERRADA}" in casos.group(1)
    assert f"i.estado_id = {pv.ESTADO_ALTA}" in casos.group(1)
    for columna in ("en_estado_desde", "cambiado_por", "origen_fecha"):
        assert columna in _alias_publicados(create), columna


def test_f156_r16_dias_y_resolucion() -> None:
    create = _create("05_estado.sql", "postventa.v_estado_incidencias", "VIEW")
    abiertos = ", ".join(str(e) for e in pv.ESTADOS_ABIERTOS)
    resolucion = ", ".join(str(e) for e in pv.ESTADOS_RESOLUCION)
    assert f"i.estado_id IN ({abiertos}) AS abierta" in create
    assert f"estado_destino_id IN ({resolucion})" in _sql("05_estado.sql")
    for columna in ("abierta", "fecha_resolucion", "dias_hasta_resolucion", "dias_abierta",
                    "dias_en_estado"):
        assert columna in _alias_publicados(create), columna


# ===========================================================================
# D · Adjuntos: R19-R21
# ===========================================================================


def test_f156_r19_adjuntos_columnas_del_contrato_de_abrir_adjunto() -> None:
    create = _create("06_adjuntos.sql", "postventa.documento_adjuntos")
    nombres = _alias_publicados(create)
    for columna in ("adjunto_id", "familia", "documento_id", "codigo_documento",
                    "cod_repositorio", "empresa_repositorio", "nombre_fichero", "extension",
                    "incidencia_id", "unidad_id", "tarea_id", "clase_grafico", "descripcion",
                    "fecha_alta", "subido_por"):
        assert columna in nombres, f"documento_adjuntos sin `{columna}` (R19)"
    assert "g.emp AS empresa_repositorio" in _sql("06_adjuntos.sql"), "entera, tal cual (F-145)"
    assert "r.ide AS adjunto_id" in _sql("06_adjuntos.sql")
    assert re.search(r"(?<!LEFT )JOIN raw\.gra g ON g\.ide = r\.gra", create)
    assert "LEFT JOIN raw.auxgra a ON a.ide = g.gratipide" in create
    assert "ADD PRIMARY KEY (adjunto_id)" in _sql("06_adjuntos.sql")


def test_f156_r19_extension_y_clase_iguales_que_compras() -> None:
    compras = _compacto(_texto(DIR_SQL / "compras" / "14_documento_adjuntos.sql"))
    propio = _sql("06_adjuntos.sql")
    extension = "lower(substring(btrim(g.nom) from '\\.([^.\\s]+)$')) AS extension"
    assert extension in compras and extension in propio
    caso = re.search(r"CASE WHEN b\.extension IS NULL.*?END::TEXT AS clase_fichero", compras)
    assert caso and caso.group(0) in propio


def test_f156_r20_familia_con_los_literales_del_dominio() -> None:
    create = _create("06_adjuntos.sql", "postventa.documento_adjuntos")
    esperado = (
        f"CASE WHEN c.tip = {pv.TIPO_UNIDAD} THEN 'UNIDAD' "
        f"WHEN c.tip = {pv.TIPO_TAREA} THEN 'TAREA' "
        f"WHEN g.gratipide = {pv.GRATIPIDE_REPARACION} THEN 'REPARACION' "
        "ELSE 'INCIDENCIA' END::TEXT AS familia"
    )
    assert esperado in create
    tipos = ", ".join(str(t) for t in pv.TIPOS_POSTVENTA)
    assert f"JOIN raw.con c ON c.ide = r.con AND c.tip IN ({tipos})" in create


def test_f156_r21_guarda_de_huerfanos() -> None:
    sql = _sql("06_adjuntos.sql")
    guarda = re.search(r"DO \$\$(.*?)\$\$;", sql)
    assert guarda, "falta la guarda (R21)"
    cuerpo = guarda.group(1)
    tipos = ", ".join(str(t) for t in pv.TIPOS_POSTVENTA)
    assert f"JOIN raw.con c ON c.ide = r.con AND c.tip IN ({tipos})" in cuerpo
    assert "LEFT JOIN raw.gra g ON g.ide = r.gra" in cuerpo
    assert "v_huerf > v_total * 0.01" in cuerpo
    assert re.search(r"RAISE EXCEPTION 'F-156 R21[^']*', v_huerf, v_total", cuerpo)
    assert sql.index("DO $$") < sql.index("DROP TABLE")


def test_f156_r19_no_nombra_el_binario() -> None:
    sql = _sql("06_adjuntos.sql")
    assert "ruesma_rep" not in sql and "g.ima" not in sql


# ===========================================================================
# E · Restringida: R23-R24
# ===========================================================================


def test_f156_r23_las_tres_tablas_restringidas() -> None:
    sql = _sql("07_restringida.sql")
    for objeto in ("contactos_incidencia", "contactos_unidad", "textos"):
        assert f"CREATE TABLE postventa_restringida.{objeto} AS" in sql, objeto
    ci = _alias_publicados(_create("07_restringida.sql",
                                   "postventa_restringida.contactos_incidencia"))
    for columna in ("incidencia_id", "propietario_id", "propietario_nombre", "reclamante_nombre",
                    "reclamante_telefono", "reclamante_correo", "contacto_nombre",
                    "contacto_telefono", "contacto_correo"):
        assert columna in ci, columna
    cu = _alias_publicados(_create("07_restringida.sql", "postventa_restringida.contactos_unidad"))
    for columna in ("unidad_id", "propietario_nombre", "contacto_nombre", "telefono_unidad",
                    "correo_unidad", "aviso_telefono", "horario_manana", "texto_otro_horario"):
        assert columna in cu, columna


def test_f156_r24_de_per_solo_salen_sus_cinco_columnas() -> None:
    sql = _sql("07_restringida.sql")
    usadas = set(re.findall(r"\bp[rcu]\.(\w+)", sql))
    assert usadas, "las personas se leen con los alias pr, pc y pu"
    assert usadas <= set(pv.COLUMNAS_PER), f"de per sale {sorted(usadas - set(pv.COLUMNAS_PER))}"
    alias = set(re.findall(r"raw\.per (\w+)", sql))
    assert alias and alias <= {"pr", "pc", "pu"}, f"raw.per se lee con alias {sorted(alias)}"
    for prohibida in pv.COLUMNAS_PER_PROHIBIDAS:
        assert not re.search(rf"\bp[rcu]\.{prohibida}\b", sql), f"07 lee per.{prohibida} (R24)"


def test_f156_r23_textos_integros_sin_mascara() -> None:
    create = _create("07_restringida.sql", "postventa_restringida.textos")
    assert "fn_enmascarar" not in create
    assert "raw.rcp" in create and "raw.tar" in create


# ===========================================================================
# F · Coste por obra: R25-R26
# ===========================================================================


def test_f156_r25_partida_obra_origen() -> None:
    create = _create("08_coste_obra.sql", "postventa.partida_obra_origen")
    assert "WITH RECURSIVE" in create
    assert "c.tip = 42" in create and "'%POSTVENTA%'" in create and "'POSTV%'" in create
    assert "postventa.fn_obra_de_partida(" in create
    assert "ca.nivel < 10" in create, "tope de 10 niveles: hay bucles en padide"
    assert "ob.emp = opv.empresa_id" in create, "la obra de origen es de SU empresa"
    literales = re.search(r"CASE (WHEN .*?) END AS liga", create)
    assert literales
    encontrados = re.findall(r"(?:THEN|ELSE) '(\w+)'", literales.group(1))
    assert set(encontrados) == set(pv.LIGAS_COSTE), encontrados
    assert "ADD PRIMARY KEY (partida_id)" in _sql("08_coste_obra.sql")


def test_f156_r25_obra_de_partida_en_sql_es_la_del_dominio() -> None:
    sql = _sql("00_setup.sql")
    funcion = sql[sql.index("FUNCTION postventa.fn_obra_de_partida("):]
    funcion = funcion[: funcion.index("$$;")]
    assert f"'{pv.PATRON_OBRA_PARTIDA}'" in funcion
    assert "lpad(" in funcion and "4, '0'" in funcion


def test_f156_r26_vista_de_coste_solo_facturas() -> None:
    create = _create("08_coste_obra.sql", "postventa.v_coste_obra", "VIEW")
    assert "FROM compras.factura_lineas fl" in create
    assert "JOIN compras.facturas f ON f.factura_id = fl.factura_id" in create
    assert "JOIN postventa.partida_obra_origen p ON p.partida_id = fl.partida_id" in create
    assert "date_trunc('month', f.fecha_factura)" in create
    assert "SUM(fl.importe)" in create
    assert "personal." not in _sql("08_coste_obra.sql"), "los partes no entran (R26)"


def test_f156_r6_tablas_solo_leen_raw_salvo_la_vista_de_coste() -> None:
    for nombre in ARCHIVOS:
        if nombre == "08_coste_obra.sql":
            continue
        sql = _sql(nombre)
        for esquema in ("compras.", "stg.", "mart.", "personal.", "maestro."):
            assert esquema not in sql, f"{nombre} lee {esquema} (design § 6)"
