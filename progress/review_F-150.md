<!-- progress/review_F-150.md -->
Revisión incremental desde 935fdd3 (pasada 4) · `git diff 935fdd3..1c54b31` · HEAD `1c54b31`

# F-150 · Review · la receta de la caja

**Veredicto: APROBADO** (pasada 4: N11-N15, T17-T35, R33-R43). Pasadas 1-3 (fase 1, hasta el
hotfix `f51b041`/`289fedb`) aprobadas y resumidas al final; el delta no las invalida (no cambia
firmas de la fase 1; `07` y `08` solo añaden ramas y columnas).

**Nivel de rigor:** `estandar` (declarado en `features.json`): fase RED en los requisitos
centrales, cobertura de lo cambiado ≥ 80 %, mutación con supervivientes analizados.

## Pasada 4 · lo que se verificó

- **`bash harness/init.sh` ejecutado por mí sobre `1c54b31`:** **verde**, exit 0, «ENTORNO LISTO»:
  9.813 passed, 268 skipped (5.783 s); `PUERTA COBERTURA` `[OK]` 100 % (21/21, diff desde
  `935fdd35ee`); `PUERTA TAMAÑO` `[OK]`. Coincide con lo que declara el implementer.
- **Alcance:** dominio (`neto_fifo`, `iva_efectivo_compra`, constantes, `PASOS_RECETA` con SALDO,
  `CODIGOS_SIGRID` con H13), dos sub-pasos nuevos en `build_tesoreria_step.py`, `00_setup`, `07`
  (cuota CP), `08` (rama H13), `09` y `10` nuevos, YAML de hipótesis (30), diccionario v66,
  ARCHITECTURE, CLAUDE.md, tests. Coincide con `design.md` y con el informe. Hexagonal respetada:
  dominio puro, SQL en `sql/tesoreria/NN_`, la secuencia en `application`.
- **`double precision` de `raw` (el fallo de `d1c2ee1`), SQL nuevo leído línea a línea:**
  - `09`: el único `ROUND` es `ROUND((COALESCE(l.tot,0) * (1 - canfac/can))::NUMERIC, 2)`; las
    otras ramas, `::NUMERIC(18,2)`; `abs(x.tot) < 1e8` no exige numeric. Correcto.
  - `10`: todos los `l.tot`, `h.tot`, `totiva`, `totpag`, `totdoc` llevan `::NUMERIC(18, 2)`; los
    ocho `ROUND(..., 2)` son sobre `tesoreria.efectos.importe` (`NUMERIC(18,2)`, `00_setup:100`)
    por cuotas ya numeric. Correcto.
  - `07`: los dos `ROUND` nuevos, sobre `efectos.importe × cuota_cp` (numeric). `08`: `ROUND(100 *
    cuota / base, 2)` con `tot` e `ivacuo` casteados. Correcto.
  - Los tests de repositorio son de TEXTO (fijan cada cast y prohíben `l.tot`/`h.tot` sin él:
    `test_f150_saldo.py:183,195`, `test_f150_albaranes.py:349`, `test_f150_iva_isp.py:96`). La
    ejecución real con `raw` en `double precision` está en las sandboxes del implementer (Postgres
    16 desechable: `09` 23 OK, `10` 14 OK, `impl_F-150.md` §4), fuera del repo como en la fase 1;
    los contrastes de solo lectura en Azure (§3) ejecutaron `09` y `10` sobre los tipos reales.
- **Decisiones del humano, respetadas:**
  - N11: `_alb_fifo` particiona por `(obra_id, proveedor_id)`, orden `(fecha NULLS FIRST,
    linea_id)`, compensa lo más antiguo; sin proveedor no compensa; guarda R35 dentro de la
    transacción. `neto_fifo` del dominio es la misma fórmula.
  - N12: H02 sin `CP`; cuota CP de la cartera (`07`) y del saldo (`10`) por la categoría de la
    partida de cada línea de `raw.dcfpro`; la receta lo resta y lo declara (F-154 fuera).
  - N13: el saldo usa `raw.hmores.tot` de recursos PERSONA internos hasta el cierre y la cartera
    GENERAL (sin nóminas); la receta prohíbe sumar nóminas.
  - H28 `[CON_SALDO, SIN_SALDO]` defecto `CON_SALDO`; H29 `[ORIGINALES, AGR]` con los originales
    `BAJA` + `estado_codigo = 14` (y la ruptura de `R-TESORERIA-ESTADO` declarada); retenciones
    como efectos propios (receta paso 0 y `COMMENT` de `10`).
  - N15: H13 SIGRID por obra con `base >= 500000` (= `UMBRAL_BASE_H13`, test `iva_isp:113`), si no
    DEFECTO (valor NULL cae al defecto en el `CASE` de `08`); H30 `MENSUAL_REDEME` por defecto, con
    `_hasta_4m`; el paso 0 suma el IVA NETO recuperado (soportado − repercutido) según H30.
- **Diccionario:** v66; fichas de `albaranes_pendientes_neto` y `saldo_partida_obra` con el aviso
  de `R-PERFILES`; ambas en `NO_DISPONIBLES` de F-141 (`5f02555`). `azure-apps` `3ca37bf` al día.
- **Sin secretos:** barrido del diff, solo `127.0.0.1:55432` (contenedor local). Ni `GRANT` ni
  `DROP` de tablas reales. Primera línea con ruta en ficheros nuevos; sin `print`.
- **MANUAL:** el redespliegue de N11-N15 está en `current.md` con comandos exactos (paso 0 de
  vuelta atrás, imagen, `build-tesoreria`, cifras esperadas, `publicar-diccionario` v66, `check-*`,
  MCP). T15/T25/T31/T35 abiertas solo por ese despliegue MANUAL, como en la fase 1.

### Observaciones (no bloquean)

1. Con H29 = `AGR`, el IVA del saldo sigue contando el de los originales vencidos (los AGR no son
   factura y no tienen fracción): aproximación razonable, pero la ficha podría decirlo.
2. `08` lleva el umbral 500000 como literal; lo ata al dominio el test de texto, no el código.
3. Tasks: T24/T31/T35 marcan la mutación e `init.sh` hechos; queda solo el despliegue.

## Mutación (C4 bis) · `progress/mutacion_F-150_n11_n15.md`

- **Recálculo puro** (`alcance_de_feature('F-150', base='0659528')` + `generar_mutantes`): **78
  líneas** (20 + 58) y **17 mutantes**, igual que el informe. Con la semilla `20260820` la muestra
  de 8 sale entera en `neto_fifo` (`:401` ×3, `:405` ×3, `:409`, `:410`).
- **Campaña no reejecutada:** 9.754,7 s según el informe (> 60 s).
- **RM1:** medido en `5f02555`; hasta HEAD solo cambian `progress/` y `tasks.md`. Alcance igual.
- **RM2:** base ~2.280 s (3 workers), media 1.219,3 s, `8 × 1.219,3 = 9.754` = tiempo total.
  Coherente; ningún salto de orden de magnitud.
- **RM3:** los dos equivalentes posibles del generador (`:401 x <= 0` y `:405 x < 0`, el cero no
  cambia nada) NO están en la muestra. Ningún equivalente sale muerto.
- **RM4 (copia `git archive` en el scratchpad, ya borrada):** sin mutar, 69 passed en
  `test_f150_albaranes.py` + `test_f150_iva_isp.py`; `:405 x <= 1` → 3 failed; y un no muestreado,
  `:408 a_compensar + acumulado` → 8 failed.
- **RM5:** N/A, rigor `estandar`. **RM6:** no se quitó ninguna guarda.
- Sin «CAMPAÑA NO VÁLIDA», 0 «Sin veredicto». Muestra de 8 (tope 20) justificada por coste en el
  informe; el SQL no se muta y lo cubren textos y sandboxes.

## Checkpoints (pasada 4)

- **C1:** `[x]` `init.sh` código 0 (ejecutado por mí) · `[x]` ficheros base.
- **C2:** `[x]` una sola `in_progress` · `[x]` rama `feature/F-150-receta-caja` · `[x]`
  `current.md` al día · `history.md`: N/A, la feature no es `done` (falta el despliegue MANUAL).
- **C3:** `[x]` hexagonal · `[x]` primera línea con ruta · `[x]` sin `print`, TODO, secretos ni
  dependencias nuevas · `[x]` semántica de Sigrid (pendiente con la fórmula de `compras/01`
  copiada y comparada por test; `R-ALBARAN-ABSURDO` a 1e8; personal por `hmores.tot`).
- **C3 bis:** N/A, el delta no toca `docs/referencia/`.
- **C4:** `[x]` trazabilidad (tabla) · `[x]` sin red ni BBDD en los tests · `[x]` MANUAL con su
  comando exacto en `current.md` · `[x]` dobles: comprobación automática de `init.sh`.
- **C4 bis:** `[x]` rigor declarado · `[x]` RED con salida real para T17-T34 (`impl_F-150.md` §5)
  · `[x]` cobertura `[OK]` (ver la línea de `init.sh` arriba) · `[x]` mutación verificada · `[x]`
  «Evidencias» con los cuatro números.
- **C4 ter:** N/A, no existe `harness/rutas_sensibles.json` (solo el `.ejemplo`).
- **C5:** `[x]` T17-T23, T27-T30, T32-T34 `[x]` con su commit `F-150 Tn`; T24/T25/T31/T35 abiertas
  solo por el despliegue MANUAL · `[x]` árbol limpio · `[x]` `features.json` al día.

## Cobertura · requisito → test (pasada 4)

| Req. | Tests (`tests/test_f150_*.py`, nº) |
|---|---|
| R33-R35 | `albaranes` r33 (13), r34 (16), r35 (2) + sandbox `09` |
| R36-R37 | `albaranes`/`sql`/`diccionario` r36 (9), r37 (2) |
| R38-R40 | `saldo` r38 (12), `receta`/`saldo` r39 (4), `diccionario` r40 (4) + sandbox `10` |
| R41-R43 | `iva_isp` r41 (10), `receta` r42 (2), `saldo`/`diccionario` r43 (6) |

## Pasadas 1-3 · resumen

- **Pasada 1** (`6efddfe`): rechazo solo por C4 (MANUAL sin comando exacto en `current.md`).
  `init.sh` verde (9.645 passed), sandbox `sandbox_f150.py` reejecutada (66 OK), Azure en solo
  lectura, catálogo 27 hipótesis, mutación 20 mutantes con RM1-RM6 verificados (RM4 en `:227`,
  `:485`, `:498`).
- **Pasada 2** (`7eed62e`): APROBADO; C4 MANUAL corregido; `init.sh` verde (9.645 passed).
- **Pasada 3** (`289fedb`): APROBADO; hotfix `SUM(fv.totbas::NUMERIC(18, 2))` en `07` con su RED
  reproducido; ninguna otra columna `double precision` de `raw` en función solo numeric.

## Automejora (propuesta, no aplicada)

1. `CHECKPOINTS.md` C4 bis: cuando el SQL nuevo lea `raw`, exigir que la sandbox con tipos de
   Azure (`double precision`) viva en el repo (p. ej. `tests/sandbox/`, marcada y saltada sin
   Docker) en vez de en el scratchpad: hoy el reviewer no puede reejecutarla si no se la pasan.
2. `implementer.md` (y `arnes-base`): «MANUAL a `current.md` CON su comando exacto» (pasada 1).
