# tests/test_f028_cache_de_suites.py
"""F-028: la caché de suites no tapa un rojo.

Tres piezas sobre `harness.servicios` y `harness.cache_suites`:

- `ejecutar_siempre` (R6–R11, R16): rutas de tests de un servicio que se
  ejecutan aunque su suite se sirva de caché. Es para los barridos que leen
  todo el repositorio (postventa F-055: un test que recorre `progress/` no
  depende de nada que la clave vea, y con la caché válida nadie lo ejecutaba).
- `depende_de: ["."]` (R17–R19): el repositorio entero como dependencia.
- El escenario del §9 del encargo 1.7.12 (R20): un documento de `docs/` que un
  test lee, declarado en `depende_de`.

Git de verdad sobre repositorios diminutos en `tmp_path`, sin las variables
`GIT_*` del entorno; la sonda, falsa (inyectada). Sin red ni BBDD.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness import cache_suites, servicios
from harness.cache_suites import (
    FORMATO_CLAVE,
    Decision,
    Sondeo,
    clave_de,
    decidir,
    hash_en_head,
    lineas_de_salida,
    main,
    texto_de_clave,
)
from harness.servicios import Servicio, cargar_servicios

PY = sys.executable


@pytest.fixture(autouse=True)
def _sin_variables_git(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in list(os.environ):
        if variable.startswith("GIT_"):
            monkeypatch.delenv(variable, raising=False)


# === servicios: el campo `ejecutar_siempre` (R6–R9) ===========================


def _arbol(raiz: Path, *rutas: str) -> Path:
    """Crea carpetas (o ficheros, si la ruta acaba en `.py`) bajo `raiz`."""
    for ruta in rutas:
        destino = raiz / ruta
        if destino.suffix == ".py":
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text("", encoding="utf-8")
        else:
            destino.mkdir(parents=True, exist_ok=True)
    return raiz


def _declarar(raiz: Path, entradas: list[dict]) -> None:
    fichero = raiz / "harness" / "servicios.json"
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(json.dumps({"servicios": entradas}), encoding="utf-8")


def _uno(raiz: Path, **extra: object) -> list[Servicio]:
    """Declara `svc` (python, ruta `services/svc`) con los campos extra."""
    entrada: dict = {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python"}
    entrada.update(extra)
    _declarar(raiz, [entrada])
    return cargar_servicios(raiz=str(raiz))


@pytest.fixture
def raiz_svc(tmp_path: Path) -> Path:
    """`services/svc` con un fichero y una carpeta de barridos."""
    return _arbol(
        tmp_path,
        "services/svc/tests/test_barrido.py",
        "services/svc/tests/barridos/test_progress.py",
    )


def test_f028_r6_ejecutar_siempre_ausente_es_tupla_vacia(raiz_svc: Path) -> None:
    (servicio,) = _uno(raiz_svc)

    assert servicio.ejecutar_siempre == ()


def test_f028_r6_ejecutar_siempre_normalizado_y_en_orden(raiz_svc: Path) -> None:
    (servicio,) = _uno(
        raiz_svc,
        ejecutar_siempre=["tests\\barridos\\", "tests/test_barrido.py"],
    )

    assert servicio.ejecutar_siempre == ("tests/barridos", "tests/test_barrido.py")


@pytest.mark.parametrize("valor", ["tests/test_barrido.py", {"a": 1}, None, 3])
def test_f028_r7_ejecutar_siempre_que_no_es_lista_falla(
    raiz_svc: Path, valor: object
) -> None:
    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, ejecutar_siempre=valor)

    mensaje = str(error.value)
    assert "'svc'" in mensaje and "'ejecutar_siempre'" in mensaje
    assert "lista" in mensaje and repr(valor) in mensaje


@pytest.mark.parametrize(
    "valor",
    [
        "",
        "   ",
        3,
        "/tests/test_barrido.py",
        "C:/tests",
        "\\\\servidor\\tests",
        "../otro/tests",
        "tests/../../fuera",
        "tests|barridos",
        "tests/test_barrido.py\n",
        "tests\rbarridos",
    ],
)
def test_f028_r7_ruta_invalida_de_ejecutar_siempre_falla_nombrando_servicio_campo_y_valor(
    raiz_svc: Path, valor: object
) -> None:
    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, ejecutar_siempre=[valor])

    mensaje = str(error.value)
    assert "'svc'" in mensaje
    assert "'ejecutar_siempre'" in mensaje
    assert repr(valor) in mensaje


def test_f028_r7_ejecutar_siempre_repetida_tras_normalizar_falla(raiz_svc: Path) -> None:
    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, ejecutar_siempre=["tests/barridos", "tests\\barridos\\"])

    mensaje = str(error.value)
    assert "'ejecutar_siempre'" in mensaje and "repetida" in mensaje


@pytest.mark.parametrize("clave", ["depende_de", "entradas_no_versionadas"])
@pytest.mark.parametrize("valor", ["services/svc\n", "services\r/svc"])
def test_f028_r7_el_salto_de_linea_tambien_falla_en_las_otras_rutas(
    raiz_svc: Path, clave: str, valor: str
) -> None:
    """Endurecimiento compartido de `_rutas`: un salto rompería `AVISO|` y `--shell`."""
    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, **{clave: [valor]})

    assert f"'{clave}'" in str(error.value) and repr(valor) in str(error.value)


@pytest.mark.parametrize(
    "clave",
    ["ejecutar_siempres", "ejecuta_siempre", "ejecutar-siempre", "Ejecutar_Siempre",
     "ejecutarsiempre"],
)
def test_f028_r7_clave_parecida_a_ejecutar_siempre_falla_y_sugiere_la_buena(
    raiz_svc: Path, clave: str
) -> None:
    """Mal escrita, se ignoraría: los barridos dejarían de correr sin avisar."""
    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, **{clave: ["tests/test_barrido.py"]})

    mensaje = str(error.value)
    assert "'svc'" in mensaje
    assert repr(clave) in mensaje
    assert "'ejecutar_siempre'" in mensaje
    assert "alcance_incluye" not in mensaje


def test_f028_r7_la_clave_parecida_a_alcance_incluye_sigue_sugiriendo_la_suya(
    raiz_svc: Path,
) -> None:
    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, alcance_incluir=["harness"])

    assert "'alcance_incluye'" in str(error.value)
    assert "ejecutar_siempre" not in str(error.value)


def test_f028_r7_una_clave_ajena_sigue_ignorandose(raiz_svc: Path) -> None:
    (servicio,) = _uno(raiz_svc, siempre_notas="libre", ejecutar="otra cosa")

    assert servicio.ejecutar_siempre == ()


def test_f028_r8_ruta_que_no_existe_bajo_el_servicio_falla(raiz_svc: Path) -> None:
    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, ejecutar_siempre=["tests/test_barrido.py", "tests/no_existe.py"])

    mensaje = str(error.value)
    assert "'svc'" in mensaje and "'ejecutar_siempre'" in mensaje
    assert "'tests/no_existe.py'" in mensaje
    assert "'services/svc'" in mensaje


def test_f028_r8_la_existencia_se_mira_bajo_la_ruta_del_servicio_y_no_la_raiz(
    raiz_svc: Path,
) -> None:
    """`tests/de_la_raiz.py` existe en la raíz, pero no bajo `services/svc`."""
    _arbol(raiz_svc, "tests/de_la_raiz.py")

    with pytest.raises(ValueError) as error:
        _uno(raiz_svc, ejecutar_siempre=["tests/de_la_raiz.py"])

    assert "'tests/de_la_raiz.py'" in str(error.value)


def test_f028_r8_la_existencia_se_mira_bajo_la_raiz_y_no_en_el_cwd(
    raiz_svc: Path, tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    otro = _arbol(tmp_path_factory.mktemp("cwd"), "services/svc/tests/solo_aqui.py")
    monkeypatch.chdir(otro)

    with pytest.raises(ValueError):
        _uno(raiz_svc, ejecutar_siempre=["tests/solo_aqui.py"])


def test_f028_r8_fichero_y_carpeta_existentes_valen(raiz_svc: Path) -> None:
    (servicio,) = _uno(
        raiz_svc, ejecutar_siempre=["tests/test_barrido.py", "tests/barridos"]
    )

    assert len(servicio.ejecutar_siempre) == 2


@pytest.mark.parametrize("valor", [[], ["tests"]])
def test_f028_r9_ejecutar_siempre_en_un_servicio_que_no_es_python_falla(
    tmp_path: Path, valor: list
) -> None:
    raiz = _arbol(tmp_path, "web/tests")
    _declarar(raiz, [{"nombre": "web", "ruta": "web", "lenguaje": "otro",
                      "ejecutar_siempre": valor}])

    with pytest.raises(ValueError) as error:
        cargar_servicios(raiz=str(raiz))

    mensaje = str(error.value)
    assert "'web'" in mensaje and "'ejecutar_siempre'" in mensaje
    assert "'python'" in mensaje and "'otro'" in mensaje


def test_f028_r9_validar_sale_con_1_y_el_motivo_en_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _arbol(tmp_path, "web")
    _declarar(raiz, [{"nombre": "web", "ruta": "web", "lenguaje": "otro",
                      "ejecutar_siempre": ["tests"]}])

    codigo = servicios.main(["--validar", "--raiz", str(raiz)])

    salida = capsys.readouterr()
    assert codigo == 1 and salida.out == "" and "ejecutar_siempre" in salida.err


# === cache_suites: git de verdad ==============================================


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Arnes", "-c", "user.email=arnes@ejemplo.invalid",
         "-C", str(raiz), *args],
        capture_output=True, text=True, encoding="utf-8", check=True,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    ).stdout


def _escribir(raiz: Path, ruta: str, texto: str) -> None:
    fichero = raiz / ruta
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(texto, encoding="utf-8")


def _commit(raiz: Path) -> None:
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "cambio")


@pytest.fixture(scope="module")
def _plantilla(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Una vez por módulo: en Windows, cada proceso git cuesta."""
    raiz = tmp_path_factory.mktemp("plantilla_f028") / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _escribir(raiz, ".gitignore", ".env\n.arnes_cache/\ncoverage.json\n__pycache__/\n")
    _escribir(raiz, "services/svc/app.py", "X = 1\n")
    _escribir(raiz, "services/svc/tests/test_barrido.py", "")
    _escribir(raiz, "services/svc/tests/barridos/test_progress.py", "")
    _escribir(raiz, "services/otro/otro.py", "Z = 1\n")
    _escribir(raiz, "docs/INTEGRACION.md", "# Integración\n")
    _escribir(raiz, "docs/OTRO.md", "# Otro\n")
    _escribir(raiz, "progress/current.md", "nada\n")
    _escribir(raiz, "harness/servicios.json", json.dumps({"servicios": [
        {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python",
         "ejecutar_siempre": ["tests/test_barrido.py", "tests/barridos"]},
    ]}))
    _commit(raiz)
    return raiz


@pytest.fixture
def repo(_plantilla: Path, tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    shutil.copytree(_plantilla, raiz)
    return raiz


def _svc(**extra: object) -> Servicio:
    datos: dict = {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python"}
    datos.update(extra)
    return Servicio(**datos)


SONDEO = Sondeo(origenes={}, tiene_coverage=False)


def _sonda(interprete: str, modulos: tuple[str, ...], cwd: Path,
           limite_s: int = 30) -> Sondeo:
    return SONDEO


def _clave(repo: Path, servicio: Servicio) -> tuple[str | None, list[str]]:
    return clave_de(servicio, str(repo), PY, SONDEO)


def _guardar_verde(repo: Path, servicio: Servicio) -> str:
    """Deja en `.arnes_cache` el verde de la clave actual (lo que haría init.sh)."""
    clave = decidir(servicio, str(repo), sondear=_sonda).clave
    assert clave is not None
    (repo / ".arnes_cache").mkdir(exist_ok=True)
    (repo / ".arnes_cache" / f"suite_{servicio.nombre}.ok").write_text(
        clave, encoding="utf-8")
    return clave


SIEMPRE = ("tests/test_barrido.py", "tests/barridos")


# --- R10 / R11: líneas SIEMPRE| solo al servir ---------------------------------


def test_f028_r10_al_servir_la_decision_lleva_ejecutar_siempre_en_orden(
    repo: Path,
) -> None:
    servicio = _svc(ejecutar_siempre=SIEMPRE)
    _guardar_verde(repo, servicio)

    decision = decidir(servicio, str(repo), sondear=_sonda)

    assert decision.servir is True
    assert decision.siempre == SIEMPRE


def test_f028_r10_lineas_siempre_despues_de_los_avisos_y_antes_de_servir() -> None:
    decision = Decision(True, "a" * 64, "2026-10-29 10:00", ("uno", "dos"),
                        siempre=("tests/b.py", "tests/a"))

    assert lineas_de_salida(decision) == [
        "AVISO|uno", "AVISO|dos",
        "SIEMPRE|tests/b.py", "SIEMPRE|tests/a",
        "SERVIR|2026-10-29 10:00",
    ]


def test_f028_r10_la_cli_imprime_siempre_y_servir(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """La forma en que lo consume init.sh: leyendo `harness/servicios.json`."""
    monkeypatch.setattr(cache_suites, "sondear", _sonda)
    _guardar_verde(repo, _svc(ejecutar_siempre=SIEMPRE))

    codigo = main(["--servicio", "svc", "--raiz", str(repo)])

    lineas = capsys.readouterr().out.splitlines()
    assert codigo == 0
    assert lineas[:2] == ["SIEMPRE|tests/test_barrido.py", "SIEMPRE|tests/barridos"]
    assert lineas[2].startswith("SERVIR|") and len(lineas) == 3


def test_f028_r11_al_ejecutar_no_hay_siempre_en_la_decision(repo: Path) -> None:
    decision = decidir(_svc(ejecutar_siempre=SIEMPRE), str(repo), sondear=_sonda)

    assert decision.servir is False
    assert decision.siempre == ()
    assert [linea for linea in lineas_de_salida(decision)
            if linea.startswith("SIEMPRE|")] == []


def test_f028_r11_sin_cache_tampoco_hay_siempre(repo: Path) -> None:
    servicio = _svc(ejecutar_siempre=SIEMPRE)
    _guardar_verde(repo, servicio)

    decision = decidir(servicio, str(repo), sin_cache=True, sondear=_sonda)

    assert decision.servir is False and decision.siempre == ()


def test_f028_r11_lineas_de_salida_no_emite_siempre_si_no_se_sirve() -> None:
    """Aunque alguien construya la decisión a mano: EJECUTAR ya corre la suite entera."""
    decision = Decision(False, "b" * 64, None, ("uno",), siempre=("tests/a",))

    assert lineas_de_salida(decision) == ["AVISO|uno", f"EJECUTAR|{'b' * 64}"]


def test_f028_r11_servir_sin_ejecutar_siempre_es_la_salida_de_siempre(repo: Path) -> None:
    servicio = _svc()
    _guardar_verde(repo, servicio)

    decision = decidir(servicio, str(repo), sondear=_sonda)

    assert decision.servir is True and decision.siempre == ()
    assert lineas_de_salida(decision) == [f"SERVIR|{decision.fecha_verde}"]


# --- R16: ejecutar_siempre no entra en la clave -----------------------------------


def test_f028_r16_ejecutar_siempre_no_cambia_la_clave(repo: Path) -> None:
    sin, _ = _clave(repo, _svc())
    con, _ = _clave(repo, _svc(ejecutar_siempre=SIEMPRE))
    texto, _ = texto_de_clave(_svc(ejecutar_siempre=SIEMPRE), str(repo), PY, SONDEO)

    assert sin is not None and con == sin
    assert texto is not None and "siempre" not in texto
    assert FORMATO_CLAVE == "cache-suites/2"


# --- R17–R19: "." en depende_de -------------------------------------------------


def _arbol_raiz(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD^{tree}").strip()


def test_f028_r17_hash_en_head_de_punto_es_el_arbol_raiz(repo: Path) -> None:
    assert hash_en_head(".", str(repo)) == _arbol_raiz(repo)


@pytest.mark.parametrize("declarado", [".", "./", ".\\"])
def test_f028_r17_depende_de_punto_da_clave_sin_aviso(repo: Path, declarado: str) -> None:
    _declarar(repo, [{"nombre": "svc", "ruta": "services/svc", "lenguaje": "python",
                      "depende_de": [declarado]}])
    _commit(repo)
    (servicio,) = cargar_servicios(raiz=str(repo))

    clave, avisos = _clave(repo, servicio)
    texto, _ = texto_de_clave(servicio, str(repo), PY, SONDEO)

    assert servicio.depende_de == (".",)
    assert avisos == []
    assert clave is not None
    assert f"depende=.@{_arbol_raiz(repo)}" in str(texto).splitlines()


@pytest.mark.parametrize(
    "cambio",
    ["docs/OTRO.md", "progress/nuevo.md", "services/otro/otro.py", ".gitignore"],
)
def test_f028_r18_con_punto_cualquier_cambio_sucio_quita_la_clave(
    repo: Path, cambio: str
) -> None:
    servicio = _svc(depende_de=(".",))
    assert _clave(repo, servicio)[0] is not None

    _escribir(repo, cambio, "sucio\n")

    assert _clave(repo, servicio) == (None, [])


@pytest.mark.parametrize(
    "cambio", ["docs/OTRO.md", "progress/current.md", "services/otro/otro.py"]
)
def test_f028_r19_un_commit_en_cualquier_ruta_cambia_la_clave_con_punto(
    repo: Path, cambio: str
) -> None:
    con_punto = _svc(depende_de=(".",))
    sin_punto = _svc()
    antes_con, _ = _clave(repo, con_punto)
    antes_sin, _ = _clave(repo, sin_punto)

    _escribir(repo, cambio, "commiteado\n")
    _commit(repo)

    despues_con, _ = _clave(repo, con_punto)
    assert antes_con is not None and despues_con is not None
    assert despues_con != antes_con
    assert antes_sin is not None and _clave(repo, sin_punto)[0] == antes_sin


# --- R20: el §9 del encargo 1.7.12, un documento de docs/ que un test lee ----------

INTEGRACION = Servicio(nombre="svc", ruta="services/svc", lenguaje="python",
                       depende_de=("docs/INTEGRACION.md",))


def test_f028_r20_commit_en_el_documento_declarado_invalida_el_verde(repo: Path) -> None:
    antes = _guardar_verde(repo, INTEGRACION)
    assert decidir(INTEGRACION, str(repo), sondear=_sonda).servir is True

    _escribir(repo, "docs/INTEGRACION.md", "# Integración\n\nEl contrato cambia.\n")
    _commit(repo)

    decision = decidir(INTEGRACION, str(repo), sondear=_sonda)
    assert decision.servir is False
    assert decision.clave is not None and decision.clave != antes
    assert lineas_de_salida(decision) == [f"EJECUTAR|{decision.clave}"]


def test_f028_r20_control_negativo_otro_documento_de_docs_no_invalida(
    repo: Path,
) -> None:
    antes = _guardar_verde(repo, INTEGRACION)

    _escribir(repo, "docs/OTRO.md", "# Otro\n\nCambio que no lee nadie.\n")
    _commit(repo)

    decision = decidir(INTEGRACION, str(repo), sondear=_sonda)
    assert decision.clave == antes
    assert decision.servir is True


def test_f028_r20_el_documento_sin_commitear_ejecuta_sin_clave(repo: Path) -> None:
    _guardar_verde(repo, INTEGRACION)

    _escribir(repo, "docs/INTEGRACION.md", "# Integración\n\nA medio escribir.\n")

    decision = decidir(INTEGRACION, str(repo), sondear=_sonda)
    assert decision.servir is False and decision.clave is None


# --- R22: sin `ejecutar_siempre`, lo mismo que la 1.7.16 ---------------------------


def test_f028_r22_decision_posicional_de_la_1_7_16_sigue_valiendo() -> None:
    """Quien construya `Decision` con los cuatro campos de antes no se rompe."""
    servir = Decision(True, "a" * 64, "2026-10-15 09:30", ())
    ejecutar = Decision(False, "b" * 64, None, ("uno",))

    assert servir.siempre == () and ejecutar.siempre == ()
    assert lineas_de_salida(servir) == ["SERVIR|2026-10-15 09:30"]
    assert lineas_de_salida(ejecutar) == ["AVISO|uno", f"EJECUTAR|{'b' * 64}"]


def test_f028_r22_la_misma_clave_con_y_sin_el_campo_declarado(repo: Path) -> None:
    """Declarar `ejecutar_siempre` al actualizar no invalida las cachés existentes."""
    (con,) = cargar_servicios(raiz=str(repo))
    sin = _svc()

    assert con.ejecutar_siempre == SIEMPRE
    assert _clave(repo, con) == _clave(repo, sin)


def test_f028_r22_shell_y_validar_identicos_con_y_sin_el_campo(
    raiz_svc: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    salidas = []
    for extra in ({}, {"ejecutar_siempre": ["tests/barridos"]}):
        _uno(raiz_svc, **extra)
        servicios.main(["--shell", "--raiz", str(raiz_svc)])
        servicios.main(["--validar", "--raiz", str(raiz_svc)])
        salidas.append(capsys.readouterr())

    assert salidas[0] == salidas[1]
    assert salidas[0].out == (
        f"svc|services/svc|python|{Path(PY).as_posix()}|\n"
        "    1 servicio(s): svc (python)\n"
    )
