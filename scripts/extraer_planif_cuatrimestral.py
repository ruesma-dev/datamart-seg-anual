# scripts/extraer_planif_cuatrimestral.py
"""
================================================================================
EXTRACTOR DE PLANIFICACIÓN VALORADA TEMPORAL — ÚLTIMO CUATRIMESTRAL
================================================================================

Script AUTOCONTENIDO (un único archivo) que:

  1. Llama a la API de Sigrid (sigrid-api, endpoint POST /api/sql/read).
  2. Para cada obra cuyo código esté en el rango [0600, 0800], localiza la
     ÚLTIMA versión vigente del MASTER COSTE (ámbito 8) — el "último
     cuatrimestral" (o la última planificación valorada disponible).
  3. Extrae su estructura de presupuesto (capítulos + partidas).
  4. DECODIFICA la planificación temporal embebida en obrparpre.planif,
     usando obrfasamb.plafec como ancla del mes 1.
  5. Crea una BBDD PostgreSQL nueva e independiente (sigrid_planif por defecto)
     con el schema planif_train y la puebla.

OBJETIVO: construir un dataset de referencia para que una IA aprenda a generar
planificación temporal valorada a partir de una estructura de presupuesto
(de Presto) que NO tiene planificación.

--------------------------------------------------------------------------------
FORMATO DE planif (confirmado con datos reales de la obra 0707)
--------------------------------------------------------------------------------
Cadena de texto separada por '|'. Cada valor es el % ACUMULADO (en rango [0,1])
de la medición de la partida al final de ese mes. Punto decimal.

Ejemplo: "0.045|0.09|0.135|...|1"
  - mes 1 (= plafec): acumulado 0.045  → pct_mes = 0.045
  - mes 2 (plafec+1) : acumulado 0.09   → pct_mes = 0.045
  - ...
  - último mes       : acumulado 1.0    (siempre cierra al 100%)

Reglas de decodificación:
  pct_mes[1]   = pct_acum[1]
  pct_mes[i]   = pct_acum[i] - pct_acum[i-1]   (i > 1)
  can_mes[i]   = pct_mes[i] * can_total
  importe_mes  = can_mes[i] * precio    (precio redondeado a `decp` decimales)

El ancla temporal (plafec) vive en obrfasamb para esa (obra, ámbito, versión).

--------------------------------------------------------------------------------
USO
--------------------------------------------------------------------------------
    # Credenciales por variables de entorno o .env (ver sección CONFIG)
    python extraer_planif_cuatrimestral.py

    # Opciones útiles:
    python extraer_planif_cuatrimestral.py --cod-desde 0600 --cod-hasta 0800
    python extraer_planif_cuatrimestral.py --solo-obra 0707     # una sola, para probar
    python extraer_planif_cuatrimestral.py --dry-run            # no crea BBDD, solo informa
    python extraer_planif_cuatrimestral.py --recrear-bbdd       # DROP + CREATE de la BBDD

--------------------------------------------------------------------------------
DEPENDENCIAS
--------------------------------------------------------------------------------
    pip install requests psycopg[binary] python-dotenv
================================================================================
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import requests

try:
    import psycopg
    from psycopg import sql as pgsql
except ImportError:
    print("ERROR: falta psycopg. Instala con: pip install 'psycopg[binary]'",
          file=sys.stderr)
    sys.exit(1)

# python-dotenv es opcional; si no está, se leen solo las env vars del sistema.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =============================================================================
# CONFIG — credenciales y parámetros (vía entorno / .env)
# =============================================================================
@dataclass(frozen=True)
class Config:
    # --- sigrid-api ---
    sigrid_base_url: str
    sigrid_function_key: str
    sigrid_database: str

    # --- PostgreSQL destino (BBDD nueva) ---
    pg_host: str
    pg_port: int
    pg_user: str
    pg_password: str
    pg_admin_db: str          # BBDD a la que conectar para crear la nueva (normalmente 'postgres')
    pg_target_db: str         # nombre de la BBDD nueva a crear/poblar
    pg_schema: str            # schema dentro de la BBDD nueva

    # --- parámetros de extracción ---
    cod_desde: str
    cod_hasta: str
    api_page_size: int        # filas por página (tope duro de la API = 1000)
    api_timeout_s: int

    @staticmethod
    def from_env() -> "Config":
        def req(name: str) -> str:
            v = os.environ.get(name)
            if not v:
                print(f"ERROR: falta la variable de entorno {name}", file=sys.stderr)
                sys.exit(2)
            return v

        return Config(
            sigrid_base_url=req("SIGRID_API_BASE_URL").rstrip("/"),
            sigrid_function_key=req("SIGRID_API_FUNCTION_KEY"),
            sigrid_database=os.environ.get("SIGRID_API_DATABASE", "ruesma_rep"),
            pg_host=os.environ.get("PG_HOST", "localhost"),
            pg_port=int(os.environ.get("PG_PORT", "5432")),
            pg_user=os.environ.get("PG_USER", "postgres"),
            pg_password=req("PG_PASSWORD"),
            pg_admin_db=os.environ.get("PG_ADMIN_DB", "postgres"),
            pg_target_db=os.environ.get("PG_TARGET_DB", "sigrid_planif"),
            pg_schema=os.environ.get("PG_SCHEMA", "planif_train"),
            cod_desde="0600",
            cod_hasta="0800",
            api_page_size=int(os.environ.get("SIGRID_API_PAGE_SIZE", "1000")),
            api_timeout_s=int(os.environ.get("SIGRID_API_TIMEOUT_S", "120")),
        )


# =============================================================================
# CLIENTE SIGRID-API
# =============================================================================
class SigridClient:
    """Cliente mínimo para POST /api/sql/read con paginación por OFFSET."""

    def __init__(self, cfg: Config) -> None:
        self._url = f"{cfg.sigrid_base_url}/api/sql/read"
        self._headers = {
            "x-functions-key": cfg.sigrid_function_key,
            "Content-Type": "application/json",
        }
        self._database = cfg.sigrid_database
        self._page_size = cfg.api_page_size
        self._timeout = cfg.api_timeout_s
        self._session = requests.Session()

    def query(
        self,
        sql: str,
        parameters: list[Any] | None = None,
        max_rows: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Ejecuta una SELECT y devuelve filas como lista de dicts.
        NO pagina: usa max_rows (tope API). Para sets grandes usa query_paged.
        """
        body = {
            "database": self._database,
            "sql": sql,
            "parameters": parameters or [],
            "timeout_seconds": self._timeout,
            "max_rows": max_rows or self._page_size,
        }
        resp = self._session.post(
            self._url, json=body, headers=self._headers, timeout=self._timeout + 10
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"sigrid-api {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
        if not data.get("ok", False):
            raise RuntimeError(f"sigrid-api error: {data}")
        cols = data["columns"]
        return [dict(zip(cols, row)) for row in data["rows"]]

    def query_paged(
        self,
        sql_base: str,
        order_by: str,
        parameters: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Pagina una consulta usando OFFSET/FETCH (SQL Server). `sql_base` NO debe
        incluir ORDER BY/OFFSET; se añaden aquí. `order_by` es la cláusula de
        ordenación estable (obligatoria para OFFSET en SQL Server).
        """
        all_rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            paged_sql = (
                f"{sql_base} ORDER BY {order_by} "
                f"OFFSET {offset} ROWS FETCH NEXT {self._page_size} ROWS ONLY"
            )
            batch = self.query(paged_sql, parameters, max_rows=self._page_size)
            all_rows.extend(batch)
            if len(batch) < self._page_size:
                break
            offset += self._page_size
            time.sleep(0.05)  # cortesía con la API
        return all_rows


# =============================================================================
# DECODIFICADOR DE planif  (réplica exacta del parser del datamart)
# =============================================================================
def sigrid_int_to_date(yyyymmdd: int | None) -> date | None:
    """Convierte un entero YYYYMMDD de Sigrid a date. 0/None → None."""
    if not yyyymmdd or yyyymmdd == 0:
        return None
    try:
        y = yyyymmdd // 10000
        m = (yyyymmdd // 100) % 100
        d = yyyymmdd % 100
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def add_months(d: date, n: int) -> date:
    """Suma n meses a una fecha, fijando el día 1 (las fases son mensuales)."""
    total = (d.year * 12 + (d.month - 1)) + n
    y, m = divmod(total, 12)
    return date(y, m + 1, 1)


@dataclass
class MesPlanificado:
    posicion_mes: int          # 1, 2, 3... relativo al ancla
    anio_mes: date             # primer día del mes (absoluto)
    pct_acumulado: float       # 0..1
    pct_mes: float             # incremento de este mes
    can_mes: float             # medición del mes
    can_origen: float          # medición acumulada a origen
    importe_mes: float         # can_mes * precio
    importe_origen: float      # acumulado


def decodificar_planif(
    planif: str,
    plafec: date,
    can_total: float,
    precio: float,
    decimales_precio: int,
    decimales_importe: int,
) -> list[MesPlanificado]:
    """
    Decodifica la cadena planif en una lista de meses.

    planif: "0.045|0.09|...|1" (% acumulados en [0,1], punto decimal).
    plafec: ancla del mes 1.
    can_total, precio: de obrparpre (can, pre).
    decimales_*: de raw.obr (decp, deci) para clavar el redondeo Sigrid.

    MÉTODO (idéntico al datamart / Sigrid para importe a origen):
      can_origen[i]   = pct_acum[i] * can_total          (cantidad acumulada)
      importe_origen  = round(can_origen[i] * round(precio, decp), deci)
      importe_mes[i]  = importe_origen[i] - importe_origen[i-1]   (diferencia)

    Es decir, el importe se ancla SIEMPRE al acumulado a origen (que es lo que
    Sigrid almacena como can×pre) y el importe del mes se obtiene por
    diferencia. Esto evita la deriva de céntimos que aparecería redondeando
    cada mes por separado. La cantidad NUNCA se redondea.
    """
    if not planif or not plafec:
        return []

    # Split robusto: ignora vacíos por '||' o trailing '|'
    tokens = [t.strip() for t in planif.split("|") if t.strip() != ""]
    if not tokens:
        return []

    precio_redondeado = round(precio, decimales_precio)

    meses: list[MesPlanificado] = []
    pct_prev = 0.0
    can_origen_prev = 0.0
    importe_origen_prev = 0.0

    for i, tok in enumerate(tokens, start=1):
        # Acepta tanto punto como coma por robustez (los datos reales usan punto).
        # Algunos planif de Sigrid traen valores anómalos (no numéricos, o
        # porcentajes fuera de [0,1] por errores de captura). Los toleramos:
        # un token no numérico mantiene el acumulado anterior (avance 0).
        try:
            pct_acum = float(tok.replace(",", "."))
        except (ValueError, TypeError):
            pct_acum = pct_prev  # token corrupto → sin avance ese mes
        pct_mes = pct_acum - pct_prev
        pct_prev = pct_acum

        # Cantidad: acumulada a origen y parcial del mes (sin redondear cantidad)
        can_origen = pct_acum * can_total
        can_mes = can_origen - can_origen_prev

        # Importe: anclado al acumulado a origen; el del mes es la diferencia
        importe_origen = round(can_origen * precio_redondeado, decimales_importe)
        importe_mes = round(importe_origen - importe_origen_prev, decimales_importe)

        meses.append(
            MesPlanificado(
                posicion_mes=i,
                anio_mes=add_months(plafec, i - 1),
                pct_acumulado=pct_acum,
                pct_mes=pct_mes,
                can_mes=can_mes,
                can_origen=can_origen,
                importe_mes=importe_mes,
                importe_origen=importe_origen,
            )
        )

        can_origen_prev = can_origen
        importe_origen_prev = importe_origen

    return meses


# Umbrales para detectar planificaciones anómalas. Una planif sana:
#   - tiene pct acumulados monótonos crecientes en [0, ~1]
#   - cierra cerca de 1.0 (100%)
# Sigrid ocasionalmente almacena valores corruptos (porcentajes 0-100 en vez de
# 0-1, o números enormes por errores de captura) que no sirven para entrenar.
PCT_MAX_RAZONABLE = 1.5     # margen sobre 1.0 (permite pequeños sobre-cierres)
PCT_CIERRE_MIN = 0.5        # una planif sana debe cerrar al menos al 50%


def planif_es_anomala(meses: list[MesPlanificado]) -> bool:
    """
    Determina si una planificación decodificada es anómala y NO debe entrar al
    dataset de entrenamiento. Criterios:
      - Algún pct_acumulado fuera de [-0.01, PCT_MAX_RAZONABLE].
      - El acumulado final está muy lejos de 1.0 (no cierra).
      - Hay retrocesos grandes (pct_mes muy negativo).
    """
    if not meses:
        return False  # sin meses no es "anómala", simplemente no hay planif

    for m in meses:
        # Porcentaje fuera de un rango sano (p.ej. 250% por captura errónea)
        if m.pct_acumulado < -0.01 or m.pct_acumulado > PCT_MAX_RAZONABLE:
            return True
        # Retroceso fuerte (la planif debería ser acumulativa creciente)
        if m.pct_mes < -0.05:
            return True

    # El acumulado final debería cerrar cerca del 100%
    pct_final = meses[-1].pct_acumulado
    if pct_final < PCT_CIERRE_MIN or pct_final > PCT_MAX_RAZONABLE:
        return True

    return False


# =============================================================================
# CLASIFICACIÓN DE VERSIÓN MASTER (réplica del datamart: por obrfasamb.tex)
# =============================================================================
def clasificar_tipo_master(tex: str | None) -> str:
    """
    Clasifica el tipo de versión master a partir del texto libre (obrfasamb.tex).
    Prioridad estricta: la primera que matchea gana.
    """
    if not tex or not tex.strip():
        return "Sin clasificar"
    t = tex.upper()
    if "ABC" in t:
        return "ABC"
    if "INICIAL" in t and "VALORADA" in t:
        return "Planif Inicial"
    if "CUATRIM" in t or "VALORADA" in t:
        return "Cuatrimestral"
    if "CIERRE" in t:
        return "Cierre mensual"
    return "Sin clasificar"


TIPOS_VIGENTES = ("Planif Inicial", "ABC", "Cuatrimestral")


# =============================================================================
# ESTRUCTURAS DE DOMINIO
# =============================================================================
@dataclass
class Obra:
    obra_id: int
    codigo: str
    nombre: str
    decimales_precio: int
    decimales_importe: int
    # versión cuatrimestral elegida
    version_num: int | None = None
    version_desc: str | None = None
    version_tex: str | None = None
    version_tipo: str | None = None
    fecha_ancla: date | None = None
    fecha_creacion_version: date | None = None


@dataclass
class NodoPresupuesto:
    """Un nodo de obrparpar: puede ser capítulo (rama) o partida (hoja)."""
    nodo_id: int               # obrparpar.ide
    obra_id: int
    padre_id: int | None       # padide (NULL para raíces)
    codigo: str
    descripcion: str
    posicion: int
    es_partida: bool           # True si es hoja con presupuesto
    desactivado: bool
    unidad_medida: str | None = None
    # solo partidas:
    medicion: float | None = None
    precio: float | None = None
    importe: float | None = None
    presupuesto_id: int | None = None   # obrparpre.ide
    planif_cruda: str | None = None
    # calculados:
    nivel: int = 0
    ruta_capitulos: str = ""
    meses: list[MesPlanificado] = field(default_factory=list)
    planif_anomala: bool = False   # True si planif tiene valores fuera de rango


# =============================================================================
# EXTRACCIÓN DESDE SIGRID
# =============================================================================
class Extractor:
    def __init__(self, client: SigridClient, cfg: Config) -> None:
        self._c = client
        self._cfg = cfg

    # ---- 1. Obras en el rango de código ----
    def obtener_obras(self, solo_obra: str | None = None) -> list[Obra]:
        """
        Obras cuyo con.cod ∈ [cod_desde, cod_hasta]. La obra hereda de con:
        obr.ide = con.ide. Decimales por obra en raw.obr (decp, deci).
        """
        if solo_obra:
            where_cod = "c.cod = ?"
            params: list[Any] = [solo_obra]
        else:
            where_cod = "c.cod >= ? AND c.cod <= ?"
            params = [self._cfg.cod_desde, self._cfg.cod_hasta]

        sql = f"""
            SELECT c.ide      AS obra_id,
                   c.cod      AS codigo,
                   c.res      AS nombre,
                   o.decp     AS decimales_precio,
                   o.deci     AS decimales_importe
            FROM dbo.con c
            INNER JOIN dbo.obr o ON o.ide = c.ide
            WHERE {where_cod}
        """
        rows = self._c.query_paged(sql, order_by="c.cod", parameters=params)
        obras = []
        for r in rows:
            obras.append(
                Obra(
                    obra_id=int(r["obra_id"]),
                    codigo=str(r["codigo"]).strip(),
                    nombre=(r["nombre"] or "").strip(),
                    decimales_precio=int(r["decimales_precio"] or 2),
                    decimales_importe=int(r["decimales_importe"] or 2),
                )
            )
        return obras

    # ---- 2. Versión cuatrimestral (master coste vigente) por obra ----
    def elegir_version_cuatrimestral(self, obra: Obra) -> bool:
        """
        Localiza la ÚLTIMA versión vigente del master coste (amb=8) de la obra.
        "Vigente" = tipo ∈ {Planif Inicial, ABC, Cuatrimestral}, plafec != 0.
        Se elige la de mayor fecha de creación (fec).

        Rellena los campos version_* y fecha_ancla de la obra.
        Devuelve True si encontró una versión válida.
        """
        sql = """
            SELECT fa.fas      AS version_num,
                   fa.res      AS version_desc,
                   fa.tex      AS version_tex,
                   fa.plafec   AS plafec,
                   fa.fec      AS fec
            FROM dbo.obrfasamb fa
            WHERE fa.obride = ?
              AND fa.amb = 8
              AND fa.plafec <> 0
        """
        rows = self._c.query(sql, parameters=[obra.obra_id], max_rows=1000)

        candidatas = []
        for r in rows:
            tex = r["version_tex"]
            tipo = clasificar_tipo_master(tex)
            if tipo not in TIPOS_VIGENTES:
                continue
            plafec = sigrid_int_to_date(int(r["plafec"] or 0))
            if plafec is None:
                continue
            fec = sigrid_int_to_date(int(r["fec"] or 0)) or date(1900, 1, 1)
            candidatas.append({
                "version_num": int(r["version_num"]),
                "version_desc": (r["version_desc"] or "").strip(),
                "version_tex": (tex or "").strip(),
                "version_tipo": tipo,
                "plafec": plafec,
                "fec": fec,
            })

        if not candidatas:
            return False

        # La última = mayor fecha de creación; desempate por número de versión.
        elegida = max(candidatas, key=lambda x: (x["fec"], x["version_num"]))
        obra.version_num = elegida["version_num"]
        obra.version_desc = elegida["version_desc"]
        obra.version_tex = elegida["version_tex"]
        obra.version_tipo = elegida["version_tipo"]
        obra.fecha_ancla = elegida["plafec"]
        obra.fecha_creacion_version = elegida["fec"]
        return True

    # ---- 3. Estructura (capítulos + partidas) con planif ----
    def obtener_estructura(self, obra: Obra) -> list[NodoPresupuesto]:
        """
        Trae todos los nodos de obrparpar de la obra y, para las partidas (hojas),
        el presupuesto + planif de obrparpre del master coste (amb=8) en la
        versión cuatrimestral elegida.

        Un nodo es CAPÍTULO si tiene hijos (aparece como padide de otro).
        Un nodo es PARTIDA si NO tiene hijos y tiene fila en obrparpre.
        """
        # 3a. Todos los nodos del árbol (capítulos y partidas)
        sql_nodos = """
            SELECT pp.ide      AS nodo_id,
                   pp.padide   AS padre_id,
                   pp.cod      AS codigo,
                   pp.res      AS descripcion,
                   pp.pos      AS posicion,
                   pp.tipdes   AS desactivado,
                   pp.unimed   AS unidad_medida
            FROM dbo.obrparpar pp
            WHERE pp.obride = ?
        """
        nodos_rows = self._c.query_paged(
            sql_nodos, order_by="pp.pos, pp.ide", parameters=[obra.obra_id]
        )

        # 3b. Presupuesto + planif de las partidas (master coste, versión elegida)
        sql_pres = """
            SELECT op.paride   AS nodo_id,
                   op.ide      AS presupuesto_id,
                   op.can      AS medicion,
                   op.pre      AS precio,
                   op.planif   AS planif
            FROM dbo.obrparpre op
            WHERE op.obride = ?
              AND op.amb = 8
              AND op.fas = ?
        """
        pres_rows = self._c.query_paged(
            sql_pres, order_by="op.paride",
            parameters=[obra.obra_id, obra.version_num],
        )
        pres_by_nodo = {int(r["nodo_id"]): r for r in pres_rows}

        # 3c. Conjunto de padres → para saber quién es capítulo (tiene hijos)
        padres = {
            int(r["padre_id"]) for r in nodos_rows
            if r["padre_id"] is not None and int(r["padre_id"]) != 0
        }

        nodos: dict[int, NodoPresupuesto] = {}
        for r in nodos_rows:
            nodo_id = int(r["nodo_id"])
            padre_id = r["padre_id"]
            padre_id = int(padre_id) if padre_id and int(padre_id) != 0 else None
            tiene_hijos = nodo_id in padres
            pres = pres_by_nodo.get(nodo_id)
            es_partida = (not tiene_hijos) and (pres is not None)

            nodo = NodoPresupuesto(
                nodo_id=nodo_id,
                obra_id=obra.obra_id,
                padre_id=padre_id,
                codigo=(r["codigo"] or "").strip(),
                descripcion=(r["descripcion"] or "").strip(),
                posicion=int(r["posicion"] or 0),
                es_partida=es_partida,
                desactivado=bool(int(r["desactivado"] or 0)),
                unidad_medida=(r["unidad_medida"] or "").strip() or None,
            )

            if es_partida and pres is not None:
                medicion = float(pres["medicion"] or 0.0)
                precio = float(pres["precio"] or 0.0)
                importe = round(
                    medicion * round(precio, obra.decimales_precio),
                    obra.decimales_importe,
                )
                nodo.medicion = medicion
                nodo.precio = precio
                nodo.importe = importe
                nodo.presupuesto_id = int(pres["presupuesto_id"])
                nodo.planif_cruda = pres["planif"]

                # Decodificar la planificación temporal
                if nodo.planif_cruda and obra.fecha_ancla:
                    nodo.meses = decodificar_planif(
                        planif=nodo.planif_cruda,
                        plafec=obra.fecha_ancla,
                        can_total=medicion,
                        precio=precio,
                        decimales_precio=obra.decimales_precio,
                        decimales_importe=obra.decimales_importe,
                    )
                    # Marcar si la planificación tiene valores anómalos
                    # (porcentajes fuera del rango esperado). Estas partidas
                    # se cargan SIN meses para no contaminar el dataset.
                    if planif_es_anomala(nodo.meses):
                        nodo.planif_anomala = True
                        nodo.meses = []

            nodos[nodo_id] = nodo

        # 3d. Calcular nivel y ruta de capítulos (recorriendo padres)
        self._calcular_jerarquia(nodos)

        return list(nodos.values())

    @staticmethod
    def _calcular_jerarquia(nodos: dict[int, NodoPresupuesto]) -> None:
        """Rellena nivel y ruta_capitulos de cada nodo subiendo por padre_id."""
        def construir_ruta(nodo: NodoPresupuesto) -> tuple[int, str]:
            partes: list[str] = []
            actual: NodoPresupuesto | None = nodo
            visto = set()
            while actual is not None and actual.padre_id is not None:
                if actual.padre_id in visto:
                    break  # protección anti-ciclo
                visto.add(actual.padre_id)
                padre = nodos.get(actual.padre_id)
                if padre is None:
                    break
                etiqueta = padre.codigo or padre.descripcion[:20]
                partes.append(etiqueta)
                actual = padre
            partes.reverse()
            nivel = len(partes)
            ruta = " > ".join(partes) if partes else "(raíz)"
            return nivel, ruta

        for nodo in nodos.values():
            nodo.nivel, nodo.ruta_capitulos = construir_ruta(nodo)


# =============================================================================
# CARGA EN POSTGRESQL (BBDD nueva)
# =============================================================================
DDL = """
CREATE SCHEMA IF NOT EXISTS {schema};

DROP TABLE IF EXISTS {schema}.planificacion_mensual CASCADE;
DROP TABLE IF EXISTS {schema}.partida CASCADE;
DROP TABLE IF EXISTS {schema}.capitulo CASCADE;
DROP TABLE IF EXISTS {schema}.obra CASCADE;

-- Cabecera de cada obra (un ejemplo de entrenamiento)
CREATE TABLE {schema}.obra (
    obra_id                BIGINT PRIMARY KEY,
    codigo                 VARCHAR(24)  NOT NULL,
    nombre                 VARCHAR(255),
    version_num            INTEGER,            -- nº de versión master coste usada
    version_descripcion    TEXT,               -- "Versión N (DD/MM/YYYY)"
    version_tex            TEXT,               -- texto libre del JO
    version_tipo           VARCHAR(20),        -- Planif Inicial / ABC / Cuatrimestral
    fecha_ancla            DATE,               -- plafec: primer mes de la planificación
    fecha_creacion_version DATE,
    plazo_total_meses      INTEGER,            -- nº de meses que abarca la planificación
    importe_total          NUMERIC(18,2),      -- suma de importes de partidas
    num_capitulos          INTEGER,
    num_partidas           INTEGER,
    _extraido_at           TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Capítulos (nodos rama del árbol de presupuesto)
CREATE TABLE {schema}.capitulo (
    capitulo_id            BIGINT PRIMARY KEY,  -- obrparpar.ide
    obra_id                BIGINT NOT NULL REFERENCES {schema}.obra(obra_id),
    padre_id               BIGINT,              -- capítulo padre (NULL si raíz)
    codigo                 VARCHAR(48),
    descripcion            VARCHAR(255),
    nivel                  INTEGER,             -- profundidad en el árbol
    posicion               INTEGER,             -- orden entre hermanos
    ruta_capitulos         TEXT                 -- "01 > 01.02" para contexto
);
CREATE INDEX idx_capitulo_obra ON {schema}.capitulo(obra_id);

-- Partidas (hojas con presupuesto + planificación)
CREATE TABLE {schema}.partida (
    partida_id             BIGINT PRIMARY KEY,  -- obrparpar.ide
    obra_id                BIGINT NOT NULL REFERENCES {schema}.obra(obra_id),
    capitulo_id            BIGINT,              -- capítulo padre directo
    codigo                 VARCHAR(48),
    descripcion            VARCHAR(255),
    unidad_medida          VARCHAR(16),
    medicion               NUMERIC(20,6),       -- can (cantidad)
    precio                 NUMERIC(20,6),       -- pre (precio unitario)
    importe                NUMERIC(18,2),       -- can * round(pre)
    nivel                  INTEGER,
    posicion               INTEGER,
    ruta_capitulos         TEXT,                -- "MOV. TIERRAS > EXCAVACION" (semántica)
    -- Resumen de la planificación temporal (para que la IA aprenda el timing)
    mes_inicio_relativo    INTEGER,             -- primer mes con avance (1..N)
    mes_fin_relativo       INTEGER,             -- último mes con avance
    num_meses_activos      INTEGER,             -- meses con pct_mes > 0
    planif_anomala         BOOLEAN NOT NULL DEFAULT FALSE,  -- planif corrupta en Sigrid (sin meses)
    planif_cruda           TEXT                 -- cadena original (auditoría)
);
CREATE INDEX idx_partida_obra ON {schema}.partida(obra_id);
CREATE INDEX idx_partida_capitulo ON {schema}.partida(capitulo_id);

-- Planificación mensual decodificada (partida × mes → importe)
CREATE TABLE {schema}.planificacion_mensual (
    id                     BIGSERIAL PRIMARY KEY,
    partida_id             BIGINT NOT NULL REFERENCES {schema}.partida(partida_id),
    obra_id                BIGINT NOT NULL REFERENCES {schema}.obra(obra_id),
    posicion_mes           INTEGER NOT NULL,    -- 1, 2, 3... relativo al inicio de obra
    anio_mes               DATE NOT NULL,       -- primer día del mes (absoluto)
    pct_acumulado          NUMERIC(18,8),       -- 0..1 normalmente; ancho por anomalías Sigrid
    pct_mes                NUMERIC(18,8),       -- incremento del mes
    medicion_mes           NUMERIC(20,6),
    medicion_origen        NUMERIC(20,6),       -- acumulada
    importe_mes            NUMERIC(18,2),
    importe_origen         NUMERIC(18,2)        -- acumulado
);
CREATE INDEX idx_planmensual_partida ON {schema}.planificacion_mensual(partida_id);
CREATE INDEX idx_planmensual_obra ON {schema}.planificacion_mensual(obra_id);
"""


class Cargador:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    def _conn_admin(self) -> "psycopg.Connection":
        return psycopg.connect(
            host=self._cfg.pg_host, port=self._cfg.pg_port,
            user=self._cfg.pg_user, password=self._cfg.pg_password,
            dbname=self._cfg.pg_admin_db, autocommit=True,
        )

    def _conn_target(self) -> "psycopg.Connection":
        return psycopg.connect(
            host=self._cfg.pg_host, port=self._cfg.pg_port,
            user=self._cfg.pg_user, password=self._cfg.pg_password,
            dbname=self._cfg.pg_target_db,
        )

    def crear_bbdd(self, recrear: bool) -> None:
        """Crea la BBDD destino si no existe (o la recrea si recrear=True)."""
        with self._conn_admin() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self._cfg.pg_target_db,),
            )
            existe = cur.fetchone() is not None

            if existe and recrear:
                # Cerrar conexiones y dropear
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (self._cfg.pg_target_db,),
                )
                cur.execute(
                    pgsql.SQL("DROP DATABASE {}").format(
                        pgsql.Identifier(self._cfg.pg_target_db)
                    )
                )
                existe = False

            if not existe:
                cur.execute(
                    pgsql.SQL("CREATE DATABASE {}").format(
                        pgsql.Identifier(self._cfg.pg_target_db)
                    )
                )
                print(f"  BBDD '{self._cfg.pg_target_db}' creada.")
            else:
                print(f"  BBDD '{self._cfg.pg_target_db}' ya existe (se reutiliza).")

    def crear_schema(self) -> None:
        """Crea schema y tablas (DROP previo de las tablas para idempotencia)."""
        ddl = DDL.format(schema=self._cfg.pg_schema)
        with self._conn_target() as conn, conn.cursor() as cur:
            cur.execute(ddl)
            conn.commit()
        print(f"  Schema '{self._cfg.pg_schema}' y tablas creadas.")

    def cargar_obra(self, obra: Obra, nodos: list[NodoPresupuesto]) -> dict[str, int]:
        """Inserta una obra completa (cabecera + capítulos + partidas + meses)."""
        sch = self._cfg.pg_schema
        capitulos = [n for n in nodos if not n.es_partida and not n.desactivado]
        partidas = [
            n for n in nodos
            if n.es_partida and not n.desactivado
            and n.importe is not None and abs(n.importe) > 0.0
        ]

        # Plazo total = máxima posición de mes entre todas las partidas
        plazo = 0
        for p in partidas:
            if p.meses:
                plazo = max(plazo, p.meses[-1].posicion_mes)
        importe_total = round(sum(p.importe or 0.0 for p in partidas), 2)

        with self._conn_target() as conn, conn.cursor() as cur:
            # --- cabecera ---
            cur.execute(
                pgsql.SQL("""
                    INSERT INTO {sch}.obra (
                        obra_id, codigo, nombre,
                        version_num, version_descripcion, version_tex, version_tipo,
                        fecha_ancla, fecha_creacion_version,
                        plazo_total_meses, importe_total,
                        num_capitulos, num_partidas
                    ) VALUES (
                        %s,%s,%s, %s,%s,%s,%s, %s,%s, %s,%s, %s,%s
                    )
                    ON CONFLICT (obra_id) DO UPDATE SET
                        codigo = EXCLUDED.codigo,
                        nombre = EXCLUDED.nombre,
                        version_num = EXCLUDED.version_num,
                        version_descripcion = EXCLUDED.version_descripcion,
                        version_tex = EXCLUDED.version_tex,
                        version_tipo = EXCLUDED.version_tipo,
                        fecha_ancla = EXCLUDED.fecha_ancla,
                        fecha_creacion_version = EXCLUDED.fecha_creacion_version,
                        plazo_total_meses = EXCLUDED.plazo_total_meses,
                        importe_total = EXCLUDED.importe_total,
                        num_capitulos = EXCLUDED.num_capitulos,
                        num_partidas = EXCLUDED.num_partidas
                """).format(sch=pgsql.Identifier(sch)),
                (
                    obra.obra_id, obra.codigo, obra.nombre,
                    obra.version_num, obra.version_desc, obra.version_tex,
                    obra.version_tipo, obra.fecha_ancla, obra.fecha_creacion_version,
                    plazo, importe_total, len(capitulos), len(partidas),
                ),
            )

            # --- capítulos ---
            if capitulos:
                cur.executemany(
                    pgsql.SQL("""
                        INSERT INTO {sch}.capitulo (
                            capitulo_id, obra_id, padre_id, codigo, descripcion,
                            nivel, posicion, ruta_capitulos
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """).format(sch=pgsql.Identifier(sch)),
                    [
                        (c.nodo_id, c.obra_id, c.padre_id, c.codigo,
                         c.descripcion, c.nivel, c.posicion, c.ruta_capitulos)
                        for c in capitulos
                    ],
                )

            # --- partidas ---
            if partidas:
                cur.executemany(
                    pgsql.SQL("""
                        INSERT INTO {sch}.partida (
                            partida_id, obra_id, capitulo_id, codigo, descripcion,
                            unidad_medida, medicion, precio, importe,
                            nivel, posicion, ruta_capitulos,
                            mes_inicio_relativo, mes_fin_relativo,
                            num_meses_activos, planif_anomala, planif_cruda
                        ) VALUES (
                            %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s,%s
                        )
                    """).format(sch=pgsql.Identifier(sch)),
                    [
                        self._fila_partida(p) for p in partidas
                    ],
                )

            # --- planificación mensual ---
            filas_meses = []
            for p in partidas:
                for m in p.meses:
                    if m.pct_mes == 0 and m.importe_mes == 0:
                        continue  # omitir meses sin avance (compactación)
                    filas_meses.append((
                        p.nodo_id, p.obra_id, m.posicion_mes, m.anio_mes,
                        m.pct_acumulado, m.pct_mes,
                        m.can_mes, m.can_origen,
                        m.importe_mes, m.importe_origen,
                    ))
            if filas_meses:
                cur.executemany(
                    pgsql.SQL("""
                        INSERT INTO {sch}.planificacion_mensual (
                            partida_id, obra_id, posicion_mes, anio_mes,
                            pct_acumulado, pct_mes,
                            medicion_mes, medicion_origen,
                            importe_mes, importe_origen
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """).format(sch=pgsql.Identifier(sch)),
                    filas_meses,
                )

            conn.commit()

        return {
            "capitulos": len(capitulos),
            "partidas": len(partidas),
            "meses": len(filas_meses),
            "anomalas": sum(1 for p in partidas if p.planif_anomala),
        }

    @staticmethod
    def _fila_partida(p: NodoPresupuesto) -> tuple:
        # Resumen del timing de la planificación
        meses_activos = [m for m in p.meses if m.pct_mes > 0]
        mes_ini = meses_activos[0].posicion_mes if meses_activos else None
        mes_fin = meses_activos[-1].posicion_mes if meses_activos else None
        return (
            p.nodo_id, p.obra_id, p.padre_id, p.codigo, p.descripcion,
            p.unidad_medida, p.medicion, p.precio, p.importe,
            p.nivel, p.posicion, p.ruta_capitulos,
            mes_ini, mes_fin, len(meses_activos), p.planif_anomala, p.planif_cruda,
        )


# =============================================================================
# ORQUESTACIÓN
# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrae la planificación valorada temporal del último "
                    "cuatrimestral (master coste) de las obras 0600-0800."
    )
    parser.add_argument("--cod-desde", default=None, help="Código obra desde (def. 0600)")
    parser.add_argument("--cod-hasta", default=None, help="Código obra hasta (def. 0800)")
    parser.add_argument("--solo-obra", default=None,
                        help="Procesa una sola obra por código (ej. 0707), para pruebas")
    parser.add_argument("--recrear-bbdd", action="store_true",
                        help="DROP + CREATE de la BBDD destino (¡borra datos!)")
    parser.add_argument("--dry-run", action="store_true",
                        help="No crea BBDD ni inserta: solo extrae e informa")
    args = parser.parse_args()

    cfg = Config.from_env()
    if args.cod_desde or args.cod_hasta:
        cfg = Config(**{**cfg.__dict__,
                        "cod_desde": args.cod_desde or cfg.cod_desde,
                        "cod_hasta": args.cod_hasta or cfg.cod_hasta})

    print("=" * 70)
    print("EXTRACTOR PLANIFICACIÓN CUATRIMESTRAL → PostgreSQL")
    print("=" * 70)
    print(f"  Sigrid DB     : {cfg.sigrid_database}")
    print(f"  Rango códigos : {cfg.cod_desde} .. {cfg.cod_hasta}"
          + (f"  (SOLO {args.solo_obra})" if args.solo_obra else ""))
    print(f"  Destino       : {cfg.pg_target_db}.{cfg.pg_schema} "
          f"@ {cfg.pg_host}:{cfg.pg_port}")
    print(f"  Modo          : {'DRY-RUN (sin escritura)' if args.dry_run else 'ESCRITURA'}")
    print()

    client = SigridClient(cfg)
    extractor = Extractor(client, cfg)

    # 1. Obras
    print("[1/4] Obteniendo obras del rango...")
    obras = extractor.obtener_obras(solo_obra=args.solo_obra)
    print(f"      {len(obras)} obra(s) encontrada(s).")
    if not obras:
        print("      Nada que procesar. Fin.")
        return

    # 2. Versión cuatrimestral por obra
    print("[2/4] Localizando última versión vigente (master coste)...")
    obras_validas = []
    for obra in obras:
        if extractor.elegir_version_cuatrimestral(obra):
            obras_validas.append(obra)
            print(f"      {obra.codigo}  v{obra.version_num} "
                  f"[{obra.version_tipo}] ancla={obra.fecha_ancla}  "
                  f"\"{(obra.version_tex or '')[:40]}\"")
        else:
            print(f"      {obra.codigo}  SIN versión vigente con planif → omitida")
    print(f"      {len(obras_validas)}/{len(obras)} obras con versión válida.")
    if not obras_validas:
        print("      Ninguna obra con planificación. Fin.")
        return

    # 3. BBDD destino (salvo dry-run)
    cargador = Cargador(cfg)
    if not args.dry_run:
        print("[3/4] Preparando BBDD destino...")
        cargador.crear_bbdd(recrear=args.recrear_bbdd)
        cargador.crear_schema()
    else:
        print("[3/4] DRY-RUN: se omite creación de BBDD.")

    # 4. Estructura + planificación, obra a obra
    print("[4/4] Extrayendo estructura y planificación...")
    tot = {"obras": 0, "capitulos": 0, "partidas": 0, "meses": 0, "anomalas": 0}
    for obra in obras_validas:
        try:
            nodos = extractor.obtener_estructura(obra)
        except Exception as e:  # noqa: BLE001
            print(f"      {obra.codigo}  ERROR extrayendo estructura: {e}")
            continue

        n_part = sum(
            1 for n in nodos
            if n.es_partida and not n.desactivado
            and n.importe is not None and abs(n.importe) > 0.0
        )
        n_meses = sum(
            len([m for m in n.meses if m.pct_mes > 0 or m.importe_mes != 0])
            for n in nodos if n.es_partida
        )
        n_anom = sum(1 for n in nodos if n.es_partida and n.planif_anomala)

        if args.dry_run:
            anom_str = f"  anomalas={n_anom}" if n_anom else ""
            print(f"      {obra.codigo}  partidas={n_part}  "
                  f"filas_mes={n_meses}{anom_str}  "
                  f"importe={sum(n.importe or 0 for n in nodos if n.es_partida):,.2f}")
            tot["obras"] += 1
            tot["partidas"] += n_part
            tot["meses"] += n_meses
            tot["anomalas"] += n_anom
            continue

        stats = cargador.cargar_obra(obra, nodos)
        tot["obras"] += 1
        tot["capitulos"] += stats["capitulos"]
        tot["partidas"] += stats["partidas"]
        tot["meses"] += stats["meses"]
        tot["anomalas"] += stats["anomalas"]
        anom_str = f"  anomalas={stats['anomalas']:>3}" if stats["anomalas"] else ""
        print(f"      {obra.codigo}  cap={stats['capitulos']:>4}  "
              f"part={stats['partidas']:>4}  meses={stats['meses']:>6}{anom_str}")

    print()
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"  Obras procesadas    : {tot['obras']}")
    print(f"  Capítulos cargados  : {tot['capitulos']:,}")
    print(f"  Partidas cargadas   : {tot['partidas']:,}")
    print(f"  Filas mensuales     : {tot['meses']:,}")
    if tot["anomalas"]:
        print(f"  Partidas anómalas   : {tot['anomalas']:,}  "
              f"(planif corrupta en Sigrid; cargadas sin meses, "
              f"flag planif_anomala=true)")
    if not args.dry_run:
        print()
        print(f"  BBDD: {cfg.pg_target_db}  schema: {cfg.pg_schema}")
        print(f"  Tablas: obra, capitulo, partida, planificacion_mensual")
    print()


if __name__ == "__main__":
    main()
