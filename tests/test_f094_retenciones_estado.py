# tests/test_f094_retenciones_estado.py
"""
F-094 · El estado de una retención de proveedor mira la ficha DEL PROPIO EFECTO.

Hasta F-094 `retenciones.movimientos` derivaba `estado` SOLO de `fecrea` y
publicaba 35,54 M€ vivos a proveedor cuando lo vivo de verdad son 8,35 M€
(medido el 2026-09-22, `progress/impl_F-094.md`). Contaban como VIVA:

  - los originales agrupados (`con.est = 14`, `con.fecbaj` = fecha del AGR),
    cuyo dinero ya está en el efecto agrupador: el mismo euro, dos veces;
  - los anulados con `con.fecbaj <> 0`;
  - los efectos ya pagados (`con.est = 10`) que no tienen `fecrea`, empezando
    por los agrupadores AGR de las remesas de retenciones.

El efecto de pago ES un documento (`raw.pag` son propiedades de `raw.con`, ver
`tests/test_f080_sql.py`), así que su estado y su baja se LEEN de su ficha
`raw.con`. Estos tests fijan esa decisión sobre el TEXTO del SQL —no se puede
ejecutar aquí: construye en un Postgres compartido con producción— y la del
lado CLIENTE, que se deja como estaba a propósito.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "retenciones"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"


@cache
def _texto(nombre: str) -> str:
    return (DIR_SQL / nombre).read_text(encoding="utf-8")


def _compacto(texto: str) -> str:
    """Una línea, sin comentarios `--` y con los espacios colapsados."""
    sin_comentarios = "\n".join(
        linea.split("--", 1)[0] for linea in texto.splitlines()
    )
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _mitades() -> tuple[str, str]:
    """(PROVEEDOR, CLIENTE): las dos ramas del `UNION ALL` de movimientos."""
    compacto = _compacto(_texto("01_movimientos.sql"))
    partes = compacto.split(" UNION ALL ")
    assert len(partes) == 2, "01_movimientos.sql tiene que ser UN solo UNION ALL"
    return partes[0], partes[1]


def _case_estado(mitad: str) -> str:
    """El CASE que produce la columna `estado` de una mitad."""
    m = re.search(r"(CASE WHEN .*? END)::VARCHAR\(\d+\) AS estado\b", mitad)
    assert m, "no se encuentra el CASE ... AS estado"
    # El CASE mas corto que termina en `AS estado`: se busca el ultimo CASE
    # anterior a la marca.
    trozo = m.group(1)
    return trozo[trozo.rfind("CASE WHEN "):]


# ===========================================================================
# PROVEEDOR · la ficha del propio efecto manda
# ===========================================================================


def test_f094_proveedor_une_la_ficha_con_del_propio_efecto() -> None:
    """Hoy solo se une la ficha del DOCUMENTO origen (`p.conide`); la baja y el
    estado del efecto están en la ficha del EFECTO (`p.ide`)."""
    proveedor, _ = _mitades()
    assert re.search(r"LEFT JOIN raw\.con efe ON efe\.ide = p\.ide\b", proveedor), (
        "la mitad PROVEEDOR tiene que unir `raw.con efe ON efe.ide = p.ide`"
    )


def test_f094_proveedor_el_estado_mira_fecbaj_y_est() -> None:
    proveedor, _ = _mitades()
    case = _case_estado(proveedor)
    assert "efe.fecbaj" in case, "el estado de PROVEEDOR no mira `con.fecbaj`"
    assert "efe.est" in case, "el estado de PROVEEDOR no mira `con.est`"
    assert "p.fecrea" in case, "el estado de PROVEEDOR sigue necesitando `fecrea`"


def test_f094_proveedor_tres_estados_y_baja_manda() -> None:
    """BAJA primero: un efecto dado de baja nunca es VIVA ni LIQUIDADA, aunque
    tenga `fecrea` (2 efectos, 1.000,84 €, medidos el 2026-09-22). Si fuera
    LIQUIDADA su importe se sumaría a lo liquidado junto al del efecto que lo
    sustituye."""
    proveedor, _ = _mitades()
    case = _case_estado(proveedor)
    esperado = (
        "CASE WHEN COALESCE(efe.fecbaj, 0) <> 0 OR efe.est IN (14, 15) THEN 'BAJA' "
        "WHEN COALESCE(p.fecrea, 0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA' "
        "ELSE 'VIVA' END"
    )
    assert case == esperado, f"CASE de estado inesperado:\n{case}"


def test_f094_proveedor_vencida_solo_si_viva() -> None:
    """`vencida_sin_liquidar` no puede marcar un agrupado ni un pagado."""
    proveedor, _ = _mitades()
    m = re.search(r"CASE WHEN (.*?) THEN TRUE ELSE FALSE END AS vencida_sin_liquidar", proveedor)
    assert m
    condicion = m.group(1).rsplit("CASE WHEN ", 1)[-1]
    assert "COALESCE(efe.fecbaj, 0) = 0" in condicion
    assert "COALESCE(efe.est, 0) NOT IN (10, 14, 15)" in condicion
    assert "COALESCE(p.fecrea, 0) = 0" in condicion


def test_f094_se_publican_estado_sigrid_y_fecha_baja_en_las_dos_mitades() -> None:
    proveedor, cliente = _mitades()
    assert "efe.est AS estado_sigrid" in proveedor
    assert "retenciones.fn_sigrid_date(efe.fecbaj) AS fecha_baja" in proveedor
    assert "efe.est AS estado_sigrid" in cliente
    assert "retenciones.fn_sigrid_date(efe.fecbaj) AS fecha_baja" in cliente


def test_f094_el_ancho_de_estado_cabe() -> None:
    for mitad in _mitades():
        m = re.search(r"END::VARCHAR\((\d+)\) AS estado\b", mitad)
        assert m and int(m.group(1)) >= len("LIQUIDADA")


# ===========================================================================
# CLIENTE · se deja como estaba, y es una decisión, no un olvido
# ===========================================================================


def test_f094_cliente_conserva_el_estado_por_fecrea() -> None:
    """En `cob` el patrón NO es el de `pag`: los ~19,9 M€ con `fecbaj <> 0` están
    en estado 1 (Pendiente), no en 14 (Agrupado), y el criterio de `pag` deja
    2,12 M€ frente a 13,81 M€ de su contabilidad. Se corrige en una feature
    propia; hasta entonces el estado de CLIENTE no cambia."""
    _, cliente = _mitades()
    case = _case_estado(cliente)
    assert case == "CASE WHEN COALESCE(c.fecrea, 0) = 0 THEN 'VIVA' ELSE 'LIQUIDADA' END"
    assert re.search(r"LEFT JOIN raw\.con efe ON efe\.ide = c\.ide\b", cliente)


# ===========================================================================
# VISTAS · BAJA no suma dos veces ni pasa por liquidada
# ===========================================================================


def _vista(nombre: str) -> str:
    compacto = _compacto(_texto("02_views.sql"))
    m = re.search(
        rf"CREATE OR REPLACE VIEW retenciones\.{nombre} AS (.*?);", compacto
    )
    assert m, nombre
    return m.group(1)


def test_f094_el_neto_y_los_cargos_excluyen_baja() -> None:
    """El original agrupado y su agrupador son el MISMO dinero."""
    for vista in ("v_pbi_retencion_entidad", "v_pbi_retencion_resumen"):
        cuerpo = _vista(vista)
        assert "SUM(importe) FILTER (WHERE estado <> 'BAJA') AS neto_practicado" in cuerpo, vista
        assert "SUM(importe) FILTER (WHERE estado = 'BAJA') AS importe_baja" in cuerpo, vista
        assert "COUNT(*) FILTER (WHERE estado = 'BAJA') AS num_bajas" in cuerpo, vista
    entidad = _vista("v_pbi_retencion_entidad")
    assert "FILTER (WHERE importe > 0 AND estado <> 'BAJA') AS total_cargos" in entidad
    assert "FILTER (WHERE importe < 0 AND estado <> 'BAJA') AS total_abonos" in entidad


# ===========================================================================
# DICCIONARIO
# ===========================================================================


def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def test_f094_la_ficha_declara_baja_y_las_columnas_nuevas() -> None:
    columnas = _yaml("retenciones.yaml")["objetos"]["movimientos"]["columnas"]
    assert columnas["estado"]["valores"] == ["VIVA", "LIQUIDADA", "BAJA"]
    assert "fecbaj" in columnas["estado"]["significado"]
    assert "estado_sigrid" in columnas and "fecha_baja" in columnas


def test_f094_la_cifra_inflada_sale_del_diccionario() -> None:
    """34,7 M€ era el saldo inflado 4,3 veces: no puede seguir sirviéndose."""
    ordenes = _yaml("00_global.yaml")["ordenes_de_magnitud"]
    valores = [o["valor_aproximado"] for o in ordenes]
    assert 34700000 not in valores
    assert 8350000 in valores
