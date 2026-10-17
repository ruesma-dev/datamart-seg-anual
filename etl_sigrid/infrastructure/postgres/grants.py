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
(`sigrid_dm_autorizado_ro`) recibe la lectura de la contabilidad completa. Las
dos listas de sentencias se generan aparte de `build_readonly_grant_statements`,
que no cambia (F-068 intacto): quien las ejecuta pone los vetos DETRÁS.

EL PERFIL RESTRINGIDO (F-141, 2026-10-17): el tercer perfil, para
administrativos, que ve MENOS que el estándar («ven como el estándar, menos el
mayor, menos el mayor analítico, menos la cartera de cobros (pero sí a
retenciones)»; «personal también quítalo, y saldos cuenta también»). Su grupo
(`sigrid_dm_perfil_restringido_ro`) recibe lo suyo con
`build_perfil_restringido_statements`, cuyo privilegio por defecto es SIEMPRE un
REVOKE: lo que nazca no lo lee hasta que la nocturna lo haya mirado. Lo que NO
es suyo sale del catálogo (`esquemas_ajenos`) y se le veta con
`build_veto_statements`. Las vistas que leen lo que no ve son la trampa de dar
esquemas sueltos (una vista se ejecuta con los permisos de su dueño): se le
revocan y el paso falla, salvo las tres vistas de pago de `compras`, que el
humano quiere visibles (D4) y son una excepción NOMINAL.
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


# ---------------------------------------------------------------------------
# El perfil RESTRINGIDO (F-141)
# ---------------------------------------------------------------------------

#: Vistas del perfil restringido que leen un esquema que no ve y que el humano
#: quiere visibles igualmente (D4: «compras debe poder verse»). Por ellas ve el
#: ESTADO DE PAGO de sus facturas (si y cuándo se pagó, forma de pago) aunque no
#: lea la cartera. La excepción es NOMINAL y por esquema: si una de ellas lee
#: además otra cosa que no ve, eso sí es una filtración. Un test comprueba que
#: las tres siguen leyendo la cartera (si no, la excepción sobra).
EXCEPCIONES_FILTRACION_RESTRINGIDO: dict[str, str] = {
    "compras.vencimientos": "tesoreria",
    "compras.v_facturas_pago": "tesoreria",
    "compras.v_control_forma_pago": "tesoreria",
}

#: Lo que se vigila por NOMBRE en los esquemas del perfil: el mayor analítico no
#: está publicado todavía (lo publicará F-127, desde `raw.apa`). Si nace con
#: «mayor» en el nombre y nadie lo excluye, la nocturna se lo revoca y falla.
#: Si F-127 le pone otro nombre, su spec TIENE que añadirlo a
#: `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES`.
PATRON_VIGILADO_RESTRINGIDO = r"mayor"

#: Esquemas que las vistas curadas de `maestro` y `compras` leen sin que eso
#: sea una filtración: `raw` no lo lee el perfil, pero sus vistas sí, a
#: propósito (son la capa curada sobre la copia de Sigrid).
ESQUEMAS_ORIGEN_DE_VISTAS: tuple[str, ...] = ("raw",)

#: Las tablas de origen de los documentos de `compras.documento_adjuntos`, una
#: por familia (F-139, D1: quien lee los adjuntos tiene que poder leer sus
#: documentos). Un test la contrasta con `ORIGEN_POR_FAMILIA` de F-139.
TABLAS_ORIGEN_ADJUNTOS: tuple[str, ...] = (
    "compras.facturas",
    "compras.contratos",
    "compras.comparativos",
    "compras.comparativo_ofertas",
    "compras.albaranes",
)
OBJETO_ADJUNTOS = "compras.documento_adjuntos"

#: Esquemas del catálogo que nunca se le vetan al perfil: el sistema (todo lo
#: que empieza por `pg_`: `pg_catalog`, `pg_toast`, `pg_temp_N`..., nombres que
#: PostgreSQL reserva) y `public`, que está vacío y sin `CREATE` (PG 15+).
ESQUEMAS_DE_SISTEMA: tuple[str, ...] = ("information_schema", "public")
PREFIJO_DE_SISTEMA = "pg_"


def perfil_restringido_en_conflicto(
    esquemas: Sequence[str],
    *,
    consumo: Sequence[str],
    vetados: Sequence[str],
    restringidos: Sequence[str],
    total_vetados: Sequence[str],
) -> list[str]:
    """Los esquemas del perfil restringido que no puede tener (F-141, R5).

    Uno que no esté en el consumo (el perfil no puede ver MÁS que el estándar),
    o que esté vetado al estándar, sea de lo restringido o esté vetado al
    total. En el orden de `esquemas` y sin repetir; vacía es lo correcto.
    """
    prohibidos = set(vetados) | set(restringidos) | set(total_vetados)
    permitidos = set(consumo)
    conflicto: list[str] = []
    for esquema in esquemas:
        if (esquema not in permitidos or esquema in prohibidos) and esquema not in conflicto:
            conflicto.append(esquema)
    return conflicto


def excluidas_invalidas(excluidas: Sequence[str], esquemas: Sequence[str]) -> list[str]:
    """Los objetos excluidos mal escritos o de un esquema que no se concede (F-141, R7).

    Una exclusión que no apunta a nada protegido es casi siempre una errata, y
    callarla dejaría el objeto que se quería quitar legible con toda la pinta de
    estar protegido. En orden y sin repetir.
    """
    concedidos = set(esquemas)
    malas: list[str] = []
    for entrada in excluidas:
        try:
            esquema: str | None = partir_tabla_cualificada(entrada)[0]
        except ValueError:
            esquema = None
        if esquema not in concedidos and entrada not in malas:
            malas.append(entrada)
    return malas


def origenes_de_adjuntos_sin_leer(esquemas: Sequence[str], excluidas: Sequence[str]) -> list[str]:
    """Las tablas de origen de los adjuntos que el perfil no leería (F-141, R8).

    Solo cuenta si lee `compras.documento_adjuntos`: excluirla también cumple
    la regla de F-139 (D1). Vacía es lo correcto.
    """
    concedidos = set(esquemas)
    fuera = set(excluidas)
    if OBJETO_ADJUNTOS in fuera:
        return []
    return [
        tabla for tabla in TABLAS_ORIGEN_ADJUNTOS
        if tabla in fuera or tabla.split(".", 1)[0] not in concedidos
    ]


def esquemas_ajenos(catalogo: Sequence[str], esquemas: Sequence[str]) -> list[str]:
    """Los esquemas del CATÁLOGO que no son del perfil restringido (F-141, R12).

    Salen de lo que existe, no de la configuración: hoy `tesoreria`, `personal`,
    `raw` y las tres `*_restringida`; mañana, cualquier esquema que nadie haya
    listado. Sin los del sistema. Ordenados y sin repetir.
    """
    suyos = set(esquemas)
    return sorted({
        esquema for esquema in catalogo
        if esquema not in suyos
        and esquema not in ESQUEMAS_DE_SISTEMA
        and not esquema.startswith(PREFIJO_DE_SISTEMA)
    })


def separar_excepciones(
    filas: Sequence[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[str]]:
    """Aparta las excepciones de D4 de lo que devuelve el catálogo (F-141, R13 y R15).

    `filas` son pares (vista, objeto que alcanza), con nombres `esquema.objeto`.
    Devuelve las FILTRACIONES (los pares que no cubre una excepción, en su orden)
    y las excepciones SOBRANTES (las que ya no aparecen leyendo su esquema,
    ordenadas): que una sobre no expone nada, pero la lista nominal miente.
    """
    filtraciones: list[tuple[str, str]] = []
    vivas: set[str] = set()
    for vista, objeto in filas:
        esquema_objeto = objeto.split(".", 1)[0]
        if EXCEPCIONES_FILTRACION_RESTRINGIDO.get(vista) == esquema_objeto:
            vivas.add(vista)
        else:
            filtraciones.append((vista, objeto))
    sobrantes = sorted(set(EXCEPCIONES_FILTRACION_RESTRINGIDO) - vivas)
    return filtraciones, sobrantes


def build_perfil_restringido_statements(
    group_role: str,
    owner_role: str,
    schemas: Sequence[str],
    *,
    database: str | None = None,
    excluded: Sequence[str] = (),
    missing: Sequence[str] = (),
) -> list[str]:
    """Sentencias que dejan al grupo del perfil restringido con lo suyo (F-141, R11).

    Función pura. `GRANT CONNECT` (lo heredan sus miembros); por esquema USAGE y
    SELECT sobre lo que existe, y su privilegio por defecto SIEMPRE en REVOKE,
    nunca un GRANT: una tabla o vista que nazca mañana no la lee hasta que la
    nocturna la haya mirado (es lo que vigila las vistas que filtran). Al final,
    `REVOKE ALL` de cada objeto de `excluded` (los excluidos, las vistas que
    filtran y los vigilados) de un esquema concedido, salvo los de `missing`,
    que hoy no existen (un REVOKE sobre un objeto ausente falla). Sin repetir.
    """
    rol = sql.Identifier(group_role)
    sentencias: list[sql.Composable] = []
    concedidos = set(schemas)
    ausentes = {partir_tabla_cualificada(t) for t in missing}
    revocables: list[tuple[str, str]] = []
    for entrada in excluded:
        par = partir_tabla_cualificada(entrada)
        if par[0] in concedidos and par not in ausentes and par not in revocables:
            revocables.append(par)

    if database:
        sentencias.append(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), rol)
        )
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
                    "REVOKE SELECT ON TABLES FROM {}"
                ).format(sql.Identifier(owner_role), esq, rol)
            )
        else:
            sentencias.append(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE SELECT ON TABLES FROM {}"
                ).format(esq, rol)
            )
    for esquema, tabla in revocables:
        sentencias.append(
            sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
                sql.Identifier(esquema, tabla), rol
            )
        )
    return [s.as_string(None) for s in sentencias]
