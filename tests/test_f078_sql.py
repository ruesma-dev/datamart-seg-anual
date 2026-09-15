# tests/test_f078_sql.py
"""
F-078 · La materializacion de FactCPTipologia, comprobada sobre su TEXTO.

`mart.v_pbi_cp_tipologia` era **la unica `v_pbi_` sin tabla detras**, asi que se
recalculaba entera en cada consulta: coste estimado 6,6 millones de unidades,
cinco `Parallel Seq Scan` sobre `stg.plan_mensual` (29,8 M de filas, 11 GB) y un
`WindowAgg` sobre 11,8 M de filas intermedias. Power BI se colgaba en el paso de
Navegacion y el MCP moria con cualquier pregunta que la tocase.

Esta feature cambia **DONDE se calcula, no QUE se calcula**. De ahi la forma de
este fichero: la mitad de sus tests fijan que la logica de negocio viajo
**verbatim** desde la vista hasta el `CREATE TABLE`. Si un refactor futuro
cambia una rama de la cascada de tipologias o el corte temporal comun a Plan y
Real, la suite se pone roja aqui y no seis meses despues, en una cifra rara de
un informe de Power BI.

Ninguno de estos tests toca red ni BBDD: el SQL construye tablas en un Postgres
**compartido con produccion**, y la convencion del proyecto es que los unit
tests no se conecten a nada. Mismo criterio que `tests/test_f073_sql.py` y
`tests/test_f080_sql.py`.

LO QUE ESTE FICHERO **NO** PUEDE DEMOSTRAR, y por eso queda como verificacion
MANUAL (humano) en `progress/impl_F-078.md`: que las cifras de la tabla nueva
coinciden con las de la vista de antes. Eso se mide contra Azure con
`python main.py check-cp-tipologia`, que es lo que comprueba la seccion final.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from tests.test_f006_fichas import columnas_proyectadas, cuerpo_de_vista

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RUTA_CP = DIR_SQL / "mart" / "06_cp_tipologia.sql"

#: El fichero que la feature retira. Se nombra a proposito: si alguien lo
#: resucita, las dos copias divergen y el build ejecuta la que este en la lista.
RUTA_VIEJA = DIR_SQL / "mart" / "06_views_cp_tipologia.sql"


@cache
def _sql() -> str:
    assert RUTA_CP.exists(), f"SQL no encontrado: {RUTA_CP}"
    return RUTA_CP.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto ejecutable. Corta el `--` alla donde aparezca, no solo al
    principio de la linea: el SQL de esta capa comenta a la derecha del codigo
    (`WHERE pm.ambito_id = 3  -- Coste Real`) y quedarse con esa cola partiria
    en dos todas las comparaciones de abajo."""
    return re.sub(r"--[^\n]*", "", texto)


def _compacto(texto: str) -> str:
    """Una sola linea, espacios colapsados: para buscar expresiones SQL."""
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


@cache
def _ejecutable() -> str:
    return _compacto(_sql())


@cache
def _cuerpo(objeto: str) -> str:
    """El cuerpo del `CREATE ... mart.<objeto> AS`, compactado."""
    cuerpo = cuerpo_de_vista(_sql(), "mart", objeto)
    assert cuerpo is not None, f"no se encontro el CREATE de mart.{objeto}"
    return _compacto(cuerpo)


# ===========================================================================
# R1 · Las tres tablas existen y se construyen en orden de dependencia
# ===========================================================================

#: Las tres tablas nuevas, en el orden en que tienen que construirse: el
#: catalogo de versiones, la vigencia anual calculada CONTRA ese catalogo, y el
#: hecho final.
TABLAS = ("master_versiones_tipadas", "master_vigente_anual", "fact_cp_tipologia")

#: Cada vista, con la tabla de la que pasa a leer. Los nombres de las vistas
#: NO cambian: es lo que permite que el `.pbix` del humano no se toque.
VISTA_SOBRE_TABLA = (
    ("v_master_versiones_tipadas", "master_versiones_tipadas"),
    ("v_master_vigente_anual", "master_vigente_anual"),
    ("v_pbi_cp_tipologia", "fact_cp_tipologia"),
)


@pytest.mark.parametrize("tabla", TABLAS)
def test_f078_r1_las_tres_tablas_se_crean_como_tabla(tabla: str) -> None:
    """El hecho y sus dos helpers dejan de ser vistas: son TABLAS."""
    assert f"CREATE TABLE mart.{tabla} AS" in _ejecutable(), (
        f"mart.{tabla} no se materializa: seguiria recalculandose en cada consulta"
    )


@pytest.mark.parametrize("tabla", TABLAS)
def test_f078_r1_cada_tabla_se_dropea_antes_de_crearse(tabla: str) -> None:
    """La nocturna reconstruye: sin el DROP, el segundo build revienta."""
    assert f"DROP TABLE IF EXISTS mart.{tabla} CASCADE;" in _ejecutable()


@pytest.mark.parametrize("vista", [v for v, _ in VISTA_SOBRE_TABLA])
def test_f078_r1_cada_vista_se_dropea_antes_de_recrearse(vista: str) -> None:
    """Las tres existen HOY colgando de `stg.plan_mensual`. Sin dropearlas, el
    `DROP TABLE` de la noche siguiente se las lleva por delante con CASCADE y
    nadie las recrea: es exactamente la averia que `03_agg_categoria.sql` le
    hizo a `cierre.v_pbi_planif_vs_real` y que R-FRESCURA documenta."""
    assert f"DROP VIEW IF EXISTS mart.{vista} CASCADE;" in _ejecutable()


def test_f078_r1_las_tablas_se_construyen_en_orden_de_dependencia() -> None:
    """`master_vigente_anual` lee de `master_versiones_tipadas` y el hecho lee de
    la vigente: construirlas al reves deja el build en un error de objeto
    inexistente la primera noche."""
    posiciones = [_ejecutable().index(f"CREATE TABLE mart.{t} AS") for t in TABLAS]

    assert posiciones == sorted(posiciones), (
        f"las tablas no se crean en orden de dependencia: {TABLAS}"
    )


def test_f078_r1_los_drop_van_antes_que_los_create() -> None:
    """Todo el bloque de limpieza, delante. Un DROP intercalado se llevaria por
    delante una tabla ya construida en esta misma ejecucion."""
    texto = _ejecutable()
    ultimo_drop = max(texto.rindex(f"DROP TABLE IF EXISTS mart.{t}") for t in TABLAS)
    primer_create = min(texto.index(f"CREATE TABLE mart.{t} AS") for t in TABLAS)

    assert ultimo_drop < primer_create


def test_f078_r1_el_fichero_de_solo_vistas_ya_no_existe() -> None:
    """Se renombro a `06_cp_tipologia.sql` porque ya no crea solo vistas.
    Dejar el viejo ahi seria dejar dos definiciones del mismo objeto."""
    assert not RUTA_VIEJA.exists(), (
        f"{RUTA_VIEJA.name} sigue en el arbol: hay dos definiciones de los "
        "mismos tres objetos y el build ejecuta la que este en SUB_PASOS"
    )


# ===========================================================================
# R2 · Lo que mata el coste: nadie vuelve a `stg.plan_mensual` en la consulta
# ===========================================================================


@pytest.mark.parametrize(("vista", "tabla"), VISTA_SOBRE_TABLA)
def test_f078_r2_cada_vista_lee_de_su_tabla(vista: str, tabla: str) -> None:
    assert f"FROM mart.{tabla}" in _cuerpo(vista), (
        f"mart.{vista} no lee de mart.{tabla}"
    )


@pytest.mark.parametrize("vista", [v for v, _ in VISTA_SOBRE_TABLA])
def test_f078_r2_ninguna_vista_vuelve_a_stg(vista: str) -> None:
    """El sintoma era este: cinco recorridos de `stg.plan_mensual` —29,8 M de
    filas, 11 GB— por cada consulta. Si una vista vuelve a `stg`, el arreglo no
    sirve de nada aunque las tablas existan."""
    assert "stg." not in _cuerpo(vista), (
        f"mart.{vista} sigue tocando `stg`: la consulta vuelve a costar lo mismo"
    )


def test_f078_r2_la_vigencia_anual_se_calcula_contra_la_TABLA_de_versiones() -> None:
    """**Esto es lo que mata el `WindowAgg` de 11,8 M de filas.** Si la vigencia
    se calculara contra la VISTA `v_master_versiones_tipadas`, el plan volveria a
    barrer `stg.plan_mensual` por debajo y la tabla no habria ahorrado nada."""
    cuerpo = _cuerpo("master_vigente_anual")

    assert "JOIN mart.master_versiones_tipadas" in cuerpo
    assert "mart.v_master_versiones_tipadas" not in cuerpo


def test_f078_r2_el_hecho_se_calcula_contra_la_TABLA_de_vigencia() -> None:
    cuerpo = _cuerpo("fact_cp_tipologia")

    assert "JOIN mart.master_vigente_anual va" in cuerpo
    assert "mart.v_master_vigente_anual" not in cuerpo


@pytest.mark.parametrize("tabla", TABLAS)
def test_f078_r2_el_build_si_puede_bajar_a_stg(tabla: str) -> None:
    """Control del test anterior: el calculo TIENE que leer `stg` en alguna
    parte. Si esto se pusiera verde con las tablas vacias de origen, el test de
    arriba estaria comprobando el vacio."""
    cuerpo = _cuerpo(tabla)

    assert "stg." in cuerpo or "mart.master_" in cuerpo


# ===========================================================================
# R3 · Las cifras no cambian: la logica de negocio viajo VERBATIM
#
# Aqui solo cambia DONDE se calcula. Cada cadena de abajo esta copiada del
# `06_views_cp_tipologia.sql` anterior a esta feature (commit b208a59).
# ===========================================================================

#: La cascada de tipologias, tal y como la dejo F-006. Las cinco primeras son
#: los subcapitulos DEFINITORIOS —mandan sobre la descripcion— y las cinco
#: siguientes el fallback por descripcion para los no definitorios.
CASCADA_TIPOLOGIA = (
    "WHEN split_part(ruta_capitulos, ' > ', 2) IN ('CP.9', 'CP.9_1') THEN 'LEVANTAMIENTO'",
    "WHEN split_part(ruta_capitulos, ' > ', 2) IN ('CP.1', 'CP.2', 'CP.3') THEN 'SEGUROS'",
    "WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.4' THEN 'AVALES'",
    "WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.6' THEN 'CONTRATACION'",
    "WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.12' THEN 'MEDIO AMBIENTE'",
    "WHEN UPPER(descripcion_corta) LIKE '%LEVANTAM%' THEN 'LEVANTAMIENTO'",
    "WHEN UPPER(descripcion_corta) LIKE '%SEGURO%' THEN 'SEGUROS'",
    "WHEN UPPER(descripcion_corta) LIKE '%AVAL%' OR UPPER(descripcion_corta) "
    "LIKE '%GARANTIA%' THEN 'AVALES'",
    "WHEN UPPER(descripcion_corta) LIKE '%CONTRATAC%' THEN 'CONTRATACION'",
    "WHEN UPPER(descripcion_corta) LIKE '%CALIDAD%' OR UPPER(descripcion_corta) "
    "LIKE '%MEDIO AMB%' THEN 'MEDIO AMBIENTE'",
    "ELSE 'APORTE GG'",
)

#: El orden de presentacion de la matriz de Power BI. Cambiarlo reordena el
#: visual del humano sin tocar el `.pbix`.
ORDEN_TIPOLOGIA = (
    "WHEN 'LEVANTAMIENTO' THEN 1",
    "WHEN 'SEGUROS' THEN 2",
    "WHEN 'AVALES' THEN 3",
    "WHEN 'CONTRATACION' THEN 4",
    "WHEN 'MEDIO AMBIENTE' THEN 5",
    "WHEN 'APORTE GG' THEN 6",
)

#: El tipado del master por el texto libre del jefe de obra, con su prioridad
#: estricta: 'INICIAL' + 'VALORADA' gana a 'VALORADA' a secas.
TIPADO_MASTER = (
    "WHEN version_tex IS NULL OR length(trim(version_tex)) = 0 THEN 'Sin clasificar'",
    "WHEN UPPER(version_tex) LIKE '%ABC%' THEN 'ABC'",
    "WHEN UPPER(version_tex) LIKE '%INICIAL%' AND UPPER(version_tex) "
    "LIKE '%VALORADA%' THEN 'Planif Inicial'",
    "WHEN UPPER(version_tex) LIKE '%CUATRIM%' OR UPPER(version_tex) "
    "LIKE '%VALORADA%' THEN 'Cuatrimestral'",
    "WHEN UPPER(version_tex) LIKE '%CIERRE%' THEN 'Cierre mensual'",
)


@pytest.mark.parametrize("rama", CASCADA_TIPOLOGIA)
def test_f078_r3_la_cascada_de_tipologias_no_cambia(rama: str) -> None:
    assert rama in _cuerpo("fact_cp_tipologia"), (
        "la cascada CP.x -> tipologia cambio: esta feature solo mueve DONDE se "
        "calcula, nunca QUE se calcula"
    )


@pytest.mark.parametrize("rama", ORDEN_TIPOLOGIA)
def test_f078_r3_el_orden_de_la_matriz_no_cambia(rama: str) -> None:
    assert rama in _cuerpo("fact_cp_tipologia")


@pytest.mark.parametrize("rama", TIPADO_MASTER)
def test_f078_r3_el_tipado_del_master_no_cambia(rama: str) -> None:
    assert rama in _cuerpo("master_versiones_tipadas")


def test_f078_r3_el_corte_temporal_comun_a_plan_y_real_no_cambia() -> None:
    """El corte es lo mas delicado de la vista: ano pasado -> 12, ano en curso
    -> ultimo mes con cierre real, con fallback a `mes_actual`. Cortar el Plan
    en el mes de calendario lo dejaria siempre por delante del Real."""
    cuerpo = _cuerpo("fact_cp_tipologia")

    assert "WHEN ao.anio < par.anio_actual THEN 12" in cuerpo
    assert "WHEN ao.anio = par.anio_actual THEN COALESCE(ur.mes, par.mes_actual)" in cuerpo
    assert "ELSE 0 END AS mes_corte" in cuerpo


def test_f078_r3_plan_y_real_se_suman_sobre_la_MISMA_ventana() -> None:
    """Dos veces, una por rama. Si se cayera una, la comparacion Real-vs-Plan
    del informe pasaria a comparar periodos distintos."""
    cuerpo = _cuerpo("fact_cp_tipologia")

    assert cuerpo.count("EXTRACT(MONTH FROM pm.anio_mes)::INT <= c.mes_corte") == 2


def test_f078_r3_los_ambitos_de_sigrid_no_cambian() -> None:
    """3 = Coste Real, 8 = Coste Planificado, 8 y 11 = los dos master."""
    hecho = _cuerpo("fact_cp_tipologia")

    assert "WHERE ambito_id = 3 GROUP BY 1, 2" in hecho, "ultimo_real"
    assert "WHERE pm.ambito_id = 3 " in hecho, "real_anual"
    assert "WHERE pm.ambito_id = 8 " in hecho, "plan_anual"
    assert "va.ambito_id = 8" in hecho, "solo la vigencia de COSTE"
    assert "WHERE ambito_id IN (8, 11)" in _cuerpo("master_versiones_tipadas")


def test_f078_r3_solo_entran_las_partidas_de_categoria_cp() -> None:
    """Una vez por rama. Sin el filtro, el hecho sumaria CD y CI."""
    assert _cuerpo("fact_cp_tipologia").count("p.categoria = 'CP'") == 2


def test_f078_r3_la_vigencia_elige_la_ultima_version_con_row_number() -> None:
    cuerpo = _cuerpo("master_vigente_anual")

    assert (
        "ROW_NUMBER() OVER ( PARTITION BY ao.obra_id, ao.anio, vt.ambito_id "
        "ORDER BY vt.version_fec_efectiva DESC, vt.version DESC ) AS rn" in cuerpo
    )
    assert "WHERE rn = 1" in cuerpo


def test_f078_r3_solo_tres_tipos_de_master_cuentan_como_vigentes() -> None:
    """Las de 'Cierre mensual' NO reemplazan al plan (R-VERSION-MASTER)."""
    assert (
        "vt.tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')"
        in _cuerpo("master_vigente_anual")
    )


def test_f078_r3_el_corte_de_la_vigencia_es_31_12_o_hoy() -> None:
    assert (
        "WHEN ao.anio < p.anio_actual THEN make_date(ao.anio, 12, 31) ELSE p.hoy"
        in _cuerpo("master_vigente_anual")
    )


def test_f078_r3_el_outer_join_entre_real_y_plan_se_conserva() -> None:
    """`FULL JOIN` y no `INNER`: hay partidas con solo Real y partidas con solo
    Plan, y un `INNER` las perderia las dos sin decir nada."""
    cuerpo = _cuerpo("fact_cp_tipologia")

    assert (
        "FROM real_anual r FULL JOIN plan_anual p ON r.obra_id = p.obra_id "
        "AND r.anio = p.anio AND r.partida_id = p.partida_id" in cuerpo
    )


def test_f078_r3_las_filas_a_cero_siguen_sin_publicarse() -> None:
    cuerpo = _cuerpo("fact_cp_tipologia")

    assert "GROUP BY obra_id, anio, tipologia" in cuerpo
    assert "HAVING SUM(cp_real) <> 0 OR SUM(cp_planificado) <> 0" in cuerpo


def test_f078_r3_los_importes_conservan_su_precision() -> None:
    """`NUMERIC(18,2)` en las tres medidas. La tabla hereda el tipo de la
    proyeccion, asi que perder un cast aqui cambia el tipo de la columna."""
    cuerpo = _cuerpo("fact_cp_tipologia")

    assert "SUM(pm.importe_mes)::NUMERIC(18,2) AS cp_real" in cuerpo
    assert "SUM(pm.importe_mes)::NUMERIC(18,2) AS cp_planificado" in cuerpo
    assert "SUM(cp_real)::NUMERIC(18,2) AS cp_real" in cuerpo
    assert "SUM(cp_planificado)::NUMERIC(18,2) AS cp_planificado" in cuerpo
    assert (
        "(SUM(cp_real) - SUM(cp_planificado))::NUMERIC(18,2) AS cp_desviacion"
        in cuerpo
    )


# ===========================================================================
# R4 · Las tres vistas conservan nombre y columnas: el `.pbix` no se toca
#
# Es el criterio 2 de la ficha y el que decide si el humano tiene que abrir
# Power Query. Las listas estan congeladas del SQL anterior a la feature.
# ===========================================================================

COLUMNAS = {
    "v_master_versiones_tipadas": [
        "obra_id", "ambito_id", "version", "version_fec_creacion",
        "version_fec_efectiva", "version_descripcion", "version_tex", "tipo_master",
    ],
    "v_master_vigente_anual": [
        "obra_id", "anio", "ambito_id", "version", "version_fec_efectiva",
        "version_descripcion", "version_tex", "tipo_master",
    ],
    "v_pbi_cp_tipologia": [
        "obra_id", "anio", "tipologia", "orden_tipologia",
        "cp_real", "cp_planificado", "cp_desviacion",
    ],
}

#: Cada tabla proyecta exactamente lo mismo que su vista: la vista es un
#: `SELECT` de columnas desnudas y nada mas.
COLUMNAS_DE_TABLA = {
    "master_versiones_tipadas": COLUMNAS["v_master_versiones_tipadas"],
    "master_vigente_anual": COLUMNAS["v_master_vigente_anual"],
    "fact_cp_tipologia": COLUMNAS["v_pbi_cp_tipologia"],
}


@pytest.mark.parametrize("vista", sorted(COLUMNAS))
def test_f078_r4_las_vistas_proyectan_exactamente_lo_de_siempre(vista: str) -> None:
    """Ni una columna de menos (Power Query se queda sin campo) ni una de mas
    (aparece sola en el modelo del humano)."""
    proyectadas = columnas_proyectadas(cuerpo_de_vista(_sql(), "mart", vista))

    assert proyectadas == COLUMNAS[vista], (
        f"mart.{vista} cambio de columnas: el .pbix del humano deja de cargar"
    )


@pytest.mark.parametrize("tabla", sorted(COLUMNAS_DE_TABLA))
def test_f078_r4_cada_tabla_proyecta_lo_que_su_vista_publica(tabla: str) -> None:
    proyectadas = columnas_proyectadas(cuerpo_de_vista(_sql(), "mart", tabla))

    assert proyectadas == COLUMNAS_DE_TABLA[tabla]


def test_f078_r4_el_comando_de_mapping_sigue_leyendo_la_vista() -> None:
    """`inspect-cp-tipologia` valida el mapping CP.x -> tipologia contra la
    VISTA. Es el criterio 9 de la ficha y no hace falta tocarlo: por eso este
    test comprueba que nadie lo ha tocado."""
    main = (RAIZ / "main.py").read_text(encoding="utf-8")

    assert "FROM mart.v_pbi_cp_tipologia" in main


# ===========================================================================
# R5 · El sub-paso del build: encadena el fichero y CUENTA SUS FILAS
# ===========================================================================


def _sub_pasos():
    from etl_sigrid.application.steps import build_mart_step

    return build_mart_step.SUB_PASOS


def test_f078_r5_el_build_mart_encadena_el_fichero_nuevo() -> None:
    ficheros = [sub.sql_file for sub in _sub_pasos()]

    assert "06_cp_tipologia.sql" in ficheros
    assert "06_views_cp_tipologia.sql" not in ficheros


def test_f078_r5_el_fichero_del_sub_paso_existe_de_verdad() -> None:
    """Control: el step falla en caliente si el fichero no esta, y ese fallo
    solo se ve de noche."""
    for sub in _sub_pasos():
        assert (DIR_SQL / "mart" / sub.sql_file).exists(), sub.sql_file


def test_f078_r5_el_sub_paso_cuenta_las_filas_del_hecho() -> None:
    """«Como hacen los demas» (criterio 1 de la ficha): sin `target_table` el
    log de la noche no dice cuantas filas quedaron, y una tabla que se queda
    vacia pasa desapercibida. Se cuenta el hecho y no los helpers, por el mismo
    motivo que `compras.texto` cuenta los comentarios: sin versiones vigentes no
    hay filas de hecho, asi que contarlo las cubre a las tres."""
    sub = next((s for s in _sub_pasos() if s.sql_file == "06_cp_tipologia.sql"), None)

    assert sub is not None, "el sub-paso de CP por tipologia no esta en SUB_PASOS"
    assert sub.target_schema == "mart"
    assert sub.target_table == "fact_cp_tipologia"


def test_f078_r5_el_sub_paso_va_detras_del_resto_del_mart() -> None:
    """Depende de `stg`, no del resto de `mart`, pero se queda el ultimo: es el
    mas caro y encabezar la lista retrasaria el hecho central del datamart."""
    ficheros = [sub.sql_file for sub in _sub_pasos()]

    assert ficheros[-1] == "06_cp_tipologia.sql"


# ===========================================================================
# R6 · `check-cp-tipologia` · el criterio 3 de la ficha, hecho comando
#
# «Las cifras no pueden cambiar» no se demuestra afirmandolo. Hace falta
# comparar el resultado de la VISTA DE ANTES contra la TABLA NUEVA, fila a fila
# sobre las claves y sobre los tres importes. Como la vista de ahora lee de la
# tabla, compararlas seria una tautologia: por eso el comando lleva dentro una
# **fotografia congelada** del calculo anterior a F-078, que recalcula desde
# `stg`.
#
# La comparacion contra Azure es una LECTURA, pero necesita la tabla
# construida, asi que queda como verificacion MANUAL (humano).
# ===========================================================================


def _modulo_comparacion():
    from etl_sigrid.infrastructure.postgres import cp_tipologia_sql

    return cp_tipologia_sql


def test_f078_r6_la_fotografia_recalcula_desde_stg() -> None:
    """Si leyera de las tablas nuevas, la comparacion se compararia consigo
    misma y daria cero diferencias aunque el build estuviera mal. Es el modo de
    fallo que convierte una comprobacion en un adorno."""
    sql = _modulo_comparacion().sql_vista_anterior()

    assert "FROM stg.plan_mensual" in sql
    assert "stg.partidas" in sql
    for prohibido in (
        "mart.fact_cp_tipologia",
        "mart.master_vigente_anual",
        "mart.master_versiones_tipadas",
        "mart.v_pbi_cp_tipologia",
        "mart.v_master_vigente_anual",
        "mart.v_master_versiones_tipadas",
    ):
        assert prohibido not in sql, (
            f"la fotografia lee {prohibido}: la comparacion seria una tautologia"
        )


def test_f078_r6_la_comparacion_si_lee_la_tabla_nueva() -> None:
    """Control del test anterior: la mitad derecha SI es la tabla."""
    assert "FROM mart.fact_cp_tipologia" in _modulo_comparacion().sql_comparacion()


@pytest.mark.parametrize(
    "rama", CASCADA_TIPOLOGIA + ORDEN_TIPOLOGIA + TIPADO_MASTER
)
def test_f078_r6_la_fotografia_conserva_la_logica_de_negocio(rama: str) -> None:
    """Misma cascada, mismo orden y mismo tipado que el SQL del build. Si la
    fotografia se desviara, la comparacion denunciaria diferencias que no
    existen —o peor, taparia las que si—."""
    assert rama in _compacto(_modulo_comparacion().sql_vista_anterior())


def test_f078_r6_se_casan_por_las_tres_claves_de_negocio() -> None:
    sql = _compacto(_modulo_comparacion().sql_comparacion())

    assert (
        "FULL JOIN ahora t ON t.obra_id = v.obra_id AND t.anio = v.anio "
        "AND t.tipologia = v.tipologia" in sql
    )


@pytest.mark.parametrize(
    "medida", ("cp_real", "cp_planificado", "cp_desviacion", "orden_tipologia")
)
def test_f078_r6_se_comparan_los_tres_importes(medida: str) -> None:
    """`IS DISTINCT FROM` y no `<>`: con `<>`, una comparacion contra NULL da
    NULL, la fila se cae del WHERE y una diferencia real pasa por coincidencia.
    Es el modo de fallo silencioso de este tipo de contrastes."""
    sql = _compacto(_modulo_comparacion().sql_comparacion())

    assert f"v.{medida} IS DISTINCT FROM t.{medida}" in sql
    assert f"v.{medida} <> t.{medida}" not in sql


def test_f078_r6_las_filas_que_faltan_a_un_lado_tambien_son_diferencia() -> None:
    """Una fila que existe solo en una de las dos mitades es la peor de las
    diferencias, y un `INNER JOIN` la habria escondido."""
    sql = _compacto(_modulo_comparacion().sql_comparacion())

    assert "WHERE v.tipologia IS NULL OR t.tipologia IS NULL" in sql
    assert "'SOLO EN LA VISTA DE ANTES'" in sql
    assert "'SOLO EN LA TABLA NUEVA'" in sql


def test_f078_r6_el_filtro_de_obra_llega_a_las_dos_mitades() -> None:
    """Sin el filtro a los dos lados, la comparacion enfrentaria una obra contra
    todas las demas y saldria roja siempre."""
    sql = _modulo_comparacion().sql_comparacion(obra_id=1442383)

    assert sql.count("obra_id = 1442383") >= 2


def test_f078_r6_sin_obra_no_se_filtra_nada() -> None:
    sql = _modulo_comparacion().sql_comparacion()

    assert "AND obra_id = " not in sql
    assert "AND pm.obra_id = " not in sql


def test_f078_r6_una_obra_que_no_sea_un_entero_no_llega_a_la_sentencia() -> None:
    """No hay concatenacion de texto libre: `int()` revienta antes."""
    with pytest.raises(ValueError):
        _modulo_comparacion().sql_comparacion(obra_id="7 OR 1=1")  # type: ignore[arg-type]


@pytest.mark.parametrize("palabra", ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE"))
def test_f078_r6_la_comparacion_no_puede_escribir(palabra: str) -> None:
    """Corre contra un servidor compartido con `albaranes` y `partes` EN
    PRODUCCION. La transaccion va READ ONLY, pero el texto tampoco lo intenta."""
    assert palabra not in _modulo_comparacion().sql_comparacion().upper()


def test_f078_r6_el_timeout_es_generoso_a_proposito() -> None:
    """La mitad izquierda ES la consulta que no terminaba en 60 s: ponerle los
    30 s de las demas comprobaciones garantizaria que no se pueda comprobar."""
    assert _modulo_comparacion().TIMEOUT_POR_CONSULTA_S >= 600


def test_f078_r6_una_tabla_vacia_no_se_lee_como_cero_diferencias() -> None:
    """EL FALSO VERDE DE ESTA COMPROBACION: si el build no construyo nada, las
    dos mitades estan vacias y no hay diferencias. Eso no es un OK."""
    modulo = _modulo_comparacion()

    veredicto = modulo.veredicto([], filas_tabla=0)

    assert veredicto.startswith("KO")
    assert "VACIA" in veredicto


def test_f078_r6_cero_diferencias_con_filas_si_es_un_ok() -> None:
    modulo = _modulo_comparacion()

    veredicto = modulo.veredicto([], filas_tabla=41_237)

    assert veredicto.startswith("OK")
    assert "41237" in veredicto.replace(".", "").replace(",", "")
    assert "CERO diferencias" in veredicto


def test_f078_r6_una_sola_diferencia_tumba_el_veredicto() -> None:
    modulo = _modulo_comparacion()
    filas = [
        (1442383, 2025, "AVALES", "IMPORTES DISTINTOS", 10, 11, 5, 5, 5, 6, 3, 3)
    ]

    diferencias = modulo.diferencias_de(filas)
    veredicto = modulo.veredicto(diferencias, filas_tabla=41_237)

    assert len(diferencias) == 1
    assert diferencias[0].tipologia == "AVALES"
    assert diferencias[0].cp_real_antes == 10
    assert diferencias[0].cp_real_ahora == 11
    assert veredicto.startswith("KO")
    assert "1 diferencias" in veredicto


def test_f078_r6_el_comando_esta_registrado_con_sus_opciones() -> None:
    from click.testing import CliRunner

    import main

    resultado = CliRunner().invoke(main.cli, ["check-cp-tipologia", "--help"])

    assert resultado.exit_code == 0
    assert "--obra" in resultado.output
    assert "--timeout" in resultado.output
    assert "--dry-run" in resultado.output


def test_f078_r6_dry_run_imprime_la_consulta_y_no_abre_conexion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from click.testing import CliRunner

    import main

    def revienta():
        raise AssertionError("--dry-run ha abierto una conexion")

    monkeypatch.setattr(main, "_get_pg", revienta)

    resultado = CliRunner().invoke(main.cli, ["check-cp-tipologia", "--dry-run"])

    assert resultado.exit_code == 0
    assert "stg.plan_mensual" in resultado.output
    assert "mart.fact_cp_tipologia" in resultado.output


class _PgComparacion:
    """Doble del cliente: devuelve lo que se le diga y NO abre nada."""

    def __init__(self, diferencias, filas_tabla: int) -> None:
        self._diferencias = diferencias
        self._filas_tabla = filas_tabla
        self.timeouts: list[int] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int):
        self.timeouts.append(timeout_s)
        if "count(*)" in sql_text:
            return [(self._filas_tabla,)]
        return self._diferencias


def test_f078_r6_sin_diferencias_el_comando_sale_con_cero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from click.testing import CliRunner

    import main

    pg = _PgComparacion(diferencias=[], filas_tabla=41_237)
    monkeypatch.setattr(main, "_get_pg", lambda: pg)

    resultado = CliRunner().invoke(main.cli, ["check-cp-tipologia"])

    assert resultado.exit_code == 0, resultado.output
    assert "CERO diferencias" in resultado.output


def test_f078_r6_con_diferencias_el_comando_sirve_de_puerta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sale con codigo 1: es una verificacion manual, y una verificacion que
    siempre sale con cero no sirve de puerta."""
    from click.testing import CliRunner

    import main

    pg = _PgComparacion(
        diferencias=[
            (1442383, 2025, "AVALES", "IMPORTES DISTINTOS", 10, 11, 5, 5, 5, 6, 3, 3)
        ],
        filas_tabla=41_237,
    )
    monkeypatch.setattr(main, "_get_pg", lambda: pg)

    resultado = CliRunner().invoke(main.cli, ["check-cp-tipologia"])

    assert resultado.exit_code == 1
    assert "1442383" in resultado.output
    assert "AVALES" in resultado.output


def test_f078_r6_la_tabla_vacia_tambien_tumba_el_comando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from click.testing import CliRunner

    import main

    pg = _PgComparacion(diferencias=[], filas_tabla=0)
    monkeypatch.setattr(main, "_get_pg", lambda: pg)

    resultado = CliRunner().invoke(main.cli, ["check-cp-tipologia"])

    assert resultado.exit_code == 1, "cero diferencias sobre cero filas no es un OK"
