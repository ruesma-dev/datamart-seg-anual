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

