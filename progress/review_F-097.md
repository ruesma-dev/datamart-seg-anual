<!-- progress/review_F-097.md -->
Revisión incremental desde 7d7dc0b (pasada 2) · delta hasta HEAD `6ca684d`

# F-097 · Review del reviewer

**Veredicto (pasada 2): CHANGES_REQUESTED.** Los tres cambios de la pasada 1 están bien
resueltos y lo he comprobado con la misma evidencia. Lo que falta es de la campaña de
mutación: el delta toca el alcance mutado, así que por RM1 el informe de mutación ya no vale,
y al repetirla salen **dos supervivientes nuevos, los dos huecos reales de test** y sin
analizar. Es trabajo pequeño: dos tests y un informe que ya está generado (abajo).

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura >= 80 % de lo
cambiado y campaña de mutación con los supervivientes analizados. RM5 no aplica.

## Pasada 2

**Delta** (`057b8d1`, `c2b1b53`, `e366d05`, `6ca684d`): `01_troceado.sql`,
`02_lineas_coste.sql`, `domain/descompuestos.py`, `build_descompuestos_step.py`, dos
ficheros de test, `current.md`, `impl_F-097.md` y este informe (el implementer lo commiteó).
No cambia firmas públicas ni ficheros de sitio. Lo aprobado en la pasada 1 sigue en pie,
salvo la validez del informe de mutación (RM1, abajo).

- **Cambio 1 (rango), RESUELTO.** Los dos importes de `fn_trocear` y los de PLANIF_JO van
  ahora con `CASE WHEN abs(ROUND(x, 2)) < 1e16 THEN ... END`, y el espejo tiene
  `LIMITE_IMPORTE`. PostgreSQL 16 local desechable (`00`+`01` recargados): `12345678901234567`,
  `-99999999999999999`, `1e300` y `…999.995` → importes NULL con el precio publicado;
  `9999999999999999.99` cabe. `02_lineas_coste.sql` ejecutado sobre un `raw` de juguete con
  un `dncpro.pre = 1e20` y un `des` de 17 cifras: termina, e importes NULL en ESTUDIO y en
  PLANIF_JO. Desviación 9 del informe corregida.
- **Cambio 2 (`$`), RESUELTO.** `fullmatch` en `_NUMERO` y `_ENLACE`, y también en el cod
  de la vigente y en el sello (la misma trampa, bien visto). Mis 15 casos límite, espejo
  frente a SQL, son **todos iguales** (antes fallaban 2 y reventaban 2): 38/37/35/29/19
  campos, CRLF, texto largo con saltos, `12\n`, enlace `55\n`, 17 cifras, `1e300`, `1e999`,
  los dos lados del límite, cabecera basura y `~d|`.
- **Cambio 3, RESUELTO:** el título de la sección F-097 de `current.md`.
- **Hallazgo 3, bien tratado:** anotado en «Review 1 atendida» de `impl_F-097.md` como
  candidato a ficha menor y NO arreglado aquí.
- **Fase RED del delta:** traza real en `impl_F-097.md` (8 failed, 1 passed).
- **Mutantes del delta, uno a uno** (RM4, copia con `git archive`, suites de F-097 y el
  barrido de dataclasses): 15 mutantes en las líneas cambiadas, 14 muertos. El que vive,
  `descompuestos.py:179` `>=` → `>`, es **equivalente**: con |x| = 1e16 exacto la segunda
  guarda (`:182`) devuelve NULL igual. Sin mutar: 344 passed.
- **RM1: el delta toca el alcance** (`descompuestos.py`, `build_descompuestos_step.py`) y el
  informe de mutación está medido en `c1bf0bf`. Repetí la campaña en HEAD con la
  herramienta (`--salida` fuera de `progress/`, 2 workers): **178 mutantes, 20 evaluados,
  18 muertos, 2 supervivientes**, 0 timeouts y 0 sin veredicto en 3.945,6 s; SHA
  `6ca684d`; base 448,4 s y media 197,3 s (× 2 = 394,6 s por mutante, coherente, RM2).
  Árbol limpio y sin worktrees de la campaña después. Informe:
  `<scratchpad de la sesion>\revisor\mutacion_F-097_pasada2.md (copiado a progress/mutacion_F-097.md en R2-1)`.
  - **S1 · `descompuestos.py:437`** `acumulado + pendiente.bytes > limite` → `>=`. No es
    equivalente: un lote que llega EXACTAMENTE a `mb_por_lote` se partiría en dos. Ningún
    test del troceado cae justo en el límite (el de la relectura sí:
    `r6_justo_en_el_tope_cabe`).
  - **S2 · `main.py:5140`** `--sin-tope` de `ingest-descompuestos` con `default=True`. No es
    equivalente, y es el más serio: `python main.py ingest-descompuestos` a secas haría la
    primera carga (2,14 GB, 1,5-2 h) sin avisar. `r25_comandos_sueltos_con_sin_tope` mira que
    la opción exista y se pase, no su valor por defecto. Lo mismo vale para
    `build-descompuestos`.
- `bash harness/init.sh` entero: exit 0, **5928 passed, 219 skipped**, cobertura 99,6 %
  (516/518), tamaño en tope (ojo: `impl_F-097.md` 214/220, el análisis va en el de mutación).

### Cambios requeridos (pasada 2)

1. `progress/mutacion_F-097.md`: sustituirlo por una campaña medida sobre el alcance
   actual. Vale **copiar el informe de arriba** (lo generó la herramienta sobre `6ca684d`;
   RM1 lo sigue dando por bueno mientras los commits siguientes toquen solo tests y
   `progress/`), o relanzarla. Completar el análisis de S1 y S2 en el informe.
2. Test de S1 en `test_f097_planificador.py`: dos pendientes cuya suma es exactamente
   `mb_por_lote` van en UN lote.
3. Test de S2 en `test_f097_descompuestos.py`: el `default` de `--sin-tope` es `False` en
   `ingest-descompuestos` y en `build-descompuestos` (mejor por comportamiento: invocar el
   comando con `CliRunner` y un paso doblado, y comprobar que llega `sin_tope=False`).
4. Anotar en el análisis el equivalente `descompuestos.py:179` (no lo sorteó la muestra; lo
   encontré en el delta) con su motivo, para que nadie lo persiga.

## Pasada 1 (resumen; el texto completo, en `git show e366d05:progress/review_F-097.md`)

Revisión completa de `main...7d7dc0b`: **CHANGES_REQUESTED**. Hallazgos: (1) MEDIA,
`fn_trocear` reventaba con un número válido grande (`numeric field overflow`) y el espejo no
(o con `InvalidOperation`); (2) BAJA, el espejo aceptaba un `\n` final que el SQL rechaza;
(3) BAJA, un error de Postgres al escribir una versión aborta la ingesta entera (a ficha
menor); (4) INFO, PK de `lineas`/`cuadre_partida` sobre `(obra, partida, amb, fas)`: 0
repetidos en Sigrid (solo lectura); (5) INFO, SQL probado por texto (convención F-056);
(6) INFO, título de `current.md`. Los cambios 1-3 salían de 1, 2 y 6.

Verificado en la pasada 1 y sin tocar por el delta: el incremental (ningún `DROP`/`TRUNCATE`
de las tablas de estado; `reemplazar_filas` en una transacción; recuento distinto → no se
escribe y se relee la noche siguiente; tope vigente > cambiada > nueva, ámbito 3 primero,
`--sin-tope`); orígenes y marcas (v0, primera ABC, vigente, `tipo_version` de `mart`,
`SUSTITUIDO_POR_PLANIFICACION` solo en ESTUDIO); cuadre (hoja, `pre <> 0`, `obride <> 0`,
tolerancia 0,01, `SIN_DESCOMPUESTO`); R29 solo en `obrparpre` (las otras 13, F-115); D3 y
`check-declarados` (11 objetos, sin rojo propio tras la primera noche en verde);
diccionario (master INCOMPLETO, tipos 3 y 11 PROVISIONALES, `version: 37`); sin secretos ni
escrituras en Azure; `azure-apps` 85356e6 sin push. Mutación de la pasada 1: 175 mutantes
recalculados, muestreo reproducido, RM1-RM4 y los 4 supervivientes reproducidos en copia.

## Checkpoints (estado tras la pasada 2)

- C1: [x] `init.sh` exit 0 (arriba) · [x] ficheros del arnés.
- C2: [x] una `in_progress` · [x] rama correcta · [x] `current.md` solo añade lo de F-097 ·
  [x] `done` con resumen en `history.md` (sin cambios).
- C3: [x] hexagonal y SQL en `sql/descompuestos/NN_*.sql` · [x] ruta en primera línea ·
  [x] sin prints de debug, secretos ni dependencias nuevas · [x] troceado robusto (cambios
  1-2 resueltos); ámbito/fase y versiones duplicadas de `obrfasamb`, bien.
- C3 bis: N/A, no toca `docs/referencia/`. C4 ter: N/A, sin `rutas_sensibles.json`.
- C4: [x] R2-R29 con test (`test_f097_un_test_por_requisito`); R1, R30, R31 MANUAL · [x]
  sin red ni BBDD · [x] MANUAL en `current.md` con comando y resultado esperado (T0 con
  PARAR, T17, T18 C1-C4, T19) · [x] dobles contra el original (barrido de la suite, verde).
- C4 bis: [x] `rigor` · [x] RED con trazas (pasada 1 y delta) · [x] cobertura (arriba) ·
  [ ] **mutación: el informe de `progress/` está medido en `c1bf0bf` y el delta toca el
  alcance (RM1)** · [x] muertos: campaña > 60 s, recálculo + RM1-RM4, y además repetida por
  mí en HEAD · [x] coste por mutante 394,6 s · [x] sin cabecera no válida · [ ] **RM1**
  (ver cambio 1) · [x] RM2 · N/A RM5 (`estandar`) · [x] RM6 (no se quitó código defensivo:
  las guardas nuevas añaden defensa) · N/A campaña manual (la automática dio 178) ·
  [ ] **supervivientes analizados: S1 y S2 sin análisis** · [x] «Evidencias» con 2 workers.
- C5: [x] tareas `[x]` con commit `F-097 Tn:` (y `R1-n` de la review); T0, T17, T18, T19
  MANUAL `[ ]` a propósito (bloquean la puesta en producción, decisión del humano del
  2026-09-28) · [x] sin temporales · [x] `features.json` en `in_progress`.

## Cobertura requisito → test (prefijo `test_f097_`)

| Req. | Test | Req. | Test | Req. | Test |
|---|---|---|---|---|---|
| R1 | MANUAL T0 | R11 | `r11_*` (2) | R21 | `r21_*` (dominio y SQL) |
| R2 | `r2_*` (7) | R12 | `r12_*` (2) | R22 | `r22_catalogo_de_elementos` |
| R3 | `r3_*` (3) | R13 | `r13_*` (14) | R23 | `r23_*` (2) |
| R4 | `r4_*` (5) | R14 | `r14_*` (8) | R24 | `r24_tres_vistas_*` |
| R5 | `r5_*` (11) | R15 | `r15_estudio_sin_*` | R25 | `r25_*` (8) |
| R6 | `r6_*` (10) | R16 | `r16_planif_jo_*` | R26 | `r26_*` (2) |
| R7 | `r7_*` (3) | R17 | `r17_*` (6) | R27 | `r27_*` (6) |
| R8 | `r8_*` (8) | R18 | `r18_identificacion_*` | R28 | `r28_documentacion` |
| R9 | `r9_*` (3) | R19 | `r19_*` (7) | R29 | `r29_*` (4) |
| R10 | `r10_*` (3) | R20 | `r20_clave_*` | R30-31 | MANUAL T17-T18 |

## Automejora (propuesta, no aplicada)

- `reviewer.md`: si hay **espejo** Python de un SQL, contrastar ambos en casos límite en un
  PostgreSQL local desechable (números enormes, saltos en campos). Cazó los hallazgos 1 y 2.
- `CHECKPOINTS.md`/RM1: cuando la review pide cambios en código del alcance, recordar en
  el propio informe de review que la campaña caduca; aquí costó una pasada más.
