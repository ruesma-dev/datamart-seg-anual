# tests/test_f042_huella.py
"""
F-042 · La huella antes/después y su veredicto (R22 a R25).

Es **la prueba que decide**, por requisito del humano del 2026-08-29: «hay que
probar que el mensual y el acumulado de las obras no afectadas no cambie», «con
el mismo raw», «en los 4 ámbitos para estar seguro». No decide que los tests
pasen: decide que el dato de las obras que nadie tocó no se mueva ni un céntimo.

Aquí se prueban las tres piezas que se pueden probar sin base: la comparación,
el veredicto y el ida y vuelta del CSV. Ejecutarla contra `sigrid_dm` es T14 a
T17 y **lo hace el humano**.

Un detalle que no es cosmético: el veredicto tiene que **fallar por dos motivos
distintos** —que se mueva una obra que no estaba en la lista, y que se mueva
algo en los ámbitos 8 u 11—. El segundo es el que demuestra que el arreglo no se
desborda, porque esos dos ámbitos hoy no tienen ni una clave duplicada y su
resultado esperado es cero cambios.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain.huella import (
    AMBITOS_DE_LA_HUELLA,
    FilaHuella,
    comparar_huellas,
    veredicto,
)
from etl_sigrid.infrastructure.postgres.huella_obras import escribir_csv, leer_csv

FEBRERO = date(2018, 2, 1)
ENERO = date(2018, 1, 1)


def _fila(
    obra_id: int = 584748,
    codigo: str = "0499",
    ambito: int = 3,
    periodo: date = FEBRERO,
    filas: int = 120,
    versiones: str = "21",
    importe_mes: str = "975249.98",
    importe_origen: str = "5688073.92",
) -> FilaHuella:
    return FilaHuella(
        obra_id=obra_id,
        codigo_obra=codigo,
        ambito_id=ambito,
        periodo=periodo,
        filas=filas,
        versiones=versiones,
        importe_mes=Decimal(importe_mes),
        importe_origen=Decimal(importe_origen),
    )


#: Una huella de juguete con las cuatro ámbitos y tres obras: la 0499 (afectada)
#: y dos que no lo están, una real y otra master.
ANTES = (
    _fila(versiones="20|21", filas=240, importe_origen="10753384.34"),
    _fila(periodo=ENERO, versiones="18|19", filas=240, importe_origen="8321104.83"),
    _fila(obra_id=700001, codigo="0700", versiones="4", importe_origen="1000.00"),
    _fila(obra_id=700001, codigo="0700", ambito=7, versiones="4", importe_origen="900.00"),
    _fila(obra_id=700001, codigo="0700", ambito=8, versiones="12", importe_origen="1100.00"),
    _fila(obra_id=700001, codigo="0700", ambito=11, versiones="12", importe_origen="1050.00"),
)

#: El mismo `raw`, con la regla aplicada: solo se mueve la 0499.
DESPUES = (
    _fila(versiones="21", filas=120, importe_origen="5688073.92"),
    _fila(periodo=ENERO, versiones="19", filas=120, importe_origen="4712823.94"),
    _fila(obra_id=700001, codigo="0700", versiones="4", importe_origen="1000.00"),
    _fila(obra_id=700001, codigo="0700", ambito=7, versiones="4", importe_origen="900.00"),
    _fila(obra_id=700001, codigo="0700", ambito=8, versiones="12", importe_origen="1100.00"),
    _fila(obra_id=700001, codigo="0700", ambito=11, versiones="12", importe_origen="1050.00"),
)


# ---------------------------------------------------------------------------
# R23 · las dos listas, completas
# ---------------------------------------------------------------------------


def test_f042_r23_dos_huellas_identicas_no_producen_ningun_cambio():
    comparacion = comparar_huellas(ANTES, ANTES)

    assert comparacion.numeracion == ()
    assert comparacion.importes == ()


def test_f042_r23_la_numeracion_que_cambia_se_lista_entera():
    """Las dos celdas de la 0499, no una muestra."""
    comparacion = comparar_huellas(ANTES, DESPUES)

    assert len(comparacion.numeracion) == 2
    assert {c.periodo for c in comparacion.numeracion} == {ENERO, FEBRERO}
    febrero = next(c for c in comparacion.numeracion if c.periodo == FEBRERO)
    assert febrero.antes == "20|21"
    assert febrero.despues == "21"
    assert febrero.codigo_obra == "0499"


def test_f042_r23_los_importes_que_cambian_se_listan_con_su_diferencia():
    comparacion = comparar_huellas(ANTES, DESPUES)

    febrero = next(
        c
        for c in comparacion.importes
        if c.periodo == FEBRERO and c.campo == "importe_origen"
    )
    assert febrero.antes == Decimal("10753384.34")
    assert febrero.despues == Decimal("5688073.92")
    assert febrero.diferencia == Decimal("-5065310.42")


def test_f042_r23_un_importe_mes_que_cambia_se_reporta_por_separado():
    """`importe_mes` e `importe_origen` son dos columnas con dos historias.

    El humano pidió las dos: el acumulado es lo que está doblado, y el mensual es
    lo que un desplazamiento mal hecho rompería. Confundirlas en un solo
    veredicto escondería justo el defecto que la renumeración evita.
    """
    despues = (_fila(importe_mes="1.00"), *ANTES[1:])

    comparacion = comparar_huellas(ANTES, despues)

    campos = {c.campo for c in comparacion.importes if c.periodo == FEBRERO}
    assert "importe_mes" in campos
    assert "importe_origen" in campos


def test_f042_r23_una_celda_que_aparece_o_desaparece_es_un_cambio():
    """Un mes que se esfuma no puede pasar por «sin diferencias»."""
    sin_enero = tuple(f for f in DESPUES if f.periodo != ENERO)

    comparacion = comparar_huellas(ANTES, sin_enero)

    desaparecidas = [c for c in comparacion.importes if c.periodo == ENERO]
    assert desaparecidas, "la celda de enero desaparece y no se ha reportado"
    assert comparacion.celdas_antes == 6
    assert comparacion.celdas_despues == 5


def test_f042_r23_la_comparacion_dice_que_ambitos_ha_visto():
    """Si una huella no trae los cuatro, la prueba no cubre lo que dice cubrir."""
    comparacion = comparar_huellas(ANTES, DESPUES)

    assert comparacion.ambitos == AMBITOS_DE_LA_HUELLA == (3, 7, 8, 11)


# ---------------------------------------------------------------------------
# R24 y R25 · el veredicto
# ---------------------------------------------------------------------------

ESPERADAS = ("0246", "0310", "0433", "0462", "0471", "0499", "0545", "0571", "0606")


def test_f042_r24_solo_se_mueve_lo_previsto_y_el_veredicto_sale_0():
    codigo, informe = veredicto(comparar_huellas(ANTES, DESPUES), ESPERADAS)

    assert codigo == 0, informe
    assert "0499" in informe


def test_f042_r24_los_ambitos_8_y_11_salen_con_cero_cambios():
    """La frase que el humano tiene que poder leer sin interpretarla."""
    _, informe = veredicto(comparar_huellas(ANTES, DESPUES), ESPERADAS)

    assert "8" in informe and "11" in informe
    assert "0 cambio" in informe or "cero cambio" in informe


def test_f042_r25_una_obra_fuera_de_la_lista_tumba_el_veredicto():
    despues = (
        *DESPUES[:2],
        _fila(obra_id=700001, codigo="0700", versiones="4", importe_origen="999.00"),
        *DESPUES[3:],
    )

    codigo, informe = veredicto(comparar_huellas(ANTES, despues), ESPERADAS)

    assert codigo != 0
    assert "0700" in informe


def test_f042_r24_un_cambio_en_el_ambito_8_tumba_el_veredicto_aunque_la_obra_este_en_la_lista():
    """El desbordamiento es un fallo distinto de «se movió una obra de más».

    Los ámbitos master no se tocan: su rama del SQL está fijada por hash y hoy no
    tienen ni una clave duplicada. Un cambio ahí significa que el arreglo se ha
    salido de su sitio, y eso no lo tapa una lista de obras esperadas.
    """
    despues = (
        *DESPUES[:4],
        _fila(obra_id=584748, codigo="0499", ambito=8, versiones="12", importe_origen="1.00"),
        *DESPUES[5:],
    )
    antes = (
        *ANTES[:4],
        _fila(obra_id=584748, codigo="0499", ambito=8, versiones="12", importe_origen="1100.00"),
        *ANTES[5:],
    )

    codigo, informe = veredicto(comparar_huellas(antes, despues), ESPERADAS)

    assert codigo != 0
    assert "8" in informe


def test_f042_r24_sin_los_cuatro_ambitos_el_veredicto_no_puede_ser_verde():
    """Una huella a la que le falte un ámbito prueba menos de lo que dice."""
    solo_reales = tuple(f for f in ANTES if f.ambito_id in (3, 7))

    codigo, informe = veredicto(comparar_huellas(solo_reales, solo_reales), ESPERADAS)

    assert codigo != 0
    assert "8" in informe and "11" in informe


def test_f042_r24_dos_huellas_identicas_con_los_cuatro_ambitos_salen_0():
    codigo, informe = veredicto(comparar_huellas(ANTES, ANTES), ESPERADAS)

    assert codigo == 0, informe


def test_f042_r23_el_informe_no_es_una_muestra():
    """Cien obras que se mueven se listan las cien: el humano pidió «la lista
    completa», y un `LIMIT 20` en un informe de no-regresión es una forma
    elegante de no mirar."""
    antes = tuple(
        _fila(obra_id=800000 + n, codigo=f"9{n:03d}", importe_origen="100.00")
        for n in range(100)
    )
    despues = tuple(
        _fila(obra_id=800000 + n, codigo=f"9{n:03d}", importe_origen="200.00")
        for n in range(100)
    )

    _, informe = veredicto(comparar_huellas(antes, despues), ESPERADAS)

    for n in range(100):
        assert f"9{n:03d}" in informe


# ---------------------------------------------------------------------------
# R22 · el CSV, fuera de la base
# ---------------------------------------------------------------------------


def test_f042_r22_el_csv_va_y_vuelve_sin_perder_un_centimo(tmp_path):
    destino = tmp_path / "huella.csv"

    escribir_csv(ANTES, destino)

    assert leer_csv(destino) == list(ANTES)


def test_f042_r22_el_csv_es_el_de_la_casa_utf8_bom_punto_y_coma_y_coma_decimal(tmp_path):
    """Convención de Ruesma: se abre en Excel ES sin tocar nada."""
    destino = tmp_path / "huella.csv"

    escribir_csv(ANTES, destino)
    crudo = destino.read_bytes()

    assert crudo.startswith(b"\xef\xbb\xbf")
    texto = crudo.decode("utf-8-sig")
    assert ";" in texto.splitlines()[0]
    assert "10753384,34" in texto
    assert "10753384.34" not in texto


def test_f042_r22_la_cabecera_nombra_las_ocho_columnas(tmp_path):
    destino = tmp_path / "huella.csv"

    escribir_csv(ANTES, destino)
    cabecera = destino.read_text(encoding="utf-8-sig").splitlines()[0]

    assert cabecera.split(";") == [
        "obra_id",
        "codigo_obra",
        "ambito_id",
        "periodo",
        "filas",
        "versiones",
        "importe_mes",
        "importe_origen",
    ]


def test_f042_r22_un_csv_vacio_se_lee_como_lista_vacia_y_no_como_verde(tmp_path):
    """Una huella vacía comparada con otra vacía da cero diferencias, y eso NO
    puede leerse como que nada cambió: el veredicto lo tiene que rechazar por no
    traer los cuatro ámbitos."""
    destino = tmp_path / "huella.csv"
    escribir_csv((), destino)

    assert leer_csv(destino) == []
    codigo, _ = veredicto(comparar_huellas([], []), ESPERADAS)
    assert codigo != 0


def test_f042_la_fila_de_huella_es_inmutable():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        _fila().filas = 1  # type: ignore[misc]
