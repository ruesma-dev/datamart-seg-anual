# tests/test_f025_huella.py
"""
F-025 · La quinta huella `plan_obra` (T21, T22, R21, R22).

**Qué añade sobre las cuatro de F-052.** Aquellas comparan el resultado
publicado —`stg` agregada, el fact, el árbol de partidas, el cierre—. Esta
compara **la tabla que la ventana deja de reconstruir**, obra a obra y ámbito a
ámbito, que es donde el daño de esta feature sería directo. Si una obra
congelada perdiera filas o importes, aquí se vería aunque `mart` y `cierre`
salieran idénticos por casualidad.

Es literalmente lo que pidió el humano: *«que no se reconstruyan, pero que **no
se borren**»*. Las cuatro primeras prueban que lo publicado no cambia; esta
prueba que **el dato sigue ahí**.

El criterio es el de F-052: **tolerancia CERO**. Cualquier diferencia en una
obra fuera de `--obras-esperadas` detiene la feature, y aquí no hay obras
esperadas: si la exclusión es correcta, las cinco salen idénticas.

Sin BBDD: la consulta se lee como texto y la comparación va sobre CSV.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from etl_sigrid.domain.huella_ampliada import (
    FORMATO_PLAN_OBRA,
    FORMATOS,
    FilaAmpliada,
    comparar_ampliada,
    formato_de,
    veredicto_ampliado,
)
from etl_sigrid.infrastructure.postgres.huella_ampliada import (
    escribir_csv_ampliada,
    leer_csv_ampliada,
    sql_huella_plan_obra,
)


def fila(
    obra_id: str = "1442383",
    codigo: str = "0599",
    ambito: str = "3",
    filas: str = "19328",
    importe: str = "2624793,00",
) -> FilaAmpliada:
    return FilaAmpliada(
        codigo_obra=codigo,
        clave=(obra_id, ambito),
        valores=(("codigo_obra", codigo), ("filas", filas), ("importe_origen", importe)),
    )


# ---------------------------------------------------------------------------
# El formato
# ---------------------------------------------------------------------------


def test_f025_r22_la_quinta_huella_esta_declarada() -> None:
    assert FORMATO_PLAN_OBRA in FORMATOS
    assert len(FORMATOS) == 5 - 2, "las dos primeras de F-042 no son `ampliadas`"


def test_f025_r22_su_grano_es_obra_POR_ambito() -> None:  # noqa: N802
    """Por ámbito y no solo por obra: una obra puede perder sus filas del ámbito
    8 y conservar las del 3, y agregando por obra el total podría cuadrar."""
    assert FORMATO_PLAN_OBRA.columnas_clave == ("obra_id", "ambito_id")


def test_f025_r22_compara_filas_E_importe() -> None:  # noqa: N802
    """Las dos: el recuento caza una obra que pierde filas, el importe caza una
    que las conserva con otros valores."""
    assert FORMATO_PLAN_OBRA.columnas_valor == ("codigo_obra", "filas", "importe_origen")


def test_f025_r22_se_reconoce_por_su_cabecera_y_no_por_el_nombre_del_fichero() -> None:
    """Un nombre de fichero cualquiera puede teclearse mal; la cabecera no."""
    assert formato_de(FORMATO_PLAN_OBRA.cabecera) is FORMATO_PLAN_OBRA


def test_f025_r22_una_cabecera_en_otro_orden_NO_se_reconoce() -> None:  # noqa: N802
    """Se rechaza en vez de leerse mal en silencio, que en una prueba de
    no-regresión sería la peor forma posible de dar verde."""
    desordenada = tuple(reversed(FORMATO_PLAN_OBRA.cabecera))

    assert formato_de(desordenada) is None


# ---------------------------------------------------------------------------
# La consulta
# ---------------------------------------------------------------------------


def test_f025_r22_la_consulta_agrupa_por_obra_y_ambito() -> None:
    sql = sql_huella_plan_obra()

    assert "GROUP BY pm.obra_id, pm.ambito_id" in sql
    assert "count(*) AS filas" in sql
    assert "SUM(pm.importe_origen)" in sql


def test_f025_r22_la_consulta_NO_filtra_por_ambito() -> None:  # noqa: N802
    """**La decisión que más importa de esta consulta.** Si se limitara a los
    cuatro ámbitos del fact, una obra congelada podría perder sus filas de los
    otros —6,7 millones en total— sin que esta huella dijera nada. Aquí se
    compara la tabla ENTERA."""
    assert "WHERE" not in sql_huella_plan_obra()
    assert "ambito_id IN" not in sql_huella_plan_obra()


def test_f025_r22_la_consulta_no_escribe_nada() -> None:
    sql = sql_huella_plan_obra().upper()

    for palabra in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP"):
        assert palabra not in sql


def test_f025_r22_una_obra_sin_ficha_en_stg_obras_sigue_saliendo() -> None:
    """`LEFT JOIN`: las obras administrativas no están en `stg.obras` y aun así
    tienen filas en `stg.plan_mensual`. Con un `INNER` desaparecerían de la
    huella y su pérdida sería invisible, que es el defecto de F-052."""
    assert "LEFT JOIN stg.obras" in sql_huella_plan_obra()


def test_f025_r22_la_consulta_sale_ordenada() -> None:
    assert sql_huella_plan_obra().strip().endswith("ORDER BY 1, 3")


# ---------------------------------------------------------------------------
# La comparación, con tolerancia CERO
# ---------------------------------------------------------------------------


def test_f025_r21_dos_huellas_identicas_no_dan_diferencias() -> None:
    comparacion = comparar_ampliada(FORMATO_PLAN_OBRA, [fila()], [fila()])

    assert comparacion.diferencias == ()
    assert veredicto_ampliado(comparacion, [])[0] == 0


def test_f025_r21_una_obra_congelada_que_pierde_filas_DETIENE_la_feature() -> None:  # noqa: N802
    """**El test de esta feature.** Es exactamente el daño que el humano
    prohibió: que una obra que no se reconstruye acabe borrada."""
    comparacion = comparar_ampliada(
        FORMATO_PLAN_OBRA, [fila()], [fila(filas="0", importe="0,00")]
    )

    codigo, informe = veredicto_ampliado(comparacion, [])

    assert codigo == 1
    assert "0599" in informe


def test_f025_r21_una_obra_que_DESAPARECE_entera_se_caza() -> None:  # noqa: N802
    """Se recorre la unión de las claves, no la intersección: una obra que se
    cae del todo pasaría por «sin diferencias» si solo se miraran las comunes."""
    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_PLAN_OBRA, [fila()], []), []
    )

    assert codigo == 1
    assert "(sin fila)" in informe


def test_f025_r21_un_importe_que_cambia_al_centimo_detiene_la_feature() -> None:
    """Tolerancia CERO, y es literal: no hay umbral ni redondeo."""
    comparacion = comparar_ampliada(
        FORMATO_PLAN_OBRA, [fila()], [fila(importe="2624793,01")]
    )

    assert veredicto_ampliado(comparacion, [])[0] == 1


def test_f025_r21_perder_un_ambito_y_conservar_otro_se_caza() -> None:
    """El motivo de que el grano sea obra x ámbito: agregando por obra, una
    pérdida en el ámbito 8 podría compensarse en el informe con el 3."""
    antes = [fila(ambito="3"), fila(ambito="8", filas="18859")]
    despues = [fila(ambito="3")]

    assert veredicto_ampliado(comparar_ampliada(FORMATO_PLAN_OBRA, antes, despues), [])[0] == 1


def test_f025_r21_dos_huellas_VACIAS_no_son_un_verde() -> None:  # noqa: N802
    """El mismo criterio que el guardián y que `check-cobertura`: un cero que no
    compara nada es indistinguible de un cero sobre el datamart entero, y solo
    uno de los dos prueba algo."""
    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_PLAN_OBRA, [], []), []
    )

    assert codigo == 1
    assert "vacias" in informe


# ---------------------------------------------------------------------------
# El ida y vuelta por CSV
# ---------------------------------------------------------------------------


def test_f025_r22_el_csv_se_escribe_y_se_relee_igual(tmp_path: Path) -> None:
    """Escribir y leer con el mismo código es lo que garantiza que el viaje no
    invente una diferencia: la comparación es de cadenas, exacta."""
    filas = [fila(), fila(ambito="7", filas="19328", importe="4066989,23")]
    destino = tmp_path / "huella_plan_obra.csv"

    escribir_csv_ampliada(FORMATO_PLAN_OBRA, filas, destino)
    formato, releidas = leer_csv_ampliada(destino)

    assert formato is FORMATO_PLAN_OBRA
    assert comparar_ampliada(formato, filas, releidas).diferencias == ()


def test_f025_r22_el_csv_va_en_utf8_con_bom_y_punto_y_coma(tmp_path: Path) -> None:
    """Convención de Ruesma: se abre en Excel ES."""
    destino = tmp_path / "huella.csv"
    escribir_csv_ampliada(FORMATO_PLAN_OBRA, [fila()], destino)

    crudo = destino.read_bytes()

    assert crudo.startswith(b"\xef\xbb\xbf")
    assert b";" in crudo


def test_f025_r22_un_csv_de_otra_huella_no_se_confunde_con_esta(tmp_path: Path) -> None:
    destino = tmp_path / "otra.csv"
    destino.write_text("obra_id;codigo_obra;cualquier_cosa\n1;0599;x\n", encoding="utf-8-sig")

    with pytest.raises(ValueError, match="plan_obra"):
        leer_csv_ampliada(destino)


# ---------------------------------------------------------------------------
# T22 · el comando
# ---------------------------------------------------------------------------


def test_f025_r22_huella_obras_admite_la_quinta() -> None:
    from click.testing import CliRunner

    import main

    resultado = CliRunner().invoke(main.cli, ["huella-obras", "--help"])

    assert resultado.exit_code == 0
    assert "plan_obra" in resultado.output


def test_f025_r22_la_quinta_va_por_la_rama_ampliada() -> None:
    """Su forma es la de las huellas nuevas —sin mes, con ámbito— y no la de
    `FilaHuella`. Meterla ahí habría dejado media docena de columnas vacías,
    que es como se acaba comparando ceros contra ceros y llamándolo verde."""
    import main

    assert "plan_obra" in main._FORMATOS_AMPLIADOS
