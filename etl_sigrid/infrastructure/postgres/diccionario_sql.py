# etl_sigrid/infrastructure/postgres/diccionario_sql.py
"""
Constructores puros de las sentencias y las filas de la publicación (F-006).

Mismo patrón que `grants.py`: aquí no se toca ninguna conexión, solo se produce
texto SQL y tuplas listas para `executemany`. Así el contrato con `mcp-bbdd` se
puede comprobar entero sin una base delante, que es lo único que se puede hacer
desde este puesto: el `.env` apunta al servidor compartido con `albaranes` y
`partes` en producción.

Dos decisiones que conviene no deshacer sin leer el porqué:

* **El reemplazo es `DELETE` + `INSERT`, nunca `DROP` + `CREATE`.** Un `DROP` se
  lleva por delante los `GRANT` del rol del MCP, que es exactamente el problema
  que ya obliga a reaplicar permisos cada noche. Con `DELETE` las tablas
  sobreviven y los permisos también.
* **El JSONB se serializa con `sort_keys=True`.** Dos publicaciones del mismo
  YAML producen entonces el mismo texto byte a byte, así que un `diff` sobre la
  tabla enseña lo que cambió de verdad en vez de todo el JSON reordenado.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime

from etl_sigrid.domain.diccionario import Diccionario, Ficha
from etl_sigrid.domain.inventario import InformeCobertura

# ---------------------------------------------------------------------------
# Sentencias
# ---------------------------------------------------------------------------
#
# Van como constantes de módulo, igual que `SQL_OCUPACION_DISCO` en
# `postgres_client.py`, para que un test pueda leerlas sin ejecutarlas.

#: Vaciado previo. Es `DELETE` y no `TRUNCATE` a propósito, y el motivo no es la
#: transaccionalidad —en PostgreSQL `TRUNCATE` **sí** es transaccional—: es que
#: `TRUNCATE` toma un `ACCESS EXCLUSIVE` sobre la tabla, que **bloquea a los
#: lectores** hasta el commit. Un MCP consultando durante la publicación se
#: quedaría esperando, que es justo lo que este diseño evita. Con unos cientos
#: de filas, `DELETE` no cuesta nada y no bloquea a nadie.
SQL_BORRAR_DICCIONARIO = "DELETE FROM _meta.diccionario"
SQL_BORRAR_REGLAS = "DELETE FROM _meta.diccionario_reglas"
SQL_BORRAR_PUBLICACION = "DELETE FROM _meta.diccionario_publicacion"

SQL_INSERT_DICCIONARIO = """
INSERT INTO _meta.diccionario (
    esquema, objeto, tipo, capa, consumo_recomendado, motivo_no_consumo,
    descripcion, grano, clave_negocio, paso_etl, refresco, avisos,
    n_columnas, ficha
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

SQL_INSERT_REGLA = """
INSERT INTO _meta.diccionario_reglas (
    codigo, titulo, severidad, ambito, regla, motivo, orden
) VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

SQL_INSERT_PUBLICACION = """
INSERT INTO _meta.diccionario_publicacion (
    id, version, hash_fuente, publicado_en, batch_id,
    n_objetos, n_reglas, n_columnas, cobertura_cols
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

#: Catálogo real de la base, para `check-diccionario` (R28). Devuelve lo que el
#: servidor tiene de verdad, que es la única fuente que no es heurística.
SQL_OBJETOS_CATALOGO = """
SELECT table_schema, table_name,
       CASE WHEN table_type = 'VIEW' THEN 'vista' ELSE 'tabla' END
FROM information_schema.tables
WHERE table_schema = ANY(%s)
UNION ALL
SELECT n.nspname, p.proname, 'funcion'
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = ANY(%s)
ORDER BY 1, 2
"""


# ---------------------------------------------------------------------------
# Filas
# ---------------------------------------------------------------------------


def _ficha_json(ficha: Ficha) -> str:
    """El cuerpo de la ficha que no cabe en columnas, como JSON estable.

    Se omiten las claves sin valor en vez de publicarlas a nulo: son 332
    columnas y arrastrar `"unidad": null` en cada una es ruido que el consumidor
    tendría que filtrar. Lo que sí se conserva es el ORDEN del YAML, que es
    editorial —primero las claves, luego los importes— y el MCP lo sirve tal
    cual; por eso `sort_keys` ordena las claves de cada objeto pero las listas
    mantienen su secuencia.
    """
    columnas = []
    for columna in ficha.columnas:
        cuerpo: dict[str, object] = {
            "nombre": columna.nombre,
            "significado": columna.significado,
        }
        if columna.unidad:
            cuerpo["unidad"] = columna.unidad
        if columna.agregacion:
            cuerpo["agregacion"] = columna.agregacion
        if columna.valores:
            cuerpo["valores"] = list(columna.valores)
        if columna.nulo_significa:
            cuerpo["nulo_significa"] = columna.nulo_significa
        columnas.append(cuerpo)

    relaciones = [
        {
            "de": relacion.de,
            "a": relacion.a,
            "cardinalidad": relacion.cardinalidad,
            "porque": relacion.porque,
        }
        for relacion in ficha.relaciones
    ]

    return json.dumps(
        {
            "columnas": columnas,
            "relaciones": relaciones,
            "ejemplos_preguntas": list(ficha.ejemplos_preguntas),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def filas_diccionario(dicc: Diccionario) -> list[tuple]:
    """Una tupla por ficha, en orden estable de `esquema.objeto`.

    El orden no es estético: sin él, dos publicaciones del mismo diccionario
    escribirían las mismas filas en distinto orden y cualquier comparación entre
    entornos se volvería ruido.
    """
    return [
        (
            ficha.esquema,
            ficha.objeto,
            ficha.tipo,
            ficha.capa,
            bool(ficha.consumo_recomendado),
            ficha.motivo_no_consumo or None,
            ficha.descripcion,
            ficha.grano or None,
            list(ficha.clave_negocio),
            ficha.paso_etl or None,
            ficha.refresco,
            list(ficha.avisos),
            len(ficha.columnas),
            _ficha_json(ficha),
        )
        for ficha in sorted(dicc.fichas, key=lambda f: (f.esquema, f.objeto))
    ]


def filas_reglas(dicc: Diccionario) -> list[tuple]:
    """Una tupla por regla dura, en el orden en que se sirven al agente."""
    return [
        (
            regla.codigo,
            regla.titulo,
            regla.severidad,
            list(regla.ambito),
            regla.regla,
            regla.motivo,
            regla.orden,
        )
        for regla in sorted(dicc.reglas, key=lambda r: (r.orden, r.codigo))
    ]


def cobertura_columnas(dicc: Diccionario) -> float:
    """Porcentaje de columnas CON significado dentro de la superficie de consumo.

    Se mide solo sobre `consumo_recomendado: true` porque es donde R26 exige el
    100 %: fuera de ahí no se pide ninguna, y mezclarlas diluiría el número
    hasta hacerlo inútil. Sin columnas que medir, la cobertura es 100: no hay
    nada que falte.
    """
    de_consumo = [c for f in dicc.fichas if f.consumo_recomendado for c in f.columnas]
    if not de_consumo:
        return 100.0
    con_significado = sum(1 for c in de_consumo if (c.significado or "").strip())
    return round(100.0 * con_significado / len(de_consumo), 2)


def fila_publicacion(
    dicc: Diccionario,
    hash_fuente: str,
    ahora: datetime,
    batch_id: str | None,
    informe: InformeCobertura,
) -> tuple:
    """La fila única de `_meta.diccionario_publicacion`.

    `id = 1` siempre: la tabla es un singleton por `CHECK`, y es lo que permite
    responder «¿el diccionario que estás leyendo es el del repositorio?»
    comparando `hash_fuente` sin salir de SQL.

    `informe` entra en la firma aunque hoy solo se use para dejar constancia de
    que la publicación pasó por la evaluación de cobertura: publicar sin haberla
    evaluado sería publicar a ciegas.
    """
    del informe  # se exige haberlo calculado; el número lo da `cobertura_columnas`
    return (
        1,
        dicc.version,
        hash_fuente,
        ahora,
        batch_id,
        len(dicc.fichas),
        len(dicc.reglas),
        sum(len(f.columnas) for f in dicc.fichas),
        cobertura_columnas(dicc),
    )


def resumen_publicacion(fila: tuple) -> Mapping[str, object]:
    """Lo que el paso deja en `_meta.etl_runs.metadata` y en la salida del CLI."""
    return {
        "version": fila[1],
        "hash_fuente": fila[2],
        "n_objetos": fila[5],
        "n_reglas": fila[6],
        "n_columnas": fila[7],
        "cobertura_cols": float(fila[8]),
    }
