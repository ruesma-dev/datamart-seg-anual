Revisión incremental desde bb1b130 (pasada 2) · `git diff bb1b130..e05fde7`

# F-168 · Review · El texto largo de la partida y del flujo de obra

**Veredicto (pasada 2): PENDIENTE DE LA PUERTA. Esto todavía NO es un APPROVED.** La feature no tiene
nada pendiente de cambiar: los tres cambios de la pasada 1 están hechos y verificados. Solo faltan
C1 y la cobertura, que dependen de la puerta completa del líder. Esa puerta está parada porque `main`
va por detrás de `dev`, un problema de base que tiene que resolver el humano. Cuando la puerta salga
en verde, se marcan esos dos puntos y el veredicto pasa a **APPROVED** sin volver a mirar el código
(salvo que la puerta descubra algo). Mientras siga en rojo, el reviewer no aprueba.

**Pasada 1 (resumen):** CHANGES_REQUESTED sobre `bb1b130`. El código y el SQL estaban bien, y los
ejecuté: sandbox 13/13, `03_lineas_master.sql` real, migración desde la base, y 1.301 tests de F-168 y
de los adaptados en verde. Pedí tres cambios: (1) un test de R17; (2) las verificaciones MANUAL en
`current.md` con su comando, y T14 con `--full`; (3) marcar T9.

**Nivel de rigor:** `estandar` (declarado). Mutación informativa; capa e2e N/A. No hay pasada de
evidencias.

## Pasada 2 · el delta

`d4d7709` (implementer) toca `tests/test_f168_sql.py`, `tests/test_f168_sandbox.py`, `tasks.md`,
`impl_F-168.md`, `current.md` y versiona esta review. `e05fde7` (líder) añade `spec_aprobada:
2026-11-23` en `features.json` y regenera `BACKLOG.md`. El delta **no toca código de producción, SQL ni
el diccionario**, así que lo aprobado en la pasada 1 sigue valiendo.

| Cambio pedido | Estado | Comprobación |
|---|---|---|
| 1. Test de R17 | **Hecho** | Test estático `test_f168_r17_las_claves_del_comparativo_son_las_de_linea_texto`: `09` publica `NULLIF(l.dncproide, 0) AS linea_necesidad_id` y `lp.ide AS linea_oferta_id` (desde `raw.dcopro lp`), y las ramas NECESIDAD/OFERTA de `16` usan `n.ide`/`o.ide`. Test de sandbox `..._r17_comparativo_y_oferta_llegan_al_texto_sin_intermedias`: las dos llegan al texto por (`tipo_linea`, `linea_id`). Su RED es una mutación a mano (`o.dncproide` en vez de `o.ide`), con la traza en `impl_F-168.md` |
| 2. MANUAL en `current.md` y T14 `--full` | **Hecho** | `current.md` trae T13-T16 con sus comandos y sus SQL exactos, y el push. T14 pasa a `python main.py ingest --full --table <t>` para cada una de las seis, con el motivo, en `tasks.md`, `impl` y `current.md` |
| 3. T9 | **Hecho** | `[x]` con su evidencia (14/14 con R17); `impl` corrige «no hay Postgres local» |

Una observación sobre el cambio 1: la parte de sandbox usa la clave NECESIDAD como literal
(`VALUES (501)`), porque la sandbox no construye `compras/09`. Junto con el test estático que fija las
dos claves en `09`, basta para R17.

**Tests de nuevo**, sobre `e05fde7`: los 6 `test_f168_*` y los 15 ficheros adaptados, contra un
PostgreSQL 16 desechable en mi scratchpad (`initdb -A trust` + `pg_ctl` en el puerto 54399; lo borré
al acabar). Resultado: **1.303 passed, 4 skipped (no son de F-168), 0 failed, en 372,32 s**. Son los
1.301 de la pasada 1 más los 2 de R17. No relancé la suite entera, por instrucción del líder.

## Checkpoints (estado tras la pasada 2)

**C1** — [ ] `ARNES_SIN_CACHE=1 bash harness/init.sh` en verde: **pendiente de la puerta del líder**.
Saldrá en rojo con los dos KO de base ya conocidos (`PUERTA COBERTURA` y
`test_en_este_repositorio_la_base_no_esta_rezagada`, por `main` detrás de `dev`). No son de F-168, pero
no se aprueba con la puerta en rojo. [x] Los ficheros del arnés están.

**C2** — [x] una sola feature activa. [x] orden de prioridad respetado. [x] rama `feature/F-168-...`.
[x] `current.md` abre con la sesión activa. [x] resúmenes en `history.md`. `spec_aprobada` ya consta.

**C3** — [x] hexagonal, [x] ruta en la primera línea, [x] sin `print`, TODO, secretos ni dependencias
nuevas, [x] semántica de Sigrid: sin cambios desde la pasada 1. **C3 bis** N/A (no toca
`docs/referencia/`). **C3 ter** N/A (el diff no atribuye afirmaciones nuevas a nadie).
**C3 quater** [x]: `azure-apps` `2f4d08c` toca solo `datamart_seg_anual.md`, va en un commit aparte, no
se ha subido y coincide con la «Frontera» de la spec.

**C4** — [x] cada requisito tiene su test (R17 incluido). R11 y R27 son MANUAL (T14 y T15) y R26 lo
verifica el reviewer. [x] los unit no tocan red ni BBDD. [x] las MANUAL están en `current.md` con su
comando exacto. [x] dobles: el de `test_f150` acepta `recortes=`; la comprobación automática corre en
la puerta del líder.

**C4 bis** — [x] nivel `estandar` declarado. [x] fase RED con trazas reales (T1-T8, T10 y R17).
[ ] cobertura de lo cambiado: **pendiente de la puerta del líder**. N/A por nivel: mutación, RM1-RM7 y
análisis de supervivientes (en `estandar` la mutación es informativa). [x] sección «Evidencias»
completa. Capa e2e N/A (`CAPA E2E: N/A`). C4 ter N/A (no hay `harness/rutas_sensibles.json`).

**C5** — [x] T1-T12 en `[x]`. T13-T16 son MANUAL de después del despliegue y T17 es la puerta: siguen
abiertas con motivo. [x] un commit `F-168 Tn:` por tarea, más el de la review. [x] el árbol del
worktree está limpio. [x] `features.json` dice `in_progress`; el líder la pasará a `in_review`.

## Requisito → test (`test_f168_` + …)

R1 `r1_*` · R2 `r2_*` (3) · R3 `r3_*` (6) · R4 `r4_*` (5) · R5 `r5_*` (10) + sandbox · R6 `r6_*` (5) ·
R7 `r7_*` (3) · R8 `r8_*` + sandbox · R9 `r9_*` · R10 `r10_*` + sandbox · R11 MANUAL (T14) ·
R12 `r12_*` (2) · R13 `r13_*` (5) + sandbox · R14 `r14_*` + sandbox · R15 `r15_*` + sandbox ·
R16 `r16_*` + sandbox · **R17 `r17_*` (estático y sandbox)** · R18 `r18_*` + sandbox · R19 `r19_*` (4) ·
R20 `r20_*` (7) + sandbox (y el master con mi script de la pasada 1) · R21 `r21_*` (5) + sandbox ·
R22 `r22_*` · R23 `r23_*` + sandbox · R24 `r24_*` (2) · R25 `r25_*` (7) · R26 reviewer (`2f4d08c`) ·
R27 MANUAL (T15).

## Lo que pidió el líder en la pasada 1 (sigue en pie: el delta no lo toca)

- **`descompuestos` sigue siendo incremental.** No hay ningún `DROP` ni `TRUNCATE` de `lineas`,
  `textos`, `_des_texto` ni `_versiones_cargadas`. El sello suma `../stg/11_texto_largo.sql`. El
  retroceso que provoca el cambio de sello lo probé con el `03` real.
- **El recorte a 16.000 se aplica de verdad en origen.** `stream_table` pide `expresion_recorte('tex',
  16000)`, y es la única vía de ingesta de `raw`. Dos tests lo fijan: uno el SQL que se envía y otro
  que el paso le pasa los recortes. La prueba contra Sigrid real es T13, MANUAL del líder.
- **D6:** ningún `GRANT`, `REVOKE` ni esquema `_restringida`. `apply_grants` concede por esquema, así
  que los objetos nuevos heredan los permisos sin código.
- **Diccionario v82:** cubre todos los objetos y columnas nuevos y las trampas de design §7.

Las desviaciones declaradas por el implementer las juzgué en la pasada 1 y siguen justificadas.
`PRESUPUESTO_MAX` +220 va contra la letra de R25 («sin pasarse»), pero es la práctica del repositorio
y trae su motivo escrito: el líder tiene que decírselo al humano en el resumen.

## Observaciones (no bloquean; pasan al resumen final)

1. **La primera noche.** `stg/11` va el ÚLTIMO de `build_stg`. Si esa noche falla un sub-paso anterior
   de `stg`, caen también `compras/16` y todo `build_descompuestos`, porque aún no existen las
   funciones. Moverlo al principio de `build_stg` (son funciones puras) lo evitaría.
2. **El coste del CTE de `03`.** `troceado` se lee dos veces, así que Postgres lo materializa. Con
   `--sin-tope` es el master entero en disco temporal: en T14, mirar `temp_bytes` y los créditos de CPU
   antes de lanzarlo.
3. **`PRESUPUESTO_MAX` +220**, contra la letra de R25: el humano tiene que verlo.
4. **`progress/current.md`** arrastra unas 6.200 líneas de sesiones anteriores. Es previo a F-168:
   purgarlo al cerrar.
5. **Mutación:** todavía no hay `progress/mutacion_F-168.md`. Es informativa: sus totales van al
   resumen final.

## Automejora (propuesta, no aplicada)

- En `implementer.md` y `reviewer.md`: antes de declarar «sin Postgres local», buscar
  `C:\Program Files\PostgreSQL\*\bin\initdb.exe` y levantar un clúster desechable en el scratchpad.
  Así las sandbox que se saltan dan evidencia, sin tocar nada compartido.
- Ninguna sandbox ejecuta `descompuestos/03_lineas_master.sql`: añadir un caso de master la próxima
  vez que alguien toque `03`.
