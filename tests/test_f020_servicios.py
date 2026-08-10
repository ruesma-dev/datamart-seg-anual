# tests/test_f020_servicios.py
"""F-020 · Declaración de servicios de un monorepo (R1 a R5, y la salida de R6).

Ningún test de este fichero toca red, base de datos ni crea un venv de verdad:
los monorepos son directorios y ficheros creados en `tmp_path`, y un «venv» es
un fichero vacío en el sitio donde iría el intérprete.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from harness.servicios import (
    LENGUAJES,
    RUTA_SERVICIOS,
    Servicio,
    cargar_servicios,
    interprete,
    linea_shell,
    main,
    servicio_de_ruta,
    tiene_tests,
)

DECLARACION_VALIDA = {
    "$doc": "Ejemplo de monorepo con dos servicios.",
    "servicios": [
        {
            "nombre": "email",
            "ruta": "services/email",
            "lenguaje": "python",
            "venv": "services/email/.venv",
        },
        {
            "nombre": "web",
            "ruta": "services/web",
            "lenguaje": "otro",
            "comando_tests": "npm test --silent",
        },
    ],
}


# --- Utilidades de fixture --------------------------------------------------


def monorepo(raiz: Path, declaracion: dict | str, rutas: tuple[str, ...] = ()) -> Path:
    """Crea en `raiz` los directorios de los servicios y la declaración."""
    for ruta in rutas:
        (raiz / ruta).mkdir(parents=True, exist_ok=True)
    fichero = raiz / RUTA_SERVICIOS
    fichero.parent.mkdir(parents=True, exist_ok=True)
    texto = declaracion if isinstance(declaracion, str) else json.dumps(declaracion)
    fichero.write_text(texto, encoding="utf-8")
    return fichero


def monorepo_valido(raiz: Path) -> Path:
    return monorepo(raiz, DECLARACION_VALIDA, ("services/email", "services/web"))


def falso_venv(raiz: Path, ruta: str, relativo: str) -> Path:
    """Crea el intérprete de un venv de mentira (un fichero vacío basta)."""
    destino = raiz / ruta / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("", encoding="utf-8")
    return destino


# --- R1: carga de una declaración válida ------------------------------------


def test_f020_r1_carga_servicios_validos(tmp_path: Path) -> None:
    monorepo_valido(tmp_path)

    servicios = cargar_servicios(raiz=str(tmp_path))

    assert [s.nombre for s in servicios] == ["email", "web"]
    email, web = servicios
    assert email.ruta == "services/email"
    assert email.lenguaje == "python"
    assert email.venv == "services/email/.venv"
    assert email.comando_tests is None
    assert web.lenguaje == "otro"
    assert web.comando_tests == "npm test --silent"
    assert web.venv is None


def test_f020_r1_campos_opcionales_ausentes_valen(tmp_path: Path) -> None:
    monorepo(
        tmp_path,
        {"servicios": [{"nombre": "api", "ruta": "services/api", "lenguaje": "python"}]},
        ("services/api",),
    )

    (servicio,) = cargar_servicios(raiz=str(tmp_path))

    assert servicio.venv is None
    assert servicio.comando_tests is None
    assert set(LENGUAJES) == {"python", "otro"}


def test_f020_r1_las_rutas_se_normalizan_a_barras(tmp_path: Path) -> None:
    monorepo(
        tmp_path,
        {"servicios": [{"nombre": "api", "ruta": "services\\api\\", "lenguaje": "otro"}]},
        ("services/api",),
    )

    (servicio,) = cargar_servicios(raiz=str(tmp_path))

    assert servicio.ruta == "services/api"


def test_f020_r1_la_declaracion_se_busca_bajo_la_raiz(tmp_path: Path) -> None:
    """Con `--raiz` apuntando a otro árbol (worktree), se lee el de ese árbol."""
    monorepo_valido(tmp_path)

    assert len(cargar_servicios(raiz=str(tmp_path))) == 2
    # Y una ruta absoluta se respeta tal cual.
    assert len(cargar_servicios(ruta=tmp_path / RUTA_SERVICIOS, raiz=str(tmp_path))) == 2


# --- R2: sin declaración, mono-proyecto -------------------------------------


def test_f020_r2_sin_declaracion_lista_vacia(tmp_path: Path) -> None:
    assert cargar_servicios(raiz=str(tmp_path)) == []


def test_f020_r2_este_repositorio_no_declara_servicios() -> None:
    """El datamart es mono-proyecto: no configura nada y sigue igual."""
    raiz = Path(__file__).resolve().parents[1]

    assert not (raiz / RUTA_SERVICIOS).exists()
    assert cargar_servicios(raiz=str(raiz)) == []


# --- R3: una declaración rota no degrada en silencio ------------------------


def test_f020_r3_json_roto_error_explicito(tmp_path: Path) -> None:
    monorepo(tmp_path, "{esto no es json")

    with pytest.raises(ValueError, match="no es JSON válido"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_esquema_de_la_raiz_invalido(tmp_path: Path) -> None:
    monorepo(tmp_path, {"servicios": {"email": "services/email"}})

    with pytest.raises(ValueError, match="'servicios'"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_entrada_que_no_es_objeto(tmp_path: Path) -> None:
    monorepo(tmp_path, {"servicios": ["services/email"]})

    with pytest.raises(ValueError, match="objeto"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_nombre_o_ruta_vacios(tmp_path: Path) -> None:
    monorepo(tmp_path, {"servicios": [{"nombre": "", "ruta": "x", "lenguaje": "otro"}]})

    with pytest.raises(ValueError, match="nombre"):
        cargar_servicios(raiz=str(tmp_path))

    monorepo(tmp_path, {"servicios": [{"nombre": "x", "ruta": "", "lenguaje": "otro"}]})

    with pytest.raises(ValueError, match="ruta"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_nombres_duplicados_error(tmp_path: Path) -> None:
    monorepo(
        tmp_path,
        {
            "servicios": [
                {"nombre": "api", "ruta": "services/api", "lenguaje": "otro"},
                {"nombre": "api", "ruta": "services/web", "lenguaje": "otro"},
            ]
        },
        ("services/api", "services/web"),
    )

    with pytest.raises(ValueError, match="nombre duplicado"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_rutas_duplicadas_o_solapadas_error(tmp_path: Path) -> None:
    duplicadas = {
        "servicios": [
            {"nombre": "api", "ruta": "services/api", "lenguaje": "otro"},
            {"nombre": "otra", "ruta": "services/api", "lenguaje": "otro"},
        ]
    }
    monorepo(tmp_path, duplicadas, ("services/api",))
    with pytest.raises(ValueError, match="ruta duplicada"):
        cargar_servicios(raiz=str(tmp_path))

    solapadas = {
        "servicios": [
            {"nombre": "todo", "ruta": "services", "lenguaje": "otro"},
            {"nombre": "api", "ruta": "services/api", "lenguaje": "otro"},
        ]
    }
    monorepo(tmp_path, solapadas, ("services/api",))
    with pytest.raises(ValueError, match="solapa"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_lenguaje_desconocido_error(tmp_path: Path) -> None:
    monorepo(
        tmp_path,
        {"servicios": [{"nombre": "api", "ruta": "services/api", "lenguaje": "rust"}]},
        ("services/api",),
    )

    with pytest.raises(ValueError, match="lenguaje"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_ruta_inexistente_error(tmp_path: Path) -> None:
    monorepo(
        tmp_path,
        {"servicios": [{"nombre": "api", "ruta": "services/api", "lenguaje": "otro"}]},
    )

    with pytest.raises(ValueError, match="no existe"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_separador_prohibido_en_los_campos(tmp_path: Path) -> None:
    """`|` separa los campos de `--shell`: no puede aparecer dentro de uno."""
    monorepo(
        tmp_path,
        {
            "servicios": [
                {
                    "nombre": "api",
                    "ruta": "services/api",
                    "lenguaje": "otro",
                    "comando_tests": "npm test | tee salida.txt",
                }
            ]
        },
        ("services/api",),
    )

    with pytest.raises(ValueError, match=r"\|"):
        cargar_servicios(raiz=str(tmp_path))


def test_f020_r3_validar_por_cli_devuelve_1_y_explica(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monorepo(tmp_path, "{roto")

    codigo = main(["--validar", "--raiz", str(tmp_path)])

    assert codigo == 1
    assert "no es JSON válido" in capsys.readouterr().err


def test_f020_r3_validar_por_cli_devuelve_0_con_declaracion_buena(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monorepo_valido(tmp_path)
    falso_venv(tmp_path, "services/email/.venv", "bin/python")

    codigo = main(["--validar", "--raiz", str(tmp_path)])

    assert codigo == 0
    assert "email" in capsys.readouterr().out


# --- R4: a qué servicio pertenece una ruta ----------------------------------


SERVICIOS_ANIDADOS = [
    Servicio(nombre="todo", ruta="services", lenguaje="python"),
    Servicio(nombre="email", ruta="services/email", lenguaje="python"),
]


def test_f020_r4_resolucion_por_prefijo_mas_largo() -> None:
    elegido = servicio_de_ruta("services/email/app/flujo.py", SERVICIOS_ANIDADOS)

    assert elegido is not None
    assert elegido.nombre == "email"
    # Separadores de Windows: misma respuesta.
    otro = servicio_de_ruta("services\\email\\app\\flujo.py", SERVICIOS_ANIDADOS)
    assert otro is not None and otro.nombre == "email"
    # Lo que cae fuera del más específico pertenece al que sí lo contiene.
    generico = servicio_de_ruta("services/otro/x.py", SERVICIOS_ANIDADOS)
    assert generico is not None and generico.nombre == "todo"


def test_f020_r4_fuera_de_servicios_devuelve_none() -> None:
    assert servicio_de_ruta("harness/alcance.py", SERVICIOS_ANIDADOS) is None
    # Un prefijo textual no basta: tiene que ser un segmento de ruta completo.
    assert servicio_de_ruta("services-viejos/x.py", SERVICIOS_ANIDADOS) is None
    assert servicio_de_ruta("harness/alcance.py", []) is None


# --- R5: el intérprete de cada servicio -------------------------------------


def test_f020_r5_interprete_del_venv_windows_y_posix(tmp_path: Path) -> None:
    windows = Servicio(nombre="a", ruta="a", lenguaje="python", venv="a/.venv")
    esperado = falso_venv(tmp_path, "a/.venv", "Scripts/python.exe")
    assert interprete(windows, raiz=str(tmp_path)) == esperado.resolve().as_posix()

    posix = Servicio(nombre="b", ruta="b", lenguaje="python", venv="b/.venv")
    esperado = falso_venv(tmp_path, "b/.venv", "bin/python")
    assert interprete(posix, raiz=str(tmp_path)) == esperado.resolve().as_posix()


def test_f020_r5_venv_declarado_inexistente_error(tmp_path: Path) -> None:
    servicio = Servicio(nombre="a", ruta="a", lenguaje="python", venv="a/.venv")

    with pytest.raises(ValueError) as error:
        interprete(servicio, raiz=str(tmp_path))

    # El error nombra al servicio y al venv, y deja claro que NO hay fallback.
    assert "a/.venv" in str(error.value)
    assert "'a'" in str(error.value)


def test_f020_r5_sin_venv_interprete_del_arnes(tmp_path: Path) -> None:
    servicio = Servicio(nombre="a", ruta="a", lenguaje="python")

    assert interprete(servicio, raiz=str(tmp_path)) == sys.executable


# --- R6: salida parseable por shell y helper de tests -----------------------


def test_f020_r6_salida_shell_parseable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monorepo_valido(tmp_path)
    falso_venv(tmp_path, "services/email/.venv", "Scripts/python.exe")

    codigo = main(["--shell", "--raiz", str(tmp_path)])

    assert codigo == 0
    lineas = capsys.readouterr().out.strip().splitlines()
    assert len(lineas) == 2
    campos = [linea.split("|") for linea in lineas]
    assert all(len(fila) == 5 for fila in campos)

    email, web = campos
    assert email[0:3] == ["email", "services/email", "python"]
    assert email[3].endswith(".venv/Scripts/python.exe")
    assert "\\" not in email[3], "Git Bash no ejecuta rutas con contrabarras"
    assert email[4] == ""
    assert web[0:3] == ["web", "services/web", "otro"]
    assert web[3] == "", "un servicio no Python no tiene intérprete que resolver"
    assert web[4] == "npm test --silent"


def test_f020_r6_shell_falla_si_el_venv_no_existe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monorepo_valido(tmp_path)

    codigo = main(["--shell", "--raiz", str(tmp_path)])

    assert codigo == 1
    assert "services/email/.venv" in capsys.readouterr().err


def test_f020_r6_linea_shell_de_un_servicio_sin_venv(tmp_path: Path) -> None:
    servicio = Servicio(nombre="api", ruta="services/api", lenguaje="python")

    linea = linea_shell(servicio, raiz=str(tmp_path))

    assert linea.split("|")[3] == Path(sys.executable).as_posix()


# --- R7: helper que decide si un servicio tiene tests -----------------------


def test_f020_r7_helper_tiene_tests(tmp_path: Path) -> None:
    con = Servicio(nombre="a", ruta="services/a", lenguaje="python")
    sin = Servicio(nombre="b", ruta="services/b", lenguaje="python")
    (tmp_path / "services/a/tests").mkdir(parents=True)
    (tmp_path / "services/b").mkdir(parents=True)

    assert tiene_tests(con, raiz=str(tmp_path)) is True
    assert tiene_tests(sin, raiz=str(tmp_path)) is False
