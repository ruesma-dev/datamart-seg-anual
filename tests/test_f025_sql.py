# tests/test_f025_sql.py
"""
F-025 · Las consultas de la ventana, leídas SIN abrir conexión (T8, R16, R18).

Mismo patrón que `tests/test_f019_tramos.py` y `tests/test_f052_sql.py`: las
consultas viven como constantes de módulo precisamente para que un test lea
**el texto que se envía**, no una reconstrucción parecida que podría diverger
sin que nadie lo note.

Lo que se protege aquí no es la sintaxis —eso lo dirá Postgres— sino las cuatro
decisiones que hacen que estas consultas sean **baratas y honestas**:

1. El censo sale de `raw`, no de `maestro.obras`: sin dependencia de orden con
   `build_maestros`, que en `run-all` va después.
2. Los dos `EXISTS` van por índice. Contar filas por obra habría costado dos
   barridos de 29 M y 13,8 M de filas en un servidor sin créditos.
3. El `LEFT JOIN` a `_meta.obra_build`: una obra nunca construida tiene que
   SALIR, no esconderse.
4. La firma **solo agrega**; el hash es del dominio, y ahí es donde lo alcanza
   la campaña de mutación.
"""

from __future__ import annotations

import re

import pytest

from etl_sigrid.infrastructure.postgres import postgres_client as cliente
from etl_sigrid.infrastructure.postgres.postgres_client import (
    COLUMNAS_FIRMA_ORIGEN,
    SQL_ESTADO_OBRAS,
    SQL_FIRMA_ORIGEN,
    SQL_FIRMA_ORIGEN_CON_PLANIF,
    SQL_MARCAR_CONGELADA,
    SQL_OBRAS_CON_FILAS,
    SQL_REGISTRAR_FIRMA_ACTUAL,
    SQL_REGISTRAR_OBRA,
    SQL_ULTIMA_COMPLETA,
    TABLAS_ACOTADAS,
    PostgresClient,
)

CONSULTAS_DE_LECTURA = (
    SQL_ESTADO_OBRAS,
    SQL_FIRMA_ORIGEN,
    SQL_FIRMA_ORIGEN_CON_PLANIF,
    SQL_ULTIMA_COMPLETA,
)


# ---------------------------------------------------------------------------
# El censo (SQL_ESTADO_OBRAS)
# ---------------------------------------------------------------------------


def test_f025_r1_el_censo_sale_de_raw_y_no_de_maestro_obras() -> None:
    """`maestro.obras` la construye `build_maestros`, que en `run-all` va
    DESPUÉS de este build, y en una base recién creada no existe. Leyendo `raw`
    no hay dependencia de orden y el estado es el de la ingesta de esta noche."""
    assert "raw.obr" in SQL_ESTADO_OBRAS
    assert "raw.con" in SQL_ESTADO_OBRAS
    assert "maestro.obras" not in SQL_ESTADO_OBRAS


def test_f025_r1_la_obra_ES_un_concepto_y_el_join_va_por_ide() -> None:
    """`c.ide = o.ide`, la misma definición que usa `maestro.obras`. NO
    `obr.cenide`, que es el centro de coste y es otra cosa."""
    assert re.search(r"JOIN\s+raw\.con\s+c\s+ON\s+c\.ide\s*=\s*o\.ide", SQL_ESTADO_OBRAS)
    assert "cenide" not in SQL_ESTADO_OBRAS


def test_f025_r18_el_registro_entra_por_LEFT_JOIN() -> None:  # noqa: N802
    """Una obra que nunca se ha construido tiene que SALIR en el censo, con el
    registro a nulo, y entrar por R18. Un `INNER JOIN` la escondería, que es
    justo el silencio que esta feature elimina."""
    assert re.search(
        r"LEFT JOIN\s+_meta\.obra_build\s+b\s+ON\s+b\.obra_id\s*=\s*c\.ide",
        SQL_ESTADO_OBRAS,
    )


def test_f025_r18_las_dos_tablas_acotadas_se_miran_con_EXISTS() -> None:  # noqa: N802
    """**La decisión que hace barato el censo.** `idx_plan_mensual_obra_amb` e
    `idx_pres_obra_amb` empiezan los dos por `obra_id` (verificado contra
    `pg_indexes` el 2026-09-02), así que cada `EXISTS` es una sonda de índice
    que se para en la primera fila. Un `count(*)` por obra habría costado dos
    barridos de 29 M y 13,8 M de filas."""
    assert SQL_ESTADO_OBRAS.count("EXISTS (SELECT 1") == 2
    assert "stg.plan_mensual" in SQL_ESTADO_OBRAS
    assert "stg.presupuesto" in SQL_ESTADO_OBRAS
    assert "count(" not in SQL_ESTADO_OBRAS.lower()


def test_f025_r2_la_actividad_sale_de_stg_fases_ya_reconstruida() -> None:
    """`05_fases.sql` va antes que `06_presupuesto.sql`, que es el primer
    sub-paso acotado: cuando se compone el plan, las fases son de esta noche."""
    assert "stg.fases" in SQL_ESTADO_OBRAS
    assert "make_date" in SQL_ESTADO_OBRAS


def test_f025_r2_el_censo_acota_los_anios_absurdos_de_las_fases() -> None:
    """Un `anio` a 0 o a 99999 haría reventar `make_date`. Es el mismo filtro
    que usó el censo de `mediciones.md`."""
    assert "BETWEEN 1990 AND 2100" in SQL_ESTADO_OBRAS


def test_f025_r1_el_censo_sale_ordenado_por_obra() -> None:
    """El plan tiene que ser determinista: mismo censo, mismo plan."""
    assert SQL_ESTADO_OBRAS.strip().endswith("ORDER BY c.ide")


def test_f025_r1_el_censo_no_escribe_nada() -> None:
    for consulta in CONSULTAS_DE_LECTURA:
        for palabra in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER"):
            assert palabra not in consulta.upper(), f"{palabra} en una consulta de lectura"


# ---------------------------------------------------------------------------
# La firma del origen (SQL_FIRMA_ORIGEN)
# ---------------------------------------------------------------------------


def test_f025_r16_la_firma_se_calcula_sobre_raw() -> None:
    """`raw` es lo único que la ingesta sigue trayendo completo cada noche
    (R34), y por eso es la única señal posible una vez que `stg.presupuesto`
    deja de reconstruirse entero (DA-2)."""
    assert "raw.obrparpre" in SQL_FIRMA_ORIGEN
    assert "raw.obrparpar" in SQL_FIRMA_ORIGEN
    assert "raw.obrfas" in SQL_FIRMA_ORIGEN
    assert "stg." not in SQL_FIRMA_ORIGEN


def test_f025_r16_la_firma_NO_usa_ventanas() -> None:  # noqa: N802
    """**Lo que la hace segura de ejecutar.** Es una agregación por hash: no
    derrama a ficheros temporales, que es lo que llenó el disco compartido en
    F-019 y obligó a trocear el build."""
    assert "OVER (" not in SQL_FIRMA_ORIGEN.upper()
    assert "PARTITION BY" not in SQL_FIRMA_ORIGEN.upper()


def test_f025_r16_el_SQL_solo_agrega_y_no_hashea() -> None:  # noqa: N802
    """El hash lo calcula `domain.ventana.firma_de_obra`. No es manía de capas:
    es lo que hace la firma testable con fixtures y lo que la pone bajo la
    campaña de mutación de DA-6."""
    assert "md5(" not in SQL_FIRMA_ORIGEN
    assert "sha256" not in SQL_FIRMA_ORIGEN


def test_f025_r20_la_variante_barata_NO_incluye_planif() -> None:  # noqa: N802
    """R20: `planif` es un texto largo en 13,8 M de filas y detoastarlo entero
    puede ser prohibitivo. Se implementa la barata y se mide la cara (T2b)."""
    assert "planif" not in SQL_FIRMA_ORIGEN


def test_f025_r20_la_variante_cara_existe_para_poder_MEDIRLA() -> None:  # noqa: N802
    """No se ejecuta: vive en el módulo para que el humano mida su coste sin
    volver a escribir el SQL, y para que la diferencia esté a la vista."""
    assert "planif" in SQL_FIRMA_ORIGEN_CON_PLANIF
    assert "md5(" in SQL_FIRMA_ORIGEN_CON_PLANIF
    assert "ORDER BY pp.ide" in SQL_FIRMA_ORIGEN_CON_PLANIF, (
        "sin orden estable dentro del string_agg, el md5 cambiaria solo entre "
        "dos ejecuciones y denunciaria obras que no se han movido"
    )


def test_f025_r16_las_columnas_declaradas_son_las_que_devuelve_la_consulta() -> None:
    """`COLUMNAS_FIRMA_ORIGEN` es el contrato: sus nombres entran en el hash. Si
    se desincroniza del `SELECT`, `zip(..., strict=True)` reventaría en
    producción, y aquí revienta antes."""
    seleccion = SQL_FIRMA_ORIGEN.rsplit("SELECT o.ide AS obra_id,", 1)[1]
    seleccion = seleccion.split("FROM raw.obr o", 1)[0]

    for columna in COLUMNAS_FIRMA_ORIGEN:
        assert columna in seleccion, f"{columna} no sale del SELECT final"

    devueltas = [c.strip() for c in seleccion.replace("\n", " ").split(",") if c.strip()]
    assert len(devueltas) == len(COLUMNAS_FIRMA_ORIGEN)


def test_f025_r16_toda_obra_sale_en_la_firma_aunque_no_tenga_datos() -> None:
    """`LEFT JOIN` desde `raw.obr`: una obra sin presupuesto tiene firma —la de
    los nulos— y eso es lo que permite compararla la noche siguiente."""
    assert SQL_FIRMA_ORIGEN.count("LEFT JOIN") == 3


def test_f025_r16_la_firma_sale_ordenada_por_obra() -> None:
    assert SQL_FIRMA_ORIGEN.strip().endswith("ORDER BY o.ide")


# ---------------------------------------------------------------------------
# El registro (R14)
# ---------------------------------------------------------------------------


def test_f025_r14_el_registro_es_un_upsert_por_obra() -> None:
    """Una fila por obra, la última manda: sin `ON CONFLICT` la segunda noche
    reventaría contra la clave primaria."""
    for consulta in (SQL_REGISTRAR_OBRA, SQL_MARCAR_CONGELADA, SQL_REGISTRAR_FIRMA_ACTUAL):
        assert "ON CONFLICT (obra_id) DO UPDATE" in consulta


def test_f025_r14_marcar_congelada_NO_toca_la_fecha_de_construccion() -> None:  # noqa: N802
    """**El test que impide mentir sobre la frescura.** Esta noche no se ha
    construido nada de esa obra: mover su `construido_at` haría que
    `_meta.v_frescura_obra` dijera que el dato es de hoy cuando es de hace
    semanas, y esa vista existe precisamente para responder eso."""
    assert "construido_at" not in SQL_MARCAR_CONGELADA
    assert "filas" not in SQL_MARCAR_CONGELADA
    assert "firma_origen" not in SQL_MARCAR_CONGELADA


def test_f025_r16_la_ingesta_solo_escribe_la_firma_ACTUAL() -> None:  # noqa: N802
    """Las dos firmas son columnas distintas a propósito: si la ingesta pisara
    `firma_origen` cada noche, la comparación «de qué es el dato» contra «qué
    hay ahora en el origen» no diría nada."""
    assert "firma_actual" in SQL_REGISTRAR_FIRMA_ACTUAL
    assert "firma_origen" not in SQL_REGISTRAR_FIRMA_ACTUAL


def test_f025_r14_una_obra_reconstruida_deja_de_estar_congelada() -> None:
    """Reconstruir y marcar congelada son las dos únicas transiciones, y cada
    una fija el flag: sin esto, una obra que vuelve a la vida seguiría marcada
    como congelada para siempre."""
    import re

    assert re.search(r"congelada\s*=\s*FALSE", SQL_REGISTRAR_OBRA)
    assert re.search(r"congelada\s*=\s*TRUE", SQL_MARCAR_CONGELADA)


def test_f025_r14_el_registro_va_parametrizado_y_no_concatenado() -> None:
    """Nada de lo que va a la base se concatena: todo por `%(nombre)s`."""
    for consulta in (SQL_REGISTRAR_OBRA, SQL_MARCAR_CONGELADA, SQL_REGISTRAR_FIRMA_ACTUAL):
        assert "%(" in consulta
        assert "'" + "{" not in consulta


# ---------------------------------------------------------------------------
# El único identificador interpolado de todo el bloque
# ---------------------------------------------------------------------------


def test_f025_r13_la_tabla_de_obras_con_filas_se_valida_contra_una_lista() -> None:
    """`SQL_OBRAS_CON_FILAS` interpola un nombre de tabla, así que el nombre no
    puede venir de fuera: se valida contra `TABLAS_ACOTADAS` antes. Es el mismo
    cuidado que tiene `componer_sql_tramo` con las obras del tramo."""
    assert "{tabla}" in SQL_OBRAS_CON_FILAS
    assert TABLAS_ACOTADAS == ("plan_mensual", "presupuesto")


@pytest.mark.parametrize("tabla", ["obras", "plan_mensual; DROP TABLE x", ""])
def test_f025_r13_una_tabla_fuera_de_la_lista_se_rechaza_sin_conectar(
    tabla: str,
) -> None:
    """Falla ANTES de abrir ninguna conexión: el `raise` está antes del
    `with self.connection()`."""
    falso = PostgresClient.__new__(PostgresClient)

    with pytest.raises(ValueError, match="no acotada"):
        PostgresClient.fetch_obras_con_filas(falso, tabla)
    with pytest.raises(ValueError, match="no acotada"):
        PostgresClient.vacuum_analyze(falso, "stg", tabla)


def test_f025_r13_el_vacuum_solo_alcanza_a_las_dos_tablas_acotadas() -> None:
    """No es una comprobación de seguridad de cara a un atacante: es que un
    `VACUUM FULL` sobre la tabla equivocada en un `B1ms` sin créditos es una
    noche perdida."""
    falso = PostgresClient.__new__(PostgresClient)

    with pytest.raises(ValueError, match="no acotada"):
        PostgresClient.vacuum_analyze(falso, "stg", "obras")


def test_f025_r25_la_ultima_completa_solo_cuenta_las_que_TERMINARON_bien() -> None:  # noqa: N802
    """Una completa que murió a mitad no puso al día a nadie. Contarla dejaría
    las 880 obras congeladas una semana más creyendo que ya se hizo."""
    assert "status = 'SUCCESS'" in SQL_ULTIMA_COMPLETA
    assert "MAX(finished_at)" in SQL_ULTIMA_COMPLETA


def test_f025_r14_los_metodos_de_la_ventana_existen_en_el_cliente() -> None:
    """Contraste: si el nombre de un método cambiara, los tests de arriba
    seguirían en verde leyendo constantes que ya no usa nadie."""
    for metodo in (
        "fetch_censo_de_obras",
        "fetch_firma_origen",
        "fetch_ultima_reconstruccion_completa",
        "fetch_obras_con_filas",
        "registrar_obras_construidas",
        "marcar_obras_congeladas",
        "registrar_firmas_actuales",
        "vacuum_analyze",
    ):
        assert callable(getattr(cliente.PostgresClient, metodo))
