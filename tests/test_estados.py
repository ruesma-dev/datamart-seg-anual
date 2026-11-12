# tests/test_estados.py
"""F-042: los estados del flujo, los campos de fecha y la feature activa.

`harness/estados.py` es la fuente única de los estados (R1). Los tests
trabajan con `features` sintéticos: este fichero viaja a cada proyecto
instalado y no puede depender de lo que haya en su `features.json`.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

from harness import estados

RAIZ = Path(__file__).resolve().parent.parent


def _f(fid: str, estado: str, **extra: object) -> dict:
    ficha = {"id": fid, "title": f"T {fid}", "status": estado, "sdd": False}
    ficha.update(extra)
    return ficha


# --- R1: una sola declaración de los estados --------------------------------


def test_f042_r1_ocho_estados_en_orden_de_flujo():
    assert estados.ESTADOS == (
        "pending", "todo", "spec_ready", "in_progress", "in_review",
        "human_review", "done", "blocked",
    )


def test_f042_r1_todo_no_es_activo():
    """`todo` = comprometida: se pueden comprometer varias a la vez (D9)."""
    assert "todo" not in estados.ACTIVOS
    assert "todo" not in estados.QUIEN_LA_TIENE


def test_f042_r1_activos_y_quien_la_tiene():
    assert estados.ACTIVOS == frozenset({"in_progress", "in_review", "human_review"})
    assert estados.QUIEN_LA_TIENE == {
        "in_progress": "implementer",
        "in_review": "reviewer",
        "human_review": "humano",
    }
    assert set(estados.QUIEN_LA_TIENE) == estados.ACTIVOS
    assert estados.CAMPOS_FECHA == ("fecha_cierre", "spec_aprobada", "ok_humano")


# --- R8 / R9: campos de fecha ------------------------------------------------


@pytest.mark.parametrize("campo", ["fecha_cierre", "spec_aprobada", "ok_humano"])
def test_f042_r8_fecha_valida_y_ausente(campo):
    assert estados.fecha(_f("F-001", "done", **{campo: "2026-10-28"}), campo) == (
        datetime.date(2026, 10, 28)
    )
    assert estados.fecha(_f("F-001", "done"), campo) is None
    assert estados.fecha(_f("F-001", "done", **{campo: None}), campo) is None


@pytest.mark.parametrize("campo", ["fecha_cierre", "spec_aprobada", "ok_humano"])
@pytest.mark.parametrize(
    "valor",
    ["2026-9-27", "27/09/2026", "2026-02-30", "2026-13-01", "20260927",
     "2026-W39-6", " 2026-09-27", "2026-09-27T10:00", 20260927, "", True,
     "２０２６-０９-２７"],
)
def test_f042_r9_fecha_mal_formada_nombra_feature_y_campo(campo, valor):
    with pytest.raises(ValueError) as exc:
        estados.fecha(_f("F-077", "done", **{campo: valor}), campo)
    assert "F-077" in str(exc.value)
    assert campo in str(exc.value)
    assert "AAAA-MM-DD" in str(exc.value)


def test_f042_r9_feature_sin_id_no_rompe_el_mensaje():
    with pytest.raises(ValueError, match=r"^\?: ok_humano"):
        estados.fecha({"ok_humano": "ayer"}, "ok_humano")


# --- feature_activa ----------------------------------------------------------


@pytest.mark.parametrize("estado", ["in_progress", "in_review", "human_review"])
def test_f042_feature_activa_reconoce_los_tres_activos(estado):
    features = [_f("F-001", "done"), _f("F-002", "pending"), _f("F-003", estado)]
    assert estados.feature_activa(features)["id"] == "F-003"


def test_f042_feature_activa_none_sin_activos_y_primera_por_orden():
    inactivas = [_f(f"F-{i:03d}", e) for i, e in enumerate(
        ("pending", "todo", "spec_ready", "done", "blocked", "otro"))]
    assert estados.feature_activa(inactivas) is None
    assert estados.feature_activa([]) is None
    dos = [_f("F-009", "human_review"), _f("F-001", "in_progress")]
    assert estados.feature_activa(dos)["id"] == "F-009"


# --- R7, R10–R12: avisos de la feature de la rama ----------------------------

RAMA = "feature/F-050-algo"


def test_f042_r10_feature_de_la_rama_done_sin_ok_humano_avisa():
    features = [_f("F-050", "done", branch=RAMA, fecha_cierre="2026-10-28")]
    lineas = estados.avisos(features, RAMA)
    assert len(lineas) == 1
    assert "F-050" in lineas[0] and "ok_humano" in lineas[0]


def test_f042_r10_con_ok_humano_no_avisa():
    features = [_f("F-050", "done", branch=RAMA, ok_humano="2026-10-28")]
    assert estados.avisos(features, RAMA) == []


@pytest.mark.parametrize("vacio", [None, ""])
def test_f042_r10_ok_humano_vacio_cuenta_como_ausente(vacio):
    features = [_f("F-050", "done", branch=RAMA, ok_humano=vacio)]
    assert len(estados.avisos(features, RAMA)) == 1


@pytest.mark.parametrize("estado", ["in_progress", "in_review", "human_review", "done"])
def test_f042_r11_sdd_activa_o_done_sin_spec_aprobada_avisa(estado):
    features = [_f("F-050", estado, branch=RAMA, sdd=True, ok_humano="2026-10-28")]
    lineas = estados.avisos(features, RAMA)
    assert len(lineas) == 1
    assert "F-050" in lineas[0] and "spec_aprobada" in lineas[0]
    assert estado in lineas[0]


@pytest.mark.parametrize("estado", ["pending", "todo", "spec_ready", "blocked"])
def test_f042_r11_sin_spec_aprobada_no_avisa_antes_de_implementar(estado):
    features = [_f("F-050", estado, branch=RAMA, sdd=True)]
    assert estados.avisos(features, RAMA) == []


def test_f042_r11_sdd_false_o_con_spec_aprobada_no_avisa():
    sin_sdd = [_f("F-050", "in_review", branch=RAMA, sdd=False)]
    assert estados.avisos(sin_sdd, RAMA) == []
    con_fecha = [_f("F-050", "in_review", branch=RAMA, sdd=True,
                    spec_aprobada="2026-10-01")]
    assert estados.avisos(con_fecha, RAMA) == []
    sdd_no_bool = [_f("F-050", "in_review", branch=RAMA, sdd="sí")]
    assert estados.avisos(sdd_no_bool, RAMA) == []


def test_f042_r10_r11_los_dos_avisos_a_la_vez():
    features = [_f("F-050", "done", branch=RAMA, sdd=True)]
    lineas = estados.avisos(features, RAMA)
    assert len(lineas) == 2
    assert "ok_humano" in lineas[0] and "spec_aprobada" in lineas[1]


def test_f042_r12_treinta_done_viejas_sin_ok_humano_no_avisan():
    viejas = [_f(f"F-{i:03d}", "done", branch=f"feature/F-{i:03d}-x", sdd=True)
              for i in range(1, 31)]
    actual = _f("F-050", "in_progress", branch=RAMA, sdd=True,
                spec_aprobada="2026-10-20")
    assert estados.avisos(viejas + [actual], RAMA) == []
    # Sin feature de la rama ni activa, tampoco.
    assert estados.avisos(viejas, "dev") == []


def test_f042_r7_done_sin_pasar_por_human_review_no_es_error():
    """Solo se ve el estado actual: no hay historial que validar."""
    features = [_f("F-050", "done", branch=RAMA, ok_humano="2026-10-28",
                   spec_aprobada="2026-10-01", sdd=True)]
    assert estados.avisos(features, RAMA) == []
    assert estados.feature_activa(features) is None


def test_f042_r7_spec_ready_sin_pasar_por_todo_no_es_error():
    """Una `spec_ready` de antes de la enmienda nunca estuvo en `todo`."""
    features = [_f("F-050", "spec_ready", branch=RAMA, sdd=True),
                _f("F-051", "pending")]
    assert "spec_ready" in estados.ESTADOS
    assert estados.avisos(features, RAMA) == []
    assert estados.feature_activa(features) is None


# --- CLI ---------------------------------------------------------------------


def _fichero(tmp_path: Path, features: list[dict]) -> str:
    ruta = tmp_path / "features.json"
    ruta.write_text(json.dumps({"features": features}), encoding="utf-8")
    return str(ruta)


def test_f042_r10_cli_imprime_un_aviso_por_linea_y_sale_con_0(tmp_path, capsys):
    ruta = _fichero(tmp_path, [_f("F-050", "done", branch=RAMA, sdd=True)])
    assert estados.main(["--avisos", "--rama", RAMA, "--features", ruta]) == 0
    salida = capsys.readouterr().out.splitlines()
    assert len(salida) == 2 and all("F-050" in li for li in salida)


def test_f042_cli_sin_avisos_no_imprime_nada(tmp_path, capsys):
    ruta = _fichero(tmp_path, [_f("F-050", "pending", branch=RAMA)])
    assert estados.main(["--avisos", "--rama", RAMA, "--features", ruta]) == 0
    assert capsys.readouterr().out == ""


def test_f042_cli_features_roto_avisa_y_sale_con_0(tmp_path, capsys):
    ruta = tmp_path / "features.json"
    ruta.write_text("{roto", encoding="utf-8")
    assert estados.main(["--avisos", "--rama", RAMA, "--features", str(ruta)]) == 0
    assert "no se pueden calcular" in capsys.readouterr().out


def test_f042_cli_sin_features_no_avisa(tmp_path, capsys):
    ruta = str(tmp_path / "no_existe.json")
    assert estados.main(["--avisos", "--rama", RAMA, "--features", ruta]) == 0
    assert capsys.readouterr().out == ""


def test_f042_cli_sin_accion_sale_con_2(capsys):
    assert estados.main([]) == 2
    assert "usage" in capsys.readouterr().err


def test_f042_cli_sin_rama_la_lee_de_git(tmp_path, capsys, monkeypatch):
    from harness import alcance

    pedidos: list[list[str]] = []

    def _git(args, raiz="."):
        pedidos.append(args)
        return RAMA + "\n"

    monkeypatch.setattr(alcance, "ejecutar_git", _git)
    features = [_f("F-001", "in_progress"), _f("F-050", "done", branch=RAMA)]
    ruta = _fichero(tmp_path, features)
    assert estados.main(["--avisos", "--features", ruta]) == 0
    assert pedidos == [["branch", "--show-current"]]
    salida = capsys.readouterr().out
    assert "F-050" in salida and "F-001" not in salida


# --- R14 / R15: las puertas encuentran la feature activa ---------------------


@pytest.mark.parametrize("estado", ["in_review", "human_review"])
def test_f042_r14_feature_de_rama_sin_rama_coincidente_da_la_activa(estado):
    from harness.rigor import feature_de_rama

    features = [_f("F-001", "done", branch="feature/F-001-x"),
                _f("F-050", estado, branch=RAMA)]
    assert feature_de_rama("dev", features)["id"] == "F-050"
    assert feature_de_rama("", features)["id"] == "F-050"
    # La rama declarada sigue mandando sobre la activa.
    assert feature_de_rama("feature/F-001-x", features)["id"] == "F-001"


def test_f042_r14_sin_activa_ni_rama_no_hay_feature():
    from harness.rigor import feature_de_rama

    assert feature_de_rama("dev", [_f("F-001", "done"), _f("F-002", "pending")]) is None


def test_f042_r14_una_todo_sin_rama_coincidente_no_es_la_feature_de_la_rama():
    from harness.rigor import feature_de_rama

    features = [_f("F-001", "done"), _f("F-002", "todo", branch="feature/F-002-x"),
                _f("F-003", "todo")]
    assert feature_de_rama("dev", features) is None
    assert estados.avisos(features, "dev") == []
    # Con una activa detrás, la activa gana aunque las `todo` vayan antes.
    features.append(_f("F-004", "in_progress", branch="feature/F-004-x"))
    assert feature_de_rama("dev", features)["id"] == "F-004"
    # Y si la rama la declara una `todo`, es esa (manda la rama, R14).
    assert feature_de_rama("feature/F-002-x", features)["id"] == "F-002"


def test_f042_r14_avisos_sin_rama_coincidente_mira_la_activa():
    features = [_f("F-001", "done"), _f("F-050", "in_review", sdd=True)]
    lineas = estados.avisos(features, "dev")
    assert len(lineas) == 1 and "F-050" in lineas[0]


@pytest.mark.parametrize("estado", ["in_progress", "in_review", "human_review"])
def test_f042_r15_rutas_sensibles_encuentra_la_feature_activa(tmp_path, estado):
    from harness.rutas_sensibles import _feature_en_curso

    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "features.json").write_text(json.dumps({"features": [
        _f("F-001", "done", branch="feature/F-001-x"),
        _f("F-050", estado, branch=RAMA),
    ]}), encoding="utf-8")
    assert _feature_en_curso(tmp_path) == ("F-050", RAMA)


def test_f042_r15_rutas_sensibles_sin_activa_devuelve_vacio(tmp_path):
    from harness.rutas_sensibles import _feature_en_curso

    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "features.json").write_text(json.dumps({"features": [
        _f("F-001", "done", branch="feature/F-001-x"),
        _f("F-002", "spec_ready", branch="feature/F-002-x"),
    ]}), encoding="utf-8")
    assert _feature_en_curso(tmp_path) == ("", "")
    (tmp_path / "harness" / "features.json").write_text(json.dumps({"features": [
        _f("F-050", "human_review"),
    ]}), encoding="utf-8")
    assert _feature_en_curso(tmp_path) == ("F-050", "")


# --- R31: CLAUDE.md y CHECKPOINTS.md con «máximo una activa» -----------------


def _plano(ruta: str) -> str:
    return " ".join((RAIZ / ruta).read_text(encoding="utf-8").split())


_ORDEN = ("`blocked` > `human_review` > `in_review` > `in_progress` > "
          "`spec_ready` > `todo`")
_PENDING = "`pending` no se arranca sin el compromiso del humano"

# Los dos documentos son `adaptado` (CONSERVAR por defecto al actualizar): si
# el proyecto conserva su bloque viejo, el rojo dice qué aceptar del diff,
# igual que `_INSTRUCCION` de R6 con harness/init.sh.
_INSTRUCCION_R31 = (
    "{doc} no tiene {que} de F-042: al actualizar el arnés, acepta ese bloque "
    "del diff de {doc} ({donde})"
)


def _r31(doc: str, que: str, donde: str) -> str:
    return _INSTRUCCION_R31.format(doc=doc, que=que, donde=donde)


def test_f042_r31_claude_md_da_el_orden_de_prioridad_y_maximo_una_activa():
    texto = _plano("CLAUDE.md")
    orden = _r31("CLAUDE.md", "el orden de prioridad", "paso 3 del protocolo")
    activa = _r31("CLAUDE.md", "el «máximo una feature activa»",
                  "paso 3 del protocolo")
    assert _ORDEN in texto, orden
    assert "> `pending`" not in texto, orden
    assert _PENDING in texto, orden
    assert ("Máximo UNA feature activa (`in_progress`, `in_review` o "
            "`human_review`) a la vez") in texto, activa
    assert "Máximo UNA feature `in_progress`" not in texto, activa


def test_f042_r31_checkpoints_c2_cuenta_las_tres_activas_y_el_orden():
    texto = _plano("CHECKPOINTS.md")
    orden = _r31("CHECKPOINTS.md", "el orden de prioridad", "C2")
    activa = _r31("CHECKPOINTS.md", "el «como mucho UNA feature activa»", "C2")
    assert ("Como mucho UNA feature activa (`in_progress`, `in_review` o "
            "`human_review`)") in texto, activa
    assert "Como mucho UNA feature en `in_progress`" not in texto, activa
    assert _ORDEN in texto, orden
    assert _PENDING in texto, orden


# Un CLAUDE.md / CHECKPOINTS.md de la 1.7.x conservado al actualizar: el rojo
# tiene que decir qué aceptar del diff (los dos son `adaptado`).
_CLAUDE_VIEJO = (
    "3. Lee `harness/features.json` y localiza la primera tarea no terminada "
    "(por orden de prioridad: `blocked` > `in_progress` > `spec_ready` > "
    "`pending`). Máximo UNA feature `in_progress` a la vez (init.sh lo valida)."
)
_CHECKPOINTS_VIEJO = (
    "## C2 — El estado es coherente - [ ] Como mucho UNA feature en "
    "`in_progress` en `harness/features.json`."
)


def test_f042_r31_claude_md_viejo_da_el_rojo_con_instrucciones(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "_plano", lambda _r: _CLAUDE_VIEJO)
    with pytest.raises(AssertionError) as exc:
        test_f042_r31_claude_md_da_el_orden_de_prioridad_y_maximo_una_activa()
    mensaje = str(exc.value)
    assert "CLAUDE.md no tiene" in mensaje and "de F-042" in mensaje
    assert "acepta ese bloque del diff de CLAUDE.md" in mensaje
    assert "paso 3 del protocolo" in mensaje


def test_f042_r31_checkpoints_viejo_da_el_rojo_con_instrucciones(monkeypatch):
    monkeypatch.setattr(
        sys.modules[__name__], "_plano", lambda _r: _CHECKPOINTS_VIEJO)
    with pytest.raises(AssertionError) as exc:
        test_f042_r31_checkpoints_c2_cuenta_las_tres_activas_y_el_orden()
    mensaje = str(exc.value)
    assert "CHECKPOINTS.md no tiene" in mensaje and "de F-042" in mensaje
    assert "acepta ese bloque del diff de CHECKPOINTS.md" in mensaje
    assert "C2" in mensaje
