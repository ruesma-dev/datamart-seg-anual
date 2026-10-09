# etl_sigrid/infrastructure/postgres/contraste_estados_sql.py
"""
F-132 · El SQL de `python main.py contraste-estados`. **Solo construye texto.**

El contraste compara la foto diaria de estados de F-067 con `rac` (vía
`compras.documento_procesos`) para decidir, con cifras, si la foto se puede
retirar (Fase B, D7 del humano). Es A DEMANDA y no corre en la nocturna (D8):
la foto guarda todas sus noches y `rac` es la historia completa, así que se
recalcula entero, sobre todas las noches, cada vez que se lanza.

**Solo lectura**: cuatro `SELECT`, que el comando ejecuta en transacciones
`READ ONLY` (`PostgresClient.filas_solo_lectura`). Las dos tablas de la foto
son PERSISTENTES y no se pueden recuperar; aquí solo se leen, y
`tests/test_f132_contraste.py` fija que ningún texto de este módulo escribe.

Las fotos son `TIMESTAMPTZ` y `documento_procesos.momento` es hora de Madrid
SIN zona: se pasa con `AT TIME ZONE 'Europe/Madrid'` para compararlos. Los
literales —los tipos de la foto y el motivo de cierre CAMBIO— son los del
dominio de F-067.
"""

from __future__ import annotations

from etl_sigrid.domain.historial_estados import MOTIVOS_CIERRE, TIPOS_HISTORIAL

_CAMBIO = MOTIVOS_CIERRE[0]
_TIPOS = ", ".join(str(tipo) for tipo in TIPOS_HISTORIAL)

#: Todas las fotos, en orden: si no hay ninguna después de la línea base, no
#: hay nada que contrastar (R16).
SQL_FOTOS = """
SELECT f.observado_en, f.es_linea_base, f.n_cambios
FROM compras.historial_estados_fotos f
ORDER BY f.observado_en
"""

#: Cada CAMBIO que vio la foto (R12): el tramo cerrado por CAMBIO unido al que
#: abre la misma foto, con el estado nuevo y la ventana (`inicio`, `fin`] =
#: (`observado_antes`, `desde`] del tramo nuevo.
SQL_CAMBIOS = f"""
SELECT n.documento_id, n.tipo_documento_codigo, n.estado_id AS estado_nuevo,
       n.observado_antes AS inicio, n.desde AS fin
FROM compras.historial_estados v
JOIN compras.historial_estados n
  ON n.documento_id = v.documento_id AND n.desde = v.hasta
WHERE v.motivo_cierre = '{_CAMBIO}'
ORDER BY n.desde, n.documento_id
"""

#: Los documentos de la foto (contrato y factura) con algún paso en la ventana
#: de una foto que esa foto NO vio cambiar (R14): su estado en la foto y si
#: esa foto les abrió tramo (no de línea base). El filtro por `fecha` (día de
#: Madrid) es solo para usar su índice; la ventana exacta la da `momento`.
SQL_NO_VISTOS = f"""
WITH ventanas AS (
    SELECT f.observado_en AS fin,
           LAG(f.observado_en) OVER (ORDER BY f.observado_en) AS inicio
    FROM compras.historial_estados_fotos f
)
SELECT DISTINCT h.documento_id, h.tipo_documento_codigo, h.estado_id AS estado_foto,
       (h.desde = v.fin AND NOT h.es_linea_base) AS abierto_en_la_foto, v.fin
FROM ventanas v
JOIN compras.documento_procesos p
  ON p.fecha BETWEEN (v.inicio AT TIME ZONE 'Europe/Madrid')::date
                 AND (v.fin AT TIME ZONE 'Europe/Madrid')::date
 AND (p.momento AT TIME ZONE 'Europe/Madrid') > v.inicio
 AND (p.momento AT TIME ZONE 'Europe/Madrid') <= v.fin
JOIN compras.historial_estados h
  ON h.documento_id = p.documento_id
 AND h.desde <= v.fin AND (h.hasta IS NULL OR h.hasta > v.fin)
WHERE v.inicio IS NOT NULL
  AND p.tipo_documento_codigo IN ({_TIPOS})
  AND NOT EXISTS (
      SELECT 1 FROM compras.historial_estados x
      WHERE x.documento_id = h.documento_id
        AND x.hasta = v.fin AND x.motivo_cierre = '{_CAMBIO}'
  )
ORDER BY v.fin, h.documento_id
"""

#: Los pasos de una lista de documentos (parámetro: la lista de `documento_id`),
#: con su `momento` pasado a UTC para compararlo con las fotos (R13).
SQL_PASOS = """
SELECT p.documento_id, p.orden, p.estado_destino_id,
       (p.momento AT TIME ZONE 'Europe/Madrid') AS momento_utc
FROM compras.documento_procesos p
WHERE p.documento_id = ANY(%s)
ORDER BY p.documento_id, p.orden
"""

#: Lo que ejecuta el comando, en este orden.
CONSULTAS: tuple[str, ...] = (SQL_FOTOS, SQL_CAMBIOS, SQL_NO_VISTOS, SQL_PASOS)
