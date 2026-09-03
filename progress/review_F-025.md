<!-- progress/review_F-025.md -->
Revisión incremental desde `fbfd0fe` (pasada 3), tres commits. Las pasadas 1
(completa) y 2 viven en los commits `a34ed9b` y `fbfd0fe`.

# F-025 · Review · Las obras cerradas no se reconstruyen cada noche

## Veredicto: **CHANGES_REQUESTED**

**Los tres cambios de la pasada 2 están cerrados y bien.** Lo impiden dos cosas
nuevas y **la fase 7**, que sigue sin ejecutar (C5, y sobre ella no dictamino).
Las nuevas: **la corrección del censo no llegó al código** —ocho sitios en `.py`,
`.sql` y tests siguen afirmando las dos cifras que la spec declara muertas,
incluido el `--help` que el humano leerá en el paso 5— y **el hueco de `infra/`**,
que juzgo cambio requerido. Ninguna toca la lógica: son registro y despliegue.

**El delta no toca ni una línea de código** (`git diff --name-only fbfd0fe..HEAD`
no da ningún `.py` ni `.sql`), así que lo verificado en las pasadas 1 y 2 sigue
en pie: borrado derivado, `TRUNCATE` retirado, hexagonal, trazabilidad.

## Los tres cambios de la pasada 2

**1 · DA-6 EXENTA: `N/A` justificado.** Está por escrito y en los tres sitios
—`harness/features.json`, `decisiones.md` §DA-6 y `tasks.md` T26—, con fecha
(2026-09-04), con la disyuntiva que planteé y **sin suavizar**: dice literalmente
que `build_stg_step.py` (34 mutantes, el borrado derivado), `main.py` (37),
`postgres_client.py` (31), `ventana_sql.py` (15) y `cobertura.py` (6) **no han
pasado por mutación**, y qué los cubre en su lugar. Es lo que `rigor.json` admite
en `critico` («salvo justificación escrita aceptada por el humano») y el
precedente de F-042 y F-052. **Lo declaro `N/A` citando esa decisión.**

**2 · «Evidencias» `[x]`.** Publica ya los números de la campaña que vale: 83/83,
**0 supervivientes**, **4 timeouts** —marcados como *sin veredicto* y remitidos
al cierre que hice por RM4—, 7.720 s, base 467-473 s, 4 workers, y el 38 % del
alcance dicho a las claras.

**3 · El censo en la documentación `[x]`.** `business_rules.yaml` quedó limpio y
explica de dónde salían las viejas y **por qué el «217 sin ninguna fase» mezclaba
universos**; R2/R3, `mediciones.md`, `design.md`, `maestro.yaml` y
`ARCHITECTURE.md` cuadran, y **T36 está marcado**. **La explicación retirada,
comprobada:** las ocho obras aparecen con su última actividad —2026-07, 2026-04,
2026-01 ×2, 2025-11, 2025-10 ×2, 2025-09— en `decisiones.md`, `maestro.yaml` y
`mediciones.md`: **ninguna en 2025-12**, así que el «36 de 39 son el cierre
anual» no reproduce y el registro lo dice. En la documentación **no queda
rastro** de las dos versiones erróneas salvo donde se las nombra para
enterrarlas. En el código sí queda.

## Hallazgo 1: la corrección del censo se paró en `.md` y `.yaml`

Barrido del árbol entero —mi grep de la pasada 2 solo miró `.md` y `.yaml`: **mío
es el fallo**—. Ocho sitios afirman como vigentes el **40** inflado, el **80**
viejo y la explicación **«39 CERRADAS, 36 por el cierre de 2025-12»**:

| Fichero:línea | Qué dice todavía |
|---|---|
| `etl_sigrid/domain/ventana.py:57` | «congela **40 obras** —**39 CERRADAS, 36 de ellas por el cierre anual de 2025-12**, y 1 por código». **Las dos versiones retiradas, en el módulo que implementa el criterio** |
| `etl_sigrid/domain/ventana.py:11` | «solo **80** habían tenido actividad» (son **48**) |
| `main.py:1333` | docstring de `ventana-plan` = **el `--help` que leerá el humano en el paso 5 de las MANUAL**: «**40** obras CON actividad… 39 CERRADAS y 1 de seis digitos» |
| `sql/ddl/00_meta.sql:175` | «congela **40** obras con actividad reciente», en el DDL de la vista que leen el MCP y Power BI |
| `config/settings.py:160` y `:192` | **80** y **40**; el segundo, en el docstring de `ventana_rescate`, el interruptor que existe por esa cifra |
| `tests/test_f025_settings.py:60`, `tests/test_f025_ventana.py:343` | **40** en los docstrings |

No es cosmético: **R3 dice 8 y el código dice 40**, y donde más se va a leer —el
`--help` del comando de la verificación manual— repite la explicación que el
humano acaba de descartar. Son comentarios: no altera comportamiento, así que ni
la campaña ni las huellas se ven afectadas.

## Hallazgo 2: el hueco de `infra/`. **Sí es cambio requerido**

Comprobado: `80_create_job.ps1` enumera **dieciséis** `--env-vars` y **ninguna
`PG_VENTANA_*`**; `85_update_job.ps1` solo cambia la imagen y dice que no toca el
entorno. El default de `settings.py` es `False`, así que hoy el job es **seguro**:
sin la variable la ventana está apagada. Documentarlo en las MANUAL era
necesario. **No es suficiente, por tres razones:**

1. **La vía documentada deja producción fuera del repositorio.** `az containerapp
   job update --set-env-vars` fija la variable *sobre el job*; el día que alguien
   recree el job con `80_create_job.ps1` —el fichero que es la verdad de cómo se
   construye— la variable **desaparece sin ruido**, la ventana se apaga y la
   nocturna vuelve a reconstruir las 920 y a vaciar la hucha de créditos: **el
   modo de fallo de F-052 aplicado a la configuración**, algo que se degrada sin
   que nadie se entere porque «apagada» es el comportamiento viejo.
2. **«No se toca `infra/`» no es aquí el principio que parece:** esta feature
   **ya tocó `infra/`** —`97_create_alert_ventana.ps1`, `README.md` y **el propio
   `infra/env/dev.json`**, +201 líneas—. Faltan justo en el fichero que sí se
   modificó.
3. **El repositorio ya tiene la convención y la red:** el valor de despliegue vive
   en `dev.json` y un test impide que diverja del código. Aquí no se aplicó.

**Coste**: cuatro claves en `infra/env/dev.json` y cuatro líneas en el bloque
`--env-vars`, desplegando **`PG_VENTANA_ACTIVA=false`**. No enciende nada: hace
que encenderla sea cambiar un valor versionado en vez de un comando suelto.

## Checkpoints

- **C1** `[x]` — `bash harness/init.sh` **EN VERDE**: 3.305 pasados, 134 saltados
  en 481 s; `COBERTURA [OK] 91,7 % (578/630, umbral 80 %, critico)`; `TAMAÑO
  [OK]`; rama correcta.
- **C2** `[x]` — una `in_progress`, `current.md` al día. **C3** `[x]`; **C3 bis**
  y **C4 ter** `N/A` justificados: sin código en el delta.
- **C4** `[ ]` — la trazabilidad requisito→test y las MANUAL con su comando
  siguen bien, pero **el código contradice R3**: ocho sitios dicen 40 y 80 donde
  el requisito dice 8 y 48 (§Hallazgo 1).
- **C4 bis** `[x]` — RED `[x]`, cobertura `[x]`, RM1-RM4 `[x]` (RM4 lo cerré yo
  en la pasada 2: los 4 timeouts MUEREN), RM5/RM6 `N/A` justificados, y **la
  mutación fuera de `ventana.py` `N/A` por EXENCIÓN ESCRITA DEL HUMANO del
  2026-09-04** (`features.json`, `decisiones.md` §DA-6, `tasks.md` T26).
- **C5** `[ ]` — `tasks.md`: 29 de 41. Lo que falta es la fase manual: T1, T2b y
  T27-T35.

## Cambios requeridos

1. **Poner al día las ocho referencias del código** (§Hallazgo 1). Por daño:
   `main.py:1333` (lo lee el humano al verificar), `ventana.py:57` y `:11` (el
   módulo del criterio), `00_meta.sql:175`, `settings.py:160` y `:192`, y los dos
   docstrings de tests. La buena es la de `decisiones.md` §DA-1: **8 congeladas
   con actividad de 48, y ninguna en 2025-12**.
2. **Declarar las `PG_VENTANA_*` en `infra/`** (§Hallazgo 2): las cuatro claves
   en `infra/env/dev.json` y su bloque en `80_create_job.ps1`, con
   `PG_VENTANA_ACTIVA=false`.
3. Menor: `features.json` dice **91,5 %** de cobertura donde son **91,7 %**.

## Pendiente de la fase manual (no dictamino sobre ello)

El orden acordado, con **el paso 0 de la pasada 2, que quedó aceptado**: (0)
completar `stg.plan_mensual` de día y **con la ventana apagada**, hasta
`check-coherencia` y `status-stg` en verde; (1) **T27**, las cinco huellas del
antes sobre ese estado ya coherente; (2) **T1 y T2b** —si T1 baja del 40 %,
PARAR—; (3) **T35**, la alerta, que sin ella el guardián es mudo (DA-5); (4)
**entonces** `PG_VENTANA_ACTIVA=true`, **T29**, y **T30/T31/T31b** con tolerancia
cero, donde una sola diferencia PARA la feature; (5) **T32-T34**: los `check-*`,
el bloat contra T2 y los créditos de CPU (R24, R29).

## Automejora propuesta (no aplicada)

Además de las dos de la pasada 2 (RM7 · el alcance de la campaña es el de la
feature; y los timeouts no son muertos), una tercera que esta pasada demuestra:
**cuando se corrige una cifra publicada, el barrido va sobre el árbol entero, no
sobre `.md` y `.yaml`.** Una cifra retirada sobrevive donde más se lee —un
`--help`, un comentario de DDL, el docstring del módulo que implementa la regla—
y ahí ningún test la ve. Va a `CHECKPOINTS.md`, C4.
