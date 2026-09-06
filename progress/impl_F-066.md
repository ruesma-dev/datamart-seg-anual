<!-- progress/impl_F-066.md -->
# F-066 · Ingerir de Sigrid los raw que faltan — Informe de implementación

**T1-T12 y T16 hechas. T13, T14 y T15 sin tocar**, y no se pueden tocar sin el
humano: T13 construye y despliega la imagen en Azure, T14 depende de que esa
nocturna haya corrido y T15 es del líder. **No se ha ejecutado nada de `infra/`
ni `az`.** Lo que hace falta para T13, al final.

La ingesta pasa de **31 a 56 tablas**. Desde el puesto se ingirieron las 17 de
menos de 100.000 filas; las 8 grandes esperan a la nocturna, por instrucción.

## Lo que cambió, tarea a tarea

| Tarea | Qué toca | Resultado |
|---|---|---|
| T1 | `tests/test_f066_ingesta_raw.py` (nuevo) | fase RED: 281 failed, 29 passed |
| T2 | `tests/test_f066_recuentos.py` (nuevo) | fase RED: `ModuleNotFoundError` |
| T3 | `etl_sigrid/domain/recuentos.py` (nuevo), `main.py` | 28 passed |
| T4 | `tables_sigrid.yaml`: bloque PERSONAL | 4 tablas, 339.572 filas |
| T5 | `tables_sigrid.yaml`: bloque CONTABILIDAD | 4 tablas, 3.681.471 filas |
| T6 | `tables_sigrid.yaml`: bloque COMPRAS/PROVEEDOR | 17 tablas, 1.307.798 filas |
| T7 | `dcf` recupera `pagtex` y `pagfor`; su ficha, de 23 a 21 | |
| T8 | `raw.yaml` (+25 fichas), `00_global.yaml`, `objetos_pendientes.yaml` | biyección 56/56 |
| T9 | ingesta real desde el puesto | 17 tablas, 136.536 filas |
| T10 | `docs/ARCHITECTURE.md` | sección nueva en «Acceso a datos» |
| T11 | `azure-apps/datamart_seg_anual.md` | commit `a900682` en ESE repositorio |
| T12 | cobertura y campaña de mutación | ver «Evidencias» |
| T16 | `bash harness/init.sh` | verde |

Arrastre inevitable de T8: el inventario del diccionario pasa de 105 a **130
objetos**, y tres tests vigilan que ese número no envejezca, así que se
corrigieron `progress/current.md`, `specs/F-006-mcp-azure/design.md` y
`design_detalle.md`.

## Fase RED (rigor crítico)

### T1 · los tests del YAML y de las fichas

`python -m pytest tests/test_f066_ingesta_raw.py -q -p no:cacheprovider`,
**antes** de tocar ningún YAML:

```
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF [ 23%]
...
281 failed, 29 passed in 5.08s
```

```
___________ test_f066_r1_las_veinticinco_tablas_estan_dadas_de_alta ___________
    def test_f066_r1_las_veinticinco_tablas_estan_dadas_de_alta() -> None:
        faltan = sorted(set(NUEVAS) - set(_ingesta()))
>       assert faltan == [], f"no se ingieren todavía: {faltan}"
E       AssertionError: no se ingieren todavía: ['apa', 'apu', 'asi', 'auxefp',
E       'auxpag', 'auxpronat', 'conact', 'conest', 'confir', 'ctrrec', 'cua',
E       'dcarec', 'dcfrec', 'dco', 'dcopro', 'dcorec', 'deffir', 'dnc',
E       'dncpro', 'emp', 'hmo', 'hmores', 'prvcer', 'prvobrpag', 'res']

___________ test_f066_r1_la_ingesta_pasa_a_cincuenta_y_seis_tablas ____________
>       assert len(_ingesta()) == TOTAL_TABLAS
E       AssertionError: assert 31 == 56
```

### T2 · los tests del comando

`python -m pytest tests/test_f066_recuentos.py -q -p no:cacheprovider`, **antes**
de escribir el dominio:

```
________________ ERROR collecting tests/test_f066_recuentos.py ________________
tests\test_f066_recuentos.py:29: in <module>
    from etl_sigrid.domain.recuentos import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.recuentos'
=========================== short test summary info ===========================
ERROR tests/test_f066_recuentos.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.65s
```

### Los tres tests escritos después de un hallazgo, en rojo antes de aceptarlos

No nacieron antes que el código, así que su fase RED se hizo al revés:
**reintroduciendo el defecto** y comprobando que muerden.

```
# guardián de duplicados, con el YAML duplicado devuelto a su sitio
tests\test_f066_ingesta_raw.py:474: AssertionError
E         Left contains 17 more items, first extra item: 'auxefp'
FAILED ...::test_f066_r1_ninguna_tabla_esta_declarada_dos_veces
--- restaurado ---  312 passed

# los dos supervivientes, con cada mutación aplicada a mano en main.py
--- mutante 17 (max_rows=2) ---
FAILED ...::test_f066_r18_el_count_no_pide_a_sigrid_mas_de_una_fila
--- mutante 18 (err=False) ---
E        +  where '' = <Result SystemExit(1)>.stderr
FAILED ...::test_f066_r15_el_aviso_de_una_tabla_sin_medir_no_ensucia_el_informe
--- restaurado ---  30 passed
```

## Decisiones, y las tres que se apartan de la letra de la spec

Todo lo que sigue se **midió contra Sigrid el 2026-09-06** en solo lectura
(`INFORMATION_SCHEMA.COLUMNS` y `COUNT(*)`). Detalle en `mediciones.md` §1.

1. **`hmo`, `cua` y `asi` no excluyen ninguna columna.** R7 dice «`tex` en las
   demás», pero **no tienen ninguna columna de texto ni binario ilimitado**. La
   primera frase de R7 pide la lista vacía, y `tasks.md` lo confirma (T4 solo
   manda `tex` en `hmores`; T5, en `apu` y `apa`).
2. **Las 17 de compras llevan la lista estándar de 13 aunque casi ninguna tenga
   las trece**, que es lo que manda R7 y la convención del YAML. Consecuencia
   asumida: fichas que dicen «No se traen 13» excluyendo poco real.
3. **Cinco columnas ilimitadas entran** porque no están en la lista estándar:
   `dncpro.com`, `dncpro.medfijdis`, `auxpag.formul`, `auxefp.est` y
   `prvobrpag.texF`. Medidas antes de decidir: ninguna pesa (la mayor, `com`,
   informada en 1.039 filas de 286.432, 38 bytes de media).

Y dos de estructura: **`_get_api()` en `main.py`**, gemelo de `_get_pg()`, sin
el cual no hay forma de doblar la puerta a Sigrid en un test sin tocar la red;
y **`formatear` en el dominio**, con un campo `recuentos` además de las cuatro
listas de `design.md` §4 —que están las cuatro, con su tipo—, porque R15 pide
una línea por tabla y R16 el orden del YAML.

## El fallo que cazó el comando nuevo el día que nació

`check-raw-recuentos`, en su primera ejecución real contra Azure, imprimió **73
líneas para 56 tablas**: el generador del bloque de compras se ejecutó dos veces
por un despiste mío y el YAML quedó con **17 entradas repetidas**. La nocturna
las habría ingerido dos veces cada noche, en silencio y pagándolo en créditos.

Lo que importa no es el despiste: es **por qué ninguno de los 310 tests lo vio**.
Todos leen la ingesta a través de un `dict` indexado por `source_table`, y un
diccionario **colapsa los duplicados**. Una vista que deduplica no puede
comprobar unicidad. Se añadieron dos comprobaciones que leen la **lista**.

## Un test ajeno que invalida campañas, medido

`tests/test_f024_dominio.py::test_f024_r1_batch_id_tiene_forma_y_es_unico` es
**aleatorio por construcción**: genera 500 `batch_id` con sufijo de 3 bytes
(16.777.216 valores) y exige 500 distintos. Medido aquí, 3.000 repeticiones:
**25 lotes con un repetido, 0,833 %**, contra el 0,741 % de la paradoja del
cumpleaños. Con 24 pasadas de la suite en una campaña, salta el **18 %** de las
veces, y eso es lo que dejó la segunda campaña marcada como NO VÁLIDA.

**ARREGLADO el 2026-09-06, tras el review** (`progress/impl_F-066_correcciones.md`).
El líder decidió arreglarlo y no excluirlo: el defecto estaba en el test —afirma
una unicidad que el código no promete— y no en el `batch_id`, así que
`etl_sigrid/domain/` no se tocó. El test comprueba ahora la forma de los 500 y
que el espacio de sufijos es grande de verdad; remedido, **0 fallos en 3.000
pasadas**. **La campaña se repitió entera y salió VÁLIDA**: 23 mutantes, 22
muertos, 1 superviviente (el equivalente firmado), 0 sin veredicto, 2.072,2 s.
Lo que sigue debajo describe el estado ANTES de esa corrección.

## Verificaciones MANUAL pendientes

* **T13** · construir y desplegar la imagen, y esperar la primera nocturna.
* **T14** · tras ella, `check-raw-recuentos` con código 0 y
  `check-diccionario` sin objetos sin ficha.
* **T15** · **HECHA** por el líder el 2026-09-06 (commit `26ce092`).

Las cinco, con su **comando literal**, en `progress/current.md` § «F-066 · LAS
VERIFICACIONES `MANUAL (humano)`».

## Qué necesita T13

1. **Construir y publicar la imagen** con tag fechado y **comprobar que el job
   apunta a ella**: la nocturna corrió diez días con una imagen del 18-08 sin
   que nadie lo notara, así que el repositorio en verde no prueba nada.
2. **Anotar los créditos antes** (`cpu_credits_remaining`) y el SKU, hoy B2s.
3. **Dejar correr la nocturna completa.** Cargará las 8 grandes (5.192.305
   filas) y **recargará `dcf`**, que es lo único que crea sus columnas `pagtex`
   y `pagfor`: hoy `raw.dcf` tiene las filas pero no las dos columnas.
4. **Rellenar `mediciones.md` §3 y §4** y ejecutar T14.

`ingest_raw` crece un **26 % en filas**; la extrapolación de lo medido da 10-15
min más. Si pasa de 45 min, F-065 tiene que verlo.

## Lo que queda FUERA, a propósito

* **`stg` y `mart`**: son F-057, F-056, F-055 y F-067. Aquí solo `raw`.
* **Revocar el `SELECT` del MCP sobre `raw.emp` y `raw.res`.** Es lo que más me
  preocupa de esta entrega y **no es decisión de este repositorio**: hoy esas
  dos tablas, con DNI, Seguridad Social, cuenta bancaria y domicilio, son
  legibles enteras por cualquier agente conectado al MCP. La spec lo deja fuera
  (§7) y la decisión del humano fue traerlas enteras **y declararlo**, que es lo
  que hacen sus fichas, `docs/ARCHITECTURE.md` y `azure-apps/`.
* **`concam`** (1,5 M filas de auditoría): no se ingiere. Si F-067 la necesita,
  entra con `where: tip = 15`.

## Evidencias

| Evidencia | Valor | De dónde sale |
|---|---|---|
| Tests ejecutados | **3.868 passed, 159 skipped**, 0 fallos | `bash harness/init.sh` |
| Tiempo de la suite | **572,42 s** (con medición de cobertura) | ídem |
| Tests propios de la feature | **342** (312 + 30) | los dos ficheros nuevos |
| Cobertura de líneas cambiadas | **92,5 %** (662/716, umbral 80, nivel crítico) | `PUERTA COBERTURA` |
| Mutantes generados / evaluados | **23 / 23** | `progress/mutacion_F-066.md` |
| Muertos / supervivientes / timeouts | **22 / 1 / 0**, 0 sin veredicto | ídem, HEAD `d8c73b8` |
| Tiempo de la campaña | **2.072,2 s** en serie, campaña **VÁLIDA** (3.ª pasada) | ídem |
| Ingesta desde el puesto | **17 tablas, 136.536 filas**, ~37 s de datos | `mediciones.md` §2 |
| Puerta de tamaño | requirements 128/150, design 218/250 | `PUERTA TAMAÑO` |

**El superviviente que queda es `bold=True -> bold=False`** en el título del
comando: **mutante equivalente**, no cambia ni una letra del texto ni el código
de salida y `CliRunner` invoca sin color, así que cazarlo exigiría afirmar sobre
secuencias ANSI y no sobre comportamiento. **Firmado por el humano el 2026-09-06
a las 20:45 UTC** («firmo»), registrado en la ficha de `harness/features.json`
(commit `5564975`) y reproducido por el reviewer.

**Los otros dos supervivientes de la primera pasada eran huecos reales y están
muertos**: `max_rows=1` (cuántas filas se le piden a Sigrid, que corta por filas
y por tiempo) y `err=True` (el aviso de tabla no medida se colaba en el informe
de la salida estándar). Los dos se verificaron además a mano.

**La 2.ª pasada la marcó el arnés CAMPAÑA NO VÁLIDA** por el test flaky de
F-024; arreglado ese test, la **3.ª pasada salió válida** y es la que valen
estas cifras. Detalle y comando exacto (`--base d1f56aa`) en
`progress/mutacion_F-066.md`; la 1.ª, en
`progress/mutacion_F-066_primera_pasada.md`.
