# -*- coding: utf-8 -*-
"""BACKLOG.md es una proyección de features.json y tiene que estar al día.

Si estos tests fallan, no hay que tocar `BACKLOG.md`: se regenera con
`python harness/backlog.py` (o arrancando `bash harness/init.sh`).
"""

from __future__ import annotations

import io
import json
import os

from harness import backlog


def _leer_features() -> dict:
    with io.open(backlog.FEATURES, encoding="utf-8") as fh:
        return json.load(fh)


def test_backlog_md_existe_y_esta_al_dia():
    assert os.path.exists(backlog.SALIDA), (
        "falta BACKLOG.md: generalo con 'python harness/backlog.py'"
    )
    with io.open(backlog.SALIDA, encoding="utf-8") as fh:
        actual = fh.read()
    assert actual == backlog.construir(_leer_features()), (
        "BACKLOG.md no coincide con features.json: regeneralo con "
        "'python harness/backlog.py'"
    )


def test_la_generacion_es_determinista():
    datos = _leer_features()
    assert backlog.construir(datos) == backlog.construir(datos)


def test_estan_todas_las_features_con_su_estado_y_prioridad():
    datos = _leer_features()
    texto = backlog.construir(datos)
    for feature in datos["features"]:
        assert feature["id"] in texto, feature["id"]
        assert feature["title"].split("|")[0][:40] in texto, feature["id"]
    abiertas = [f for f in datos["features"] if f["status"] != "done"]
    assert "%d abiertas" % len(abiertas) in texto


def _ids_de_seccion(texto: str, titulo: str) -> list[str]:
    bloque = texto.split("## %s\n" % titulo, 1)[1].split("\n## ", 1)[0]
    return [
        linea.split("|")[1].strip()
        for linea in bloque.splitlines()
        if linea.startswith("| F-")
    ]


def test_cada_estado_tiene_su_tabla_ordenada_por_prioridad():
    datos = _leer_features()
    texto = backlog.construir(datos)
    prioridades = {f["id"]: f.get("priority", 999) for f in datos["features"]}
    for estado, titulo, _ in backlog._SECCIONES:
        ids = _ids_de_seccion(texto, titulo)
        esperados = {f["id"] for f in datos["features"] if f["status"] == estado}
        assert set(ids) == esperados, titulo
        orden = [prioridades[fid] for fid in ids]
        assert orden == sorted(orden), (titulo, orden)


def test_una_seccion_vacia_lo_dice_y_un_estado_raro_no_se_pierde():
    datos = {
        "features": [
            {"id": "F-002", "title": "B", "status": "pending", "priority": 2},
            {"id": "F-001", "title": "A", "status": "pending", "priority": 1},
            {"id": "F-003", "title": "C", "status": "en_pausa", "priority": 3},
        ]
    }
    texto = backlog.construir(datos)
    for _, titulo, vacio in backlog._SECCIONES:
        assert "## %s\n" % titulo in texto
        if titulo != "Backlog":
            assert vacio in texto, titulo
    assert _ids_de_seccion(texto, "Backlog") == ["F-001", "F-002"]
    assert _ids_de_seccion(texto, "Otros estados") == ["F-003"]
    assert "3 abiertas (0 en curso, 0 con la spec lista, 0 bloqueadas y 2 en backlog)" in texto


def test_no_lleva_marca_de_tiempo():
    """Sin timestamp: el fichero solo cambia cuando cambia el backlog."""
    texto = backlog.construir(_leer_features())
    for palabra in ("generado el", "Generado el", "timestamp", "datetime"):
        assert palabra not in texto
