# tests/test_f168_descompuestos.py
"""
F-168 · El texto largo de los descompuestos (R19-R22), sin base de datos.

- El campo 9 del registro (`texto_largo`) sale de `fn_trocear` y de su espejo
  `trocear_des`, y está en `POSICIONES` (R19).
- `descompuestos.lineas.texto_id` en todos los orígenes y el texto una vez en
  `descompuestos.textos`, en la misma transacción que sus líneas (R20, R21).
- `stg/11_texto_largo.sql` entra en el sello del troceado (R22).

Lo que hace el SQL de verdad lo prueba `tests/test_f168_sandbox.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

from etl_sigrid.domain.descompuestos import POSICIONES, trocear_des
from etl_sigrid.domain.texto_largo import limpiar, texto_id

RAIZ = Path(__file__).resolve().parents[1]
DIR_DES = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "descompuestos"
TROCEADO = DIR_DES / "01_troceado.sql"
COSTE = DIR_DES / "02_lineas_coste.sql"
MASTER = DIR_DES / "03_lineas_master.sql"


def _sql(ruta: Path) -> str:
    sin = "\n".join(linea.split("--", 1)[0] for linea in ruta.read_text(encoding="utf-8").splitlines())
    return re.sub(r"\s+", " ", sin).strip()


def _registro(campos: dict[int, str], total: int = 38) -> str:
    lista = [""] * total
    lista[0] = "~D"
    for posicion, valor in campos.items():
        lista[posicion] = valor
    return "|".join(lista)


# ---------------------------------------------------------------------------
# R19 · el campo 9
# ---------------------------------------------------------------------------


def test_f168_r19_posiciones_incluye_el_campo_9() -> None:
    assert POSICIONES["texto_largo"] == 9


def test_f168_r19_fn_trocear_devuelve_el_campo_9_al_final() -> None:
    texto = _sql(TROCEADO)
    assert "NULLIF(btrim(split_part(g.reg, '|', 10)), '') AS texto_largo" in texto
    retorno = texto.split("RETURNS TABLE (", 1)[1].split(") LANGUAGE sql", 1)[0]
    assert retorno.strip().endswith("factor NUMERIC, texto_largo TEXT"), "al final (no mueve las demás)"
    assert "c.factor, c.texto_largo FROM (" in texto


def test_f168_r19_trocear_des_con_texto_multilinea_en_el_campo_9() -> None:
    des = "\r\n".join([
        _registro({1: "E01", 2: "Hormigon", 9: "  Hormigón HA-25\r\nvertido con bomba  ", 14: "2"}),
        _registro({1: "E02", 2: "Acero", 14: "1"}),
    ])
    registros = trocear_des(des)
    assert [r.codigo_elemento for r in registros] == ["E01", "E02"]
    assert registros[0].texto_largo == "Hormigón HA-25\nvertido con bomba"
    assert registros[1].texto_largo is None


def test_f168_r19_r6_el_texto_del_descompuesto_tiene_la_identidad_del_dominio() -> None:
    registro = trocear_des(_registro({1: "E01", 9: "Encofrado\tmetálico "}))[0]
    assert texto_id(limpiar(registro.texto_largo)) == texto_id("Encofrado\tmetálico")


# ---------------------------------------------------------------------------
# R20 · R21 · texto_id en las líneas y el catálogo de textos
# ---------------------------------------------------------------------------


def test_f168_r21_ddl_de_textos_y_alter_de_lineas() -> None:
    texto = _sql(COSTE)
    alter = "ALTER TABLE descompuestos.lineas ADD COLUMN IF NOT EXISTS texto_id UUID;"
    crear = ("CREATE TABLE IF NOT EXISTS descompuestos.textos ( texto_id UUID PRIMARY KEY, "
             "texto TEXT NOT NULL );")
    assert alter in texto and crear in texto
    assert texto.index(alter) < texto.index("DELETE FROM descompuestos.lineas")
    assert not re.search(r"(DROP\s+TABLE|TRUNCATE)[^;]*textos", texto), "textos nunca se vacía"
    assert "CREATE INDEX IF NOT EXISTS ix_lineas_texto ON descompuestos.lineas (texto_id);" in texto


def test_f168_r20_estudio_con_el_campo_9_limpio() -> None:
    texto = _sql(COSTE)
    troceado = texto.split("WITH troceado AS (", 1)[1].split("), enlazadas AS (", 1)[0]
    assert "stg.fn_texto_largo(t.texto_largo) AS texto_limpio" in troceado
    estudio = texto.split("SELECT 'ESTUDIO'", 1)[1].split(";", 1)[0]
    assert "t.factor, stg.fn_texto_id(t.texto_limpio) FROM troceado t" in estudio


def test_f168_r20_planif_jo_con_el_tex_de_dncpro() -> None:
    planif = _sql(COSTE).split("SELECT 'PLANIF_JO'", 1)[1].split(";", 1)[0]
    assert "f.factor, stg.fn_texto_id(stg.fn_texto_largo(p.tex)) FROM raw.obr o" in planif


def test_f168_r21_coste_guarda_sus_textos_sin_repetir() -> None:
    texto = _sql(COSTE)
    estudio = texto.split("WITH troceado AS (", 1)[1].split("INSERT INTO descompuestos.lineas", 1)[0]
    assert "INSERT INTO descompuestos.textos (texto_id, texto)" in estudio
    assert "ON CONFLICT (texto_id) DO NOTHING" in estudio
    planif = texto.split("SELECT 'PLANIF_JO'", 1)[1]
    assert ("INSERT INTO descompuestos.textos (texto_id, texto) SELECT DISTINCT ON (x.texto_id) "
            "x.texto_id, x.texto FROM raw.obr o JOIN raw.dncpro p ON p.dncide = o.dncide") in planif
    assert planif.count("ON CONFLICT (texto_id) DO NOTHING") == 1


def test_f168_r20_r21_master_texto_id_y_textos_en_la_misma_sentencia() -> None:
    texto = _sql(MASTER)
    sentencia = texto.split("WITH troceado AS (", 1)[1].split(";", 1)[0]
    assert "stg.fn_texto_largo(t.texto_largo) AS texto_limpio" in sentencia
    assert "INSERT INTO descompuestos.textos (texto_id, texto)" in sentencia
    assert "ON CONFLICT (texto_id) DO NOTHING" in sentencia
    assert "INSERT INTO descompuestos.lineas" in sentencia
    assert "t.factor, stg.fn_texto_id(t.texto_limpio) FROM troceado t" in sentencia
    for columna in ("texto_version, factor, texto_id )",):
        assert columna in sentencia


def test_f168_r20_las_columnas_de_los_insert_llevan_texto_id_al_final() -> None:
    for ruta in (COSTE, MASTER):
        listas = re.findall(r"INSERT INTO descompuestos\.lineas \(([^)]*)\)", _sql(ruta))
        assert listas, ruta.name
        for lista in listas:
            assert lista.strip().endswith("texto_version, factor, texto_id"), ruta.name


def test_f168_r20_solo_las_funciones_de_stg() -> None:
    for ruta in (COSTE, MASTER):
        usos = set(re.findall(r"\bstg\.(\w+)", _sql(ruta)))
        assert usos == {"fn_texto_largo", "fn_texto_id"}, (ruta.name, usos)


# ---------------------------------------------------------------------------
# R22 · el sello
# ---------------------------------------------------------------------------


def test_f168_r22_stg_11_entra_en_el_sello(tmp_path: Path) -> None:
    from etl_sigrid.application.steps.build_descompuestos_step import (
        FICHEROS_DEL_SELLO,
        sello_de_troceado,
    )

    assert FICHEROS_DEL_SELLO == (
        "00_setup.sql", "01_troceado.sql", "03_lineas_master.sql", "../stg/11_texto_largo.sql"
    )
    des = tmp_path / "descompuestos"
    (tmp_path / "stg").mkdir()
    des.mkdir()
    for nombre in FICHEROS_DEL_SELLO:
        (des / nombre).write_text((DIR_DES / nombre).read_text(encoding="utf-8"), encoding="utf-8")
    real = sello_de_troceado()
    assert sello_de_troceado(des) == real
    stg11 = des / "../stg/11_texto_largo.sql"
    stg11.write_text(stg11.read_text(encoding="utf-8") + "\n-- cambia la limpieza", encoding="utf-8")
    assert sello_de_troceado(des) != real, "cambiar la limpieza retrocea el master"
