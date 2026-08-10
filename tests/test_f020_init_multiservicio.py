# tests/test_f020_init_multiservicio.py
"""F-020 · Sección multi-servicio del portero (R3, R6 a R10).

Análisis textual de `harness/init.sh`, como hizo F-015 con los protocolos: lo
que se verifica es que el guion EXIGE lo que dicen los requisitos. Que el bucle
funciona de verdad contra un monorepo se comprueba en la verificación MANUAL
R20, cuya salida real va en `progress/impl_F-020.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
INIT = RAIZ / "harness" / "init.sh"

#: Marca que abre la sección multi-servicio. Fuera de ella, el portero es el
#: de siempre.
MARCA = "SERVICIOS DEL MONOREPO"


def guion() -> str:
    return INIT.read_text(encoding="utf-8")


def seccion_multiservicio() -> str:
    """Texto de la sección multi-servicio, de su cabecera a la siguiente."""
    texto = guion()
    inicio = texto.index(MARCA)
    resto = texto[inicio:]
    siguiente = re.search(r"\n# --- ", resto)
    return resto[: siguiente.start()] if siguiente else resto


def cuerpo_del_bucle() -> str:
    """Texto del bucle que recorre los servicios, sin la validación previa."""
    seccion = seccion_multiservicio()
    return seccion[seccion.index("IFS='|' read -r") : seccion.index("done <<")]


# --- R10: sin declaración no se ejecuta nada de esto ------------------------


def test_f020_r10_seccion_multiservicio_condicionada_a_la_declaracion() -> None:
    seccion = seccion_multiservicio()

    # Todo el bloque cuelga de que exista la declaración.
    assert re.search(r'if \[ -f "harness/servicios\.json" \]', seccion)
    # Y el fichero solo se nombra dentro de la sección: nada más del portero
    # depende de él.
    assert guion().count("harness/servicios.json") == seccion.count(
        "harness/servicios.json"
    )


def test_f020_r10_este_repositorio_sigue_siendo_mono_proyecto() -> None:
    assert not (RAIZ / "harness" / "servicios.json").exists()


def test_f020_r10_las_secciones_de_siempre_siguen_estando() -> None:
    texto = guion()

    for imprescindible in (
        "compileall",
        "harness.rigor --validar",
        "harness.cobertura",
        "coverage run -m pytest",
        "ENTORNO LISTO",
    ):
        assert imprescindible in texto, imprescindible


# --- R3: una declaración rota es KO, no una degradación silenciosa ----------


def test_f020_r3_init_sh_hace_ko_si_declaracion_invalida() -> None:
    seccion = seccion_multiservicio()

    assert "harness.servicios --validar" in seccion
    # El fallo de la validación llama a `ko`, que es lo que suma a FALLOS.
    validacion = seccion[seccion.index("--validar") :]
    assert re.search(r"ko \"[^\"]*servicios\.json", validacion)


# --- R6: un ejecutor por servicio y un agregado -----------------------------


def test_f020_r6_init_itera_servicios_y_agrega() -> None:
    seccion = seccion_multiservicio()

    # Los servicios se obtienen de la herramienta, no se adivinan del árbol.
    assert "harness.servicios --shell" in seccion
    # Y se recorren campo a campo con el separador de la salida --shell.
    assert "IFS='|' read -r" in seccion
    assert re.search(
        r"IFS='\|' read -r \w+ \w+ \w+ \w+ \w+", seccion
    ), "hay que leer los cinco campos de la línea"
    # El bucle NO puede colgar de una tubería: en un subshell, los `ko` no
    # sumarían a FALLOS y un servicio en rojo saldría en verde.
    assert "| while" not in seccion
    assert "done <<" in seccion


def test_f020_r6_cada_servicio_puede_sumar_al_recuento_de_fallos() -> None:
    seccion = seccion_multiservicio()

    # `ko` es la única función que incrementa FALLOS: si aparece en la sección,
    # un servicio en rojo tumba el veredicto global.
    assert seccion.count("ko \"") >= 2
    assert "FALLOS=$((FALLOS + 1))" in guion()


def test_f020_r6_el_interprete_de_cada_servicio_es_el_que_resuelve_la_herramienta() -> (
    None
):
    seccion = seccion_multiservicio()

    # El bucle no busca venvs a mano: usa la ruta ya resuelta que le da
    # `--shell` (cuarto campo).
    assert re.search(r"\$INTERPRETE\"? -m pytest", seccion)
    assert "Scripts/python.exe" not in seccion, "resolver el venv es cosa de Python"


def test_f020_r6_la_suite_de_cada_servicio_corre_desde_su_directorio() -> None:
    seccion = seccion_multiservicio()

    assert re.search(r"\(\s*cd \"\$RUTA\"", seccion)
    # Y deja su coverage.json donde la puerta de cobertura lo busca.
    assert "coverage json" in seccion


# --- R7: un servicio sin tests se avisa por su nombre -----------------------


def test_f020_r7_servicio_sin_tests_aviso_nominal() -> None:
    seccion = seccion_multiservicio()

    sin_tests = re.search(r'\[ ! -d "\$RUTA/tests" \].*?\n.*?warn "([^"]+)"', seccion)
    assert sin_tests, "falta el aviso del servicio sin directorio de tests"
    assert "$NOMBRE" in sin_tests.group(1), "el aviso tiene que nombrar al servicio"
    # Es AVISO, no KO: igual que hoy en un repositorio sin tests/.
    assert "ko" not in sin_tests.group(1)


# --- R8: servicios de otro lenguaje -----------------------------------------


def test_f020_r8_servicio_no_python_degrada_con_aviso() -> None:
    seccion = seccion_multiservicio()

    assert re.search(r'\[ "\$LENGUAJE" = "python" \]', seccion)
    # Sin comando_tests, aviso nominal de que nadie comprueba ese servicio.
    sin_comando = re.findall(r'warn "([^"]*\$NOMBRE[^"]*)"', seccion)
    assert any("NADIE" in aviso.upper() for aviso in sin_comando), sin_comando


def test_f020_r8_comando_tests_cuenta_en_el_agregado() -> None:
    seccion = seccion_multiservicio()

    assert 'eval "$COMANDO"' in seccion
    # Su fallo es un KO como el de cualquier otro servicio.
    tras_comando = seccion[seccion.index('eval "$COMANDO"') :]
    assert re.search(r"ko \"[^\"]*\$NOMBRE", tras_comando)


# --- R9: una línea por servicio y un único veredicto ------------------------


def test_f020_r9_una_linea_por_servicio_y_veredicto_unico() -> None:
    bucle = cuerpo_del_bucle()
    texto = guion()

    # Cada rama del bucle imprime con el formato [OK]/[AVISO]/[KO] del portero,
    # y todas nombran al servicio.
    for funcion in ("ok", "warn", "ko"):
        llamadas = re.findall(rf'{funcion} "([^"]+)"', bucle)
        assert llamadas, funcion
        assert all("$NOMBRE" in llamada for llamada in llamadas), (funcion, llamadas)

    # El veredicto sigue siendo uno solo, al final y con el recuento de fallos.
    assert texto.count("ENTORNO LISTO") == 1
    assert texto.count("comprobaciones fallidas") == 1
    assert texto.rstrip().endswith("fi")
