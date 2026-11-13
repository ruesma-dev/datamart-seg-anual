# tests/test_servicios_dependencias.py
"""Los tres campos nuevos de `harness/servicios.json`.

`depende_de` (rutas del repositorio de las que depende la suite de un
servicio), `importa` (módulos cuya ruta real se vigila) y
`entradas_no_versionadas` (ficheros locales cuya huella entra en la clave de
la caché). Son opcionales: una declaración sin ellos se comporta exactamente
como antes (R1). Cada error de forma nombra el servicio, el campo y el valor.

Sin red ni git: cada test escribe su declaración en `tmp_path`.

Origen: albaranes F-072 (requisitos R1–R6), portado en la 1.7.16.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from harness import servicios
from harness.servicios import cargar_servicios


def _arbol(tmp_path: Path, *carpetas: str) -> Path:
    """Raíz temporal con las carpetas pedidas (las rutas tienen que existir)."""
    for carpeta in carpetas:
        (tmp_path / carpeta).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _declarar(raiz: Path, servicios_declarados: list[dict]) -> Path:
    fichero = raiz / "harness" / "servicios.json"
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(
        json.dumps({"servicios": servicios_declarados}), encoding="utf-8"
    )
    return fichero


def _uno(raiz: Path, **extra: object) -> list:
    """Declara `svc` (python, ruta `services/svc`) con los campos extra."""
    entrada = {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python"}
    entrada.update(extra)
    _declarar(raiz, [entrada])
    return cargar_servicios(raiz=str(raiz))


# --- R1: sin los campos nuevos, todo igual que hoy ----------------------------


def test_r1_sin_campos_nuevos_los_tres_quedan_vacios(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    (servicio,) = _uno(raiz)

    assert servicio.depende_de == ()
    assert servicio.importa == ()
    assert servicio.entradas_no_versionadas == ()


def test_r1_salida_shell_identica_a_la_de_hoy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _arbol(tmp_path, "services/svc", "infra")
    _declarar(
        raiz,
        [
            {"nombre": "svc", "ruta": "services/svc/", "lenguaje": "python"},
            {
                "nombre": "infra",
                "ruta": "infra",
                "lenguaje": "otro",
                "comando_tests": "npm test",
            },
        ],
    )

    codigo = servicios.main(["--shell", "--raiz", str(raiz)])

    interprete = Path(sys.executable).as_posix()
    assert codigo == 0
    assert capsys.readouterr().out == (
        f"svc|services/svc|python|{interprete}|\n" "infra|infra|otro||npm test\n"
    )


def test_r1_salida_validar_identica_a_la_de_hoy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _arbol(tmp_path, "services/svc", "infra")
    _declarar(
        raiz,
        [
            {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python"},
            {"nombre": "infra", "ruta": "infra", "lenguaje": "otro"},
        ],
    )

    codigo = servicios.main(["--validar", "--raiz", str(raiz)])

    salida = capsys.readouterr()
    assert codigo == 0
    assert salida.out == "    2 servicio(s): svc (python), infra (otro)\n"
    assert salida.err == ""


def test_r1_los_campos_nuevos_no_cambian_la_salida_shell(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--shell` sigue con cinco campos: el `read` de init.sh no se rompe."""
    raiz = _arbol(tmp_path, "services/svc", "services/comun")
    _uno(
        raiz,
        depende_de=["services/comun"],
        importa=["comun"],
        entradas_no_versionadas=["config/local.ini"],
    )

    servicios.main(["--shell", "--raiz", str(raiz)])

    assert capsys.readouterr().out == (
        f"svc|services/svc|python|{Path(sys.executable).as_posix()}|\n"
    )


# --- R2: depende_de normalizada y en orden -----------------------------------


def test_r2_depende_de_normalizada_y_en_el_orden_declarado(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc", "services/zeta", "services/alfa")
    (raiz / "pyproject.toml").write_text("", encoding="utf-8")

    (servicio,) = _uno(
        raiz, depende_de=["services\\zeta\\", "pyproject.toml", "services/alfa/"]
    )

    assert servicio.depende_de == ("services/zeta", "pyproject.toml", "services/alfa")


# --- R3: errores de depende_de -----------------------------------------------


@pytest.mark.parametrize(
    "valor",
    [
        "services/comun",  # no es lista
        {"ruta": "services/comun"},  # no es lista
        None,  # declarado a null: tampoco es lista
    ],
)
def test_r3_depende_de_que_no_es_lista_falla(tmp_path: Path, valor: object) -> None:
    raiz = _arbol(tmp_path, "services/svc", "services/comun")

    with pytest.raises(ValueError) as error:
        _uno(raiz, depende_de=valor)

    assert "svc" in str(error.value)
    assert "depende_de" in str(error.value)


@pytest.mark.parametrize(
    ("valor", "trozo"),
    [
        ("", "''"),
        ("   ", "'   '"),
        (7, "7"),
        (None, "None"),
        ("services/co|mun", "services/co|mun"),
        ("/services/comun", "/services/comun"),
        ("\\services\\comun", "services"),
        ("C:/repo/services/comun", "C:/repo/services/comun"),
        ("c:\\repo", "repo"),
        ("services/../services/comun", ".."),
        ("..", ".."),
        ("services/no-existe", "services/no-existe"),
    ],
)
def test_r3_elemento_invalido_de_depende_de_falla_nombrando_servicio_campo_y_valor(
    tmp_path: Path, valor: object, trozo: str
) -> None:
    raiz = _arbol(tmp_path, "services/svc", "services/comun")

    with pytest.raises(ValueError) as error:
        _uno(raiz, depende_de=["services/comun", valor])

    mensaje = str(error.value)
    assert "'svc'" in mensaje
    assert "depende_de" in mensaje
    assert trozo in mensaje


def test_r3_depende_de_repetida_tras_normalizar_falla(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc", "services/comun")

    with pytest.raises(ValueError) as error:
        _uno(raiz, depende_de=["services/comun", "services\\comun\\"])

    assert "depende_de" in str(error.value)
    assert "services/comun" in str(error.value)
    assert "repetid" in str(error.value)


def test_r3_depende_de_admite_un_fichero_existente(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")
    (raiz / "requirements.txt").write_text("", encoding="utf-8")

    (servicio,) = _uno(raiz, depende_de=["requirements.txt"])

    assert servicio.depende_de == ("requirements.txt",)


def test_r3_la_existencia_se_mira_bajo_la_raiz_y_no_en_el_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raiz = _arbol(tmp_path / "repo", "services/svc")
    otro = _arbol(tmp_path / "otro", "services/comun")
    monkeypatch.chdir(otro)

    with pytest.raises(ValueError, match="depende_de"):
        _uno(raiz, depende_de=["services/comun"])


# --- R4: importa ----------------------------------------------------------------


def test_r4_importa_se_carga_como_tupla_en_orden(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    (servicio,) = _uno(raiz, importa=["comun", "pkg.sub", "_privado2"])

    assert servicio.importa == ("comun", "pkg.sub", "_privado2")


@pytest.mark.parametrize(
    "nombre",
    ["", "2pkg", "pkg-guion", "pkg.", ".pkg", "pkg..sub", "pkg sub", "pkg/sub", 3, None],
)
def test_r4_nombre_de_modulo_invalido_falla(tmp_path: Path, nombre: object) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    with pytest.raises(ValueError) as error:
        _uno(raiz, importa=["comun", nombre])

    assert "'svc'" in str(error.value)
    assert "importa" in str(error.value)
    assert repr(nombre) in str(error.value)


def test_r4_importa_que_no_es_lista_falla(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    with pytest.raises(ValueError, match="importa"):
        _uno(raiz, importa="comun")


def test_r4_importa_repetido_falla(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    with pytest.raises(ValueError) as error:
        _uno(raiz, importa=["comun", "comun"])

    assert "importa" in str(error.value)
    assert "comun" in str(error.value)
    assert "repetid" in str(error.value)


def test_r4_importa_en_un_servicio_que_no_es_python_falla(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "web")
    _declarar(
        raiz,
        [{"nombre": "web", "ruta": "web", "lenguaje": "otro", "importa": ["pkg"]}],
    )

    with pytest.raises(ValueError) as error:
        cargar_servicios(raiz=str(raiz))

    assert "'web'" in str(error.value)
    assert "importa" in str(error.value)
    assert "python" in str(error.value)


# --- R5: entradas_no_versionadas ---------------------------------------------


def test_r5_entradas_normalizadas_existan_o_no(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    (servicio,) = _uno(
        raiz, entradas_no_versionadas=["config\\local.ini", "services/svc/datos/"]
    )

    assert servicio.entradas_no_versionadas == (
        "config/local.ini",
        "services/svc/datos",
    )


def test_r5_entradas_que_no_son_lista_fallan(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    with pytest.raises(ValueError, match="entradas_no_versionadas"):
        _uno(raiz, entradas_no_versionadas=".env.local")


@pytest.mark.parametrize(
    "valor", ["", 5, "a|b", "/etc/passwd", "D:/secretos", "../fuera.ini", "x/../y"]
)
def test_r5_entrada_de_forma_invalida_falla(tmp_path: Path, valor: object) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    with pytest.raises(ValueError) as error:
        _uno(raiz, entradas_no_versionadas=[valor])

    assert "'svc'" in str(error.value)
    assert "entradas_no_versionadas" in str(error.value)


def test_r5_entrada_repetida_falla(tmp_path: Path) -> None:
    raiz = _arbol(tmp_path, "services/svc")

    with pytest.raises(ValueError, match="repetid"):
        _uno(raiz, entradas_no_versionadas=["a.ini", "a.ini/"])


# --- R6: --validar falla con código 1 y el motivo en stderr -------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"depende_de": ["services/no-existe"]},
        {"importa": ["no-valido"]},
        {"entradas_no_versionadas": ["../fuera"]},
    ],
)
def test_r6_validar_sale_con_1_y_motivo_en_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: dict
) -> None:
    raiz = _arbol(tmp_path, "services/svc")
    entrada = {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python"}
    entrada.update(extra)
    _declarar(raiz, [entrada])

    codigo = servicios.main(["--validar", "--raiz", str(raiz)])

    salida = capsys.readouterr()
    assert codigo == 1
    assert salida.out == ""
    assert "svc" in salida.err
    assert next(iter(extra)) in salida.err
