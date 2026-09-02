# tests/test_f025_firma.py
"""
F-025 · La firma del origen y el sello del SQL (R16, R17, R20).

Las dos son hashes deterministas, y las dos tienen el **mismo modo de fallo
silencioso**: si cambian solas, denuncian obras que no se han movido o
reconstruyen las 920 sin motivo; si no cambian cuando deben, el dato se queda
viejo y nadie se entera. Por eso los bordes van aquí uno a uno.

El caso que más cuesta ver, y por el que existe la mitad de este fichero: un
`git checkout` en Windows con `core.autocrlf` cambia los finales de línea de un
`.sql` **sin cambiar una coma de su lógica**. Sin normalizar, ese checkout
reconstruiría las 920 obras esa noche, con el servidor sin créditos, creyendo que
el SQL cambió.

Sin BBDD y sin ficheros: los agregados entran como diccionario y el SQL como
texto.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from etl_sigrid.domain.ventana import firma_de_obra, sello_sql

AGREGADOS = {
    "filas": 108790,
    "suma_can": Decimal("1234.560000"),
    "suma_pre": Decimal("987.65"),
    "suma_impcoe": Decimal("0"),
    "max_fas": 21,
    "filas_partidas": 1440,
    "filas_fases": 37,
}


# ---------------------------------------------------------------------------
# R16 · La firma del origen
# ---------------------------------------------------------------------------


def test_f025_r16_la_firma_es_determinista() -> None:
    assert firma_de_obra(AGREGADOS) == firma_de_obra(dict(AGREGADOS))


def test_f025_r16_la_firma_no_depende_del_orden_de_las_columnas() -> None:
    """Las claves se ordenan, así que reordenar el `SELECT` de
    `SQL_FIRMA_ORIGEN` no puede denunciar las 880 obras congeladas de golpe."""
    al_reves = dict(reversed(list(AGREGADOS.items())))

    assert firma_de_obra(al_reves) == firma_de_obra(AGREGADOS)


def test_f025_r16_un_solo_agregado_distinto_cambia_la_firma() -> None:
    movida = dict(AGREGADOS, filas=108791)

    assert firma_de_obra(movida) != firma_de_obra(AGREGADOS)


def test_f025_r16_un_importe_que_cambia_al_centimo_cambia_la_firma() -> None:
    movida = dict(AGREGADOS, suma_pre=Decimal("987.66"))

    assert firma_de_obra(movida) != firma_de_obra(AGREGADOS)


def test_f025_r16_el_mismo_numero_con_otra_escala_da_la_MISMA_firma() -> None:  # noqa: N802
    """`Decimal('987.65')` y `Decimal('987.650000')` son el mismo importe.

    Postgres puede devolver una escala u otra según el plan que elija, y sin la
    normalización la firma cambiaría sola. Una firma que da falsos positivos se
    acaba ignorando, que es peor que no tenerla.
    """
    otra_escala = dict(AGREGADOS, suma_pre=Decimal("987.650000"))

    assert firma_de_obra(otra_escala) == firma_de_obra(AGREGADOS)


def test_f025_r16_un_entero_grande_no_se_rinde_en_notacion_cientifica() -> None:
    """`Decimal('1000').normalize()` es `1E+3`. Si eso entrara en el hash, la
    firma dependería de cómo Postgres formatee, no del valor."""
    a = firma_de_obra({"x": Decimal("1000")})
    b = firma_de_obra({"x": Decimal("1000.00")})

    assert a == b


def test_f025_r16_un_agregado_nulo_no_es_lo_mismo_que_un_cero() -> None:
    """Obra sin filas (`NULL`) y obra con filas que suman cero son estados
    distintos, y confundirlos dejaría de denunciar la transición entre ellos."""
    nulo = firma_de_obra(dict(AGREGADOS, suma_impcoe=None))
    cero = firma_de_obra(dict(AGREGADOS, suma_impcoe=Decimal("0")))

    assert nulo != cero


def test_f025_r16_un_agregado_nulo_no_es_lo_mismo_que_una_cadena_vacia() -> None:
    assert firma_de_obra({"x": None}) != firma_de_obra({"x": ""})


def test_f025_r16_el_NOMBRE_del_agregado_entra_en_la_firma() -> None:  # noqa: N802
    """Mover un valor de una columna a otra tiene que cambiar la firma, y añadir
    un agregado nuevo tiene que cambiarlas todas: el significado de la firma ha
    cambiado, y la primera noche se reconstruye todo. Es lo correcto."""
    assert firma_de_obra({"a": 1, "b": 2}) != firma_de_obra({"a": 2, "b": 1})
    assert firma_de_obra({"a": 1}) != firma_de_obra({"a": 1, "b": None})


def test_f025_r16_la_firma_es_un_sha256_hexadecimal() -> None:
    firma = firma_de_obra(AGREGADOS)

    assert len(firma) == 64
    assert set(firma) <= set("0123456789abcdef")


def test_f025_r16_una_obra_sin_agregados_tiene_firma_y_no_revienta() -> None:
    """Una obra que no está en `raw` sale del `LEFT JOIN` con todo a nulo. Que
    eso tenga firma es lo que permite compararla la noche siguiente."""
    assert len(firma_de_obra({})) == 64


def test_f025_r16_las_fechas_entran_de_forma_estable() -> None:
    assert firma_de_obra({"f": date(2026, 9, 2)}) == firma_de_obra(
        {"f": date(2026, 9, 2)}
    )
    assert firma_de_obra({"f": date(2026, 9, 2)}) != firma_de_obra(
        {"f": date(2026, 9, 3)}
    )
    assert len(firma_de_obra({"f": datetime(2026, 9, 2, 3, 17, 1)})) == 64


# ---------------------------------------------------------------------------
# R17 · El sello del SQL
# ---------------------------------------------------------------------------

SQL_A = "SELECT 1;\nSELECT 2;\n"
SQL_B = "SELECT 3;\n"


def test_f025_r17_el_sello_es_determinista() -> None:
    assert sello_sql([SQL_A, SQL_B]) == sello_sql([SQL_A, SQL_B])


def test_f025_r17_cambiar_una_coma_del_sql_cambia_el_sello() -> None:
    assert sello_sql([SQL_A + "-- x\n", SQL_B]) != sello_sql([SQL_A, SQL_B])


def test_f025_r17_cambiar_un_COMENTARIO_tambien_cambia_el_sello() -> None:  # noqa: N802
    """Deliberado. Se podría ignorar los comentarios, pero eso exige parsear
    SQL, y equivocarse ahí significa NO reconstruir cuando había que hacerlo.
    Reconstruir de más por un comentario cuesta una noche; no reconstruir deja
    un dato falso publicado."""
    assert sello_sql(["SELECT 1 -- viejo\n"]) != sello_sql(["SELECT 1 -- nuevo\n"])


def test_f025_r17_los_finales_de_linea_NO_cambian_el_sello() -> None:  # noqa: N802
    """**El test que evita una nocturna entera de trabajo inútil.** Un
    `git checkout` en Windows con `core.autocrlf` convierte los `\\n` de un
    `.sql` en `\\r\\n` sin cambiar su lógica."""
    assert sello_sql([SQL_A.replace("\n", "\r\n")]) == sello_sql([SQL_A])
    assert sello_sql([SQL_A.replace("\n", "\r")]) == sello_sql([SQL_A])


def test_f025_r17_un_BOM_al_principio_tampoco_cambia_el_sello() -> None:  # noqa: N802
    assert sello_sql(["﻿" + SQL_A]) == sello_sql([SQL_A])


def test_f025_r17_el_ORDEN_de_los_ficheros_importa() -> None:  # noqa: N802
    """A diferencia de la firma, aquí el orden SÍ es significativo: son dos
    ficheros distintos y el sello identifica al par, no al conjunto."""
    assert sello_sql([SQL_A, SQL_B]) != sello_sql([SQL_B, SQL_A])


def test_f025_r17_dos_ficheros_no_se_confunden_con_uno_concatenado() -> None:
    """Sin un separador que no pueda aparecer dentro de un `.sql`, partir un
    fichero en dos por la mitad daría el mismo sello."""
    assert sello_sql(["SELECT 1;", "SELECT 2;"]) != sello_sql(["SELECT 1;SELECT 2;"])


def test_f025_r17_los_parametros_del_build_entran_en_el_sello() -> None:
    """R17 lo dice: «hash de `08_plan_mensual.sql` y de los PARÁMETROS del
    build». Cambiar `cod_version_master_vigente` cambia lo que se construye
    aunque el SQL sea byte a byte el mismo."""
    a = sello_sql([SQL_A], {"cod": "15"})
    b = sello_sql([SQL_A], {"cod": "17"})

    assert a != b
    assert a != sello_sql([SQL_A])


def test_f025_r17_el_orden_de_los_parametros_no_importa() -> None:
    assert sello_sql([SQL_A], {"a": 1, "b": 2}) == sello_sql([SQL_A], {"b": 2, "a": 1})


def test_f025_r17_sin_parametros_o_con_diccionario_vacio_es_lo_mismo() -> None:
    assert sello_sql([SQL_A], {}) == sello_sql([SQL_A])
    assert sello_sql([SQL_A], None) == sello_sql([SQL_A])


def test_f025_r17_el_sello_es_un_sha256_hexadecimal() -> None:
    sello = sello_sql([SQL_A, SQL_B])

    assert len(sello) == 64
    assert set(sello) <= set("0123456789abcdef")


def test_f025_r17_el_sello_del_sql_REAL_del_repositorio_se_calcula() -> None:
    """Contraste de realidad: no basta con que funcione sobre cadenas de
    juguete. Se sella el SQL que ejecuta la nocturna de verdad."""
    from etl_sigrid.application.steps.build_stg_step import (
        DIRECTORIO_SQL_STG,
        FICHEROS_DEL_SELLO,
    )

    textos = [
        (DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8")
        for nombre in FICHEROS_DEL_SELLO
    ]

    assert len(textos) == 2
    assert all(texto.strip() for texto in textos)
    assert len(sello_sql(textos, {"cod": "15"})) == 64
