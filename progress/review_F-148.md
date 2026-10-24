Revisión incremental desde f44aa95 (pasada 2) · delta `f44aa95..16bce45`

# F-148 · Robustez de la nocturna · informe del reviewer

- **Veredicto: APPROVED.**
- **Rigor:** `critico`, declarado en `features.json`. Exige fase RED, cobertura ≥ 80 %, campaña de
  mutación con cero supervivientes y las verificaciones MANUAL con su comando.
- **`bash harness/init.sh`** (lo ejecuté yo, entero, sobre `16bce45`): exit 0, **8.798 passed,
  254 skipped** en 31 min 06 s. `PUERTA COBERTURA` 100 % (284/284), `PUERTA TAMAÑO` OK
  (requirements 148/150, design 250/250, impl 219/220) y `ENTORNO LISTO`. Árbol limpio.
- **Lo aprobado hasta `f44aa95` queda dado por bueno.** La pasada 1 (CHANGES_REQUESTED, cuatro
  cambios) está en el historial: `git show f44aa95:progress/review_F-148.md`. El delta no cambia
  ninguna firma pública ni mueve ficheros. Sí cambia la lógica de `pasos_a_omitir`, que ya estaba
  aprobada: la he vuelto a mirar entera (abajo).

## Los cuatro cambios de la pasada 1

1. **R4 real: hecho.** `reintento_conexion.py:61-73`: `MARCAS_DEFINITIVAS` = `password
   authentication failed`, `pg_hba.conf` (cubre «no … entry» y «rejects connection») y `permission
   denied for database`. El comentario explica que psycopg 3.3 abre SIN SQLSTATE. Ninguna de las
   tres aparece en un error transitorio (red, `53300`, `57P03`, DNS). Los tests traen seis casos con
   la forma REAL (`connection failed: connection to server at "h" (192.0.2.1), port 5432 failed:
   FATAL: …`, una IP de documentación RFC 5737), uno por marca.
   `test_f148_r4_la_apertura_real_llega_sin_sqlstate` provoca un fallo real de libpq SIN red
   (`service=` inexistente, con `PGSERVICEFILE` en `tmp_path`) y fija `sqlstate is None`: deja de
   ser un doble inventado. Los casos con SQLSTATE quedan como contrato, anotados. La RED se ve en
   `impl_F-148.md` (2 failed: `real-pg_hba-rechaza` y `real-sin-connect`). R4 está reescrito en
   `requirements.md`, con la decisión del humano del 2026-10-24.
2. **Mutación del delta: hecha y verificada.** Ver C4 bis.
3. **`azure-apps`: hecho.** El commit local `4535829` (sin push) dice que `conexiones_abiertas` mide
   SOLO la ingesta y que el «~550» no cuenta los diez `apply_grants.tras_*`. También cambia la fecha
   a «del 17 al 23 de octubre», amplía R4 y explica las retenciones al reanudar. Lo mismo en
   `docs/ARCHITECTURE.md:1018` y `:1274`.
4. **Despliegue MANUAL completo: hecho.** `current.md` trae: paso 0 con el tag de hoy
   (`r20261023-1016`) y su vuelta atrás exacta; la comprobación de la imagen del job (`az
   containerapp job show … --query "properties.template.containers[0].image"`); el reinicio del MCP
   y «Versión 60»; el push de `azure-apps` (`40b0da9`, `4535829`) solo con autorización, quitando
   después el «PENDIENTE»; y R31(a) por SQL (`GROUP BY step HAVING count(*) > 1`) o por la ausencia
   de `ejecucion_reanudada`.

## Lo nuevo: lecturas sin declarar al reanudar (riesgo R-a, decisión del humano)

- **Implementación** (`domain/reanudacion.py:42-51, 82-97`): `LECTURAS_PARA_REANUDAR =
  {"build_retenciones": {"build_stg", "build_mart"}}`. En `pasos_a_omitir` se añade la condición
  `lecturas <= omitidos`, donde `lecturas` es la intersección con los pasos de ESTA ejecución.
  Correcto en los cuatro casos: (a) se rehace stg o mart → retenciones no se omite; (b) se omite
  todo → se omite; (c) `build-retenciones` suelto, sin stg ni mart en la ejecución → la lectura no
  cuenta; (d) stg o mart DETRÁS en el orden → todavía no están en `omitidos`, así que se rehace (lo
  conservador, «ante la duda, construir»). Solo actúa al reanudar: `depends_on` sigue siendo
  `["ingest_raw"]` (lo fija un test) y el orden topológico no cambia. La noche normal queda igual:
  sin `terminados` no se omite nada. Sigue siendo dominio puro.
- **Tests** (`test_f148_reanudacion.py`): siete casos, uno por rama, más un test del orquestador
  (`ejecutados == [build_stg, build_mart, build_retenciones]`). Uno fija que el SQL sigue leyendo
  `stg.plan_mensual` y `mart.master_versiones_tipadas`, así que si deja de leerlos la declaración
  sobra y el test lo dice. RED pegada (5 failed).
- **¿Omite algo más que lea sin declarar? No.** Barrí yo todos los `.sql` de cada capa, con los
  comentarios quitados, buscando referencias a OTRO esquema construido, y clasifiqué cada una:
  - **Declaradas:** `cierre` → `stg` y `mart` (`depends_on` de `build_cierre`); `mart` → `stg`;
    `personal/02` → `stg.obras`.
  - **Vistas vivas** (leen el dato de hoy, no se quedan atrás): `maestro` → `stg` y `personal.*`
    (`CREATE OR REPLACE VIEW`); `compras/05` → `tesoreria.efectos`; `contabilidad`, `tesoreria` y
    `retenciones/01-03` → `maestro.*` (vistas); `mart/04` → `aux.periodificacion_partida` (vista).
  - **Lecturas de un build POSTERIOR** (las dos réplicas ven las de la noche anterior, igual que una
    noche normal): `retenciones/05` → `cierre.fact_cierre_mensual`; `compras/09` →
    `descompuestos.lineas` (`CREATE TABLE AS`, pero `descompuestos` va detrás).
  - **Funciones** (`CREATE OR REPLACE`, persistentes): `tesoreria`/`retenciones` → `compras.fn_*` y
    `stg` → `cierre.fn_parse_mes_fase`.
  - **Falsos positivos:** las menciones a `compras.documento_procesos` en `personal/06` y a
    `personal.usuarios_sigrid` en `compras/12` están en comentarios o en el texto del `COMMENT ON`.
    `personal/06` lee solo `raw`.
  La única lectura MATERIALIZADA y sin declarar de un build ANTERIOR de la misma noche es
  `retenciones/05_fin_obra.sql` → `stg.plan_mensual` y `mart.master_versiones_tipadas`, que es
  justo la declarada. Nadie lee de `retenciones`, así que la regla no hay que propagarla.

## Checkpoints (sobre el delta; los demás, como en la pasada 1)

- **C1** [x] `init.sh` en verde (arriba).
- **C2** [x] Una sola `in_progress`. [x] Rama de la feature. [x] `current.md` al día.
- **C3** [x] Hexagonal: lo nuevo está en el dominio y es puro. [x] Rutas en la primera línea.
  [x] Sin `print`, TODOs ni secretos: las IP son de documentación (`192.0.2.x`), y `caj-…`/`rg-…`
  son nombres de recurso que ya están en `azure-apps`, no IDs de suscripción.
- **C3 bis** N/A: el delta no toca `docs/referencia/`. **C4 ter** N/A: no hay `rutas_sensibles.json`.
- **C4** [x] R4 y R21 con sus tests nuevos, en verde. [x] Sin red ni BBDD (el test de libpq falla en
  el propio proceso, antes de abrir ningún socket). [x] Las MANUAL, con su comando.
  [x] **Dobles fieles**: el `[ ]` de la pasada 1 queda cerrado por los casos de forma real y por
  `r4_la_apertura_real_llega_sin_sqlstate`.
- **C4 bis** [x] Fase RED pegada para R4 y R-a. [x] Cobertura 100 % (284/284). [x] **Mutación del
  delta** (`progress/mutacion_F-148_revision1.md`, `--ficheros` sobre los dos módulos tocados,
  ENTEROS). La recalculé yo con `alcance_de_ficheros`: 2 ficheros y **243 líneas**;
  `generar_mutantes` da **20**. Coincide. Compilé los 20 y ninguno es inválido (el defecto del
  operador `not` no se repite aquí). Las líneas nuevas dan 2 mutantes (`reanudacion.py:94`, `and`→`or`
  y `<=`→`<`), los dos muertos y ninguno equivalente (`<` dejaría sin omitir el primer paso de la
  noche, con `omitidos` vacío). Las marcas nuevas son literales y no generan mutantes; las fijan los
  tests de forma real. [x] «Tiempo total» 11.862 s > 60 s: **campaña no reejecutada (3 h 18 min
  según el informe)**; queda el recálculo puro más las RM. [x] **RM1**: se midió sobre `6cb0de3`;
  de ahí a HEAD solo cambian `progress/impl_F-148.md` y el propio informe de mutación.
  [x] **RM2**: media 593,1 × 3 workers = 1.779 s frente a una línea base de 1.549-1.556 s, el mismo
  orden de magnitud; y 20 × 593,1 = el total. [x] **RM3**: ningún equivalente sale muerto.
  [x] **RM5** N/A: no hay supervivientes. [x] **RM6**: no se quitó ninguna guarda. [x] Ninguna
  cabecera de no válida y «Sin veredicto» a 0. [x] Reverificación EN SERIE 20/20 declarada.
  [x] La campaña ENTERA de la pasada 1 (92/92) sigue valiendo: fuera de estos dos módulos, el delta
  no toca ninguna línea de producción.
- **C5** [x] Las tareas T1-T15 están en `[x]`. Los commits de la revisión son `F-148 revisión 1: …`,
  uno por cambio. [x] Árbol limpio. [x] `features.json` sigue en `in_progress`; el cierre lo hace el
  líder.

## Cobertura de lo nuevo

| Req. | Tests |
|---|---|
| R4 (ampliado) | `conexion::r4_errores_que_no_se_reintentan[real-*]` (6), `r4_la_apertura_real_llega_sin_sqlstate` |
| R21 (lecturas al reanudar) | `reanudacion::r21_retenciones_se_rehace_si_*` (2), `r21_retenciones_se_omite_si_lo_que_lee_tambien`, `r21_una_lectura_*` (2), `r21_lecturas_para_reanudar_son_las_de_f110`, `r21_las_lecturas_siguen_en_el_sql_y_no_en_depends_on`, `r21_el_orquestador_rehace_retenciones_si_rehace_stg` |

El resto de la tabla requisito → test sigue como en la pasada 1.

## Riesgos que siguen abiertos (no bloquean; ya los conoce el humano)

- **R-b · `tcp_user_timeout`**: si la ventana TCP queda a cero más de 60 s, corta también el COPY de
  `reemplazar_filas` (`ingest_descompuestos`), que no tiene reintento. Hay que vigilarlo en las 7
  noches.
- **D4**: el coste de los diez `apply_grants.tras_*` está sin medir (paso 4 del despliegue).
- **`LECTURAS_PARA_REANUDAR` se mantiene a mano**: un build nuevo que lea, sin declararla, una tabla
  de otro build anterior tiene que añadirse ahí. Lo cubre en parte
  `r21_las_lecturas_siguen_en_el_sql…` (vigila la que ya hay, no las nuevas).

## Automejora (propuesta, no aplicada; ya figuraba en la pasada 1)

- **`harness/mutacion.py`, operador `not`**: compilar cada mutante en `generar_mutantes` y apartar
  los que no compilan. Hay que portarlo a `arnes-base`.
- **`reviewer.md` / C4**: «una excepción fabricada en un test tiene la forma que da la librería real
  en ESE camino».
- **Barrido de lecturas sin declarar**: esta pasada lo hizo a mano. Un test que lo automatice sobre
  los `.sql` (referencias a otro esquema en `CREATE TABLE AS`/`INSERT … SELECT` ⇒ están en
  `depends_on` o en `LECTURAS_PARA_REANUDAR`, o leen un build posterior) cerraría el tercer riesgo.
  Es una feature aparte, para que la decida el humano.
