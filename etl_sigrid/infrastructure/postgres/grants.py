# etl_sigrid/infrastructure/postgres/grants.py
"""
Generación de las sentencias de permisos del rol de solo lectura (el del MCP).

Por qué esto es Python y no un fichero .sql: haría falta un bloque
`DO $$ ... $$` con el nombre del rol parametrizado, y `_split_sql_statements`
de `postgres_client.py` no sabe manejar `$$` — está escrito en su propio
docstring. Generarlo aquí evita la trampa y hace la unidad comprobable sin BBDD.

Por qué hay que reaplicarlos en cada ejecución: siete ficheros SQL de `mart`,
`cierre` y `compras` hacen `DROP VIEW ... CASCADE` seguido de `CREATE VIEW`, y
un DROP se lleva por delante los GRANT concedidos sobre esa vista. El
`ALTER DEFAULT PRIVILEGES` cubre lo que se cree DESPUÉS, no lo ya existente:
son complementarios, no alternativos.

TABLAS EXCLUIDAS (F-068, 2026-09-07), Y ESTO ES TEMPORAL:
`GRANT SELECT ON ALL TABLES IN SCHEMA raw` no sabe saltarse una tabla, así que
la única forma de dejar `raw.emp` y `raw.res` fuera del alcance del MCP es
conceder el esquema y REVOCAR después, en la misma tanda y en ese orden. La
lista vive en `config/settings.py` (`DEFAULT_EXCLUDED_TABLES`), que es donde
está escrito el porqué y la condición bajo la cual el humano ya ha decidido
levantarlo: que el MCP tenga control por usuario.

ESQUEMAS VETADOS Y ROL AUTORIZADO (F-135, 2026-10-11): la contabilidad COMPLETA
(`contabilidad_restringida`, con los apuntes de personal) y `raw` entero quedan
fuera del rol general. A diferencia de las tablas excluidas, aquí se veta el
ESQUEMA: sus tablas, su USAGE y su privilegio por defecto. Y el rol autorizado
(`sigrid_dm_restringido_ro`) recibe la lectura de la contabilidad completa. Las
dos listas de sentencias se generan aparte de `build_readonly_grant_statements`,
que no cambia (F-068 intacto): quien las ejecuta pone los vetos DETRÁS.
"""

from __future__ import annotations

from collections.abc import Sequence

from psycopg import sql


def partir_tabla_cualificada(entrada: str) -> tuple[str, str]:
    """
    `'raw.emp'` -> `('raw', 'emp')`, y revienta si no tiene esa forma.

    Falla ruidosamente a propósito. Una exclusión mal escrita que se ignorase
    en silencio dejaría los datos personales legibles con la parametrización
    puesta y con toda la pinta de estar protegidos, que es el peor desenlace
    posible de esta feature.
    """
    partes = entrada.split(".")
    if len(partes) != 2 or not all(p.strip() for p in partes):
        raise ValueError(
            f"tabla excluida mal declarada: {entrada!r}. Se espera "
            f"'esquema.tabla' (por ejemplo 'raw.emp')."
        )
    return partes[0].strip(), partes[1].strip()


def build_readonly_grant_statements(
    readonly_role: str,
    owner_role: str,
    schemas: Sequence[str],
    *,
    database: str | None = None,
    excluded_tables: Sequence[str] = (),
    missing_tables: Sequence[str] = (),
) -> list[str]:
    """
    Sentencias que dejan a `readonly_role` con lectura sobre `schemas`.

    Función pura: devuelve texto SQL con los identificadores ya citados, sin
    tocar ninguna conexión.

    `owner_role` es el rol de grupo propietario de los objetos. Se necesita
    para `ALTER DEFAULT PRIVILEGES FOR ROLE`, porque los privilegios por
    defecto se declaran POR rol creador: si el ETL crea las vistas como
    `sigrid_dm_etl`, la regla tiene que estar puesta para ese rol y no para
    quien ejecute este código. Si viene vacío, se omite la cláusula `FOR ROLE`
    y la regla aplica al rol de la sesión (caso de desarrollo local).

    `excluded_tables` son tablas `esquema.tabla` que el rol NO puede leer
    aunque su esquema esté en `schemas` (F-068). Se ignoran las que caen en un
    esquema que no se concede: si mañana se saca `raw` de la lista de consumo,
    no hay nada que revocar. Tienen dos efectos en el SQL generado, y los dos
    hacen falta:

      - un `REVOKE ALL PRIVILEGES ON TABLE` por tabla, emitido DESPUÉS de todos
        los GRANT, porque el GRANT del esquema la alcanza;
      - el esquema que tenga alguna exclusión cambia su `ALTER DEFAULT
        PRIVILEGES` de GRANT a REVOKE. Esa regla vive en el catálogo: mientras
        esté puesta, una tabla que nazca en ese esquema es legible sin que
        nadie ejecute un GRANT, y dejar de emitirla NO la borra. Hay que
        emitir su REVOKE.

    `missing_tables` son las de `excluded_tables` que HOY no existen en la
    base. Solo se les quita el `REVOKE ... ON TABLE`, que fallaría sobre una
    tabla ausente; la regla del catálogo se emite igual, porque se declara
    sobre el ESQUEMA y es precisamente la que protege a la tabla que todavía
    no ha nacido. Las dos listas van separadas por eso: derivar los esquemas
    con exclusión de las tablas existentes desactivaba la protección justo en
    el escenario para el que se diseñó —tras un `DROP` de `raw.emp` la
    nocturna reponía el GRANT por defecto y la siguiente `raw.emp` nacía
    legible— (agujero cazado en la revisión de F-068, 2026-09-08).

    El defecto es el seguro: quien no diga qué falta, revoca todo lo
    declarado. Equivocarse por ahí da un error contra la BBDD, ruidoso; al
    revés dejaría la tabla legible en silencio.
    """
    ro = sql.Identifier(readonly_role)
    sentencias: list[sql.Composable] = []

    # Se valida la lista ENTERA antes de generar nada, incluidas las entradas
    # de un esquema que no se concede: una entrada mal escrita es un error de
    # configuración y se denuncia siempre, no solo cuando toca revocar.
    excluidas = [partir_tabla_cualificada(t) for t in excluded_tables]
    aplicables = [(esq, tab) for esq, tab in excluidas if esq in set(schemas)]

    # Los esquemas con exclusión salen de lo DECLARADO, no de lo que exista
    # hoy: la regla del catálogo no necesita la tabla para valer, y quitarla
    # cuando la tabla no está es justo lo contrario de lo que hace falta.
    esquemas_con_exclusion = {esq for esq, _ in aplicables}

    # Lo que sí necesita la tabla presente es el REVOKE tabla a tabla.
    ausentes = {partir_tabla_cualificada(t) for t in missing_tables}
    revocables = [par for par in aplicables if par not in ausentes]

    if database:
        sentencias.append(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), ro
            )
        )

    for esquema in schemas:
        esq = sql.Identifier(esquema)
        sentencias.append(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(esq, ro))
        sentencias.append(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(esq, ro)
        )
        excluido = esquema in esquemas_con_exclusion
        if owner_role:
            if excluido:
                plantilla = (
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                    "REVOKE SELECT ON TABLES FROM {}"
                )
            else:
                plantilla = (
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                    "GRANT SELECT ON TABLES TO {}"
                )
            sentencias.append(
                sql.SQL(plantilla).format(sql.Identifier(owner_role), esq, ro)
            )
        else:
            if excluido:
                plantilla = (
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
                    "REVOKE SELECT ON TABLES FROM {}"
                )
            else:
                plantilla = (
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
                    "GRANT SELECT ON TABLES TO {}"
                )
            sentencias.append(sql.SQL(plantilla).format(esq, ro))

    # Al final del todo: el GRANT del esquema ya ha pasado y esto lo deshace
    # tabla a tabla. En el orden contrario no serviría de nada.
    for esquema, tabla in revocables:
        sentencias.append(
            sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
                sql.Identifier(esquema, tabla), ro
            )
        )

    return [s.as_string(None) for s in sentencias]


def esquemas_en_conflicto(consumo: Sequence[str], vetados: Sequence[str]) -> list[str]:
    """Los esquemas que están a la vez en la lista de consumo y en la de vetados.

    En el orden en que aparecen en `consumo` y sin repetir. No vacía significa
    una configuración contradictoria —típicamente un `.env` viejo que aún
    lista `raw`— y quien llama debe parar sin ejecutar nada (F-135, R17): un
    GRANT y su REVOKE en la misma tanda dejan el resultado al orden de las
    sentencias, que es justo lo que no se quiere confiar a la suerte.
    """
    vetado = set(vetados)
    conflicto: list[str] = []
    for esquema in consumo:
        if esquema in vetado and esquema not in conflicto:
            conflicto.append(esquema)
    return conflicto


def build_veto_statements(
    readonly_role: str,
    owner_role: str,
    vetoed_schemas: Sequence[str],
) -> list[str]:
    """Sentencias que dejan a `readonly_role` SIN lectura sobre `vetoed_schemas`.

    Función pura. Por esquema, tres sentencias y las tres hacen falta:

      - `REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA`: lo concedido tabla a
        tabla (o por el `GRANT ... ON ALL TABLES` de una noche anterior);
      - `REVOKE ALL PRIVILEGES ON SCHEMA`: sin USAGE no se llega a ninguna tabla,
        tampoco a la que nazca mañana;
      - `ALTER DEFAULT PRIVILEGES ... REVOKE ALL ON TABLES`: la regla del
        catálogo que haría legible una tabla recién creada (F-068).

    OJO, la lección de F-068: un REVOKE solo quita lo concedido por EL MISMO
    concedente. Lo que concedió el administrador a mano no lo quita la
    nocturna; por eso el paso COMPRUEBA después en el catálogo (R18), y
    `infra/sql/02_roles.sql` revoca con los dos concedentes.
    """
    ro = sql.Identifier(readonly_role)
    sentencias: list[sql.Composable] = []
    for esquema in vetoed_schemas:
        esq = sql.Identifier(esquema)
        sentencias.append(
            sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} FROM {}").format(esq, ro)
        )
        sentencias.append(
            sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA {} FROM {}").format(esq, ro)
        )
        if owner_role:
            sentencias.append(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                    "REVOKE ALL ON TABLES FROM {}"
                ).format(sql.Identifier(owner_role), esq, ro)
            )
        else:
            sentencias.append(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE ALL ON TABLES FROM {}"
                ).format(esq, ro)
            )
    return [s.as_string(None) for s in sentencias]


def build_restricted_grant_statements(
    restricted_role: str,
    owner_role: str,
    schemas: Sequence[str],
) -> list[str]:
    """Sentencias que dan al rol AUTORIZADO lectura sobre `schemas` (F-135, R15).

    Función pura. USAGE, SELECT sobre lo que existe y el privilegio por defecto
    para lo que nazca (el build hace DROP + CREATE cada noche). `owner_role`,
    como en `build_readonly_grant_statements`: vacío, la regla aplica al rol de
    la sesión. Solo lectura: ni INSERT, ni ALL PRIVILEGES.
    """
    rol = sql.Identifier(restricted_role)
    sentencias: list[sql.Composable] = []
    for esquema in schemas:
        esq = sql.Identifier(esquema)
        sentencias.append(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(esq, rol))
        sentencias.append(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(esq, rol)
        )
        if owner_role:
            sentencias.append(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                    "GRANT SELECT ON TABLES TO {}"
                ).format(sql.Identifier(owner_role), esq, rol)
            )
        else:
            sentencias.append(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {}"
                ).format(esq, rol)
            )
    return [s.as_string(None) for s in sentencias]
