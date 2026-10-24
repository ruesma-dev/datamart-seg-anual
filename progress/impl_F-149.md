<!-- progress/impl_F-149.md -->
# F-149 · Informe del implementer · lo que sirve el MCP no nombra reglas que no se publican

- Rama `feature/F-149-mcp-sin-reglas-no-publicadas` (desde `main` en `18c1d11`), `sdd=false`, rigor
  `estandar`. Trabajada en un worktree temporal de la rama: el árbol principal lo usaba el
  spec-author de F-140. Intérprete: el venv del árbol principal, enlazado como `.venv` (ignorado).
- Commits (`git log 18c1d11..HEAD`): `072da4a` T0 `in_progress` · `f127f1f` T1 test en RED ·
  `8134d5e` T2 textos, v61 y los tests de F-147 · `ecc7604` T3 despliegue en `current.md` ·
  `fa8c04a` T3 test de F-006 y BACKLOG · y el de este informe.

## Qué cambió

| Fichero | Cambio |
|---|---|
| `config/diccionario/00_global.yaml` | `convenciones.identidad_sigrid`: «… es guia interna del ETL.» (fuera «en la regla `R-SIGRID-CON`, que es la unica version»); su comentario `#` explica F-149. `version: 61` con su comentario. |
| `config/diccionario/compras.yaml` | `codigo_obra_cabecera` de `compras.albaranes` (~l.770) y `compras.facturas` (~l.1321): «Codigo de la obra de cabecera (`con.cod`).» |
| `tests/test_f149_mcp_sin_reglas_no_publicadas.py` | NUEVO, 13 tests (abajo). |
| `tests/test_f147_contenido.py` | R14 exigía que `identidad_sigrid` NOMBRARA la regla; ahora lo prohíbe (sigue el tope de 300). |
| `tests/test_f006_copias.py` | R26 exigía lo mismo («tiene que remitir a la regla»); ahora prohíbe la cita y exige «guia interna del ETL». Lo de fondo (no repetir el contenido de la regla) sigue igual. |
| `docs/CONVENTIONS.md` | Una frase en la viñeta de `entrega`: lo que llega al MCP no cita una `fuera_mcp` ni un código inexistente. |
| `harness/features.json`, `BACKLOG.md`, `progress/current.md` | `in_progress`, backlog regenerado por `init.sh`, despliegue MANUAL y desviaciones. |

Sin cambios en `etl_sigrid/`: ni una línea de producción. La regla `R-SIGRID-CON` sigue en el YAML,
`fuera_mcp`, como guía del ETL; los comentarios `#` y la ficha de `raw` la siguen citando (FUERA).

## Decisiones de diseño

1. **«Lo que llega al MCP» se calcula con el código que publica, no con una copia.** El test aplica
   `cargar_diccionario` + `derivar_avisos` (como `PublicarDiccionarioStep.run`) y barre las filas de
   `filas_diccionario`, `filas_reglas` y `filas_contexto`, serializadas enteras a JSON: entra todo
   campo de texto (descripción, grano, columnas, relaciones, preguntas, `avisos`, `texto` y `datos`
   del contexto, título/regla/motivo/resumen de las reglas), también los que se añadan mañana.
2. **Qué fichas sirve el MCP**: las de todos los esquemas salvo los vetados incluso al login total,
   `DEFAULT_TOTAL_VETOED_SCHEMAS` de `config/settings.py` (hoy `raw`, F-136: «total no incluye raw,
   siempre fuera»). Total ⊃ estándar ⊃ restringido, así que lo que el total no ve no lo ve nadie, y
   las `*_restringida` (que sí ve el total) quedan dentro del barrido. Un test fija que hoy es `{raw}`.
3. **Qué regla «se publica»**: `Regla.publicable` (todas menos `fuera_mcp`, D4 de F-147). Una cita
   a un código que no está en el YAML cuenta igual que una `fuera_mcp`.
4. **Código de regla**: `\bR-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*` (la letra tras `R-` evita un `R-1`).
   Sobre el diccionario real encuentra 21 códigos distintos y ningún falso positivo.
5. **Los `avisos` también cuentan**: una futura `fuera_mcp` con ámbito en un esquema servido pondría
   su código en los `avisos` de cada ficha de ese esquema; hay un test para ese caso.
6. El detector vive en el test, no en `etl_sigrid/`: la feature pide un test, y no hay comportamiento
   de producción que cambiar (la publicación ya excluye las `fuera_mcp`; lo malo era el texto).

## Tests de `tests/test_f149_mcp_sin_reglas_no_publicadas.py`

- Diccionario real: nada de lo publicado al MCP cita una regla no publicada (la aceptación);
  `R-SIGRID-CON` no aparece en ningún texto servido; control de que el barrido ve
  `ficha compras.facturas`, `contexto convenciones.identidad_sigrid`, reglas y ninguna ficha de
  `raw`; la regla sigue `fuera_mcp`; `identidad_sigrid` dice «guia interna del ETL» y «no se
  consulta desde el MCP»; `version >= 61`.
- Detector sobre diccionarios sintéticos: caza una `fuera_mcp` en una columna, en un bloque de
  contexto, en una regla publicada y en un `aviso` derivado; caza un código inexistente; no mira
  fichas de `raw` ni el texto de la propia `fuera_mcp`; una cita a una regla publicada no es hallazgo.

## Fase RED

Test escrito y commiteado (`F-149 T1`) ANTES de tocar los YAML. Comando, desde la raíz del worktree:

`.venv/Scripts/python.exe -m pytest tests/test_f149_mcp_sin_reglas_no_publicadas.py -q -p no:cacheprovider`

```
E       AssertionError: Texto servido por el MCP que cita una regla que el MCP no puede leer (`fuera_mcp` o inexistente): [('contexto convenciones.identidad_sigrid', 'R-SIGRID-CON'), ('ficha compras.albaranes', 'R-SIGRID-CON'), ('ficha compras.facturas', 'R-SIGRID-CON')]
E       assert [('contexto c...-SIGRID-CON')] == []
tests\test_f149_mcp_sin_reglas_no_publicadas.py:117: AssertionError
______ test_f149_r_sigrid_con_no_aparece_en_nada_de_lo_que_llega_al_mcp _______
E       AssertionError: assert ['ficha compr...tidad_sigrid'] == []
E         Left contains 3 more items, first extra item: 'ficha compras.albaranes'
_________ test_f149_identidad_sigrid_dice_que_es_guia_interna_del_etl _________
E       AssertionError: assert 'guia interna del ETL' in '`raw` (la copia de Sigrid) no se consulta desde el MCP. Como se lee Sigrid -la clave `ide`, las tablas que son propiedades de `con` y de que lado sale cada campo- es guia del ETL, en la regla `R-SIGRID-CON`, que es la unica version.'
____________________________ test_f149_version_61 _____________________________
E       assert 60 >= 61
FAILED tests/test_f149_mcp_sin_reglas_no_publicadas.py::test_f149_nada_de_lo_que_llega_al_mcp_cita_una_regla_que_no_se_publica
FAILED tests/test_f149_mcp_sin_reglas_no_publicadas.py::test_f149_r_sigrid_con_no_aparece_en_nada_de_lo_que_llega_al_mcp
FAILED tests/test_f149_mcp_sin_reglas_no_publicadas.py::test_f149_identidad_sigrid_dice_que_es_guia_interna_del_etl
FAILED tests/test_f149_mcp_sin_reglas_no_publicadas.py::test_f149_version_61
4 failed, 9 passed in 6.86s
```

Los 9 que ya pasaban en RED son los del detector sobre diccionarios sintéticos y los controles: no
dependen del texto real. Tras `F-149 T2`, el mismo comando: `13 passed in 5.17s`.

## Desviaciones (también en `progress/current.md`)

1. **Dos tests anteriores exigían la cita que F-149 quita**: `test_f147_contenido.py` (R14 de F-147:
   «que remita a `R-SIGRID-CON`») y `test_f006_copias.py` (R26: «tiene que remitir a la regla»).
   La petición del humano de F-149 revoca justo eso; se invierten a «no la nombra» y conservan lo
   demás (tope de 300 caracteres; no repetir el contenido de la regla). El primero lo cazó mi
   barrido de los tests del diccionario; el segundo, el primer `init.sh` (`-x`).
2. **`.env` de marcador en el worktree.** `init.sh` exige `.env` (sección 5) y los tests de CLI lo
   leen (`SigridApiSettings`). NO se copió el `.env` real: se creó uno ignorado por git con dos
   líneas sin secretos (`SIGRID_API_BASE_URL=https://sigrid-api.invalid`, `SIGRID_API_FUNCTION_KEY=`
   vacía). `.env.example` no servía: trae `SIGRID_API_TIMEOUT_S=300.0`, por encima del techo de 230
   del código, y tumba 23 tests de CLI. **Defecto previo de `.env.example`, fuera de alcance**:
   propuesto al líder como arreglo aparte.

## `azure-apps`

**No cambia.** F-149 no toca lo que el datamart expone ni consume: ni objetos, ni columnas, ni tablas
de `_meta`, ni contrato con `mcp-bbdd`. `azure-apps/datamart_seg_anual.md` (~l.220) dice que las
`fuera_mcp` no llegan a la tabla, «hoy `R-SIGRID-CON`», y sigue siendo cierto.

## MANUAL pendiente (tras APROBADO y merge; lo autoriza el humano)

Secuencia completa en `progress/current.md` (sección «F-149 · Despliegue MANUAL»): imagen
(`infra/70_build_image.ps1`) y job (`infra/85_update_job.ps1 -Tag <nuevo>`, comprobando la imagen del
job), `publicar-diccionario` (v61, `n_reglas` = 20) y `check-diccionario` OK, reinicio del MCP leyendo
antes la revisión activa (`latestReadyRevisionName`), y comprobar «Versión 61» en `contexto_bbdd()`
sin `R-SIGRID-CON`, y «(`con.cod`)» en `describir_tabla` de `compras.facturas`/`compras.albaranes`.
Nada se ha ejecutado contra Azure ni Sigrid.

## Evidencias

| Evidencia | Valor real | Cómo |
|---|---|---|
| Tests propios de F-149 | **13 passed** en 5,17 s (RED: 4 failed, 9 passed) | `pytest tests/test_f149_mcp_sin_reglas_no_publicadas.py` |
| Suite completa | **8.782 passed, 283 skipped, 0 failed** en 1.112,30 s (18 min 32 s) | `pytest tests -q`, sin `-x`, tras el último cambio de tests (`fa8c04a`) |
| `init.sh` final | **exit 0, `ENTORNO LISTO`**, 8.782 passed / 283 skipped | `bash harness/init.sh` sobre `43e5554` |
| Cobertura de líneas cambiadas | **N/A**: «F-149 no cambia líneas Python de producción frente a main» | `PUERTA COBERTURA` de `init.sh` |
| Mutación | **0 mutantes: ALCANCE VACÍO**, «ni una línea de producción que mutar»; la herramienta no escribe `progress/mutacion_F-149.md` a propósito | `python -m harness.mutacion --feature F-149` |
| Tiempo de la suite | 1.112,30 s sin cobertura; 3.296,99 s con cobertura dentro de `init.sh` | línea final de pytest |

Sobre la mutación vacía: lo que F-149 cambia es texto del diccionario y tests, y la herramienta solo
muta Python de producción. La defensa equivalente es la del propio detector: la fase RED (cazó los
tres textos reales) y los seis tests sintéticos que prueban que caza cada sitio y no da falsos
positivos (`raw`, la propia `fuera_mcp`, una cita a regla publicada).

## `bash harness/init.sh`

- Primer intento (antes de arreglar `test_f006_copias.py`): exit 1, un KO, pytest con `-x` paró en
  `test_f006_r26_la_convencion_de_sigrid_no_duplica_la_regla` (`1 failed, 342 passed`). Arreglado
  en `fa8c04a` (desviación 1).
- Final (sobre `43e5554`, con este informe ya commiteado): **exit 0, `ENTORNO LISTO`**; pytest con
  cobertura `8782 passed, 283 skipped` en 3.296,99 s (54 min 56 s; la máquina iba cargada);
  `PUERTA COBERTURA: N/A`; `PUERTA TAMAÑO` OK (impl 134/220); único aviso, ruff 275 (deuda previa).
