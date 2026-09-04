<!-- progress/review_F-025.md -->
Revisión incremental desde `9ce89c4` (pasada 4), tres commits. Las pasadas 1
(completa), 2 y 3 viven en `a34ed9b`, `fbfd0fe` y `9ce89c4`.

# F-025 · Review · Las obras cerradas no se reconstruyen cada noche

## Veredicto sobre lo entregable: **APROBADO**

**El código y el papeleo de F-025 están en condiciones de que el humano ejecute
la fase manual con confianza.** Los tres cambios de la pasada 3 están cerrados y
dos de ellos mejor de lo que pedí. No queda nada que deba tocar el implementer.
Quedan **dos observaciones que NO bloquean** —una de ellas, una frase de las
MANUAL que falla si se ejecuta tal cual, y conviene arreglarla antes del paso 4—.

**Esto no es cerrar la feature.** **C5 sigue abierto**: 12 de 41 tareas son la
fase 7 (T1, T2b, T27-T35), no se han ejecutado y su precondición —una
`stg.plan_mensual` completa— sigue sin cumplirse. Sobre eso no dictamino. La
feature no se marca `done` hasta que esa fase corra y sus huellas den cero
diferencias; lo que aquí queda aprobado es **lo entregable**.

## Los tres cambios de la pasada 3

**1 · Las cifras muertas del código `[x]`, y eran 11.** Barrido propio del árbol
entero, todas las extensiones: **no queda ninguna viva**. Sobreviven solo las que
**nombran la vieja para enterrarla** —`main.py:1339`, `ventana.py:62`,
`decisiones.md`, `mediciones.md`, `business_rules.yaml`, `maestro.yaml`—, que es
lo correcto. Y lo que sí sigue diciendo «40» —`stg.yaml:285`,
`build_stg_step.py:92`, `ventana.py:52`, `00_meta.sql:134`, T1 y T31b— es **el 40
bueno, el de obras vivas**, no el de congeladas-con-actividad: la trampa de este
barrido es justo esa, que la cifra muerta se esconde detrás de una viva idéntica.
El `--help` de `ventana-plan` ya dice «de las 48… 8 quedan congeladas» y añade la
corrección con su fecha.

**2 · Las `PG_VENTANA_*` en `infra/` `[x]`, y con red.** `80_create_job.ps1`
inyecta las cuatro **desde `$CFG`**, no escritas a mano; `dev.json` las declara
con su `$aviso_` —que además deja escrito el porqué: el modo de fallo de F-052
aplicado a la configuración— y con los booleanos **como cadena**, igual que
`pgAutoCreateDb`, que es lo que pydantic espera. **Nacen apagadas.** Y trae lo
que no había pedido y es lo que lo sostiene: **tres tests nuevos** que cierran el
circuito nombre→valor→inyección, comprueban que `ventanaActiva` y
`ventanaRescate` están en `false` **en todos los entornos**, y ponen la red
anti-divergencia sobre `ventanaMeses`/`ventanaDiaCompleta` —dejando fuera los dos
interruptores a propósito, porque el día que se encienda la ventana `dev.json`
dirá `true` y el código seguirá diciendo `False`—. Reutilizan los helpers de
`test_f003_infra` en vez de copiarlos. Los tres pasan.

**3 · La cobertura `[x]`:** `features.json` ya dice **91,7 %**.

## La campaña de mutación sigue siendo válida (RM1, comprobado)

`ventana.py` **cambió** después del SHA que midió la campaña (`073af30`): 779 →
784 líneas. Por RM1 eso obliga a mirar si hay que repetirla. **No hay que
repetirla, y no lo doy por supuesto:** el diff es solo docstring, y he comparado
el juego de mutantes de `073af30` con el de HEAD por **operador y texto
original→mutado**, ignorando el número de línea: **83 mutantes y la misma huella
(`f63d521836650b62`) en los dos**. Byte a byte, la campaña juzgó exactamente
estos 83. El resto del alcance sigue **`N/A` por la exención escrita del humano
del 2026-09-04**.

## Observaciones que NO bloquean

**1 · La instrucción de encendido falla si se ejecuta tal cual.** Las MANUAL
dicen ahora «cambiar `"ventanaActiva": "true"` en `dev.json` y volver a lanzar
`80_create_job.ps1`». Pero `80_create_job.ps1:85-87` **lanza excepción si el job
ya existe** —«el job ya existe. Para cambiarle la imagen usa
`85_update_job.ps1`»—, que es el caso de producción. El párrafo siguiente sí da
la salida buena (fijarla a mano sobre el job), así que el humano no se queda
parado, pero la que va a probar primero es la que falla. **Arreglo: una frase.**

Y respondiendo a lo que se me preguntó: **sí, `85_update_job.ps1` —o un `86`
nuevo— haría falta** si se quiere que encender la ventana sea un cambio dirigido
por el repositorio. Hoy el camino versionado solo funciona **al crear el job de
cero**; sobre un job vivo, el único que funciona es el `az … --set-env-vars` a
mano. Eso no anula lo ganado: el valor ya está versionado y una recreación futura
lo lleva, que era el agujero de la pasada 3.

**2 · Queda un «40» muerto, en la spec.** `design.md:205`, en la lista de
riesgos: «**40 obras vivas congeladas** (R3)». R3 dice **8 de las 48**, y
«obras vivas congeladas» es además una contradicción. Es exactamente la trampa
del punto 1: el 40 muerto escondido detrás del 40 bueno.

## Checkpoints

- **C1** `[x]` — `bash harness/init.sh` **EN VERDE**: **3.308** pasados (los 3
  nuevos), 134 saltados en 242 s; `COBERTURA [OK] 91,7 % (578/630, umbral 80 %,
  critico)`; `TAMAÑO [OK]`; rama correcta.
- **C2** `[x]` — una `in_progress`, `current.md` al día con las MANUAL.
- **C3** `[x]` — el delta toca `.py`, `.sql`, `.ps1` y `.json`, y lo revisé: son
  **docstrings y comentarios** salvo el bloque `--env-vars` y los tres tests.
  Dominio sin infraestructura, ruta en la primera línea, sin secretos ni prints.
  **Ni una línea de lógica cambia**, así que lo aprobado en la pasada 1 sigue.
- **C3 bis** y **C4 ter** `N/A` justificados: no toca `docs/referencia/` ni
  existe `harness/rutas_sensibles.json`.
- **C4** `[x]` — cerrado lo que lo tenía en `[ ]`: las 11 referencias al día.
  Trazabilidad requisito→test intacta y las MANUAL con su comando literal.
- **C4 bis** `[x]` — RED `[x]`, cobertura `[x]`, RM1 `[x]` **revalidada arriba**,
  RM2-RM4 `[x]`, RM5/RM6 `N/A`, y la mutación fuera de `ventana.py` `N/A` por
  **exención escrita del humano** (`features.json`, `decisiones.md` §DA-6, T26).
- **C5** `[ ]` — **29 de 41**. Las 12 que faltan son la fase manual, y ninguna
  es del implementer.

## Lo que falta para cerrar (no dictamino sobre ello)

El orden acordado, con **el paso 0 de la pasada 2**: (0) completar
`stg.plan_mensual` de día y **con la ventana apagada**, hasta `check-coherencia`
y `status-stg` en verde; (1) **T27**, las cinco huellas del antes sobre ese
estado ya coherente; (2) **T1 y T2b** —si T1 baja del 40 %, PARAR—; (3) **T35**,
la alerta, que sin ella el guardián es mudo (DA-5); (4) **entonces**
`PG_VENTANA_ACTIVA`, **T28/T29** y **T30/T31/T31b** con tolerancia cero, donde
una sola diferencia PARA la feature; (5) **T32-T34**: los `check-*`, el bloat
contra T2 y los créditos de CPU (R24, R29).

## Automejora propuesta (no aplicada)

Las tres de las pasadas anteriores siguen en pie —RM7 · el alcance de la campaña
es el de la feature; los timeouts no son muertos; y el barrido de una cifra
corregida va sobre el árbol entero—. Esta pasada añade el matiz que las hace
útiles: **cuando la cifra retirada y la vigente son el mismo número con distinto
significado** —aquí, «40 vivas» frente a «40 congeladas con actividad»— el grep
no basta y hay que leer cada acierto. Se coló en `design.md` después de tres
barridos. Va a `CHECKPOINTS.md`, C4.
