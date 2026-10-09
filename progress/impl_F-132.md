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
| Tests nuevos | `test_f132_dominio.py` (47), `test_f132_sql.py` (21), `test_f132_contraste.py` (24), `test_f132_diccionario.py` (25): **117** |
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
- **Cuatro consultas, no tres** (`SQL_FOTOS`, para R16 y las noches sin nada);
  **columna `grupo`** (CAMBIO / NO VISTO: DISCREPANCIA existe en los dos);
  agregación y formato en el dominio, como `formatear_recuentos`.
- **Un paso sin `momento`** (uno en toda `documento_procesos`) no cae en ninguna
  ventana del contraste; en la vista cuenta su día a las 00:00 (R4).
- **P24** espera `compras.documento_procesos` primero y conserva
  `compras.historial_estados` (lo que fecha un deshacer mientras exista la
  foto); R28 (Fase B) es quien la quita.
- **R22, alcance**: `main.py`, `etl_sigrid/**`, `config/**`, `docs/**`, `README*`
  (fuera `progress/`, `specs/`, `tests/` y la historia de `00_global.yaml`).
- **Entorno**: trabajo en el worktree `../datamart-seg-anual-wt-f132` (rama
  `trabajo/F-132`), llevado a la feature por fast-forward, como F-085. Sin
  `.env` allí: los tests de CLI con `SIGRID_API_*` ficticias; manda el
  `init.sh` del árbol principal (§5).

## 3 · Fase RED (trazas reales; `PY=../datamart-seg-anual/.venv/Scripts/python.exe`)

**T1 · dominio (R4-R9, R11).** Sin módulo, y luego con un esqueleto (constantes
y dataclasses; `fecha_estado` y `dias_en_estado` con `raise NotImplementedError`):

```
$ $PY -m pytest tests/test_f132_dominio.py -q -p no:cacheprovider
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.estado_documentos'
1 error in 1.00s
$ $PY -m pytest tests/test_f132_dominio.py -q -p no:cacheprovider --tb=line
FAILED tests/test_f132_dominio.py::test_f132_r4_paso_fecha_al_segundo_del_ultimo_paso
FAILED tests/test_f132_dominio.py::test_f132_r5_alta_cuenta_desde_el_dia_de_alta[46-100]
FAILED tests/test_f132_dominio.py::test_f132_r8_alta_sin_fecha_de_alta_no_tiene_fecha_ni_dias
FAILED tests/test_f132_dominio.py::test_f132_r6_fuera_de_proceso_si_el_ultimo_paso_lleva_a_otro_estado
FAILED tests/test_f132_dominio.py::test_f132_r9_sin_fecha_no_hay_dias - NotIm...
  (... extracto: 24 en total; los 4 que pasan son las constantes y el veto de imports)
24 failed, 4 passed in 0.34s
```
GREEN: `28 passed in 0.32s`.

**T2 · contraste en el dominio (R13, R14)**, con esqueleto que lanza `NotImplementedError`:
```
$ $PY -m pytest tests/test_f132_dominio.py -q -p no:cacheprovider -k "r13 or r14" --tb=no
FAILED ...::test_f132_r13_paso_hay_un_paso_al_estado_nuevo_en_la_ventana[factura_2808958]
FAILED ...::test_f132_r13_deshecho_el_ultimo_paso_ya_llevaba_al_estado_nuevo[contrato_2833636]
FAILED ...::test_f132_r13_vuelta_al_inicial_sin_un_solo_paso
FAILED ...::test_f132_r14_ida_y_vuelta_el_ultimo_paso_deja_el_estado_de_la_foto
  (... extracto: 18 en total; pasa solo el de las constantes)
18 failed, 1 passed, 28 deselected in 0.26s
```
Con el código, 1 fallo que era del TEST (esperaba DISCREPANCIA donde R13 da
FUERA_DE_PROCESO: el último paso por `orden` lleva a otro estado); corregido el
test, `47 passed in 0.51s`.

**T3 · la vista (R1-R3, R7, R10, R11)**, antes de escribir `13` y de tocar `11`:
```
$ $PY -m pytest tests/test_f132_sql.py -q -p no:cacheprovider --tb=no -rf
FAILED tests/test_f132_sql.py::test_f132_r10_la_vista_se_tira_y_se_crea_en_13
FAILED tests/test_f132_sql.py::test_f132_r10_la_foto_ya_no_crea_la_vista - As...
FAILED tests/test_f132_sql.py::test_f132_r1_no_lee_la_foto_ni_raw - Assertion...
FAILED tests/test_f132_sql.py::test_f132_r2_publica_sus_columnas_en_orden - A...
FAILED tests/test_f132_sql.py::test_f132_r11_los_estados_iniciales_son_los_del_dominio
  (... extracto: 19 en total)
19 failed in 0.19s
```
Ficha de la vista (R18), antes de reescribirla: `8 failed in 4.19s`.
**T4 · sub-paso**: `2 failed, 19 deselected` (`...compras_acaba_en_la_vista...`,
`...el_docstring_del_paso_nombra_el_13`).

**T6-T7 · contraste (R12, R15-R17).** Sin `contraste_estados_sql.py`:
`E   ImportError: cannot import name 'contraste_estados_sql'` (1 error). Con el
módulo y sin comando ni `params`:
```
$ SIGRID_API_BASE_URL=http://ficticio SIGRID_API_FUNCTION_KEY=ficticia $PY -m pytest tests/test_f132_contraste.py -q -p no:cacheprovider --tb=line
E   AssertionError: Usage: cli [OPTIONS] COMMAND [ARGS]...
E   TypeError: PostgresClient.filas_solo_lectura() takes 3 positional arguments but 4 were given
FAILED tests/test_f132_contraste.py::test_f132_r15_sin_discrepancias_tabla_por_noche_tipo_y_clase_y_sale_con_cero
FAILED tests/test_f132_contraste.py::test_f132_r15_una_discrepancia_da_su_id_y_sale_con_uno
FAILED tests/test_f132_contraste.py::test_f132_r16_sin_fotos_despues_de_la_linea_base_no_clasifica_y_sale_con_cero
FAILED tests/test_f132_contraste.py::test_f132_r17_todas_las_lecturas_van_por_la_sesion_de_solo_lectura
FAILED tests/test_f132_contraste.py::test_f132_r17_los_parametros_viajan_tras_el_read_only
  (... extracto: 9 en total)
9 failed, 12 passed in 3.18s
```
**T8-T10 · textos.** Fichas (R18, R19) `8 failed, 8 passed`; `00_global` (R20)
`4 failed`; premisa fuera del diccionario (R21, R22), antes de corregirla:
```
E   AssertionError: docs/ARCHITECTURE.md: «la fecha del cambio de estado no existe en sigrid»
E     docs/ARCHITECTURE.md: «no hay copia en sigrid»
E     etl_sigrid/domain/historial_estados.py: «la fecha del cambio de estado no existe en sigrid»
E     etl_sigrid/infrastructure/postgres/compras_reset_sql.py: «historia que no existe en sigrid»
E     main.py: «historia de estados que no existe en sigrid»
4 failed, 20 deselected
```
Sin fase RED: R23 (escrito tras el commit de `azure-apps`) y las constantes.

## 4 · Verificación automática (resultado real)

- Por tarea, la verificación de `tasks.md` (con `-k` si el fichero cubre más).
- **En Azure, SOLO LECTURA (MCP)**: los SQL del contraste corren y dan lo de la
  spec para la noche del 2026-10-08 00:03:01 UTC: `SQL_CAMBIOS` 221 facturas +
  9 contratos = **230**; `SQL_NO_VISTOS` 88 + 1 abiertos (ALTA) y 5 no abiertos
  (IDA_Y_VUELTA) = **94**, 99 ms. De ahí salen los casos reales de los tests.
  La clasificación completa con el comando es MANUAL (§6).
- `init.sh` tras T11 salió ROJO por `test_f073_sql::r23` (huella de
  `01_documentos.sql`, tocado en un comentario): revertido (§2); el final, §5.

## 5 · Evidencias

Medidas, no estimadas. `bash harness/init.sh` final en el árbol principal,
sobre `b68c1aa` (terminado el 2026-10-09 a las 01:21 UTC): **VERDE**, `ENTORNO LISTO`.

| Evidencia | Valor real |
|---|---|
| Tests ejecutados | **7.245 passed, 229 skipped, 0 failed** (suite entera de `init.sh`); de F-132, 117 (`dominio` 47, `sql` 21, `contraste` 24, `diccionario` 25) |
| Cobertura de las líneas cambiadas | **100,0 %** (142/142, umbral 80 %, nivel estándar; `PUERTA COBERTURA`) |
| Mutación (muestreo estándar: 20 de 79, semilla 20260820, 2 workers, `--timeout 3600`) | **20 evaluados, 18 muertos, 2 supervivientes, 0 timeouts**, 5.596 s, sobre `82f0e0d`. Los dos (`--timeout`: `default=300` y `show_default=True`) eran huecos reales y los cierra un test nuevo, comprobado con el mutante aplicado a mano: `progress/mutacion_F-132.md` |
| Tiempo de la suite | **1.052,62 s (17 min 32 s)** con cobertura; 6 min 54 s sin ella en el worktree |
| Puerta de tamaño | requirements 150/150, design 246/250 (`init.sh`); este informe ≤ 220 |

La primera campaña (4 workers por defecto) se abortó sin veredicto: la línea
base no cupo en 600 s con la máquina compartida; se relanzó como F-085.

## 6 · MANUAL pendiente del humano (T14). Todo lo que escribe en Azure es suyo

Orden sugerido, tras integrar la rama:

1. **Imagen y job** (`infra/`, tag `rYYYYMMDD-HHmm` nuevo). Comprobar que el job
   apunta a ella antes de dar la feature por entregada (memoria «el repositorio
   en verde no es producción»).
2. **`python main.py build-compras`** (o esperar la nocturna). Esperado:
   SUCCESS con un sub-paso más, `estado_documentos`, de < 1 s y `rows=0` (es una
   vista). La foto (`historial_estados`) se toma igual que antes.
3. **Solo lectura**, la vista:
   `SELECT origen_fecha, tipo_documento, count(*) FROM compras.v_estado_documentos GROUP BY 1,2`
   → PASO ≈ 205.000, ALTA ≈ 1.250, FUERA_DE_PROCESO ≈ 75 (más los pasos
   lanzados entre la carga de `con` y la de `rac`; de madrugada, casi ninguno).
   `SELECT count(*) FROM compras.v_estado_documentos WHERE tipo_documento='CONTRATO' AND estado_codigo='EPF' AND dias_en_estado > 21`
   → ≈ 785.
4. **`python main.py contraste-estados`** (solo lectura, a demanda; desde el
   puesto con la rama integrada y el `.env`, sin desplegar: lee la foto y
   `documento_procesos`, que ya están en Azure). Esperado con las noches que haya: una tabla por noche
   (`observado_en` UTC, tipo, grupo, clase, documentos). Para la noche del
   2026-10-08 00:03:01, lo medido por la spec: CAMBIO 230 = 218 PASO + 9
   DESHECHO + 3 VUELTA_AL_INICIAL (facturas 214/7/0, contratos 4/2/3); NO VISTO
   94 = 89 ALTA (88 facturas + 1 contrato) + 5 IDA_Y_VUELTA (contratos);
   `Resultado: 0 DISCREPANCIA sin explicar.` y código de salida 0. Si sale 1,
   la lista de `documento_id` va en la línea `DISCREPANCIA <noche>: ...`. Al
   recalcular sobre todas las noches, un paso deshecho DESPUÉS de una noche
   cambia la clase de esa noche (de PASO a DESHECHO): es la historia neta. El
   líder pega la salida, fechada, en `progress/contraste_F-132.md`; mínimo al
   terminar el plazo (2026-10-22).
5. **`python main.py publicar-diccionario`** (v46) y **`check-diccionario`**:
   esperado OK, 207 objetos, 1.623 columnas (la vista pasa de 11 a 15).
6. **Reiniciar el MCP** (`mcp-bbdd`, sin cambios de lista blanca) y preguntarle,
   sin explicar nada, «¿qué contratos llevan más de tres semanas enviados sin
   firmar y desde cuándo?» (R24). Esperado: filtra `v_estado_documentos` por
   CONTRATO, EPF y `dias_en_estado > 21`, da `en_estado_desde` como fecha real
   del envío y avisa de los envíos antiguos sin cerrar (solo ~23 de 2025 en
   adelante).
7. `git push` de esta rama y de `azure-apps` (`89f63d5`), cuando el humano lo decida.

## 7 · Riesgos, fuera de alcance y lo que falta

- **La vista cambia de forma** (D4): fuera `cambio_observado_tras`,
  `antiguedad_es_minima` y `ultima_foto`. Su único consumidor es el MCP, que
  necesita la v46 publicada y reiniciarse; entre desplegar la imagen y publicar,
  la ficha publicada (v45) describe columnas que ya no existen.
- **La vista cae cada noche con el `CASCADE` de `12`** y la levanta `13`: si
  `12` o `13` fallan, esa noche no hay vista.
- **Desfase de ingesta**: un paso lanzado entre la carga de `con` y la de `rac`
  sale FUERA_DE_PROCESO un día (la ficha lo dice).
- **Historia NETA**: el deshacer no se fecha; con la foto retirada, hasta F-105.
- **Fuera de alcance (Fase B, D7)**: retirar, congelar o conservar la foto,
  `retirar-foto-estados`, `reset-compras` sin conservadas, v47. Nada tocado.
- **Texto viejo que queda**: la cabecera de `01_documentos.sql` dice que la
  antigüedad «la da la foto diaria»; no se toca (spec y huella de F-073).
- **Falta para cerrar**: review; MANUAL de §6 (despliegue, `build-compras`,
  contraste, v46, MCP y R24); contraste de 14 noches y decisión D7.
