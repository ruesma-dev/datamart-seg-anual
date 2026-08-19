# tests/test_f011_tiemod.py
"""
F-011 · Tests del diagnóstico de `tiemod`: estado por tabla (R6) y veredicto
`SIRVE` / `NO SIRVE` / `SIN EVIDENCIA` comparando dos cargas (R7).

Aquí se decide si la ingesta incremental es siquiera posible, así que los tres
veredictos tienen test propio y los bordes también: columna toda nula, tabla
vacía, dos fotografías idénticas y la tabla que cambió de contenido sin que
`tiemod` se enterara —que es el caso que descalifica la columna—.

Ninguno abre red ni BBDD: funciones puras sobre fixtures.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from etl_sigrid.domain.tiemod import (
    EstadoTiemod,
    Veredicto,
    comparar_tiemod,
    escribir_csv_tiemod,
    format_comparacion,
    format_diagnostico,
    leer_csv_tiemod,
    veredicto_tiemod,
)

#: Valores realistas: si `tiemod` es una marca de fecha y hora de Sigrid, el
#: número ronda los 46.200 (días desde 1899-12-30 más la fracción del día).
AYER = 46_263.5
HOY = 46_264.75


def estado(
    tabla: str = "obrparpre",
    filas: int = 13_809_350,
    nulos: int = 0,
    minimo: float | None = 40_000.0,
    maximo: float | None = AYER,
    distintos: int = 900_000,
) -> EstadoTiemod:
    return EstadoTiemod(
        tabla=tabla,
        filas=filas,
        nulos=nulos,
        minimo=minimo,
        maximo=maximo,
        distintos=distintos,
    )


# ---------------------------------------------------------------------------
# R6 · Estado de la columna por tabla
# ---------------------------------------------------------------------------


def test_f011_r6_diagnostico_por_tabla() -> None:
    """Las seis cifras de R6, con el porcentaje de nulos calculado."""
    e = estado(filas=1_000, nulos=250)

    assert e.pct_nulos == pytest.approx(25.0)
    assert e.filas == 1_000
    assert e.minimo == 40_000.0
    assert e.maximo == AYER
    assert e.distintos == 900_000


def test_f011_r6_una_tabla_vacia_no_divide_por_cero() -> None:
    """0 filas → 0 % de nulos, no una excepción."""
    e = estado(filas=0, nulos=0, minimo=None, maximo=None, distintos=0)

    assert e.pct_nulos == 0.0
    assert e.esta_vacia is True


def test_f011_r6_columna_toda_nula_se_reconoce() -> None:
    """Si todas las filas tienen `_source_tiemod` nulo, la columna no sirve."""
    e = estado(filas=500, nulos=500, minimo=None, maximo=None, distintos=0)

    assert e.pct_nulos == 100.0
    assert e.toda_nula is True
    # Una tabla vacía NO es una columna toda nula: no hay nada que juzgar.
    assert estado(filas=0, nulos=0).toda_nula is False


def test_f011_r6_el_estado_es_inmutable() -> None:
    with pytest.raises(FrozenInstanceError):
        estado().filas = 1  # type: ignore[misc]


def test_f011_r6_el_informe_lista_las_tablas_con_sus_seis_cifras() -> None:
    """Lo que el humano lee: una línea por tabla y el total al pie."""
    texto = format_diagnostico(
        [estado(tabla="con", filas=2_172_969, nulos=0),
         estado(tabla="cen", filas=802, nulos=802, minimo=None, maximo=None,
                distintos=0)]
    )

    assert "con" in texto and "cen" in texto
    assert "2,172,969" in texto
    assert "100.0" in texto  # el 100 % de nulos de `cen`
    assert "TOTAL" in texto


def test_f011_r6_sin_tablas_el_informe_lo_dice() -> None:
    """Ninguna tabla de `raw` con `_source_tiemod`: no es un error."""
    assert "Ninguna tabla" in format_diagnostico([])


# ---------------------------------------------------------------------------
# R7 · Veredicto comparando dos cargas
# ---------------------------------------------------------------------------


def test_f011_r7_veredicto_sirve_no_sirve_sin_evidencia() -> None:
    """Los tres veredictos de R7, uno por caso, con su condición exacta."""
    antes = estado(filas=13_809_325, maximo=AYER)

    # SIRVE: el máximo global creció y hubo filas que avanzaron.
    ahora = estado(filas=13_809_350, maximo=HOY)
    assert veredicto_tiemod(antes, ahora, filas_avanzadas=25) is Veredicto.SIRVE

    # NO SIRVE: la tabla cambió de contenido y `tiemod` no se movió.
    quieta = estado(filas=13_809_350, maximo=AYER)
    assert veredicto_tiemod(antes, quieta, filas_avanzadas=0) is Veredicto.NO_SIRVE

    # SIN EVIDENCIA: no hay carga anterior con la que comparar.
    assert veredicto_tiemod(None, ahora, filas_avanzadas=None) is Veredicto.SIN_EVIDENCIA


def test_f011_r7_columna_toda_nula_es_no_sirve_aunque_no_haya_con_que_comparar() -> None:
    """Una columna vacía se descalifica sola: no hace falta una segunda carga."""
    nula = estado(filas=500, nulos=500, minimo=None, maximo=None, distintos=0)

    assert veredicto_tiemod(None, nula, filas_avanzadas=None) is Veredicto.NO_SIRVE
    assert veredicto_tiemod(estado(), nula, filas_avanzadas=0) is Veredicto.NO_SIRVE


def test_f011_r7_dos_fotografias_identicas_no_prueban_nada() -> None:
    """Si nada cambió en la tabla, que `tiemod` no cambie no la descalifica.

    Es la diferencia entre «no sirve» y «no lo sé», y confundirlas mandaría a
    la basura una columna buena solo porque esa noche nadie tocó la tabla.
    """
    foto = estado(filas=13_809_350, maximo=AYER)

    assert veredicto_tiemod(foto, foto, filas_avanzadas=0) is Veredicto.SIN_EVIDENCIA


def test_f011_r7_una_tabla_vacia_no_da_veredicto() -> None:
    """Sin filas no hay nada que juzgar."""
    vacia = estado(filas=0, nulos=0, minimo=None, maximo=None, distintos=0)

    assert veredicto_tiemod(estado(), vacia, filas_avanzadas=0) is Veredicto.SIN_EVIDENCIA


def test_f011_r7_sin_maximo_anterior_no_se_puede_comparar() -> None:
    """La foto anterior tenía la columna vacía: no hay punto de partida."""
    antes = estado(filas=100, nulos=100, minimo=None, maximo=None, distintos=0)
    ahora = estado(filas=100, nulos=0, maximo=HOY)

    assert veredicto_tiemod(antes, ahora, filas_avanzadas=5) is Veredicto.SIN_EVIDENCIA


def test_f011_r7_el_maximo_crece_pero_ninguna_fila_avanza_no_es_sirve() -> None:
    """Coherencia entre las dos señales de R7: hacen falta las dos.

    `filas_avanzadas` se mide con una consulta aparte (`COUNT(*)` por encima
    del máximo anterior). Si el máximo creció pero el recuento sale 0, los dos
    números se contradicen y lo honrado es no dar la columna por buena.
    """
    antes = estado(filas=100, maximo=AYER)
    ahora = estado(filas=100, maximo=HOY)

    assert veredicto_tiemod(antes, ahora, filas_avanzadas=0) is Veredicto.SIN_EVIDENCIA
    # Sin ese recuento (comparación de dos CSV a secas), el máximo manda.
    assert veredicto_tiemod(antes, ahora, filas_avanzadas=None) is Veredicto.SIRVE


def test_f011_r7_comparar_empareja_por_tabla_y_no_por_posicion() -> None:
    """Las dos fotos pueden traer distintas tablas y en distinto orden."""
    antes = [estado(tabla="con", filas=100, maximo=AYER),
             estado(tabla="obr", filas=10, maximo=AYER)]
    ahora = [estado(tabla="obr", filas=11, maximo=HOY),
             estado(tabla="con", filas=100, maximo=AYER),
             estado(tabla="dca", filas=7, maximo=HOY)]  # tabla nueva

    comparaciones = {c.tabla: c for c in comparar_tiemod(antes, ahora,
                                                         filas_avanzadas={"obr": 1})}

    assert comparaciones["obr"].veredicto is Veredicto.SIRVE
    assert comparaciones["con"].veredicto is Veredicto.SIN_EVIDENCIA
    # Una tabla que no estaba en la foto anterior no tiene con qué compararse.
    assert comparaciones["dca"].veredicto is Veredicto.SIN_EVIDENCIA
    assert set(comparaciones) == {"con", "obr", "dca"}


def test_f011_r7_una_tabla_nueva_no_tiene_delta_de_filas() -> None:
    """Sin fotografía anterior, la variación es 0 y no una resta contra nada."""
    (comparacion,) = comparar_tiemod([], [estado(tabla="dca", filas=7, maximo=HOY)])

    assert comparacion.antes is None
    assert comparacion.delta_filas == 0
    assert comparacion.veredicto is Veredicto.SIN_EVIDENCIA


def test_f011_r7_el_delta_de_filas_cuenta_altas_y_bajas() -> None:
    """El signo importa: una tabla que encoge es una baja en Sigrid."""
    antes = [estado(tabla="con", filas=100, maximo=AYER)]

    (crecio,) = comparar_tiemod(antes, [estado(tabla="con", filas=118, maximo=HOY)])
    (encogio,) = comparar_tiemod(antes, [estado(tabla="con", filas=95, maximo=HOY)])

    assert crecio.delta_filas == 18
    assert encogio.delta_filas == -5


def test_f011_r7_el_informe_de_comparacion_trae_el_veredicto_por_tabla() -> None:
    """Y el resumen global, que es lo que decide si R19 deja activar el modo."""
    antes = [estado(tabla="obr", filas=10, maximo=AYER)]
    ahora = [estado(tabla="obr", filas=11, maximo=HOY)]

    texto = format_comparacion(
        comparar_tiemod(antes, ahora, filas_avanzadas={"obr": 1})
    )

    assert "obr" in texto
    assert "SIRVE" in texto
    assert "1 SIRVE" in texto


def test_f011_r7_el_informe_sin_comparaciones_lo_dice() -> None:
    assert "Nada que comparar" in format_comparacion([])


# ---------------------------------------------------------------------------
# El CSV de la fotografía: es lo que se compara entre dos cargas
# ---------------------------------------------------------------------------


def test_f011_r7_el_csv_de_la_huella_va_y_vuelve_igual(tmp_path) -> None:
    """Escribir y leer devuelve los mismos datos: si no, la comparación miente."""
    estados = [
        estado(tabla="con", filas=2_172_969, nulos=3, minimo=1.5, maximo=AYER),
        estado(tabla="cen", filas=0, nulos=0, minimo=None, maximo=None, distintos=0),
    ]
    salida = tmp_path / "huella_tiemod.csv"

    escribir_csv_tiemod(estados, salida)
    leidos = leer_csv_tiemod(salida)

    # El fichero se escribe ordenado por tabla a propósito: dos huellas de
    # cargas distintas se comparan mejor —y hasta con `diff`— si el orden no
    # depende de en qué orden respondiera el catálogo.
    assert leidos == sorted(estados, key=lambda e: e.tabla)
    assert [e.tabla for e in leidos] == ["cen", "con"]
    # Convención de Ruesma: UTF-8 con BOM y `;` como separador.
    assert salida.read_bytes().startswith(b"\xef\xbb\xbf")
    assert ";" in salida.read_text(encoding="utf-8-sig").splitlines()[0]


def test_f011_r7_un_csv_que_no_es_una_huella_se_rechaza(tmp_path) -> None:
    """Comparar contra un fichero cualquiera daría un veredicto inventado."""
    otro = tmp_path / "cualquiera.csv"
    otro.write_text("a;b;c\n1;2;3\n", encoding="utf-8-sig")

    with pytest.raises(ValueError, match="huella"):
        leer_csv_tiemod(otro)


def test_f011_r7_un_csv_vacio_no_trae_estados(tmp_path) -> None:
    vacio = tmp_path / "vacio.csv"
    vacio.write_text("", encoding="utf-8-sig")

    assert leer_csv_tiemod(vacio) == []


# ---------------------------------------------------------------------------
# Bordes que la campaña de mutación dejó al descubierto
# ---------------------------------------------------------------------------


def test_f011_r6_una_tabla_de_una_fila_se_juzga_como_las_demas() -> None:
    """Una fila no es «vacía»: las guardias comparan con 0, no con 1.

    `dcfprodes` tiene 271 filas y hay catálogos con menos de diez. Tratar una
    tabla pequeña como si no existiera sería perder justo las que se pueden
    revisar a mano.
    """
    una = estado(tabla="rara", filas=1, nulos=1, minimo=None, maximo=None, distintos=0)

    assert una.esta_vacia is False
    assert una.pct_nulos == 100.0
    assert una.toda_nula is True

    con_marca = estado(tabla="rara", filas=1, nulos=0, maximo=HOY, distintos=1)
    assert con_marca.toda_nula is False
    assert con_marca.pct_nulos == 0.0


def test_f011_r7_la_comparacion_es_inmutable() -> None:
    """El veredicto de una tabla no se reescribe después de emitirse."""
    (comparacion,) = comparar_tiemod([], [estado(tabla="con", filas=1, maximo=HOY)])

    with pytest.raises(FrozenInstanceError):
        comparacion.veredicto = Veredicto.SIRVE  # type: ignore[misc]


def test_f011_r7_el_motivo_del_no_sirve_dice_cuanto_cambio_la_tabla() -> None:
    """«cambió de contenido (+18 filas)»: el número es el argumento.

    Sin él, el veredicto es una opinión; con él, quien lo lee puede
    comprobarlo. Y la resta tiene que ser resta: sumar las dos fotos daría un
    número enorme y sin sentido.
    """
    antes = [estado(tabla="con", filas=100, maximo=AYER)]
    ahora = [estado(tabla="con", filas=118, maximo=AYER)]

    (comparacion,) = comparar_tiemod(antes, ahora, filas_avanzadas={"con": 0})

    assert comparacion.veredicto is Veredicto.NO_SIRVE
    assert "+18 filas" in comparacion.motivo


def test_f011_r6_el_total_del_informe_reparte_los_nulos() -> None:
    """El pie del diagnóstico calcula el porcentaje global, y sabe dividir."""
    texto = format_diagnostico(
        [
            estado(tabla="a", filas=3, nulos=3, minimo=None, maximo=None, distintos=0),
            estado(tabla="b", filas=1, nulos=0, maximo=HOY, distintos=1),
        ]
    )

    total = next(x for x in texto.splitlines() if x.startswith("TOTAL"))

    assert "75.0" in total, f"3 nulos de 4 filas son el 75 %: {total}"


def test_f011_r6_el_total_con_todas_las_tablas_vacias_no_divide_por_cero() -> None:
    """Base recién creada: todas las tablas a 0 filas. 0 %, no una excepción."""
    texto = format_diagnostico(
        [estado(tabla="a", filas=0, nulos=0, minimo=None, maximo=None, distintos=0)]
    )

    total = next(x for x in texto.splitlines() if x.startswith("TOTAL"))

    assert "0.0" in total


def test_f011_r6_una_sola_fila_nula_da_el_cien_por_cien_en_el_total() -> None:
    """Total de 1 fila: el porcentaje sigue siendo 100 %, no 0 %."""
    texto = format_diagnostico(
        [estado(tabla="a", filas=1, nulos=1, minimo=None, maximo=None, distintos=0)]
    )

    total = next(x for x in texto.splitlines() if x.startswith("TOTAL"))

    assert "100.0" in total


def test_f011_r7_el_csv_crea_los_directorios_que_falten(tmp_path) -> None:
    """`--out informes/2026/huella.csv` no puede fallar por una carpeta ausente."""
    salida = tmp_path / "informes" / "2026" / "huella.csv"

    escribir_csv_tiemod([estado(tabla="con", filas=1, maximo=HOY)], salida)

    assert salida.is_file()


def test_f011_r7_el_error_del_csv_ensena_la_cabecera_encontrada(tmp_path) -> None:
    """El mensaje trae la cabecera REAL del fichero, no la de otra fila.

    Es lo que convierte «este CSV no vale» en «has pasado el fichero del bench
    en vez de la huella».
    """
    otro = tmp_path / "cualquiera.csv"
    otro.write_text("page_size;peticiones;filas\n1000;1;1000\n", encoding="utf-8-sig")

    with pytest.raises(ValueError) as excinfo:
        leer_csv_tiemod(otro)

    assert "page_size;peticiones;filas" in str(excinfo.value)


def test_f011_r7_cada_columna_del_csv_va_a_su_campo(tmp_path) -> None:
    """Mínimo y máximo se leen por separado: uno puede faltar y el otro no.

    Un fichero editado a mano —o truncado— puede traer justo eso, y confundir
    las dos columnas daría un veredicto con el umbral equivocado.
    """
    huella = tmp_path / "huella.csv"
    huella.write_text(
        "tabla;filas;nulos;minimo;maximo;distintos\ncon;10;0;;46264.75;3\n",
        encoding="utf-8-sig",
    )

    (leido,) = leer_csv_tiemod(huella)

    assert leido.minimo is None
    assert leido.maximo == pytest.approx(46_264.75)
