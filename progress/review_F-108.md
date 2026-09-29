Revisión completa (pasada 1) · `main...HEAD` = `323910f..250009d`

# F-108 · Review (reviewer, 2026-09-25)

**Veredicto: APPROVED** (APROBADO).

**Rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura
de lo cambiado ≥ 80 % y mutación muestreada (20, semilla 20260820) con
supervivientes analizados. RM5 no aplica.

**Puertas:** `bash harness/init.sh` tal cual sobre `250009d`.

- Pasó a segundo plano y esperé al final: **exit 0, ENTORNO LISTO**,
  5486 passed y 203 skipped en 2.548,62 s.
- `[OK] PUERTA COBERTURA`: 95.1 % (1052/1106) · `[OK] PUERTA TAMAÑO`.
- Avisos previos: ruff 233 y F-052 `blocked`.

## Los siete puntos del encargo

1. **Versión 33 (D5)** [x]: `version: 33` y cabecera `version 33 (F-108`;
   `test_f108_r19` exige `>= 33`. Correcto, `main` estaba en la 32.
2. **`check-unicidad`** [x]
   - Una consulta por alternativa, aunque se salte la de negocio (R9).
   - Excluye los NULL en la consulta y en el detalle (D1). R11 fija el texto.
   - Un KO sale con 1 (D2, R12).
   - Un objeto inexistente se informa una vez (R14).
   - Fuera de la nocturna: `r16` barre `build_pipeline_steps`, `run_all` e
     `infra/`. El diff no toca `sql/**`.
3. **Validador R5** [x]
   - `_es_unica_por` solo gana `(columna,) in claves_alternativas`. La guarda
     `None` queda intacta.
   - R7: una compuesta no es lado 1.
   - Controles R6 y R8: sin declaración, el `N:1` sigue siendo error.
   - Las cinco relaciones de `compras` pasan a `N:1` (R21).
4. **Seis claves (D3)** [x], medidas por mí (MCP, solo lectura, 2026-09-25,
   filas / distintas / NULL):
   - `maestro.obras.clave_obra` y `maestro.v_obra_fichas.clave_obra`:
     922/922/0.
   - `personal.recursos.clave_recurso`: 2.619/2.619/0.
   - `stg.obras.codigo_obra`: 584/584/0.
   - `maestro.centros_coste (empresa, codigo_centro)`: 804/804/0.
   - `maestro.cuentas_analiticas (empresa_id, codigo_cuenta)`:
     184.234/184.234/0.
   - Todas únicas hoy. `r22_solo_estan_las_seis_aprobadas` impide declarar H1.
5. **Mutación** [x]
   - Los 4 supervivientes de `main.py` eran huecos reales, y los he visto
     morir (RM4).
   - `ensure_ascii` es equivalente de contrato, con justificación escrita: en
     `estandar` basta.
6. **SQL de negocio sin cambios** [x]
   - Con el diccionario real, `unicidad_sql.py` de `main` y de HEAD dan las
     mismas 75 consultas (81 con `--todos`).
   - `sql` y `sql_detalle` son idénticos byte a byte, y los veredictos de
     negocio también (`scratchpad/cmp.py`).
7. **`azure-apps` `ae8edd3`** [x]: una línea en `datamart_seg_anual.md` con
   la clave nueva del JSONB `ficha`. `master` sin upstream: nada subido.

## Checkpoints

- **C1** [x]: `init.sh` sale con exit 0 y el arnés está completo.
- **C2** [x]
  - Una sola `in_progress` (F-108), en su rama.
  - `current.md` tiene su sección, pero arrastra 2.158 líneas de sesiones
    cerradas: deuda previa del líder (review de F-095).
- **C3** [x]: el dominio no importa infraestructura; sin SQL; ruta en la
  primera línea del test; sin `print`, secretos ni dependencias nuevas.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x]
  - R1-R24 trazables (tabla abajo). R25 es MANUAL (T11), en `current.md` y
    en `impl_F-108.md`.
  - Todo offline.
  - El doble `_PgPorClave.comprobar_unicidad(consulta, timeout_s)` casa con
    `PostgresClient` (`postgres_client.py:1128`).
- **C4 bis**
  - [x] Rigor declarado.
  - [x] RED: traza real, 58 fallos y 4 pasan (controles y guardas de R16).
  - [x] Cobertura 95,1 %.
  - [x] Recálculo independiente con `harness.alcance` y `generar_mutantes`:
    238 líneas y 37 mutantes. La semilla sortea los mismos 20, y los 5
    supervivientes coinciden en operador y en texto.
  - [x] 8.205,7 s, más de 60: **campaña no reejecutada**. Recálculo puro,
    RM1-RM6 y RM4.
  - [x] Coste por mutante: 8.205,7 × 2 ÷ 20 = 820 s, frente a ~1.070 s de
    base. Coherente con 15 muertos con `-x`.
  - [x] Sin «CAMPAÑA NO VÁLIDA»; base rota = 0.
  - [x] **RM1**: se midió en `2158cc8`, pero su alcance es igual al de HEAD
    (`==`). Después solo cambian tests y papeles.
  - [x] **RM2**: media × W = 820,6 s. 20 × 410,3 = total.
  - N/A **RM5**: el nivel es `estandar`.
  - [x] **RM6**: no se quitó ninguna guarda.
  - N/A tabla manual: la campaña generó mutantes.
  - [x] Ningún `PENDIENTE`; «Evidencias» con 2 workers.
- **C4 ter** N/A: no hay `rutas_sensibles.json`.
- **C5** [x]: T1-T10 y T12 hechas, con commit `F-108 Tn:`; T11 es MANUAL
  del humano. El árbol está limpio, salvo este informe.

## RM3 y RM4

- **RM3.** `sort_keys=True→False` (línea 146) sale muerto, aunque para el
  JSONB sería equivalente.
  - Lo mata `test_f006_r22_filas_la_ficha_jsonb_es_determinista_y_completa`
    (`list(ficha) == sorted(ficha)`), que mira la salida de la función.
  - Con ese criterio, `ensure_ascii=True` cambia el texto devuelto: es
    equivalente para el contrato, no para la función.
  - La línea es de F-006, solo reformateada. En `estandar`, aceptado.
- **RM4.** Copia `git archive HEAD` en el scratchpad (`.env.example`,
  `SIGRID_API_TIMEOUT_S=200`) y `test_f108 -k "r12 or r13 or r14"`. Base:
  8 passed.
  `omitidas = 0→1` da 3 failed; `+= 1→-= 1`, `- fallos→+` y
  `- sin_comprobar→+`, 1 failed cada uno. Mueren los cuatro; el árbol de
  trabajo no se tocó.

## Cobertura requisito → test (`tests/test_f108_claves_alternativas.py`)

| R | Tests `test_f108_...` |
|---|---|
| R1-R5 | `r1_*` (2), `r2_*` (x7), `r3_*` (3), `r4_*` (6), `r5_*` |
| R6-R11 | `r6_*` (4), `r7_*`, `r8_*` (2), `r9_*` (3), `r10_*`, `r11_*` (3) |
| R12-R15 | `r12_*` (3), `r13_*` (3), `r12_r13_*`, `r14_*`, `r15_*` |
| R16-R22 | `r16_*` (2), `r17_*` (2), `r18_*`, `r19_*`, `r20_*` (2), `r21_*` (5), `r22_*` (5) |
| R23-R24 | `test_f102_r22_...` exige N:1; `test_f107_r4` ya pedía `>= 30`; `r24_*` (2) |
| R25 | MANUAL (T11), pendiente del humano |

## Lo que falta para `done` (humano)

1. **T11 / R25**, en solo lectura con su `.env`: `python main.py
   check-unicidad` y `--todos`. Esperado: seis `OK` de alternativa, y las de
   negocio como antes.
2. Después, `python main.py publicar-diccionario` (**versión 33**).

`main` va por `4586916`, que solo toca `features.json` y `BACKLOG.md`.

## Observación (no bloquea) y automejora (propuesta)

- `.env.example` trae `SIGRID_API_TIMEOUT_S=300.0`, pero `settings.py` exige
  `<= 230`. Es ajeno a F-108.
- **RM3 debería fijar a qué nivel se juzga la equivalencia.** Propuesta:
  «equivalente = no cambia la salida de la función mutada; si solo lo es para
  el contrato, se declara así y lo acepta el reviewer». Aquí `sort_keys` y
  `ensure_ascii` darían veredictos opuestos según el criterio.
