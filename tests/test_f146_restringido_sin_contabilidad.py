# tests/test_f146_restringido_sin_contabilidad.py
"""
F-146 · El perfil RESTRINGIDO del MCP no ve NADA de contabilidad: fuera el esquema entero.

Decisión del humano del 2026-10-21. Hasta F-146 el restringido (F-141) tenía `contabilidad` en
su lista y excluía solo `contabilidad.mayor` y `contabilidad.saldos_cuenta_mes`: le quedaban
`contabilidad.plan_cuentas` y `contabilidad.apuntes_restringidos_mes`. Ahora `contabilidad` sale
de su lista y la nocturna se lo VETA como a `tesoreria` y `personal` (tablas, USAGE y privilegio
por defecto), porque lo que no es suyo sale del CATÁLOGO: una tabla nueva de `contabilidad` (el
mayor analítico de F-127, por ejemplo) no le llega. FUERA: `retenciones` (con
`retenciones.apuntes_contables`) lo sigue viendo; el estándar y el total no cambian.

Ningún test abre red ni BBDD: el cliente se simula.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
ESTANDAR = "mcp_sigrid_dm_ro"
AUTORIZADO = "sigrid_dm_autorizado_ro"
TOTAL = "mcp_sigrid_dm_total"
GRUPO = "sigrid_dm_perfil_restringido_ro"
LOGIN = "mcp_sigrid_dm_restringido"
DUENO = "sigrid_dm_etl"
CONTABILIDAD = "contabilidad"
#: lo que el perfil restringido no lee de la lista de consumo (F-141 y F-146)
VETADOS_AL_PERFIL = ("personal", "contabilidad", "tesoreria")
#: lo que hoy hay en `contabilidad` y una tabla que naciera mañana
TABLAS_CONTABILIDAD = (
    "contabilidad.plan_cuentas", "contabilidad.mayor", "contabilidad.saldos_cuenta_mes",
    "contabilidad.apuntes_restringidos_mes",
)
TABLA_NUEVA = "contabilidad.mayor_analitico"
VERSION_F146 = 58
DICC = RAIZ / "config" / "diccionario"
AVISO = "No disponible para el perfil restringido"


def _pg(**cambios: object):
    from config.settings import PostgresSettings

    base = {"readonly_role": ESTANDAR, "set_role": DUENO}
    base.update(cambios)
    return PostgresSettings(_env_file=None, **base)


# ===========================================================================
# R1 · la configuración: `contabilidad` fuera de la lista del perfil
# ===========================================================================


def test_f146_r1_contabilidad_no_esta_entre_los_esquemas_del_perfil() -> None:
    from config.settings import DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS

    assert CONTABILIDAD not in DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS.split(",")
    pg = _pg()
    assert CONTABILIDAD not in pg.perfil_restringido_schema_list
    assert pg.perfil_restringido_schema_list == [
        s for s in pg.consumption_schema_list if s not in VETADOS_AL_PERFIL
    ], "el consumo menos personal, contabilidad y tesoreria, en su orden"


def test_f146_r1_retenciones_sigue_dentro() -> None:
    """FUERA de F-146: el cuadre de retenciones necesita `retenciones.apuntes_contables`."""
    assert "retenciones" in _pg().perfil_restringido_schema_list


def test_f146_r1_la_lista_de_excluidas_queda_vacia() -> None:
    """Decisión: vaciarla. No puede quedar «como red»: R7 de F-141 rechaza una exclusión
    de un esquema que no se le concede, y la nocturna pararía en seco."""
    from config.settings import DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES
    from etl_sigrid.infrastructure.postgres.grants import excluidas_invalidas

    assert DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES == ""
    pg = _pg()
    assert pg.perfil_restringido_excluded_table_list == []
    viejas = ["contabilidad.mayor", "contabilidad.saldos_cuenta_mes"]
    assert excluidas_invalidas(viejas, pg.perfil_restringido_schema_list) == viejas


def test_f146_r1_env_example_al_dia() -> None:
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    lineas = dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )
    from config.settings import (
        DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES,
        DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS,
    )

    assert lineas["PG_PERFIL_RESTRINGIDO_SCHEMAS"] == DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS
    assert lineas["PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES"] == (
        DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES
    )
    bloque = texto.split("PG_PERFIL_RESTRINGIDO_GROUP=")[0].rsplit("\n\n", 1)[-1]
    assert "F-146" in bloque and "contabilidad" in bloque, "el porqué, delante de las variables"


def test_f146_r1_el_comentario_de_settings_explica_la_decision() -> None:
    texto = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
    bloque = texto.split("DEFAULT_PERFIL_RESTRINGIDO_GROUP =")[0].rsplit("\n\n", 1)[-1]
    plano = re.sub(r"\s*#\s*", " ", bloque)
    for cosa in ("F-146", "2026-10-21", "`contabilidad`", "F-127", "vac"):
        assert cosa in plano, f"el comentario no dice {cosa}"


# ===========================================================================
# R2 · la nocturna: veta `contabilidad` entera y una tabla nueva no le llega
# ===========================================================================


class _Cliente:
    """Cliente simulado con el catálogo de hoy MÁS una tabla nueva en `contabilidad`."""

    def __init__(self, indebidas: dict[str, list[str]] | None = None) -> None:
        pg = _pg()
        self.catalogo = [
            *pg.consumption_schema_list, *pg.vetoed_schema_list,
            "public", "pg_catalog", "information_schema", "pg_toast",
        ]
        #: objetos con «mayor» en el nombre que existen; el SQL real solo mira los esquemas pedidos
        self.mayores = ["contabilidad.mayor", TABLA_NUEVA, "contabilidad_restringida.mayor"]
        self.indebidas = indebidas or {}
        self.llamadas: list[tuple] = []

    def role_exists(self, role):
        return role in (ESTANDAR, AUTORIZADO, TOTAL, GRUPO, LOGIN)

    def list_schemas(self):
        return list(self.catalogo)

    def apply_readonly_grants(self, readonly_role, owner_role, schemas, excluded_tables=(),
                              vetoed_schemas=()):
        self.llamadas.append(("general", readonly_role, list(schemas), list(vetoed_schemas)))
        return ["G"]

    def apply_restricted_grants(self, role, owner_role, schemas):
        self.llamadas.append(("autorizado", role, list(schemas)))
        return ["A"]

    def apply_veto(self, role, owner_role, schemas):
        self.llamadas.append(("veto", role, list(schemas)))
        return ["V"] * len(list(schemas))

    def lecturas_indebidas(self, role, schemas, tables):
        self.llamadas.append(("verifica", role, list(schemas), list(tables)))
        return list(self.indebidas.get(role, []))

    def esquemas_sin_usage(self, role, schemas):
        self.llamadas.append(("usage", role, list(schemas)))
        return []

    def vistas_que_filtran(self, schemas, foreign_schemas, tables):
        self.llamadas.append(("filtran", list(schemas), list(foreign_schemas)))
        return [(v, "tesoreria.efectos") for v in
                ("compras.vencimientos", "compras.v_facturas_pago", "compras.v_control_forma_pago")]

    def objetos_vigilados(self, schemas, pattern):
        return [o for o in self.mayores if o.split(".", 1)[0] in schemas]

    def pertenencias(self, role):
        return [GRUPO] if role == LOGIN else []

    def apply_perfil_restringido(self, role, owner_role, schemas, revoked):
        self.llamadas.append(("perfil", role, list(schemas), list(revoked)))
        return ["R"]


def _paso(cliente: _Cliente):
    from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep

    return ApplyGrantsStep(SimpleNamespace(postgres=_pg()), client=cliente).run()


def _llamada(cliente: _Cliente, tipo: str, rol: str) -> tuple:
    (llamada,) = [c for c in cliente.llamadas if c[0] == tipo and c[1] == rol]
    return llamada


def test_f146_r2_la_nocturna_le_veta_contabilidad_entera() -> None:
    cliente = _Cliente()
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS", resultado.error_message
    _, _, esquemas, revocadas = _llamada(cliente, "perfil", GRUPO)
    assert CONTABILIDAD not in esquemas, "no se le concede el esquema"
    assert not [t for t in revocadas if t.startswith("contabilidad.")], (
        "ni excluidas tabla a tabla: el esquema entero es ajeno"
    )
    _, _, vetados = _llamada(cliente, "veto", GRUPO)
    assert CONTABILIDAD in vetados, "se le veta como a tesoreria y personal"
    assert {"tesoreria", "personal"} <= set(vetados)
    for quien in (GRUPO, LOGIN):
        _, _, ajenos, _ = _llamada(cliente, "verifica", quien)
        assert CONTABILIDAD in ajenos, f"la postcondición pregunta por contabilidad a {quien}"


def test_f146_r2_una_tabla_nueva_de_contabilidad_no_le_llega() -> None:
    """El mayor analítico de F-127 (u otra) naciendo en `contabilidad`: ni se le concede, ni
    es un «vigilado» que haga fallar la nocturna, ni la puede leer al nacer."""
    from etl_sigrid.infrastructure.postgres.grants import (
        build_perfil_restringido_statements,
        build_veto_statements,
    )

    cliente = _Cliente()
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS", resultado.error_message
    assert resultado.metadata["vigilados_restringido"] == "ok"
    _, _, vetados = _llamada(cliente, "veto", GRUPO)
    veto = build_veto_statements(GRUPO, DUENO, vetados)
    for sentencia in (
        f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA "contabilidad" FROM "{GRUPO}"',
        f'REVOKE ALL PRIVILEGES ON SCHEMA "contabilidad" FROM "{GRUPO}"',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "contabilidad" '
        f'REVOKE ALL ON TABLES FROM "{GRUPO}"',
    ):
        assert sentencia in veto, sentencia
    pg = _pg()
    concesion = build_perfil_restringido_statements(
        GRUPO, DUENO, pg.perfil_restringido_schema_list, database="sigrid_dm",
        excluded=pg.perfil_restringido_excluded_table_list,
    )
    assert not [s for s in concesion if "contabilidad" in s], concesion


def test_f146_r2_si_aun_lee_algo_de_contabilidad_la_nocturna_falla() -> None:
    """Una concesión que la nocturna no puede revocar (de otro concedente) no pasa
    inadvertida: la postcondición del catálogo la nombra y el paso termina en FAILED."""
    cliente = _Cliente(indebidas={LOGIN: [f"{TABLA_NUEVA} (SELECT)", "contabilidad (USAGE)"]})
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    assert f"'{LOGIN}' lee lo que no debe: {TABLA_NUEVA} (SELECT), contabilidad (USAGE)" in (
        resultado.error_message or ""
    )


def test_f146_r3_el_estandar_y_el_total_no_cambian() -> None:
    cliente = _Cliente()
    _paso(cliente)
    pg = _pg()
    _, _, consumo, vetados = _llamada(cliente, "general", ESTANDAR)
    assert CONTABILIDAD in consumo and CONTABILIDAD not in vetados, "el estándar la sigue leyendo"
    assert _llamada(cliente, "veto", TOTAL) == ("veto", TOTAL, ["raw"]), "al total, solo raw"
    _, _, usage_total = _llamada(cliente, "usage", TOTAL)
    assert CONTABILIDAD in usage_total and "contabilidad_restringida" in usage_total
    assert CONTABILIDAD in pg.consumption_schema_list
    assert CONTABILIDAD not in pg.vetoed_schema_list + pg.total_vetoed_schema_list


# ===========================================================================
# R4 · `infra/sql/02_roles.sql`: lo mismo al provisionar
# ===========================================================================


def _roles_sql() -> str:
    crudo = (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")
    return "\n".join(
        linea for linea in crudo.splitlines() if not linea.lstrip().startswith("--")
    )


def test_f146_r4_02_roles_no_le_concede_contabilidad() -> None:
    sql = _roles_sql()
    bucle = re.search(r"FOREACH esquema_r IN ARRAY ARRAY\[(.*?)\]", sql, re.DOTALL)
    assert bucle and "'contabilidad'" not in bucle.group(1)
    vetos = [m.start() for m in re.finditer(r"FOR ajeno_r IN", sql)]
    assert len(vetos) == 2
    for p in vetos:
        assert "'contabilidad'" not in sql[p:sql.index("LOOP", p)], (
            "el veto del catálogo tiene que alcanzar a contabilidad"
        )
    assert "FOREACH excluida_r" not in sql, "sin exclusiones que revocar"


def test_f146_r4_la_comprobacion_final_espera_f_en_contabilidad() -> None:
    final = _roles_sql().split("\nCOMMIT;", 1)[1]
    negativa = re.search(
        rf"SELECT has_schema_privilege\('{LOGIN}', 'tesoreria', 'USAGE'\).*?;", final, re.DOTALL,
    )
    assert negativa and f"has_schema_privilege('{LOGIN}', 'contabilidad', 'USAGE')" in (
        negativa.group(0)
    ), "contabilidad, entre lo que tiene que salir f"
    positiva = re.search(
        rf"SELECT has_schema_privilege\('{LOGIN}', 'mart', 'USAGE'\).*?;", final, re.DOTALL,
    )
    assert positiva and "'contabilidad'" not in positiva.group(0)
    for tabla in TABLAS_CONTABILIDAD:
        assert f"has_table_privilege('{LOGIN}', to_regclass('{tabla}'), 'SELECT')" in final, tabla


# ===========================================================================
# R5 · el diccionario: la IA tiene que responder que el perfil no la incluye
# ===========================================================================


def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DICC / nombre).read_text(encoding="utf-8"))


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def _regla() -> dict:
    (regla,) = [r for r in _yaml("00_global.yaml")["reglas"]
                if r["codigo"] == "R-PERFIL-RESTRINGIDO"]
    return regla


def _tablas_de_contabilidad() -> list[str]:
    objetos = _yaml("contabilidad.yaml")["objetos"]
    return [o for o, ficha in objetos.items() if ficha["tipo"] in ("tabla", "vista")]


def test_f146_r5_las_tablas_del_diccionario_son_las_de_hoy() -> None:
    assert sorted(f"contabilidad.{o}" for o in _tablas_de_contabilidad()) == sorted(
        TABLAS_CONTABILIDAD
    )


@pytest.mark.parametrize("objeto", ["plan_cuentas", "mayor", "saldos_cuenta_mes",
                                    "apuntes_restringidos_mes"])
def test_f146_r5_cada_ficha_de_contabilidad_empieza_por_el_aviso(objeto: str) -> None:
    descripcion = _yaml("contabilidad.yaml")["objetos"][objeto]["descripcion"]
    primera = _plano(descripcion.split("\n", 1)[0])
    assert primera.startswith(f"**{AVISO}**"), primera
    assert "permission denied" in primera and "`R-PERFIL-RESTRINGIDO`" in primera
    assert "F-146" in primera and "el perfil no lo incluye" in primera


def test_f146_r5_la_regla_dice_que_no_ve_nada_de_contabilidad() -> None:
    regla = _regla()
    texto = _plano(regla["regla"])
    for termino in ("el esquema `contabilidad` entero", "`retenciones`",
                    "`retenciones.apuntes_contables`", "el perfil no lo incluye"):
        assert termino in texto, f"la regla no dice «{termino}»"
    si_lee = texto.split("SI lee", 1)[1].split("OJO AL NOMBRE", 1)[0]
    assert "contabilidad" not in si_lee, f"la regla aún le da algo de contabilidad: {si_lee}"
    assert CONTABILIDAD in regla["ambito"]
    motivo = _plano(regla["motivo"])
    assert "2026-10-21" in motivo and "F-146" in motivo


def test_f146_r5_ningun_texto_del_diccionario_le_da_el_plan_de_cuentas() -> None:
    """Ninguna frase del diccionario que diga lo que el restringido SÍ lee nombra contabilidad
    (frases partidas por punto y espacio: los nombres `esquema.tabla` no las cortan)."""
    for ruta in sorted(DICC.glob("*.yaml")):
        plano = _plano(ruta.read_text(encoding="utf-8"))
        for frase in re.split(r"\.\s", plano):
            if re.search(r"\bSI (la |lo )?lee", frase):
                sin_restringida = frase.replace("contabilidad_restringida", "")
                assert not re.search(r"`contabilidad[`.]", sin_restringida), (
                    f"{ruta.name}: {frase}"
                )


def _global_de_main() -> str | None:
    try:
        r = subprocess.run(
            ["git", "show", "main:config/diccionario/00_global.yaml"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def test_f146_r5_version_la_siguiente_a_la_de_main() -> None:
    """Antes del merge, la de `main` + 1; después, `main` YA lleva la entrada de F-146 y
    basta con no bajar de ella (patrón de F-128 y F-145)."""
    texto_main = _global_de_main()
    if texto_main is None:
        pytest.skip("sin git o sin rama main: no se puede comparar")
    version_main = int(yaml.safe_load(texto_main)["version"])
    actual = int(_yaml("00_global.yaml")["version"])
    if "(F-146, " in texto_main:
        assert actual >= version_main
    else:
        assert actual >= version_main + 1


def test_f146_r5_historia_de_versiones() -> None:
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert int(_yaml("00_global.yaml")["version"]) >= VERSION_F146
    assert f"# version {VERSION_F146} (F-146, " in texto


# ===========================================================================
# R6 · la documentación y el contrato con `mcp-bbdd`
# ===========================================================================


def test_f146_r6_arquitectura_y_runbook_al_dia() -> None:
    arquitectura = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    perfil = arquitectura.split("**El perfil restringido en `apply_grants`, desde F-141.**", 1)[1]
    perfil = perfil.split("\n- **", 1)[0]
    assert "F-146" in perfil and "`contabilidad`" in perfil
    runbook = (RAIZ / "docs" / "runbook_postgres_azure.md").read_text(encoding="utf-8")
    (fila,) = [linea for linea in runbook.splitlines() if linea.startswith(f"| `{GRUPO}` |")]
    assert "F-146" in fila and "`contabilidad`" in fila
    p6 = runbook.split("\n## 13. ", 1)[1].split("### P6 ", 1)[1].split("\n### ", 1)[0]
    no = p6.split("$no = ", 1)[1].split("foreach", 1)[0]
    si = p6.split("$si = ", 1)[1].split("foreach", 1)[0]
    assert "contabilidad.plan_cuentas" in no and "contabilidad.apuntes_restringidos_mes" in no
    assert "contabilidad" not in si


def _azure_apps() -> str:
    ruta = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"
    if not ruta.exists():  # pragma: no cover - solo en un puesto sin el repositorio hermano
        pytest.skip(f"no está {ruta}: azure-apps es otro repositorio")
    return ruta.read_text(encoding="utf-8")


def test_f146_r6_azure_apps_describe_el_alcance_nuevo() -> None:
    texto = _azure_apps()
    (fila,) = [linea for linea in texto.splitlines() if linea.startswith("| **El MCP, perfil RESTRINGIDO**")]
    assert "F-146" in fila and "`contabilidad`" in fila
    contrato = texto.split("### El perfil RESTRINGIDO del MCP", 1)[1].split("\n### ", 1)[0]
    assert "F-146" in contrato
    assert "`contabilidad` (sin" not in contrato, "ya no lee contabilidad con exclusiones"
    e2 = contrato.split("**E2.", 1)[1].split("\n- **", 1)[0]
    assert "`contabilidad`" in _plano(e2) and "`retenciones`" in _plano(e2)


# ===========================================================================
# T6 · AMPLIACIÓN del 2026-10-21 («arregla ya el diccionario»): los adjuntos llegan
# CONVERTIDOS. Aviso formal de `mcp-bbdd`: su F-028 (nuestra F-142) está desplegada
# (`ca-mcp-bbdd-dev--0000023`, imagen `r20261021-1510`). `abrir_adjunto` ya no entrega
# el original tal cual: TEXTO por página, escaneos e imágenes como IMAGEN, `paginas`
# (10 primeras por defecto) y el documento 24 h en un SharePoint propio. La clave
# (`emp`, `cod`), el respaldo con la empresa 1 y `ORIGEN_AMBIGUO` NO cambian.
# ===========================================================================

#: lo que ya no es verdad y no puede quedar como estado vigente
CADUCADO = re.compile(r"sin convertir|incrustad|como binario", re.IGNORECASE)


def _ficha_adjuntos() -> str:
    return _plano(_yaml("compras.yaml")["objetos"]["documento_adjuntos"]["descripcion"])


def test_f146_t6_la_ficha_dice_lo_que_entrega_hoy_abrir_adjunto() -> None:
    ficha = _ficha_adjuntos()
    for dato in ("F-028", "2026-10-21", "F-142", "TEXTO por pagina", "Microsoft Graph",
                 "`.doc`", "`.msg`", "como IMAGEN", "`paginas`", "10 primeras",
                 'paginas="11-20"', "24 h", "SharePoint", "solo para quien lo pidio"):
        assert dato in ficha, f"la ficha de documento_adjuntos no dice «{dato}»"


def test_f146_t6_la_ficha_ya_no_dice_que_llega_sin_convertir() -> None:
    caducado = CADUCADO.findall(_ficha_adjuntos())
    assert not caducado, f"la ficha aún da por vigente: {caducado}"


def test_f146_t6_la_clave_y_el_respaldo_no_cambian() -> None:
    ficha = _ficha_adjuntos()
    for dato in ('key: {"emp": empresa_repositorio, "cod": cod_repositorio}',
                 "empresa 1", "`SIN_BINARIO`", "`ORIGEN_AMBIGUO`", "respaldo=empresa_defecto",
                 "QUIEN PUEDE ABRIR EL FICHERO", "`abrir_adjunto(adjunto_id)`"):
        assert dato in ficha, f"la ficha perdió «{dato}»"


def test_f146_t6_la_v58_cuenta_las_dos_cosas() -> None:
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    entrada = texto.split(f"# version {VERSION_F146} (F-146, ", 1)[1].split("\nversion:", 1)[0]
    plano = _plano(entrada.replace("#", " "))
    for dato in ("`contabilidad`", "F-028", "F-142", "`compras.documento_adjuntos`", "`paginas`"):
        assert dato in plano, f"la entrada de la v58 no dice «{dato}»"


def test_f146_t6_arquitectura_al_dia() -> None:
    texto = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    punto = texto.split("**El límite (F-139)**", 1)[1].split("\n  - **", 1)[0]
    assert not CADUCADO.findall(punto), punto
    for dato in ("F-028", "F-142", "`paginas`", "SharePoint", "24 h"):
        assert dato in punto, f"ARCHITECTURE (el límite de F-139) no dice «{dato}»"


def test_f146_t6_azure_apps_al_dia() -> None:
    texto = _azure_apps()
    seccion = texto.split("### Abrir el original de un adjunto", 1)[1].split("\n### ", 1)[0]
    assert not CADUCADO.findall(seccion), CADUCADO.findall(seccion)
    for dato in ("F-028", "--0000023", "r20261021-1510", "`paginas`", "24 h", "SharePoint",
                 "299624", "305078", "304800", "304883"):
        assert dato in seccion, f"azure-apps (abrir un adjunto) no dice «{dato}»"
    h5 = seccion[seccion.index("- **H5.**"): seccion.index("- **H6.**")]
    assert '"emp": empresa_repositorio, "cod": cod_repositorio' in h5 and "ORIGEN_AMBIGUO" in h5
