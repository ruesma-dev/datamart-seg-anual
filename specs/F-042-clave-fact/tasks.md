<!-- specs/F-042-clave-fact/tasks.md -->
# F-042 · Tareas

Rama `feature/F-042-clave-fact`. Un commit por tarea (`F-042 Tn: ...`).
Rigor `critico`: **fase RED obligatoria** (test que falla antes del código, con
su traza en el informe) y **cobertura de las líneas cambiadas**.
**SIN campaña de mutación**, por decisión del humano del 2026-08-29: el reviewer
la declara N/A en C4 bis citándola, y la evidencia que la sustituye es T14–T17.

## Bloque A · La regla, en dominio puro

- [x] T1: Escribir `tests/test_f042_regla.py` con las **24 colisiones reales** de `progress/explore_F-042.md` como fixture, incluida 0606 (todo a cero) y 0545 (dos fases con fechas idénticas), contra una API que aún no existe | Verificación: `pytest tests/test_f042_regla.py` **falla** (fase RED, traza al informe)
- [x] T2: Crear `etl_sigrid/domain/cierres.py` con `Cierre`, `PlanCierres` y `plan_de_cierres()`: gana el de mayor `numero_fase` con acumulado `<> 0`; si todos son 0, el mayor; el orden desplaza solo por descartes | Verificación: `pytest tests/test_f042_regla.py` en verde (R1, R2, R4, R5, R11)
- [x] T3: Añadir a `tests/test_f042_regla.py` los casos de borde: N≥3 cierres en un mes, hueco de origen NO descartado que debe seguir siendo hueco, mes con un solo cierre que no se toca | Verificación: `pytest tests/test_f042_regla.py` (R3, R4, R6)

## Bloque B · El SQL

- [x] T4: Escribir `tests/test_f042_sql.py` afirmando sobre el texto de `sql/stg/08_plan_mensual.sql` que existen las CTE `reales_cierres` / `reales_vigente` / `reales_orden`, que el `LAG` de la rama de reales compara `orden_fase`, que `version` recibe `mes_fase_num`, y que la **rama master (amb 8/11) no cambia** | Verificación: `pytest tests/test_f042_sql.py` **falla** (fase RED)
- [x] T5: Insertar las tres CTE en la rama de reales de `sql/stg/08_plan_mensual.sql` según §1 del diseño, sin tocar la rama master | Verificación: `pytest tests/test_f042_sql.py` en verde
- [x] T6: Cambiar `reales_con_lag` para leer de `reales_base ⨝ reales_orden` con `WHERE vive` y usar `orden_fase` en los cuatro `CASE` y en el `WINDOW` | Verificación: `pytest tests/test_f042_sql.py`; `python -c "import etl_sigrid"`; revisión visual del diff
- [x] T7: Comprobar que `build_stg_step.py` NO necesita marcador nuevo y dejar por escrito el argumento de tramos de F-019 en el comentario de cabecera del bloque | Verificación: `grep F019_FILTRO_OBRAS` sigue dando una sola aparición; `pytest tests/test_f019_tramos.py`

## Bloque C · La comprobación de solo lectura (R17)

- [x] T8: Escribir `tests/test_f042_check_cierres.py` contra un cliente Postgres falso, con un caso conforme y otro discrepante | Verificación: `pytest tests/test_f042_check_cierres.py` **falla** (fase RED)
- [x] T9: Crear `etl_sigrid/infrastructure/postgres/cierres_sql.py`, que **solo construye texto** y no abre conexión, al estilo de `unicidad_sql.py` | Verificación: `pytest tests/test_f042_check_cierres.py` en verde
- [x] T10: Añadir el comando `check-cierres` a `main.py`: contrasta lo que hay en `stg.plan_mensual` contra `plan_de_cierres()` y comprueba el telescopio `SUM(importe_mes) = último importe_origen`; sale distinto de 0 nombrando obra, mes y cierres | Verificación: `python main.py check-cierres --help`; `pytest tests/test_f042_check_cierres.py` (R16, R17)

## Bloque D · La huella antes/después (R22–R25)

- [x] T11: Escribir `tests/test_f042_huella.py` con dos huellas de juguete —una con una obra que cambia, otra con todo igual— y el veredicto esperado | Verificación: `pytest tests/test_f042_huella.py` **falla** (fase RED)
- [x] T12: Crear `etl_sigrid/domain/huella.py` con `FilaHuella`, `comparar_huellas()` y `veredicto(comparacion, obras_esperadas)`, que devuelve las **dos listas completas** (numeración e importes) y código distinto de 0 si cambia algo fuera de lo esperado | Verificación: `pytest tests/test_f042_huella.py` en verde (R23, R24, R25)
- [x] T13: Crear `etl_sigrid/infrastructure/postgres/huella_obras.py` (SQL agregado a obra × ámbito × mes con `importe_mes` e `importe_origen`, lectura por tramos con la puerta de disco de F-019, y CSV UTF-8 BOM con `;`) y los comandos `huella-obras` y `comparar-huellas` en `main.py` | Verificación: `pytest tests/test_f042_huella.py`; `python main.py huella-obras --help` (R22)
- [x] T14: **ANTES de nada contra la base**, capturar la huella actual de los cuatro ámbitos: `python main.py huella-obras --desde stg --out huella_f042_stg_antes.csv` y `--desde mart --out huella_f042_mart_antes.csv` | Verificación: MANUAL (humano) — los dos CSV existen, con ~11.883 celdas y los cuatro ámbitos presentes
- [x] T15: Generar la huella propuesta sin materializar: `python main.py huella-obras --desde stg --propuesta --out huella_f042_stg_despues.csv` | Verificación: MANUAL (humano) — termina sin escribir en la base y la ocupación de disco no se mueve
- [x] T16: Comparar: `python main.py comparar-huellas huella_f042_stg_antes.csv huella_f042_stg_despues.csv --obras-esperadas 0246,0310,0433,0462,0471,0499,0545,0571,0606` | Verificación: MANUAL (humano) — código 0; **cero diferencias en los ámbitos 8 y 11**; ninguna obra fuera de la lista se mueve (R9, R10, R24)
- [x] T17: Contrastar el informe de T16 contra la línea base de `progress/explore_F-042.md`, obra a obra, y pegar la tabla en el informe de implementación | Verificación: MANUAL (humano) — las 7 obras con dinero cuadran con R14; 0433 y 0606 cambian de filas y **0 €** (R11, R12, R14)

## Bloque E · El diccionario

- [x] T18: Actualizar `config/diccionario/stg.yaml` (ficha de `plan_mensual`): la regla nueva y que `version` es el número original de Sigrid **con huecos** | Verificación: `pytest tests/test_f006_fichas.py tests/test_f006_formato.py` (R18)
- [x] T19: Retirar de `config/diccionario/mart.yaml` el aviso de dato doblado en las cuatro fichas y en las columnas `importe_origen` / `importe_origen_raw` | Verificación: `grep -n "DOBLADO\|39,07\|8.778" config/diccionario/mart.yaml` no devuelve nada vigente; `pytest tests/test_f006_fichas.py` (R18)
- [x] T20: Describir el grano ya sin defecto en `mart.v_pbi_fact_categoria` y en `cierre.v_pbi_planif_vs_real`, que eran las fichas sin aviso pese a ser la superficie de consumo | Verificación: `pytest tests/test_f006_fichas.py` (R19)
- [x] T21: Revisar la detección de fan-out del diccionario, que derivaba de la unicidad de la clave | Verificación: `pytest tests/test_f006_relaciones.py` (R20)
- [x] T22: Subir `version` en `config/diccionario/00_global.yaml` y comprobar que la lista de pendientes no crece | Verificación: `pytest tests/test_f006_regla_de_oro.py` (R21)
- [x] T23: Añadir a `docs/ARCHITECTURE.md` una línea en «Semántica Sigrid imprescindible»: dos cierres en un mes, manda el moderno; el descartado sigue en `raw` y en `stg.fases` | Verificación: `pytest tests/test_f006_docs.py`

## Bloque F · Cierre

- [x] T24: Comprobar la cobertura de las líneas cambiadas y escribir el informe en `progress/impl_F-042.md` (≤220 líneas), con la traza de cada fase RED y la tabla de T17 | Verificación: `python -m harness.tamano --feature F-042`
- [x] T25: Ejecutar `bash harness/init.sh` en verde | Verificación: `bash harness/init.sh` termina con código 0

---

## Pasos de cierre que NO ejecuta el agente

Son **escrituras contra el Postgres compartido en producción**. Las autoriza y
lanza el humano, con el detalle y el coste en §5 del diseño. El disco dejó de
ser la restricción el 2026-08-29 (64 GB, 29 % ocupado, 45,4 GB libres); lo que
sigue siendo regla dura es que un agente no escribe en producción.

1. **La reconstrucción con el mismo `raw`**, sin `ingest`: `python main.py stage`
   + `build-mart` + `build-cierre`. Coste en disco **cero neto** (el build es en
   el mismo sitio) y el pico lo acota la puerta de F-019. Tiempo: **hora y media
   a dos horas** el `stage` y **media hora** el `build-mart`, con la advertencia
   de que las medidas conocidas (110 y 21,5 min) son con 120 IOPS y que el techo
   de 10 MiB/s del `B1ms` no ha cambiado. **Requiere que T14 se haya ejecutado
   antes**: el build pisa la tabla.
2. **La huella de después**, ya materializada:
   `huella-obras --desde stg --out ..._stg_despues_real.csv` y `--desde mart --out
   ..._mart_despues.csv`, y `comparar-huellas` contra las de T14. Es la que cierra
   R22–R25 en los cuatro ámbitos sobre el dato de verdad.
3. **`python main.py check-unicidad`** → debe dar **0 claves duplicadas** en
   `mart.fact_seguimiento_mensual`, frente a 8.778 (R13).
4. **`python main.py check-cierres`** y **`check-diccionario`** → código 0 y
   biyección exacta (R17, R21).
5. **`python main.py publicar-diccionario`** → escritura contra Azure, la
   autoriza el humano (R18–R21).
6. **`python main.py timings`** → contrastar el coste del `build_stg` contra el
   1 h 50 del 2026-08-28 (riesgo 4 del diseño).
