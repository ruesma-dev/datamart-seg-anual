<!-- progress/review_F-011_cierre.md -->
# F-011 · Carga incremental del datamart — Review de cierre

> **Fecha**: 2026-08-20. **Rama**: `feature/F-011-carga-incremental`.
> **Alcance de esta review**: el **bloque A entregado** (T1–T6, T21, T22, T23),
> la **puerta de R8** (`progress/medicion_F-011.md`) y el **descarte del
> bloque B** firmado por el humano el 2026-08-20 (§6.2 de ese documento).
> **Qué NO reviso**: código del bloque B, porque no existe y no debe existir.

## Veredicto

> ## APPROVED

Con una reserva a la vista —**C5 queda en `[ ]`** hasta el commit de cierre— y
la lista de **apuntes obligatorios antes de marcar `done`** del §8. Marcar
`done` sin ellos deja C2 y C5 incumplidos: esto aprueba el trabajo, no exime
del bookkeeping.

**Nivel de rigor**: `critico`, **declarado** en `harness/features.json`
(`"rigor": "critico"`). Exige: C1–C5 + C3 bis, tests trazables, **fase RED**,
**cobertura** de las líneas cambiadas ≥ 80 %, **campaña de mutación con cero
supervivientes** salvo justificación aceptada por el humano, y verificaciones
`MANUAL (humano)` listadas con su comando exacto y su resultado real.

---

## 1 · Lo que de verdad había que juzgar: ¿es creíble la medición?

Es la pregunta correcta, porque si el bloque A está mal medido se ha tomado
una decisión de arquitectura sobre datos falsos. **Mi conclusión: la medición
es creíble, y con más respaldo del que el propio informe reclama.**

No me he limitado a leer el §0 («de dónde salen los números y de dónde no»).
He buscado corroboración **fuera** de las fuentes que el implementer no puede
enseñarme hoy (los logs de Log Analytics y la lectura del catálogo de Sigrid,
las dos inalcanzables desde el puesto por D11).

### 1.1 · Coherencia interna: cuadra hasta el decimal

Recalculado a mano sobre el propio documento:

| Comprobación | Resultado |
|---|---|
| Suma de la tabla de `§2` (por tabla) | 2.124,9 s = **35,4 min** ≈ los 35,6 min que `§1` da a la ingesta de esa misma carga |
| Porcentajes de `§2` (61,3 / 9,8 / 8,6 / 6,7 %…) | **todos correctos** contra ese total; el acumulado 79,7 % también |
| Conversión segundos→minutos de las 11 filas | **las 11 correctas** al redondeo declarado |
| Medias de `§1` (`build_stg` 110,7 · `build_mart` 21,6 · total 165,2) | **correctas** |
| Reparto de `§5` (134,9 + 1.831,3 = 1.966,2 s; 6,9 % / 93,1 %) | **correcto** |
| Crecimientos de `§2.1` (0,0004 % / 0,023 % / 0,029 % / 0,044 % / 0,0084 %) | **los cinco correctos** |
| Partición 7 + 24 = 31 tablas | **exacta**: las 31 de `config/tables_sigrid.yaml`, sin duplicados ni sobrantes |

Y una prueba de consistencia que no se puede fabricar a mano con facilidad:
**los recuentos de filas de `§2` caen ordenadamente entre las dos fotografías
de `§2.1`**. `obrparpre` 13.809.325 (18-ago) < 13.809.350 (nocturna del 19) <
13.809.381 (19-ago mediodía); igual `con` (2.172.651 < 2.172.969 < 2.173.156),
`dcapro` y `dcfpro`. Tres cargas, tres instantes, monotonía perfecta. Eso sale
de datos reales, no de una estimación.

### 1.2 · Corroboración externa de los totales

`progress/current.md`, escrito **en su día por otra sesión y para otra cosa**,
registra la carga del 18-ago como «`Succeeded` en **2 h 45**» y la nocturna del
19 como «02:00:16 → 04:48:05 UTC = **2 h 48**». La medición dice **165,1** y
**167,7** minutos. Coinciden. Dos registros independientes del mismo hecho.

### 1.3 · ¿Son comparables las tres cargas?

Sí, y el sesgo que podría haber **empuja en la dirección contraria a la
conclusión**, que es lo que importa:

- Las tres son `--full` y las tres acabaron en `SUCCESS`.
- Dos son manuales (horario laboral, servidor **compartido** con `albaranes` y
  `partes`) y una es la nocturna de las 02:00. Cabría temer que las manuales
  salieran infladas por contención. **Ocurre lo contrario**: la nocturna es la
  que más tarda en la ingesta (35,6 min) y la que da a la ingesta **más peso**
  (21,2 %). Es decir, el caso más favorable al bloque B ya está dentro de la
  media, y aun así se queda en la mitad del umbral del 40 %.
- Las dos primeras corren imágenes distintas (`r20260818-1003` y
  `r20260818-2146`), pero lo único que añade la segunda son las puertas de
  coherencia de F-024, que `current.md` registra en **0,1 y 0,2 s**.
- `build_stg` varía **menos de 30 s** entre cargas de días distintos: la
  dispersión del conjunto es baja de verdad, no dicha de pasada.

### 1.4 · ¿Es 2,25 min un techo o una estimación optimista?

**Es un techo, y además holgado.** No es una proyección de cuánto ahorraría un
incremental: es el **coste completo** de las 7 tablas que podrían ser
incrementales, puesto a cero. El ahorro real sería estrictamente menor —a cada
una de esas 7 hay que pedirle igualmente el esquema y al menos una página—.
El documento lo dice y el cálculo lo sostiene.

Y la conclusión no vive de la precisión: para tocar el umbral de DA-7 haría
falta que el ahorro fuera **9 veces** mayor, o que la ingesta **doblara** su
peso. Ninguna imprecisión plausible de la medición cubre esa distancia.

### 1.5 · El hallazgo que decide, verificado por una vía independiente

Que `tiemod` no existe en 24 de 31 tablas sale de una lectura del catálogo de
Sigrid que **hoy no puedo repetir**. Así que lo he contrastado contra
`azure-apps/sigrid_tablas.md`, el diccionario, que sí está en local:

- **`obrparpre`** (13,8 M filas, 61 % de la ingesta): la ficha del diccionario
  (línea 17441) lista **exactamente las mismas 22 columnas, en el mismo
  orden**, que el implementer transcribió del catálogo. **Ninguna es una marca
  de modificación.**
- **`dcapro`** y **`dcfpro`** (18,4 % entre las dos): tampoco tienen `tiemod`;
  sus fechas son `fec` «Fecha prevista» y `garfec` «Fecha garantía» — fechas de
  **negocio**, exactamente como dice §3.1.
- **`con`** (línea 5665): **sí** tiene `| tiemod | Tiempo modificación | Real
  tiempo |`. Y `auxobrtip` (línea 2751) también. Los dos lados de la partición
  cuadran.
- Los recuentos del diccionario que la spec mandaba poder reproducir salen
  clavados: `fecalt` **18**, `fecmod` **6**, `sello` **2**, `tiemod` **232**.
- `config/tables_sigrid.yaml` declara `incremental_column: tiemod` en **18**
  entradas: el número del §8 es correcto.

**Conclusión**: el hallazgo no depende de creerle al implementer una lectura
que no puedo repetir. Está corroborado por el diccionario, que además explica
de dónde venía el error heredado de F-009: el recuento de 232 filas de
`tiemod` es real, pero **no incluye las tablas que nos cuestan el tiempo**.

---

## 2 · El descarte del §6.1: ¿se sostiene el argumento del «solo altas»?

Es la alternativa peligrosa, porque **sí llegaría al umbral** (1.688 filas en
vez de 20 M). El argumento para descartarla es que `obrparpre` guarda
planificación que **se edita**, y que una noche de solo altas daría un dato
silenciosamente viejo.

**El argumento se sostiene, y no es teórico. Lo he verificado en el código:**

| Evidencia | Dónde |
|---|---|
| `planif` es «**Planificación temporal**», Texto ilimitado, **columna de la partida**, no fila propia | `azure-apps/sigrid_tablas.md:17445` |
| El ETL la ingiere **a propósito** | `config/tables_sigrid.yaml:63` — «planif SÍ lo necesitamos (cadena de planificación temporal)» |
| `build_stg` la lee de `raw.obrparpre` | `build_stg_step.py:485` — está entre las 10 columnas seleccionadas |
| Hay un **parser de `obrparpre.planif`** que alimenta el plan mensual | `config/business_rules.yaml:11`, `postgres_client.py:74` |

Es decir: `planif` no es un campo decorativo, es **la entrada del cálculo que
produce `stg.plan_mensual`**, el corazón del seguimiento. Editar la
planificación de una partida existente **no crea ninguna fila nueva**, así que
un cursor por `ide` no la vería jamás, y el datamart serviría un plan viejo sin
que nada se pusiera rojo. El descarte está bien argumentado y bien cerrado.

Los otros dos descartes del §6.1 también se sostienen: el watermark por sumas
de control ya estaba muerto por DA-4 (opción c) y el `where` del YAML acota por
**negocio**, que es DA-1 y por tanto F-025.

**Un detalle de calidad, no un defecto**: el bajado de `page_size` de
`obrparpre` por lo pesada que es `planif` (`tables_sigrid.yaml:64`) explica de
paso por qué esa tabla se lleva 21,7 min. La forma del perfil de `§2` es
coherente con cómo está configurada la ingesta.

---

## 3 · ¿Puede una feature `critico` cerrarse `done` sin su bloque principal?

**Sí, y en este caso es el desenlace correcto.** El argumento, contra
`CHECKPOINTS.md` y contra la spec aprobada, no contra mi gusto:

1. **`CHECKPOINTS.md` abre diciendo «no se evalúa el camino, se evalúa el
   destino».** El destino de F-011 no lo fijo yo: lo fija su spec aprobada, y
   esa spec define **dos** destinos legítimos.
2. **La condicionalidad es normativa, no una salida de emergencia.**
   `requirements.md` §0 dice, en la tabla de bloques, que el bloque B «se
   implementa **solo si** la puerta de decisión de R8 lo justifica», y que «el
   orden es normativo». R8 hace del informe firmado una **puerta de proceso**.
3. **La rama del NO estaba escrita antes de medir.** DA-4: «si el veredicto de
   R7 es `NO SIRVE`, (a) se renuncia a la ingesta incremental por watermark y
   el esfuerzo se lleva al build»; y su efecto concreto: «si R7 dice `NO
   SIRVE`, **el bloque B se cierra sin implementar y F-011 entrega solo el
   bloque A**». DA-7 fijó los dos umbrales. **La feature ha ejecutado su propia
   spec.**
4. **La puerta se ha cruzado como la spec manda**: informe con los dos números
   al lado de sus dos umbrales (`§5`), recomendación firmada del implementer
   (`§6`) y **firma del humano** fechada (`§6.2`, commit `6125be3`).
5. **El entregable existe y es sustancial**: tres comandos de solo lectura,
   1.548 líneas en alcance, 175 tests nuevos, y —lo que más vale— una **línea
   base medida** contra la que F-025 podrá demostrar su mejora.

Lo contrario sería el peor incentivo posible: penalizar a la feature que midió
antes de optimizar y descubrió que no había que optimizar ahí. **Un NO medido
es un entregable.** El único estado alternativo defendible sería `done` con una
ficha nueva para el bloque B, y ni eso hace falta: el trabajo ya tiene destino
nominado, que es **F-025**.

**Lo que sí exijo** es que el cierre lo **diga**. Hoy no lo dice: ver §8.

### 3.1 · ¿Merece quedarse el trabajo que sí se hizo?

**Sí, entero.** Los tres comandos convierten esta medición en repetible en vez
de en la cuenta a mano de una sesión, y `perfil-carga` es justamente el
instrumento con el que se va a juzgar F-025 («si este paso costase cero…»).
`diagnostico-tiemod` deja acreditado para siempre por qué no hay watermark, que
es la pregunta que ya se ha hecho dos veces (F-009 y F-011). Tirarlo sería
tener que volver a medir a mano la próxima vez.

---

## 4 · Cobertura requisito → test

Del **bloque A y los transversales**, que es lo entregado. Comprobado por
barrido de nombres sobre `tests/test_f011_*.py`; la suite completa pasa (798).

| Req | Test que lo cubre | Estado |
|---|---|---|
| R1 | `test_f011_perfil.py::test_f011_r1_desglosa_pasos_y_tablas` (+13 más) | **[x]** |
| R2 | `test_f011_perfil.py::test_f011_r2_techo_de_mejora_por_paso` (+5) | **[x]** |
| R3 | `test_f011_perfil.py::test_f011_r3_tablas_que_acumulan_el_80_pct` (+9) | **[x]** |
| R4 | `test_f011_bench.py::test_f011_r4_bench_no_escribe_en_postgres` (+25) | **[x]** |
| R5 | `test_f011_bench.py::test_f011_r5_cap_rechazado_no_aborta_el_bench` (+10) | **[x]** |
| R5-bis | `test_f011_bench.py::test_f011_r5bis_registra_latencia_maxima_por_pagina` (+4) | **[x]** |
| R6 | `test_f011_tiemod.py::test_f011_r6_diagnostico_por_tabla` (+16) | **[x]** |
| R7 | `test_f011_tiemod.py::test_f011_r7_veredicto_sirve_no_sirve_sin_evidencia` (+25) | **[x]** |
| R8 | **MANUAL** · `progress/medicion_F-011.md` + firma del humano (`§6.2`) | **[x]** verificado por mí en §1 y §5 |
| R9–R19 | **no aplican**: bloque B descartado por la puerta de R8 (DA-4/DA-7) | **N/A justificado** |
| R22 | `test_f011_alcance.py::test_f011_r22_el_sql_de_stg_y_mart_no_se_toca` (+4) | **[x]** |
| R23 | `test_f011_bench.py::test_f011_r23_solo_select_contra_sigrid_*` (+6) | **[x]** |
| R24 | `test_f011_alcance.py::test_f011_r24_sin_secretos_en_lo_nuevo` (+3) | **[x]** |
| R25 | `test_f011_cli.py::test_f011_r25_comandos_de_lectura_no_escriben_en_meta` (+3) | **[x]** |

**Cómo comprobé que la suite no toca red ni BBDD** (lo pide el afinado que
propuso la review de F-004): barrido de imports sobre `tests/test_f011_*.py`.
No hay `psycopg`, `requests`, `httpx`, `urllib` ni `socket`; la única aparición
de «psycopg» es una **aserción de que el módulo del banco NO lo importa**
(`test_f011_bench.py:507`). Los dobles son `unittest.mock` y `SimpleNamespace`.

**R22 verificado también por mí**, no solo por su test: `git diff dev...HEAD
--stat` no toca `sql/stg`, `sql/mart`, `tramos.py`, `build_stg_step.py`,
`coherencia.py`, `business_rules.yaml` ni `tables_sigrid.yaml`.

---

## 5 · Verificación independiente de la campaña de mutación

La ficha **F-029** obliga a mirar dos veces cualquier cero. He hecho las tres
comprobaciones, no una.

**1 · Recálculo puro del alcance y del número de mutantes** (`harness.alcance` +
`harness.mutacion.generar_mutantes`, sin ejecutar la suite):

| Fichero | Líneas (informe / recalculadas) | Mutantes |
|---|---|---|
| `domain/extraccion.py` | 273 / **273** | 28 |
| `domain/perfil_carga.py` | 289 / **289** | 47 |
| `domain/tiemod.py` | 324 / **324** | 53 |
| `postgres/postgres_client.py` | 163 / **163** | 18 |
| `sigrid/bench_extraccion.py` | 206 / **206** | 19 |
| `sigrid/sigrid_api_client.py` | 43 / **43** | 2 |
| `main.py` | 250 / **250** | 22 |
| **Total** | **1.548 / 1.548** | **189** |

**189 mutantes recalculados = 189 declarados.** El alcance y el reparto por
fichero coinciden exactamente.

**2 · La prueba de control del cero.** Aquí el cero **no es de mutantes** (hay
189), así que la prueba de control de «cero mutantes» no aplica: lo que hay que
verificar es el cero de **supervivientes**, y eso solo se verifica reejecutando.

**3 · Reejecución completa por mi cuenta, con `--workers 1`**:

```
python -m harness.mutacion --feature F-011 --workers 1 --salida <fuera de progress/>
```

| Métrica | Implementer | **Mi reejecución** |
|---|---|---|
| Mutantes generados | 189 | **189** |
| Mutantes evaluados | 189 | **189** |
| Muertos | 189 | **189** |
| **Supervivientes** | 0 | **0** |
| Timeouts | 0 | **0** |
| Tiempo total | 808,4 s | 899,4 s |
| Muestreo | campaña completa | campaña completa |

**El cero es reproducible.** Recorridos los 189 mutantes uno a uno con un solo
worker, los 189 mueren; el recuento por veredicto de la traza da `189 muerto` y
ni un `superviviente`. El mismo `Origen del diff` (`30efd28f…`) y el mismo
alcance. La diferencia de tiempo (899,4 s frente a 808,4) es carga de máquina,
no de recuento.

Además, la traza sostiene el relato del §8.1 del implementer: los mutantes que
mueren son los **finos** —`<= 0` → `<= 1`, `== 1` → `== 2`, `filas[0]` →
`filas[1]`, `or` → `and`, decimales de formato—, que son exactamente los que
sobreviven a una suite que solo comprueba el camino feliz. No es un cero de
tests laxos.

**Sobre el `--workers 1`**: el informe del implementer (`impl_F-011.md` §8)
declara haberlo usado, y su §8.1 documenta cuatro campañas en serie con la
correspondencia entre cada test añadido y cada mutante muerto. Pero
**`progress/mutacion_F-011.md` NO registra los workers**: su cabecera dice
`python -m harness.mutacion --feature F-011` a secas. Es decir, del informe
generado por la herramienta **no se puede saber si la campaña fue paralela**,
que es justo el dato que F-029 obliga a comprobar. Lo he resuelto reejecutando;
queda como propuesta de mejora del arnés en §9.

**Supervivientes con análisis en `PENDIENTE`**: ninguno, porque no hay
supervivientes.

---

## 6 · Recorrido de `CHECKPOINTS.md`

| Checkpoint | Estado | Nota |
|---|---|---|
| **C1** · arnés completo y en verde | **[x]** | `bash harness/init.sh` ejecutado por mí hoy: **exit 0**, 798 tests, arnés v1.5.1. Los 10 documentos obligatorios existen. Único aviso: `ruff` 159, deuda previa declarada no bloqueante |
| **C2** · estado coherente | **[x] con reserva** | una sola feature `in_progress` (F-011, lo valida `init.sh`); rama `feature/F-011-carga-incremental` correcta. **Reserva**: la sección F-011 de `current.md` está **caducada** —dice «hace falta una firma del humano» y lista «T9, la firma» como pendiente cuando ya se firmó (commit `6125be3`)— → punto 2 de §8. `history.md` se escribe al cerrar, por definición |
| **C3** · arquitectura y convenciones | **[x]** | Los 3 módulos de dominio importan **solo stdlib** (`csv`, `re`, `dataclasses`, `pathlib`, `enum`): ni psycopg, ni click, ni infraestructura. El adaptador `bench_extraccion.py` vive en `infrastructure/` e importa el dominio (dirección correcta). **Primera línea con la ruta** en los 4 ficheros nuevos. **Sin `print()` de debug, sin TODO/FIXME**. Barrido de secretos **ejecutado por mí** sobre el diff (patrones: `password|passwd|pwd|secret|token|api_key|connectionstring` junto a `:`/`=`, base64 ≥ 40, GUID, IPv4): **limpio**; los únicos aciertos son rutas largas del propio texto de las specs, el falso positivo conocido de F-016. Semántica Sigrid: la feature no calcula negocio, no hay `amb`/`fas` ni importes que mezclar |
| **C3 bis** · documentos de fuera | **N/A justificado** | la rama **no añade ni modifica ningún fichero en `docs/referencia/`** (comprobado en `git diff dev...HEAD --stat`). No hay original PDF ni ofimático en el historial de la rama |
| **C4** · verificación real | **[x]** | Trazabilidad completa del bloque A y los transversales (§4); R9–R19 N/A **justificado por la puerta de R8**. Tests sin red ni BBDD, **con el método de comprobación escrito** (§4). Las verificaciones MANUAL están listadas con su **comando exacto** en `medicion_F-011.md` §7 y en `tasks.md` T7/T8-bis; en `current.md` aparecen **sin los comandos** → se arregla en el punto 2 de §8 |
| **C4 bis** · el rigor declarado se cumple | **[x]** | `rigor: critico` **declarado** en `features.json`. **Fase RED**: `impl_F-011.md` §4 trae **seis trazas reales pegadas** (T1–T5 y T21), con el comando exacto; la de T21 encontró un defecto de verdad (falso positivo del barrido de secretos), no un módulo ausente. **Cobertura**: `[OK] 100.0 % de 469 líneas cambiadas (469/469, umbral 80 %)`, línea impresa por `init.sh` en mi ejecución de hoy. **Mutación**: informe presente, generado por la herramienta, **totales recalculados y campaña reejecutada por mí** (§5). **Cero supervivientes**, ninguno en `PENDIENTE`. Sección **«Evidencias»** presente en `impl_F-011.md` §8 con los **cuatro** números (798 tests, 100 % de 469, 189/189/0, 8,2 s de suite) |
| **C4 ter** · rutas sensibles | **N/A justificado** | este repositorio no declara `harness/rutas_sensibles.json` (solo existe el `.ejemplo.json`); el propio `CHECKPOINTS.md` dice que sin declaración el bloque es N/A y no hay nada que justificar |
| **C5** · la sesión se cerró bien | **[ ] pendiente del commit de cierre** | `tasks.md` tiene **T9 en `[ ]` pese a estar decidida** y T10–T19 sin marcar como descartadas; `features.json` sigue `in_progress`. Sin ficheros temporales sospechosos: `git status` limpio (los `huella_*.csv` del árbol los cubre `.gitignore:27`). **Es la lista de §8** |

**Sobre el `[ ]` de C5.** Mi protocolo dice que un checkbox vacío es
`CHANGES_REQUESTED`. Lo dejo vacío **a propósito y a la vista**, y aun así
apruebo, con el mismo criterio con el que se cerró F-024
(`review_F-024_cierre.md` §8): **T7, T8-bis y T9 las ejecuta el humano, no el
implementer**, así que ningún commit de tarea podía marcarlas antes de esta
review; y las tareas T10–T19 no están «sin hacer», están **canceladas por una
puerta que la propia spec definió**. Lo que afirmo sin matices: **si se marca
`done` sin el commit de cierre del punto 1 de §8, C5 queda violado y el cierre
es ilegítimo.**

---

## 7 · Desviaciones del diseño y observaciones (ninguna bloqueante)

Las cuatro desviaciones declaradas en `impl_F-011.md` §3 están justificadas y
las doy por buenas: el batch de vuelta en `fetch_perfil_carga` (lo exige R8),
`leer_sql()` como puerta pública (sin ella el validador de R23 sería
decorativo, y hay test **sobre el cliente real con control negativo**),
`filas_avanzadas` en `veredicto_tiemod` (R7 pide «cuántas filas cambiaron», y
con dos agregados no se sabe) y el tercer método de lectura que eso obliga a
añadir, frente a los «dos» que anunciaba `design.md` §3.

Dos observaciones para el acta, ninguna cambia el veredicto:

1. **El CSV de la huella vive en el dominio, y el precedente que se cita dice
   lo contrario.** `impl_F-011.md` §3.4 justifica poner `escribir_csv` en
   `etl_sigrid/domain/tiemod.py` «como `Metrica`/`escribir_csv` en
   `fingerprint.py`». Pero `fingerprint.py` está en
   **`etl_sigrid/infrastructure/postgres/`** (y llega a importar `psycopg`):
   el precedente sostiene justo lo contrario, que ese código es de
   infraestructura. C3 se cumple **literalmente** —`tiemod.py` no importa nada
   de infraestructura, solo `csv` y `pathlib` de la stdlib— así que no bloqueo;
   pero el dominio está haciendo E/S de fichero y la justificación escrita es
   inexacta. Si el bloque A crece, ese `escribir_csv`/`leer_csv` es candidato a
   mudarse a infraestructura.
2. **Un desajuste menor de redondeo en la medición.** `§1` da a la ingesta una
   media de **32,9 min** (las tres cargas dan 32,97) y `§5` reparte un total de
   **1.966,2 s = 32,77 min**. Son 12 segundos de diferencia, seguramente por
   qué se cuenta como ingesta en cada tabla. **No mueve nada** —el techo son
   2,25 min con cualquiera de los dos— pero conviene saber que las dos cifras
   no salen del mismo agregado.

Y un apunte sobre el §3.1 de la medición: dice que el diccionario «describe
entidades lógicas» y que por eso `tiemod` aparecía «sobre todo en tablas
Propiedades de `con`». La explicación es imprecisa —el diccionario **sí** lista
las columnas físicas tabla por tabla, y **no** le atribuye `tiemod` a
`obrparpre`—. Lo que falló fue la **lectura agregada** del recuento de 232
filas que hizo la spec en §0.2, no el diccionario. El fondo es correcto; la
atribución de la culpa, no.

---

## 8 · Apuntes de cierre OBLIGATORIOS antes de marcar `done`

Los tres primeros son bookkeeping; el cuarto es la condición de mi aprobación.

1. **`specs/F-011-carga-incremental/tasks.md` no refleja lo ocurrido.** Hoy un
   lector concluye que la feature sigue esperando una firma que ya existe.
   Hay que, en un commit de cierre:
   - **T9 → `[x]`** con su fecha (2026-08-20) y puntero a
     `progress/medicion_F-011.md` §6.2 y al commit `6125be3`.
   - **T10–T19 → marcadas como DESCARTADAS por la puerta de R8**, con el mismo
     tratamiento que ya tiene T20 (`~~HUECO DELIBERADO~~`), citando DA-4 y
     DA-7. No como `[ ]` sueltas: un `[ ]` sin explicación es indistinguible de
     trabajo pendiente.
   - **T7 y T8-bis**: dejarlas explícitamente como **MANUAL pendiente del
     humano**, con lo ya hecho anotado (T7 está parcialmente cumplida y así lo
     dice su propio texto).
   **Sin esto, C5 queda incumplido.**
2. **`progress/current.md` está caducado.** Su sección F-011 dice «La feature
   está en su parada: hace falta una firma del humano» y lista «1. **T9, la
   firma** (humano)» como lo primero pendiente. **Ya se firmó**: el commit
   `6125be3` tocó solo `decisiones_abiertas.md` y `medicion_F-011.md`, y se
   dejó `current.md` atrás. Refrescarla con el estado real (bloque A entregado,
   bloque B descartado, trabajo trasladado a F-025) y, de paso, **poner los
   comandos exactos** de las tres verificaciones MANUAL que quedan, que hoy
   solo están en `medicion_F-011.md` §7 y en `tasks.md` (lo pide C4).
3. **`progress/history.md`**: resumen de F-011 al pasar a `done` (C2), y
   `harness/features.json` a **`done`** (C5). En el resumen conviene que quede
   escrito que **cierra con el bloque A entregado y el B descartado por su
   propia puerta**, para que dentro de seis meses nadie lo lea como una feature
   a medias.
4. **Que el descarte no vuelva por la puerta de atrás.** El §6.1 de la medición
   es hoy el único sitio donde vive el «no al cursor por solo altas», y
   `medicion_F-011.md` es un documento de una feature cerrada. **Clavarlo en
   `progress/decisiones_abiertas.md`** —que es donde miran las sesiones
   futuras, como se hizo con D9 y D11— con esta forma o equivalente:
   - *Decisión*: la ingesta incremental de Sigrid por watermark **no es
     posible** (no existe marca de modificación en las 24 tablas que son el
     93 % del tiempo) y el cursor por «solo altas» **queda descartado**.
   - *Motivo que hay que recordar*: `obrparpre.planif` —la planificación
     temporal que alimenta `stg.plan_mensual`— **se edita sin crear filas**, así
     que un cursor por `ide` serviría un plan viejo en silencio.
   - *Qué lo reabriría*: que Sigrid añada una marca de modificación a las
     tablas de detalle, o que Negocio acepte **por escrito** la pérdida.
   - *Dónde está el tiempo de verdad*: `build_stg`, 110,7 min de 165,2
     (67,0 %) → **F-025**.

Y dos recordatorios no bloqueantes:

- **T8-bis** sigue pendiente: avisar al dueño de `sigrid-api` de que su
  documento da 1.000 filas y 120 s. Verificado que **este proyecto no lo ha
  tocado**: la rama no incluye ningún cambio en `azure-apps/`.
- **`config/tables_sigrid.yaml` miente en 17 entradas** (declara
  `incremental_column: tiemod` en tablas que no la tienen). Es inerte hoy y el
  implementer hizo bien en **no** tocarlo estando la feature en su parada, pero
  merece **ficha propia de backlog**: es exactamente la documentación
  equivocada que sostuvo una premisa falsa durante meses, y ahora hay medición
  para corregirla con confianza.

---

## 9 · Automejora (propuesta, no aplicada)

Dos cosas que esta feature deja a la vista. Si se aceptan, hay que portarlas a
`arnes-base` en el mismo trabajo.

1. **El informe de mutación no registra con cuántos workers se generó.**
   `harness/mutacion.py::escribir_informe` escribe «Generado por `python -m
   harness.mutacion --feature F-XXX`» sin los workers, aunque la campaña haya
   corrido en paralelo. Con F-029 abierta —el modo paralelo declara muertos
   mutantes vivos— eso convierte al reviewer en adivino: el dato que decide si
   el informe es fiable **no está en el informe**. **Propuesta**: que
   `InformeMutacion` lleve el número de workers y que `escribir_informe` lo
   imprima en la línea de cabecera, junto al modo (secuencial/paralelo). Es
   barato y elimina una reejecución de 13 minutos por review.
2. **`CHECKPOINTS.md` C5 no contempla las tareas canceladas por una puerta.**
   Su redacción («todas las tareas `[x]`») solo admite hecho o no hecho. Una
   spec que condiciona un bloque entero a una medición —que es *buena*
   ingeniería y lo que este arnés predica al decir «medir, no optimizar»—
   termina necesariamente con tareas que **no deben hacerse**, y el reviewer se
   queda entre aprobar con `[ ]` o rechazar un trabajo terminado.
   **Propuesta**: reconocer en C5 el estado **`[—] descartada por <puerta>`**,
   exigiendo que la marca cite la decisión y el documento donde se firmó, y que
   el reviewer la liste expresamente en su informe. Es hermana de la propuesta
   1 de `review_F-024_cierre.md` §9 (las tareas MANUAL que cierra el humano) y
   convendría resolverlas juntas.
3. **F-029 tiene un cuarto efecto que su ficha no recoge: el agente que espera
   su propia campaña.** Me ha pasado hoy en esta review. Lancé la reejecución
   en segundo plano y **terminé el turno esperando la notificación**; al
   cerrarse el turno la notificación ya no podía llegarme, la campaña siguió
   corriendo **huérfana** y durante ~10 minutos hubo un mutante aplicado en
   `etl_sigrid/domain/tiemod.py`. Cualquiera que hubiera pasado por el
   repositorio en esa ventana habría visto tests en rojo ajenos a su trabajo,
   y quien intentara «arreglarlo» restaurando el fichero **habría contaminado
   el recuento de la campaña**. El coordinador hizo lo correcto: poner un
   vigía y **no tocar el árbol**. La pieza 4 del encargo de la 1.5.3 —que
   `init.sh` reconozca una campaña en curso— lo cubre, pero conviene que en la
   ficha de F-029 quede escrito que **el disparador puede ser el propio
   agente**, no solo una caída: basta con delegar la campaña al fondo y
   terminar el turno. Corolario práctico mientras eso no exista: **quien lanza
   una campaña no cierra el turno hasta recogerla**, o la lanza en primer
   plano aunque tarde.

---

## 10 · Lo que NO he podido verificar (y por qué no cambia el veredicto)

Por **D11** (la IP pública del puesto rota cada pocos minutos y las reglas de
firewall no aguantan) y por la instrucción de no tocar Azure:

| Sin verificar | Por qué no cambia el veredicto |
|---|---|
| Los logs de `ContainerAppConsoleLogs_CL` de las tres cargas | Corroborados por dos vías: los totales coinciden con lo que `current.md` registró en su día, y las cifras cuadran internamente hasta el decimal (§1.1, §1.2) |
| La lectura del catálogo de Sigrid (`INFORMATION_SCHEMA.COLUMNS`) | Corroborada columna a columna contra `azure-apps/sigrid_tablas.md`, que sí está en local (§1.5) |
| `perfil-carga` y `diagnostico-tiemod` contra el datamart real | Son las verificaciones MANUAL del humano; el camino de error de `perfil-carga` sí se ejercitó en real (salida 2) |
| `bench-sigrid` (R4, R5-bis) | Va contra producción de Sigrid y la spec lo reserva al humano (T7). **No afecta a la decisión**: aunque la extracción fuera instantánea, el techo son 32,9 min de 165,2 |

Ninguna de estas cuatro puede hacer aparecer una columna que no existe en el
origen, que es lo que decide la feature.
