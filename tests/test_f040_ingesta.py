# tests/test_f040_ingesta.py
"""
F-040 · La ingesta del lado de ingresos (`config/tables_sigrid.yaml`, R1-R4),
sobre el texto del YAML: sin red ni BBDD.

Lo que defiende, por orden de lo que costaría un error:

1. **Ningún dato personal que no se haya pedido entra en `raw`** (R1, R3): `cli`
   y `dvf` van con LISTA BLANCA y una columna bancaria, de contraseña o de
   correo de facturación que se cuele tumba el test.
2. **Las listas son exactamente las del diseño** (`design_detalle.md` § A),
   que el dominio (`etl_sigrid/domain/ventas.py`) guarda como constantes.
3. **El censo de `raw` sube de 93 a 100** (R4).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain import ventas as v

RAIZ = Path(__file__).resolve().parents[1]
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"

#: Las siete tablas nuevas (R2) y `dvf`, ampliada (R3).
NUEVAS = ("cli", "cer", "cerpro", "cerrec", "cerprodes", "dvfpro", "dvfrec")
TOTAL_TABLAS = 100


@cache
def _texto() -> str:
    return RUTA_TABLAS.read_text(encoding="utf-8")


@cache
def _lista() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(_texto())["tables"])


def _tablas() -> dict[str, dict]:
    return {t["source_table"]: t for t in _lista()}


def _comentario_de(tabla: str) -> str:
    """El comentario que precede a la entrada `tabla` y la propia entrada."""
    texto = _texto()
    fin = texto.index(f"source_table: {tabla}\n")
    inicio = texto.rfind("- source_table:", 0, fin)
    trozo = texto[inicio if inicio >= 0 else 0: fin]
    sigue = texto[fin:]
    corte = sigue.find("- source_table:", 1)
    return trozo + (sigue[:corte] if corte >= 0 else sigue)


# ===========================================================================
# R1 · cli
# ===========================================================================


def test_f040_r1_cli_con_las_veinte_columnas_exactas() -> None:
    cli = _tablas()["cli"]
    assert tuple(cli["include_columns"]) == v.COLUMNAS_CLI
    assert v.COLUMNAS_CLI == v.COLUMNAS_CLI_NEGOCIO + v.COLUMNAS_CLI_CONTACTO
    assert v.COLUMNAS_CLI_NEGOCIO == (
        "ide", "tipcif", "cifpai", "cif", "raz", "perfis", "cenide", "taride", "secide",
        "pagide", "efeide", "cueide", "cueretide",
    )
    assert v.COLUMNAS_CLI_CONTACTO == ("dir1", "dir2", "dircpo", "dir", "tel", "tel2", "ele")


def test_f040_r1_si_entra_una_columna_prohibida_de_cli_falla() -> None:
    entran = set(_tablas()["cli"]["include_columns"])
    for columna in entran:
        assert not columna.startswith(v.PREFIJOS_PROHIBIDOS_CLI), (
            f"`cli.{columna}` empieza por un prefijo prohibido (R1)")
        assert columna not in v.COLUMNAS_PROHIBIDAS_CLI, f"`cli.{columna}` prohibida (R1)"


def test_f040_r1_las_prohibidas_de_cli_son_las_del_diseno() -> None:
    assert v.PREFIJOS_PROHIBIDOS_CLI == ("ban", "fax", "telsin", "tel2sin", "fac", "nom", "g3w")
    assert v.COLUMNAS_PROHIBIDAS_CLI == frozenset({
        "fecnac", "numseg", "clamai", "dirtex", "web", "dniper", "munide", "proide",
        "paiide", "g3wpas",
    })
    # Las del diseño que sí son de negocio no caen en la lista negra.
    for columna in v.COLUMNAS_CLI:
        assert not columna.startswith(v.PREFIJOS_PROHIBIDOS_CLI), columna
        assert columna not in v.COLUMNAS_PROHIBIDAS_CLI, columna


def test_f040_r1_cli_sin_lista_negra() -> None:
    assert _tablas()["cli"].get("exclude_columns") in (None, [])


# ===========================================================================
# R2 · cer, cerpro, dvfpro, cerrec, dvfrec y cerprodes
# ===========================================================================


def test_f040_r2_las_siete_tablas_declaradas_con_ide_y_sin_incremental() -> None:
    tablas = _tablas()
    for nombre in NUEVAS:
        assert nombre in tablas, f"`{nombre}` no está en tables_sigrid.yaml (R2)"
        entrada = tablas[nombre]
        assert entrada["target_table"] == nombre
        assert entrada["id_column"] == "ide"
        assert entrada["incremental_column"] is None, f"`{nombre}` no tiene tiemod (R2)"
        assert entrada["where"] is None, f"`{nombre}` se trae entera (R2)"


def test_f040_r2_cada_tabla_con_su_comentario_y_cifras_del_dia() -> None:
    for nombre in (*NUEVAS, "dvf"):
        comentario = _comentario_de(nombre)
        assert "F-040" in comentario, f"`{nombre}` sin comentario de F-040 (R2)"
        assert re.search(r"2026-11-0[67]", comentario), f"`{nombre}` sin la fecha de la medida"


def test_f040_r2_cer_cerpro_y_dvfpro_con_lista_blanca_exacta() -> None:
    tablas = _tablas()
    assert tuple(tablas["cer"]["include_columns"]) == v.COLUMNAS_CER
    assert tuple(tablas["cerpro"]["include_columns"]) == v.COLUMNAS_CERPRO
    assert tuple(tablas["dvfpro"]["include_columns"]) == v.COLUMNAS_DVFPRO


def test_f040_r2_las_listas_del_dominio_son_las_del_diseno() -> None:
    assert v.COLUMNAS_CER == (
        "ide", "cla", "entide", "cenide", "obride", "ctride", "expide", "fas", "fecdoc",
        "fecfac", "estfac", "idefac", "docoriide", "pagide", "efeide", "ivaide", "impbru",
        "impnet", "impdes", "imprec", "totbas", "totiva", "totdoc", "tot", "totpag",
        "totproori", "totprcori",
    )
    assert v.COLUMNAS_CERPRO == (
        "ide", "docide", "pos", "res", "can", "pre", "tot", "ivaide", "ivacuo", "cenide",
        "obride", "paride", "docoritip", "docoriide", "linoriide", "imporiori", "imporiant",
        "canoriori",
    )
    assert v.COLUMNAS_DVFPRO == (
        "ide", "docide", "pos", "res", "can", "pre", "tot", "ivaide", "ivacuo", "cenide",
        "obride", "paride", "docoritip", "docoriide", "linoriide", "unimed", "proide",
    )


def test_f040_r2_cerrec_y_dvfrec_sin_tex() -> None:
    for nombre in ("cerrec", "dvfrec"):
        entrada = _tablas()[nombre]
        assert entrada["exclude_columns"] == ["tex"], nombre
        assert not entrada.get("include_columns"), nombre


def test_f040_r2_cerprodes_entera() -> None:
    entrada = _tablas()["cerprodes"]
    assert entrada.get("exclude_columns") in (None, [])
    assert not entrada.get("include_columns")


# ===========================================================================
# R3 · dvf de 9 a 35 columnas
# ===========================================================================


def test_f040_r3_dvf_con_las_treinta_y_cinco_columnas() -> None:
    dvf = _tablas()["dvf"]
    assert tuple(dvf["include_columns"]) == v.COLUMNAS_DVF
    assert len(v.COLUMNAS_DVF) == 35 == len(set(v.COLUMNAS_DVF))
    assert v.COLUMNAS_DVF == v.COLUMNAS_DVF_NEGOCIO + v.COLUMNAS_PERSONALES_DVF
    # Las nueve de F-150 siguen delante y en su orden: `tesoreria` no cambia.
    assert v.COLUMNAS_DVF[:9] == (
        "ide", "cla", "entide", "cenide", "ctride", "fecdoc", "totbas", "totiva", "totdoc",
    )
    assert len(v.COLUMNAS_DVF_NEGOCIO) == 24
    assert v.COLUMNAS_PERSONALES_DVF == (
        "entcif", "entres", "diremp1", "dircon1", "dirdir1", "diremp2", "dircon2",
        "dirdir2", "diremp3", "dircon3", "dirdir3",
    )


def test_f040_r3_si_entra_una_columna_prohibida_de_dvf_falla() -> None:
    for columna in _tablas()["dvf"]["include_columns"]:
        assert not columna.startswith("ban"), f"`dvf.{columna}`: cuenta bancaria (R3)"
        assert columna not in v.COLUMNAS_PROHIBIDAS_DVF, f"`dvf.{columna}` prohibida (R3)"
    assert v.COLUMNAS_PROHIBIDAS_DVF == frozenset({
        "emptex", "entcod", "entref", "entciftip", "entcifpai", "empcif",
    })


# ===========================================================================
# R4 · censo
# ===========================================================================


def test_f040_r4_censo_de_raw_cien_tablas() -> None:
    assert len(_tablas()) == TOTAL_TABLAS
    assert len(_lista()) == TOTAL_TABLAS, "tabla declarada dos veces"


def test_f040_r4_ninguna_vacia_entra() -> None:
    """`obrcer`, `cerpropar` y `dvfpropar` están VACÍAS en Sigrid: no entran."""
    for vacia in ("obrcer", "cerpropar", "dvfpropar"):
        assert vacia not in _tablas(), vacia


def test_f040_r4_el_snippet_obsoleto_esta_borrado() -> None:
    assert not (RAIZ / "config" / "tables_sigrid_venta_snippet.yaml").exists()
