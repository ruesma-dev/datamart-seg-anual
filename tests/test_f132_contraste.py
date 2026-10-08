# tests/test_f132_contraste.py
"""
F-132 · El contraste foto diaria <-> `rac`: `python main.py contraste-estados`
(R12-R17).

El contraste decide si la foto de F-067 se puede retirar (Fase B, D7 del
humano), así que tiene que ser de fiar en las dos direcciones:

1. **No escribe** (R17): lee tablas PERSISTENTES que no se pueden recuperar, en
   un servidor compartido con producción. Cada SQL es un `SELECT`, y además la
   sesión va `READ ONLY`.
2. **Clasifica con el dominio** (R12-R14) y **sirve de puerta** (R15): una sola
   DISCREPANCIA sale con código 1.

Ningún test toca red ni BBDD: el cliente es un doble que devuelve filas con la
forma de las de verdad (las de la noche del 07-10 al 08-10).
"""

from __future__ import annotations

import re

import pytest

from etl_sigrid.domain.historial_estados import MOTIVOS_CIERRE, TIPOS_HISTORIAL
from etl_sigrid.infrastructure.postgres import contraste_estados_sql as sql_contraste

#: Los SQL que ejecuta el comando, por nombre.
CONSULTAS = ("SQL_FOTOS", "SQL_CAMBIOS", "SQL_NO_VISTOS", "SQL_PASOS")

_ESCRITURA = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO)\b",
    re.IGNORECASE,
)


def _sin_comentarios(texto: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


# ===========================================================================
# R17 · ningún SQL del contraste escribe
# ===========================================================================


def test_f132_r17_el_modulo_declara_las_cuatro_consultas() -> None:
    assert sql_contraste.CONSULTAS == tuple(getattr(sql_contraste, n) for n in CONSULTAS)


@pytest.mark.parametrize("nombre", CONSULTAS)
def test_f132_r17_cada_consulta_es_un_select_de_una_sola_sentencia(nombre: str) -> None:
    texto = _compacto(getattr(sql_contraste, nombre))
    assert texto.startswith(("SELECT ", "WITH ")), texto[:40]
    assert ";" not in texto, "una sola sentencia y sin `;`"
    assert not _ESCRITURA.search(texto), _ESCRITURA.search(texto).group(0)


def test_f132_r17_el_contraste_lee_la_foto_y_rac_y_nada_mas() -> None:
    leidas = {
        tabla
        for nombre in CONSULTAS
        for tabla in re.findall(r"\b(?:FROM|JOIN) (\w+\.\w+)", _compacto(getattr(sql_contraste, nombre)))
    }
    assert leidas == {
        "compras.historial_estados",
        "compras.historial_estados_fotos",
        "compras.documento_procesos",
    }, leidas


# ===========================================================================
# R12-R14 · lo que lee cada consulta, con los literales del dominio
# ===========================================================================


def test_f132_r12_los_cambios_son_los_tramos_cerrados_por_cambio_con_su_ventana() -> None:
    texto = _compacto(sql_contraste.SQL_CAMBIOS)
    cambio = MOTIVOS_CIERRE[0]
    assert f"WHERE v.motivo_cierre = '{cambio}'" in texto
    # El tramo cerrado se une al que abre LA MISMA foto: su estado es el nuevo.
    assert "JOIN compras.historial_estados n ON n.documento_id = v.documento_id AND n.desde = v.hasta" in texto
    assert (
        "SELECT n.documento_id, n.tipo_documento_codigo, n.estado_id AS estado_nuevo, "
        "n.observado_antes AS inicio, n.desde AS fin " in texto
    )


def test_f132_r14_los_no_vistos_son_de_contrato_y_factura_y_sin_cambio_en_esa_foto() -> None:
    texto = _compacto(sql_contraste.SQL_NO_VISTOS)
    tipos = ", ".join(str(t) for t in TIPOS_HISTORIAL)
    assert f"p.tipo_documento_codigo IN ({tipos})" in texto
    assert f"x.hasta = v.fin AND x.motivo_cierre = '{MOTIVOS_CIERRE[0]}'" in texto
    assert "NOT EXISTS" in texto
    # El estado que la foto les vio en `fin` y si esa foto les abrió tramo.
    assert "h.desde <= v.fin AND (h.hasta IS NULL OR h.hasta > v.fin)" in texto
    assert "(h.desde = v.fin AND NOT h.es_linea_base) AS abierto_en_la_foto" in texto
    # La ventana es (foto anterior, foto], y la línea base no tiene ventana.
    assert "LAG(f.observado_en) OVER (ORDER BY f.observado_en) AS inicio" in texto
    assert "WHERE v.inicio IS NOT NULL" in texto


def test_f132_r13_los_pasos_se_comparan_en_utc() -> None:
    """`rac` guarda hora de Madrid sin zona y las fotos son TIMESTAMPTZ."""
    assert "(p.momento AT TIME ZONE 'Europe/Madrid') AS momento_utc" in _compacto(
        sql_contraste.SQL_PASOS
    )
    no_vistos = _compacto(sql_contraste.SQL_NO_VISTOS)
    assert "(p.momento AT TIME ZONE 'Europe/Madrid') > v.inicio" in no_vistos
    assert "(p.momento AT TIME ZONE 'Europe/Madrid') <= v.fin" in no_vistos


def test_f132_r12_los_pasos_de_una_lista_de_documentos_en_su_orden() -> None:
    texto = _compacto(sql_contraste.SQL_PASOS)
    assert "WHERE p.documento_id = ANY(%s)" in texto
    assert texto.endswith("ORDER BY p.documento_id, p.orden")
    assert texto.startswith("SELECT p.documento_id, p.orden, p.estado_destino_id, ")


def test_f132_r16_las_fotos_en_orden_con_su_linea_base() -> None:
    texto = _compacto(sql_contraste.SQL_FOTOS)
    assert texto == (
        "SELECT f.observado_en, f.es_linea_base, f.n_cambios "
        "FROM compras.historial_estados_fotos f ORDER BY f.observado_en"
    )
