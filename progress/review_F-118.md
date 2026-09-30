<!-- progress/review_F-118.md -->
Revisión completa (pasada 1), alcance `0bca856..f2d7877` (HEAD f2d78770b3480d2ac058fc9966b3d463829c55a7)

# F-118 · Review · pasada 1

- **Veredicto: APPROVED.** Hay una corrección OBLIGATORIA antes de T27 (O1). Es documental, no de código.
- **Nivel de rigor:** `critico`, declarado en `features.json`. Exige fase RED, cobertura, cero supervivientes y MANUAL con comando.
- **Mutación exenta** por F-051 D7, heredada: la decisión del humano del 2026-08-29 para F-042, repetida en F-051 y en la PARADA 1 de F-118 (`progress/spec_F-118.md`). La sustituyen las huellas antes y después (T26-T29) y el invariante R21-R23.
- **`bash harness/init.sh`:** exit 0 en esta pasada.
  - 6.149 passed y 219 skipped, en 30 min 43 s.
  - PUERTA COBERTURA OK: 97,9 % (237/242, umbral 80 %).
  - PUERTA TAMAÑO OK. Ruff: 234 avisos previos, no bloquean.
  - Árbol limpio.

## Hallazgos, por gravedad

**O1 · Media (documental; bloquea T27, no el código).** El esperado de septiembre de la 0709 ha caducado.
- `current.md` (T27) y R35 esperan «0709 venta 2026-09 = **0,00**»: es la sonda del build del 29-09.
- El `stg` de hoy (`_built_at` 2026-09-30 01:28) trae la f13 con datos: septiembre **273.204,78**.
- Mi reproducción de la serie densa, en solo lectura:
  - jul 396.768,08 · **ago 377.492,30**, con 1 deshacer de +58.000 · sep 273.204,78;
  - la 417031, −58.000 / +58.000 / 0.
- Agosto y la 417031 cuadran; septiembre no será 0.
- Arreglo: cambiar el esperado a «= `cierre` del mismo build» y anotar la deriva del dato en R35 y en design §9. Es lo mismo que la decisión 12 del informe hizo con la 0371 y la 0606.

**O2 · Baja.** Dos comentarios que contradicen D6 en un fichero tocado por F-118.
- `sql/stg/01_ddl.sql:92`: «`importe_oficial` … usado por cierre venta».
- `sql/stg/01_ddl.sql:144-145`: «Lo usa el schema cierre para que el FINAL master cuadre».
- Desde F-118 el final del cierre usa `importe`. `06_presupuesto.sql` se deja por el hash de F-073 (documentado).

**O3 · Baja.** Posible dependencia fuera del repositorio que no pude comprobar.
- `sql/cierre/00_setup.sql:113` hace `DROP FUNCTION … cierre.fn_mes_de_fase(DATE, TEXT) CASCADE`.
- En el repositorio solo la usaban las vistas de `04_views_detalle.sql`, que se recrean en el mismo build.
- En la base no pude verlo: el MCP veta `pg_catalog`.
- Propuesta para T29: consultar `pg_depend` antes de desplegar, para confirmar que CASCADE no borra vistas fuera de `cierre/`.

**O4 · Baja.** Posible falso positivo en `check-mes-fase`.
- `mes_fase_sql.sql_marcas` decide si un deshacer «mueve» con valores ya redondeados a 2 decimales.
- `reales_final` (`08_plan_mensual.sql:641-643`) lo publica con los valores sin redondear.
- Un deshacer de céntimos fraccionarios saldría «sin movimiento» y el comando terminaría con código 1. Si aparece en T29, es la herramienta, no el dato.

**O5 · Informativa.** `stg.yaml:345` (relación `plan_mensual → presupuesto`) conserva «señal de estorno».
- No incumple R47: ese texto no se ha tocado, y ninguna línea añadida del diccionario, del SQL ni de `ARCHITECTURE.md` dice «estorno» (grep sobre el diff).
- Con la serie densa, la frase ya no es cierta.

**O6 · Informativa.** `mes_fase_sql.py:24` importa `_filtro_de_obras`, que es privada de `cierres_sql`.

**O7 · Informativa, para el aviso a Juan (T28).**
- La 0371 f31 «DICIEMBRE-18» (fechas 2015-08 a 2018-12) pasa de 2015-08 a **2018-12** con el parser nuevo (F-051 R4).
- Eso son unos 40 meses de relleno para unas 890 partidas. Es la regla aprobada, pero conviene listarla.

## Contraste en solo lectura (MCP, solo SELECT)

- **0709 venta.** La serie densa, reproducida con el mes del texto, da ago 377.492,30, igual que `cierre`; hoy `stg` publica 319.492,30. La partida 417031 va −58.000 / +58.000 / 0. El acumulado final es igual a la suma de los movimientos (R21).
- **0371 coste.** f29 («Mayo 2015») menos f27: 4.293.905,89 − 4.735.135,20 = **−441.229,31**. Es igual a la suma de conceptos de `cierre` en 2015-05 (−102,92 − 477,13 − 440.649,26). R36 OK.
- **0702 ago-26 (v19).**
  - Venta sin coeficientes 9.658.390,84; con coeficientes 12.144.681,17 (el `final_importe` de hoy).
  - Coste 10.449.109,30; beneficio **−790.718,46**. R40 OK.
- **0247 venta.** La f9 no tiene filas de venta, así que la f10 resta a la f8 (R34). Como la f10 está entera a 0, el movimiento es −1.163.036,07.
- **Sin escrituras.** `raw` y `pg_catalog` están fuera del alcance del MCP.

## El foco pedido

- **Serie densa** (`stg/08_plan_mensual.sql:352-644`), leída CTE a CTE.
  - Rejilla de meses de cierre vigente y de relleno por (obra, ámbito), desde el alta. Cierre sin fila = 0 (R29-R30); relleno = arrastre con `grupo_cierre` (R33); movimiento = `LAG` por `anio_mes`, sin `CASE` (R9).
  - Lo no publicado mueve 0 en las cuatro medidas y el último mes siempre es un cierre: telescopea (R21). R34 por construcción. El hueco de F-103 se trata como un deshacer.
  - Marcas sin pisarse (`es_deshacer = NOT es_relleno AND NOT tiene_fila`). Mes por la cascada de D5. R31 correcto, sin presupuesto NULL publicado. Ventanas por `obra_id`.
- **Tests de F-042 (T12 y T15), uno a uno.** Los que fijaban el defecto (`CASE` de `orden_fase`, suma por tramos, apartado del telescopio) ahora fijan lo contrario, con su motivo. «Cierres que viven» pasa al JOIN con `reales_vigente_alta`. Los cinco de hueco tienen sustituto en `test_f118_check` y `test_f118_serie_densa`. El hash de la rama master es el mismo.
- **`mart`/`cierre`.** `nombre_mes` sale de `anio_mes`; marcas en `fact` y `v_pbi_fact` (NULL en planificado); `cierre` agrupa por `pm.anio_mes`; R38 arrastra el último ejecutado con filas, o 0.
- **Vista `v_pbi_planif_vs_real`.** `base` por (obra, mes, categoría, concepto); `producc` y `total_costes` por (obra, mes), y `beneficio` 1:1; `nombre_mes` solo en la SELECT final. La clave es única por construcción.
- **Coeficientes (D6, D10, D11).**
  - La venta final (`final_master` y `final_fase0`) suma `importe`, y de ahí salen pendiente, variación, % y beneficio.
  - La columna con coeficientes solo existe en VENTA con fuente master (NULL con fase 0). En el resumen, solo en la fila VENTA, fuera de gastos, beneficio y %. En la cabecera, dos columnas aparte; `modificados_aprobados` sigue sin coeficientes.
- **Diccionario v38.** `R-VENTA-COEFICIENTES` dice «sin coeficientes: cierres, beneficio y análisis; con coeficientes: lo que se factura; no hay ejecutado con coeficientes». P10 invertida y ficha de `ambito_id` corregida.

## Checkpoints

- **C1:** [x] `init.sh` en verde · [x] ficheros base.
- **C2:**
  - [x] una sola feature `in_progress`;
  - [x] rama `feature/F-118-…`;
  - [x] `current.md` al día;
  - [x] `history.md`: N/A, F-118 aún no está `done`.
- **C3:**
  - [x] hexagonal: `domain/` sin imports de infraestructura;
  - [x] primera línea con ruta en los 10 ficheros nuevos;
  - [x] sin prints, TODO ni secretos, y sin dependencias nuevas;
  - [x] semántica Sigrid: sin mezclar ámbitos ni `importe_origen` con `importe_mes`, y las versiones master intactas.
- **C3 bis:** N/A, no toca `docs/referencia/`.
- **C4:**
  - [x] trazabilidad (tabla de abajo) y suite en verde;
  - [x] los tests no tocan red ni base;
  - [x] MANUAL T26-T31 en `current.md` con comando y esperado (salvo O1);
  - [x] dobles: `test_f025_contrato_cliente` pasa, y los `PgFalso` nuevos solo implementan `filas_solo_lectura`, que existe en el cliente real.
- **C4 bis:**
  - [x] `rigor: critico`;
  - [x] fase RED con trazas reales en `impl_F-118.md` (T1, T3, T5, T7 con mutante en copia aislada, T8, T13-T16, T20, T23);
  - [x] cobertura 97,9 %;
  - [x] «Evidencias» con los cuatro números (sin fila de workers: no hubo campaña);
  - mutación N/A **justificada** por la exención de F-051 D7 (arriba), sustituida por huellas, invariante R21 (400 casos) y contraste local de 4 semillas.
  - Por esa misma exención quedan N/A la regla de 60 s, el coste por mutante, la cabecera no válida, RM1, RM2 y RM5, la campaña manual y los supervivientes. RM6 es N/A porque no se quitó ninguna guarda.
- **C4 ter:** N/A, no existe `harness/rutas_sensibles.json`.
- **C5:**
  - [x] T1-T25 y T32 `[x]`, con un commit `F-118 Tn:` por tarea;
  - T26-T31 son MANUAL, pendientes **por diseño**: F-118 no pasa a `done` sin ellas;
  - [x] sin temporales · [x] `features.json` coherente.

## Cobertura requisito → test

| Req. | Test (o verificación) |
|---|---|
| R1-R8 | `test_f118_regla_mes`; `test_f118_sql::…r1…`, `…r3_r4…`, `…r4…`, `…r5…`, `…r6…`, `…r7…`; `test_f118_check::…r8…` |
| R9, R29-R34 | `test_f118_serie_densa` (19 tests); `test_f118_sql::…r9…`, `…r29…`, `…r32…`, `…r34…` |
| R10-R14 | `test_f118_regla_mes` (relleno); `test_f118_serie_densa::…r13…`, `…r14…`; R12 con `…r33_…arrastra…` |
| R15-R19 | `test_f118_sql::…r15…` (ddl, mart, cierre), `…r16…`, `…r17…`, `…r18…` (3), `…r19…` |
| R20, R23, R24, R40, R46 | MANUAL T26-T30. R40 contrastado aquí |
| R21 | `test_f118_invariante::…r21…` (400 casos) y `test_f118_serie_densa::…r21…` |
| R22 | hash de la rama master (`test_f042_sql::…r9…`) y huellas T29 |
| R25-R26, R45 | `test_f118_check::…r25…` (6), `…r45…`; `test_f118_invariante::…r26…` |
| R27, R47 | `test_f118_sql::…r47…` (6: fichas sin «estorno», versión, regla dura, P10) |
| R28 | `test_f118_sql::…r28_sello…`, `test_f025_firma` |
| R35-R36 | `test_f118_serie_densa::…r29_r35_0709…`, `…r36…`; cifras contrastadas aquí (O1) |
| R37, R38 | `test_f118_check::…r37…` (6); `test_f118_sql::…r38…` |
| R39, R41-R44 | `test_f118_coeficientes` (18 tests) |

## Cambios requeridos

- Ninguno de código.
- **Antes de T27**, el líder corrige O1 en `progress/current.md`.
- O2-O7 no bloquean.

## Automejora (propuesta, no aplicada)

- **`CHECKPOINTS.md` C4:** toda cifra esperada de una MANUAL que dependa del dato debería llevar el `_built_at` de la sonda que la produjo. Así, una cifra caducada como O1 se ve antes de ejecutar.
