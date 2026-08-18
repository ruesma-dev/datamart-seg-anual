# tests/test_f024_infra_alerta.py
"""
F-024 · Tests de la alerta de frescura (R21, R22).

Fijan los DOS extremos del mismo contrato, y a propósito en el mismo fichero:
el orquestador emite el evento `step_finished` con `step` y `status`, y el
script de la alerta busca exactamente esos tres términos en los logs. Si
alguien renombra el evento, lo que tiene que romperse es la suite, no la
alerta en silencio a las 02:00 de un martes.

(Desviación menor respecto a `design.md`, que ponía el test del orquestador en
`test_f024_meta_y_formato.py`: separarlos deja cada mitad del contrato sin
constancia de la otra, que es justo lo que el requisito quiere impedir.)

Los helpers de lectura de `infra/` se IMPORTAN de `test_f003_infra.py`, no se
copian: dos copias de un barrido de secretos divergen, y ya pasó en este
repositorio.

Ninguno toca Azure: se lee el `.ps1` como texto.
"""

from __future__ import annotations

import re

from tests.test_f003_infra import (
    INFRA,
    PATRONES_PROHIBIDOS,
    _config,
    _lineas_de_codigo,
    _ps1,
    _script,
    _texto,
)

SCRIPT = "95_create_alert_frescura.ps1"

#: Los tres términos que la consulta de la alerta busca en la línea de log.
#: Son los que emite el orquestador al terminar `build_mart` correctamente.
TERMINOS_DEL_EVENTO = ("step_finished", "build_mart", "SUCCESS")

#: Todo lo que el script tiene que leer del fichero de entorno (R22.1).
CLAVES_QUE_LEE = (
    "frescuraAlertName",
    "frescuraUmbralHoras",
    "logAnalytics",
    "job",
    "resourceGroup",
    "alertActionGroupName",
    "alertActionGroupRg",
)


# ---------------------------------------------------------------------------
# R21 · El evento que vigila la alerta es estable, por los dos lados
# ---------------------------------------------------------------------------


def test_f024_r21_orquestador_emite_step_finished_con_step_y_status() -> None:
    """El extremo del ETL: el evento existe y lleva `step` y `status`.

    La alerta de frescura no mide la BBDD: mide que en el log del job haya
    aparecido una línea diciendo que `build_mart` terminó en `SUCCESS`. Si el
    evento cambiara de nombre o dejara de llevar el estado, la alerta seguiría
    sin disparar y nadie se enteraría hasta echar de menos un correo.
    """
    from etl_sigrid.application.orchestrator import Orchestrator
    from etl_sigrid.domain.entities import StepResult, StepStatus

    eventos: list[tuple[str, dict]] = []

    class _LoggerFalso:
        def info(self, evento: str, **kwargs: object) -> None:
            eventos.append((evento, dict(kwargs)))

        def warning(self, evento: str, **kwargs: object) -> None:
            eventos.append((evento, dict(kwargs)))

        def exception(self, evento: str, **kwargs: object) -> None:
            eventos.append((evento, dict(kwargs)))

    class _PasoFalso:
        name = "build_mart"
        stage = "build_mart"

        @property
        def depends_on(self) -> list[str]:
            return []

        def run(self) -> StepResult:
            from datetime import datetime

            return StepResult(
                step_name="build_mart",
                status=StepStatus.SUCCESS,
                started_at=datetime(2026, 8, 19, 5, 0, 0),
                finished_at=datetime(2026, 8, 19, 5, 25, 0),
                rows_processed=1_000,
            )

    import etl_sigrid.application.orchestrator as modulo

    original = modulo.logger
    modulo.logger = _LoggerFalso()  # type: ignore[assignment]
    try:
        Orchestrator([_PasoFalso()]).run_all()  # type: ignore[list-item]
    finally:
        modulo.logger = original

    terminados = [kw for nombre, kw in eventos if nombre == "step_finished"]
    assert terminados, "el orquestador ya no emite 'step_finished'"
    assert terminados[0]["step"] == "build_mart"
    assert terminados[0]["status"] == "SUCCESS"


def test_f024_r21_la_alerta_filtra_por_los_tres_terminos() -> None:
    """El otro extremo: el script busca esos tres términos y ninguna otra cosa."""
    texto = _script(SCRIPT)

    for termino in TERMINOS_DEL_EVENTO:
        assert termino in texto, (
            f"la consulta de la alerta no busca '{termino}': dejaría de vigilar "
            f"lo que R21 dice que vigila"
        )

    # Y los busca JUNTOS, en la misma línea de log, no cada uno por su lado.
    assert re.search(r"has_all\s*\(", texto), (
        "los tres términos tienen que exigirse en la MISMA línea (has_all): por "
        "separado, un 'SUCCESS' de cualquier otro paso apagaría la alerta"
    )


def test_f024_r21_la_alerta_mira_el_job_por_la_columna_real() -> None:
    """`ContainerJobName_s`, confirmada con `getschema` en T3.

    `ContainerAppName_s` —la que decía el README— NO existe en
    `ContainerAppConsoleLogs_CL` para un job: filtrar por ella devolvería
    siempre cero filas y la alerta dispararía todas las noches.
    """
    # Solo el CÓDIGO: la cabecera del script menciona `ContainerAppName_s` a
    # propósito, para explicar por qué NO se usa. Prohibir la palabra también
    # en los comentarios obligaría a borrar justo la explicación que evita que
    # alguien la reintroduzca.
    codigo = "\n".join(linea for _n, linea in _lineas_de_codigo(INFRA / SCRIPT))

    assert "ContainerJobName_s" in codigo
    assert "ContainerAppName_s" not in codigo
    assert "ContainerAppConsoleLogs_CL" in codigo


# ---------------------------------------------------------------------------
# R22 · El script de la alerta
# ---------------------------------------------------------------------------


def test_f024_r22_script_alerta_frescura_lee_de_cfg_y_sin_nombres() -> None:
    """Todo de `$CFG`. Ni un nombre de recurso, ni un correo, escrito aquí."""
    texto = _script(SCRIPT)

    for clave in CLAVES_QUE_LEE:
        assert f"$CFG.{clave}" in texto, f"el script no lee $CFG.{clave}"

    # Ningún valor concreto del entorno aparece escrito.
    cfg = _config("dev")
    for clave in ("resourceGroup", "logAnalytics", "job", "frescuraAlertName",
                  "alertActionGroupName", "alertActionGroupRg"):
        assert str(cfg[clave]) not in texto, (
            f"el script escribe el valor de '{clave}' en vez de leerlo de $CFG"
        )

    assert not re.search(PATRONES_PROHIBIDOS["dirección de correo"], texto), (
        "los destinatarios se resuelven contra el action group, nunca se escriben"
    )


def test_f024_r22_la_alerta_es_idempotente() -> None:
    """Si la regla ya existe, no se recrea. Igual que los otros doce scripts."""
    texto = _script(SCRIPT)

    assert re.search(r"scheduled-query\s+show", texto), (
        "no se comprueba si la regla ya existe antes de crearla"
    )
    assert re.search(r"scheduled-query\s+create", texto)


def test_f024_r22_la_ventana_sale_del_umbral_y_no_es_iso_8601() -> None:
    """La ventana se deriva de `frescuraUmbralHoras`, en formato `##h##m##s`.

    Confirmado con `--help` en T3: `az monitor scheduled-query` NO admite
    ISO 8601 aquí. Un `PT30H` se rechaza al crear la regla, y el script no se
    ejecuta contra Azure sin haberlo confirmado.
    """
    texto = _script(SCRIPT)

    assert "$CFG.frescuraUmbralHoras" in texto
    assert "--window-size" in texto

    ventana = re.search(r"--window-size\s+(\S+)", texto)
    assert ventana is not None
    assert not ventana.group(1).startswith("PT"), (
        "la ventana está en ISO 8601 y az la rechaza; el formato es ##h##m##s"
    )

    # Se compone a partir del umbral, no se escribe un 30 a mano.
    assert re.search(r'"\{0\}h"\s+-f|"\$\(\$?horas\)h"|"\$\{?horas\}?h"', texto), (
        "la ventana no se deriva del umbral: escribir el número a mano es "
        "exactamente lo que hace que la alerta y check-frescura diverjan"
    )

    assert re.search(r"--evaluation-frequency\s+1h", texto), (
        "la regla debe evaluarse cada hora"
    )


def test_f024_r22_la_alerta_dispara_por_ausencia_y_se_desactiva_sola() -> None:
    """`count < 1`: lo que se vigila es la AUSENCIA del evento.

    Una regla que buscara «el último evento» no dispararía nunca cuando no hay
    eventos, que es justo el caso a detectar.
    """
    texto = _script(SCRIPT)

    condicion = re.search(r'--condition\s+"([^"]+)"', texto)
    assert condicion is not None, "no hay --condition"
    assert re.search(r"count\s+\S+\s*<\s*1", condicion.group(1)), condicion.group(1)

    assert re.search(r"--severity\s+2", texto), "severidad 2 (R22.4)"
    assert re.search(r"--auto-mitigate\s+true", texto), (
        "sin auto-mitigación no llega el 'Deactivated' cuando vuelve a haber carga"
    )


def test_f024_r22_script_alerta_frescura_bom_crlf_cabecera() -> None:
    """UTF-8 con BOM, CRLF y primera línea con su ruta (docs/CONVENTIONS.md).

    Lo comprueba también el test genérico de F-003 sobre todos los `.ps1`; se
    repite aquí para que el fallo señale a este script y a esta feature.
    """
    ruta = INFRA / SCRIPT
    crudo = ruta.read_bytes()

    assert crudo.startswith(b"\xef\xbb\xbf"), "no está en UTF-8 con BOM"
    assert b"\r\n" in crudo, "no usa CRLF"
    assert not re.search(rb"(?<!\r)\n", crudo), "mezcla LF y CRLF"
    assert _texto(ruta).splitlines()[0] == f"# infra/{SCRIPT}"


def test_f024_r22_ninguna_variable_se_llama_como_las_de_00_vars() -> None:
    """`00_vars.ps1` define `$TAG`, `$IMG`, `$SUB`, `$CFG` y `$PG_SERVER`.

    Se carga con dot-sourcing DESPUÉS de los parámetros, así que una variable
    propia con uno de esos nombres se machaca sin avisar. Le pasó de verdad a
    `80_create_job.ps1` con `-Tag`, y costó una imagen desplegada con el tag
    equivocado.
    """
    texto = _script(SCRIPT)
    reservadas = ("TAG", "IMG", "SUB", "CFG", "PG_SERVER", "BUILD_DATE")

    for nombre in reservadas:
        asignacion = re.search(rf"(?m)^\s*\${nombre}\s*=", texto)
        assert asignacion is None, (
            f"el script asigna ${nombre}, que ya define 00_vars.ps1 y se "
            f"machacaría al cargarlo"
        )
        parametro = re.search(rf"(?im)^\s*\[\w+.*\]\s*\${nombre}\b", texto)
        assert parametro is None, f"hay un parámetro llamado ${nombre}"


def test_f024_r22_readme_documenta_el_script_en_orden() -> None:
    """El README lista los scripts en orden de ejecución: el 95 va tras el 90."""
    readme = _texto(INFRA / "README.md")

    assert SCRIPT in readme, f"{SCRIPT} no está documentado en infra/README.md"
    assert readme.index("90_create_alert.ps1") < readme.index(SCRIPT)

    # Y explica el paso previo que no es un script.
    assert "scheduled-query" in readme, (
        "el README no dice que hay que instalar la extensión de az una vez"
    )


def test_f024_r22_dev_json_declara_umbral_y_nombre() -> None:
    cfg = _config("dev")

    assert cfg["frescuraUmbralHoras"] == 30, "DA-4: el umbral acordado son 30 h"
    assert cfg["frescuraAlertName"], "falta el nombre de la regla de frescura"
    # Nombre de recurso, no un correo ni un identificador.
    assert not re.search(PATRONES_PROHIBIDOS["dirección de correo"], cfg["frescuraAlertName"])


def test_f024_r22_el_script_esta_en_la_lista_de_los_ps1() -> None:
    """Contraste: si el fichero no existiera, los tests de arriba que leen su
    texto fallarían con FileNotFoundError en vez de decir qué falta."""
    assert SCRIPT in [p.name for p in _ps1()]
