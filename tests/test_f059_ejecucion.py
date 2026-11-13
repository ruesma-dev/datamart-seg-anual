# tests/test_f059_ejecucion.py
"""F-059 · R5–R14: `python -m harness.e2e` con un servicio de juguete.

Sin red, sin navegador y sin abrir puertos: el «comando» de la capa es un
script de Python que sale con el código pedido, duerme o escribe un junit
falso en `$ARNES_E2E_SALIDA`; la sonda de `url_base` se inyecta. Los procesos
sí son reales: es lo que hay que demostrar (árbol, timeout, parada).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness import e2e
from harness.servicios import BloqueE2E, Servicio

PY = Path(sys.executable).as_posix()

#: Script de juguete: `juguete.py CODIGO [DORMIR_S] [JUNIT]`. Anota su entorno.
JUGUETE = """\
import json, os, sys, time
from pathlib import Path
codigo = int(sys.argv[1])
Path("entorno.json").write_text(json.dumps({
    "cwd": os.getcwd(),
    **{k: v for k, v in os.environ.items() if k.startswith("ARNES_E2E")}}))
if len(sys.argv) > 3:
    salida = Path(os.environ["ARNES_E2E_SALIDA"])
    (salida / "junit.xml").write_text(Path(sys.argv[3]).read_text())
for numero in range(30):
    print(f"linea {numero}")
sys.stdout.flush()
if len(sys.argv) > 2:
    time.sleep(float(sys.argv[2]))
sys.exit(codigo)
"""

#: Lanza un nieto durmiente, anota su PID y duerme: para probar el árbol.
CON_NIETO = """\
import subprocess, sys, time
from pathlib import Path
nieto = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
Path("nieto.pid").write_text(str(nieto.pid))
time.sleep(60)
"""

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
<testcase classname="tests_e2e.test_a" name="test_f900_r4_alta_de_obra"/>
<testcase classname="tests_e2e.test_a" name="test_F900_R4_baja"><failure message="x"/></testcase>
<testcase classname="tests_e2e.test_a" name="test_f900_r40_otro"><skipped message="s"/></testcase>
<testcase classname="tests_e2e.test_a" name="test_f900_r9_listado"/>
</testsuite></testsuites>
"""


def _vivo(pid: int) -> bool:
    if os.name == "nt":
        salida = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                capture_output=True, text=True, check=False).stdout
        return str(pid) in salida
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _resultado(resultado: str) -> e2e.ResultadoServicio:
    return e2e.ResultadoServicio(
        servicio="s", runner="pytest-playwright", comando="c", url_base="http://x",
        resultado=resultado, pasados=None, fallados=None, omitidos=None,
        duracion_s=0.0, trazas="t", cola_salida=())


def _proyecto(tmp_path: Path, bloques: dict[str, dict | None], spec: str | None = None) -> Path:
    """Repositorio de juguete con un servicio por entrada de `bloques`."""
    entradas = []
    for nombre, bloque in bloques.items():
        (tmp_path / nombre).mkdir()
        (tmp_path / nombre / "juguete.py").write_text(JUGUETE, encoding="utf-8")
        (tmp_path / nombre / "con_nieto.py").write_text(CON_NIETO, encoding="utf-8")
        (tmp_path / nombre / "junit_falso.xml").write_text(JUNIT, encoding="utf-8")
        entrada = {"nombre": nombre, "ruta": nombre, "lenguaje": "python"}
        if bloque is not None:
            entrada["e2e"] = {"url_base": "http://localhost:8000", "rutas_ui": ["**"],
                              **bloque}
        entradas.append(entrada)
    (tmp_path / "harness").mkdir()
    if entradas:
        (tmp_path / "harness" / "servicios.json").write_text(
            json.dumps({"servicios": entradas}), encoding="utf-8")
    features = {"features": [{"id": "F-900", "title": "t", "status": "in_progress",
                              "sdd": True, "rigor": "estandar",
                              "branch": "feature/F-900-x"}]}
    (tmp_path / "harness" / "features.json").write_text(json.dumps(features), encoding="utf-8")
    if spec is not None:
        carpeta = tmp_path / "specs" / "F-900-juguete"
        carpeta.mkdir(parents=True)
        (carpeta / "requirements.md").write_text(spec, encoding="utf-8")
    return tmp_path


def _comando(*args: object) -> str:
    return f'"{PY}" juguete.py ' + " ".join(str(a) for a in args)


@pytest.fixture
def sin_procesos(monkeypatch):
    """Falla si alguien lanza un proceso por la vía por defecto."""
    def _prohibido(*args, **kwargs):
        raise AssertionError(f"no debía lanzarse ningún proceso: {args}")
    monkeypatch.setattr(subprocess, "Popen", _prohibido)


# --- R5: sin servicio con `e2e`, N/A y nada más ------------------------------


@pytest.mark.parametrize("bloques", [{}, {"svc": None}], ids=["sin servicios.json", "sin bloque"])
def test_f059_r5_sin_bloque_e2e_dice_na_y_sale_con_0(
    tmp_path: Path, capsys, sin_procesos, bloques
) -> None:
    raiz = _proyecto(tmp_path, bloques)

    codigo = e2e.main(["--feature", "F-900", "--raiz", str(raiz)])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert salida.startswith("CAPA E2E: N/A (") and salida.strip().endswith(")")
    assert not (raiz / "progress").exists()
    assert not (raiz / ".arnes_cache").exists()


# --- R9: clasificación y código global -------------------------------------


@pytest.mark.parametrize(("resultados", "codigo"), [
    ([], 0),
    (["VERDE", "VERDE"], 0),
    (["VERDE", "TIMEOUT"], 2),
    (["TIMEOUT", "NO ARRANCA"], 3),
    (["NO ARRANCA", "ROJO", "TIMEOUT"], 1),
    (["ROJO"], 1),
])
def test_f059_r9_codigo_global_por_prioridad(resultados, codigo) -> None:
    assert e2e.codigo_global([_resultado(r) for r in resultados]) == codigo


def _servicio(raiz: Path, **bloque: object) -> Servicio:
    return Servicio(nombre="svc", ruta="svc", lenguaje="python", e2e=BloqueE2E(
        url_base="http://localhost:8000", rutas_ui=("**",), **bloque))


@pytest.mark.parametrize(("args", "esperado"), [((0,), "VERDE"), ((1,), "ROJO")])
def test_f059_r9_verde_y_rojo_por_la_salida(tmp_path: Path, args, esperado) -> None:
    raiz = _proyecto(tmp_path, {"svc": {}})

    resultado = e2e.ejecutar_servicio(_servicio(raiz, comando=_comando(*args)), "F-900",
                                      raiz=str(raiz))

    assert resultado.resultado == esperado


def test_f059_r9_timeout_mata_el_arbol_y_no_es_rojo(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {}})
    servicio = _servicio(raiz, comando=f'"{PY}" con_nieto.py', timeout_s=3)

    inicio = time.monotonic()
    resultado = e2e.ejecutar_servicio(servicio, "F-900", raiz=str(raiz))

    assert resultado.resultado == "TIMEOUT"
    assert time.monotonic() - inicio < 30
    nieto = int((raiz / "svc" / "nieto.pid").read_text())
    time.sleep(0.5)
    assert not _vivo(nieto)


def test_f059_r9_un_arranque_que_muere_es_no_arranca_sin_esperar(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {}})
    servicio = _servicio(raiz, comando=_comando(0), arranque=f'"{PY}" -c "raise SystemExit(3)"',
                         espera_arranque_s=60)

    inicio = time.monotonic()
    resultado = e2e.ejecutar_servicio(servicio, "F-900", raiz=str(raiz),
                                      sonda=lambda url: False)

    assert resultado.resultado == "NO ARRANCA"
    assert time.monotonic() - inicio < 30
    assert not (raiz / "svc" / "entorno.json").exists()


def test_f059_r9_una_url_que_no_responde_a_tiempo_es_no_arranca(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {}})
    lanzados: list = []

    def lanzar(*args, **kwargs):
        lanzados.append(subprocess.Popen(*args, **kwargs))
        return lanzados[-1]

    servicio = _servicio(raiz, comando=_comando(0), arranque=f'"{PY}" con_nieto.py',
                         espera_arranque_s=1)
    resultado = e2e.ejecutar_servicio(servicio, "F-900", raiz=str(raiz), lanzar=lanzar,
                                      sonda=lambda url: False)

    assert resultado.resultado == "NO ARRANCA"
    assert len(lanzados) == 1 and lanzados[0].poll() is not None


def test_f059_r9_configuracion_invalida_sale_con_4(tmp_path: Path, capsys) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"runner": "cypress"}})

    assert e2e.main(["--feature", "F-900", "--raiz", str(raiz)]) == 4
    assert "runner" in capsys.readouterr().err


# --- R6: dónde y con qué entorno se ejecuta ----------------------------------


def test_f059_r6_ejecuta_en_la_ruta_del_servicio_con_las_variables(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {}})

    e2e.ejecutar_servicio(_servicio(raiz, comando=_comando(0)), "F-900", raiz=str(raiz),
                          url_base="http://127.0.0.1:9999")

    entorno = json.loads((raiz / "svc" / "entorno.json").read_text())
    assert Path(entorno["cwd"]).resolve() == (raiz / "svc").resolve()
    assert entorno["ARNES_E2E"] == "1"
    assert entorno["ARNES_E2E_URL_BASE"] == "http://127.0.0.1:9999"
    salida = (raiz / ".arnes_cache" / "e2e" / "F-900" / "svc").resolve()
    assert Path(entorno["ARNES_E2E_SALIDA"]) == salida


def test_f059_r6_con_servicio_solo_ese(tmp_path: Path, capsys) -> None:
    raiz = _proyecto(tmp_path, {"uno": {"comando": _comando(0)},
                                "dos": {"comando": _comando(0)}})

    codigo = e2e.main(["--feature", "F-900", "--servicio", "dos", "--raiz", str(raiz)])

    assert codigo == 0
    assert (raiz / "dos" / "entorno.json").exists()
    assert not (raiz / "uno" / "entorno.json").exists()


def test_f059_r6_sin_servicio_todos(tmp_path: Path, capsys) -> None:
    raiz = _proyecto(tmp_path, {"uno": {"comando": _comando(0)},
                                "dos": {"comando": _comando(1)}, "tres": None})

    codigo = e2e.main(["--feature", "F-900", "--raiz", str(raiz)])

    assert codigo == 1
    assert (raiz / "uno" / "entorno.json").exists() and (raiz / "dos" / "entorno.json").exists()
    salida = capsys.readouterr().out
    assert "[uno]: VERDE" in salida and "[dos]: ROJO" in salida and "tres" not in salida


@pytest.mark.parametrize("nombre", ["nadie", "tres"])
def test_f059_r6_un_servicio_sin_bloque_o_inexistente_es_configuracion(
    tmp_path: Path, nombre
) -> None:
    raiz = _proyecto(tmp_path, {"uno": {"comando": _comando(0)}, "tres": None})

    assert e2e.main(["--feature", "F-900", "--servicio", nombre, "--raiz", str(raiz)]) == 4


# --- R7: el arranque se lanza antes y se para siempre ------------------------


def _registrando(lanzados: list, falla_en: int | None = None):
    def lanzar(*args, **kwargs):
        if falla_en is not None and len(lanzados) == falla_en:
            raise OSError("fallo provocado")
        lanzados.append((args[0], subprocess.Popen(*args, **kwargs)))
        return lanzados[-1][1]
    return lanzar


@pytest.mark.parametrize(("comando", "timeout_s", "esperado"), [
    (_comando(0), 900, "VERDE"), (_comando(1), 900, "ROJO"),
    (_comando(0, 30), 2, "TIMEOUT"),
])
def test_f059_r7_el_arranque_va_antes_y_se_para_al_terminar(
    tmp_path: Path, comando, timeout_s, esperado
) -> None:
    raiz = _proyecto(tmp_path, {"svc": {}})
    lanzados: list = []
    sondeadas: list = []
    arranque = f'"{PY}" con_nieto.py'

    def sonda(url: str) -> bool:
        sondeadas.append(url)
        return len(sondeadas) > 1

    resultado = e2e.ejecutar_servicio(
        _servicio(raiz, comando=comando, arranque=arranque, timeout_s=timeout_s),
        "F-900", raiz=str(raiz), lanzar=_registrando(lanzados), sonda=sonda,
        dormir=lambda s: time.sleep(0.5))

    assert resultado.resultado == esperado
    assert [orden for orden, _ in lanzados] == [arranque, comando]
    assert sondeadas == ["http://localhost:8000"] * 2
    assert all(proceso.poll() is not None for _, proceso in lanzados)
    time.sleep(0.5)
    assert not _vivo(int((raiz / "svc" / "nieto.pid").read_text()))


def test_f059_r7_tras_una_excepcion_el_arranque_tambien_se_para(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {}})
    lanzados: list = []

    with pytest.raises(OSError, match="fallo provocado"):
        e2e.ejecutar_servicio(
            _servicio(raiz, comando=_comando(0), arranque=f'"{PY}" con_nieto.py'),
            "F-900", raiz=str(raiz), lanzar=_registrando(lanzados, falla_en=1),
            sonda=lambda url: True)

    assert len(lanzados) == 1 and lanzados[0][1].poll() is not None


def test_f059_r7_parar_arbol_mata_hijo_y_nieto(tmp_path: Path) -> None:
    (tmp_path / "con_nieto.py").write_text(CON_NIETO, encoding="utf-8")
    proceso = subprocess.Popen([sys.executable, "con_nieto.py"], cwd=tmp_path,
                               **e2e._opciones_arbol())
    limite = time.monotonic() + 30
    while not (tmp_path / "nieto.pid").exists() and time.monotonic() < limite:
        time.sleep(0.1)
    time.sleep(0.2)
    nieto = int((tmp_path / "nieto.pid").read_text())

    e2e.parar_arbol(proceso)
    e2e.parar_arbol(proceso)  # ya parado: no hace nada

    time.sleep(0.5)
    assert proceso.poll() is not None
    assert not _vivo(nieto)


class _CarreraConLaMuerte:
    """Proceso que `poll()` da por vivo y que ya murió cuando llega la orden de parar."""

    pid = 4_000_000  # nunca se usa contra el sistema: run y killpg van simulados

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0


def test_f059_r7_parar_un_proceso_que_muere_en_la_carrera_no_lanza(monkeypatch) -> None:
    """Dentro de un `finally`, una orden de parada fallida no puede tapar el resultado."""
    llamadas: list = []

    def run(args, **kwargs):
        # Como `taskkill` sobre un PID que ya no existe: código 128. Si alguien
        # pidiera check=True, el CompletedProcess real lanzaría aquí.
        llamadas.append(args)
        completado = subprocess.CompletedProcess(args, 128, b"", b"no encontrado")
        if kwargs.get("check"):
            completado.check_returncode()
        return completado

    def killpg(pid, senal):
        llamadas.append(pid)
        raise ProcessLookupError(pid)

    monkeypatch.setattr(e2e.subprocess, "run", run)
    if hasattr(e2e.os, "killpg"):
        monkeypatch.setattr(e2e.os, "killpg", killpg)

    e2e.parar_arbol(_CarreraConLaMuerte())

    assert len(llamadas) == 1


def test_f059_r7_url_responde_sin_servidor_es_false() -> None:
    assert e2e.url_responde("http://127.0.0.1:9/", timeout_s=0.5) is False
    assert e2e.url_responde("no-es-una-url") is False


# --- R8: el comando por defecto de cada runner -------------------------------


def test_f059_r8_pytest_playwright_por_defecto(tmp_path: Path) -> None:
    servicio = _servicio(tmp_path)

    comando, entorno = e2e.comando_efectivo(servicio, "http://h:1", tmp_path / "t")

    assert comando[:4] == [sys.executable, "-m", "pytest", "tests_e2e"]
    assert "--base-url=http://h:1" in comando
    assert "--tracing=retain-on-failure" in comando
    assert f"--junitxml={(tmp_path / 't' / 'junit.xml').resolve()}" in comando
    assert f"--output={(tmp_path / 't' / 'trazas').resolve()}" in comando
    assert entorno["ARNES_E2E"] == "1"


def test_f059_r8_playwright_test_por_defecto(tmp_path: Path) -> None:
    servicio = Servicio(nombre="w", ruta="w", lenguaje="otro", e2e=BloqueE2E(
        url_base="http://h:1", rutas_ui=("**",), runner="playwright-test"))

    comando, entorno = e2e.comando_efectivo(servicio, "http://h:1", tmp_path)

    assert Path(comando[0]).stem.lower() == "npx"
    assert comando[1:] == ["playwright", "test", "--reporter=junit"]
    assert entorno["PLAYWRIGHT_JUNIT_OUTPUT_NAME"] == str((tmp_path / "junit.xml").resolve())


def test_f059_r8_el_comando_declarado_va_por_shell(tmp_path: Path) -> None:
    comando, _ = e2e.comando_efectivo(_servicio(tmp_path, comando="make e2e | tee x"),
                                      "http://h:1", tmp_path)

    assert comando == "make e2e | tee x"


# --- R10: --url-base contra un host productivo --------------------------------


def test_f059_r10_url_base_productiva_sale_con_4_sin_lanzar(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0),
                                        "hosts_prohibidos": ["*.ruesma.es"]}})
    monkeypatch.setattr(e2e, "ejecutar_servicio",
                        lambda *a, **k: pytest.fail("no debía ejecutarse nada"))

    codigo = e2e.main(["--feature", "F-900", "--url-base", "https://App.Ruesma.es",
                       "--raiz", str(raiz)])

    assert codigo == 4
    assert "host declarado como productivo" in capsys.readouterr().err
    assert not (raiz / ".arnes_cache").exists()


@pytest.mark.parametrize("url_base", ["http://app.ruesma.es./", "http://app.ruesma.es%2e/"])
def test_f059_r10_url_base_productiva_normalizada_sale_con_4(
    tmp_path: Path, capsys, monkeypatch, url_base
) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0),
                                        "hosts_prohibidos": ["*.ruesma.es"]}})
    monkeypatch.setattr(e2e, "ejecutar_servicio",
                        lambda *a, **k: pytest.fail("no debía ejecutarse nada"))

    codigo = e2e.main(["--feature", "F-900", "--url-base", url_base, "--raiz", str(raiz)])

    assert codigo == 4
    assert "host declarado como productivo" in capsys.readouterr().err
    assert not (raiz / ".arnes_cache").exists()


@pytest.mark.parametrize("url_base", [
    "app.ruesma.es", "localhost:8000", "ftp://localhost/", "http://", "http:///x",
    # Pasada 3: lo que el navegador (WHATWG) lee distinto que urlsplit.
    "http://app.ruesma.es\\@localhost/", "http://localhost/\n", "http://loc\x00alhost/",
    "http://localhost\x7f/", "http://localhost/a b", "http://localhost/\t",
], ids=repr)
@pytest.mark.parametrize("prohibidos", [["*.ruesma.es"], []], ids=["con", "sin prohibidos"])
def test_f059_r10_url_base_sin_esquema_o_sin_host_sale_con_4(
    tmp_path: Path, capsys, monkeypatch, url_base, prohibidos
) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0),
                                        "hosts_prohibidos": prohibidos}})
    monkeypatch.setattr(e2e, "ejecutar_servicio",
                        lambda *a, **k: pytest.fail("no debía ejecutarse nada"))

    codigo = e2e.main(["--feature", "F-900", "--url-base", url_base, "--raiz", str(raiz)])

    assert codigo == 4
    error = capsys.readouterr().err
    assert "--url-base" in error and "http://" in error and "barra invertida" in error
    assert not (raiz / ".arnes_cache").exists()


# Pasada 4: hosts no ASCII que el navegador mapea por IDNA a `app.ruesma.es`.
@pytest.mark.parametrize("url_base", [
    "http://app.ruesma.es\u3002/", "http://app.ruesma.es%E3%80%82/",
    "http://app.ruesma.es\uff0e/", "http://app.ruesma.es\uff61/",
    "http://app.ruesma\u00ad.es/", "http://app.ruesma%C2%AD.es/",
    "http://app.ruesma\u200b.es/", "http://\uff41pp.ruesma.es/",
], ids=ascii)
@pytest.mark.parametrize("prohibidos", [["*.ruesma.es", "app.ruesma.es"], []],
                         ids=["con", "sin prohibidos"])
def test_f059_r10_url_base_con_host_no_ascii_sale_con_4(
    tmp_path: Path, capsys, monkeypatch, url_base, prohibidos
) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0),
                                        "hosts_prohibidos": prohibidos}})
    monkeypatch.setattr(e2e, "ejecutar_servicio",
                        lambda *a, **k: pytest.fail("no debía ejecutarse nada"))

    codigo = e2e.main(["--feature", "F-900", "--url-base", url_base, "--raiz", str(raiz)])

    assert codigo == 4
    error = capsys.readouterr().err
    assert "--url-base" in error and "no ASCII" in error and "xn--" in error
    assert not (raiz / ".arnes_cache").exists()


# Pasada 5: hosts que el navegador analiza como IPv4 10.0.0.5 o 127.0.0.1.
@pytest.mark.parametrize("url_base", [
    "http://10.5/", "http://167772165/", "http://0x0a000005/", "http://012.0.0.5/",
    "http://10.0.0.05/", "http://127.1/", "http://0/", "http://[::ffff:10.0.0.5]/",
])
@pytest.mark.parametrize("prohibidos", [["10.0.0.5", "127.0.0.1"], []],
                         ids=["con", "sin prohibidos"])
def test_f059_r10_url_base_con_ip_no_canonica_sale_con_4(
    tmp_path: Path, capsys, monkeypatch, url_base, prohibidos
) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0),
                                        "hosts_prohibidos": prohibidos}})
    monkeypatch.setattr(e2e, "ejecutar_servicio",
                        lambda *a, **k: pytest.fail("no debía ejecutarse nada"))

    codigo = e2e.main(["--feature", "F-900", "--url-base", url_base, "--raiz", str(raiz)])

    assert codigo == 4
    error = capsys.readouterr().err
    assert "--url-base" in error and "IP en forma canónica" in error
    assert not (raiz / ".arnes_cache").exists()


def test_f059_r10_url_base_idn_en_forma_xn_casa_con_su_glob(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0),
                                        "hosts_prohibidos": ["*.ruesma.es"]}})
    monkeypatch.setattr(e2e, "ejecutar_servicio",
                        lambda *a, **k: pytest.fail("no debía ejecutarse nada"))

    codigo = e2e.main(["--feature", "F-900", "--url-base", "https://xn--pp-8cd.ruesma.es/",
                       "--raiz", str(raiz)])

    assert codigo == 4
    assert "host declarado como productivo" in capsys.readouterr().err


# --- R11–R12: el resumen y dónde quedan los artefactos -----------------------

RIGOR = Path(__file__).resolve().parents[1] / "harness" / "rigor.json"


def _con_rigor(raiz: Path) -> Path:
    (raiz / "harness" / "rigor.json").write_text(RIGOR.read_text(encoding="utf-8"),
                                                 encoding="utf-8")
    return raiz


def test_f059_r11_resumen_de_un_rojo_con_junit(tmp_path: Path) -> None:
    raiz = _con_rigor(_proyecto(tmp_path, {"svc": {"comando": _comando(1, 0, "junit_falso.xml")}}))

    codigo = e2e.main(["--feature", "F-900", "--raiz", str(raiz)])

    texto = (raiz / "progress" / "e2e_F-900.md").read_text(encoding="utf-8")
    assert codigo == 1
    assert texto.startswith("# F-900 · Capa e2e\n")
    for fila in ("| Fecha | ", "| SHA de HEAD | desconocido |", "| Nivel | estandar |",
                 "| Modo de la capa | informativa |", "| Resultado global | ROJO |"):
        assert fila in texto, fila
    fila_svc = next(li for li in texto.splitlines() if li.startswith("| svc |"))
    for dato in ("pytest-playwright", "juguete.py 1 0 junit_falso.xml",
                 "http://localhost:8000", "ROJO", "| 2 | 1 | 1 |",
                 ".arnes_cache/e2e/F-900/svc"):
        assert dato in fila_svc, dato
    cola = texto.split("## Cola de salida", 1)[1]
    assert "linea 29" in cola and "linea 10" in cola and "linea 9\n" not in cola


def test_f059_r11_un_verde_sin_junit_dice_desconocido_y_sin_cola(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0)}})

    assert e2e.main(["--feature", "F-900", "--raiz", str(raiz)]) == 0

    texto = (raiz / "progress" / "e2e_F-900.md").read_text(encoding="utf-8")
    fila_svc = next(li for li in texto.splitlines() if li.startswith("| svc |"))
    assert "| VERDE |" in fila_svc and fila_svc.count("desconocido") == 3
    assert "| Nivel | desconocido |" in texto
    assert "## Cola de salida" not in texto
    assert "| Resultado global | VERDE |" in texto


def test_f059_r11_salida_fuera_de_progress(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0)}})
    otra = tmp_path / "fuera" / "e2e_reviewer.md"

    e2e.main(["--feature", "F-900", "--raiz", str(raiz), "--salida", str(otra)])

    assert otra.read_text(encoding="utf-8").startswith("# F-900 · Capa e2e")
    assert not (raiz / "progress").exists()


def test_f059_r11_el_sha_es_el_de_head(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0)}})
    git = ["git", "-C", str(raiz), "-c", "user.name=A", "-c", "user.email=a@b.invalid",
           "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "x"], check=True)
    sha = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True,
                         check=True).stdout.strip()

    e2e.main(["--feature", "F-900", "--raiz", str(raiz)])

    assert f"| SHA de HEAD | {sha} |" in (raiz / "progress" / "e2e_F-900.md").read_text(
        encoding="utf-8")


def test_f059_r12_artefactos_en_la_cache_vaciada_al_empezar(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0, 0, "junit_falso.xml")}})
    viejo = raiz / ".arnes_cache" / "e2e" / "F-900" / "svc" / "viejo.txt"
    viejo.parent.mkdir(parents=True)
    viejo.write_text("de otra ejecución", encoding="utf-8")

    e2e.main(["--feature", "F-900", "--raiz", str(raiz)])

    carpeta = viejo.parent
    assert not viejo.exists()
    assert (carpeta / "junit.xml").is_file() and (carpeta / "salida.txt").is_file()
    assert "linea 29" in (carpeta / "salida.txt").read_text(encoding="utf-8")
    assert sorted(p.name for p in (raiz / "progress").iterdir()) == ["e2e_F-900.md"]


def test_f059_r12_contar_junit(tmp_path: Path) -> None:
    (tmp_path / "j.xml").write_text(JUNIT, encoding="utf-8")
    (tmp_path / "roto.xml").write_text("<no", encoding="utf-8")

    assert e2e.contar_junit(tmp_path / "j.xml") == (2, 1, 1)
    assert e2e.contar_junit(tmp_path / "roto.xml") is None
    assert e2e.contar_junit(tmp_path / "no_existe.xml") is None


# --- R13–R14: requisitos marcados `(capa: e2e)` --------------------------------

SPEC = """\
# Requisitos

- **R1.** El sistema debe validar. (capa: unit)
- **R4.** CUANDO se dé de alta una obra, la pantalla debe mostrarla
  en el listado (capa: e2e)
- **R7.** Menciona `(capa: e2e)` en medio y es de otra capa. (capa: unit)
- **R9.** El listado debe paginar (capa: E2E).

## Otra sección

- **R12.** Sin marca: cuenta como unit.
- **R13.** El informe debe salir en pantalla (capa:
  e2e)
"""


def test_f059_r13_requisitos_e2e_por_la_marca_final(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {}, spec=SPEC)

    assert e2e.requisitos_e2e("F-900", str(raiz)) == ["R4", "R9", "R13"]
    assert e2e.requisitos_e2e("F-901", str(raiz)) == []


def test_f059_r13_trazado_por_nombre_de_test(tmp_path: Path) -> None:
    (tmp_path / "j.xml").write_text(JUNIT, encoding="utf-8")

    filas = e2e.trazar_requisitos("F-900", ["R4", "R9", "R13"], [tmp_path / "j.xml"])

    assert filas == [
        ("R4", ["test_f900_r4_alta_de_obra", "test_F900_R4_baja"], "FALLA"),
        ("R9", ["test_f900_r9_listado"], "PASA"),
        ("R13", [], "sin test"),
    ]


def test_f059_r13_sin_junit_el_resultado_es_desconocido(tmp_path: Path) -> None:
    assert e2e.trazar_requisitos("F-900", ["R4"], [tmp_path / "no.xml"]) == [
        ("R4", [], "desconocido (sin junit)")]


def test_f059_r13_el_resumen_trae_una_fila_por_requisito(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path, {"svc": {"comando": _comando(0, 0, "junit_falso.xml")}},
                     spec=SPEC)

    e2e.main(["--feature", "F-900", "--raiz", str(raiz)])

    texto = (raiz / "progress" / "e2e_F-900.md").read_text(encoding="utf-8")
    tabla = texto.split("## Requisitos e2e", 1)[1]
    assert "| R4 | test_f900_r4_alta_de_obra, test_F900_R4_baja | FALLA |" in tabla
    assert "| R9 | test_f900_r9_listado | PASA |" in tabla
    assert "| R13 | — | sin test |" in tabla


def test_f059_r14_requisitos_e2e_sin_servicio_que_los_ejecute(
    tmp_path: Path, capsys
) -> None:
    raiz = _proyecto(tmp_path, {"svc": None}, spec=SPEC)

    codigo = e2e.main(["--feature", "F-900", "--raiz", str(raiz)])

    assert codigo == 4
    error = capsys.readouterr().err
    assert "R4, R9, R13" in error and "ningún servicio declara el bloque e2e" in error
    assert not (raiz / "progress").exists()
