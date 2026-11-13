# tests/test_f059_servicios_e2e.py
"""F-059 · R1–R4: el bloque `e2e` de un servicio en `harness/servicios.json`.

Estricto por dentro (una clave desconocida del bloque es un error) y sin
efecto fuera: una declaración sin `e2e` da los mismos servicios y la misma
salida de `--shell` y `--validar`. Sin red ni git: todo en `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import servicios
from harness.servicios import BloqueE2E, cargar_servicios, host_prohibido

E2E_MINIMO = {"url_base": "http://localhost:8000", "rutas_ui": ["web/**"]}


def _declarar(raiz: Path, entradas: list[dict]) -> None:
    fichero = raiz / "harness" / "servicios.json"
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(json.dumps({"servicios": entradas}), encoding="utf-8")


def _uno(raiz: Path, lenguaje: str = "python", **extra: object) -> list:
    (raiz / "svc").mkdir(exist_ok=True)
    entrada = {"nombre": "svc", "ruta": "svc", "lenguaje": lenguaje, **extra}
    _declarar(raiz, [entrada])
    return cargar_servicios(raiz=str(raiz))


# --- R1: el bloque válido se expone con sus valores por defecto -------------


def test_f059_r1_bloque_minimo_con_los_valores_por_defecto(tmp_path: Path) -> None:
    (servicio,) = _uno(tmp_path, e2e=E2E_MINIMO)

    assert servicio.e2e == BloqueE2E(
        url_base="http://localhost:8000", rutas_ui=("web/**",),
        runner="pytest-playwright", comando=None, arranque=None,
        ruta_tests="tests_e2e", espera_arranque_s=60, timeout_s=900,
        hosts_prohibidos=(),
    )


def test_f059_r1_bloque_completo(tmp_path: Path) -> None:
    bloque = {
        "url_base": "https://127.0.0.1:5173/app", "rutas_ui": ["src\\ui/**", "web/*.html"],
        "runner": "playwright-test", "comando": "npx playwright test | cat",
        "arranque": "npm run dev", "ruta_tests": "e2e", "espera_arranque_s": 5,
        "timeout_s": 30, "hosts_prohibidos": ["*.ruesma.es", "prod-*"],
    }

    (servicio,) = _uno(tmp_path, lenguaje="otro", e2e=bloque)

    assert servicio.e2e.rutas_ui == ("src/ui/**", "web/*.html")
    assert servicio.e2e.runner == "playwright-test"
    assert servicio.e2e.comando == "npx playwright test | cat"
    assert (servicio.e2e.espera_arranque_s, servicio.e2e.timeout_s) == (5, 30)
    assert servicio.e2e.hosts_prohibidos == ("*.ruesma.es", "prod-*")


# --- R2: cada error nombra servicio y clave ---------------------------------


@pytest.mark.parametrize(("cambio", "clave"), [
    ({"otra": 1}, "otra"),
    ({"url_base": "localhost:8000"}, "url_base"),
    ({"url_base": 8000}, "url_base"),
    ({"rutas_ui": []}, "rutas_ui"),
    ({"rutas_ui": "web/**"}, "rutas_ui"),
    ({"rutas_ui": ["../fuera/**"]}, "rutas_ui"),
    ({"runner": "cypress"}, "runner"),
    ({"comando": ""}, "comando"),
    ({"arranque": 3}, "arranque"),
    ({"ruta_tests": ["x"]}, "ruta_tests"),
    ({"espera_arranque_s": 0}, "espera_arranque_s"),
    ({"espera_arranque_s": True}, "espera_arranque_s"),
    ({"timeout_s": -5}, "timeout_s"),
    ({"timeout_s": 1.5}, "timeout_s"),
    ({"hosts_prohibidos": "prod"}, "hosts_prohibidos"),
    ({"hosts_prohibidos": [""]}, "hosts_prohibidos"),
], ids=lambda valor: str(valor))
def test_f059_r2_un_bloque_mal_formado_falla_con_servicio_y_clave(
    tmp_path: Path, cambio: dict, clave: str
) -> None:
    with pytest.raises(ValueError) as error:
        _uno(tmp_path, e2e={**E2E_MINIMO, **cambio})

    assert "svc" in str(error.value) and clave in str(error.value)


@pytest.mark.parametrize("bloque", [{"rutas_ui": ["web/**"]}, {"url_base": "http://x"}],
                         ids=["sin url_base", "sin rutas_ui"])
def test_f059_r2_url_base_y_rutas_ui_son_obligatorias(tmp_path: Path, bloque) -> None:
    with pytest.raises(ValueError, match="svc"):
        _uno(tmp_path, e2e=bloque)


def test_f059_r2_el_bloque_tiene_que_ser_un_objeto(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'e2e'"):
        _uno(tmp_path, e2e=["http://localhost"])


def test_f059_r2_pytest_playwright_no_vale_en_un_servicio_otro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="runner"):
        _uno(tmp_path, lenguaje="otro", e2e=E2E_MINIMO)


def test_f059_r2_validar_sale_con_1(tmp_path: Path, capsys) -> None:
    (tmp_path / "svc").mkdir()
    _declarar(tmp_path, [{"nombre": "svc", "ruta": "svc", "lenguaje": "python",
                          "e2e": {**E2E_MINIMO, "runner": "otro"}}])

    codigo = servicios.main(["--validar", "--raiz", str(tmp_path)])

    assert codigo == 1
    assert "runner" in capsys.readouterr().err


# --- R3: un host productivo tumba la declaración ----------------------------


@pytest.mark.parametrize(("url", "patrones", "esperado"), [
    ("https://APP.Ruesma.es/x", ("*.ruesma.es",), "*.ruesma.es"),
    ("http://localhost:8000", ("*.ruesma.es",), None),
    ("http://prod-web:80", ("dev", "PROD-*"), "PROD-*"),
    ("http://localhost", (), None),
])
def test_f059_r3_host_prohibido_sin_distinguir_mayusculas(url, patrones, esperado) -> None:
    assert host_prohibido(url, patrones) == esperado


@pytest.mark.parametrize(("url", "patrones", "esperado"), [
    # Punto final (FQDN): el DNS lo resuelve al mismo host productivo.
    ("http://app.ruesma.es./", ("*.ruesma.es",), "*.ruesma.es"),
    ("http://app.ruesma.es.../x", ("*.ruesma.es",), "*.ruesma.es"),
    ("http://10.0.0.5./", ("10.0.0.5",), "10.0.0.5"),
    # Percent-encoding: el navegador decodifica el host antes de resolverlo.
    ("http://app.ruesma.es%2e/", ("*.ruesma.es",), "*.ruesma.es"),
    ("http://APP.RUESMA.ES%2E:443/", ("*.ruesma.es",), "*.ruesma.es"),
    ("http://%61pp.ruesma.es/", ("app.ruesma.es",), "app.ruesma.es"),
    ("http://usuario:clave@app.ruesma.es.:8443/", ("*.ruesma.es",), "*.ruesma.es"),
    # Controles: normalizar no inventa coincidencias.
    ("http://localhost./", ("*.ruesma.es",), None),
    ("http://ruesma.es.ejemplo.invalid/", ("*.ruesma.es",), None),
], ids=lambda valor: str(valor))
def test_f059_r3_host_prohibido_normaliza_punto_final_y_percent_encoding(
    url, patrones, esperado
) -> None:
    assert host_prohibido(url, patrones) == esperado


@pytest.mark.parametrize("url_base", [
    "http://app.ruesma.es./", "http://app.ruesma.es%2e/", "https://APP.Ruesma.ES.:443/x",
])
def test_f059_r3_host_prohibido_normalizado_en_la_carga(tmp_path: Path, url_base) -> None:
    bloque = {**E2E_MINIMO, "url_base": url_base, "hosts_prohibidos": ["*.ruesma.es"]}

    with pytest.raises(ValueError, match="host declarado como productivo"):
        _uno(tmp_path, e2e=bloque)


@pytest.mark.parametrize("url_base", ["http:///sin-host", "http://[::1/roto"])
def test_f059_r1_url_base_sin_host_es_un_error(tmp_path: Path, url_base) -> None:
    with pytest.raises(ValueError, match="svc.*url_base"):
        _uno(tmp_path, e2e={**E2E_MINIMO, "url_base": url_base})


# Pasada 3: lo que el analizador WHATWG del navegador lee distinto que urlsplit.
# Para él la `\` es una `/`, y los blancos y controles los elimina: Python y
# Playwright verían hosts distintos, así que la URL se rechaza entera.
URL_AMBIGUAS = [
    "http://app.ruesma.es\\@localhost/",
    "http://localhost\\@app.ruesma.es/",
    "http://app.ruesma.es\\x",
    "http://localhost/\n",
    "http://localhost/\r",
    "http://loc\x00alhost/",
    "http://localhost\x1f/",
    "http://localhost\x7f/",
    "http://localhost\x85/",
    "http://localhost/a b",
    "http://localhost/\t",
    " http://localhost/",
]


@pytest.mark.parametrize("url", URL_AMBIGUAS, ids=repr)
def test_f059_r3_host_de_url_rechaza_barra_invertida_blancos_y_controles(url) -> None:
    assert servicios.host_de_url(url) == ""
    assert host_prohibido(url, ("localhost", "app.ruesma.es")) is None


@pytest.mark.parametrize("prohibidos", [["*.ruesma.es"], []], ids=["con", "sin prohibidos"])
@pytest.mark.parametrize("url_base", URL_AMBIGUAS, ids=repr)
def test_f059_r1_url_base_con_barra_invertida_o_controles_es_un_error(
    tmp_path: Path, url_base, prohibidos
) -> None:
    bloque = {**E2E_MINIMO, "url_base": url_base, "hosts_prohibidos": prohibidos}

    with pytest.raises(ValueError, match=r"svc.*url_base.*barra invertida"):
        _uno(tmp_path, e2e=bloque)


# Pasada 4: lo que el navegador mapea por IDNA y urlsplit deja tal cual. Para
# WHATWG los puntos ideográficos y de ancho completo son un punto, el guion
# blando y el espacio de ancho cero desaparecen y el ancho completo pasa a
# ASCII: todas estas URL son `app.ruesma.es` en el navegador. La guarda es una
# lista blanca (nombre DNS ASCII, IPv4 o IPv6), no otra lista negra.
URL_NO_ASCII = [
    "http://app.ruesma.es\u3002/",       # punto ideográfico
    "http://app.ruesma.es%E3%80%82/",    # el mismo, en %xx
    "http://app.ruesma%E3%80%82es/",
    "http://app.ruesma.es\uff0e/",       # punto de ancho completo
    "http://app.ruesma.es\uff61/",       # punto ideográfico de media anchura
    "http://app.ruesma\u00ad.es/",       # guion blando
    "http://app.ruesma%C2%AD.es/",       # el mismo, en %xx
    "http://app.ruesma\u200b.es/",       # espacio de ancho cero
    "http://\uff41pp.ruesma.es/",        # «a» de ancho completo
    "http://app.ruesma..es/",            # etiqueta vacía
    "http://app_web.ruesma.es/",         # fuera de [a-z0-9-]
    "http://[fe80::1%25eth0]/",          # IPv6 con zona
]

#: Un IDN se declara en forma `xn--`: ASCII, y el navegador lo lee igual.
IDN_XN = "https://xn--pp-8cd.ruesma.es:8443/"


@pytest.mark.parametrize("url", URL_NO_ASCII, ids=ascii)
def test_f059_r3_host_de_url_solo_acepta_nombres_ascii_e_ip(url) -> None:
    assert servicios.host_de_url(url) == ""
    assert host_prohibido(url, ("app.ruesma.es", "*.ruesma.es")) is None


@pytest.mark.parametrize(("url", "esperado"), [
    (IDN_XN, "xn--pp-8cd.ruesma.es"),
    ("http://192.168.1.10:8000/", "192.168.1.10"),
    ("http://[::1]:8000/", "::1"),
    ("http://[2001:DB8::A]/", "2001:db8::a"),
    ("http://mi-servicio/", "mi-servicio"),
])
def test_f059_r3_host_de_url_acepta_dns_ascii_ipv4_e_ipv6(url, esperado) -> None:
    assert servicios.host_de_url(url) == esperado


@pytest.mark.parametrize("patrones", [("*.ruesma.es",), ("xn--pp-8cd.ruesma.es",)])
def test_f059_r3_idn_en_forma_xn_casa_con_su_glob(tmp_path: Path, patrones) -> None:
    assert host_prohibido(IDN_XN, patrones) == patrones[0]
    bloque = {**E2E_MINIMO, "url_base": IDN_XN, "hosts_prohibidos": list(patrones)}

    with pytest.raises(ValueError, match="host declarado como productivo"):
        _uno(tmp_path, e2e=bloque)


def test_f059_r1_idn_en_forma_xn_se_acepta(tmp_path: Path) -> None:
    (servicio,) = _uno(tmp_path, e2e={**E2E_MINIMO, "url_base": IDN_XN})

    assert servicio.e2e.url_base == IDN_XN


@pytest.mark.parametrize("prohibidos", [["*.ruesma.es", "app.ruesma.es"], []],
                         ids=["con", "sin prohibidos"])
@pytest.mark.parametrize("url_base", URL_NO_ASCII, ids=ascii)
def test_f059_r1_url_base_con_host_no_ascii_es_un_error(
    tmp_path: Path, url_base, prohibidos
) -> None:
    bloque = {**E2E_MINIMO, "url_base": url_base, "hosts_prohibidos": prohibidos}

    with pytest.raises(ValueError, match=r"svc.*url_base.*no ASCII.*xn--"):
        _uno(tmp_path, e2e=bloque)


# Pasada 5: hosts numéricos que urlsplit deja tal cual y el navegador analiza
# como IPv4 (WHATWG: si la última etiqueta es numérica, el host entero es una
# IPv4 en decimal, octal o hex, de 1 a 4 partes). Todos son 10.0.0.5, 127.0.0.1
# u otra IP para el navegador. Y la IPv6 con IPv4 embebida, que el navegador
# reescribe. Solo vale la IPv4 canónica de cuatro decimales.
URL_IP_NO_CANONICA = [
    "http://10.5/",                      # dos partes: 10.0.0.5
    "http://10.0.5/",                    # tres partes: 10.0.0.5
    "http://167772165/",                 # entero: 10.0.0.5
    "http://0x0a000005/",                # hex: 10.0.0.5
    "http://0xa.0.0.5/",                 # parte en hex
    "http://10.0.0.0x5/",                # última parte en hex
    "http://012.0.0.5/",                 # octal: 10.0.0.5
    "http://10.0.0.05/",                 # cero a la izquierda
    "http://010.000.000.005/",           # octal: 8.0.0.5
    "http://127.1/",                     # 127.0.0.1
    "http://0177.0.0.1/",                # octal: 127.0.0.1
    "http://0/",                         # 0.0.0.0
    "http://app.1/",                     # última etiqueta numérica, no IPv4
    "http://10.0.0.256/",                # fuera de rango
    "http://[::ffff:10.0.0.5]/",         # IPv6 con IPv4 embebida
    "http://[0:0:0:0:0:ffff:10.0.0.5]/",
    "http://[::ffff:a00:5]/",            # la misma, en hex
    "http://[::10.0.0.5]/",              # IPv4 compatible (con punto)
]


@pytest.mark.parametrize("url", URL_IP_NO_CANONICA)
def test_f059_r3_host_de_url_solo_acepta_ip_canonica(url) -> None:
    assert servicios.host_de_url(url) == ""
    assert host_prohibido(url, ("10.0.0.5", "127.0.0.1")) is None


@pytest.mark.parametrize(("url", "esperado"), [
    ("http://10.0.0.5:8000/", "10.0.0.5"),
    ("http://127.0.0.1/", "127.0.0.1"),
    ("http://localhost:8000/", "localhost"),
    ("http://[::1]/", "::1"),
    (IDN_XN, "xn--pp-8cd.ruesma.es"),
    ("http://1e1/", "1e1"),              # no es numérica: nombre DNS
    ("http://0.0.0.0/", "0.0.0.0"),
])
def test_f059_r3_host_de_url_acepta_ip_canonica_y_nombres(url, esperado) -> None:
    assert servicios.host_de_url(url) == esperado


@pytest.mark.parametrize("prohibidos", [["10.0.0.5", "127.0.0.1"], []],
                         ids=["con", "sin prohibidos"])
@pytest.mark.parametrize("url_base", URL_IP_NO_CANONICA)
def test_f059_r1_url_base_con_ip_no_canonica_es_un_error(
    tmp_path: Path, url_base, prohibidos
) -> None:
    bloque = {**E2E_MINIMO, "url_base": url_base, "hosts_prohibidos": prohibidos}

    with pytest.raises(ValueError, match=r"svc.*url_base.*IP en forma can"):
        _uno(tmp_path, e2e=bloque)


@pytest.mark.parametrize("url_base", ["http://10.0.0.5:8000/", "http://127.0.0.1/",
                                      "http://localhost/", "http://[::1]:8000/"])
def test_f059_r1_url_base_con_ip_canonica_se_acepta(tmp_path: Path, url_base) -> None:
    (servicio,) = _uno(tmp_path, e2e={**E2E_MINIMO, "url_base": url_base})

    assert servicio.e2e.url_base == url_base


def test_f059_r3_url_base_productiva_es_un_error(tmp_path: Path) -> None:
    bloque = {**E2E_MINIMO, "url_base": "https://app.ruesma.es",
              "hosts_prohibidos": ["*.RUESMA.es"]}

    with pytest.raises(ValueError, match="host declarado como productivo"):
        _uno(tmp_path, e2e=bloque)


# --- R4: sin bloque, nada cambia --------------------------------------------


def test_f059_r4_sin_e2e_el_servicio_lleva_none(tmp_path: Path) -> None:
    (servicio,) = _uno(tmp_path)

    assert servicio.e2e is None


def test_f059_r4_la_salida_shell_y_validar_no_cambian_con_el_bloque(
    tmp_path: Path, capsys
) -> None:
    (tmp_path / "svc").mkdir()
    entrada = {"nombre": "svc", "ruta": "svc", "lenguaje": "python"}
    salidas = []
    for declarada in (entrada, {**entrada, "e2e": E2E_MINIMO}):
        _declarar(tmp_path, [declarada])
        assert servicios.main(["--shell", "--raiz", str(tmp_path)]) == 0
        assert servicios.main(["--validar", "--raiz", str(tmp_path)]) == 0
        salidas.append(capsys.readouterr().out)

    assert salidas[0] == salidas[1]
    assert salidas[0].count("|") == 4
