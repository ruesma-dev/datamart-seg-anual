# tests/test_f006_nombres_fichero.py
"""
Los nombres de fichero del diccionario tienen que poder VERSIONARSE (F-006).

Este fichero existe por un fallo que no dio la cara hasta el `git add`: el
esquema `aux` produce `config/diccionario/aux.yaml`, y **`AUX` es un nombre de
dispositivo reservado de MS-DOS que Windows sigue honrando**. Python lo crea y
lo lee sin quejarse —los 618 tests pasaron con la ficha dentro—, pero git no
puede abrirlo:

    error: open("config/diccionario/aux.yaml"): No such file or directory
    error: unable to index file 'config/diccionario/aux.yaml'

Un fichero que existe, que el ETL carga y que el control de versiones no puede
guardar es lo peor de los dos mundos: funciona en el puesto de quien lo escribió
y no llega a ningún otro sitio.

`aux` no es el único: `con`, `prn`, `nul` y los `com1`..`lpt9` caen igual, y
`con` es además el nombre de la tabla central de Sigrid. Por eso la comprobación
no lista `aux`, sino que barre la familia entera.
"""

from __future__ import annotations

import pathlib

import pytest

#: Los nombres de dispositivo que MS-DOS reservó y Windows nunca soltó. Un
#: fichero llamado así —con cualquier extensión— es inabrible por su nombre.
DISPOSITIVOS_RESERVADOS = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

DIR_DICCIONARIO = pathlib.Path(__file__).resolve().parents[1] / "config" / "diccionario"


def test_f006_ningun_fichero_del_diccionario_usa_un_nombre_reservado() -> None:
    """El barrido sobre lo que hay en disco. Es el que impide la reincidencia."""
    culpables = [
        p.name
        for p in DIR_DICCIONARIO.glob("*.yaml")
        if p.stem.lower() in DISPOSITIVOS_RESERVADOS
    ]
    assert culpables == [], (
        f"{culpables} usa un nombre de dispositivo reservado de Windows: git no "
        f"puede indexar el fichero aunque Python lo lea. La convención es "
        f"añadirle un `_` al final (`aux_.yaml`), como se hace en Python con las "
        f"palabras reservadas"
    )


def test_f006_el_cargador_acepta_el_sufijo_de_escape(tmp_path: pathlib.Path) -> None:
    """`aux_.yaml` declarando `esquema: aux` tiene que cargar sin protestar.

    El cargador exige que el nombre del fichero case con el esquema —y hace bien,
    es lo que impide que una ficha acabe colgando del esquema equivocado—. La
    única excepción admisible es la que impone el sistema operativo.
    """
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    (tmp_path / "00_global.yaml").write_text(
        "version: 1\nbase: d\nesquemas: {aux: x}\nreglas: []\npendientes: []\n",
        encoding="utf-8",
    )
    (tmp_path / "aux_.yaml").write_text(
        "version: 1\nesquema: aux\nobjetos:\n"
        "  t:\n    tipo: tabla\n    capa: preparacion\n"
        "    consumo_recomendado: false\n    motivo_no_consumo: x\n"
        "    descripcion: x\n    grano: x\n    clave_negocio: []\n"
        "    refresco: estatico\n    columnas: {}\n",
        encoding="utf-8",
    )
    dicc, _ = cargar_diccionario(tmp_path)
    assert [f.nombre for f in dicc.fichas] == ["aux.t"]


def test_f006_el_sufijo_de_escape_no_sirve_para_esquemas_normales(
    tmp_path: pathlib.Path,
) -> None:
    """La excepción es SOLO para los reservados; si no, sería una puerta trasera.

    Sin esto, `mart_.yaml` colaría, y el día que alguien duplique un esquema por
    error tendríamos dos ficheros cargando fichas del mismo sitio sin que nada
    lo diga.
    """
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    (tmp_path / "00_global.yaml").write_text(
        "version: 1\nbase: d\nesquemas: {mart: x}\nreglas: []\npendientes: []\n",
        encoding="utf-8",
    )
    (tmp_path / "mart_.yaml").write_text(
        "version: 1\nesquema: mart\nobjetos: {}\n", encoding="utf-8"
    )
    with pytest.raises(DiccionarioIlegible) as exc:
        cargar_diccionario(tmp_path)
    assert "mart_" in str(exc.value)
