# tests/test_f120_factor.py
"""
F-120 · El factor del descompuesto, comprobado OFFLINE (R1-R27).

El campo 14 del registro `~D|` no es el rendimiento: es «factor x rendimiento»
cuando la linea tiene factor (`1.22x0.003`) y un numero cuando no. Aqui se fija:

- el espejo en Python (`factor_rendimiento`, `trocear_des`) con las formas
  MEDIDAS en `_des_texto` (`progress/spec_F-120.md` §2) y la partida 400854 de
  la 0713, version 6, con sus 19 registros (§3): 9 con factor y suma 249,41;
- el TEXTO del SQL (`01`, `02`, `03`, `06`): el patron literal, `fn_num` a cada
  lado de la `x`, el `DROP FUNCTION`, el `ALTER TABLE`, PLANIF_JO con
  `dncpro.factip`/`faccan` y la columna al final de las vistas;
- el sello que retrocea lo ya cargado, el diccionario y la documentacion.

Ningun test toca red ni base de datos. El contraste SQL frente a espejo contra
un PostgreSQL de verdad (T8, T9) se hizo en uno local y desechable: su resultado
esta en `progress/impl_F-120.md`. R28 y R29 son verificacion MANUAL del humano.
Los helpers se copian de `test_f097_descompuestos.py` y no se importan: la suite
de otra feature no es una API.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain import descompuestos as dominio
from etl_sigrid.domain.descompuestos import POSICIONES, trocear_des

RAIZ = Path(__file__).resolve().parents[1]
DIR_DES = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "descompuestos"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

SETUP = "00_setup.sql"
TROCEADO = "01_troceado.sql"
COSTE = "02_lineas_coste.sql"
MASTER = "03_lineas_master.sql"
CUADRE = "05_cuadre.sql"
VISTAS = "06_views.sql"

#: El sello que tenia produccion el 2026-09-30 (`build_descompuestos`).
SELLO_DE_F097 = "99f827a11969d59f"

#: El texto EXACTO de `PATRON_NUMERO` en F-097: lo comparte `fn_num` y no cambia.
PATRON_NUMERO_F097 = r"^[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?$"

VISTAS_CON_FACTOR = ("v_pbi_estudio", "v_pbi_planif_jo", "v_pbi_master_planif_jo")

D = Decimal


@cache
def _crudo(nombre: str) -> str:
    return (DIR_DES / nombre).read_text(encoding="utf-8")


@cache
def _sql(nombre: str) -> str:
    """El SQL sin comentarios `--` y con los blancos colapsados."""
    sin_comentarios = "\n".join(linea.split("--", 1)[0] for linea in _crudo(nombre).splitlines())
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _bloque(nombre: str, desde: str, hasta: str | None = None) -> str:
    texto = _sql(nombre)
    assert desde in texto, f"no encuentro «{desde}» en {nombre}"
    trozo = texto.split(desde, 1)[1]
    if hasta is not None:
        assert hasta in trozo, f"no encuentro «{hasta}» detras de «{desde}» en {nombre}"
        trozo = trozo.split(hasta, 1)[0]
    return trozo


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(objeto: str) -> dict:
    return _yaml("descompuestos.yaml")["objetos"][objeto]


def _texto_ficha(objeto: str) -> str:
    return yaml.safe_dump(_ficha(objeto), allow_unicode=True, width=10_000)


def _registro(precio: str = "", cantidad: str = "", campo14: str = "", tipo: str = "") -> str:
    """Un registro `~D|` de 38 campos con lo que importa en su posicion."""
    campos = ["~D", "X", "DESC"] + [""] * 35
    campos[POSICIONES["precio"]] = precio
    campos[POSICIONES["cantidad_total"]] = cantidad
    campos[POSICIONES["factor_rendimiento"]] = campo14
    campos[POSICIONES["tipo_elemento_codigo"]] = tipo
    return "|".join(campos)


def _des(*registros: str) -> str:
    return "\n".join(registros) + "\n"


# ===========================================================================
# R1-R5 · R9 · las formas del campo 14 (medidas el 2026-10-01, §2)
# ===========================================================================

FORMAS = [
    # numero: factor 1 (R1)
    ("0.41", D(1), D("0.41")),
    ("-0.001", D(1), D("-0.001")),
    ("1", D(1), D(1)),
    ("1e3", D(1), D("1E+3")),
    # a x b, con signo en cualquiera de los dos lados (R2)
    ("1.00021x1", D("1.00021"), D(1)),
    ("1.22x0.003", D("1.22"), D("0.003")),
    ("0.99765x-0.15", D("0.99765"), D("-0.15")),
    ("-1x1", D(-1), D(1)),
    ("-1.27x0.001", D("-1.27"), D("0.001")),
    ("1x-0.011", D(1), D("-0.011")),
    ("0.0000005x384.721", D("0.0000005"), D("384.721")),
    ("54.73x15993.859", D("54.73"), D("15993.859")),
    ("+2x.5", D(2), D("0.5")),
    # a x, rendimiento vacio (R3)
    ("-23.05x", D("-23.05"), None),
    ("1.1x", D("1.1"), None),
    # factor 0 es un factor (R9)
    ("0x1", D(0), D(1)),
    ("0x", D(0), None),
    # vacio (R4, D1)
    ("", None, None),
    (None, None, None),
    # raros, medidos y sinteticos (R5, D2)
    ("0678.CDMA15", None, None),
    ("1963589xF321886", None, None),
    ("1X2", None, None),
    ("1,5", None, None),
    ("1,5x2", None, None),
    ("1x2x3", None, None),
    ("1 x 2", None, None),
    ("x2", None, None),
    ("x", None, None),
    ("abc", None, None),
    ("1x2\n", None, None),
    ("1x1e9999", None, None),
]


@pytest.mark.parametrize(("texto", "factor", "rendimiento"), FORMAS)
def test_f120_r1_r5_forma_del_campo_14(
    texto: str | None, factor: Decimal | None, rendimiento: Decimal | None
) -> None:
    assert dominio.factor_rendimiento(texto) == (factor, rendimiento)


@pytest.mark.parametrize(
    ("texto", "factor", "rendimiento"),
    # sin el salto final: el troceado lo quita al partir registros
    [f for f in FORMAS if f[0] is not None and not f[0].endswith("\n")],
)
def test_f120_r10_espejo_trocea_cada_forma(
    texto: str, factor: Decimal | None, rendimiento: Decimal | None
) -> None:
    """`trocear_des` aplica la MISMA regla que `factor_rendimiento` (R10)."""
    (r,) = trocear_des(_des(_registro(precio="10", cantidad="2", campo14=texto)))
    assert (r.factor, r.rendimiento) == (factor, rendimiento)


def test_f120_r2_factor_por_rendimiento_con_signo() -> None:
    """El orden es factor x rendimiento (0 casos al reves contra `dncpro`)."""
    assert dominio.factor_rendimiento("1.00021x1") == (D("1.00021"), D(1))
    assert dominio.factor_rendimiento("-1x1") == (D(-1), D(1))
    assert dominio.factor_rendimiento("0.99765x-0.15") == (D("0.99765"), D("-0.15"))


def test_f120_r3_rendimiento_vacio() -> None:
    assert dominio.factor_rendimiento("-23.05x") == (D("-23.05"), None)
    (r,) = trocear_des(_des(_registro(precio="10", campo14="1.1x")))
    assert (r.factor, r.rendimiento, r.importe_unitario) == (D("1.1"), None, None)


def test_f120_r1_numero_con_blancos_en_los_extremos() -> None:
    assert dominio.factor_rendimiento(" 0.5 ") == (D(1), D("0.5"))
    assert dominio.factor_rendimiento(" 1.2x3 ") == (D("1.2"), D(3))
    (r,) = trocear_des(_des(_registro(precio="10", campo14=" 1.2x3 ")))
    assert (r.factor, r.rendimiento, r.importe_unitario) == (D("1.2"), D(3), D("36.00"))


def test_f120_r4_campo_14_ausente_es_null() -> None:
    """Un registro de menos de 15 campos no tiene campo 14: factor y rendimiento NULL."""
    (r,) = trocear_des(_des("~D|X|DESC|10|2|UD"))
    assert (r.factor, r.rendimiento, r.importe_unitario) == (None, None, None)
    assert r.importe_total == D("20.00")


def test_f120_r5_raro_no_tumba_el_troceado() -> None:
    (r,) = trocear_des(_des(_registro(precio="3", cantidad="4", campo14="0678.CDMA15")))
    assert (r.factor, r.rendimiento, r.importe_unitario) == (None, None, None)
    assert r.importe_total == D("12.00"), "lo demas de la linea se publica igual"


# ===========================================================================
# R6 · R7 · R8 · R9 · R11 · los importes
# ===========================================================================


def test_f120_r6_importe_unitario_lleva_el_factor() -> None:
    (r,) = trocear_des(_des(_registro(precio="339.39", cantidad="3.995", campo14="1.22x0.003")))
    assert r.importe_unitario == D("1.24"), "1,22 x 0,003 x 339,39 = 1,2421"
    (s,) = trocear_des(_des(_registro(precio="28", campo14="1.013x0.06")))
    assert s.importe_unitario == D("1.70"), "28 x 1,013 x 0,06 = 1,70184"


@pytest.mark.parametrize("campo14", ["", "1.1x", "abc"])
def test_f120_r6_sin_factor_o_sin_rendimiento_no_hay_importe(campo14: str) -> None:
    (r,) = trocear_des(_des(_registro(precio="10", campo14=campo14)))
    assert r.importe_unitario is None


def test_f120_r6_sin_precio_no_hay_importe() -> None:
    (r,) = trocear_des(_des(_registro(precio="", campo14="1.2x3")))
    assert r.importe_unitario is None and r.factor == D("1.2")


def test_f120_r6_el_tope_del_importe_sigue_valiendo() -> None:
    """El factor puede llevar el importe por encima de NUMERIC(18,2): NULL (LIMITE_IMPORTE)."""
    (r,) = trocear_des(_des(_registro(precio="1e10", campo14="1e5x1e1")))
    assert r.importe_unitario is None
    (s,) = trocear_des(_des(_registro(precio="1e10", campo14="1e5x1e-1")))
    assert s.importe_unitario == D("100000000000000.00")


def test_f120_r7_importe_total_sin_el_factor() -> None:
    """El campo 4 ya lleva el factor (1091,5 x 1,00021 x 1 = 1091,729)."""
    (r,) = trocear_des(_des(_registro(precio="34.2", cantidad="1091.729", campo14="1.00021x1")))
    assert r.importe_total == D("37337.13"), "1091,729 x 34,2 = 37337,1318, sin volver a multiplicar"
    assert r.importe_unitario == D("34.21")


def test_f120_r8_porcentaje_sin_factor_e_importe_con_el() -> None:
    (r,) = trocear_des(_des(_registro(precio="100", campo14="0.99765x-0.15", tipo="13")))
    assert r.es_porcentaje and r.factor == D("0.99765")
    assert r.porcentaje == D("-15.00"), "rendimiento x 100, sin el factor (D6)"
    assert r.base_porcentaje == D(100)
    assert r.importe_unitario == D("-14.96"), "100 x 0,99765 x -0,15 = -14,96475"


def test_f120_r9_factor_cero_es_un_factor() -> None:
    (r,) = trocear_des(_des(_registro(precio="5", cantidad="0", campo14="0x1")))
    assert r.factor == D(0) and r.rendimiento == D(1)
    assert r.importe_unitario == D("0.00"), "0 no es ausencia: el importe es 0, no NULL"


def test_f120_r11_multiplica_sin_perder_precision() -> None:
    """Con el contexto por defecto (28 cifras) el producto se redondearia ANTES
    que el NUMERIC exacto de PostgreSQL: 0,00499...9 (29 nueves) pasaria a 0,005
    y el importe a 0,01. El exacto es 0,00."""
    precio = "0.0049999999999999999999999999999"
    (r,) = trocear_des(_des(_registro(precio=precio, campo14="1x1")))
    assert r.importe_unitario == D("0.00")
    (s,) = trocear_des(_des(_registro(precio="1", campo14=f"1x{precio}")))
    assert s.importe_unitario == D("0.00")


# ===========================================================================
# R13 · la 0713, partida 400854, version 6: los 19 registros de §3
# ===========================================================================

#: (precio, cantidad total, campo 14, importe_unitario esperado) de cada registro.
PARTIDA_400854_V6 = [
    ("262.25", "", "", None),
    ("34.2", "1091.729", "1.00021x1", "34.21"),
    ("2", "1091.729", "1.00021x1", "2.00"),
    ("44.1", "189.589", "0.99825x0.174", "7.66"),
    ("28", "66.341", "1.013x0.06", "1.70"),
    ("28", "66.341", "1.013x0.06", "1.70"),
    ("119", "480.26", "0.44", "52.36"),
    ("3", "480.26", "0.44", "1.32"),
    ("3", "480.26", "0.44", "1.32"),
    ("0.94", "81545.965", "74.71", "70.23"),
    ("0.26", "81545.965", "74.71", "19.42"),
    ("16.96", "491.175", "1x0.45", "7.63"),
    ("339.39", "3.995", "1.22x0.003", "1.24"),
    ("339.39", "7.025", "0.9194x0.007", "2.18"),
    ("2.3", "545.75", "0.5", "1.15"),
    ("0.1", "4366.917", "1.00021x4", "0.40"),
    ("0.65", "6956.13", "6.373", "4.14"),
    ("15.68", "1200.65", "1.1", "17.25"),
    ("23.5", "1091.5", "1", "23.50"),
]


def test_f120_r13_la_400854_v6_cuadra_al_centimo() -> None:
    registros = trocear_des(_des(*(_registro(p, c, f) for p, c, f, _ in PARTIDA_400854_V6)))
    assert len(registros) == 19
    con_factor = [r for r, fila in zip(registros, PARTIDA_400854_V6) if "x" in fila[2]]
    assert len(con_factor) == 9, "D9: son 9 lineas con factor (7 formas)"
    assert all(r.rendimiento is not None and r.importe_unitario is not None for r in con_factor)
    assert sum(1 for r in con_factor if r.factor != 1) == 8
    assert registros[12].importe_unitario == D("1.24"), "linea 13: 1,22 x 0,003 x 339,39"
    assert [r.importe_unitario for r in registros] == [
        None if esperado is None else D(esperado) for *_, esperado in PARTIDA_400854_V6
    ]
    assert sum(r.importe_unitario for r in registros if r.importe_unitario is not None) == D("249.41")


def test_f120_r10_registro_lleva_factor() -> None:
    assert "factor" in dominio.RegistroDes.__dataclass_fields__
    assert POSICIONES["factor_rendimiento"] == 14
    assert "rendimiento" not in POSICIONES, "el campo 14 ya no es el rendimiento a secas"


# ===========================================================================
# R12 · R19 · el troceado SQL
# ===========================================================================


def test_f120_r12_patron_numero_intacto_y_patron_del_factor() -> None:
    assert dominio.PATRON_NUMERO == PATRON_NUMERO_F097, "fn_num lo comparte: no cambia"
    cuerpo = PATRON_NUMERO_F097[1:-1]
    assert dominio.PATRON_FACTOR_RENDIMIENTO == f"^{cuerpo}x({cuerpo})?$"


def test_f120_r12_troceado_usa_el_patron_literal_y_fn_num() -> None:
    texto = _sql(TROCEADO)
    patron = dominio.PATRON_FACTOR_RENDIMIENTO
    assert "NULLIF(btrim(split_part(g.reg, '|', 15)), '') AS factor_rendimiento" in texto
    factor = _bloque(TROCEADO, "CASE WHEN descompuestos.fn_num(f.factor_rendimiento) IS NOT NULL THEN 1::NUMERIC",
                     "AS factor,")
    assert (f" WHEN f.factor_rendimiento ~ '{patron}' "
            "THEN descompuestos.fn_num(split_part(f.factor_rendimiento, 'x', 1)) END ") == factor
    rendimiento = _bloque(TROCEADO, "AS factor, CASE WHEN descompuestos.fn_num(f.factor_rendimiento) IS NOT NULL",
                          "AS rendimiento")
    assert (f" THEN descompuestos.fn_num(f.factor_rendimiento) WHEN f.factor_rendimiento ~ '{patron}' "
            "THEN descompuestos.fn_num(split_part(f.factor_rendimiento, 'x', 2)) END ") == rendimiento
    assert "split_part(g.reg, '|', 15)) AS rendimiento" not in texto


def test_f120_r6_troceado_importe_con_el_factor() -> None:
    texto = _sql(TROCEADO)
    assert ("CASE WHEN abs(ROUND(c.precio * c.factor * c.rendimiento, 2)) < 1e16 "
            "THEN ROUND(c.precio * c.factor * c.rendimiento, 2)::NUMERIC(18,2) END AS importe_unitario") in texto
    assert ("CASE WHEN abs(ROUND(c.cantidad_total * c.precio, 2)) < 1e16 "
            "THEN ROUND(c.cantidad_total * c.precio, 2)::NUMERIC(18,2) END AS importe_total") in texto, "R7"
    assert "CASE WHEN c.tipo_elemento_codigo IN ('4', '13') THEN c.rendimiento * 100 END AS porcentaje" in texto, "R8"


def test_f120_r19_troceado_drop_y_factor_en_returns() -> None:
    texto = _sql(TROCEADO)
    drop = "DROP FUNCTION IF EXISTS descompuestos.fn_trocear(TEXT);"
    crear = "CREATE OR REPLACE FUNCTION descompuestos.fn_trocear(des TEXT)"
    assert drop in texto and crear in texto
    assert texto.index(drop) < texto.index(crear)
    retorno = _bloque(TROCEADO, "RETURNS TABLE (", ") LANGUAGE sql")
    assert retorno.strip().endswith("base_porcentaje NUMERIC, factor NUMERIC")
    assert "THEN c.precio END AS base_porcentaje, c.factor FROM (" in texto, "el orden del RETURNS TABLE"


# ===========================================================================
# R14-R17 · la tabla y PLANIF_JO
# ===========================================================================


def test_f120_r17_ddl_y_alter_de_lineas() -> None:
    ddl = _bloque(COSTE, "CREATE TABLE IF NOT EXISTS descompuestos.lineas (", "CONSTRAINT ck_lineas_origen")
    assert ddl.strip().endswith("texto_version TEXT, factor NUMERIC,"), "factor al final (D8)"
    texto = _sql(COSTE)
    alter = "ALTER TABLE descompuestos.lineas ADD COLUMN IF NOT EXISTS factor NUMERIC;"
    assert alter in texto
    assert texto.index("CREATE TABLE IF NOT EXISTS descompuestos.lineas") < texto.index(alter)
    assert texto.index(alter) < texto.index("DELETE FROM descompuestos.lineas")
    assert "DROP TABLE" not in texto, "lineas persiste entre noches: sin DROP"
    assert "DEFAULT" not in _bloque(COSTE, "ALTER TABLE descompuestos.lineas", ";")


def test_f120_r17_estudio_inserta_el_factor() -> None:
    insert = _bloque(COSTE, "WITH troceado AS (", "PLANIF_JO")
    assert "es_ultima, tipo_version, texto_version, factor )" in insert
    assert "NULL::BOOLEAN, NULL::TEXT, NULL::TEXT, t.factor FROM troceado t" in insert


def test_f120_r14_r16_planif_jo_con_factip_y_faccan() -> None:
    planif = _bloque(COSTE, "SELECT 'PLANIF_JO'", ";")
    assert ("CROSS JOIN LATERAL (SELECT CASE p.factip WHEN 1 THEN p.faccan::NUMERIC "
            "WHEN 0 THEN 1::NUMERIC END AS factor) f") in planif
    assert ("CASE WHEN abs(ROUND(p.pre::NUMERIC * f.factor * p.canren::NUMERIC, 2)) < 1e16 "
            "THEN ROUND(p.pre::NUMERIC * f.factor * p.canren::NUMERIC, 2) END") in planif
    assert "p.canren::NUMERIC, p.pre::NUMERIC," in planif, "rendimiento = canren, sin el factor"
    assert ("CASE WHEN abs(ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2)) < 1e16 "
            "THEN ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2) END") in planif, "importe_total igual"
    assert "NULL::TEXT, NULL::TEXT, f.factor FROM raw.obr o" in planif
    assert planif.index("LEFT JOIN raw.auxpronat") < planif.index("CROSS JOIN LATERAL")
    insert = _bloque(COSTE, "WHERE NOT EXISTS (SELECT 1 FROM enlazadas e", "SELECT 'PLANIF_JO'")
    assert "es_ultima, tipo_version, texto_version, factor )" in insert


def test_f120_r15_factip_raro_sin_factor() -> None:
    """Sin `ELSE`: cualquier `factip` que no sea 0 ni 1 (el 646) deja factor NULL,
    y con el, el importe unitario (NULL x algo es NULL)."""
    planif = _bloque(COSTE, "SELECT 'PLANIF_JO'", ";")
    caso = planif.split("CASE p.factip", 1)[1].split("END AS factor", 1)[0]
    assert "ELSE" not in caso


def test_f120_r17_master_inserta_el_factor() -> None:
    insert = _bloque(MASTER, "INSERT INTO descompuestos.lineas (", "WHERE d.ambito_id = 8")
    assert "es_ultima, tipo_version, texto_version, factor )" in insert
    assert "a.tipo_version, a.texto_version, t.factor FROM descompuestos._des_texto d" in insert


# ===========================================================================
# R18 · las vistas
# ===========================================================================


@pytest.mark.parametrize("vista", VISTAS_CON_FACTOR)
def test_f120_r18_factor_ultima_columna_de_cada_vista(vista: str) -> None:
    cuerpo = _bloque(VISTAS, f"CREATE OR REPLACE VIEW descompuestos.{vista} AS", " FROM descompuestos.lineas")
    columnas = [c.strip() for c in cuerpo.replace("SELECT", "", 1).split(",")]
    assert columnas[-1] == "factor"
    assert columnas.count("factor") == 1


# ===========================================================================
# R20 · R21 · R22 · R23 · el retroceo de lo ya cargado
# ===========================================================================


def test_f120_r21_el_sello_incluye_00_setup(tmp_path: Path) -> None:
    from etl_sigrid.application.steps.build_descompuestos_step import (
        FICHEROS_DEL_SELLO,
        sello_de_troceado,
    )

    assert FICHEROS_DEL_SELLO == (SETUP, TROCEADO, MASTER)
    for nombre in FICHEROS_DEL_SELLO:
        (tmp_path / nombre).write_text(_crudo(nombre), encoding="utf-8")
    real = sello_de_troceado()
    assert sello_de_troceado(tmp_path) == real
    (tmp_path / SETUP).write_text(_crudo(SETUP) + "\n-- fn_num cambia", encoding="utf-8")
    assert sello_de_troceado(tmp_path) != real, "cambiar fn_num retrocea"


def test_f120_r20_el_sello_cambia_respecto_a_produccion() -> None:
    from etl_sigrid.application.steps.build_descompuestos_step import sello_de_troceado

    assert sello_de_troceado() != SELLO_DE_F097, "sin sello nuevo no se retrocea nada"


def test_f120_r22_el_retroceo_no_toca_el_texto_ni_la_huella() -> None:
    for nombre in (SETUP, TROCEADO, COSTE, MASTER, CUADRE, VISTAS):
        texto = _sql(nombre)
        assert not re.search(r"(INSERT INTO|UPDATE|DELETE FROM|TRUNCATE)\s+descompuestos\._des_texto", texto), nombre
    sellado = _bloque(MASTER, "UPDATE descompuestos._versiones_cargadas v SET sello_troceado", "FROM _atributos a")
    asignadas = re.findall(r"(\w+) =", sellado.replace("= /*F097_SELLO*/", "= x"))
    assert set(asignadas) <= {"sello_troceado", "troceada_at", "atributos_troceado"}
    for columna in ("filas", "bytes", "huella", "batch_id", "cargada_at"):
        assert not re.search(rf"SET[^;]*\b{columna} =", _sql(MASTER)), columna


def test_f120_r23_el_cuadre_no_cambia_de_regla() -> None:
    for nombre in (MASTER, CUADRE):
        texto = _sql(nombre)
        assert "SUM(li.importe_unitario) AS suma" in texto or "SUM(importe_unitario) AS suma" in texto
        assert "ABS(h.precio_partida - COALESCE(s.suma, 0)) <= 0.01 THEN 'CUADRA'" in texto


# ===========================================================================
# R24 · R25 · R26 · el diccionario
# ===========================================================================


def test_f120_r24_factor_en_las_fichas() -> None:
    assert list(_ficha("lineas")["columnas"])[-1] == "factor"
    for vista in VISTAS_CON_FACTOR:
        assert list(_ficha(vista)["columnas"])[-1] == "factor", vista
    lineas = _ficha("lineas")["columnas"]
    factor = lineas["factor"]["significado"]
    for termino in ("factor x rendimiento", "1 ", "PLANIF_JO", "faccan"):
        assert termino in factor, termino
    assert "campo 14" in lineas["factor"]["nulo_significa"]
    assert "sin el factor" in lineas["rendimiento"]["significado"]
    assert "factor x rendimiento x precio" in lineas["importe_unitario"]["significado"]
    assert "ya lleva el factor" in lineas["cantidad_total"]["significado"]
    assert "faccan" in _ficha("v_pbi_planif_jo")["columnas"]["factor"]["significado"]


def test_f120_r24_el_factor_explicado_con_su_ejemplo() -> None:
    """Anadido 1 del humano: que es, como viene, la formula y el ejemplo."""
    texto = _texto_ficha("lineas")
    for termino in ("FACTOR", "Descomposicion", "factor x rendimiento", "1,22 x 0,003 x 339,39 = 1,24",
                    "DESPLAZAMIENTO BOMBA", "400854", "F-122"):
        assert termino in texto, termino
    assert "factor" in _texto_ficha("fn_trocear")


@pytest.mark.parametrize("objeto", ["lineas", "v_pbi_estudio", "cuadre_partida"])
def test_f120_r25_estudio_sigue_la_medicion_actual(objeto: str) -> None:
    """D7 reescrita y aprobada (2026-10-01): precios de Estudios, medicion ACTUAL;
    el importe de Estudios es medicion x precio de la version 0; MASTER_INICIAL
    solo existe donde la version 0 guarda descompuesto."""
    texto = _texto_ficha(objeto)
    for termino in ("medicion ACTUAL", "version 0", "4.979,02", "5.376,84", "0726", "527.564,24",
                    "134,35", "MASTER_INICIAL solo existe donde la version 0 guarda descompuesto"):
        assert termino in texto, f"{objeto}: falta «{termino}»"
    assert "foto fija de Estudios es MASTER_INICIAL" not in texto, "D7 original: es falso en general"


def test_f120_r25_sin_el_aviso_caducado_de_la_primera_carga() -> None:
    """Anadido 2: la primera carga se hizo el 2026-09-29; el aviso sobra."""
    crudo = (DIR_DICCIONARIO / "descompuestos.yaml").read_text(encoding="utf-8")
    assert "INCOMPLETO" not in crudo
    for objeto in ("lineas", "cuadre_partida"):
        texto = _texto_ficha(objeto)
        assert "2026-09-29" in texto and "_versiones_cargadas" in texto, objeto


def test_f120_r26_version_del_diccionario() -> None:
    assert _yaml("00_global.yaml")["version"] == 39


# ===========================================================================
# R27 · la documentacion
# ===========================================================================


def test_f120_r27_docs_arquitectura_y_ayuda() -> None:
    arquitectura = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    assert "14 «factor x rendimiento»" in arquitectura
    assert "`00_setup.sql`, `01_troceado.sql` y `03_lineas_master.sql`" in arquitectura, "el sello"
    import main

    ayuda = {o.name: o.help for o in main.cli.commands["build-descompuestos"].params}["sin_tope"]
    assert "916,9 s" in ayuda and "sin medir" not in ayuda


def test_f120_r27_docs_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    assert "F-120" in texto and "`factor`" in texto


def test_f120_un_test_por_requisito() -> None:
    """R1-R27 con al menos un test (R28 y R29 son verificacion MANUAL)."""
    nombres = [n for n in globals() if n.startswith("test_f120_r")]
    for n in range(1, 28):
        assert any(re.match(rf"test_f120_(r\d+_)*r{n}_", x) for x in nombres), f"R{n} sin test"
