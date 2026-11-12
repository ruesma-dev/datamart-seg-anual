# tests/test_cache_suites_init_sh.py
"""El pegamento de `harness/init.sh` §7 bis con la caché.

Dos capas. La primera es el contrato estático del texto: la sección decide la
caché solo a través de `python -m harness.cache_suites`, con `</dev/null`, y ya
no compone la clave en bash. La segunda ejecuta la sección DE VERDAD con bash,
extraída del propio `init.sh`, contra un intérprete falso que responde lo que
cada caso necesita: así se comprueba el comportamiento (qué imprime, qué guarda,
que no se come la entrada del bucle) y no solo que unas palabras estén escritas.

Origen: albaranes F-072 (requisitos R23–R27), portado en la 1.7.16.
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

from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
INIT_SH = RAIZ / "harness" / "init.sh"


def _texto() -> str:
    return INIT_SH.read_text(encoding="utf-8")


def _seccion_7_bis(texto: str | None = None) -> str:
    lineas = (_texto() if texto is None else texto).splitlines()
    inicio = next(i for i, linea in enumerate(lineas) if linea.startswith("# --- 7 bis"))
    fin = next(i for i, linea in enumerate(lineas) if linea.startswith("# --- 7b"))
    return "\n".join(lineas[inicio:fin]) + "\n"


def _cabecera() -> str:
    texto = _texto()
    return texto[: texto.index("set -u")]


# --- Contrato estático -----------------------------------------------------------


def test_r23_la_seccion_llama_al_modulo_de_cache() -> None:
    llamadas = [linea for linea in _seccion_7_bis().splitlines()
                if "-m harness.cache_suites" in linea and not linea.lstrip().startswith("#")]

    assert llamadas, "la §7 bis no llama a python -m harness.cache_suites"
    assert any('--servicio "$NOMBRE"' in linea for linea in llamadas)


def test_r23_la_clave_ya_no_se_compone_en_bash() -> None:
    texto = _texto()

    assert 'git rev-parse "HEAD:$RUTA"' not in texto
    assert "HASH_SRV" not in texto
    assert "SUCIO_SRV" not in texto


def test_r27_la_llamada_no_consume_la_entrada_del_bucle() -> None:
    llamada = next(linea for linea in _seccion_7_bis().splitlines()
                   if "-m harness.cache_suites" in linea and "$(" in linea)

    assert "</dev/null" in llamada


def test_r24_solo_se_guarda_con_clave_no_vacia() -> None:
    seccion = _seccion_7_bis()
    escrituras = [linea for linea in seccion.splitlines() if "suite_${NOMBRE}.ok" in linea
                  and ">" in linea]

    assert len(escrituras) == 1
    assert '[ -n "$CLAVE_SRV" ]' in escrituras[0]
    assert '"$CLAVE_SRV"' in escrituras[0].split("printf", 1)[1]


def test_r24_mensaje_de_cache_con_la_fecha_del_verde() -> None:
    assert ("caché: ni el servicio ni sus dependencias han cambiado desde el verde del "
            "$FECHA_VERDE") in _seccion_7_bis()


def test_r25_sin_cache_en_la_cabecera_y_aviso_unico_fuera_del_bucle() -> None:
    seccion = _seccion_7_bis()
    avisos = [i for i, linea in enumerate(seccion.splitlines())
              if "ARNES_SIN_CACHE=1:" in linea]
    bucle = next(i for i, linea in enumerate(seccion.splitlines())
                 if linea.lstrip().startswith("while IFS='|' read -r NOMBRE"))

    assert 'SIN_CACHE="${ARNES_SIN_CACHE:-0}"' in _cabecera()
    assert len(avisos) == 1
    assert avisos[0] < bucle
    assert "--sin-cache" in seccion


_INSTRUCCION_SIEMPRE = (
    "la §7 bis de harness/init.sh no reconoce las líneas SIEMPRE| de F-028, así "
    "que `ejecutar_siempre` no se ejecuta con la caché válida: al actualizar el "
    "arnés, acepta ese bloque del diff de harness/init.sh"
)


def _motivo_init_sh_viejo(texto: str) -> str | None:
    """Por qué este init.sh es de antes de F-028, con el mensaje del rojo de R23; o None.

    Un init.sh irreconocible (sin las marcas de la §7 bis) también es viejo:
    nunca rompe la recogida de la suite.
    """
    try:
        seccion = _seccion_7_bis(texto)
    except StopIteration:
        return _INSTRUCCION_SIEMPRE
    return None if "SIEMPRE)" in seccion else _INSTRUCCION_SIEMPRE


#: Patrón de F-055. Con el init.sh que un proyecto conservó al actualizar, los
#: tests de comportamiento de F-028 en la §7 bis fallarían sin explicar nada: se
#: saltan con la instrucción, y el test de abajo queda como el único rojo.
_MOTIVO_INIT_SH_VIEJO = _motivo_init_sh_viejo(_texto())
init_sh_de_f028 = pytest.mark.skipif(
    _MOTIVO_INIT_SH_VIEJO is not None, reason=_MOTIVO_INIT_SH_VIEJO or "")


def test_f028_r23_el_init_sh_instalado_reconoce_las_lineas_siempre() -> None:
    """En un proyecto que conservó su `init.sh` al actualizar, el rojo dice qué hacer."""
    motivo = _motivo_init_sh_viejo(_texto())

    assert motivo is None, motivo


def test_r26_rama_de_fallo_ejecuta_sin_guardar() -> None:
    assert "no se pudo decidir la caché" in _seccion_7_bis()


# --- Comportamiento: la sección ejecutada con bash ----------------------------------


def _bash() -> str | None:
    ruta = shutil.which("bash")
    if ruta is None:
        return None
    if os.name == "nt" and "system32" in ruta.lower():
        return None  # el bash de WSL no ve las rutas de Windows igual
    return ruta


BASH = _bash()

_PY_FALSO = """#!/bin/bash
# Intérprete falso: responde como harness.servicios y harness.cache_suites.
case "$1 $2" in
  "-m harness.servicios")
    if [ "$3" = "--shell" ]; then cat "$DIR_CASO/servicios.txt"; fi
    exit 0 ;;
  "-m harness.cache_suites")
    echo "$*" >> "$DIR_CASO/llamadas.txt"
    cat > /dev/null   # se come la entrada estándar si se la dejan
    shift 3
    cat "$DIR_CASO/respuesta_$1.txt"
    exit "$(cat "$DIR_CASO/codigo_$1.txt" 2>/dev/null || echo 0)" ;;
  "-c import coverage") exit "$(cat "$DIR_CASO/coverage.txt" 2>/dev/null || echo 1)" ;;
  "-m coverage")
    echo "$(basename "$PWD") $*" >> "$DIR_CASO/coverage_llamadas.txt"
    exit 0 ;;
  "-m pytest")
    nombre=$(basename "$PWD")
    echo "$nombre" >> "$DIR_CASO/suites.txt"
    echo "$(basename "$0") $nombre $*" >> "$DIR_CASO/pytest_args.txt"
    # La ejecución de `ejecutar_siempre` (F-028) se come la entrada si se la dejan.
    case "$*" in *no:cacheprovider*) cat > /dev/null ;; esac
    # Como pytest de verdad: una ruta acabada en `\\r` no existe y sale con 4.
    case "$*" in *$'\\r'*) exit 4 ;; esac
    exit "$(cat "$DIR_CASO/pytest_$nombre.txt" 2>/dev/null || echo 0)" ;;
esac
exit 2
"""


def _caso(tmp_path: Path, respuestas: dict[str, tuple[str, int]],
          sin_cache: str = "0", pytest_rojo: tuple[str, ...] = (),
          saltar: str = "0", con_coverage: bool = False,
          interprete_propio: bool = False,
          caches: dict[str, str] | None = None,
          fin_de_linea: str = "\n") -> tuple[str, Path]:
    """Ejecuta la §7 bis real con los servicios pedidos y devuelve (salida, dir del caso).

    F-028 añade: `saltar` (portero ligero), `con_coverage` (el falso dice que
    hay coverage), `interprete_propio` (los servicios corren con `py_servicio`,
    otro fichero que el `PY` del portero) y `caches` (verdes ya guardados).
    `fin_de_linea="\\r\\n"` responde como Python en Windows (review de F-028,
    pasada 1). La salida vuelve sin traducir los saltos: un `\\r` se ve.
    """
    caso = tmp_path / "caso"
    (caso / "harness").mkdir(parents=True)
    (caso / "harness" / "servicios.json").write_text("{}", encoding="utf-8")
    falso = caso / "py_falso"
    falso.write_text(_PY_FALSO, encoding="utf-8", newline="\n")
    falso.chmod(0o755)
    py = falso.as_posix()
    py_servicio = py
    if interprete_propio:
        propio = caso / "py_servicio"
        propio.write_text(_PY_FALSO, encoding="utf-8", newline="\n")
        propio.chmod(0o755)
        py_servicio = propio.as_posix()
    if con_coverage:
        (caso / "coverage.txt").write_text("0", encoding="utf-8")
    for nombre, contenido in (caches or {}).items():
        (caso / ".arnes_cache").mkdir(exist_ok=True)
        (caso / ".arnes_cache" / f"suite_{nombre}.ok").write_text(contenido, encoding="utf-8")
    lineas = []
    for nombre, (respuesta, codigo) in respuestas.items():
        (caso / f"svc_{nombre}" / "tests").mkdir(parents=True)
        lineas.append(f"{nombre}|svc_{nombre}|python|{py_servicio}|")
        (caso / f"respuesta_{nombre}.txt").write_text(respuesta, encoding="utf-8",
                                                     newline=fin_de_linea)
        (caso / f"codigo_{nombre}.txt").write_text(str(codigo), encoding="utf-8")
    for nombre in pytest_rojo:
        (caso / f"pytest_svc_{nombre}.txt").write_text("1", encoding="utf-8")
    (caso / "servicios.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8",
                                        newline="\n")
    return _ejecutar_seccion(caso, py, saltar=saltar, sin_cache=sin_cache), caso


def _ejecutar_seccion(caso: Path, py: str, saltar: str = "0", sin_cache: str = "0",
                      limite_s: int = 60) -> str:
    """La §7 bis real con bash desde `caso`: stdout + stderr sin traducir saltos."""
    guion = caso / "seccion.sh"
    guion.write_text(
        f"set -u\nFALLOS=0\nSALTAR_SUITES={saltar}\n"
        f"SIN_CACHE={sin_cache}\nPY={py}\n"
        'ok()   { printf "[OK] %s\\n" "$1"; }\n'
        'warn() { printf "[AVISO] %s\\n" "$1"; }\n'
        'ko()   { printf "[KO] %s\\n" "$1"; FALLOS=$((FALLOS + 1)); }\n'
        + _seccion_7_bis() + 'echo "FALLOS=$FALLOS"\n',
        encoding="utf-8", newline="\n",
    )
    proceso = subprocess.run(
        [BASH, guion.name], cwd=caso, capture_output=True, timeout=limite_s, check=False,
        env={**os.environ, "DIR_CASO": caso.as_posix()},
    )
    return (proceso.stdout + proceso.stderr).decode("utf-8")


def _leer(caso: Path, fichero: str) -> str:
    ruta = caso / fichero
    return ruta.read_text(encoding="utf-8") if ruta.exists() else ""


necesita_bash = pytest.mark.skipif(BASH is None, reason="sin bash utilizable")


#: Corrida normal: cinco servicios, uno por caso. El falso se come stdin en cada
#: llamada: sin `</dev/null`, el bucle perdería todos los servicios tras `a`.
NORMAL = {
    "a": ("AVISO|importa `x` desde /otro/arbol\nEJECUTAR|clave-a\n", 0),
    "b": ("SERVIR|2026-10-15 09:30\n", 0),
    "c": ("EJECUTAR|\n", 0),
    "d": ("EJECUTAR|clave-d\n", 0),
    "e": ("SERVIR|2026-10-15 09:30\n", 1),
}


@pytest.fixture(scope="module")
def normal(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    return _caso(tmp_path_factory.mktemp("cache_normal"), NORMAL, pytest_rojo=("d",))


@pytest.fixture(scope="module")
def sin_cache(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    return _caso(tmp_path_factory.mktemp("cache_sin_cache"),
                 {"a": ("EJECUTAR|k1\n", 0), "b": ("EJECUTAR|k2\n", 0)}, sin_cache="1")


@necesita_bash
def test_r24_aviso_y_guardado_con_clave(normal: tuple[str, Path]) -> None:
    salida, caso = normal

    assert "[AVISO] servicio a (svc_a): importa `x` desde /otro/arbol" in salida
    assert "[OK] servicio a (svc_a): pytest en verde" in salida
    assert _leer(caso, ".arnes_cache/suite_a.ok") == "clave-a"


@necesita_bash
def test_r24_servir_con_la_fecha_y_sin_ejecutar(normal: tuple[str, Path]) -> None:
    salida, caso = normal

    assert ("[OK] servicio b (svc_b): pytest en verde (caché: ni el servicio ni sus "
            "dependencias han cambiado desde el verde del 2026-10-15 09:30)") in salida
    assert "svc_b" not in _leer(caso, "suites.txt").split()
    assert not (caso / ".arnes_cache" / "suite_b.ok").exists()


@necesita_bash
def test_r24_sin_clave_no_se_guarda(normal: tuple[str, Path]) -> None:
    salida, caso = normal

    assert "[OK] servicio c (svc_c): pytest en verde" in salida
    assert not (caso / ".arnes_cache" / "suite_c.ok").exists()


@necesita_bash
def test_r24_suite_en_rojo_no_se_guarda(normal: tuple[str, Path]) -> None:
    salida, caso = normal

    assert "[KO] servicio d (svc_d): pytest en rojo" in salida
    assert "FALLOS=1" in salida
    assert not (caso / ".arnes_cache" / "suite_d.ok").exists()


@necesita_bash
def test_r26_fallo_del_modulo_avisa_ejecuta_y_no_guarda(
    normal: tuple[str, Path],
) -> None:
    salida, caso = normal

    assert re.search(r"\[AVISO\] servicio e \(svc_e\): no se pudo decidir la caché", salida)
    assert "servicio e (svc_e): pytest en verde (caché" not in salida
    assert "svc_e" in _leer(caso, "suites.txt").split()
    assert not (caso / ".arnes_cache" / "suite_e.ok").exists()


@necesita_bash
def test_r27_todos_los_servicios_se_procesan(normal: tuple[str, Path]) -> None:
    salida, caso = normal

    assert len(_leer(caso, "llamadas.txt").splitlines()) == 5
    assert _leer(caso, "suites.txt").split() == ["svc_a", "svc_c", "svc_d", "svc_e"]
    assert "ARNES_SIN_CACHE" not in salida
    assert "--sin-cache" not in _leer(caso, "llamadas.txt")


@necesita_bash
def test_r25_sin_cache_avisa_una_vez_y_pasa_la_opcion(
    sin_cache: tuple[str, Path],
) -> None:
    salida, caso = sin_cache

    assert salida.count("ARNES_SIN_CACHE=1") == 1
    llamadas = _leer(caso, "llamadas.txt").splitlines()
    assert len(llamadas) == 2
    assert all(linea.endswith("--sin-cache") for linea in llamadas)
    assert _leer(caso, ".arnes_cache/suite_b.ok") == "k2"


# === F-028: `ejecutar_siempre` con la caché válida (R12–R15, R21, R23) ===============

FECHA = "2026-10-15 09:30"
LINEA_CACHE_1_7_16 = ("[OK] servicio {n} (svc_{n}): pytest en verde (caché: ni el servicio "
                      "ni sus dependencias han cambiado desde el verde del " + FECHA + ")")

#: `s` sirve con dos rutas que salen en verde; `v`, con una que sale en rojo y un
#: verde ya guardado; `b` sirve sin `ejecutar_siempre`. `s` va primero: si su
#: pytest se come la entrada del bucle, `v` y `b` no llegan a procesarse.
SIEMPRE = {
    "s": (f"SIEMPRE|tests/test_barrido.py\nSIEMPRE|tests/barridos\nSERVIR|{FECHA}\n", 0),
    "v": (f"AVISO|un aviso\nSIEMPRE|tests/test_rojo.py\nSERVIR|{FECHA}\n", 0),
    "b": (f"SERVIR|{FECHA}\n", 0),
}


@pytest.fixture(scope="module")
def siempre(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    return _caso(tmp_path_factory.mktemp("cache_siempre"), SIEMPRE, pytest_rojo=("v",),
                 interprete_propio=True, caches={"v": "clave-del-verde"})


def _args_pytest(caso: Path, servicio: str) -> list[str]:
    return [linea for linea in _leer(caso, "pytest_args.txt").splitlines()
            if linea.split()[1] == f"svc_{servicio}"]


@necesita_bash
@init_sh_de_f028
def test_f028_r12_ejecuta_las_rutas_con_el_interprete_del_servicio_desde_su_carpeta(
    siempre: tuple[str, Path],
) -> None:
    _, caso = siempre

    assert _args_pytest(caso, "s") == [
        ("py_servicio svc_s -m pytest -q --tb=short -p no:cacheprovider "
         "tests/test_barrido.py tests/barridos")
    ]
    assert _args_pytest(caso, "v") == [
        "py_servicio svc_v -m pytest -q --tb=short -p no:cacheprovider tests/test_rojo.py"
    ]


@necesita_bash
@init_sh_de_f028
def test_f028_r12_la_ejecucion_no_se_come_la_entrada_del_bucle(
    siempre: tuple[str, Path],
) -> None:
    salida, caso = siempre

    assert len(_leer(caso, "llamadas.txt").splitlines()) == 3
    assert LINEA_CACHE_1_7_16.format(n="b") in salida.splitlines()


@necesita_bash
@init_sh_de_f028
def test_f028_r12_sin_coverage_aunque_el_interprete_lo_tenga(tmp_path: Path) -> None:
    salida, caso = _caso(tmp_path, {"s": SIEMPRE["s"]}, con_coverage=True)

    assert _leer(caso, "coverage_llamadas.txt") == ""
    assert len(_args_pytest(caso, "s")) == 1
    assert "FALLOS=0" in salida


@necesita_bash
@init_sh_de_f028
def test_f028_r13_rojo_en_ejecutar_siempre_es_ko_aunque_la_cache_valga(
    siempre: tuple[str, Path],
) -> None:
    salida, caso = siempre

    assert (f"[KO] servicio v (svc_v): ejecutar_siempre en rojo con la caché válida "
            f"del {FECHA}") in salida.splitlines()
    assert "[OK] servicio v (svc_v)" not in salida
    assert "[AVISO] servicio v (svc_v): un aviso" in salida
    assert "FALLOS=1" in salida
    assert _leer(caso, ".arnes_cache/suite_v.ok") == "clave-del-verde"


@necesita_bash
@init_sh_de_f028
def test_f028_r14_verde_en_ejecutar_siempre_dice_la_fecha_y_cuantas_rutas(
    siempre: tuple[str, Path],
) -> None:
    salida, caso = siempre

    assert (f"[OK] servicio s (svc_s): pytest en verde (caché: ni el servicio ni sus "
            f"dependencias han cambiado desde el verde del {FECHA}; ejecutar_siempre: "
            f"2 rutas en verde)") in salida.splitlines()
    assert not (caso / ".arnes_cache" / "suite_s.ok").exists()


@necesita_bash
def test_f028_r15_el_portero_ligero_no_ejecuta_ejecutar_siempre(tmp_path: Path) -> None:
    salida, caso = _caso(tmp_path, {"s": SIEMPRE["s"]}, saltar="1")

    assert "[AVISO] servicio s (svc_s): suite saltada (portero ligero)" in salida
    assert _leer(caso, "pytest_args.txt") == ""
    assert _leer(caso, "llamadas.txt") == ""
    assert "FALLOS=0" in salida


#: El caso de postventa F-055: un barrido de `progress/` declarado en
#: `ejecutar_siempre`. Un client ID llegó a `main` porque, con la caché válida,
#: nadie ejecutaba el barrido.
POSTVENTA = {"postventa": (
    f"SIEMPRE|tests/test_sin_secretos_en_progress.py\nSERVIR|{FECHA}\n", 0)}


@necesita_bash
@init_sh_de_f028
def test_f028_r21_postventa_barrido_en_rojo_tumba_el_portero(tmp_path: Path) -> None:
    salida, caso = _caso(tmp_path, POSTVENTA, pytest_rojo=("postventa",))

    assert _args_pytest(caso, "postventa") == [
        ("py_falso svc_postventa -m pytest -q --tb=short -p no:cacheprovider "
         "tests/test_sin_secretos_en_progress.py")
    ]
    assert re.search(r"^\[KO\] servicio postventa .*ejecutar_siempre", salida, re.MULTILINE)
    assert "FALLOS=1" in salida


@necesita_bash
@init_sh_de_f028
def test_f028_r21_postventa_barrido_en_verde_deja_el_portero_en_verde(
    tmp_path: Path,
) -> None:
    salida, caso = _caso(tmp_path, POSTVENTA)

    assert len(_args_pytest(caso, "postventa")) == 1
    assert re.search(r"^\[OK\] servicio postventa .*ejecutar_siempre: 1 rutas en verde\)$",
                     salida, re.MULTILINE)
    assert "FALLOS=0" in salida


@necesita_bash
def test_f028_r21_sin_siempre_la_linea_de_cache_es_la_de_la_1_7_16(
    siempre: tuple[str, Path],
) -> None:
    salida, caso = siempre

    assert LINEA_CACHE_1_7_16.format(n="b") in salida.splitlines()
    assert _args_pytest(caso, "b") == []


#: El bucle de la §7 bis de la 1.7.16 (2026-10-16), copiado tal cual: es el que
#: conserva un proyecto que, al actualizar, no acepta el `init.sh` nuevo.
CASE_1_7_16 = """while IFS='|' read -r TIPO VALOR; do
    case "$TIPO" in
        AVISO)    warn "servicio $NOMBRE ($RUTA): $VALOR" ;;
        SERVIR)   FECHA_VERDE="$VALOR" ;;
        EJECUTAR) CLAVE_SRV="$VALOR" ;;
    esac
done <<EOF_CACHE
$DECISION
EOF_CACHE
"""


@necesita_bash
@pytest.mark.parametrize("con_siempre", [False, True])
def test_f028_r23_el_init_sh_de_la_1_7_16_ignora_siempre_sin_error(
    tmp_path: Path, con_siempre: bool
) -> None:
    siempre = "SIEMPRE|tests/test_barrido.py\n" if con_siempre else ""
    guion = tmp_path / "viejo.sh"
    guion.write_text(
        "set -u\nNOMBRE=s\nRUTA=svc_s\nCLAVE_SRV=\"\"\nFECHA_VERDE=\"\"\n"
        'warn() { printf "[AVISO] %s\\n" "$1"; }\n'
        f"DECISION='AVISO|uno\n{siempre}SERVIR|{FECHA}'\n"
        + CASE_1_7_16
        + 'echo "FECHA_VERDE=$FECHA_VERDE CLAVE_SRV=$CLAVE_SRV"\n',
        encoding="utf-8", newline="\n",
    )

    proceso = subprocess.run([BASH, guion.name], cwd=tmp_path, capture_output=True,
                             text=True, encoding="utf-8", timeout=escalar_timeout(60), check=False)

    assert proceso.returncode == 0
    assert proceso.stderr == ""
    assert proceso.stdout == (
        "[AVISO] servicio s (svc_s): uno\n"
        f"FECHA_VERDE={FECHA} CLAVE_SRV=\n"
    )


# === Review de F-028, pasada 1: Python en Windows responde en CRLF =================

#: En Windows, `print()` a una tubería escribe `\r\n` y `DECISION=$(…)` solo quita
#: el último salto. Sin recortar el `\r`, `SIEMPRE|tests/barridos` llegaba a
#: pytest como `tests/barridos\r` (no existe: sale con 4 y da `[KO]` con la caché
#: válida), la fecha del verde y los avisos llevaban un `\r` dentro, y la clave se
#: guardaba con él (`EJECUTAR|` sin clave guardaba una caché que solo era `\r`).
CRLF = {
    "s": ((f"AVISO|un aviso\nSIEMPRE|tests/test_barrido.py\nSIEMPRE|tests/barridos\n"
           f"SERVIR|{FECHA}\n"), 0),
    "c": ("EJECUTAR|\n", 0),
    "d": ("EJECUTAR|clave-d\n", 0),
}


@pytest.fixture(scope="module")
def crlf(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    return _caso(tmp_path_factory.mktemp("cache_crlf"), CRLF, fin_de_linea="\r\n")


@necesita_bash
@init_sh_de_f028
def test_f028_r12_crlf_pytest_recibe_las_rutas_sin_retorno_de_carro(
    crlf: tuple[str, Path],
) -> None:
    salida, caso = crlf

    assert b"\r" not in (caso / "pytest_args.txt").read_bytes()
    assert _args_pytest(caso, "s") == [
        ("py_falso svc_s -m pytest -q --tb=short -p no:cacheprovider "
         "tests/test_barrido.py tests/barridos")
    ]
    assert (f"[OK] servicio s (svc_s): pytest en verde (caché: ni el servicio ni sus "
            f"dependencias han cambiado desde el verde del {FECHA}; ejecutar_siempre: "
            f"2 rutas en verde)") in salida.splitlines()
    assert "FALLOS=0" in salida.splitlines()


@necesita_bash
@init_sh_de_f028
def test_f028_r12_crlf_ni_los_avisos_ni_la_fecha_llevan_retorno_de_carro(
    crlf: tuple[str, Path],
) -> None:
    salida, _ = crlf

    assert "\r" not in salida
    assert "[AVISO] servicio s (svc_s): un aviso" in salida.splitlines()


@necesita_bash
@init_sh_de_f028
def test_f028_r12_crlf_la_clave_se_guarda_sin_retorno_de_carro(
    crlf: tuple[str, Path],
) -> None:
    _, caso = crlf

    assert (caso / ".arnes_cache" / "suite_d.ok").read_bytes() == b"clave-d"
    assert not (caso / ".arnes_cache" / "suite_c.ok").exists()


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Arnes", "-c", "user.email=arnes@ejemplo.invalid",
         "-C", str(raiz), *args],
        capture_output=True, check=True,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    )


@necesita_bash
@init_sh_de_f028
def test_f028_r12_de_punta_a_punta_con_la_salida_real_de_cache_suites(
    tmp_path: Path,
) -> None:
    """Sin falsos: el Python, el git y el pytest de verdad (en Windows, CRLF)."""
    raiz = tmp_path / "repo"
    shutil.copytree(RAIZ / "harness", raiz / "harness",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (raiz / "harness" / "servicios.json").write_text(json.dumps({"servicios": [
        {"nombre": "svc", "ruta": "svc", "lenguaje": "python",
         "ejecutar_siempre": ["tests/barridos"]},
    ]}), encoding="utf-8")
    (raiz / ".gitignore").write_text(
        ".arnes_cache/\ncoverage.json\n.coverage\n__pycache__/\n.pytest_cache/\n"
        "seccion.sh\n", encoding="utf-8")
    for ruta in ("svc/tests/test_app.py", "svc/tests/barridos/test_barrido.py"):
        (raiz / ruta).parent.mkdir(parents=True, exist_ok=True)
        (raiz / ruta).write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    _git(raiz, "init", "-q")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    py = Path(sys.executable).as_posix()

    primera = _ejecutar_seccion(raiz, py, limite_s=300)
    segunda = _ejecutar_seccion(raiz, py, limite_s=300)

    assert "[OK] servicio svc (svc): pytest en verde" in primera.splitlines(), primera
    lineas = segunda.splitlines()
    assert [linea for linea in lineas if linea.startswith("[OK] servicio svc (svc)")
            and linea.endswith("; ejecutar_siempre: 1 rutas en verde)")], segunda
    assert "FALLOS=0" in lineas, segunda


# === Desviación 1 de F-028 con el patrón de F-055: UN rojo y el resto saltado ========

#: Los tests que dan por hecho la §7 bis de F-028, y el que fabrica un init.sh
#: viejo a partir del nuevo. R23 del init.sh instalado no: es el rojo que lleva
#: la instrucción.
_CON_MARCA = ("test_f028_r12_", "test_f028_r13_", "test_f028_r14_",
              "test_f028_r21_postventa_", "test_f028_r23_un_init_sh_de_la_1_7_16_")


def test_f028_r23_los_tests_que_dependen_del_init_sh_nuevo_llevan_la_marca() -> None:
    funciones = {nombre: f for nombre, f in globals().items()
                 if nombre.startswith(_CON_MARCA) and callable(f)}

    assert len(funciones) >= 12, sorted(funciones)
    for nombre, funcion in funciones.items():
        assert init_sh_de_f028.mark in getattr(funcion, "pytestmark", []), nombre
    r23 = test_f028_r23_el_init_sh_instalado_reconoce_las_lineas_siempre
    assert init_sh_de_f028.mark not in getattr(r23, "pytestmark", [])


@init_sh_de_f028
def test_f028_r23_un_init_sh_de_la_1_7_16_da_el_motivo_con_instrucciones() -> None:
    viejo = _texto().replace('SIEMPRE)  SIEMPRE_SRV+=("$VALOR") ;;', "")

    assert viejo != _texto()
    assert _motivo_init_sh_viejo(viejo) == _INSTRUCCION_SIEMPRE
    assert "acepta ese bloque del diff de harness/init.sh" in _INSTRUCCION_SIEMPRE


@pytest.mark.parametrize("texto", ["", "#!/usr/bin/env bash\necho hola\n"])
def test_f028_r23_un_init_sh_irreconocible_no_rompe_la_coleccion(texto: str) -> None:
    assert _motivo_init_sh_viejo(texto) == _INSTRUCCION_SIEMPRE


#: En el taller el init.sh es el del payload; en un proyecto instalado puede ser
#: el que conservó, y entonces el rojo ya lo da R23 del init.sh instalado.
es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="harness/init.sh es el del proyecto, no el del payload",
)


@es_el_taller
def test_f028_r23_con_el_init_sh_del_payload_no_se_salta_nada_por_esa_causa() -> None:
    assert _motivo_init_sh_viejo(_texto()) is None
    assert _MOTIVO_INIT_SH_VIEJO is None
