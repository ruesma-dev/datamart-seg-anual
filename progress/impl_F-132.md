<!-- progress/impl_F-132.md -->
# F-132 · Informe del implementer · Fase A · la antigüedad del estado sale de `rac`

Rama `feature/F-132-estado-desde-rac`, 2026-10-08/09. Rigor **estándar**. Spec
aprobada con D1-D8 (`progress/spec_F-132.md` §7). **Solo la Fase A** (T1-T15);
la B (qué hacer con la foto) NO se ha tocado. Un commit por tarea
(`git log 4d25fcb..HEAD`). **Nada se escribió en Sigrid ni en el Postgres de
Azure**: los tests leen el texto del SQL y del YAML; las únicas lecturas
externas fueron `SELECT` por el MCP (solo lectura) para sacar los casos reales
de los tests y comprobar que los SQL del contraste corren (§4).

## 1 · Qué cambió

| Fichero | Qué |
|---|---|
| `etl_sigrid/domain/estado_documentos.py` (nuevo) | Oráculo puro: `FAMILIAS_ESTADO` {44,15,46}, `ESTADOS_INICIALES`, `ORIGENES_FECHA`, `PasoEstado`, `FechaEstado`, `fecha_estado`, `dias_en_estado` (R4-R9, R11); `CLASES_CAMBIO`, `CLASES_NO_VISTO`, `clasificar_cambio`, `clasificar_no_visto` (R13-R14); `Contrastado`, `contrastar`, `discrepancias`, `formatear_contraste` (R15) |
| `sql/compras/13_estado_documentos.sql` (nuevo) | `DROP VIEW IF EXISTS` + `CREATE VIEW compras.v_estado_documentos` desde las tres cabeceras y el último paso de `documento_procesos`; 15 columnas de R2 (R1-R10) |
| `sql/compras/11_historial_estados.sql` | Pierde la vista y la cabecera ya no afirma la premisa: la foto es RESPALDO (F-132). Lo ejecutable restante es IDÉNTICO a 4d25fcb (huella fijada en test) |
| `application/steps/build_compras_step.py` | Sub-paso `estado_documentos` (`13`, sin tabla destino) el ÚLTIMO; docstring |
| `infrastructure/postgres/contraste_estados_sql.py` (nuevo) | Cuatro `SELECT`: `SQL_FOTOS`, `SQL_CAMBIOS`, `SQL_NO_VISTOS`, `SQL_PASOS` |
| `infrastructure/postgres/postgres_client.py` | `filas_solo_lectura(..., params=None)`: el parámetro viaja al `execute` solo si se pasa |
| `main.py` | Comando `contraste-estados [--timeout]`; docstring de `reset-compras` sin la premisa |
| `config/diccionario/compras.yaml` | Ficha de `v_estado_documentos` reescrita (15 columnas, 3 familias, orígenes, historia neta, envíos antiguos); `contratos`, `historial_estados`, `historial_estados_fotos`, `fn_sigrid_tiempo` (R18) |
| `config/diccionario/raw.yaml` | Ficha de `conest` (R19) |
| `config/diccionario/00_global.yaml` | **v46** con su historia; esquema `compras`; P23 respondible; P24 con `documento_procesos` (R20) |
| `config/tables_sigrid.yaml`, `docs/ARCHITECTURE.md`, `README_COMPRAS_C1_C2.md` | La antigüedad sale de `rac`; la foto, respaldo (R21). ARCHITECTURE gana la viñeta de F-132 |
| `domain/historial_estados.py`, `compras_reset_sql.py`, `01_documentos.sql` | Solo docstrings/comentarios que afirmaban la premisa o la vista vieja (R22) |
| `../azure-apps/datamart_seg_anual.md` | Sección F-132; F-067 «DESPLEGADA el 2026-10-07» y sin «Sigrid no la guarda» ni «no hay copia en Sigrid». Commit **`89f63d5`** en `azure-apps`, sin push (R23) |
| Tests nuevos | `test_f132_dominio.py` (47), `test_f132_sql.py` (21), `test_f132_contraste.py` (23), `test_f132_diccionario.py` (25): **116** |
| Tests ajustados | `test_f067_sql` (fuera r9-r11 de la vista; `QUIEN_PUEDE_NOMBRARLAS` + `contraste_estados_sql.py`), `test_f067_diccionario` (fuera r10, r11 de la vista y p23 parcial), `test_f006_reglas` (P23 respondible: 22/2/2), listas de sub-pasos de `f047`, `f073`, `f080`, `f085` |

## 2 · Decisiones y desviaciones (justificadas; también en `progress/current.md`)

- **La ficha de la vista entra en T3, con su SQL**, no en T8 (orden del líder:
  ficha en el mismo commit que el objeto). Con ella pasan a T3 la retirada de
  los tests de la vista vieja (`test_f067_sql` r9-r11, de T5; `test_f067_diccionario`
  r10/r11, de T9).
- **Sin relación `paso_id` → `documento_procesos`** en la ficha: el validador R5
  de F-006 la rechaza (la clave de la vista es `documento_id`); el camino se
  explica en la columna.
- **Lectura en solo lectura por `filas_solo_lectura`** (transacción `READ ONLY` +
  `statement_timeout` con `SET LOCAL`, la vía única del repositorio) en vez de
  una conexión `read_only = True`: misma garantía, la impone el motor. Gana un
  `params` opcional para `= ANY(%s)`; sin él, la llamada es la de siempre.
- **Cuatro consultas, no tres**: `SQL_FOTOS` hace falta para R16 y para decir
  qué noches no tuvieron nada que contrastar.
- **Columna `grupo` (CAMBIO / NO VISTO)** en la tabla del informe: DISCREPANCIA
  existe en los dos grupos y sin ella no se distinguen.
- **Agregación y formato en el dominio** (`contrastar`, `formatear_contraste`),
  como `formatear_recuentos`; el comando solo lee y convierte filas.
- **Un paso sin `momento`** (uno en toda `documento_procesos`) no cae en ninguna
  ventana del contraste; en la vista cuenta su día a las 00:00 (R4).
- **P24** espera `compras.documento_procesos` primero y conserva
  `compras.historial_estados` (lo que fecha un deshacer mientras exista la
  foto); R28 (Fase B) es quien la quita.
- **R22, alcance**: código (`main.py`, `etl_sigrid/**`), `config/**`, `docs/**`
  y `README*`; fuera `progress/`, `specs/`, `tests/` y la historia de
  versiones de `00_global.yaml`. Frases conocidas, con saltos de línea y
  marcas de comentario plegados.
- **Entorno**: trabajo en el worktree `../datamart-seg-anual-wt-f132` (rama
  temporal `trabajo/F-132`), llevado a la rama de la feature por fast-forward,
  para no ensuciar el `init.sh` de arranque (el barrido de dataclasses de F-006
  ve módulos de `domain/` creados con la suite corriendo, como en F-085). En el
  worktree no hay `.env`: los tests de CLI se pasaron allí con
  `SIGRID_API_BASE_URL`/`SIGRID_API_FUNCTION_KEY` ficticias (sin secretos) y el
  veredicto es el `init.sh` del árbol principal (§5).

PENDIENTE_RED_Y_RESTO
