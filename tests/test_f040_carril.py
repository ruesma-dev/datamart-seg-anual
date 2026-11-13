# tests/test_f040_carril.py
"""F-040: la puerta de carril (`harness/carril.py`).

Repositorios git de verdad bajo `tmp_path`: una plantilla por módulo y una copia
por test, porque lo que se prueba es la lectura real de `git diff --numstat -z`
(binarios, renombrados, espacios y acentos), no un doble suyo. Sin red ni BBDD.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from harness import carril

RAMA = "feature/F-900-x"
LIMITES = {"ficheros": 3, "lineas": 10,
           "no_cuentan": ["progress/**", "specs/**", "BACKLOG.md",
                          "harness/features.json", "tests/**", "**/tests/**"]}
RIGOR = {
    "nivel_por_defecto": "estandar",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "niveles": {
        "estandar": {"fase_red": True, "cobertura": True, "mutacion": True},
        "rapido": {"fase_red": False, "cobertura": False, "mutacion": False,
                   "limites": LIMITES},
    },
}
SALIDA_ROJA = "sube el nivel"


def _git(raiz: Path, *args: str) -> str:
    salida = subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=Arnes",
         "-c", "user.email=arnes@ejemplo.invalid", "-c", "commit.gpgsign=false",
         "-c", "core.autocrlf=false", "-c", "core.quotepath=true", *args],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    return salida.stdout.strip()


def _lineas(n: int, marca: str = "x") -> str:
    return "".join(f"{marca}{i}\n" for i in range(n))


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory: pytest.TempPathFactory) -> Path:
    raiz = tmp_path_factory.mktemp("plantilla") / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "dev")
    (raiz / "viejo.txt").write_text(_lineas(4), encoding="utf-8", newline="\n")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicio")
    _git(raiz, "checkout", "-q", "-b", RAMA)
    return raiz


class Repo:
    """Copia de la plantilla, en la rama de la feature, con su configuración."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.config = raiz.parent / "rigor.json"
        self.features = raiz.parent / "features.json"
        self.ficha({})
        self.rigor(RIGOR)

    def rigor(self, datos: dict) -> None:
        self.config.write_text(json.dumps(datos), encoding="utf-8")

    def ficha(self, cambios: dict) -> None:
        ficha = {"id": "F-900", "title": "T", "status": "in_progress", "sdd": False,
                 "rigor": "rapido", "branch": RAMA, **cambios}
        self.features.write_text(json.dumps({"features": [ficha]}), encoding="utf-8")

    def commit(self, ficheros: dict[str, str | bytes]) -> None:
        for ruta, contenido in ficheros.items():
            fichero = self.raiz / ruta
            fichero.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(contenido, bytes):
                fichero.write_bytes(contenido)
            else:
                fichero.write_text(contenido, encoding="utf-8", newline="\n")
        _git(self.raiz, "add", "-A")
        _git(self.raiz, "commit", "-q", "-m", "F-900: cambio")

    def sensibles(self, patron: str = "app/pagos/**") -> None:
        datos = {"verificaciones": [{
            "nombre": "pagos", "comando": "x", "informe": "progress/x.md",
            "exigencia": "bloqueo",
            "rutas": [{"patron": patron, "motivo": "mueve dinero"}],
        }]}
        (self.raiz / "harness").mkdir(exist_ok=True)
        (self.raiz / "harness" / "rutas_sensibles.json").write_text(
            json.dumps(datos), encoding="utf-8")

    def puerta(self, capsys: pytest.CaptureFixture, *extra: str) -> tuple[int, str]:
        codigo = carril.main(["--config", str(self.config),
                              "--features", str(self.features),
                              "--raiz", str(self.raiz), "--base", "dev", *extra])
        capturado = capsys.readouterr()
        return codigo, capturado.out + capturado.err


@pytest.fixture
def repo(plantilla: Path, tmp_path: Path) -> Repo:
    raiz = tmp_path / "repo"
    shutil.copytree(plantilla, raiz)
    return Repo(raiz)


# --- R7, R9: medir, y el límite exacto pasa ----------------------------------


def test_f040_r7_cuenta_ficheros_y_lineas_sumando_anadidas_y_borradas(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(2), "viejo.txt": "x0\nnuevo\nx2\nx3\n"})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "2/3 ficheros" in salida and "4/10 líneas" in salida


def test_f040_r7_no_cuenta_lo_que_casa_con_no_cuentan(repo, capsys) -> None:
    repo.commit({
        "a.txt": _lineas(1), "progress/i.md": _lineas(99), "specs/F/r.md": _lineas(99),
        "BACKLOG.md": _lineas(99), "harness/features.json": _lineas(99),
        "tests/t.py": _lineas(99), "servicio/tests/t.py": _lineas(99),
    })

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "1/3 ficheros" in salida and "1/10 líneas" in salida


def test_f040_r7_solo_mide_lo_comprometido(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(1)})
    (repo.raiz / "b.txt").write_text(_lineas(99), encoding="utf-8")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "1/10 líneas" in salida


def test_f040_r7_mide_contra_el_merge_base_no_contra_la_punta_de_la_base(repo, capsys) -> None:
    """La base avanza con trabajo ajeno y la feature no paga por él."""
    repo.commit({"a.txt": _lineas(1)})
    _git(repo.raiz, "checkout", "-q", "dev")
    repo.commit({"ajeno1.txt": _lineas(50), "ajeno2.txt": _lineas(50)})
    _git(repo.raiz, "checkout", "-q", RAMA)

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "1/3 ficheros" in salida


def test_f040_r9_lo_medido_igual_al_limite_pasa(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(8), "b.txt": _lineas(1), "c.txt": _lineas(1)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "3/3 ficheros" in salida and "10/10 líneas" in salida


# --- R8, R11: rojo con medido, tope y salida ---------------------------------


def test_f040_r8_un_fichero_de_mas_es_rojo(repo, capsys) -> None:
    repo.commit({f"{n}.txt": _lineas(1) for n in "abcd"})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "F-900" in salida and "nivel rapido" in salida
    assert "4 ficheros" in salida and "tope 3" in salida
    assert "líneas >" not in salida, "solo se nombra el límite superado"


def test_f040_r8_una_linea_de_mas_es_rojo(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(11)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "11 líneas" in salida and "tope 10" in salida


def test_f040_r8_los_dos_limites_superados_salen_los_dos(repo, capsys) -> None:
    repo.commit({f"{n}.txt": _lineas(3) for n in "abcd"})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "4 ficheros" in salida and "12 líneas" in salida


def test_f040_r11_el_rojo_dice_la_salida_y_no_editar_los_limites(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(11)})

    _, salida = repo.puerta(capsys)

    assert SALIDA_ROJA in salida and "PARADA 1" in salida
    assert "nunca" in salida and "límites" in salida


# --- R10: rutas sensibles ----------------------------------------------------


def test_f040_r10_ruta_sensible_es_rojo_aunque_quepa(repo, capsys) -> None:
    repo.sensibles()
    repo.commit({"app/pagos/iva.py": _lineas(1)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "app/pagos/iva.py" in salida and "mueve dinero" in salida
    assert SALIDA_ROJA in salida


def test_f040_r10_ruta_sensible_en_un_fichero_que_no_cuenta_tambien(repo, capsys) -> None:
    repo.sensibles("tests/pagos/**")
    repo.commit({"tests/pagos/t.py": _lineas(1)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "tests/pagos/t.py" in salida


def test_f040_r10_exceso_y_ruta_sensible_salen_juntos(repo, capsys) -> None:
    repo.sensibles()
    repo.commit({"app/pagos/iva.py": _lineas(11)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "12 líneas" in salida and "mueve dinero" in salida  # 11 + la declaración


def test_f040_r16_con_declaracion_que_no_toca_cuenta_las_rutas(repo, capsys) -> None:
    repo.sensibles()
    repo.commit({"a.txt": _lineas(1)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "1 rutas sensibles declaradas" in salida


# --- R12: binario, renombrado, nombres raros ---------------------------------


def test_f040_r12_binario_es_un_fichero_con_cero_lineas(repo, capsys) -> None:
    repo.commit({"logo.bin": b"\x00\x01\x02" * 500})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "1/3 ficheros" in salida and "0/10 líneas" in salida


def test_f040_r12_un_renombrado_cuenta_como_dos_ficheros(repo, capsys) -> None:
    _git(repo.raiz, "mv", "viejo.txt", "nuevo.txt")
    _git(repo.raiz, "commit", "-q", "-m", "F-900: renombra")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "2/3 ficheros" in salida and "8/10 líneas" in salida


def test_f040_r12_un_renombrado_a_una_ruta_que_no_cuenta_cuenta_solo_el_origen(repo, capsys) -> None:
    _git(repo.raiz, "mv", "viejo.txt", "BACKLOG.md")
    _git(repo.raiz, "commit", "-q", "-m", "F-900: renombra")

    _, salida = repo.puerta(capsys)

    assert "1/3 ficheros" in salida and "4/10 líneas" in salida


def test_f040_r12_ruta_con_espacios_y_acentos_por_su_nombre_real(repo, capsys) -> None:
    repo.sensibles("docs/año nuevo/**")
    repo.commit({"docs/año nuevo/guía.md": _lineas(1)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1, salida
    assert "docs/año nuevo/guía.md" in salida


def test_f040_r12_no_cuentan_casa_nombres_con_acentos(repo, capsys) -> None:
    rigor = json.loads(json.dumps(RIGOR))
    rigor["niveles"]["rapido"]["limites"]["no_cuentan"] = ["año/**"]
    repo.rigor(rigor)
    repo.commit({"año/guía de uso.md": _lineas(99)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "0/3 ficheros" in salida


def test_f040_r12_parsear_numstat_lee_el_formato_real() -> None:
    texto = "3\t2\ta b.txt\x00-\t-\tlogo.bin\x000\t1\taño.md\x00"

    assert carril.parsear_numstat(texto) == [
        ("a b.txt", 5), ("logo.bin", 0), ("año.md", 1)]


def test_f040_r12_parsear_numstat_vacio() -> None:
    assert carril.parsear_numstat("") == []


# --- R13: N/A ----------------------------------------------------------------


@pytest.mark.parametrize("rama", ["dev", "main", "master"])
def test_f040_r13_en_la_base_o_en_main_es_na(repo, capsys, rama: str) -> None:
    if rama != "dev":
        _git(repo.raiz, "branch", rama)
    _git(repo.raiz, "checkout", "-q", rama)

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0
    assert "N/A" in salida and rama in salida


def test_f040_r13_sin_rama_es_na(repo, capsys) -> None:
    _git(repo.raiz, "checkout", "-q", "--detach")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0
    assert "N/A" in salida and "(detached)" in salida


def test_f040_r13_sin_feature_es_na(repo, capsys) -> None:
    repo.ficha({"branch": "feature/F-901-otra", "status": "pending"})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0
    assert "N/A" in salida and RAMA in salida


def test_f040_r13_feature_done_es_na_aunque_se_pase(repo, capsys) -> None:
    repo.ficha({"status": "done"})
    repo.commit({"a.txt": _lineas(99)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0
    assert "N/A" in salida and "F-900" in salida and "cerrada" in salida


def test_f040_r13_nivel_sin_limites_es_na_aunque_se_pase(repo, capsys) -> None:
    repo.ficha({"rigor": "estandar"})
    repo.commit({"a.txt": _lineas(99)})

    codigo, salida = repo.puerta(capsys)

    assert codigo == 0
    assert "N/A" in salida and "estandar" in salida


# --- R14: lo que no se puede medir no pasa -----------------------------------


def test_f040_r14_base_rezagada_es_rojo(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(1)})
    _git(repo.raiz, "branch", "main")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "se ha quedado por detrás" in salida


def test_f040_r14_base_inexistente_es_rojo(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(1)})
    _git(repo.raiz, "branch", "-m", "dev", "develop")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "no existe" in salida


def test_f040_r14_declaracion_rota_es_rojo(repo, capsys) -> None:
    (repo.raiz / "harness").mkdir()
    (repo.raiz / "harness" / "rutas_sensibles.json").write_text("{roto", encoding="utf-8")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "no es JSON válido" in salida


def test_f040_r14_sin_alcance_calculable_es_rojo(repo, capsys, monkeypatch) -> None:
    def _sin_alcance(*_args: object, **_kwargs: object) -> None:
        raise SystemExit("no se puede calcular")

    monkeypatch.setattr(carril, "resolver_refs", _sin_alcance)

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "no se puede calcular" in salida


def test_f040_r14_si_git_diff_falla_no_pasa(repo, capsys, monkeypatch) -> None:
    """`ejecutar_git` devuelve "" al fallar: un diff vacío no es un diff limpio."""
    repo.commit({"a.txt": _lineas(99)})
    monkeypatch.setattr(carril, "resolver_refs",
                        lambda *_a, **_k: ("no-existe-1", "no-existe-2", "rama"))

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "no se pudo calcular" in salida


def test_f040_r7_una_rama_sin_commits_propios_mide_cero_y_pasa(repo, capsys) -> None:
    codigo, salida = repo.puerta(capsys)

    assert codigo == 0, salida
    assert "0/3 ficheros" in salida and "0/10 líneas" in salida


def test_f040_r13_sin_base_explicita_lee_rama_base_de_init_sh(repo, capsys) -> None:
    (repo.raiz / "harness").mkdir()
    (repo.raiz / "harness" / "init.sh").write_text(
        "RAMA_BASE=trunk\n", encoding="utf-8")
    _git(repo.raiz, "checkout", "-q", "-b", "trunk")

    codigo = carril.main(["--config", str(repo.config), "--features", str(repo.features),
                          "--raiz", str(repo.raiz)])

    assert codigo == 0
    assert "N/A (rama trunk" in capsys.readouterr().out


# --- R15, R16 ----------------------------------------------------------------


def test_f040_r15_rigor_ilegible_sale_con_2(repo, capsys) -> None:
    repo.config.write_text("{roto", encoding="utf-8")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 2
    assert "no es JSON válido" in salida


def test_f040_r15_features_ilegible_sale_con_2(repo, capsys) -> None:
    repo.features.write_text("{roto", encoding="utf-8")

    codigo, salida = repo.puerta(capsys)

    assert codigo == 2
    assert salida.startswith("PUERTA CARRIL:")


def test_f040_r16_sin_declaracion_lo_dice(repo, capsys) -> None:
    repo.commit({"a.txt": _lineas(1)})

    _, salida = repo.puerta(capsys)

    assert "sin rutas sensibles declaradas" in salida


# --- Unidades ----------------------------------------------------------------


def test_f040_r8_excesos_es_vacio_en_el_limite() -> None:
    medida = carril.Medida(ficheros=("a", "b"), lineas=5, tocados=("a", "b"))

    assert carril.excesos(medida, {"ficheros": 2, "lineas": 5}) == []


def test_f040_r8_excesos_describe_cada_limite() -> None:
    medida = carril.Medida(ficheros=("a", "b"), lineas=6, tocados=("a", "b"))

    assert carril.excesos(medida, {"ficheros": 1, "lineas": 5}) == [
        "2 ficheros > tope 1", "6 líneas > tope 5"]


def test_f040_r7_medir_separa_lo_que_cuenta_de_lo_tocado() -> None:
    def git(args: list[str]) -> str:
        assert args == ["diff", "--no-renames", "--numstat", "-z", "A", "B"]
        return "1\t1\ta.txt\x005\t0\ttests/t.py\x00"

    medida = carril.medir("A", "B", ["tests/**"], git)

    assert medida == carril.Medida(
        ficheros=("a.txt",), lineas=2, tocados=("a.txt", "tests/t.py"))


# --- Supervivientes de la campaña de mutación ---------------------------------


def test_f040_r12_parsear_numstat_respeta_un_tabulador_en_el_nombre() -> None:
    """Con `-z` el nombre va tal cual: un tabulador dentro es parte de la ruta."""
    assert carril.parsear_numstat("1\t1\ta\tb.txt\x00") == [("a\tb.txt", 2)]


def test_f040_r7_la_medida_es_inmutable() -> None:
    import dataclasses

    medida = carril.Medida(ficheros=("a",), lineas=1, tocados=("a",))

    with pytest.raises(dataclasses.FrozenInstanceError):
        medida.lineas = 0  # type: ignore[misc]


def test_f040_r7_resuelve_las_referencias_con_el_id_de_la_feature(
    repo, capsys, monkeypatch
) -> None:
    """Sin rama, `resolver_refs` busca el merge por el id: tiene que recibirlo."""
    vistos: list[tuple] = []
    original = carril.resolver_refs

    def espia(feature_id, rama, base, git=None):
        vistos.append((feature_id, rama, base))
        return original(feature_id, rama, base, git=git)

    monkeypatch.setattr(carril, "resolver_refs", espia)

    repo.puerta(capsys)

    assert vistos == [("F-900", RAMA, "dev")]


@pytest.mark.parametrize("refs", [("no-existe", "HEAD"), ("HEAD", "no-existe")],
                         ids=["origen", "destino"])
def test_f040_r14_basta_una_referencia_imposible_para_no_pasar(
    repo, capsys, monkeypatch, refs
) -> None:
    repo.commit({"a.txt": _lineas(1)})
    monkeypatch.setattr(carril, "resolver_refs", lambda *_a, **_k: (*refs, "rama"))

    codigo, salida = repo.puerta(capsys)

    assert codigo == 1
    assert "no se pudo calcular" in salida
