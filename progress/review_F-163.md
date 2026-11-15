# progress/review_F-163.md
Revisión incremental desde 8fdfece (pasada 2) · delta `bfcd29a..f75357d`; azure-apps `006b293..0511029`

## Veredicto: APPROVED

Los tres cambios requeridos de la pasada 1 están resueltos, y el test con `dia_semana=0` mata
la mutación que sobrevivía. No se ha colado nada fuera del alcance de los cambios. La puerta
completa sale en verde: la ejecuté yo, sin caché.

**Pasada 1 (resumen):** CHANGES_REQUESTED en 8fdfece. La lógica, los tests y la desviación de
`PG_VENTANA_DIA_COMPLETA` eran correctos. Se rechazó por el `detalle` publicado «reconstruccion
completa semanal (domingo)», por los restos de «domingo» en comentarios, en `settings.py` y en
`dev.json`, y porque faltaba la marca SIN DESPLEGAR en `azure-apps`. El detalle completo está en
el historial de git de este fichero (f75357d).

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura de lo cambiado y la sección
«Evidencias». La mutación es informativa: la campaña va tras este APPROVED.

## Puerta (C1)

`ARNES_SIN_CACHE=1 bash harness/init.sh` sobre `f75357d`: **EXIT 0, «ENTORNO LISTO»**.
- **Tests:** 13.255 passed, 2.526 skipped, en 5.157 s.
- **`PUERTA COBERTURA`:** 100,0 % (18/18).
- **`PUERTA TAMAÑO`:** impl 168/220, review 140/140.
- **`CARRIL` y `CAPA E2E`:** N/A.
- **ruff:** 436 avisos, que son deuda previa y no bloquea. En los cinco ficheros tocados, ruff da
  «All checks passed».
- **Árbol de trabajo:** limpio después de la puerta.

## Cambios de la pasada 1, uno por uno

1. **`detalle` publicado (Media): RESUELTO.**
   - `etl_sigrid/domain/ventana.py:480` devuelve ahora «reconstruccion completa: entra todo».
   - Lo fija `test_f025_precedencia.py::test_f163_el_detalle_de_la_completa_no_nombra_ningun_dia`,
     que exige el texto exacto, sin ningún `NOMBRES_DIA` y sin «semanal».
   - Lo comprobé con una mutación en una copia del scratchpad: volver al texto viejo da 1 fallo.
   - No queda ningún «semanal (domingo)» en el código, el SQL ni el diccionario.
2. **Restos de «domingo» (Baja): RESUELTO.**
   - `ventana.py`: corregidos los pasajes de las líneas :49, :67 y :418.
   - `postgres_client.py`: corregidos los de :372, :442 y :524.
   - `test_f025_cli.py`: corregido el docstring de :309.
   - El grep posterior solo deja menciones legítimas: el domingo como reserva, la constante
     `DOMINGO` y la historia de DA-4.
   - `config/settings.py:504-507` dice ahora «6 = el sábado hace la completa y el domingo es la
     reserva» y añade que el job no fija la variable.
   - `infra/env/dev.json:62` explica qué significa `ventanaDiaCompleta`.
3. **`azure-apps` (Baja): RESUELTO EN EL TEXTO.** El commit 0511029 añade la marca «SIN
   DESPLEGAR» en los cuatro pasajes de F-163 y dice qué rige hasta el despliegue: domingo con la
   red de 7 días, 8 h y 7 h. Solo toca `datamart_seg_anual.md` y va en un commit aparte. **Pero
   ver H1.**
4. **Recomendado, `dia_semana=0`: HECHO.** El test
   `test_f163_el_lunes_como_ultimo_dia_da_la_vispera_en_domingo` mata la mutación `(dia_semana
   - 1) % 7` → `(dia_semana - 1)`, que sobrevivía en la pasada 1: lo reproduje y da 1 fallo. La
   mutación del domingo sin el `-1 día` sigue muriendo, con 4 fallos.

## Verdad de los textos sobre `PG_VENTANA_DIA_COMPLETA`

El job vivo no lleva la variable y rige el defecto 6 (lectura del líder en Azure, solo
lectura). Lo dicen ya `ventana.py:624-628`, `settings.py:505`, `dev.json:62`, `current.md:20` e
`impl_F-163.md` («Ciclo 1»); el «valor ya desplegado (6)» de la pasada 1 ha desaparecido.
`ventana.py:624` («domingo por defecto y en `dev.json`») sigue siendo cierto: `dev.json:65` vale
6 y `80_create_job.ps1:180` lo inyectaría si se recreara el job, sin cambiar la conducta.

## Hallazgos de esta pasada

- **H1 · [Atención del líder, no bloquea el código] `azure-apps` YA ESTÁ EN `origin/main`.** El
  reflog dice `refs/remotes/origin/main@{2026-11-15 16:24:51 +0100}: update by push` y apunta a
  0511029, que incluye 006b293. `git status -sb` ya no sale `ahead`. En cambio, el informe del
  implementer (`impl_F-163.md:62` y `:154`) y tu mensaje dicen «sin push». No puedo saber
  quién lo empujó: el commit es de las 16:03 y el push de las 16:24. Si lo hizo el humano, solo
  hay que corregir la línea del informe. Si lo hizo un agente, se rompe la regla dura «los
  agentes nunca hacen push», y hay que contárselo al humano. Lo que se subió es veraz (lleva la
  marca SIN DESPLEGAR), así que no hay contenido que retirar.
- **H2 · [Cosmético] `tests/test_f025_cli.py:310`** tiene 111 caracteres, más que los 100 de
  `pyproject.toml`. ruff no lo marca porque E501 no está activo para docstrings. No hace falta
  tocarlo.

## Observaciones que siguen en pie (de la pasada 1, para el humano)

- **O1 · Ventana encendida solo a mano.** `dev.json:63` dice `ventanaActiva: "false"`, pero el
  job vivo tiene `PG_VENTANA_ACTIVA=true`, puesta a mano. Si alguien recrea el job con
  `80_create_job.ps1`, la ventana se apaga, todas las noches vuelven a ser completas y F-163 deja
  de servir. Ya lo anota el informe del ciclo 1. Propongo una feature aparte.
- **O2 · 14 h con `replicaRetryLimit` 1.** Hay que confirmar al desplegar que el plazo es por
  ejecución (`DeadlineExceeded`) y no por réplica. Si fuera por réplica, el peor caso serían 28 h
  y se solaparía con la nocturna siguiente, porque no hay cerrojo.
- **O3 · Job puntual con completa.** Si un job puntual del sábado por la tarde hace la completa y
  su hito cae pasada la medianoche, puede coincidir con la decisión de la nocturna del domingo. Es
  el problema de siempre: no hay cerrojo.

## Checkpoints (pasada 2)

- **C1** [x] Puerta completa sin caché, ejecutada por mí: EXIT 0.
- **C2** [x] Una sola feature activa (`in_review`), en su rama; `current.md` y la ficha al día.
- **C3** [x] Arquitectura hexagonal intacta: el delta son textos y tests. Las cabeceras con la
  ruta se mantienen, sin `print` ni secretos. Documentación coherente: los cambios 1 y 2 están
  resueltos.
- **C3 bis / C3 ter** N/A: no entra ningún documento de fuera ni se registra una conversación.
- **C3 quater** [x] Solo `datamart_seg_anual.md`, en commits aparte (006b293 y 0511029, que
  constan en el informe), y fiel al estado desplegado. [!] El push ya está hecho: ver H1. Si lo
  hizo el humano, este punto se cumple.
- **C4** [x] Cada criterio de `acceptance` tiene su test (tabla abajo). Los tests no tocan red ni
  BBDD. El paso MANUAL de despliegue está listado.
- **C4 bis**
  - [x] Fase RED del ciclo 1 con salida real: el `AssertionError` del `detalle`, y el
    `assert False is True` del `% 7`.
  - [x] Cobertura 18/18.
  - [x] Sección «Evidencias» presente.
  - Mutación: N/A por nivel (informativa). La campaña va tras el APPROVED.
  - RM1–RM7: N/A, el nivel es `estandar`.
  - Capa e2e: N/A, no existe `harness/servicios.json`.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] `sdd=false`. Los commits del ciclo llevan el prefijo `F-163 ciclo 1`. El árbol está
  limpio.

## Cobertura: criterio de acceptance → test

| Criterio | Test |
|---|---|
| El sábado dispara | `test_f025_precedencia.py::test_f163_d1_el_sabado_toca` (+ `_aunque_la_ultima_fuera_ayer`, `_no_se_repite_el_mismo_dia`) |
| El domingo, solo si falta la del sábado | `test_f163_d1_el_domingo_toca_si_falta_la_del_sabado`, `_no_toca_si_la_del_sabado_quedo_registrada` (×3), `_no_repite_la_del_propio_domingo` |
| Los laborables nunca, ni con 7+ días | `test_f163_entre_semana_nunca_toca_ni_con_la_completa_vencida` (5 días × 5 antigüedades) |
| Sin completa registrada: esa misma noche | `test_f163_d2_sin_ninguna_completa_registrada_toca_cualquier_dia` (×7) |
| Ajuste configurable (incluido el lunes) | `test_f163_el_ultimo_dia_de_la_ventana_es_configurable`, `test_f163_el_lunes_como_ultimo_dia_da_la_vispera_en_domingo` |
| `check-ventana` avisa a los 7 días | `test_f025_cli.py::test_f025_r26_una_completa_vencida_se_denuncia`, `test_f163_el_tope_de_siete_dias_queda_solo_para_la_alerta` |
| 15 h > 50.400 de `dev.json` | `test_f148_reanudacion.py::test_f148_dominio_ventana_de_quince_horas_y_mayor_que_el_techo_del_job` |
| Diccionario, docs y `azure-apps` | Revisión manual: al día, con la marca SIN DESPLEGAR y el `detalle` fijado por un test |
| Despliegue | MANUAL (humano): imagen nueva y `az containerapp job update --replica-timeout 50400` |

## Propuesta de automejora (no aplicada, se mantiene de la pasada 1)

Propongo que `reviewer.md` pida dos cosas:

1. Cuando una feature cambia un calendario o una constante con nombre propio, barrer también
   los literales que el código escribe en datos publicados (`detalle`, `motivo`).
2. En la pasada de un ciclo que toca el repositorio del ecosistema, comprobar con
   `git reflog show origin/<rama>` si lo que el informe dice «sin push» sigue sin subir.
