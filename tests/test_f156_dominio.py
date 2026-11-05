# tests/test_f156_dominio.py
"""
F-156 · El dominio de postventa (`etl_sigrid/domain/postventa.py`): el ORÁCULO de
R8 (fin de garantía por clase), R13 (máscara de teléfonos y correos), R15-R16
(origen de la fecha del estado y días), R20 (familia del adjunto) y R25 (obra de
origen de una partida de las obras de postventa).

Sin red ni BBDD. Los literales del SQL se comparan con estos en
`tests/test_f156_ingesta_sql.py`.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from etl_sigrid.domain import postventa as pv

# ===========================================================================
# Constantes
# ===========================================================================


def test_f156_r18_tipos_y_estados() -> None:
    assert (pv.TIPO_UNIDAD, pv.TIPO_INCIDENCIA, pv.TIPO_TAREA) == (707, 708, 47)
    assert pv.TIPOS_POSTVENTA == (47, 707, 708)
    assert pv.ESTADOS_ABIERTOS == (1, 3)
    assert pv.ESTADOS_RESOLUCION == (5, 7, 9)
    assert pv.ESTADO_CERRADA == 9
    assert pv.ESTADO_ALTA == 1
    assert pv.GRATIPIDE_REPARACION == 35
    assert pv.ORIGENES_FECHA == ("PASO", "CIERRE_APLICACION", "ALTA", "SIN_HISTORIAL")
    assert pv.LIGAS_COSTE == ("PARTIDA", "ANCESTRO", "SIN_OBRA")
    assert pv.TEXTO_CIERRE_APLICACION == "Cerrar parte (postventa-incidencias)"


def test_f156_r3_columnas_de_per() -> None:
    assert pv.COLUMNAS_PER == ("ide", "nom", "tel", "tel2", "ele")
    for prohibida in ("dni", "esiglog", "esigpas", "clamai", "dir", "dir1", "dir2", "tex",
                      "dirtex"):
        assert prohibida in pv.COLUMNAS_PER_PROHIBIDAS
    assert not set(pv.COLUMNAS_PER) & pv.COLUMNAS_PER_PROHIBIDAS


def test_f156_r20_familias() -> None:
    assert pv.FAMILIAS_ADJUNTOS == ("INCIDENCIA", "REPARACION", "UNIDAD", "TAREA")
    assert pv.ORIGEN_POR_FAMILIA == {
        "INCIDENCIA": "postventa.incidencias.incidencia_id",
        "UNIDAD": "postventa.unidades.unidad_id",
        "TAREA": "postventa.tareas.tarea_id",
        "REPARACION": "postventa_restringida.contactos_incidencia.incidencia_id",
    }


# ===========================================================================
# R8 · fin de garantía por clase
# ===========================================================================

FIN1 = date(2027, 9, 18)
FIN2 = date(2029, 9, 18)


@pytest.mark.parametrize(
    ("clase", "esperado"),
    [("0001", FIN1), ("0002", FIN2), ("0003", None), (None, None), ("", None), ("9999", None)],
)
def test_f156_r8_fin_garantia(clase: str | None, esperado: date | None) -> None:
    assert pv.fin_garantia(clase, FIN1, FIN2) == esperado


def test_f156_r8_fin_garantia_recorta_espacios() -> None:
    assert pv.fin_garantia(" 0001 ", FIN1, FIN2) == FIN1


def test_f156_r8_columna_de_cada_clase() -> None:
    assert pv.CLASE_FIN_GARANTIA == {"0001": "fecfin1", "0002": "fecfin2"}


@pytest.mark.parametrize(
    ("alta", "fin", "esperado"),
    [
        (date(2027, 9, 18), FIN1, True),    # el mismo día: dentro (<=)
        (date(2027, 9, 19), FIN1, False),
        (date(2020, 1, 1), FIN1, True),
        (None, FIN1, None),
        (date(2020, 1, 1), None, None),
    ],
)
def test_f156_r8_dentro_garantia(alta, fin, esperado) -> None:
    assert pv.dentro_garantia(alta, fin) is esperado


# ===========================================================================
# R13 · la máscara
# ===========================================================================


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("llamar al 612345678 por la tarde", "llamar al [TELEFONO] por la tarde"),
        ("tel 912 34 56 78", "tel [TELEFONO]"),
        ("fijo 712345678 y movil 812 34 56 78", "fijo [TELEFONO] y movil [TELEFONO]"),
        ("escribir a ana.perez@correo.es ya", "escribir a [CORREO] ya"),
        ("612345678@correo.es", "[CORREO]"),
        ("codigo 512345678 no es telefono", "codigo 512345678 no es telefono"),
        ("12345678", "12345678"),
        ("sin datos", "sin datos"),
        ("", ""),
        (None, None),
    ],
)
def test_f156_r13_enmascarar(texto: str | None, esperado: str | None) -> None:
    assert pv.enmascarar(texto) == esperado


def test_f156_r13_marcas() -> None:
    assert (pv.MARCA_TELEFONO, pv.MARCA_CORREO) == ("[TELEFONO]", "[CORREO]")


# ===========================================================================
# R15-R16 · origen de la fecha y días
# ===========================================================================

M1 = datetime(2025, 1, 10, 9, 0)
M2 = datetime(2026, 9, 12, 10, 0)


@pytest.mark.parametrize(
    ("estado", "destino", "momento", "cierre", "esperado"),
    [
        (9, 9, M1, None, "PASO"),
        (3, 3, M1, None, "PASO"),
        (9, 9, M1, M2, "PASO"),                    # PASO gana aunque haya cierre
        (9, 3, M1, M2, "CIERRE_APLICACION"),       # cierre posterior al último paso
        (9, 5, M2, M1, "SIN_HISTORIAL"),           # cierre ANTERIOR al último paso
        (9, None, None, M2, "CIERRE_APLICACION"),  # sin pasos y con cierre
        (9, 3, None, M2, "CIERRE_APLICACION"),     # paso sin momento
        (3, 1, M1, M2, "SIN_HISTORIAL"),           # el cierre solo explica el 9
        (1, None, None, None, "ALTA"),
        (1, 3, M1, None, "SIN_HISTORIAL"),         # con pasos ya no es ALTA
        (9, None, None, None, "SIN_HISTORIAL"),
        (5, None, None, None, "SIN_HISTORIAL"),
    ],
)
def test_f156_r15_origen_fecha(estado, destino, momento, cierre, esperado) -> None:
    assert pv.origen_fecha(estado, destino, momento, cierre) == esperado


@pytest.mark.parametrize(("estado", "esperado"), [(1, True), (3, True), (5, False),
                                                  (7, False), (9, False), (None, False)])
def test_f156_r16_esta_abierta(estado, esperado) -> None:
    assert pv.esta_abierta(estado) is esperado


@pytest.mark.parametrize(("estado", "esperado"), [(5, True), (7, True), (9, True),
                                                  (1, False), (3, False)])
def test_f156_r16_es_resolucion(estado, esperado) -> None:
    assert pv.es_resolucion(estado) is esperado


def test_f156_r16_dias_abierta() -> None:
    hoy = date(2026, 11, 4)
    alta = date(2026, 11, 1)
    assert pv.dias_abierta(alta, None, True, hoy) == 3
    assert pv.dias_abierta(alta, date(2026, 11, 2), False, hoy) == 1
    assert pv.dias_abierta(alta, None, False, hoy) is None
    assert pv.dias_abierta(None, None, True, hoy) is None


# ===========================================================================
# R20 · familia del adjunto
# ===========================================================================


@pytest.mark.parametrize(
    ("tip", "gratipide", "esperado"),
    [
        (707, 0, "UNIDAD"),
        (707, 35, "UNIDAD"),       # los 3 PV002 de unidades siguen siendo UNIDAD
        (47, 0, "TAREA"),
        (708, 35, "REPARACION"),
        (708, 0, "INCIDENCIA"),
        (708, None, "INCIDENCIA"),
        (708, 34, "INCIDENCIA"),
        (15, 0, None),
    ],
)
def test_f156_r20_familia_adjunto(tip, gratipide, esperado) -> None:
    assert pv.familia_adjunto(tip, gratipide) == esperado


# ===========================================================================
# R25 · obra de origen de una partida
# ===========================================================================


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        ("0561 ", "0561"),
        ("0593B", "0593"),
        ("0613-B", "0613"),
        ("626", "0626"),
        ("0342", "0342"),
        (" 0592", "0592"),
        ("CI.1.2", None),
        ("CD", None),
        ("12", None),        # dos cifras: no es una obra
        ("12345", None),     # cinco cifras: tampoco
        ("", None),
        (None, None),
    ],
)
def test_f156_r25_obra_de_partida(codigo, esperado) -> None:
    assert pv.obra_de_partida(codigo) == esperado


def test_f156_r25_liga_coste() -> None:
    assert pv.liga_coste(["0592", "CD"]) == ("PARTIDA", "0592")
    assert pv.liga_coste(["CD.1", "0593B", "CD"]) == ("ANCESTRO", "0593")
    assert pv.liga_coste(["CI.1", "CI"]) == ("SIN_OBRA", None)
    assert pv.liga_coste([]) == ("SIN_OBRA", None)
    # con la lista de obras de la empresa: un código sin obra no liga
    assert pv.liga_coste(["0999", "0592"], obras={"0592"}) == ("ANCESTRO", "0592")
    assert pv.liga_coste(["0999"], obras={"0592"}) == ("SIN_OBRA", None)


def test_f156_r11_palabras_prohibidas_del_general() -> None:
    assert pv.PALABRAS_PROHIBIDAS_GENERAL == (
        "telefono", "correo", "dni", "reclamante", "contacto", "propietario_nombre",
    )
