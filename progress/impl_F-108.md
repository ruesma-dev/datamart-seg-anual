# F-108 · Informe del implementer — claves alternativas en el diccionario y en `check-unicidad`

Rama `feature/F-108-claves-alternativas` (desde `main` 323910f). Spec aprobada
con D1-D5 (`progress/spec_F-108.md`). Rigor `estandar`. Un commit por tarea
(`F-108 T1` ... `F-108 T9`); `azure-apps` con commit LOCAL `ae8edd3`, sin push.

## Qué cambió

| Fichero | Cambio |
|---|---|
| `etl_sigrid/domain/diccionario.py` | `Ficha.claves_alternativas` (tupla de tuplas, `()` por defecto); `_validar_claves_alternativas` (R2: funcion, ficha sin columnas, columna no documentada, clave vacia, columna repetida, igual a `clave_negocio` o a otra alternativa como conjunto); tercer caso de `_es_unica_por` (`(col,) in claves_alternativas`); `_sus_claves` para el mensaje de `_validar_cardinalidad` (`su clave es [...]; claves alternativas: [[...]]`) |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | `claves_alternativas` en `CLAVES_FICHA`; `_claves_alternativas` (no reutiliza `_tupla`): solo acepta lista no vacia de listas no vacias de textos; cualquier otra forma, error `R1` con la ficha y `[[clave_obra]]` |
| `etl_sigrid/infrastructure/postgres/unicidad_sql.py` | `ConsultaUnicidad.tipo_clave = "negocio"` y propiedad `rotulo`; `_consulta(ficha, clave, tipo_clave)`; una consulta por alternativa (aunque la de negocio se salte) con `WHERE c IS NOT NULL AND ...` en la consulta y en el detalle; veredictos OK/KO/NO COMPROBADO rotulados «clave alternativa (...)». El texto de la de negocio sale byte a byte igual |
| `main.py` (`check_unicidad_cmd`) | cabecera `N comprobacion(es) (K de clave alternativa), S saltado(s)`; `--dry-run` rotula `clave alternativa: (...)`; un solo «no existe» por objeto (sus demas consultas ni se lanzan ni se cuentan) |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | `_ficha_json` publica `claves_alternativas` solo si las hay; sin DDL, la tupla sigue con 14 campos |
| `config/diccionario/maestro.yaml`, `personal.yaml`, `stg.yaml` | seis `claves_alternativas` (R20 + R22 con D3) y la frase «clave alternativa ... la vigila `check-unicidad`» en el significado de cada columna clave |
| `config/diccionario/compras.yaml` | las cinco `clave_obra -> maestro.obras.clave_obra` a `N:1`, `porque` de `design.md` §7 |
| `config/diccionario/00_global.yaml` | `version: 33` y cabecera de F-108 |
| `tests/test_f108_claves_alternativas.py` (nuevo) | 62 tests, R1-R22 y R24, sin red ni BBDD |
| `tests/test_f102_obra_principal.py` | `test_f102_r22_la_relacion_por_clave_esta_declarada` exige `N:1` y «clave alternativa» (R23) |
| `docs/ARCHITECTURE.md` | parrafo «Claves alternativas (F-108)» en «El datamart se explica solo» (R24) |
| `../azure-apps/datamart_seg_anual.md` | fila de `_meta.diccionario`: el JSONB puede traer `claves_alternativas` (R24), commit local `ae8edd3` |

## Decisiones de diseño y desviaciones

1. **Version 33, no 31 (D5, indicado por el lider).** `main` ya estaba en la 32
   (F-095 y sus cifras). `test_f108_r19_la_version_sube_a_33` exige `>= 33` y la
   cabecera `version 33 (F-108`.
2. **R23, mitad F-107 ya hecha.** `test_f107_r4_la_version_sube_a_30` ya exigia
   `>= 30` en `main` (lo ajusto F-095): no se toca.
3. **Cargador mas estricto que el minimo de R2**: tambien rechaza `[]` (lista
   sin claves) y columnas que no son texto (`[[[clave_obra]]]`) o vacias; todas
   con el mismo mensaje `R1`. Una clave vacia construida a mano en el dominio la
   caza `validar` (R2).
4. **`rotulo` en `ConsultaUnicidad`** (no estaba en el design): una sola fuente
   para «clave (...)» / «clave alternativa (...)» en los veredictos. Para la de
   negocio, `interpretar_resultado` conserva literalmente su texto de hoy (lo
   fijan los tests y supervivientes de F-006); solo `veredicto_no_comprobado` lo
   usa en los dos tipos, y para la de negocio produce el mismo texto que antes.
5. **Filas con NULL (D1)**: el KO de una alternativa lo dice («sin contar las que
   la tienen a NULL»). La de negocio sigue agrupando los NULL.
6. **D2**: una alternativa rota suma en «con la clave rota» y sale con 1.
7. **R14**: el recuento «sin contradiccion» descuenta las consultas omitidas de
   un objeto inexistente, para que el resumen no las cuente como OK.
8. **Frases en las fichas**: se añaden al final del `significado` existente, sin
   reescribirlo; en las compuestas se anota en las dos columnas.

## Fase RED (obligatoria, nivel `estandar`)

Tests escritos antes que el codigo (commit `54d0a34`, `F-108 T1`). Comando y
salida real (`--tb=line`, lineas del fichero de tests; resumen agrupado):

```
$ python -m pytest tests/test_f108_claves_alternativas.py -q -p no:cacheprovider --tb=line
...
tests\test_f108_claves_alternativas.py:105: TypeError: Ficha.__init__() got an unexpected keyword argument 'claves_alternativas'      (x26: R3-R9, R11-R13, R18)
tests\test_f108_claves_alternativas.py:243: AttributeError: 'Ficha' object has no attribute 'claves_alternativas'                  (R1)
tests\test_f108_claves_alternativas.py:271: AssertionError: y ensena la forma correcta                                              (x7: R2)
    + where '`claves_alternativas` no es una clave admitida en la ficha `mart.obras`: avisos, capa, clave_negocio, ...'
tests\test_f108_claves_alternativas.py:453: AttributeError: 'ConsultaUnicidad' object has no attribute 'tipo_clave'                 (R10)
tests\test_f108_claves_alternativas.py:577: AssertionError: assert ('maestro.obras', 'alternativa', ('clave_obra',)) in []          (R12, CLI)
tests\test_f108_claves_alternativas.py:595: assert '?    personal.recursos: NO COMPROBADO' in 'Comprobacion de unicidad · solo la superficie de consumo\n  75 objeto(s) a comprobar, 97 saltado(s)...'   (R13, CLI)
tests\test_f108_claves_alternativas.py:604: assert 0 == 1                                                                           (R14)
tests\test_f108_claves_alternativas.py:621: AssertionError: assert '-- maestro.obras  clave alternativa: (clave_obra)' in 'Comprobacion de unicidad · ... 75 objeto(s) a comprobar, ...'   (R15)
tests\test_f108_claves_alternativas.py:698: AssertionError: assert ('maestro.obras', ('clave_obra',)) in set()                     (R17)
tests\test_f108_claves_alternativas.py:736: assert 32 >= 33                                                                         (R19)
tests\test_f108_claves_alternativas.py:767: AssertionError: assert 'N:N' == 'N:1'                                                   (x5: R21)
tests\test_f108_claves_alternativas.py:809: AssertionError: assert 'claves_alternativas' in ' (F-006)\n\nEl datamart publica **su propia semántica ...'   (R24)
tests\test_f108_claves_alternativas.py:818: AssertionError: assert ('claves_alternativas' in '<!-- datamart_seg_anual.md -->...')   (R24)
58 failed, 4 passed in 17.39s
```

Los 4 que pasaban en RED son los que deben pasar sin la feature: los dos
controles (`r6_sin_alternativa_el_mismo_n_1_sigue_siendo_error`,
`r8_sin_alternativas_el_mensaje_es_el_de_hoy`) y las dos guardas de la opcion B
(`r16_*`: `run-all` no ejecuta `check-unicidad` y ningun SQL crea un indice
unico sobre `clave_obra`/`clave_recurso`), que ya se cumplian por construccion.

Tras cada tarea, en verde (salidas reales):

- T2 `-k "r3 or r4 or r5 or r6 or r7 or r8"`: `17 passed`; F-006 formato/relaciones/supervivientes: `170 passed`.
- T3 `-k "r1_ or r2_"`: `9 passed`; `-k "f006 and (carga or formato or fichas)"`: `1027 passed, 197 skipped`.
- T4 R9-R13: `11 passed`; F-006 unicidad/constantes/supervivientes/mensajes/dataclasses/comandos: `242 passed, 3 skipped`.
- T5-T7: `test_f108` + F-102 + F-107 + `test_f006_fichas` + `test_f006_relaciones`: `897 passed, 197 skipped` (solo faltaban los dos de R24, T9).
- T9: `tests/test_f108_claves_alternativas.py`: `62 passed in 17.28s`.
- T10: tres aserciones nuevas (recuento «sin contradiccion» en R12, R13 y R14)
  matan los cuatro supervivientes de `main.py`; cada una comprobada con el
  mutante aplicado a mano (`1 failed`) y sin él (`1 passed`).

`python main.py check-unicidad --dry-run` (sin conexion), cabecera y rotulos reales:

```
  81 comprobacion(es) (6 de clave alternativa), 97 saltado(s)
-- maestro.centros_coste  clave alternativa: (empresa, codigo_centro)
-- maestro.cuentas_analiticas  clave alternativa: (empresa_id, codigo_cuenta)
-- maestro.obras  clave alternativa: (clave_obra)
-- maestro.v_obra_fichas  clave alternativa: (clave_obra)
-- personal.recursos  clave alternativa: (clave_recurso)
-- stg.obras  clave alternativa: (codigo_obra)
-- 81 consulta(s). No se ha abierto ninguna conexion.
```

## Fuera del alcance

- Servir las claves al agente en `mcp-bbdd` (D4): hoy las ignora sin romperse.
- H1 (partidas no unicas por obra y codigo): F-109, no se declara nada.
- Ningun SQL tocado; ningun indice unico (opcion B).

## Verificaciones MANUAL pendientes (humano)

- **T11 / R25**: `python main.py check-unicidad` y `--todos` con su `.env`
  (solo lectura). Esperado `OK` en las seis alternativas (922, 2.619, 922,
  184.234, 804, 584 filas) y las de negocio como antes. Despues
  `python main.py publicar-diccionario` (**version 33**), escritura que autoriza
  el humano.

## Campaña de mutación (T10)

`python -m harness.mutacion --feature F-108 --base main --workers 2 --timeout 1800`
(detalle: `progress/mutacion_F-108.md`). Un primer intento con los 4 workers por
defecto salió con código 3, «LÍNEA BASE SIN TERMINAR»: la suite limpia no cupo
en los 600 s de holgura con 4 suites compitiendo (línea base medida después:
1.063 y 1.083 s por worker). Se relanzó como indica la propia herramienta, con 2
workers y el timeout fijado a mano; `harness/rigor.json` no se toca.

- 37 mutantes generados, 20 evaluados (muestreo `estandar`, semilla 20260820):
  **15 muertos, 5 supervivientes**, 0 timeouts, 8.205,7 s.
- 4 supervivientes de `main.py`, todos en el recuento «sin contradiccion» del
  resumen (`omitidas = 1`, `omitidas -= 1`, `+ fallos`, `+ sin_comprobar`),
  eran un **hueco real**: ningún test, ni de F-006 ni de F-108, fijaba ese
  número. Se cierran con aserciones en `test_f108_r12`/`r13`/`r14` (commits
  `32fd20b`, `3afb1ae` y `7ea69d8`).
- 1 **equivalente**: `ensure_ascii=False -> True` en `_ficha_json`. La línea es
  de F-006, solo reformateada; el `JSONB` que guarda PostgreSQL es el mismo
  valor con o sin escapes `\u`.

## Aviso para el merge

`main` avanzo tras el punto de partida (4586916, «Merge de la ficha F-110»):
solo toca `harness/features.json` y `BACKLOG.md`. Esta rama cambia en
`features.json` unicamente el `status` de F-108; `BACKLOG.md` se regenera.

## Evidencias

| Evidencia | Valor medido |
|---|---|
| Resultado real de `bash harness/init.sh` (T12, 2026-09-25 ~17:25 UTC, HEAD `7ea69d8`) | **`ENTORNO LISTO. Puedes trabajar.`**, código 0 |
| Tests ejecutados (suite completa, dentro de `init.sh`) | **5.486 passed, 203 skipped**, 0 fallos |
| Tests de F-108 (`tests/test_f108_claves_alternativas.py`) | **62 passed in 14.54s** |
| Cobertura de las líneas cambiadas | `PUERTA COBERTURA: 95.1% de 1106 líneas cambiadas cubiertas (1052/1106, umbral 80%, nivel estandar)` |
| Mutantes | 37 generados, 20 evaluados: **15 muertos, 5 supervivientes** (4 huecos reales cerrados con test después de la campaña, 1 equivalente), 0 timeouts (`progress/mutacion_F-108.md`) |
| Tiempo de la suite | **1.901,38 s (31 min 41 s)** con cobertura, en `init.sh`; la campaña de mutación, 8.205,7 s con 2 workers |
| Puerta de tamaño | `requirements 136/150, design 230/250, impl 143/220` |

La campaña midió el HEAD `2158cc8`: los cuatro supervivientes de `main.py` se
cerraron después con tests (`32fd20b`, `3afb1ae`, `7ea69d8`) y cada muerte se
comprobó a mano con el mutante aplicado. No se ha relanzado la campaña entera
(2 h 17 min).
