# tests/test_f004_sin_dependencias_locales.py
"""
F-004 · Auditoría automatizada del código que viaja en la imagen (R15, R16).

Estos tests no prueban una función: vigilan una propiedad del repositorio. Que
hoy esté limpio no impide que mañana alguien pegue una ruta de su OneDrive en
un step; el trabajo de este fichero es que eso salga en rojo antes de que un
job nocturno lo descubra en Azure.

Ámbito: solo lo que el Dockerfile copia (`etl_sigrid/`, `config/`, `main.py`).
`scripts/` y `patches/` quedan fuera a propósito: no viajan en la imagen.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PAQUETE = RAIZ / "etl_sigrid"

#: Capas SQL que el ETL ejecuta en tiempo de ejecución, cada una con su carpeta.
CAPAS_SQL = ("ddl", "stg", "mart", "cierre", "compras", "maestro", "retenciones", "auxiliar")

#: Rutas absolutas dentro de un literal de cadena. Cada patrón, un modo de atarse
#: al puesto de quien escribió el código.
PATRONES_RUTA_ABSOLUTA = {
    "unidad de Windows": re.compile(r"""['"][A-Za-z]:[\\/]"""),
    # Un UNC es \\servidor\recurso: dos (o cuatro, si van escapadas) barras,
    # un nombre de servidor y otra barra. Pedir el nombre y la barra siguiente
    # NO es cosmético: sin ellos el patrón caza el escapado de `bytea` de
    # postgres_client.py ("\\\\x" + hex), que no es ninguna ruta.
    "recurso de red UNC": re.compile(r"""['"]\\{2,4}[A-Za-z0-9_.$-]+\\{1,2}"""),
    "home de Linux": re.compile(r"/home/"),
    "home de macOS": re.compile(r"/Users/"),
    "montaje de Linux": re.compile(r"/mnt/"),
}


def _ficheros_de_la_imagen() -> list[Path]:
    """Los .py que el Dockerfile mete en la imagen, y solo esos."""
    return sorted(
        [
            *(RAIZ / "etl_sigrid").rglob("*.py"),
            *(RAIZ / "config").rglob("*.py"),
            RAIZ / "main.py",
        ]
    )


# ---------------------------------------------------------------------------
# R15 · nada del código de la imagen depende de una ruta absoluta local
# ---------------------------------------------------------------------------

def test_f004_r15_el_codigo_de_la_imagen_no_contiene_rutas_absolutas() -> None:
    """Una ruta absoluta del puesto no existe en el contenedor: es una bomba de relojería."""
    hallazgos: list[str] = []

    for fichero in _ficheros_de_la_imagen():
        relativa = fichero.relative_to(RAIZ).as_posix()
        for numero, linea in enumerate(
            fichero.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for descripcion, patron in PATRONES_RUTA_ABSOLUTA.items():
                if patron.search(linea):
                    hallazgos.append(f"{relativa}:{numero} [{descripcion}] {linea.strip()}")

    assert hallazgos == [], "Rutas absolutas en el código que viaja en la imagen:\n" + "\n".join(
        hallazgos
    )


def test_f004_r15_el_barrido_caza_de_verdad_una_ruta_absoluta() -> None:
    """
    Un test de auditoría que no sabe fallar no vigila nada: aquí se comprueba
    que cada patrón caza su forma y no caza una ruta relativa legítima.
    """
    muestras = {
        "unidad de Windows": 'RUTA = "C:/datos/x.xlsx"',
        "recurso de red UNC": r'RUTA = "\\\\servidor\\recurso\\x.xlsx"',
        "home de Linux": 'RUTA = "/home/pgris/x.xlsx"',
        "home de macOS": 'RUTA = "/Users/pgris/x.xlsx"',
        "montaje de Linux": 'RUTA = "/mnt/datos/x.xlsx"',
    }

    # Formas legítimas que NO son rutas absolutas y no pueden dar falso positivo.
    inocentes = (
        'Path(__file__).resolve().parent / "sql" / "stg"',
        r'return "\\\\x" + value.hex()',          # escapado de bytea
        r's.replace("\\", "\\\\")',               # escapado de barras
    )

    for descripcion, patron in PATRONES_RUTA_ABSOLUTA.items():
        assert patron.search(muestras[descripcion]), descripcion
        for inocente in inocentes:
            assert not patron.search(inocente), f"{descripcion} vs {inocente}"


# ---------------------------------------------------------------------------
# R16 · todo lo que se lee en ejecución está dentro del árbol que copia la imagen
# ---------------------------------------------------------------------------

def test_f004_r16_los_directorios_sql_de_cada_capa_existen_en_el_paquete() -> None:
    """Los SQL viajan en la imagen porque viven dentro de etl_sigrid/."""
    base_sql = PAQUETE / "infrastructure" / "postgres" / "sql"

    for capa in CAPAS_SQL:
        directorio = base_sql / capa
        assert directorio.is_dir(), f"Falta la capa SQL '{capa}' en {base_sql}"
        assert list(directorio.glob("*.sql")), f"La capa SQL '{capa}' no tiene ficheros"
        assert directorio.resolve().is_relative_to(PAQUETE.resolve())


def test_f004_r16_los_steps_resuelven_sus_sql_relativos_al_paquete() -> None:
    """
    Se reproduce la expresión que usan los steps (`parents[2]/infrastructure/...`)
    y se comprueba que apunta dentro del paquete y que el fichero existe. Si
    alguien mueve un step de carpeta, esto se entera.
    """
    steps = PAQUETE / "application" / "steps"
    esperados = {
        "build_stg_step.py": ("stg", "01_ddl.sql"),
        "build_mart_step.py": ("mart", None),
        "build_cierre_step.py": ("cierre", None),
        "build_maestros_step.py": ("maestro", None),
    }

    for nombre, (capa, fichero) in esperados.items():
        modulo = steps / nombre
        assert modulo.is_file()
        sql_dir = modulo.resolve().parents[2] / "infrastructure" / "postgres" / "sql" / capa
        assert sql_dir.is_dir(), f"{nombre} apunta a {sql_dir}, que no existe"
        assert sql_dir.is_relative_to(PAQUETE.resolve())
        if fichero:
            assert (sql_dir / fichero).is_file()

    # El auto-bootstrap de _meta resuelve su DDL igual, desde el cliente.
    ddl_meta = (
        PAQUETE / "infrastructure" / "postgres" / "sql" / "ddl" / "00_meta.sql"
    )
    assert ddl_meta.is_file()


def test_f004_r16_los_yaml_de_configuracion_viven_bajo_config() -> None:
    """`Settings` los resuelve con Path(__file__).parent, y el Dockerfile copia config/."""
    for nombre in ("tables_sigrid.yaml", "business_rules.yaml"):
        ruta = RAIZ / "config" / nombre
        assert ruta.is_file(), f"Falta config/{nombre}, que Settings lee al arrancar"


def test_f004_r16_el_dockerfile_copia_config_y_el_paquete_y_no_copia_env() -> None:
    """La imagen lleva lo que el ETL necesita, y ni un secreto de más."""
    lineas = (RAIZ / "Dockerfile").read_text(encoding="utf-8").splitlines()
    origenes = [
        linea.split()[1]
        for linea in lineas
        if linea.strip().upper().startswith("COPY") and len(linea.split()) >= 3
    ]

    assert {"config/", "etl_sigrid/", "main.py", "requirements.txt"} <= set(origenes)
    # Ni .env explícito ni un 'COPY . .' que lo arrastre sin querer.
    assert ".env" not in " ".join(origenes)
    assert "." not in origenes
