# progress/review_F-163.md
Revisión completa (pasada 1) · diff `e086ee4...8fdfece` (rama `feature/F-163-completa-fin-de-semana`)

## Veredicto: CHANGES_REQUESTED

La lógica es correcta, los tests la blindan y la desviación de `PG_VENTANA_DIA_COMPLETA` es la
lectura acertada. Se rechaza por **texto publicado que miente**: cada obra de la completa del
sábado se registra con el `detalle` «reconstruccion completa semanal (domingo)», que sale tal
cual en `_meta.v_frescura_obra`, más el rastro de «domingo» del punto 5. Cambios pequeños.

**Nivel de rigor:** `estandar` (declarado): fase RED, cobertura de lo cambiado y «Evidencias»;
mutación informativa (campaña tras el APPROVED).

## Cambios requeridos

1. **[Media] `etl_sigrid/domain/ventana.py:478`.** `_decidir` devuelve
   `"reconstruccion completa semanal (domingo)"` como `detalle` de TODA obra reconstruida por
   `completa`. Ese texto se escribe en `_meta.obra_build.detalle` y se publica en
   `_meta.v_frescura_obra.detalle`, que `_meta.yaml:802` y `:883` describen como «la misma
   decisión en una frase legible». Desde F-163 la completa normal es la del sábado, así que el
   dato publicado es falso en cada completa (y ya lo era con `--reconstruir-todo` y con la
   ventana apagada). Usar un texto neutro (p. ej. «reconstruccion completa: entra todo») y
   fijarlo con un test que compruebe que el `detalle` no nombra un día.
2. **[Baja] Restos de «domingo» del punto 5.** Docstrings y comentarios que siguen diciendo que
   la completa es el domingo: `etl_sigrid/domain/ventana.py:49` («los domingos entra todo»),
   `:67` («El domingo la pone al día»), `:418` («la noche del domingo entra todo»);
   `etl_sigrid/infrastructure/postgres/postgres_client.py:372` y `:442` («la cierra la
   reconstrucción del domingo» / «el domingo»), `:524` («cada domingo»);
   `tests/test_f025_cli.py:309` (docstring «El domingo no corrió»). En el mismo cambio:
   - `config/settings.py:504-506`: la descripción sigue llamando al domingo «la noche que puede
     permitirse volver a costar lo que cuesta hoy», y desde F-163 el domingo es solo la reserva.
     Reescribirla: «6 = el sábado hace la completa y el domingo es la reserva».
   - `infra/env/dev.json:62` (`$aviso_ventanaEnv`): añadir una frase con el significado de
     `ventanaDiaCompleta` (ÚLTIMO día; la completa va la víspera): es donde se configura.
3. **[Baja] `azure-apps` 006b293 (`datamart_seg_anual.md`).** Solo toca ese fichero, va en un
   commit aparte y sin push, y lo que dice coincide con el código (C3 quater bien en forma). Pero
   el párrafo nuevo «Techo de una ejecución: 14 h» y «Todas se rehacen enteras la noche del
   sábado» están escritos en presente, y **no está desplegado**: el job sigue con 25.200 s y la
   imagen vieja. El documento marca «SIN DESPLEGAR» en otras secciones (F-161): añadir esa marca
   (se quita al desplegar) en un commit nuevo en `azure-apps`, aparte y sin push.

## Respuesta a los puntos del encargo

**1 · `toca_reconstruccion_completa` frente a D1/D2. Correcta.** Sábado: `ultima.date() < hoy`
(no se repite el mismo día, tampoco con un puntual el sábado por la tarde). Domingo:
`< hoy - 1` (la del sábado a las 00:00, 04:52 o 23:59 la anula, y una que acabó ya en domingo
también). Lunes a viernes nunca; `None` cualquier día. `--reconstruir-todo` manda
(`build_stg_step.py:667`): forzado un viernes, el sábado se repite, como dice D1. UTC coherente:
`utcnow()` y `etl_runs.finished_at TIMESTAMP` sin zona (`00_meta.sql:12`). **Reanudación
(F-148):** el lote se adopta por el sufijo del NOMBRE de la ejecución (15 h no alcanza otra
noche). Un reintento que rehace `build_stg` vuelve a decidir con `utcnow()`: si la completa del
sábado (o del domingo de reserva) se cortó sin hito, el reintento cae el mismo día (≤ 14 h) y la
rehace. Si murió tras el hito y antes del `SUCCESS` (VACUUM), hace una acotada, lo correcto
porque la completa sí terminó. Si el sábado acabó sin hito, el domingo la rehace.

**2 · Desviación `PG_VENTANA_DIA_COMPLETA` = último día. Se acepta.** El valor real del job sale
de `infra/env/dev.json:65` (`ventanaDiaCompleta: 6`) por `infra/80_create_job.ps1:180`, y
`85_update_job.ps1` no toca el entorno. Con la lectura «día principal», el 6 heredado pondría la
reserva en LUNES, un laborable, que es justo lo que el humano prohíbe, y además obligaría a un
cambio manual en Azure, fácil de olvidar. La lectura elegida es la más segura, aunque el nombre
sorprende un poco. Lo pagan la documentación (ver el cambio 2) y los tests, que siguen
cuadrando: `test_f025_settings.py:68` (defecto = DOMINGO) y `:249` (env ↔ `dev.json`). No pude
comprobar el entorno vivo del job: no se lanzó nada contra Azure.

**3 · Umbral de 7 días.** `DIAS_MAXIMOS_SIN_COMPLETA` solo se usa en `main.py:2031` (`>= 7` o
`None`), cubierto por `test_f025_cli.py:308,322`. `97_create_alert_ventana.ps1` sigue teniendo
sentido (única vía de aviso de un fin de semana perdido) y su comentario está al día.

**4 · 15 h > 50.400 s.** `test_f148_reanudacion.py:88` lee `dev.json`, fija 50.400 y exige
`techo < 15 h < 24 h`. `85_update_job.ps1` no menciona `replica`; que no aplica el techo lo dicen
`dev.json:34`, el informe y la `acceptance`.

**5 · Diccionario v78 y docs.** `stg.yaml`, `_meta.yaml`, `00_global.yaml` y `ARCHITECTURE.md`
bien; quedan los cambios 1 y 2. «Hasta 6 días» sigue siendo cierto (de sábado a sábado). Sin
restos de `25200`, `7 h` ni `8 h` fuera de la historia de `dev.json:34` y de las specs de
F-025/F-148, que son historia.

**6 · Tests.** Ocho mutaciones a mano en una copia del scratchpad contra
`test_f025_precedencia.py`. Mueren siete: sábado `<`→`<=` (1 fallo); domingo `<`→`<=` (4);
domingo sin el `-1 día` (4); laborables con `dias >= 7` → True (15); `vispera = SABADO` fijo (1);
`dia_semana`→`DOMINGO` fijo (1); `None`→False (7). **Sobrevive** `(dia_semana - 1) % 7` →
`(dia_semana - 1)`: solo afecta a `PG_VENTANA_DIA_COMPLETA=0`. Recomendado, no exigido: un caso
con `dia_semana=0`.

## Observaciones (no bloquean; para el humano)

- **O1 · La ventana en producción depende de una variable puesta a mano. Es anterior a F-163.**
  `dev.json:63` dice `ventanaActiva: "false"`, pero la ventana se encendió en Azure a mano
  (`specs/F-025-.../mediciones.md:363`). Si alguien recrea el job con `80_create_job.ps1`, la
  ventana se apaga, TODAS las noches pasan a ser completas y F-163 deja de servir. Conviene una
  feature aparte que lleve `true` a `dev.json`, y comprobar con una lectura
  (`az containerapp job show`) antes de dar F-163 por desplegada.
- **O2 · 14 h con `replicaRetryLimit` 1.** Si `replicaTimeout` fuera por réplica, el peor caso
  serían 28 h y el reintento se solaparía con la nocturna siguiente, y no hay cerrojo entre
  ejecuciones. El motivo `DeadlineExceeded` del 2026-11-15 apunta a un plazo por ejecución (14 h
  en total), y entonces no hay solape. Conviene confirmarlo al desplegar.
- **O3.** Un puntual con completa el sábado por la tarde, cuyo hito caiga pasada la medianoche,
  puede coincidir con la nocturna del domingo: es el problema de siempre, sin cerrojo.

## Checkpoints

- **C1** [x] Por la evidencia del implementer (`init.sh` EXIT 0 sobre `cc567f1`, 13.253 passed;
  después solo cambian `progress/` y `features.json`). No la reejecuté, por indicación del líder.
  Ejecuté `test_f025_precedencia/_settings/_build` y `test_f148_reanudacion`: **176 passed**.
  La pasada 2 correrá `ARNES_SIN_CACHE=1` entera.
- **C2** [x] Una sola feature activa (`in_review`), en su rama, con `current.md` al día.
- **C3** [x] Hexagonal: el dominio sigue puro (`timedelta` de la biblioteca estándar) y las
  cabeceras con la ruta se mantienen. Sin `print` ni secretos. Semántica Sigrid: no aplica.
  [ ] Documentación coherente: cambios 1 y 2.
- **C3 bis / C3 ter** N/A: no entra ningún documento de fuera ni se registra una conversación.
- **C3 quater** [x] Solo `datamart_seg_anual.md`, en un commit aparte (006b293, que consta en el
  informe del implementer) y sin push (`ahead 1`). [ ] Fidelidad al estado desplegado: cambio 3.
- **C4** [x] Cada `acceptance` tiene su test (tabla abajo). Los tests no tocan red ni BBDD. El
  paso MANUAL (despliegue y `--replica-timeout`) está listado en la ficha y en el informe.
- **C4 bis** [x] `rigor` declarado. [x] Fase RED con salida real (35 failed antes del código).
  [x] Cobertura 100 % (17/17). [x] «Evidencias» completas. Mutación N/A por nivel (informativa;
  la campaña va tras el APPROVED). RM1–RM7 N/A por nivel `estandar`. Capa e2e N/A: no existe
  `harness/servicios.json`.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] `sdd=false`: no hay `tasks.md`; commits T1–T3 con el prefijo `F-163 Tn`. Árbol
  limpio. `features.json` en `in_review`.

## Cobertura acceptance → test

| Criterio | Test |
|---|---|
| El sábado dispara | `test_f025_precedencia.py::test_f163_d1_el_sabado_toca` (+ `_aunque_la_ultima_fuera_ayer`, `_no_se_repite_el_mismo_dia`) |
| El domingo solo sin la del sábado | `test_f163_d1_el_domingo_toca_si_falta_la_del_sabado`, `_no_toca_si_la_del_sabado_quedo_registrada` (×3), `_no_repite_la_del_propio_domingo` |
| Laborables nunca, ni con 7+ días | `test_f163_entre_semana_nunca_toca_ni_con_la_completa_vencida` (5 días × 5 antigüedades) |
| Sin completa: esa noche | `test_f163_d2_sin_ninguna_completa_registrada_toca_cualquier_dia` (×7) |
| `check-ventana` avisa a los 7 días | `test_f025_cli.py::test_f025_r26_una_completa_vencida_se_denuncia`, `test_f163_el_tope_de_siete_dias_queda_solo_para_la_alerta` |
| 15 h > 50.400 en `dev.json` | `test_f148_reanudacion.py::test_f148_dominio_ventana_de_quince_horas_y_mayor_que_el_techo_del_job` |
| Diccionario/docs/azure-apps | revisión manual; incompleto (cambios 1–3) |
| Despliegue | MANUAL (humano), anotado en la ficha |

## Propuesta de automejora (no aplicada)

Que `reviewer.md` pida, cuando una feature cambia un calendario o una constante con nombre
propio, barrer también los **literales que el código escribe en datos publicados**
(`detalle`, `motivo`): el cambio 1 se escapa mirando solo el diff.
