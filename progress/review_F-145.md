<!-- progress/review_F-145.md -->
Revisión incremental desde b0e3298 (pasada 2) · delta `b0e3298..0d1c896` + `azure-apps` `5602198`

# F-145 · Review · la ficha de los adjuntos según la F-025 de `mcp-bbdd`

- **Veredicto: APROBADO (APPROVED)** (pasada 2). Pasada 1: CHANGES_REQUESTED (resumen al final).
- **Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura y mutación.

## Pasada 2 · qué se verificó y cómo

- `bash harness/init.sh` **entero, tal cual**, sobre `0d1c896`: **exit 0**, `8486 passed, 254 skipped`
  en 5395 s; `PUERTA COBERTURA: N/A` con motivo; `PUERTA TAMAÑO` OK (impl 183/220, review 127/140).
- Lo aprobado hasta `b0e3298` queda dado por bueno; el delta no cambia firmas, ficheros ni alcance medido
  (sigue siendo solo el docstring de `documento_adjuntos.py`).
- **Contraste con el CÓDIGO de `mcp-bbdd`** (solo lectura): `infrastructure/sigrid/cliente_documentos.py`
  `leer()` l.192-225 —`empresa = clave.empresa if … is not None else EMPRESA_RESPALDO`; sin fila y
  `empresa == EMPRESA_RESPALDO` → `SinBinario` sin segunda petición; si no, UNA más con la 1 y, si tampoco,
  `SinBinario`; `por_respaldo` si se localizó con la 1 sin que la fila lo dijera (también con la fila nula)—,
  `servicio_adjuntos.py` l.236-237 (`respaldo=empresa_defecto`) y `domain/adjuntos.py` `AVISO_RESPALDO`.
  `azure-apps/mcp_bbdd.md` §1 (hoy l.155, la fila de `sigrid-api`) dice lo mismo. **Los cuatro textos nuevos
  (ficha, v57, ARCHITECTURE, H5) dicen exactamente eso**, incluido «lo mismo si con la 1 tampoco hay fichero».
- **Barrido de lo mezclado** (`vez más con la empresa`, `empresa (es) nula`, `no trae empresa`, `segunda
  petici`) en el árbol (fuera de `progress/`, `specs/`, `BACKLOG.md`) y en `azure-apps/datamart_seg_anual.md`:
  ningún texto atribuye ya un reintento a la empresa 1 ni dos peticiones a la nula. Quedan solo los textos
  correctos y los literales de los sabotajes del test. `azure-apps` l.1028 («Nula se tolera (va al respaldo
  con la empresa 1)») es correcto: el MCP lo traza como respaldo. COMMENT del SQL y docstring del dominio no
  hablan del respaldo.
- `azure-apps` `5602198`: un commit, solo `datamart_seg_anual.md` (H5, +8/-5). Sin cambios posteriores a H5.

### RED reproducida y sabotajes propios (en una copia aislada: `git worktree` en el scratchpad)

| Prueba | Resultado |
|---|---|
| RED de H1: `compras.yaml`, `00_global.yaml`, ARCHITECTURE de `b0e3298` + H5 de `5602198^` | **8 failed, 40 passed**: los 8 del informe (§7), mismos tests |
| S7 · v57: «con la empresa 1, una segunda peticion igual» (sin `SIN_BINARIO`) | 1 FAILED: `…_el_resto_separa_…[comentario_v57]` |
| S8 · H5: «directamente con la empresa 1» → «con la empresa 1 tras un primer intento» | 1 FAILED: `…_azure_apps_dice_la_pareja_y_el_contrato` |
| S5 (O1) · SQL real: `b.empresa_repositorio AS empresa,` en el SELECT final | 4 FAILED, **ahora también la guarda F-145** (`…_es_entera_en_el_sql`) |
| S9 · ficha: añadir «Con la empresa nula o un 400, lo pide una vez mas con la empresa 1» conservando lo correcto | **pasa** (ver O2) |

Corridos con `test_f145_adjuntos_clave.py` + `test_f090_diccionario.py`. Worktree retirado; árbol limpio.

### Mutación: cero mutantes, recalculado otra vez

`harness.alcance` (base `main`, `14316d5..rama`): 1 fichero, l.12-14 de `documento_adjuntos.py` (docstring)
→ `generar_mutantes` = **0**. El delta de la pasada 2 no toca producción. Control de la pasada 1 vigente.

## Cambios requeridos de la pasada 1 → estado

| Cambio | Estado | Verificación |
|---|---|---|
| 1 · ficha, v57, ARCHITECTURE separan los tres casos | **hecho** | diff `ac6ab44` contra el código de `mcp-bbdd` (arriba) |
| 2 · H5 en `azure-apps`, commit propio | **hecho** | `5602198`, solo ese fichero |
| 3 · test que exige la distinción, con RED | **hecho** | `TRES_CASOS_DEL_RESPALDO` en ficha y H5; v57 y ARCHITECTURE con su test; la forma mezclada en `CADUCADO` con 4 sabotajes y control. RED reproducida |
| 4 · `impl_F-145.md` al día | **hecho** | estado `in_progress`, §5 con la historia y el `init.sh` final, «Evidencias» con la suite final |
| 5 · MANUAL en `current.md` con comandos | **hecho** | 6 pasos en orden; scripts `70_build_image.ps1`, `85_update_job.ps1 -Tag`, `check-diccionario`, `rg-mcp-bbdd-dev` comprobados |
| O1 · la guarda ve el renombrado final | **hecho** | S5 propio: la guarda lo ve |

## ¿La §1 del informe del implementer choca con C4 bis?

**No.** C4 bis exige la traza RED, la puerta de cobertura, la mutación y «Evidencias» con números finales,
y las cuatro están en §3/§7 y §8 con valores reales. La §1 trae en l.12 la forma mezclada («un 400 `ValueError`
o una empresa nula provocan UNA petición más»), pero el propio informe declara en l.6 que las §1-4 son la
pasada 1 y la §7 lo corrige punto por punto. El informe es memoria de `progress/`, no lo lee ni el MCP ni la
IA que consulta el diccionario. No bloquea (O3).

## Hallazgos de la pasada 2 (ninguno bloquea)

- **O2 · El barrido negativo no es exhaustivo (S9).** Una forma mezclada con otras palabras («con la empresa
  nula o un 400») añadida junto al texto correcto no la caza nadie: `CADUCADO` lista las formas que hubo y
  `TRES_CASOS` solo exige lo positivo. Es el límite de cualquier test de texto, no un defecto de F-145; si un
  día se quiere cerrar, una regex de «nula … o … 400 … una vez m» en la ficha. A criterio.
- **O3 · `impl_F-145.md`**: l.12 (§1) repite la forma mezclada sin remitir a la §7; una nota «(corregido en
  la pasada 2, §7)» bastaría. l.98 trae comillas invertidas descuadradas (``` ``b922f0f` (exit 0)` ```). Cosmético.
- **O4 · Para el líder:** la `description` de F-145 en `harness/features.json` (y el `BACKLOG.md` generado)
  conserva la forma mezclada «(2) si … 400 … o la fila trae `empresa_repositorio` nula, lo pide UNA vez
  más». Es el encargo y no llega al MCP, pero al cerrar conviene una nota que remita a la ficha.
- **O5 · MANUAL paso 5:** la revisión `ca-mcp-bbdd-dev--0000022` es la vigente hoy; F-028 de `mcp-bbdd` está
  pendiente de despliegue y la cambiará. Quien ejecute el paso 5 lee antes la revisión activa.

## Checkpoints (pasada 2)

| Punto | Estado | Razón |
|---|---|---|
| C1 init.sh exit 0 y ficheros del arnés | [x] | init.sh relanzado entero en esta pasada: exit 0, 8486 passed, 254 skipped |
| C2 una sola `in_progress` y rama | [x] | solo F-145; `feature/F-145-adjuntos-clave-empresa-codigo` |
| C2 current.md solo la sesión activa | [x] | la entrada de F-145 sustituye a las dos anteriores; lo demás, previo a la rama |
| C2 features `done` en history.md | [x] | F-145 no está cerrada; no cambia ninguna otra |
| C3 hexagonal, primera línea con ruta | [x] | delta: texto y tests; el test conserva su ruta |
| C3 sin prints/TODOs/secretos; semántica Sigrid | [x] | revisado el delta; sin secretos (el `az … restart` solo nombra recursos ya documentados) |
| C3 bis (documentos de fuera) | N/A | no entra ningún documento externo |
| C4 trazabilidad acceptance → test | [x] | tabla de abajo |
| C4 tests sin red ni BBDD | [x] | estáticos; `git show main:` local |
| C4 MANUAL en current.md | [x] | H3 resuelto: 6 pasos con comando exacto |
| C4 dobles comparados | N/A | la feature no añade ni toca dobles |
| C4 bis rigor declarado | [x] | `estandar` |
| C4 bis fase RED | [x] | pasada 1 (§3) y pasada 2 (§7: 8 y 1 failed), salida real; la de H1 reproducida aquí |
| C4 bis cobertura | N/A | `PUERTA COBERTURA: N/A` con motivo impreso: las líneas cambiadas no son ejecutables |
| C4 bis mutación | N/A | cero mutantes legítimo: recalculado en las dos pasadas, con control en la 1 |
| C4 bis muertos, tiempo, ⚠, RM1, RM2, supervivientes, campaña manual | N/A | sin campaña: cero mutantes; los sabotajes son guardas de test, no mutantes |
| C4 bis RM5 / RM6 | N/A | rigor `estandar` / no se quitó código defensivo |
| C4 bis «Evidencias» | [x] | §8 con los cuatro números finales (H2 resuelto); workers N/A sin campaña |
| C4 ter | N/A | no existe `harness/rutas_sensibles.json` |
| C5 tasks.md | N/A | `sdd=false`; commits `F-145 T4`…`T6 ter` presentes |
| C5 sin temporales | [x] | árbol limpio tras los sabotajes |
| C5 features.json refleja el estado | [x] | `in_progress` hasta el cierre del líder |

## Cobertura: acceptance → test

| Acceptance | Test | Estado |
|---|---|---|
| A1 ficha y `cod_repositorio`: pareja, respaldo con sus casos, `ORIGEN_AMBIGUO`; nada caducado | `…_la_ficha_dice_…` (+`TRES_CASOS`), `…_columna_cod_repositorio_…`, `…_ninguna_ficha_dice_lo_caducado[*]` | pasa |
| A2 COMMENT y azure-apps dicen lo mismo; contrato del entero | `…_comment_de_la_tabla_…`, `…_azure_apps_dice_…` (+`TRES_CASOS`), `…_ni_azure_apps`, `…_el_resto_separa_…[*]` | pasa |
| A3 entero en el SQL, nada caducado, v57 | `…_es_entera_en_el_sql`, 7 sabotajes (con O1), `…_version_…`, `…_historia_de_versiones` | pasa |
| A4 init.sh verde + APROBADO; despliegue tras el merge | init.sh de esta pasada; MANUAL en `current.md` | init.sh verde y APROBADO; MANUAL pendiente del merge |

## Pasada 1 (resumen; el detalle está en `git show b0e3298:progress/review_F-145.md`)

Revisión completa de `14316d5..d36bd09` + `azure-apps` `4d77cbc`. CHANGES_REQUESTED por **H1** (el respaldo
con la empresa 1 descrito más amplio que el MCP: atribuía un reintento a la empresa 1 y dos peticiones a la
nula, en ficha, v57, ARCHITECTURE y H5), **H2** (informe del implementer con el estado `blocked` y la suite en
rojo ya superados) y **H3** (MANUAL fuera de `current.md`); **O1** (la guarda no veía el renombrado final).
Sabotajes S1-S5 y mutación recalculada (0, con control: 8 y 26 sin la exclusión). Todo resuelto arriba.

## Automejora (propuesta, no aplicada)

Se mantiene la de la pasada 1: si una feature de texto describe lo que hace otro servicio, contrastar con su
**código**, no solo con su documento ni con el encargo (aquí los dos traían la misma simplificación, y
`features.json` la conserva, O4). Una línea en `reviewer.md`, paso 3.
