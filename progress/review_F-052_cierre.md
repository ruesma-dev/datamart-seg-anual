<!-- progress/review_F-052_cierre.md -->
# F-052 · Review del CIERRE (pasada 3, incremental)

**Revisión incremental desde `cd18e09`** (pasada 3), rango `cd18e09..b194a5c`. Lo
aprobado en `review_F-052.md` y `review_F-052_fase2.md` queda dado por bueno. El
delta: los 7 commits del 2026-09-02 (`ec516bd`..`9ee8603`), el merge de `main`
`28bf449` y el papeleo `b194a5c`. `init.sh` y la suite, enteros.

## Veredicto: **APPROVED**

El criterio del cierre se cumple **de verdad**: `check-cobertura` sale con código 0
mirando **56 combinaciones reales**, no cero. Las 23 excepciones casan una a una
con lo que se mide hoy y ninguna tapa algo que no deba. Quedan decisiones para el
humano (abajo), pero ninguna invalida el verde.

**Rigor `critico`** (declarado). Mutación **N/A** por la decisión escrita del
humano del 2026-08-31 (T21), sustituida por las cuatro huellas ya juzgadas en la
fase 2. RM1-RM6 N/A: no hay campaña. Cobertura **N/A con motivo impreso**
(`F-052 no cambia líneas Python de producción frente a main`), comprobado en el
diff: YAML, JSON, Markdown y tests, ni una línea de `etl_sigrid/` ni de `main.py`.

## Lo que ejecuté yo

| Qué | Resultado |
|---|---|
| `bash harness/init.sh` | **exit 0** · 5.666 passed, 207 skipped, 760 s · tamaño OK · rama OK |
| `python main.py check-cobertura --timeout 900` (08:52-08:54 UTC) | **exit 0** · 23 excepciones · **56 miradas, 56 cubiertas** · invisibles: ninguna · huérfanas: ninguna |
| Fase RED, reproducida | el YAML anterior a `ec516bd` (10 entradas) contra la fixture: **44 invisibles, 19 con huérfanas, código 1**; el de HEAD: 0 y 0, código 0 |
| `pytest` de los dos ficheros de F-052 | 54 passed |
| Alerta en Azure (solo lectura) | `alert-caj-datamart-seg-dev-cobertura` habilitada; **se ha disparado** el 03-09, el 07-09 y el 20-09 (activa desde entonces) |
| Barrido de secretos del diff | contraseñas, tokens, GUID, IPs, correos, cadenas de conexión: **nada** |
| `git status` al terminar | limpio |

**El marcador `0 miradas` ya no puede dar verde**: `Veredicto.no_ha_mirado_nada`
(F-025, entra con el merge de `main`) convierte en KO la trampa que denunciaba el
aviso de `impl_F-052_cierre.md`. El verde de hoy no es ese.

## Las 23 excepciones contra la base de hoy (detalle obra a obra, solo lectura)

| Excepción | Qué tapa hoy | Juicio |
|---|---|---|
| `~OBRA PRUEBA` ambas | 9 obras, 21 comb. (ámb. 3/7/8/11) | exacto; **no casa con ninguna obra de `stg.obras`** |
| `~POSTVENTA` ambas | POSTV y POSTV2, ámb. 3 | exacto; ninguna obra real casa |
| `VAR` ambas | ámb. 3 y 7 | exacto (por código) |
| 0517, 0252 ambas | el ide perdido, invisible y huérfano | exacto |
| 0606 ambas | el ide perdido 1562946, ámb. 3/7/8/11 | exacto, pero ver obs. 2 |
| 0613 / 0618 `filas_huerfanas` | **150** (18+18+55+59) y **76** (38+21+17) | idéntico al 09-02; el tipo no tapa invisibilidad |
| 0578, 0585, 0670, 0687 `obra_invisible` ×8 | **solo ámb. 8 y 11**; en 3 y 7 publican (1.793/702, 17.185/18.933, 665/306, 4.760/3.062 filas) | acotadas como debían: el ámbito 3 sigue vigilado |
| 150414 / 150703 / 181001 ambas | **12** (8+4), **6** (3+3), **50** (34+16) | idéntico al 09-02 |
| 0565, 0630, 0686 `filas_huerfanas` | **nada** | muertas, ver obs. 1 |
| 0720 ambas | **nada** | muerta, ver obs. 1 |

Recuento: 22 obras invisibles distintas (las 20 del 09-02 más 0517 y 0252, ya
declaradas en `main`), 49 comb. invisibles, 48 con huérfanas, 56 en total.

**La 0599 ya no sale**, y lo he contrastado: en `mart.fact_seguimiento_mensual`
tiene **21.051 / 18.266 / 9.999 / 8.999** filas en los ámbitos 3/7/8/11, las mismas
cifras de R9 que midió la fase 2; en 3 y 7 coincide fila a fila con `stg.plan_mensual`.

## El merge `28bf449` y la renumeración F-055 → F-117

- **No se pierde nada de la rama.** `git diff 9ee8603 HEAD` sobre el YAML, los dos
  tests, `tasks.md` e `impl_F-052_cierre.md`: la única diferencia es `F-055` →
  `F-117` (8 `feature:` y un comentario en el YAML, comentarios en los tests). Lo
  que trae `main` a esos ficheros es el arreglo de `no_ha_mirado_nada`.
- **Las correcciones de `aad3412` a `current.md` no sobreviven, y es correcto**: el
  párrafo que corregían ya no existe en el `current.md` de `main` (la frase «ninguna
  de las 294» no aparece). La corrección vive en el YAML y en el informe de cierre.
- **`features.json`**: sin ids duplicados, una sola `in_progress` (F-052). F-117
  es la F-055 de la rama con id, rama y el `acceptance` de retirada renumerados;
  su descripción conserva el texto histórico con nota de renumeración delante.
  F-045 falta porque `main` la retiró (`fcf6871`), no por el merge. F-055 es la
  de `main` (ejes del proveedor).
- **`b194a5c`** solo toca `BACKLOG.md`, `features.json` (F-118, F-119, F-037 a
  prioridad 2) y `current.md`; `init.sh` en verde con él dentro.

## Checkpoints

- **C1** [x] `init.sh` exit 0; los ficheros del arnés existen.
- **C2** [x] una sola `in_progress`; rama `feature/F-052-partidas-huerfanas`;
  `current.md` abre con la sesión activa (ver obs. 6 sobre la sección vieja).
- **C3** [x] sin código de producción en el delta; primera línea con ruta en el
  YAML y los tests; sin prints ni secretos; ninguna dependencia nueva.
- **C3 bis** N/A: el delta no toca `docs/referencia/`.
- **C4** [x] R16 lo cubren `test_f052_cobertura.py` (mecanismo y trinquete) y
  `test_f052_cierre_excepciones.py` (contenido contra el veredicto real); leen el
  YAML del disco, sin red ni BBDD; sin dobles nuevos. Paso 6 bis: la regla se
  dispara (tabla de arriba); falta solo que el humano confirme el buzón (obs. 5).
- **C4 bis** [x] rigor declarado; fase RED con traza en el informe **y reproducida
  por mí**; cobertura N/A con motivo impreso y verificado; mutación N/A por la
  decisión escrita del humano (T21), con el sustituto juzgado en la fase 2;
  RM1-RM6 y «cero supervivientes» N/A por no haber campaña; «Evidencias» con los
  cuatro números (workers N/A: sin campaña).
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] T1-T30 en `[x]`, con T13-T15 en `7216aa6`; árbol limpio (las huellas
  y los `obras_*.csv` de la raíz los ignora `.gitignore`); `features.json` refleja
  `in_progress` hasta que el líder la cierre.

## Observaciones (no bloquean; las decide el humano o el líder al cerrar)

1. **Cuatro excepciones no tapan nada hoy.** 0565, 0630 y 0686: sus partidas en
   ciclo (279988, 279997, 310512, 375474) **no tienen ni una fila en
   `stg.plan_mensual`**, así que nunca han podido casar en este guardián (sus
   huérfanas son de `stg.presupuesto`, que el guardián no mira). **0720 PROMIRIS**
   ya publica (197 + 31 filas en 3 y 7, con fact): está en `ambas` sin ámbito, y
   **si mañana vuelve a desaparecer, el guardián callaría sobre una obra viva**.
   Propuesta: retirar la de 0720 (trinquete 23 → 22) y avisar a F-053 de que su
   caso ya no se reproduce; decidir si las tres del ciclo se quedan como
   documentación o se retiran.
2. **0606 `ambas` por código tapa también al ide ganador** (1581378, 27.776 filas
   en el ámbito 3): si ese dejara de publicar, no sonaría. `Excepcion` no puede
   acotar por `obra_id`; deuda para F-053 (campo `obra_id` opcional, o resolver el
   desempate).
3. **Los `obras_*.csv` (920 obras) siguen en la historia local**, en `16bf645`. No
   están en `origin` (su `feature/F-052-partidas-huerfanas` está en `c1c5930`) ni
   en `HEAD`. No son secretos según `CLAUDE.md`, y `9ee8603` lo anota, pero **el
   merge a `main` y el push los harán permanentes**: purgarlos es barato ahora y
   carísimo después. Decisión del humano antes del push.
4. **Números descuadrados en el papeleo**: `tests/test_f052_cobertura.py:78` dice
   que el trinquete «vuelve a bajar a 13» tras F-117; son **15** (23 − 8), como
   dicen el informe y el `acceptance` de F-117. `current.md:35` dice «sus 21
   excepciones»; son 23. La fixture de `test_f052_cierre_excepciones.py` lleva
   `obra_id` que ya no son los de la base (0606 perdido 1581377 → hoy 1562946;
   VAR 870000 «VARIOS» → hoy 683806 «OBRAS VARIAS»); inocuo porque casa por código.
5. **Paso 6 bis**: anotar en `current.md` que la regla se disparó el 03, 07 y 20-09
   y dejar como MANUAL (humano) confirmar que el correo llegó al buzón.
6. **`current.md`** conserva la sección «F-052 · SIGUE BLOQUEADA» (línea ~1587) y
   las menciones de las líneas ~1357 y ~1397: al cerrar, al historial.
7. **El repositorio verde no es producción.** La nocturna corre con las 10
   excepciones de `main`: por eso la alerta sigue activa desde el 20-09. Las 23
   solo llegan con el merge a `main` **y una imagen nueva del job**.

## Automejora (propuesta, no aplicada)

`check-cobertura` debería listar también las **excepciones que no han tapado
nada** en la pasada: hoy son cuatro y solo se ven cruzando a mano, como aquí. Una
excepción muerta es una alarma apagada sin motivo, y el trinquete no la detecta.
