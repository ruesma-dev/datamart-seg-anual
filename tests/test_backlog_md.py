# tests/test_backlog_md.py
"""BACKLOG.md es una proyección de features.json y tiene que estar al día.

Si los tests contra el `features.json` real fallan, no hay que tocar
`BACKLOG.md`: se regenera con `python harness/backlog.py` (o arrancando
`bash harness/init.sh`).

La estructura (una tabla por estado) viene de la 1.7.15; el orden de las
terminadas por `fecha_cierre`, de F-022; el tablero de siete columnas sobre
los ocho estados del flujo, de F-042. Los tests de F-022 y F-042 trabajan sobre un backlog
sintético: este fichero viaja a cada proyecto instalado y no puede depender de
lo que haya en su `features.json`.
"""

from __future__ import annotations

import datetime
import io
import json
import os

import pytest

from harness import backlog

#: Las columnas del tablero, en el orden en que tienen que salir (F-042, R16;
#: invertido por F-070, humano 2026-11-12): lo más avanzado arriba, salvo Done,
#: que sigue abajo. Una sola Review para `in_review` y `human_review`.
SECCIONES = (
    "## Review",
    "## Blocked",
    "## In progress",
    "## Spec aprobada",
    "## To do",
    "## Backlog",
    "## Done",
)


def _f(fid: str, estado: str, prioridad: int = 5, **extra: object) -> dict:
    ficha = {
        "id": fid,
        "title": "Titulo de %s" % fid,
        "description": "Descripcion de %s." % fid,
        "status": estado,
        "sdd": False,
        "rigor": "estandar",
        "priority": prioridad,
    }
    ficha.update(extra)
    return ficha


def _bloque(texto: str, seccion: str) -> str:
    """El texto de una sección, hasta la siguiente `## `."""
    resto = texto.split(seccion + "\n", 1)[1]
    return resto.split("\n## ", 1)[0]


def _ids(bloque: str) -> list[str]:
    return [
        linea.split("|")[1].strip()
        for linea in bloque.splitlines()
        if linea.startswith("| F-")
    ]


def _fila(bloque: str, fid: str) -> str:
    return next(li for li in bloque.splitlines() if li.startswith("| %s " % fid))


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
    return _ids(_bloque(texto, "## %s" % titulo))


def test_cada_estado_tiene_su_tabla_ordenada_por_prioridad():
    datos = _leer_features()
    texto = backlog.construir(datos)
    prioridades = {f["id"]: f.get("priority", 999) for f in datos["features"]}
    for titulo, de_la_columna, _ in backlog._COLUMNAS:
        ids = _ids_de_seccion(texto, titulo)
        esperados = {f["id"] for f in datos["features"]
                     if f["status"] in de_la_columna}
        assert set(ids) == esperados, titulo
        if de_la_columna == ("done",):
            # Las terminadas no van por prioridad sino por fecha de cierre.
            por_cierre = sorted(
                (f for f in datos["features"] if f["status"] == "done"),
                key=backlog._clave_cierre,
            )
            assert ids == [f["id"] for f in por_cierre], titulo
            continue
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
    for titulo, _, vacio in backlog._COLUMNAS:
        assert "## %s\n" % titulo in texto
        if titulo != "Backlog":
            assert vacio in texto, titulo
    assert _ids_de_seccion(texto, "Backlog") == ["F-001", "F-002"]
    assert _ids_de_seccion(texto, "Otros estados") == ["F-003"]
    assert "**3 features**, 3 abiertas y 0 terminadas" in texto
    assert "Por columna: 0 en Review, 0 en Blocked, 0 en In progress" in texto
    assert "0 en To do, 2 en Backlog y 0 en Done. Otros estados: 1." in texto
    assert texto.index("## Done\n") < texto.index("## Otros estados\n")
    sin_raros = backlog.construir({"features": datos["features"][:2]})
    assert "## Otros estados" not in sin_raros


def test_no_lleva_marca_de_tiempo():
    """Sin timestamp: el fichero solo cambia cuando cambia el backlog."""
    texto = backlog.construir(_leer_features())
    for palabra in ("generado el", "Generado el", "timestamp", "datetime"):
        assert palabra not in texto


# --- F-022: orden de secciones y fecha de cierre (backlog sintético) ---------


def _sintetico() -> dict:
    return {
        "features": [
            _f("F-010", "done", 1, fecha_cierre="2026-08-25"),
            _f("F-011", "pending", 3),
            _f("F-012", "blocked", 2),
            _f("F-013", "in_progress", 4),
            _f("F-014", "spec_ready", 6),
            _f("F-015", "pending", 1),
            _f("F-016", "done", 9, fecha_cierre="2026-09-27"),
            _f("F-017", "done", 2),
            _f("F-018", "spec_ready", 2),
            _f("F-019", "done", 1),
            _f("F-020", "done", 7, fecha_cierre="2025-12-31"),
        ]
    }


def test_f022_r1_secciones_en_orden_fijo():
    texto = backlog.construir(_sintetico())
    posiciones = [texto.index(s + "\n") for s in SECCIONES]
    assert posiciones == sorted(posiciones), posiciones
    assert "## Trabajo abierto" not in texto
    assert texto.index("## Done\n") < texto.index("## Detalle\n")


def test_f022_r1_reparto_por_estado():
    texto = backlog.construir(_sintetico())
    assert _ids(_bloque(texto, "## In progress")) == ["F-013"]
    assert _ids(_bloque(texto, "## Spec aprobada")) == ["F-018", "F-014"]
    assert _ids(_bloque(texto, "## Blocked")) == ["F-012"]
    assert _ids(_bloque(texto, "## Backlog")) == ["F-015", "F-011"]
    assert sorted(_ids(_bloque(texto, "## Done"))) == [
        "F-010", "F-016", "F-017", "F-019", "F-020",
    ]


def test_f022_r2_terminadas_por_fecha_descendente_con_columna():
    texto = backlog.construir(_sintetico())
    bloque = _bloque(texto, "## Done")
    assert "Cierre" in bloque.strip().splitlines()[0]
    assert _ids(bloque)[:3] == ["F-016", "F-010", "F-020"]
    assert "2026-09-27" in _fila(bloque, "F-016")


def test_f022_r2_terminadas_sin_fecha_al_final_marcadas_y_deterministas():
    datos = _sintetico()
    texto = backlog.construir(datos)
    bloque = _bloque(texto, "## Done")
    # Sin fecha: al final, por prioridad y luego por id.
    assert _ids(bloque)[3:] == ["F-019", "F-017"]
    for fid in ("F-019", "F-017"):
        assert "sin fecha" in _fila(bloque, fid), fid
    # El orden no depende del orden de entrada.
    datos["features"].reverse()
    assert backlog.construir(datos) == texto


def test_f022_r2_empate_de_fecha_se_desempata_por_prioridad_e_id():
    datos = {
        "features": [
            _f("F-003", "done", 2, fecha_cierre="2026-09-01"),
            _f("F-002", "done", 2, fecha_cierre="2026-09-01"),
            _f("F-001", "done", 5, fecha_cierre="2026-09-01"),
        ]
    }
    assert _ids(_bloque(backlog.construir(datos), "## Done")) == [
        "F-002", "F-003", "F-001",
    ]


def test_f022_r3_sin_fecha_cierre_no_falla():
    """Compatibilidad: los proyectos ya instalados no llevan el campo."""
    datos = {"features": [
        _f("F-001", "done", 1),
        _f("F-002", "done", 2, fecha_cierre=None),
    ]}
    bloque = _bloque(backlog.construir(datos), "## Done")
    assert _ids(bloque) == ["F-001", "F-002"]
    assert bloque.count("sin fecha") == 2


@pytest.mark.parametrize(
    "valor",
    ["2026-9-27", "27/09/2026", "2026-02-30", "2026-13-01", "20260927",
     "2026-W39-6", " 2026-09-27", "2026-09-27T10:00", 20260927, "", True,
     "２０２６-０９-２７"],
)
def test_f022_r3_fecha_mal_formada_se_rechaza_nombrando_la_feature(valor):
    datos = {"features": [
        _f("F-001", "done", 1),
        _f("F-042", "done", 2, fecha_cierre=valor),
    ]}
    with pytest.raises(ValueError) as exc:
        backlog.construir(datos)
    assert "F-042" in str(exc.value)
    assert "fecha_cierre" in str(exc.value)


def test_f022_r3_tambien_se_valida_en_una_feature_abierta():
    datos = {"features": [_f("F-043", "pending", 1, fecha_cierre="ayer")]}
    with pytest.raises(ValueError, match="F-043"):
        backlog.construir(datos)


def test_f022_r3_con_fecha_mala_main_falla_y_no_escribe_backlog(
    tmp_path, monkeypatch, capsys
):
    features = tmp_path / "features.json"
    salida = tmp_path / "BACKLOG.md"
    features.write_text(json.dumps({"features": [
        _f("F-042", "done", 1, fecha_cierre="2026-02-30")]}), encoding="utf-8")
    salida.write_text("anterior\n", encoding="utf-8")
    monkeypatch.setattr(backlog, "FEATURES", str(features))
    monkeypatch.setattr(backlog, "SALIDA", str(salida))

    assert backlog.main([]) == 1
    assert backlog.main(["--comprobar"]) == 1
    assert salida.read_text(encoding="utf-8") == "anterior\n"
    err = capsys.readouterr().err
    assert "F-042" in err and "fecha_cierre" in err


def test_main_regenera_con_0_y_comprobar_detecta_el_desfase_con_1(
    tmp_path, monkeypatch
):
    """init.sh lee el código de salida: 0 = generado (o al día), otro = fallo."""
    features = tmp_path / "features.json"
    salida = tmp_path / "BACKLOG.md"
    features.write_text(json.dumps({"features": [_f("F-001", "pending", 1)]}),
                        encoding="utf-8")
    salida.write_text("desfasado\n", encoding="utf-8")
    monkeypatch.setattr(backlog, "FEATURES", str(features))
    monkeypatch.setattr(backlog, "SALIDA", str(salida))

    assert backlog.main(["--comprobar"]) == 1
    assert salida.read_text(encoding="utf-8") == "desfasado\n"
    assert backlog.main([]) == 0
    assert "## Backlog" in salida.read_text(encoding="utf-8")
    assert backlog.main(["--comprobar"]) == 0


def test_f022_r4_salida_pura_sin_fecha_de_hoy():
    datos = _sintetico()
    texto = backlog.construir(datos)
    assert backlog.construir(json.loads(json.dumps(datos))) == texto
    sin_datos = texto.replace("2026-09-27", "")
    assert datetime.date.today().isoformat() not in sin_datos


def test_f022_r4_el_detalle_muestra_la_fecha_de_cierre():
    texto = backlog.construir(_sintetico())
    detalle = texto.split("## Detalle\n", 1)[1]
    ficha = detalle.split("### F-016 ", 1)[1].split("\n### ", 1)[0]
    assert "cerrada el 2026-09-27" in ficha
    ficha = detalle.split("### F-017 ", 1)[1].split("\n### ", 1)[0]
    assert "sin fecha de cierre" in ficha


def test_f022_r5_leader_manda_escribir_fecha_cierre_al_marcar_done():
    assert "fecha_cierre" in _fila_leader("done")


# --- F-042: el protocolo del líder (leader.md) ---------------------------------


def _leader() -> str:
    ruta = os.path.join(backlog.RAIZ, ".claude", "agents", "leader.md")
    with open(ruta, encoding="utf-8") as fh:
        return fh.read()


def _fila_leader(estado: str) -> str:
    return next(li for li in _leader().splitlines()
                if li.startswith(f"| `{estado}` |"))


def test_f042_r25_una_fila_por_estado_con_quien_lo_pone():
    from harness import estados

    for estado in estados.ESTADOS:
        celdas = [c.strip() for c in _fila_leader(estado).strip("|").split("|")]
        assert celdas[1] in ("líder", "cualquiera"), estado
    assert "| revisión OK" not in _leader()


def test_f042_r25_las_vueltas_estan_escritas():
    fila = _fila_leader("in_progress")
    assert "in_review" in fila and "CHANGES_REQUESTED" in fila
    assert "human_review" in fila and "pide cambios" in fila
    assert "vuelve al estado del que salió" in _fila_leader("blocked")
    todo = _fila_leader("todo")
    assert "retira" in todo and "vuelve a `pending`" in todo


def test_f042_r25_ocho_filas_en_el_orden_de_estados_py():
    from harness import estados

    filas = [li.split("`")[1] for li in _leader().splitlines()
             if li.startswith("| `")]
    assert tuple(filas) == estados.ESTADOS
    assert "Ocho estados (`harness/estados.py`)" in " ".join(_leader().split())


def test_f042_r34_pending_no_arranca_nada_y_todo_es_el_compromiso_del_humano():
    pending = _fila_leader("pending")
    assert "No arrancas nada" in pending
    assert "spec-author" not in pending and "PARADA 1" not in pending
    todo = _fila_leader("todo")
    assert "el humano la compromete" in todo
    assert "una fase del plan" in todo
    assert "`sdd: true`" in todo and "spec-author" in todo
    assert "`sdd: false`" in todo and "PARADA 1" in todo
    texto = " ".join(_leader().split())
    assert ("Solo lanzas el spec-author o el implementer sobre una feature que "
            "viene de `todo`") in texto
    assert ("Si no hay nada en `todo`, no arrancas nada de `pending`: propones "
            "al humano qué comprometer") in texto


def test_f042_r34_orden_de_prioridad_terminado_en_todo():
    texto = " ".join(_leader().split())
    assert ("`blocked` > `human_review` > `in_review` > `in_progress` > "
            "`spec_ready` > `todo`.") in texto
    assert "> `pending`" not in texto


def test_f042_r26_cada_cambio_de_estado_regenera_el_backlog_en_el_momento():
    texto = " ".join(_leader().split())
    assert ("Cada cambio de estado se escribe en `features.json` y regenera "
            "`BACKLOG.md` (`python harness/backlog.py`) en ese momento") in texto
    assert "mismo commit" in texto
    assert "Ninguna fase de un plan se cierra sin el backlog al día" in texto


def test_f042_r27_done_solo_desde_human_review_con_el_ok_del_humano():
    fila = _fila_leader("done")
    assert "SOLO desde `human_review`" in fila and "OK del humano" in fila
    assert "ok_humano" in fila and "fecha_cierre" in fila
    revision = _fila_leader("human_review")
    assert "APROBADO del último reviewer" in revision and "PARADA 2" in revision
    texto = " ".join(_leader().split())
    # F-070: con dos pasadas, lo lleva el último reviewer (el de evidencias si lo hay).
    assert ("El APPROVED del último reviewer —el de evidencias si lo hay— lleva la feature a "
            "`human_review`, no a `done`") in texto


def test_f042_r28_spec_aprobada_la_anota_el_lider_y_sin_ella_no_hay_implementer():
    assert "spec_aprobada" in _fila_leader("spec_ready")
    assert "humano" in _fila_leader("spec_ready")
    fila = _fila_leader("in_progress")
    assert "`sdd: true`" in fila and "spec_aprobada" in fila
    assert "sin ella no lanzas el implementer" in fila


def test_f042_r29_express_salta_in_review_pero_nunca_human_review():
    texto = " ".join(_leader().split())
    assert "El carril `express` salta `in_review`, pero nunca `human_review`" in texto
    assert "express" in _fila_leader("in_review")


# --- F-042: BACKLOG.md como tablero (backlog sintético) ----------------------


def _celda(bloque: str, fid: str, columna: str) -> str:
    """El valor de `columna` en la fila de `fid` de la tabla de `bloque`."""
    cabecera = next(li for li in bloque.splitlines() if li.startswith("| #"))
    nombres = [c.strip() for c in cabecera.strip("|").split("|")]
    celdas = [c.strip() for c in _fila(bloque, fid).strip("|").split("|")]
    return celdas[nombres.index(columna)]


def _cabecera(bloque: str) -> list[str]:
    cabecera = next(li for li in bloque.splitlines() if li.startswith("| #"))
    return [c.strip() for c in cabecera.strip("|").split("|")]


def _tablero() -> dict:
    """Una feature (o más) en cada uno de los ocho estados."""
    return {
        "features": [
            _f("F-101", "pending", 2, branch="feature/F-101-a"),
            _f("F-110", "todo", 3, branch="feature/F-110-h"),
            _f("F-111", "todo", 1),
            _f("F-102", "spec_ready", 3, branch="feature/F-102-b",
               spec_aprobada="2026-10-20"),
            _f("F-103", "spec_ready", 1, branch="feature/F-103-c"),
            _f("F-104", "in_progress", 4, branch="feature/F-104-d"),
            _f("F-105", "in_review", 5, branch="feature/F-105-e"),
            _f("F-106", "human_review", 6, branch="feature/F-106-f",
               agente="otro"),
            _f("F-107", "done", 7, fecha_cierre="2026-10-01",
               ok_humano="2026-10-02", spec_aprobada="2026-09-20"),
            _f("F-108", "done", 8, fecha_cierre="2026-10-10"),
            _f("F-109", "blocked", 9, branch="feature/F-109-g"),
        ]
    }


#: La columna del tablero de cada estado (R16).
SECCION_DE_ESTADO = {
    "pending": "## Backlog",
    "todo": "## To do",
    "spec_ready": "## Spec aprobada",
    "in_progress": "## In progress",
    "blocked": "## Blocked",
    "in_review": "## Review",
    "human_review": "## Review",
    "done": "## Done",
}


def test_f042_r16_siete_columnas_en_orden_y_cada_feature_en_la_suya():
    texto = backlog.construir(_tablero())
    posiciones = [texto.index(s + "\n") for s in SECCIONES]
    assert posiciones == sorted(posiciones), posiciones
    assert texto.index("Resumen:") < posiciones[0]
    titulos = [li for li in texto.splitlines() if li.startswith("## ")]
    assert titulos[:7] == list(SECCIONES)
    datos = _tablero()
    for seccion in SECCIONES:
        esperados = sorted(
            (f for f in datos["features"]
             if SECCION_DE_ESTADO[f["status"]] == seccion),
            key=lambda f: (f["priority"], f["id"]),
        )
        if seccion == "## Done":
            esperados.sort(key=lambda f: f["fecha_cierre"], reverse=True)
        assert _ids(_bloque(texto, seccion)) == [f["id"] for f in esperados], seccion


def test_f042_r16_las_columnas_cubren_los_estados_de_estados_py_sin_repetir():
    """Si mañana nace un estado, el tablero no lo pierde en silencio."""
    from harness import estados

    assert ["## " + titulo for titulo, _, _ in backlog._COLUMNAS] == list(SECCIONES)
    todos = [e for _, de_la_columna, _ in backlog._COLUMNAS for e in de_la_columna]
    assert len(todos) == len(set(todos)), todos
    assert set(todos) == set(estados.ESTADOS)
    columna_de = {e: "## " + t for t, col, _ in backlog._COLUMNAS for e in col}
    assert columna_de == SECCION_DE_ESTADO


def test_f042_r17_blocked_tras_in_progress_y_una_sola_review():
    texto = backlog.construir(_tablero())
    # F-070: el orden se invierte (Review arriba); Blocked sigue junto a In progress.
    assert (texto.index("## Review\n") < texto.index("## Blocked\n")
            < texto.index("## In progress\n") < texto.index("## Done\n"))
    assert _ids(_bloque(texto, "## Blocked")) == ["F-109"]
    # Las dos en una tabla, por prioridad; «La tiene» las distingue.
    assert _ids(_bloque(texto, "## Review")) == ["F-105", "F-106"]
    for viejo in ("## Terminadas", "## Bloqueadas", "## En QA",
                  "## En revisión humana", "## Spec lista"):
        assert viejo not in texto, viejo


def test_f042_r18_seccion_vacia_en_cursiva_y_estado_raro_en_otros():
    texto = backlog.construir({"features": [_f("F-001", "en_pausa", 1)]})
    for seccion in SECCIONES:
        cuerpo = _bloque(texto, seccion).strip()
        assert cuerpo.startswith("_") and cuerpo.endswith("_"), seccion
        assert "\n" not in cuerpo, seccion
    vacios = [vacio for _, _, vacio in backlog._COLUMNAS]
    assert len(set(vacios)) == len(vacios), "cada columna dice lo suyo"
    assert _ids(_bloque(texto, "## Otros estados")) == ["F-001"]


@pytest.mark.parametrize("estado,quien", [
    ("in_progress", "implementer"),
    ("in_review", "reviewer"),
    ("human_review", "humano"),
])
def test_f042_r19_activos_con_rama_y_la_tiene_derivada_del_estado(estado, quien):
    texto = backlog.construir(_tablero())
    bloque = _bloque(texto, SECCION_DE_ESTADO[estado])
    fid = next(f["id"] for f in _tablero()["features"] if f["status"] == estado)
    assert _celda(bloque, fid, "La tiene") == quien
    assert _celda(bloque, fid, "Rama").startswith("`feature/" + fid)


def test_f042_r19_ningun_campo_alimenta_la_tiene_y_solo_en_in_progress_y_review():
    texto = backlog.construir(_tablero())
    assert "otro" not in _fila(_bloque(texto, "## Review"), "F-106")
    for seccion in ("## Backlog", "## To do", "## Spec aprobada", "## Done",
                    "## Blocked"):
        assert "La tiene" not in _cabecera(_bloque(texto, seccion)), seccion


def test_f042_r20_spec_aprobada_con_fecha_o_pendiente_de_tu_aprobacion():
    bloque = _bloque(backlog.construir(_tablero()), "## Spec aprobada")
    assert _celda(bloque, "F-102", "Spec aprobada") == "2026-10-20"
    assert _celda(bloque, "F-103", "Spec aprobada") == "pendiente de tu aprobación"
    assert _celda(bloque, "F-103", "Rama") == "`feature/F-103-c`"


def test_f042_r21_terminadas_por_cierre_con_columna_ok_humano():
    bloque = _bloque(backlog.construir(_tablero()), "## Done")
    assert _ids(bloque) == ["F-108", "F-107"]
    assert _celda(bloque, "F-107", "OK humano") == "2026-10-02"
    assert _celda(bloque, "F-108", "OK humano") == "sin anotar"
    assert _celda(bloque, "F-107", "Cierre") == "2026-10-01"
    assert "Rama" not in _cabecera(bloque)


def test_f042_r22_resumen_con_el_recuento_de_cada_columna():
    texto = backlog.construir(_tablero())
    linea = next(li for li in texto.splitlines() if li.startswith("Resumen:"))
    assert linea == (
        "Resumen: **11 features**, 9 abiertas y 2 terminadas. Por columna: "
        "2 en Review, 1 en Blocked, 1 en In progress, 2 en Spec aprobada, "
        "2 en To do, 1 en Backlog y 2 en Done."
    )


def test_f042_r22_r23_todo_en_su_columna_y_en_el_detalle():
    texto = backlog.construir(_tablero())
    assert _ids(_bloque(texto, "## To do")) == ["F-111", "F-110"]
    detalle = texto.split("## Detalle\n", 1)[1]
    ficha = detalle.split("### F-110 ", 1)[1].split("\n### ", 1)[0]
    assert "estado **to do (comprometida)**" in ficha


def test_f042_r23_el_detalle_muestra_spec_aprobada_y_ok_humano():
    detalle = backlog.construir(_tablero()).split("## Detalle\n", 1)[1]
    ficha = detalle.split("### F-107 ", 1)[1].split("\n### ", 1)[0]
    assert "spec aprobada el 2026-09-20" in ficha
    assert "OK del humano el 2026-10-02" in ficha
    ficha = detalle.split("### F-108 ", 1)[1].split("\n### ", 1)[0]
    assert "spec aprobada" not in ficha and "OK del humano" not in ficha
    ficha = detalle.split("### F-105 ", 1)[1].split("\n### ", 1)[0]
    assert "estado **en QA / revisión**" in ficha
    ficha = detalle.split("### F-106 ", 1)[1].split("\n### ", 1)[0]
    assert "estado **en revisión humana**" in ficha


def test_f042_r24_salida_pura_e_independiente_del_orden():
    datos = _tablero()
    texto = backlog.construir(datos)
    datos["features"].reverse()
    assert backlog.construir(datos) == texto
    assert datetime.date.today().isoformat() not in texto


@pytest.mark.parametrize("campo", ["spec_aprobada", "ok_humano", "fecha_cierre"])
def test_f042_r9_fecha_nueva_mal_formada_hace_fallar_el_tablero(campo):
    datos = {"features": [_f("F-001", "pending", 1),
                          _f("F-077", "in_review", 2, **{campo: "2026-02-30"})]}
    with pytest.raises(ValueError) as exc:
        backlog.construir(datos)
    assert "F-077" in str(exc.value) and campo in str(exc.value)


def test_f042_r9_main_con_ok_humano_malo_no_escribe(tmp_path, monkeypatch, capsys):
    features = tmp_path / "features.json"
    salida = tmp_path / "BACKLOG.md"
    features.write_text(json.dumps({"features": [
        _f("F-077", "done", 1, ok_humano="28/10/2026")]}), encoding="utf-8")
    salida.write_text("anterior\n", encoding="utf-8")
    monkeypatch.setattr(backlog, "FEATURES", str(features))
    monkeypatch.setattr(backlog, "SALIDA", str(salida))
    assert backlog.main([]) == 1
    assert salida.read_text(encoding="utf-8") == "anterior\n"
    err = capsys.readouterr().err
    assert "F-077" in err and "ok_humano" in err


def test_f042_backlog_py_se_ejecuta_como_script(tmp_path):
    """init.sh lo llama como `python harness/backlog.py`, no con -m."""
    import subprocess
    import sys

    proceso = subprocess.run(
        [sys.executable, os.path.join(backlog.RAIZ, "harness", "backlog.py"),
         "--comprobar"],
        cwd=str(tmp_path), capture_output=True, text=True, check=False,
    )
    assert "ModuleNotFoundError" not in proceso.stderr, proceso.stderr
    assert "ImportError" not in proceso.stderr, proceso.stderr
    assert proceso.returncode in (0, 1), proceso.stderr


# --- F-040 R25: cerradas por mes del carril express ----------------------------


def _express(fid: str, cierre: str | None) -> dict:
    extra = {"fecha_cierre": cierre} if cierre else {}
    return _f(fid, "done", rigor="express", **extra)


def test_f040_r25_cuenta_las_express_cerradas_por_mes_en_orden() -> None:
    texto = backlog.construir({"features": [
        _express("F-001", "2026-11-03"), _express("F-002", "2026-10-30"),
        _express("F-003", "2026-10-01"), _express("F-004", "2026-10-02"),
    ]})

    assert "Express cerradas por mes: 2026-10: 3 · 2026-11: 1\n" in texto


def test_f040_r25_la_linea_va_en_la_columna_done() -> None:
    texto = backlog.construir({"features": [_express("F-001", "2026-10-30")]})

    assert "Express cerradas por mes" in _bloque(texto, "## Done")


@pytest.mark.parametrize("ficha", [
    _express("F-001", None),
    _f("F-001", "done", fecha_cierre="2026-10-30"),
    _f("F-001", "in_progress", rigor="express", fecha_cierre="2026-10-30"),
], ids=["sin fecha", "otro rigor", "sin cerrar"])
def test_f040_r25_lo_demas_no_cuenta(ficha: dict) -> None:
    assert "Express cerradas" not in backlog.construir({"features": [ficha]})


def test_f040_r25_sin_express_el_fichero_no_cambia_un_caracter(monkeypatch) -> None:
    """Se compara con la salida sin la línea, añadiendo y quitando una express."""
    base = [_f("F-001", "done", fecha_cierre="2026-10-30"), _f("F-002", "todo")]
    sin_express = backlog.construir({"features": base})

    monkeypatch.setattr(backlog, "_express_por_mes", lambda _features: None)

    assert backlog.construir({"features": base}) == sin_express


def test_f040_r25_no_mira_el_reloj() -> None:
    assert "datetime" not in vars(backlog) and "time" not in vars(backlog)
    assert "date" not in vars(backlog)
