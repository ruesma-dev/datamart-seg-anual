# tests/test_init_sh_estados.py
"""F-042: la sección 3 de `harness/init.sh` con los ocho estados.

La sección se extrae del propio `init.sh` y se ejecuta DE VERDAD con bash,
forzando cada validador (python, node, jq y el degradado por texto) contra un
`features.json` sintético. Los casos de node y jq se saltan con su motivo si
la máquina no tiene ese intérprete: el de jq es la verificación MANUAL T13.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness import estados
from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
INIT_SH = RAIZ / "harness" / "init.sh"


def _texto() -> str:
    return INIT_SH.read_text(encoding="utf-8")


def _bash() -> str | None:
    ruta = shutil.which("bash")
    if ruta is None:
        return None
    if os.name == "nt" and "system32" in ruta.lower():
        return None  # el bash de WSL no ve las rutas de Windows igual
    return ruta


BASH = _bash()
necesita_bash = pytest.mark.skipif(BASH is None, reason="sin bash utilizable")


_INSTRUCCION = (
    "la sección 3 de harness/init.sh ({validador}) no acepta `{estado}`: al "
    "actualizar el arnés, acepta ese bloque del diff de harness/init.sh"
)

_INSTRUCCION_3_TER = (
    "harness/init.sh no tiene la sección 3 ter (avisos de estado): al "
    "actualizar el arnés, acepta ese bloque del diff de harness/init.sh"
)


def _listas_de_init_sh(texto: str | None = None) -> dict[str, list[str]]:
    """Las listas de estados de los tres validadores, localizadas por su forma."""
    texto = _texto() if texto is None else texto
    tercera = texto[texto.index("# --- 3. features.json"):texto.index("# --- 3 bis.")]
    listas: dict[str, list[str]] = {}
    formas = {
        "python": r"estados = \{([^}]*)\}",
        "node": r"const estados = \[([^\]]*)\]",
        "jq": r'\[("pending"[^\]]*)\] \| index\(\$s\)',
    }
    for validador, forma in formas.items():
        rama = tercera
        if validador == "jq":
            rama = tercera[tercera.index("\njq)"):tercera.index("\n*)")]
        encontradas = re.findall(forma, rama)
        listas[validador] = [
            sorted(re.findall(r'"([^"]+)"', cuerpo)) for cuerpo in encontradas
        ]
    return listas


def _motivo_init_sh_viejo(texto: str) -> str | None:
    """Por qué este init.sh es de antes de F-042, con el mensaje de R6; o None.

    Recorre las listas en el mismo orden que R6, así que el motivo es el
    mensaje del rojo de R6. Un init.sh irreconocible (sin las marcas de la
    sección 3) también es viejo: nunca rompe la recogida de la suite.
    """
    try:
        listas = _listas_de_init_sh(texto)
    except ValueError:
        return _INSTRUCCION.format(validador="python", estado="in_review")
    for validador, encontradas in listas.items():
        if not encontradas:
            return _INSTRUCCION.format(validador=validador, estado="in_review")
        for lista in encontradas:
            for estado in sorted(estados.ESTADOS):
                if estado not in lista:
                    return _INSTRUCCION.format(validador=validador, estado=estado)
    if "# --- 3 ter." not in texto or "# --- 3b." not in texto:
        return _INSTRUCCION_3_TER
    return None


#: F-055. Con el init.sh viejo de un proyecto instalado, los tests de
#: comportamiento de §3 y §3 ter fallarían sin explicar nada: se saltan con la
#: instrucción de R6, y R6 de las listas queda como el único rojo.
_MOTIVO_INIT_SH_VIEJO = _motivo_init_sh_viejo(_texto())
init_sh_de_f042 = pytest.mark.skipif(
    _MOTIVO_INIT_SH_VIEJO is not None, reason=_MOTIVO_INIT_SH_VIEJO or "")

_PRELUDIO = (
    "set -u\nFALLOS=0\n"
    'ok()   { printf "[OK] %s\\n" "$1"; }\n'
    'warn() { printf "[AVISO] %s\\n" "$1"; }\n'
    'ko()   { printf "[KO] %s\\n" "$1"; FALLOS=$((FALLOS + 1)); }\n'
)


def _seccion_3_validadores() -> str:
    """Del `case "$VALIDADOR"` al veredicto de la sección 3, ambos incluidos."""
    texto = _texto()
    inicio = texto.index('case "$VALIDADOR" in')
    fin = texto.index('if [ "$RES" -eq 0 ]; then ok "features.json válido"', inicio)
    return texto[inicio:texto.index("\n", fin) + 1]


def _ejecutar(tmp_path: Path, guion: str, features: dict | None,
              entorno: dict | None = None) -> str:
    (tmp_path / "harness").mkdir(exist_ok=True)
    if features is not None:
        (tmp_path / "harness" / "features.json").write_text(
            json.dumps(features), encoding="utf-8")
    fichero = tmp_path / "seccion.sh"
    fichero.write_text(_PRELUDIO + guion + 'echo "FALLOS=$FALLOS"\n',
                       encoding="utf-8", newline="\n")
    proceso = subprocess.run(
        [BASH, fichero.name], cwd=tmp_path, capture_output=True, text=True,
        encoding="utf-8", env={**os.environ, **(entorno or {})}, timeout=escalar_timeout(60),
        check=False,
    )
    return proceso.stdout + proceso.stderr


def _validar(tmp_path: Path, validador: str, features: dict) -> str:
    py = Path(sys.executable).as_posix()
    guion = f'PY="{py}"\nVALIDADOR={validador}\n' + _seccion_3_validadores()
    return _ejecutar(tmp_path, guion, features)


def _f(fid: str, estado: str, **extra: object) -> dict:
    ficha = {"id": fid, "title": f"T {fid}", "status": estado, "sdd": False}
    ficha.update(extra)
    return ficha


VALIDADORES = [
    "python",
    pytest.param("node", marks=pytest.mark.skipif(
        shutil.which("node") is None, reason="sin node en esta máquina")),
    pytest.param("jq", marks=pytest.mark.skipif(
        shutil.which("jq") is None,
        reason="sin jq en esta máquina: verificación MANUAL T13")),
]

#: Los validadores completos más el degradado por texto (solo cuenta activos).
CON_DEGRADADO = VALIDADORES + ["degradado"]


def _nombre(validador: str) -> str:
    return "" if validador == "degradado" else validador


# --- R2: los ocho estados valen ----------------------------------------------


@necesita_bash
@pytest.mark.parametrize("validador", VALIDADORES)
@init_sh_de_f042
def test_f042_r2_acepta_los_ocho_estados(tmp_path, validador):
    features = {"features": [
        _f("F-001", "pending"), _f("F-002", "spec_ready"),
        _f("F-003", "in_review"), _f("F-004", "done", ok_humano="2026-10-28"),
        _f("F-005", "blocked"), _f("F-006", "todo"),
    ]}
    for activo in sorted(estados.ACTIVOS):
        features["features"][2]["status"] = activo
        salida = _validar(tmp_path, validador, features)
        assert "[OK] features.json válido" in salida, (activo, salida)
        assert "FALLOS=0" in salida, salida
        assert "F-003" in salida, "la línea de resumen nombra la activa"


# --- R3: un estado fuera de los ocho es rojo nombrando feature y estado ------


@necesita_bash
@pytest.mark.parametrize("validador", VALIDADORES)
@pytest.mark.parametrize("raro", ["en_pausa", "revision", "IN_REVIEW", "TODO", "to_do"])
@init_sh_de_f042
def test_f042_r3_estado_desconocido_es_rojo_y_se_nombra(tmp_path, validador, raro):
    features = {"features": [_f("F-001", "pending"), _f("F-077", raro)]}
    salida = _validar(tmp_path, validador, features)
    assert "[KO] features.json inválido" in salida, salida
    assert "F-077" in salida and raro in salida, salida


# --- R4: como mucho una activa, contando los tres estados --------------------


@necesita_bash
@pytest.mark.parametrize("validador", CON_DEGRADADO)
@pytest.mark.parametrize("pareja", [
    ("in_progress", "in_review"),
    ("in_review", "human_review"),
    ("human_review", "in_progress"),
    ("in_progress", "in_progress"),
])
@init_sh_de_f042
def test_f042_r4_dos_activas_es_rojo_y_las_lista(tmp_path, validador, pareja):
    features = {"features": [
        _f("F-010", "done"), _f("F-011", pareja[0]), _f("F-012", "pending"),
        _f("F-013", pareja[1]),
    ]}
    salida = _validar(tmp_path, _nombre(validador), features)
    assert "[KO] features.json inválido (o más de una feature activa)" in salida, salida
    assert "Hay 2 features activas" in salida, salida
    assert "F-011, F-013" in salida, salida


@necesita_bash
@pytest.mark.parametrize("validador", CON_DEGRADADO)
@init_sh_de_f042
def test_f042_r4_una_activa_y_el_resto_no_activas_es_verde(tmp_path, validador):
    features = {"features": [
        _f("F-010", "done"), _f("F-011", "human_review"), _f("F-012", "spec_ready"),
        _f("F-013", "blocked"), _f("F-014", "pending"),
    ]}
    salida = _validar(tmp_path, _nombre(validador), features)
    assert "[OK] features.json válido" in salida, salida
    assert "FALLOS=0" in salida, salida


@necesita_bash
@pytest.mark.parametrize("validador", CON_DEGRADADO)
@pytest.mark.parametrize("con_activa", [True, False])
@init_sh_de_f042
def test_f042_r4_varias_todo_con_una_activa_o_ninguna_es_verde(
        tmp_path, validador, con_activa):
    """`todo` no es activa: se compromete una fase entera sin chocar con R4."""
    features = {"features": [
        _f("F-010", "todo"), _f("F-011", "todo"), _f("F-012", "todo"),
        _f("F-013", "in_review" if con_activa else "pending"),
    ]}
    salida = _validar(tmp_path, _nombre(validador), features)
    assert "[OK] features.json válido" in salida, salida
    assert "FALLOS=0" in salida, salida
    assert "activas" not in salida, salida


@necesita_bash
@init_sh_de_f042
def test_f042_r4_el_degradado_lo_avisa(tmp_path):
    salida = _validar(tmp_path, "", {"features": [_f("F-001", "pending")]})
    assert "[AVISO] Sin python, node ni jq" in salida, salida


# --- R5: un features.json de la 1.7.x sigue valiendo --------------------------


def _features_17x() -> dict:
    """Cinco estados, `rules.valid_status` viejo y sin los campos nuevos."""
    return {
        "$schema_doc": "Estados: pending -> spec_ready -> in_progress -> done.",
        "rules": {
            "one_feature_at_a_time": True,
            "require_init_green_to_close": True,
            "valid_status": ["pending", "spec_ready", "in_progress", "done", "blocked"],
        },
        "features": [
            _f("F-001", "done", sdd=True, fecha_cierre="2026-08-01",
               branch="feature/F-001-a"),
            _f("F-002", "done", branch="feature/F-002-b"),
            _f("F-003", "in_progress", sdd=True, branch="feature/F-003-c"),
            _f("F-004", "spec_ready", sdd=True),
            _f("F-005", "blocked"),
            _f("F-006", "pending"),
        ],
    }


@necesita_bash
@pytest.mark.parametrize("validador", CON_DEGRADADO)
@init_sh_de_f042
def test_f042_r5_features_json_viejo_es_valido_sin_avisos_nuevos(tmp_path, validador):
    salida = _validar(tmp_path, _nombre(validador), _features_17x())
    assert "[OK] features.json válido" in salida, salida
    assert "FALLOS=0" in salida, salida
    if validador != "degradado":
        assert "[AVISO]" not in salida, salida


# --- R13 (y R10–R11 en el portero): sección 3 ter -----------------------------


def _seccion_3_ter() -> str:
    texto = _texto()
    inicio = texto.index("# --- 3 ter.")
    return texto[inicio:texto.index("# --- 3b.", inicio)]


@init_sh_de_f042
def test_f042_r13_la_3_ter_va_tras_3_bis_y_antes_de_los_niveles():
    texto = _texto()
    assert texto.index("# --- 3 bis.") < texto.index("# --- 3 ter.") < texto.index("# --- 3b.")
    seccion = _seccion_3_ter()
    assert "-m harness.estados --avisos" in seccion
    assert "ko " not in seccion and "ko(" not in seccion, "son avisos, nunca rojo"


@necesita_bash
@init_sh_de_f042
def test_f042_r13_sin_python_avisa_na_con_motivo(tmp_path):
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "estados.py").write_text("", encoding="utf-8")
    salida = _ejecutar(tmp_path, 'PY=""\n' + _seccion_3_ter(), None)
    assert "[AVISO] AVISOS DE ESTADO: N/A (no hay intérprete de Python" in salida, salida
    assert "FALLOS=0" in salida


@necesita_bash
@init_sh_de_f042
def test_f042_r13_sin_estados_py_avisa_na_con_motivo(tmp_path):
    py = Path(sys.executable).as_posix()
    salida = _ejecutar(tmp_path, f'PY="{py}"\n' + _seccion_3_ter(), {"features": []})
    assert "[AVISO] AVISOS DE ESTADO: N/A (no existe harness/estados.py" in salida, salida
    assert "FALLOS=0" in salida


def _con_harness(tmp_path: Path) -> None:
    shutil.copytree(RAIZ / "harness", tmp_path / "harness",
                    ignore=shutil.ignore_patterns("__pycache__", "features.json"))


@necesita_bash
@init_sh_de_f042
def test_f042_r13_con_python_y_modulo_imprime_un_aviso_por_linea(tmp_path):
    _con_harness(tmp_path)
    py = Path(sys.executable).as_posix()
    features = {"features": [
        _f("F-001", "done"),
        _f("F-050", "human_review", sdd=True, branch="feature/F-050-ninguna"),
    ]}
    salida = _ejecutar(tmp_path, f'PY="{py}"\n' + _seccion_3_ter(), features)
    avisos = [li for li in salida.splitlines() if li.startswith("[AVISO]")]
    assert len(avisos) == 1, salida
    assert "F-050" in avisos[0] and "spec_aprobada" in avisos[0]
    assert "F-001" not in salida
    assert "FALLOS=0" in salida


@necesita_bash
@init_sh_de_f042
def test_f042_r13_sin_nada_que_avisar_no_imprime_nada(tmp_path):
    _con_harness(tmp_path)
    py = Path(sys.executable).as_posix()
    features = {"features": [_f("F-001", "done"), _f("F-002", "pending")]}
    salida = _ejecutar(tmp_path, f'PY="{py}"\n' + _seccion_3_ter(), features)
    assert salida.strip() == "FALLOS=0", salida


@necesita_bash
@init_sh_de_f042
def test_f042_r13_si_el_modulo_revienta_lo_dice_sin_rojo(tmp_path):
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "harness" / "estados.py").write_text(
        "raise SystemExit('roto a proposito')\n", encoding="utf-8")
    py = Path(sys.executable).as_posix()
    salida = _ejecutar(tmp_path, f'PY="{py}"\n' + _seccion_3_ter(), {"features": []})
    assert "[AVISO] AVISOS DE ESTADO: no se pudieron calcular" in salida, salida
    assert "roto a proposito" in salida
    assert "FALLOS=0" in salida


# --- R6: las listas de estados no divergen de harness/estados.py -------------


def test_f042_r6_los_tres_validadores_aceptan_los_ocho_estados():
    esperados = sorted(estados.ESTADOS)
    for validador, listas in _listas_de_init_sh().items():
        # Sin la lista no hay validador que vigilar: mismo mensaje que si falta
        # un estado (el init.sh es de antes de F-042 o se reescribió).
        assert listas, _INSTRUCCION.format(validador=validador, estado="in_review")
        for lista in listas:
            for estado in esperados:
                assert estado in lista, _INSTRUCCION.format(
                    validador=validador, estado=estado)
            sobran = sorted(set(lista) - set(esperados))
            assert not sobran, (
                f"la sección 3 de harness/init.sh ({validador}) acepta {sobran}, "
                "que no están en harness/estados.py"
            )


@init_sh_de_f042
def test_f042_r6_el_mensaje_dice_que_aceptar_si_falta_un_estado(monkeypatch):
    """Un init.sh de la 1.7.x (cinco estados) da el rojo con instrucciones."""
    viejo = _texto().replace('"in_review", "human_review", ', "")
    monkeypatch.setattr(sys.modules[__name__], "_texto", lambda: viejo)
    with pytest.raises(AssertionError) as exc:
        test_f042_r6_los_tres_validadores_aceptan_los_ocho_estados()
    assert "acepta ese bloque del diff" in str(exc.value)
    assert "(python)" in str(exc.value) and "`human_review`" in str(exc.value)


@init_sh_de_f042
def test_f042_r6_un_init_sh_sin_todo_da_el_rojo_con_instrucciones(monkeypatch):
    """El init.sh de la primera pasada de F-042 (siete estados) tampoco vale."""
    sin_todo = (_texto().replace('"todo", ', "").replace('"todo",', ""))
    monkeypatch.setattr(sys.modules[__name__], "_texto", lambda: sin_todo)
    with pytest.raises(AssertionError) as exc:
        test_f042_r6_los_tres_validadores_aceptan_los_ocho_estados()
    assert "acepta ese bloque del diff" in str(exc.value)
    assert "`todo`" in str(exc.value)


def _plantilla() -> dict:
    with open(RAIZ / "harness" / "features.json", encoding="utf-8") as fh:
        return json.load(fh)


#: En el taller, `harness/features.json` del payload es la PLANTILLA. En un
#: proyecto instalado es su backlog, que el instalador nunca toca: su
#: `valid_status` viejo es documental y sigue valiendo (R5).
es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="harness/features.json es el backlog del proyecto, no la plantilla",
)


@es_el_taller
def test_f042_r6_r30_la_plantilla_declara_los_ocho_estados():
    assert _plantilla()["rules"]["valid_status"] == list(estados.ESTADOS)


@es_el_taller
def test_f042_r30_el_schema_doc_explica_estados_activos_y_campos():
    doc = _plantilla()["$schema_doc"]
    for termino in estados.ESTADOS + ("spec_aprobada", "ok_humano", "fecha_cierre",
                                      "Activos", "UNA feature activa",
                                      "comprometida"):
        assert termino in doc, termino
    assert "todo no es activa" in doc


# --- F-055: un init.sh viejo da UN rojo (R6) y el resto se salta --------------


def _init_sh_viejo() -> str:
    """El init.sh del payload devuelto a la 1.7.x: cinco estados y sin 3 ter."""
    texto = _texto().replace('"in_review", "human_review", ', "")
    texto = texto.replace('"todo", ', "").replace('"todo",', "")
    inicio = texto.index("# --- 3 ter.")
    return texto[:inicio] + texto[texto.index("# --- 3b.", inicio):]


def _mensaje_de_r6(monkeypatch, texto: str) -> str:
    monkeypatch.setattr(sys.modules[__name__], "_texto", lambda: texto)
    with pytest.raises(AssertionError) as exc:
        test_f042_r6_los_tres_validadores_aceptan_los_ocho_estados()
    return str(exc.value).splitlines()[0]


@init_sh_de_f042
def test_f055_r2_un_init_sh_viejo_da_como_motivo_el_mensaje_de_r6(monkeypatch):
    viejo = _init_sh_viejo()
    motivo = _motivo_init_sh_viejo(viejo)
    assert motivo is not None
    assert motivo == _mensaje_de_r6(monkeypatch, viejo)
    assert "acepta ese bloque del diff" in motivo


@init_sh_de_f042
def test_f055_r2_sin_la_3_ter_tambien_se_salta_con_instrucciones():
    texto = _texto()
    inicio = texto.index("# --- 3 ter.")
    sin_3_ter = texto[:inicio] + texto[texto.index("# --- 3b.", inicio):]
    motivo = _motivo_init_sh_viejo(sin_3_ter)
    assert motivo is not None
    assert "3 ter" in motivo and "acepta ese bloque del diff" in motivo


@pytest.mark.parametrize("texto", ["", "#!/usr/bin/env bash\necho hola\n"])
def test_f055_r2_un_init_sh_irreconocible_no_rompe_la_coleccion(texto):
    motivo = _motivo_init_sh_viejo(texto)
    assert motivo is not None and "acepta ese bloque del diff" in motivo


#: Los tests que dan por hecho el init.sh de F-042: el comportamiento de §3 y
#: §3 ter, y los que fabrican un init.sh viejo a partir del nuevo (las
#: meta-pruebas de R6 y las de F-055). R6 de las listas no.
_CON_MARCA = ("test_f042_r2_", "test_f042_r3_", "test_f042_r4_", "test_f042_r5_",
              "test_f042_r13_", "test_f042_r6_el_mensaje_",
              "test_f042_r6_un_init_sh_sin_todo", "test_f055_r2_un_init_sh_viejo_",
              "test_f055_r2_sin_la_3_ter_")


def test_f055_r2_los_tests_que_dependen_del_init_sh_nuevo_llevan_la_marca():
    funciones = {nombre: f for nombre, f in globals().items()
                 if nombre.startswith(_CON_MARCA) and callable(f)}
    assert len(funciones) >= 15, sorted(funciones)
    for nombre, funcion in funciones.items():
        assert init_sh_de_f042.mark in getattr(funcion, "pytestmark", []), nombre
    r6 = test_f042_r6_los_tres_validadores_aceptan_los_ocho_estados
    assert init_sh_de_f042.mark not in getattr(r6, "pytestmark", []), (
        "R6 de las listas es el rojo que lleva la instrucción: no se salta"
    )


def _junit(ruta: Path) -> dict[str, tuple[str, str]]:
    """{test: (resultado, mensaje)} de un informe junit de pytest."""
    import xml.etree.ElementTree as ET

    casos: dict[str, tuple[str, str]] = {}
    for caso in ET.parse(ruta).iter("testcase"):
        resultado, mensaje = "passed", ""
        for hijo in caso:
            if hijo.tag in ("failure", "error", "skipped"):
                resultado, mensaje = hijo.tag, hijo.get("message", "")
        casos[caso.get("name", "")] = (resultado, mensaje)
    return casos


@es_el_taller
def test_f055_r2_la_suite_con_un_init_sh_viejo_da_un_unico_rojo(tmp_path):
    """La suite entera, en otro proceso, sobre una copia con el init.sh viejo."""
    proyecto = tmp_path / "proyecto"
    shutil.copytree(RAIZ / "harness", proyecto / "harness",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (proyecto / "tests").mkdir()
    shutil.copy2(Path(__file__), proyecto / "tests" / Path(__file__).name)
    (proyecto / "harness" / "init.sh").write_text(
        _init_sh_viejo(), encoding="utf-8", newline="\n")
    informe = tmp_path / "junit.xml"
    subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         f"--junitxml={informe}", "tests/" + Path(__file__).name],
        cwd=proyecto, capture_output=True, text=True, timeout=escalar_timeout(300), check=False,
    )
    casos = _junit(informe)
    rojos = {n: m for n, (r, m) in casos.items() if r in ("failure", "error")}
    assert list(rojos) == ["test_f042_r6_los_tres_validadores_aceptan_los_ocho_estados"], rojos
    assert "acepta ese bloque del diff" in next(iter(rojos.values()))
    dependientes = {n: v for n, v in casos.items() if n.startswith(_CON_MARCA)}
    assert len(dependientes) >= 30, sorted(casos)
    for nombre, (resultado, mensaje) in dependientes.items():
        assert resultado == "skipped", (nombre, resultado)
        assert "acepta ese bloque del diff" in mensaje, (nombre, mensaje)


@es_el_taller
def test_f055_r3_con_el_init_sh_del_payload_no_se_salta_nada_por_esa_causa():
    assert _motivo_init_sh_viejo(_texto()) is None
    assert _MOTIVO_INIT_SH_VIEJO is None
    assert init_sh_de_f042.mark.args == (False,)
