# tests/test_f040_sql.py
"""
F-040 · El SQL de los esquemas `ventas` y `ventas_restringida` (R5-R25), sobre
su TEXTO.

Los SQL construyen objetos en un Postgres compartido con producción, así que
aquí no se ejecutan: se leen (criterio de `tests/test_f156_ingesta_sql.py`).
Que además den las cifras que dice el dominio lo prueba, contra un Postgres
desechable, `tests/test_f040_sandbox.py`. Lo que este fichero defiende, por
orden de lo que costaría un error:

1. **Nada personal del cliente en `ventas`** (R7, R9, R24): ni `entcif`,
   `entres` ni direcciones en los ficheros del esquema general, y una guarda
   `DO` que tumba el paso si un CIF de persona física queda publicado.
2. **Los literales del SQL son los del dominio** (R6, R8, R11, R12, R15, R18):
   el patrón del NIF, las clases de garantía (el ÚNICO punto de D4), los
   estados que cuentan y los de seguimiento.
3. **Los importes de `raw` son `double precision`**: se castean a `NUMERIC`
   y no hay `ROUND` (ya tumbó una noche de producción, F-150).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import ventas as v

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_V = DIR_SQL / "ventas"
FICHEROS = (
    "00_setup.sql", "01_clientes.sql", "02_facturas.sql", "03_certificaciones.sql",
    "04_enlace.sql", "05_vistas.sql", "06_restringida.sql", "07_guardas.sql",
)
#: Los ficheros del esquema GENERAL: ninguno toca lo personal de la cabecera.
GENERALES = FICHEROS[1:6]

# ---------------------------------------------------------------------------
# Columnas de cada objeto (design_detalle.md § B)
# ---------------------------------------------------------------------------

COLUMNAS = {
    ("01_clientes.sql", "ventas.clientes"): (
        "cliente_id", "codigo_cliente", "nombre", "cif", "cif_normalizado", "tipo_documento",
        "pais", "es_persona_fisica", "cif_valido", "cif_repetido", "num_obras",
        "num_facturas", "num_certificaciones", "facturado_base", "primera_factura",
        "ultima_factura",
    ),
    ("02_facturas.sql", "ventas.facturas"): (
        "factura_id", "codigo_factura", "empresa_id", "fecha_factura", "clase",
        "estado_codigo", "estado_sigrid", "anulada", "cliente_id", "nombre_cliente",
        "cif_cliente", "es_persona_fisica", "obra_id", "codigo_obra", "obra_via",
        "contrato_id", "contrato_nombre", "base", "iva", "total_sin_retencion", "total",
        "a_cobrar", "importe_coeficientes", "retencion_garantia", "retencion_retesp",
        "retencion_otras", "num_lineas",
    ),
    ("02_facturas.sql", "ventas.factura_lineas"): (
        "linea_id", "factura_id", "posicion", "descripcion", "cantidad", "precio", "importe",
        "iva_id", "iva_cuota", "obra_id", "partida_id", "unidad", "linea_certificacion_id",
    ),
    ("02_facturas.sql", "ventas.factura_recargos"): (
        "recargo_linea_id", "factura_id", "recargo_id", "codigo_recargo", "nombre_recargo",
        "clase", "clase_recargo", "es_garantia", "base", "porcentaje", "importe",
    ),
    ("03_certificaciones.sql", "ventas.certificaciones"): (
        "certificacion_id", "codigo_certificacion", "numero", "mes", "fecha_certificacion",
        "empresa_id", "obra_id", "codigo_obra", "contrato_id", "contrato_nombre",
        "cliente_id", "nombre_cliente", "estado_codigo", "estado_sigrid", "cuenta",
        "facturada", "certificacion_anterior_id", "importe_a_cuenta", "importe_a_origen",
        "importe_anterior", "base", "iva", "total", "base_origen_contrato",
        "importe_coeficientes", "retencion_garantia", "retencion_retesp",
        "retencion_otras", "num_lineas",
    ),
    ("03_certificaciones.sql", "ventas.certificacion_recargos"): (
        "recargo_linea_id", "certificacion_id", "recargo_id", "codigo_recargo",
        "nombre_recargo", "clase", "clase_recargo", "es_garantia", "base", "porcentaje",
        "importe",
    ),
    ("04_enlace.sql", "ventas.certificacion_factura"): (
        "certificacion_id", "factura_id", "num_lineas", "cantidad",
    ),
    ("04_enlace.sql", "ventas.cobertura_enlace"): (
        "eslabon", "total", "enlazados", "importe_total", "importe_enlazado", "calculado_en",
    ),
    ("06_restringida.sql", "ventas_restringida.clientes_contacto"): (
        "cliente_id", "nombre", "cif", "cif_normalizado", "es_persona_fisica", "direccion",
        "direccion_linea1", "direccion_linea2", "codigo_postal", "telefono", "telefono2",
        "correo",
    ),
    ("06_restringida.sql", "ventas_restringida.factura_cabecera"): (
        "factura_id", "cliente_id", "es_persona_fisica", "nombre_cabecera", "cif_cabecera",
        "direccion_empresa_1", "direccion_contacto_1", "direccion_completa_1",
        "direccion_empresa_2", "direccion_contacto_2", "direccion_completa_2",
        "direccion_empresa_3", "direccion_contacto_3", "direccion_completa_3",
    ),
    ("06_restringida.sql", "ventas_restringida.factura_lineas_persona"): (
        "linea_id", "factura_id", "cliente_id", "descripcion",
    ),
}

VISTAS = {
    "ventas.v_factura_cobro": (
        "factura_id", "emitido", "cobrado", "pendiente", "num_efectos", "ultima_fecha_cobro",
    ),
    "ventas.v_seguimiento_certificacion": (
        "certificacion_id", "num_facturas", "facturado", "emitido", "cobrado", "pendiente",
        "factura_compartida", "estado_seguimiento",
    ),
    "ventas.v_contraste_certificado_obra": (
        "obra_id", "codigo_obra", "venta_real_origen_con_coeficientes", "certificado_origen",
        "facturado_origen", "pendiente_certificar", "certificado_sin_facturar",
    ),
}

#: Importes y cantidades de `raw` (double precision en la ingesta).
IMPORTES_RAW = ("totbas", "totiva", "totdoc", "tot", "totpag", "cuo", "bas", "valpor",
                "imporiori", "imporiant", "can", "pre", "ivacuo")


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


def _sql(nombre: str) -> str:
    return _compacto(_texto(DIR_V / nombre))


def _todo() -> str:
    return " ".join(_sql(f) for f in FICHEROS)


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
    final = final[: final.index(" FROM ")] if " FROM " in final else final
    return re.findall(r" AS (\w+)", final)


def _lista(tupla: tuple[int, ...]) -> str:
    return "(" + ", ".join(str(x) for x in tupla) + ")"


# ===========================================================================
# Ficheros, cabecera y estilo
# ===========================================================================


def test_f040_setup_los_ocho_ficheros_y_nada_mas() -> None:
    assert sorted(p.name for p in DIR_V.glob("*.sql")) == list(FICHEROS)


@pytest.mark.parametrize("fichero", FICHEROS)
def test_f040_setup_cabecera_con_ruta_y_lectura(fichero: str) -> None:
    texto = _texto(DIR_V / fichero)
    assert texto.splitlines()[0] == f"-- etl_sigrid/infrastructure/postgres/sql/ventas/{fichero}"
    assert "F-040" in texto
    assert "Lee de" in texto, f"{fichero}: la cabecera dice de qué lee"


def test_f040_setup_sin_round_y_con_los_importes_casteados() -> None:
    """`ROUND(double, 2)` no existe en PostgreSQL: el cast a NUMERIC ya redondea."""
    todo = _todo()
    assert "ROUND(" not in todo.upper()
    columnas = "|".join(IMPORTES_RAW)
    limpio = re.sub(rf"COALESCE\((?:\w+\.)?(?:{columnas}), 0\)::NUMERIC", "", todo)
    limpio = re.sub(rf"(?<![\w.])(?:\w+\.)?(?:{columnas})::NUMERIC", "", limpio)
    sueltos = re.findall(rf"(?<![\w.'])(?:\w+\.)?(?:{columnas})\b(?!')", limpio)
    assert sueltos == [], f"importes de raw sin castear a NUMERIC: {sueltos}"


def test_f040_setup_los_dos_esquemas_y_las_funciones() -> None:
    sql = _sql("00_setup.sql")
    assert "CREATE SCHEMA IF NOT EXISTS ventas;" in sql
    assert "CREATE SCHEMA IF NOT EXISTS ventas_restringida;" in sql
    for funcion in ("fn_fecha(d BIGINT)", "fn_cif_normalizado(c TEXT)",
                    "fn_es_persona_fisica(c TEXT, perfis INT)", "fn_cif_valido(c TEXT)",
                    "fn_clase_recargo(reccla INT)"):
        assert f"CREATE OR REPLACE FUNCTION ventas.{funcion}" in sql, funcion
    assert sql.count("IMMUTABLE") >= 5


def _cuerpo_funcion(sql: str, nombre: str) -> str:
    inicio = sql.index(f"FUNCTION {nombre}(")
    abre = sql.index("$$", inicio)
    return sql[abre: sql.index("$$", abre + 2) + 2]


def test_f040_setup_fn_fecha_es_copia_de_tesoreria() -> None:
    propio = _cuerpo_funcion(_sql("00_setup.sql"), "ventas.fn_fecha")
    tesoreria = _cuerpo_funcion(_compacto(_texto(DIR_SQL / "tesoreria" / "00_setup.sql")),
                                "tesoreria.fn_fecha")
    assert propio == tesoreria


def test_f040_r6_el_patron_del_nif_es_el_del_dominio() -> None:
    cuerpo = _cuerpo_funcion(_sql("00_setup.sql"), "ventas.fn_es_persona_fisica")
    assert v.PATRON_NIF_PERSONA == r"^[0-9KLMXYZ][0-9]{7}[A-Z]$"
    assert f"'{v.PATRON_NIF_PERSONA}'" in cuerpo
    assert "COALESCE(perfis, 0) <> 0" in cuerpo


def test_f040_r6_la_normalizacion_es_la_del_dominio() -> None:
    cuerpo = _cuerpo_funcion(_sql("00_setup.sql"), "ventas.fn_cif_normalizado")
    assert f"'{v.PATRON_SEPARADORES_CIF}'" in cuerpo
    assert "upper(" in cuerpo and "NULLIF(" in cuerpo


def test_f040_r8_cif_valido_con_los_literales_del_dominio() -> None:
    cuerpo = _cuerpo_funcion(_sql("00_setup.sql"), "ventas.fn_cif_valido")
    assert f"'{v.LETRAS_DNI}'" in cuerpo
    assert f"'{v.PATRON_DNI}'" in cuerpo
    assert f"'{v.PATRON_NIE}'" in cuerpo
    assert f"'{v.PATRON_NIF_KLM}'" in cuerpo
    assert f"'{v.PATRON_CIF_SOCIEDAD}'" in cuerpo
    assert "% 23" in cuerpo
    assert "'XYZ', '012'" in cuerpo


def test_f040_r12_clases_garantia_iguales_en_dominio_y_sql() -> None:
    """El ÚNICO punto de decisión de D4: si uno cambia y el otro no, falla."""
    cuerpo = _cuerpo_funcion(_sql("00_setup.sql"), "ventas.fn_clase_recargo")
    assert f"WHEN reccla IN {_lista(v.CLASES_GARANTIA)} THEN 'GARANTIA'" in cuerpo
    assert f"WHEN reccla = {v.CLASE_COEFICIENTES} THEN 'COEFICIENTES'" in cuerpo
    assert f"WHEN reccla = {v.CLASE_RETESP} THEN 'RETESP'" in cuerpo
    assert "ELSE 'OTRAS'" in cuerpo
    # La precedencia del dominio: coeficientes, garantía y, solo después, RETESP.
    assert cuerpo.index("'COEFICIENTES'") < cuerpo.index("'GARANTIA'") < cuerpo.index("'RETESP'")


def test_f040_r12_ningun_otro_fichero_repite_las_clases() -> None:
    """Las cuatro columnas se reparten SOLO por la función, nunca por `reccla`."""
    for fichero in FICHEROS[1:]:
        assert "reccla IN" not in _sql(fichero), fichero
        assert not re.search(r"reccla\s*=\s*\d", _sql(fichero)), fichero


# ===========================================================================
# Columnas publicadas de cada tabla y vista
# ===========================================================================


@pytest.mark.parametrize(("clave", "columnas"), list(COLUMNAS.items()),
                         ids=[k[1] for k in COLUMNAS])
def test_f040_r5_r23_columnas_de_cada_tabla(clave: tuple[str, str],
                                            columnas: tuple[str, ...]) -> None:
    fichero, objeto = clave
    assert tuple(_alias_publicados(_create(fichero, objeto))) == columnas


@pytest.mark.parametrize(("objeto", "columnas"), list(VISTAS.items()))
def test_f040_r17_r19_columnas_de_cada_vista(objeto: str, columnas: tuple[str, ...]) -> None:
    assert tuple(_alias_publicados(_create("05_vistas.sql", objeto, "VIEW"))) == columnas


@pytest.mark.parametrize("fichero", FICHEROS[1:7])
def test_f040_setup_tablas_con_drop_y_create(fichero: str) -> None:
    sql = _sql(fichero)
    for objeto in re.findall(r"CREATE TABLE ([\w.]+) AS", sql):
        assert f"DROP TABLE IF EXISTS {objeto} CASCADE;" in sql, objeto


# ===========================================================================
# R5-R8 · clientes
# ===========================================================================


def test_f040_r5_clientes_lee_cli_y_su_con() -> None:
    crea = _create("01_clientes.sql", "ventas.clientes")
    assert "FROM raw.cli" in crea
    assert f"raw.con c ON c.ide = cl.ide AND c.tip = {v.TIP_CLIENTE}" in crea
    for origen in ("raw.dvf", "raw.cer", "raw.obr"):
        assert origen in crea, origen


def test_f040_r5_agregados_antes_de_unir() -> None:
    """Facturas, certificaciones y obras se cuentan por cliente ANTES del JOIN."""
    crea = _create("01_clientes.sql", "ventas.clientes")
    for cte in ("facturas_cliente", "certificaciones_cliente", "obras_cliente"):
        cuerpo = crea[crea.index(f"{cte} AS ("):]
        cuerpo = cuerpo[: cuerpo.index(")", cuerpo.index("GROUP BY"))]
        assert "GROUP BY" in cuerpo, cte


def test_f040_r7_cif_de_persona_fisica_a_null_y_nombre_publico() -> None:
    crea = _create("01_clientes.sql", "ventas.clientes")
    assert "CASE WHEN b.es_persona_fisica THEN NULL ELSE b.cif END AS cif" in crea
    assert ("CASE WHEN b.es_persona_fisica THEN NULL ELSE b.cif_normalizado END "
            "AS cif_normalizado") in crea
    assert "b.nombre AS nombre" in crea


def test_f040_r7_valido_y_repetido_se_calculan_antes_de_anular() -> None:
    crea = _create("01_clientes.sql", "ventas.clientes")
    base = crea[crea.index("base AS ("): crea.index("SELECT", crea.index("base AS (") + 12)]
    assert "ventas.fn_cif_normalizado(cl.cif)" in crea
    assert "ventas.fn_cif_valido(" in crea
    assert "count(*) OVER (PARTITION BY" in crea
    assert "ventas.fn_es_persona_fisica(" in crea
    assert "base" in base
    final = crea[crea.rindex("SELECT "):]
    assert "b.cif_valido AS cif_valido" in final and "b.cif_repetido AS cif_repetido" in final


# ===========================================================================
# R9-R13 · facturas, líneas y recargos
# ===========================================================================


@pytest.mark.parametrize("fichero", GENERALES)
def test_f040_r9_nada_de_la_cabecera_personal_en_el_esquema_general(fichero: str) -> None:
    sql = _sql(fichero)
    for columna in (*v.COLUMNAS_PERSONALES_DVF, *v.COLUMNAS_CLI_CONTACTO):
        assert not re.search(rf"\.{columna}\b", sql), f"{fichero} lee `{columna}` (R9, R24)"
    assert "ventas_restringida" not in sql, fichero


def test_f040_r9_estado_y_anulada() -> None:
    crea = _create("02_facturas.sql", "ventas.facturas")
    assert f"raw.conest ce ON ce.tip = {v.TIP_FACTURA_VENTA} AND ce.est = c.est" in crea
    assert "(COALESCE(c.fecbaj, 0) <> 0) AS anulada" in crea
    assert "vc.cif AS cif_cliente" in crea, "el CIF del cliente ya anulado (R7)"
    assert "LEFT JOIN ventas.clientes vc ON vc.cliente_id = NULLIF(f.entide, 0)" in crea


def test_f040_r10_obra_por_el_centro_y_si_no_por_la_cabecera() -> None:
    crea = _create("02_facturas.sql", "ventas.facturas")
    assert "LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(f.cenide, 0)" in crea
    assert "COALESCE(cc.obra_id, ob.ide) AS obra_id" in crea
    assert ("CASE WHEN cc.obra_id IS NOT NULL THEN 'CENTRO' "
            "WHEN ob.ide IS NOT NULL THEN 'OBRA' END AS obra_via") in crea


@pytest.mark.parametrize(("fichero", "objeto", "tabla"), [
    ("02_facturas.sql", "ventas.facturas", "raw.dvfrec"),
    ("03_certificaciones.sql", "ventas.certificaciones", "raw.cerrec"),
])
def test_f040_r11_cuatro_columnas_por_la_funcion_y_agregadas_antes(
    fichero: str, objeto: str, tabla: str,
) -> None:
    crea = _create(fichero, objeto)
    recargos = crea[crea.index("recargos AS ("):]
    recargos = recargos[: recargos.index("GROUP BY r.docide") + len("GROUP BY r.docide")]
    assert f"FROM {tabla} r" in recargos
    for clase, columna in zip(v.CLASES_RECARGO, (
            "importe_coeficientes", "retencion_garantia", "retencion_retesp",
            "retencion_otras"), strict=True):
        assert (f"COALESCE(SUM(r.cuo::NUMERIC(18, 2)) FILTER (WHERE "
                f"ventas.fn_clase_recargo(r.reccla::INT) = '{clase}'), 0) AS {columna}"
                ) in recargos, columna
    final = crea[crea.rindex("SELECT "):]
    for columna in ("importe_coeficientes", "retencion_garantia", "retencion_retesp",
                    "retencion_otras"):
        assert f"COALESCE(rc.{columna}, 0) AS {columna}" in final, columna


def test_f040_r13_descripcion_null_de_persona_fisica() -> None:
    crea = _create("02_facturas.sql", "ventas.factura_lineas")
    assert "FROM raw.dvfpro l" in crea
    assert "CASE WHEN f.es_persona_fisica THEN NULL ELSE l.res END AS descripcion" in crea
    assert "LEFT JOIN ventas.facturas f ON f.factura_id = l.docide" in crea


def test_f040_r13_linea_de_certificacion_de_origen() -> None:
    crea = _create("02_facturas.sql", "ventas.factura_lineas")
    assert ("LEFT JOIN raw.cerpro cp ON cp.ide = NULLIF(l.linoriide, 0) "
            "AND cp.docide = NULLIF(l.docoriide, 0)") in crea
    assert "cp.ide AS linea_certificacion_id" in crea


@pytest.mark.parametrize(("fichero", "objeto", "tabla", "padre"), [
    ("02_facturas.sql", "ventas.factura_recargos", "raw.dvfrec", "factura_id"),
    ("03_certificaciones.sql", "ventas.certificacion_recargos", "raw.cerrec",
     "certificacion_id"),
])
def test_f040_r13_r15_recargos_por_linea(fichero: str, objeto: str, tabla: str,
                                        padre: str) -> None:
    crea = _create(fichero, objeto)
    assert f"FROM {tabla} r" in crea
    assert "LEFT JOIN raw.con rc ON rc.ide = NULLIF(r.recide, 0)" in crea
    assert "ventas.fn_clase_recargo(r.reccla::INT) AS clase_recargo" in crea
    assert "(ventas.fn_clase_recargo(r.reccla::INT) = 'GARANTIA') AS es_garantia" in crea
    assert f"r.docide AS {padre}" in crea


# ===========================================================================
# R14-R15 · certificaciones
# ===========================================================================


def test_f040_r14_estado_contrato_y_anterior() -> None:
    crea = _create("03_certificaciones.sql", "ventas.certificaciones")
    assert "FROM raw.cer k" in crea
    assert f"raw.conest ce ON ce.tip = {v.TIP_CERTIFICACION} AND ce.est = c.est" in crea
    assert "LEFT JOIN raw.obrctr oc ON oc.ide = NULLIF(k.ctride, 0)" in crea
    assert "(COALESCE(k.estfac, 0) <> 0) AS facturada" in crea
    assert "NULLIF(k.docoriide, 0) AS certificacion_anterior_id" in crea
    assert f"c.est IN {_lista(v.ESTADOS_CERT_CUENTAN)}" in crea


def test_f040_r15_a_cuenta_a_origen_y_anterior_de_las_lineas() -> None:
    crea = _create("03_certificaciones.sql", "ventas.certificaciones")
    lineas = crea[crea.index("lineas AS ("):]
    lineas = lineas[: lineas.index("GROUP BY p.docide") + len("GROUP BY p.docide")]
    assert "FROM raw.cerpro p" in lineas
    assert "SUM(COALESCE(p.tot, 0)::NUMERIC(18, 2)) AS importe_a_cuenta" in lineas
    assert "SUM(COALESCE(p.imporiori, 0)::NUMERIC(18, 2)) AS importe_a_origen" in lineas
    assert "SUM(COALESCE(p.imporiant, 0)::NUMERIC(18, 2)) AS importe_anterior" in lineas


def test_f040_r15_base_origen_contrato_acumulada_solo_si_cuenta() -> None:
    crea = _create("03_certificaciones.sql", "ventas.certificaciones")
    assert ("CASE WHEN b.cuenta AND b.contrato_id IS NOT NULL THEN "
            "SUM(b.base) FILTER (WHERE b.cuenta) OVER (PARTITION BY b.contrato_id "
            "ORDER BY b.numero, b.certificacion_id) END AS base_origen_contrato") in crea


# ===========================================================================
# R16-R20 · el enlace hasta el cobro
# ===========================================================================


def test_f040_r16_certificacion_factura_por_cerprodes() -> None:
    crea = _create("04_enlace.sql", "ventas.certificacion_factura")
    assert "FROM raw.cerprodes d" in crea
    assert "JOIN raw.cerpro p ON p.ide = d.docproide" in crea
    assert "JOIN raw.dvf f ON f.ide = d.docdeside" in crea
    assert f"WHERE d.docdestip = {v.DOCDESTIP_FACTURA_VENTA}" in crea
    assert "GROUP BY p.docide, d.docdeside" in crea


def test_f040_r20_cobertura_tres_eslabones_y_lee_cob() -> None:
    sql = _sql("04_enlace.sql")
    for eslabon in v.ESLABONES_COBERTURA:
        assert f"'{eslabon}'" in sql, eslabon
    assert v.ESLABONES_COBERTURA == ("CERTIFICACION_FACTURA", "FACTURA_EFECTO",
                                     "EFECTO_FACTURA")
    assert "raw.cob" in sql
    assert "tesoreria." not in sql, "la cobertura no espera a otro paso"


def test_f040_r17_v_factura_cobro_lee_cobros_y_no_suma_bajas() -> None:
    crea = _create("05_vistas.sql", "ventas.v_factura_cobro", "VIEW")
    assert "FROM tesoreria.efectos e" in crea
    assert "e.sentido = 'COBRO'" in crea
    assert "e.estado_tesoreria <> 'BAJA'" in crea
    assert "FILTER (WHERE e.estado_tesoreria = 'REALIZADO')" in crea
    assert "FILTER (WHERE e.estado_tesoreria = 'PREVISTO')" in crea
    assert "GROUP BY e.documento_id" in crea
    assert "FROM ventas.facturas f" in crea


def test_f040_r18_seguimiento_replica_el_dominio() -> None:
    crea = _create("05_vistas.sql", "ventas.v_seguimiento_certificacion", "VIEW")
    caso = crea[crea.index("CASE WHEN NOT"):]
    caso = caso[: caso.index(" END AS estado_seguimiento")]
    orden = [caso.index(f"'{e}'") for e in v.ESTADOS_SEGUIMIENTO]
    assert orden == sorted(orden), "la precedencia del dominio"
    assert f"{v.TOLERANCIA_COBRO}" in caso
    assert "factura_compartida" in crea
    assert "FROM ventas.certificaciones k" in crea
    assert "ventas.v_factura_cobro" in crea


def test_f040_r19_contraste_obras_venta_de_la_receta() -> None:
    crea = _create("05_vistas.sql", "ventas.v_contraste_certificado_obra", "VIEW")
    assert "FROM tesoreria.devengo_corte_obra d" in crea
    assert "d.concepto = 'VENTA'" in crea
    assert "WHERE k.cuenta" in crea
    assert "GREATEST" not in crea, "sin suelo: las diferencias llevan signo"


# ===========================================================================
# R21-R23 · ventas_restringida
# ===========================================================================


def test_f040_r21_contacto_con_el_cif_integro() -> None:
    crea = _create("06_restringida.sql", "ventas_restringida.clientes_contacto")
    assert "FROM raw.cli cl" in crea
    assert "cl.cif AS cif" in crea
    for raw_col, pub in (("dir", "direccion"), ("dir1", "direccion_linea1"),
                         ("dir2", "direccion_linea2"), ("dircpo", "codigo_postal"),
                         ("tel", "telefono"), ("tel2", "telefono2"), ("ele", "correo")):
        assert f"cl.{raw_col} AS {pub}" in crea, raw_col


def test_f040_r22_cabecera_con_las_once_columnas_personales() -> None:
    crea = _create("06_restringida.sql", "ventas_restringida.factura_cabecera")
    assert "FROM raw.dvf f" in crea
    for columna in v.COLUMNAS_PERSONALES_DVF:
        assert f"f.{columna} AS" in crea, columna


def test_f040_r23_lineas_de_persona_fisica_integras() -> None:
    crea = _create("06_restringida.sql", "ventas_restringida.factura_lineas_persona")
    assert "FROM raw.dvfpro l" in crea
    assert "JOIN ventas.facturas f ON f.factura_id = l.docide AND f.es_persona_fisica" in crea
    assert "l.res AS descripcion" in crea


def test_f040_restringida_solo_en_su_esquema() -> None:
    sql = _sql("06_restringida.sql")
    assert re.findall(r"CREATE TABLE (\w+)\.", sql) == ["ventas_restringida"] * 3
    assert "CREATE VIEW" not in sql


# ===========================================================================
# R24-R25 · la guarda
# ===========================================================================


def _guarda() -> str:
    sql = _sql("07_guardas.sql")
    assert sql.startswith("DO $$"), "la guarda es un bloque DO"
    return sql


@pytest.mark.parametrize(("publicada", "origen"), [
    ("ventas.facturas", "raw.dvf"),
    ("ventas.factura_lineas", "raw.dvfpro"),
    ("ventas.certificaciones", "raw.cer"),
    ("ventas_restringida.clientes_contacto", "raw.cli"),
    ("ventas_restringida.factura_cabecera", "raw.dvf"),
])
def test_f040_r25_guarda_recuentos(publicada: str, origen: str) -> None:
    guarda = _guarda()
    assert f"(SELECT count(*) FROM {publicada})" in guarda, publicada
    assert f"(SELECT count(*) FROM {origen})" in guarda, origen


def test_f040_r25_guarda_base_y_reparto_de_recargos() -> None:
    guarda = _guarda()
    assert "SUM(base) FROM ventas.facturas" in guarda
    assert "SUM(COALESCE(totbas, 0)::NUMERIC(18, 2)) FROM raw.dvf" in guarda
    for tabla, padre in (("ventas.facturas", "raw.dvfrec"),
                         ("ventas.certificaciones", "raw.cerrec")):
        assert (f"SUM(importe_coeficientes + retencion_garantia + retencion_retesp "
                f"+ retencion_otras) FROM {tabla}") in guarda, tabla
        assert f"FROM {padre} r" in guarda, padre
    assert guarda.count("RAISE EXCEPTION") >= 6


def test_f040_r24_guarda_de_lo_personal() -> None:
    guarda = _guarda()
    assert "FROM ventas.clientes WHERE cif IS NOT NULL AND (es_persona_fisica" in guarda
    assert "FROM ventas.facturas WHERE cif_cliente IS NOT NULL AND (es_persona_fisica" in guarda
    assert f"'{v.PATRON_NIF_PERSONA}'" in guarda
    assert "f.es_persona_fisica AND l.descripcion IS NOT NULL" in guarda
    assert "information_schema.columns" in guarda
    assert "table_schema = 'ventas'" in guarda
    for prefijo in v.PREFIJOS_PROHIBIDOS_EN_VENTAS:
        assert f"column_name LIKE '{prefijo}%'" in guarda, prefijo


def test_f040_r25_la_guarda_dice_la_cifra() -> None:
    guarda = _guarda()
    for mensaje in re.findall(r"RAISE EXCEPTION '([^']*)'", guarda):
        assert mensaje.startswith("F-040 R2"), mensaje
        assert "%" in mensaje, f"sin cifra: {mensaje}"
