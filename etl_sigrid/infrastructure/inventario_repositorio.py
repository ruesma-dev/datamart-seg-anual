# etl_sigrid/infrastructure/inventario_repositorio.py
"""
Lee del disco lo que este repositorio declara publicar, y qué de eso se aplaza.

Es el adaptador de ficheros de `etl_sigrid.domain.inventario`, que es dominio
puro y recibe textos ya leídos. Aquí vive lo único que ese módulo no puede
hacer: abrir `sql/**` y `config/tables_sigrid.yaml`.

**Por qué existe teniendo ya el código repetido en tres sitios.** La misma
docena de líneas estaba copiada en `publicar_diccionario_step._inventario` y en
`tests/test_f006_cobertura._inventario_del_repositorio`, y F-047 necesitaba una
tercera copia para el comando `check-declarados`. Tres copias de «qué publica
este repositorio» son tres respuestas que pueden divergir, y la divergencia
sería invisible: cada puerta seguiría en verde contra su propio inventario.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from etl_sigrid.domain.inventario import ObjetoPublicado, objetos_de_raw, objetos_de_sql

RAIZ = Path(__file__).resolve().parents[2]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
YAML_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
YAML_PENDIENTES = RAIZ / "config" / "objetos_pendientes.yaml"


def inventario_del_repositorio(
    dir_sql: Path | None = None, yaml_tablas: Path | None = None
) -> list[ObjetoPublicado]:
    """Los objetos que este repositorio publica, leídos de sus propios ficheros.

    `raw` no sale de `sql/**`: sus tablas las crea `ensure_raw_table` desde
    Python y el inventario se deduce de `config/tables_sigrid.yaml`.

    Es una **heurística** (R29) y hay que decirlo: lee SQL con expresiones
    regulares y puede no ver un objeto creado por una vía que la expresión no
    contemple. La fuente que dice la verdad es el catálogo de la base.
    """
    dir_sql = DIR_SQL if dir_sql is None else dir_sql
    yaml_tablas = YAML_TABLAS if yaml_tablas is None else yaml_tablas

    textos = {
        str(ruta.relative_to(dir_sql)).replace("\\", "/"): ruta.read_text(
            encoding="utf-8"
        )
        for ruta in dir_sql.rglob("*.sql")
    }
    tablas = yaml.safe_load(yaml_tablas.read_text(encoding="utf-8"))["tables"]
    return objetos_de_sql(textos) + objetos_de_raw(tablas)


def cargar_pendientes_construccion(ruta: Path | None = None) -> tuple[str, ...]:
    """Los objetos declarados que todavía no toca construir (F-047).

    NO se tolera que el fichero falte. Devolver una lista vacía sería la
    dirección segura para la puerta —más estricta, no menos—, pero convertiría
    «alguien borró la configuración» en «todo correcto», y ese es justo el modo
    de fallo que esta feature existe para impedir. Un `pendientes:` ausente o
    nulo sí vale y significa lista vacía: es como se escribe «no hay ninguno».
    """
    ruta = YAML_PENDIENTES if ruta is None else ruta
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return tuple(datos.get("pendientes") or ())
