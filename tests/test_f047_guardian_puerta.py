# tests/test_f047_guardian_puerta.py
"""
F-047 · El guardián como PUERTA: el comando y este repositorio de verdad.

`test_f047_guardian.py` prueba la lógica con inventarios de mentira. Aquí se
ejercita lo otro: el comando `check-declarados` con el inventario REAL de este
repositorio y los pendientes REALES, y el trinquete de
`config/objetos_pendientes.yaml`.

El único doble es `PostgresClient`. Cargar el inventario, leer los pendientes,
comparar y formatear se ejecuta de verdad: el cuerpo de un comando es código, y
dejarlo fuera de la suite es lo que ya convirtió 64 líneas sin cubrir en paisaje
(lección de la 12ª pasada de F-006). Ni red ni BBDD.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from etl_sigrid.infrastructure.inventario_repositorio import (
    YAML_PENDIENTES,
    cargar_pendientes_construccion,
    inventario_del_repositorio,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"

#: EL TRINQUETE de F-047, mismo criterio que `PENDIENTES_MAX` en
#: `tests/test_f006_cobertura.py`: cuántos objetos declara el repositorio y
#: todavía no toca construir. **Solo baja.** Hoy vale 0, y eso es un dato: los
#: diez pasos de `run-all` construyen los 103 objetos declarados.
PENDIENTES_CONSTRUCCION_MAX = 0


class _PgCatalogoFalso:
    def __init__(self, catalogo) -> None:
        self.catalogo = catalogo
        self.esquemas_pedidos: list[str] | None = None

    def list_objetos_catalogo(self, schemas):
        self.esquemas_pedidos = list(schemas)
        return self.catalogo


def _catalogo_de_todo_lo_declarado() -> list[tuple[str, str, str]]:
    """Un catálogo que contiene EXACTAMENTE lo que el repositorio declara."""
    return [
        (objeto.esquema, objeto.objeto, objeto.tipo)
        for objeto in inventario_del_repositorio()
    ]


def _runner(monkeypatch, pg) -> CliRunner:
    import main

    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    return CliRunner()


# ---------------------------------------------------------------------------
# R8 · el comando
# ---------------------------------------------------------------------------


def test_f047_r8_cli_con_todo_construido_sale_con_cero(monkeypatch) -> None:
    import main

    pg = _PgCatalogoFalso(_catalogo_de_todo_lo_declarado())
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-declarados"])

    assert resultado.exit_code == 0, resultado.output
    assert "OK" in resultado.output
    assert pg.esquemas_pedidos is not None and len(pg.esquemas_pedidos) == 9


def test_f047_r8_cli_detecta_la_vista_que_la_nocturna_destruia(monkeypatch) -> None:
    """EL CASO REAL, con el inventario y los pendientes de verdad.

    El 2026-08-26 `check-diccionario` daba 103 fichas y 102 objetos y hacía
    falta que alguien lo mirase a mano. Esto sale con código 1.
    """
    import main

    catalogo = [
        fila
        for fila in _catalogo_de_todo_lo_declarado()
        if fila[1] != "v_pbi_planif_vs_real"
    ]
    pg = _PgCatalogoFalso(catalogo)
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-declarados"])

    assert resultado.exit_code == 1
    assert "DECLARADO Y NO CONSTRUIDO" in resultado.output
    assert "cierre.v_pbi_planif_vs_real" in resultado.output
    assert "06_views_planif_vs_real.sql" in resultado.output


def test_f047_r8_cli_una_tabla_de_raw_sin_ingerir_tambien_se_ve(monkeypatch) -> None:
    """`raw` entra en el contraste. Sus tablas no salen de `sql/**` sino de
    `config/tables_sigrid.yaml`, y una ingesta que dejara de crearlas sería
    igual de invisible que la vista de `cierre`."""
    import main

    catalogo = [fila for fila in _catalogo_de_todo_lo_declarado() if fila[0] != "raw"]
    pg = _PgCatalogoFalso(catalogo)
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-declarados"])

    assert resultado.exit_code == 1
    assert "raw." in resultado.output
    assert "config/tables_sigrid.yaml" in resultado.output


def test_f047_r8_cli_no_escribe_nada_en_la_base(monkeypatch) -> None:
    """Es de SOLO LECTURA: el doble no ofrece ningún método de escritura, así
    que cualquier intento reventaría el test."""
    import main

    pg = _PgCatalogoFalso(_catalogo_de_todo_lo_declarado())
    resultado = _runner(monkeypatch, pg).invoke(main.cli, ["check-declarados"])

    assert resultado.exit_code == 0, resultado.output


# ---------------------------------------------------------------------------
# R6 · el trinquete sobre ESTE repositorio
# ---------------------------------------------------------------------------


def test_f047_r6_el_trinquete_vale_lo_que_hay_declarado() -> None:
    """La constante y la lista se comprueban una contra otra.

    Es la defensa que el trinquete de F-006 tuvo que añadir tras una review:
    subir la lista y el tope a la vez pasaba en verde.
    """
    pendientes = cargar_pendientes_construccion()

    assert len(pendientes) == PENDIENTES_CONSTRUCCION_MAX, (
        f"`config/objetos_pendientes.yaml` declara {len(pendientes)} pendientes "
        f"y la constante vale {PENDIENTES_CONSTRUCCION_MAX}: ajústala en la "
        f"misma tarea que construya el objeto. El trinquete solo baja"
    )


def test_f047_r6_los_pendientes_declarados_existen_en_el_repositorio() -> None:
    """Un pendiente que ningún SQL declara aplaza humo y engorda el trinquete."""
    declarados = {objeto.nombre for objeto in inventario_del_repositorio()}

    fantasmas = sorted(set(cargar_pendientes_construccion()) - declarados)

    assert fantasmas == [], f"{fantasmas} no los crea ningún SQL del repositorio"


def test_f047_r8_control_el_inventario_no_esta_vacio() -> None:
    """Un inventario vacío dejaría la puerta verde sin comprobar nada.

    Es el modo de fallo silencioso de estas puertas: si mañana cambia la ruta
    del SQL, el `rglob` no encuentra nada y todo queda en OK.
    """
    inventario = inventario_del_repositorio()

    assert len(inventario) >= 90, f"solo se inventariaron {len(inventario)}"
    assert {"mart", "cierre", "compras", "retenciones", "maestro", "stg", "raw",
            "aux", "_meta"} <= {o.esquema for o in inventario}


def test_f047_r8_sin_el_fichero_de_pendientes_no_se_finge_una_lista_vacia() -> None:
    """Devolver `()` sería la dirección SEGURA para la puerta —más estricta— y
    aun así está mal: convierte «alguien borró la configuración» en «todo
    correcto», que es el modo de fallo que esta feature existe para impedir."""
    with pytest.raises(OSError):
        cargar_pendientes_construccion(RAIZ / "config" / "no_existe_este.yaml")


def test_f047_r8_un_fichero_sin_clave_pendientes_es_lista_vacia(tmp_path) -> None:
    """Así es como se escribe «no hay ninguno», y tiene que valer."""
    ruta = tmp_path / "vacio.yaml"
    ruta.write_text("# sin nada\n", encoding="utf-8")

    assert cargar_pendientes_construccion(ruta) == ()


def test_f047_r8_el_fichero_de_pendientes_esta_versionado() -> None:
    """Un trinquete que no está en git no es un trinquete: no deja diff."""
    hecho = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "config/objetos_pendientes.yaml"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
    )

    assert hecho.returncode == 0, "config/objetos_pendientes.yaml no está en git"
    assert YAML_PENDIENTES.exists()


# ---------------------------------------------------------------------------
# El límite conocido del parseo, vigilado en vez de solo documentado
# ---------------------------------------------------------------------------


def test_f047_r8_no_hay_vistas_materializadas_que_el_guardian_no_sepa_ver() -> None:
    """`objetos_de_sql` reconoce `CREATE MATERIALIZED VIEW`, pero una vista
    materializada NO aparece en `information_schema.tables`: el guardián la
    daría por no construida cada noche.

    Hoy no hay ninguna. El día que alguien escriba la primera, esto se pone rojo
    y le manda ampliar la consulta del catálogo, en vez de dejarle un falso
    positivo a las tres de la mañana. Documentar el límite sin vigilarlo es
    confiar en que quien añada la vista lea el docstring de otro módulo.
    """
    patron = re.compile(r"CREATE\s+(OR\s+REPLACE\s+)?MATERIALIZED\s+VIEW", re.I)

    culpables = sorted(
        str(ruta.relative_to(DIR_SQL)).replace("\\", "/")
        for ruta in DIR_SQL.rglob("*.sql")
        if patron.search(ruta.read_text(encoding="utf-8"))
    )

    assert culpables == [], (
        f"{culpables} crean vistas materializadas: `check-declarados` las daría "
        f"por no construidas. Hay que ampliar SQL_OBJETOS_CATALOGO con "
        f"`pg_matviews` antes de fusionar esto"
    )


def test_f047_r8_el_ddl_condicional_de_retenciones_no_es_falso_positivo() -> None:
    """El otro caso raro del árbol, comprobado en vez de supuesto.

    `retenciones/00_setup.sql` crea dos vistas dentro de un `EXECUTE` con un
    `IF/ELSE` según exista `raw.dcfpro`. Las DOS ramas crean el MISMO objeto con
    el MISMO tipo, así que el objeto existe pase lo que pase y el guardián no
    puede equivocarse. Si algún día una rama dejara de crearlo, esto avisa.
    """
    texto = (DIR_SQL / "retenciones" / "00_setup.sql").read_text(encoding="utf-8")

    for vista in ("v_src_lineas_compra", "v_src_lineas_venta"):
        creaciones = re.findall(
            rf"CREATE\s+VIEW\s+retenciones\.{vista}\b", texto, re.I
        )
        assert len(creaciones) == 2, (
            f"{vista} se crea {len(creaciones)} vez/veces: el DDL condicional "
            f"tiene dos ramas y las dos tienen que crearla"
        )
