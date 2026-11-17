# tests/test_f164_dominio.py
"""
F-164 · Los partes firmados de postventa, siempre en la familia restringida
(R1-R8), sobre la función pura del dominio `familia_publicada`.

La regla (design §3): un enlace solo queda ABIERTO si su pareja (tipo de
documento, clase de gráfico) está en la LISTA ABIERTA —PV001 en incidencia,
PV006 en unidad, PV004 en tarea— y ni su nombre ni su descripción dan la señal
de firma, ni su nombre la del código de incidencia. Todo lo demás, REPARACION.

Fixture SINTÉTICA (ningún dato real): las formas de nombre de los 7 ficheros
que el líder midió el 2026-11-16 fuera de REPARACION (`progress/spec_F-164.md`
§3), con números inventados.
"""

from __future__ import annotations

import re

import pytest

from etl_sigrid.domain import postventa as pv

INC, UNI, TAR = 708, 707, 47
PV001, PV002, PV004, PV005, PV006 = 34, 35, 37, 38, 39

# ---------------------------------------------------------------------------
# Fixture de los 7 (R8): (tipo, clase, nombre, descripción)
# ---------------------------------------------------------------------------

LOS_SIETE: tuple[tuple[int, int | None, str, str | None], ...] = (
    (INC, None, "VIV 1 - RS24.11-0123.pdf", "PARTE FIRMADO"),
    (INC, None, "B1C - RS24.11-0456.pdf", "PARTE FIRMADO"),
    (INC, PV001, "RS25.07 - 0321 FIRMADO.pdf", "PARTE FIRMADO"),
    (INC, None, "0601 - RS26.10 - 0789 PARTE FIRMADO.pdf", None),
    (UNI, PV002, "VIV 2 - RS24.11-0124.pdf", "PARTE FIRMADO"),
    (UNI, PV002, "B2D - RS24.11-0457.pdf", "PARTE FIRMADO"),
    (UNI, PV002, "VIV 3 - RS24.12-0125.pdf", "PARTE FIRMADO"),
)

#: Los que deben quedar ABIERTOS, con su familia por documento (R3).
CONTROLES_ABIERTOS: tuple[tuple[int, int, str | None, str | None, str], ...] = (
    (INC, PV001, "20250312_101010.jpg", None, "INCIDENCIA"),
    (INC, PV001, "20250312_101011.jpg", "PARTE TRASERA DEL ARMARIO", "INCIDENCIA"),
    (INC, PV001, "foto_salon.jpg", "CONFIRMADO POR EL JEFE DE OBRA", "INCIDENCIA"),
    (INC, PV001, "3f2a9c1e-0b7d-4e55-9a10-1c2d3e4f5a6b.pdf", "", "INCIDENCIA"),
    (UNI, PV006, "0601_02_03_04_PRIMERA_HAB1.pdf", None, "UNIDAD"),
    (TAR, PV004, "1_2_3_4_TAR_PRV_RCP.pdf", None, "TAREA"),
    (TAR, PV004, "1_2_3_4_TAR_PARTE_DE_TRABAJOS.pdf", "Informe", "TAREA"),
)


# ===========================================================================
# Constantes (design §3)
# ===========================================================================


def test_f164_r1_la_lista_abierta_son_tres_parejas() -> None:
    assert pv.GRATIPIDE_FOTOS_INCIDENCIA == PV001
    assert pv.GRATIPIDE_INFORMES == PV004
    assert pv.GRATIPIDE_FICHA_INMUEBLE == PV006
    assert frozenset({(INC, PV001), (UNI, PV006), (TAR, PV004)}) == pv.LISTA_ABIERTA


def test_f164_r9_los_patrones_son_los_de_la_spec() -> None:
    assert pv.PATRON_SENAL_FIRMA == r"(^|[^A-ZÁÉÍÓÚÑÜ])FIRMA(D|S?([^A-ZÁÉÍÓÚÑÜ]|$))"
    assert pv.PATRON_SENAL_CODIGO == r"RS\s*[0-9]{2}\.[0-9]{2}\s*[-/_. ]\s*[0-9]{3,5}"
    # Ni `\b` ni `\m`/`\y` ni clases POSIX: el mismo texto vale en el ARE de PostgreSQL.
    for patron in (pv.PATRON_SENAL_FIRMA, pv.PATRON_SENAL_CODIGO):
        assert "\\b" not in patron and "\\m" not in patron and "\\y" not in patron
        assert "[:" not in patron and "'" not in patron
        re.compile(patron)


# ===========================================================================
# R8 · Los 7 del líder, en ROJO sobre el código de hoy
# ===========================================================================


@pytest.mark.parametrize("tip, clase, nombre, descripcion", LOS_SIETE)
def test_f164_r8_los_siete_partes_quedan_en_reparacion(
    tip: int, clase: int | None, nombre: str, descripcion: str | None
) -> None:
    assert pv.familia_publicada(tip, clase, nombre, descripcion) == "REPARACION"


def test_f164_r8_la_regla_de_hoy_los_dejaba_abiertos() -> None:
    """La fixture tiene sentido: con la familia por documento (F-156) ninguno es REPARACION."""
    for tip, clase, _nombre, _desc in LOS_SIETE:
        assert pv.familia_adjunto(tip, clase) != "REPARACION"


# ===========================================================================
# R1 / R5 / R6 · Fuera de la lista abierta, siempre REPARACION
# ===========================================================================


@pytest.mark.parametrize("tip, clase", [
    (INC, None), (INC, 0), (INC, PV002), (INC, PV004), (INC, PV005), (INC, PV006),
    (INC, 36), (INC, 40), (INC, 999),
    (UNI, None), (UNI, 0), (UNI, PV001), (UNI, PV002), (UNI, PV004), (UNI, PV005), (UNI, 40),
    (TAR, None), (TAR, 0), (TAR, PV001), (TAR, PV002), (TAR, PV005), (TAR, PV006), (TAR, 40),
])
@pytest.mark.parametrize("nombre, descripcion", [
    ("UNTITLED_1_2.pdf", None),
    ("foto.jpg", "Foto del salon"),
    ("video.mp4", None),
    ("correo.msg", ""),
    (None, None),
    ("0601_02_03_04_PRIMERA_HAB1.pdf", None),
])
def test_f164_r1_r5_r6_fuera_de_la_lista_es_reparacion_sin_mirar_el_texto(
    tip: int, clase: int | None, nombre: str | None, descripcion: str | None
) -> None:
    assert pv.familia_publicada(tip, clase, nombre, descripcion) == "REPARACION"


def test_f164_r5_una_clase_nueva_no_abre_nada() -> None:
    usadas = {c for _t, c in pv.LISTA_ABIERTA}
    for clase in range(0, 200):
        for tip in pv.TIPOS_POSTVENTA:
            esperado = (
                pv.familia_adjunto(tip, clase) if (tip, clase) in pv.LISTA_ABIERTA else "REPARACION"
            )
            assert pv.familia_publicada(tip, clase, "foto.jpg", None) == esperado, (tip, clase)
    assert usadas == {PV001, PV004, PV006}


@pytest.mark.parametrize("nombre", ["foto.jpg", "foto.pdf", "video.mp4", "correo.msg", "sin_ext"])
def test_f164_r6_la_extension_no_abre_ni_cierra(nombre: str) -> None:
    assert pv.familia_publicada(INC, PV001, nombre, None) == "INCIDENCIA"
    assert pv.familia_publicada(INC, None, nombre, None) == "REPARACION"
    firmado = nombre.replace(".", " FIRMADO.") if "." in nombre else nombre + " FIRMADO"
    assert pv.familia_publicada(INC, PV001, firmado, None) == "REPARACION"


# ===========================================================================
# R2 / R3 · Dentro de la lista abierta, la señal decide
# ===========================================================================


@pytest.mark.parametrize("tip, clase, nombre, descripcion, familia", CONTROLES_ABIERTOS)
def test_f164_r3_sin_senal_la_familia_por_documento(
    tip: int, clase: int, nombre: str | None, descripcion: str | None, familia: str
) -> None:
    assert pv.familia_publicada(tip, clase, nombre, descripcion) == familia
    assert pv.familia_adjunto(tip, clase) == familia


@pytest.mark.parametrize("tip, clase", [(INC, PV001), (UNI, PV006), (TAR, PV004)])
@pytest.mark.parametrize("nombre, descripcion", [
    ("documento.pdf", "PARTE FIRMADO"),
    ("documento FIRMADO.pdf", None),
    ("p1.2a firmada.pdf", None),
    ("todas las incidencias firmadas.pdf", ""),
    ("hoja.pdf", "firma del cliente"),
    ("hoja.pdf", "FIRMAS"),
    ("FIRMA", None),
    ("x_FIRMA_y.pdf", None),
    ("RS24.11-0123.pdf", None),
    ("VIV 1 - RS 24.11 / 0123.pdf", None),
    ("RS24.11_01234.pdf", "Foto"),
    ("rs24.11.012.jpg", None),
    ("B1C RS24.11 0456.pdf", None),
    ("parte firmado por la dueña.pdf", None),
])
def test_f164_r2_con_senal_es_reparacion(
    tip: int, clase: int, nombre: str | None, descripcion: str | None
) -> None:
    assert pv.familia_publicada(tip, clase, nombre, descripcion) == "REPARACION"


@pytest.mark.parametrize("texto, senal", [
    ("FIRMADO", True), ("FIRMADA", True), ("FIRMADAS", True), ("FIRMA", True), ("FIRMAS", True),
    ("firmado", True), ("parte-firmado", True), ("1FIRMA2", True), ("FIRMA.", True),
    ("CONFIRMADO", False), ("CONFIRMACIÓN", False), ("AFIRMA", False), ("FIRMAMENTO", False),
    ("FIRMAR", False), ("FIRM", False), ("ÁFIRMA", False), ("FIRMAÑ", False),
    ("FIRMASO", False), ("", False),
])
def test_f164_r2_la_senal_de_firma_como_palabra(texto: str, senal: bool) -> None:
    assert pv.senal_parte_firmado(texto, None) is senal
    assert pv.senal_parte_firmado(None, texto) is senal


@pytest.mark.parametrize("nombre, senal", [
    ("RS24.11-0123", True), ("RS 24.11 - 0123", True), ("RS24.11/0123", True),
    ("RS24.11_0123", True), ("RS24.11.0123", True), ("RS24.11 0123", True),
    ("RS24.11-01234", True), ("rs24.11-012", True),
    ("RS24.11-12", False), ("RS2.11-0123", False), ("RS24-11-0123", False),
    ("RS24.110123", False), ("R24.11-0123", False),
])
def test_f164_r2_la_senal_de_codigo_solo_en_el_nombre(nombre: str, senal: bool) -> None:
    assert pv.senal_parte_firmado(nombre, None) is senal
    # S3 no mira la descripción (design §3: falso positivo medido en PV001).
    assert pv.senal_parte_firmado(None, nombre) is False


def test_f164_r2_el_codigo_en_la_descripcion_no_restringe_una_foto() -> None:
    assert pv.familia_publicada(INC, PV001, "IMG_0001.jpg", "RS24.11-0123 salon") == "INCIDENCIA"


def test_f164_r2_la_firma_puede_venir_de_cualquiera_de_los_dos_campos() -> None:
    assert pv.senal_parte_firmado("x FIRMA", "y")
    assert pv.senal_parte_firmado("x", "y FIRMADO")
    # La unión es «nombre + espacio + descripción»: no se pega una palabra a la
    # otra («CON» + «FIRMADO» no es «CONFIRMADO»).
    assert pv.senal_parte_firmado("CON", "FIRMADO")
    assert not pv.senal_parte_firmado("CONFIRMADO", None)


# ===========================================================================
# R4 · Nulos: ninguno abre un fichero
# ===========================================================================


def test_f164_r4_tipo_o_clase_nulos_van_a_reparacion() -> None:
    assert pv.familia_publicada(INC, None, "foto.jpg", None) == "REPARACION"
    assert pv.familia_publicada(UNI, None, "ficha.pdf", None) == "REPARACION"
    assert pv.familia_publicada(TAR, None, "informe.pdf", None) == "REPARACION"
    assert pv.familia_publicada(None, PV001, "foto.jpg", None) == "REPARACION"
    assert pv.familia_publicada(None, None, None, None) == "REPARACION"


@pytest.mark.parametrize("vacio", [None, "", "   "])
def test_f164_r4_nombre_o_descripcion_vacios_son_texto_vacio(vacio: str | None) -> None:
    assert pv.familia_publicada(INC, PV001, vacio, vacio) == "INCIDENCIA"
    assert pv.familia_publicada(INC, PV001, "parte FIRMADO.pdf", vacio) == "REPARACION"
    assert pv.familia_publicada(INC, PV001, vacio, "PARTE FIRMADO") == "REPARACION"
    assert pv.senal_parte_firmado(vacio, vacio) is False


def test_f164_r4_el_parte_de_2026_10_sin_descripcion() -> None:
    assert pv.familia_publicada(INC, None, "0601 - RS26.10 - 0789 PARTE FIRMADO.pdf", None) \
        == "REPARACION"
    assert pv.familia_publicada(INC, PV001, "0601 - RS26.10 - 0789 PARTE FIRMADO.pdf", None) \
        == "REPARACION"


def test_f164_r4_los_espacios_de_los_bordes_no_cambian_la_senal() -> None:
    """El SQL recorta con `BTRIM`; el dominio no necesita hacerlo (review H4): da lo mismo."""
    assert pv.senal_parte_firmado("  FIRMA  ", None)
    assert pv.senal_parte_firmado("  RS24.11-0123.pdf  ", "  ")
    assert not pv.senal_parte_firmado("  foto.jpg  ", "  ")
    assert pv.familia_publicada(INC, PV001, "  foto.jpg  ", "  ") == "INCIDENCIA"


# ===========================================================================
# R7 · REPARACION por documento nunca sale de REPARACION
# ===========================================================================


@pytest.mark.parametrize("nombre, descripcion", [
    ("20250312_101010.jpg", None), ("foto.jpg", "Foto"), (None, None), ("x.pdf", "PARTE FIRMADO"),
])
def test_f164_r7_pv002_en_incidencia_sigue_en_reparacion(
    nombre: str | None, descripcion: str | None
) -> None:
    assert pv.familia_adjunto(INC, PV002) == "REPARACION"
    assert pv.familia_publicada(INC, PV002, nombre, descripcion) == "REPARACION"


def test_f164_r7_la_publicada_nunca_abre_lo_que_el_documento_cierra() -> None:
    for tip in (*pv.TIPOS_POSTVENTA, None):
        for clase in (None, 0, *range(30, 45)):
            for nombre, desc in (("foto.jpg", None), ("x FIRMADO.pdf", None), (None, None)):
                publicada = pv.familia_publicada(tip, clase, nombre, desc)
                if pv.familia_adjunto(tip, clase) == "REPARACION":
                    assert publicada == "REPARACION"
                assert publicada in pv.FAMILIAS_ADJUNTOS


def test_f164_fuera_de_postventa_sigue_siendo_none() -> None:
    """Como `familia_adjunto`: un tipo de compras no es de este índice."""
    assert pv.familia_publicada(41, PV001, "foto.jpg", None) is None
    assert pv.familia_adjunto(41, PV001) is None


def test_f164_familia_adjunto_no_cambia() -> None:
    """D3: `familia_adjunto` es la `familia_documento` publicada, la de F-156."""
    assert pv.familia_adjunto(UNI, PV002) == "UNIDAD"
    assert pv.familia_adjunto(TAR, PV002) == "TAREA"
    assert pv.familia_adjunto(INC, None) == "INCIDENCIA"
    assert pv.familia_adjunto(INC, PV002) == "REPARACION"
