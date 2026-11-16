# tests/test_alcance_por_servicio.py
"""Un servicio puede pedir que su `harness/` se mida (F-052).

Desde la 1.7.8 el alcance AUTOMÁTICO —el que sale del diff y alimenta la puerta
de cobertura y la campaña de mutación— excluye `harness` como segmento a
cualquier profundidad, para que la campaña no se mute a sí misma. Pero en el
repositorio que PRODUCE el arnés (el taller) el producto es justamente
`arnes-base/harness/`: con un portero ≥ 1.7.8 se quedaba sin medir.

La salida elegida por el humano (opción B, 2026-10-18): cada servicio de
`harness/servicios.json` puede declarar `"alcance_incluye": ["harness"]`, y
entonces el `harness/` que cae bajo SU ruta deja de excluirse. Sin la clave,
nada cambia: es requisito duro, porque el instalador sirve a proyectos ya
instalados.

Nombres trazables a `acceptance` de F-052: `r1` (la clave y su ausencia), `r2`
(el árbol del taller, de punta a punta). Sin red: git de juguete en `tmp_path`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import cobertura, servicios
from harness.alcance import (
    DIRECTORIOS_EXCLUIDOS,
    DIRECTORIOS_EXCLUIDOS_AL_DECLARAR,
    alcance_de_feature,
    filtrar_produccion,
)
from harness.mutacion import main as mutacion_main
from harness.servicios import DIRECTORIOS_INCLUIBLES, Servicio, cargar_servicios

#: El servicio del taller tal y como lo declarará su `servicios.json`.
TALLER = Servicio(
    nombre="payload",
    ruta="arnes-base",
    lenguaje="python",
    alcance_incluye=("harness",),
)

RAMA = "feature/F-900-taller"


# --- Ayudas -----------------------------------------------------------------


def _declarar(raiz: Path, entradas: list[dict]) -> None:
    fichero = raiz / "harness" / "servicios.json"
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(json.dumps({"servicios": entradas}), encoding="utf-8")


def _uno(tmp_path: Path, **extra: object) -> list[Servicio]:
    """Declara `payload` (python, ruta `arnes-base`) con los campos extra."""
    (tmp_path / "arnes-base").mkdir(parents=True, exist_ok=True)
    entrada = {"nombre": "payload", "ruta": "arnes-base", "lenguaje": "python"}
    entrada.update(extra)
    _declarar(tmp_path, [entrada])
    return cargar_servicios(raiz=str(tmp_path))


def _git(raiz: Path, *args: str) -> str:
    salida = subprocess.run(
        [
            "git",
            "-C",
            str(raiz),
            "-c",
            "user.name=Arnes",
            "-c",
            "user.email=arnes@ejemplo.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return salida.stdout.strip()


def _escribir(raiz: Path, ruta: str, texto: str) -> None:
    fichero = raiz / ruta
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(texto, encoding="utf-8", newline="\n")


def _taller(tmp_path: Path, con_clave: bool) -> Path:
    """Repositorio con la forma del taller y una rama que toca de todo.

    En `dev`: la declaración del servicio `payload` (con o sin la clave). En la
    rama: un módulo del payload (`arnes-base/harness/medir.py`), su test, un
    fichero del portero de la raíz (`harness/portero.py`) y uno de una carpeta
    que solo comparte PREFIJO DE TEXTO con el servicio (`arnes-base-x/`).
    """
    raiz = tmp_path / "taller"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "dev")
    _escribir(raiz, "arnes-base/LEEME.md", "payload\n")
    entrada: dict = {"nombre": "payload", "ruta": "arnes-base", "lenguaje": "python"}
    if con_clave:
        entrada["alcance_incluye"] = ["harness"]
    _declarar(raiz, [entrada])
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "inicio")

    _git(raiz, "checkout", "-q", "-b", RAMA)
    _escribir(
        raiz,
        "arnes-base/harness/medir.py",
        "# harness/medir.py\ndef medir():\n    return 1\n",
    )
    _escribir(
        raiz,
        "arnes-base/tests/test_medir.py",
        "# tests/test_medir.py\ndef test_medir():\n    assert True\n",
    )
    _escribir(raiz, "harness/portero.py", "# harness/portero.py\nX = 1\n")
    _escribir(raiz, "arnes-base-x/harness/ajeno.py", "# harness/ajeno.py\nY = 2\n")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "F-900 T1: toca el payload")
    return raiz


# --- R1 · la clave se lee y se valida ----------------------------------------


def test_f052_r1_sin_la_clave_el_servicio_no_incluye_nada(tmp_path: Path) -> None:
    (servicio,) = _uno(tmp_path)

    assert servicio.alcance_incluye == ()


def test_f052_r1_la_clave_se_lee(tmp_path: Path) -> None:
    (servicio,) = _uno(tmp_path, alcance_incluye=["harness"])

    assert servicio.alcance_incluye == ("harness",)


def test_f052_r1_lista_vacia_equivale_a_no_declararla(tmp_path: Path) -> None:
    (servicio,) = _uno(tmp_path, alcance_incluye=[])

    assert servicio.alcance_incluye == ()


@pytest.mark.parametrize("valor", ["tests", "docs", "Harness", "harnes", "", 3, None])
def test_f052_r1_un_valor_desconocido_falla_con_motivo(
    tmp_path: Path, valor: object
) -> None:
    with pytest.raises(ValueError) as error:
        _uno(tmp_path, alcance_incluye=[valor])

    mensaje = str(error.value)
    assert "'payload'" in mensaje
    assert "alcance_incluye" in mensaje
    assert repr(valor) in mensaje
    assert "harness" in mensaje  # dice qué SÍ vale


def test_f052_r1_un_valor_repetido_falla(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        _uno(tmp_path, alcance_incluye=["harness", "harness"])

    assert "alcance_incluye" in str(error.value)
    assert "repetid" in str(error.value)


@pytest.mark.parametrize("valor", ["harness", {"harness": True}, 1])
def test_f052_r1_la_clave_que_no_es_lista_falla(tmp_path: Path, valor: object) -> None:
    with pytest.raises(ValueError) as error:
        _uno(tmp_path, alcance_incluye=valor)

    assert "alcance_incluye" in str(error.value)
    assert "lista" in str(error.value)


@pytest.mark.parametrize(
    "clave",
    [
        "alcance_incluir",
        "alcance-incluye",
        "alcances_incluye",
        "alcance_incluyes",
        "Alcance_Incluye",
    ],
)
def test_f052_r1_la_clave_mal_escrita_falla_en_vez_de_ignorarse(
    tmp_path: Path, clave: str
) -> None:
    """Una clave mal escrita dejaría el `harness/` sin medir SIN AVISAR.

    Es exactamente el fallo silencioso que F-052 viene a cerrar, así que la
    declaración lo rechaza y sugiere la buena.
    """
    with pytest.raises(ValueError) as error:
        _uno(tmp_path, **{clave: ["harness"]})

    mensaje = str(error.value)
    assert "'payload'" in mensaje
    assert repr(clave) in mensaje
    assert "'alcance_incluye'" in mensaje


def test_f052_r1_las_claves_ajenas_siguen_ignorandose(tmp_path: Path) -> None:
    """Compatibilidad: hasta hoy una clave desconocida no rompía nada."""
    (servicio,) = _uno(tmp_path, notas="cualquier cosa", **{"$doc": "texto"})

    assert servicio.alcance_incluye == ()


def test_f052_r1_la_salida_shell_no_cambia_con_la_clave(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`init.sh` parsea `--shell` por posiciones: la clave nueva no viaja ahí."""
    _uno(tmp_path)
    servicios.main(["--shell", "--raiz", str(tmp_path)])
    sin_clave = capsys.readouterr().out

    _uno(tmp_path, alcance_incluye=["harness"])
    servicios.main(["--shell", "--raiz", str(tmp_path)])

    assert capsys.readouterr().out == sin_clave


def test_f052_r1_solo_se_incluye_lo_que_el_alcance_declarado_ya_admite() -> None:
    """Los incluibles son los excluidos que `--ficheros` ya deja nombrar.

    `tests`, `specs`, `progress` y `docs` no son producto en ningún proyecto:
    mutar un test no significa nada, lo declare quien lo declare.
    """
    assert set(DIRECTORIOS_INCLUIBLES) == set(DIRECTORIOS_EXCLUIDOS) - set(
        DIRECTORIOS_EXCLUIDOS_AL_DECLARAR
    )


# --- R1 · el filtro aplica la excepción solo bajo el servicio ----------------


def test_f052_r1_el_harness_del_servicio_con_la_clave_es_produccion() -> None:
    lineas = {"arnes-base/harness/alcance.py": {10}}

    assert filtrar_produccion(lineas, [TALLER]) == lineas


@pytest.mark.parametrize(
    "ruta",
    [
        "arnes-base/tests/test_alcance.py",
        "arnes-base/specs/F-001/plan.py",
        "arnes-base/docs/ejemplo.py",
        "arnes-base/progress/apunte.py",
        "arnes-base/tests/harness/ayuda.py",
        "arnes-base/harness/tests/test_x.py",
    ],
)
def test_f052_r1_bajo_el_servicio_lo_demas_sigue_excluido(ruta: str) -> None:
    assert filtrar_produccion({ruta: {1}}, [TALLER]) == {}


@pytest.mark.parametrize(
    "ruta",
    [
        "harness/alcance.py",  # el portero de la raíz
        "harness\\alcance.py",
        "arnes-base-x/harness/ajeno.py",  # solo comparte prefijo de TEXTO
        "otro/arnes-base/harness/ajeno.py",  # ni empieza por la ruta
    ],
)
def test_f052_r1_fuera_del_servicio_el_harness_sigue_excluido(ruta: str) -> None:
    assert filtrar_produccion({ruta: {1}}, [TALLER]) == {}


@pytest.mark.parametrize(
    "ruta",
    [
        "harness/mutacion.py",
        "services/api/harness/parche.py",
        "services/api/tests/test_algo.py",
    ],
)
def test_f052_r1_un_monorepo_sin_la_clave_no_cambia(ruta: str) -> None:
    sin_clave = [
        Servicio(nombre="api", ruta="services/api", lenguaje="python"),
        Servicio(nombre="web", ruta="services/web", lenguaje="otro"),
    ]

    assert filtrar_produccion({ruta: {1}}, sin_clave) == {}
    assert filtrar_produccion({ruta: {1}}) == {}


def test_f052_r1_la_clave_de_un_servicio_no_alcanza_a_otro() -> None:
    declarados = [
        TALLER,
        Servicio(nombre="api", ruta="services/api", lenguaje="python"),
    ]
    lineas = {
        "arnes-base/harness/alcance.py": {1},
        "services/api/harness/parche.py": {2},
        "services/api/entrada.py": {3},
    }

    assert filtrar_produccion(lineas, declarados) == {
        "arnes-base/harness/alcance.py": {1},
        "services/api/entrada.py": {3},
    }


# --- R2 · el árbol del taller, de punta a punta ------------------------------


def test_f052_r2_taller_con_la_clave_mide_el_harness_del_payload(tmp_path: Path) -> None:
    raiz = _taller(tmp_path, con_clave=True)

    alcance = alcance_de_feature("F-900", base="dev", rama=RAMA, raiz=str(raiz))

    assert alcance.ficheros() == ["arnes-base/harness/medir.py"]
    assert alcance.total_lineas() == 3


def test_f052_r2_taller_sin_la_clave_se_queda_sin_medir(tmp_path: Path) -> None:
    """El problema que motiva F-052: sin declararlo, el producto no se mide."""
    raiz = _taller(tmp_path, con_clave=False)

    alcance = alcance_de_feature("F-900", base="dev", rama=RAMA, raiz=str(raiz))

    assert alcance.lineas == {}


def test_f052_r2_los_servicios_inyectados_mandan_sobre_el_disco(tmp_path: Path) -> None:
    """Quien ya cargó la declaración la pasa: no se lee dos veces ni distinto."""
    raiz = _taller(tmp_path, con_clave=False)

    alcance = alcance_de_feature(
        "F-900", base="dev", rama=RAMA, raiz=str(raiz), servicios=[TALLER]
    )

    assert alcance.ficheros() == ["arnes-base/harness/medir.py"]


def test_f052_r2_la_puerta_de_cobertura_mide_el_harness_del_taller(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cobertura, "hay_coverage", lambda: True)
    raiz = _taller(tmp_path, con_clave=True)
    fuera = tmp_path
    features = {
        "features": [
            {
                "id": "F-900",
                "title": "Taller",
                "status": "in_progress",
                "sdd": False,
                "rigor": "estandar",
                "branch": RAMA,
            }
        ]
    }
    rigor = {
        "nivel_por_defecto": "estandar",
        "cobertura": {"umbral_lineas_cambiadas": 80},
        "niveles": {
            "estandar": {"fase_red": True, "cobertura": True, "mutacion": True}
        },
    }
    # El informe del servicio numera respecto a SU carpeta, como lo deja init.sh.
    (raiz / "arnes-base" / "coverage.json").write_text(
        json.dumps(
            {"files": {"harness/medir.py": {"executed_lines": [2], "missing_lines": [3]}}}
        ),
        encoding="utf-8",
    )
    (fuera / "features.json").write_text(json.dumps(features), encoding="utf-8")
    (fuera / "rigor.json").write_text(json.dumps(rigor), encoding="utf-8")

    codigo = cobertura.main(
        [
            "--base",
            "dev",
            "--config",
            str(fuera / "rigor.json"),
            "--features",
            str(fuera / "features.json"),
            # Sin informe de raíz: solo el del servicio, que se busca con el
            # MISMO nombre de fichero dentro de su carpeta.
            "--cov",
            str(fuera / "coverage.json"),
            "--raiz",
            str(raiz),
        ]
    )

    salida = capsys.readouterr()
    # 1 de 2 sentencias cubiertas: 50 % < 80 %. Lo que importa es que MIDE el
    # payload; antes salía «N/A: no cambia líneas Python de producción».
    assert codigo == 1, salida.out
    assert "50.0% de 2 líneas cambiadas" in salida.err


def test_f052_r2_la_puerta_de_cobertura_con_declaracion_rota_es_ko(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _taller(tmp_path, con_clave=True)
    _declarar(
        raiz,
        [
            {
                "nombre": "payload",
                "ruta": "arnes-base",
                "lenguaje": "python",
                "alcance_incluye": ["tests"],
            }
        ],
    )
    (tmp_path / "features.json").write_text(
        json.dumps(
            {"features": [{"id": "F-900", "status": "in_progress", "branch": RAMA}]}
        ),
        encoding="utf-8",
    )
    (tmp_path / "rigor.json").write_text(
        json.dumps(
            {
                "nivel_por_defecto": "estandar",
                "cobertura": {"umbral_lineas_cambiadas": 80},
                "niveles": {
                    "estandar": {"fase_red": True, "cobertura": True, "mutacion": True}
                },
            }
        ),
        encoding="utf-8",
    )

    codigo = cobertura.main(
        [
            "--base",
            "dev",
            "--config",
            str(tmp_path / "rigor.json"),
            "--features",
            str(tmp_path / "features.json"),
            "--raiz",
            str(raiz),
        ]
    )

    assert codigo == 1
    assert "alcance_incluye" in capsys.readouterr().err


def test_f052_r2_la_campana_pasa_la_declaracion_al_alcance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La mutación usa la MISMA declaración que ya cargó para elegir suites."""
    _uno(tmp_path, alcance_incluye=["harness"])
    recibidos: list[object] = []

    def _alcance_espia(*_args: object, **kwargs: object):
        recibidos.append(kwargs.get("servicios"))
        raise SystemExit("hasta aquí basta")

    monkeypatch.setattr("harness.mutacion.alcance_de_feature", _alcance_espia)

    assert mutacion_main(["--feature", "F-900", "--raiz", str(tmp_path)]) == 2
    (declarados,) = recibidos
    assert [s.alcance_incluye for s in declarados] == [("harness",)]
