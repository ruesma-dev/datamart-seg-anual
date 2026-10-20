<!-- progress/review_F-145.md -->
Revisión completa (pasada 1) · `main` 14316d5 ... `d36bd09` (b37768c..d36bd09) + `azure-apps` 4d77cbc

# F-145 · Review · la ficha de los adjuntos según la F-025 de `mcp-bbdd`

- **Veredicto: CHANGES_REQUESTED** (5 cambios: texto, un test y papeleo; nada de código).
- **Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura y mutación.

## Qué se verificó y cómo

- `bash harness/init.sh`: **no relanzado**; vale el del líder de hoy sobre este HEAD `d36bd09` (8479
  passed, 254 skipped). El rechazo es de texto y no depende de él. **En la pasada 2 se ejecuta entero.**
- `pytest tests/test_f145_adjuntos_clave.py test_f090_diccionario.py test_f139_limite.py`: **78 passed**.
- Contraste: `azure-apps/mcp_bbdd.md` (l.38-43, 147, 218-225, 1011) y el código de `mcp-bbdd`
  (`cliente_documentos.py` l.41-47 y `leer()`; `domain/adjuntos.py` `clave_documental`, `AVISO_RESPALDO`).
- SQL: solo comentarios y el literal del `COMMENT ON TABLE` (ninguna sentencia). Dominio: solo docstring.
- `id_column: cod` / `ADJUNTO_AMBIGUO` en fichas, COMMENT, dominio o ARCHITECTURE: cero (grep del árbol
  fuera de `progress/`, `specs/` y el `BACKLOG.md` generado).
- **Nota:** `azure-apps` `4d77cbc` toca `datamart_seg_anual.md`, no `mcp_bbdd.md` como decía el encargo.
  Revisado el que es (~l.880, «Estado» de F-139, H5, contrato del entero): correcto salvo H1.

### Sabotajes verificados (independientes de los del informe)

| Sabotaje | Resultado |
|---|---|
| S1 · `compras.yaml`: la `key` vuelve a ser `` `id_column:\n      cod` `` (envuelta) | `caducados_en` lo ve |
| S2 · `ADJUNTO_AMBIGUO` partido en dos líneas de comentario YAML | lo ve |
| S3 · SQL real: `COALESCE(g.emp, 1) AS empresa_repositorio` (forma no citada en el informe) | 6 FAILED: la guarda F-145 y `test_f090_r12_cada_columna_sale_de_su_campo` |
| S5 · SQL real: `b.empresa_repositorio AS empresa,` en el SELECT final | la guarda F-145 **no** lo ve; lo caza `test_f090_r12_publica_exactamente_las_columnas_en_su_orden` |

S3 y S5: aplicados en el árbol, tres ficheros de test corridos y restaurado con `git checkout --`.

### Mutación: cero mutantes, recalculado

Alcance (`harness.alcance`, `main...HEAD`): `documento_adjuntos.py` l.12-14 (docstring) → **0** mutantes.
Control sin la exclusión: 8 en el fichero entero y 26 en el test nuevo. El cero es legítimo.

## Hallazgos

### H1 · [ ] El respaldo con la empresa 1 se describe más amplio de lo que hace el MCP

Lo que hace `mcp-bbdd` (`cliente_documentos.py` l.41-47 y l.198-224; `mcp_bbdd.md` l.147):

- Fila **con empresa ≠ 1** y 400 `ValueError` → **una** segunda petición con la 1 y el mismo `cod`, y aviso.
- Fila **con empresa = 1** y 400 → **no hay segunda petición**: `SIN_BINARIO` directo.
- Fila **con empresa nula** → la **primera y única** petición ya va con la 1 (no es «una vez más»),
  con aviso y `respaldo=empresa_defecto`.

Lo que dicen nuestros textos: «Si `sigrid-api` responde 400 `ValueError` (…) **o** la fila trae
`empresa_repositorio` nula, lo pide UNA vez mas con la empresa 1». Eso atribuye un reintento a las filas
de la empresa 1 y dos peticiones a las de empresa nula. Una IA que lea la ficha le contará al usuario un
reintento que no existió. Es el punto que el encargo pedía vigilar, y el valor de esta feature es que el
texto diga exactamente lo que hace el MCP. Aparece en:

- `config/diccionario/compras.yaml` l.4407-4412 (descripción de `compras.documento_adjuntos`).
- `config/diccionario/00_global.yaml` l.635-636 (comentario de la v57).
- `docs/ARCHITECTURE.md` l.430-431 («una sola segunda petición con la empresa 1 si no hay fichero con
  ella o la empresa es nula»).
- `azure-apps/datamart_seg_anual.md`, H5 (l.942-946). Necesita commit nuevo en `azure-apps`.

La columna `empresa_repositorio` (compras.yaml l.4506-4511) está bien: «Si es nula, pide … con la empresa 1».

### H2 · [ ] El informe del implementer no refleja el estado final

`progress/impl_F-145.md` sigue diciendo **«Estado: `blocked`»** (l.5-6), la sección 5 trae el
`init.sh` en rojo como «Final», y en «Evidencias» la suite figura con `1 failed`. Desde `d36bd09`, la
feature está desbloqueada y en verde (8479 passed, 254 skipped). Las evidencias tienen que ser las
finales.

### H3 · [ ] C4: las verificaciones MANUAL no están en `current.md` con su comando

La entrada de F-145 en `progress/current.md` no lista la secuencia de despliegue: imagen y job **antes**
de publicar la v57, `python main.py publicar-diccionario`, `python main.py check-diccionario` y reinicio
del MCP. Solo está en `impl_F-145.md` §6, y C4 la pide en `current.md`.

## Cambios requeridos

1. **compras.yaml l.4407-4412**: separar los casos. Propuesta: «Si la fila trae una empresa distinta de
   la 1 y `sigrid-api` responde 400 `ValueError` (no hay fichero con esa pareja), lo pide UNA vez más con
   la empresa 1 (…) y el mismo `cod`; si la fila trae `empresa_repositorio` nula, lo pide directamente
   con la empresa 1. En los dos casos avisa (…) y deja `respaldo=empresa_defecto`. Con la empresa 1 en la
   fila, un 400 es `SIN_BINARIO`, sin segunda petición.» Mismo ajuste en el comentario de
   `00_global.yaml` l.635-636 y en `docs/ARCHITECTURE.md` l.430-431.
2. **`azure-apps/datamart_seg_anual.md` H5**: el mismo ajuste, en un commit nuevo de `azure-apps` (solo ese
   fichero).
3. **Test**: en `test_f145_la_ficha_dice_la_pareja_el_respaldo_y_el_409` (y en el de H5), exigir que el
   texto distinga el caso de la empresa 1 (p. ej. que diga `SIN_BINARIO` en la descripción y una forma de
   «distinta de la 1» / «directamente con la empresa 1»). Con fase RED: que falle antes del texto nuevo.
4. **`progress/impl_F-145.md`**: estado y sección 5 al día (verde, sin el bloqueo como estado vigente; el
   episodio puede quedar como historia en dos líneas) y «Evidencias» con la suite final real.
5. **`progress/current.md`**: en la entrada de F-145, la secuencia MANUAL con sus comandos exactos (H3).

### Observación O1 (no bloquea)

La guarda `problemas_empresa_entera` no ve el renombrado en el SELECT final (S5); lo cubre
`test_f090_r12_publica_exactamente_las_columnas_en_su_orden`. Citarlo en el docstring de la guarda, o
añadir ese sabotaje y que la guarda lo vea. A criterio del implementer.

## Checkpoints

| Punto | Estado | Razón |
|---|---|---|
| C1 init.sh exit 0 y ficheros del arnés | [x] | init.sh del líder de hoy sobre `d36bd09` (se relanza en la pasada 2); ficheros presentes |
| C2 una sola `in_progress` y rama | [x] | solo F-145; `feature/F-145-adjuntos-clave-empresa-codigo` |
| C2 current.md solo la sesión activa | [x] | entradas nuevas encima; lo anterior es previo a la rama (mismo criterio que F-144) |
| C2 features `done` en history.md | [x] | F-145 no está cerrada; no cambia ninguna otra |
| C3 hexagonal, primera línea con ruta | [x] | el dominio solo cambia un docstring; el test nuevo lleva su ruta |
| C3 sin prints/TODOs/secretos; semántica Sigrid | [x] | revisado el diff; no toca ámbito, fase ni importes |
| C3 bis (documentos de fuera) | N/A | no entra ningún documento externo |
| C4 trazabilidad acceptance → test | [x] | tabla de abajo |
| C4 tests sin red ni BBDD | [x] | estáticos; solo `git show main:` local |
| C4 MANUAL en current.md | **[ ]** | H3 |
| C4 dobles comparados | N/A | la feature no añade ni toca dobles |
| C4 bis rigor declarado | [x] | `estandar` |
| C4 bis fase RED | [x] | salida real en `impl_F-145.md` §3 (10 failed / 31 passed, con errores) |
| C4 bis cobertura | N/A | puerta `N/A` con motivo impreso por init.sh: las líneas cambiadas no son ejecutables |
| C4 bis mutación | N/A | cero mutantes legítimo: recalculado y con control (sección de mutación) |
| C4 bis muertos, tiempo, ⚠, RM1, RM2, supervivientes, campaña manual | N/A | sin campaña: cero mutantes legítimos; los sabotajes son guardas de test, no mutantes |
| C4 bis RM5 / RM6 | N/A | rigor `estandar` / no se quitó código defensivo |
| C4 bis «Evidencias» | **[ ]** | existe con los cuatro números, pero con la suite en rojo ya superada (H2) |
| C4 ter | N/A | no existe `harness/rutas_sensibles.json` |
| C5 tasks.md | N/A | `sdd=false`; commits `F-145 Tn:` presentes |
| C5 sin temporales | [x] | árbol limpio |
| C5 features.json refleja el estado | [x] | `in_progress` y una nota del desbloqueo |

## Cobertura: acceptance → test

| Acceptance | Test | Estado |
|---|---|---|
| A1 ficha y `cod_repositorio` dicen la pareja, el respaldo y `ORIGEN_AMBIGUO`; nada caducado | `test_f145_la_ficha_dice_…`, `…_columna_cod_repositorio_…`, `…_ninguna_ficha_dice_lo_caducado[*]` | pasa; el respaldo, impreciso (H1) |
| A2 COMMENT y azure-apps dicen lo mismo; contrato del entero | `…_el_comment_de_la_tabla_…`, `…_azure_apps_dice_la_pareja_y_el_contrato`, `…_ni_azure_apps` | pasa; H5 impreciso (H1) |
| A3 entero en el SQL, nada caducado, v57 | `…_empresa_repositorio_es_entera_en_el_sql`, 6 sabotajes, `…_version_la_siguiente_a_la_de_main`, `…_historia_de_versiones` | pasa |
| A4 init.sh verde + APROBADO; despliegue tras el merge | init.sh del líder; MANUAL tras el merge | pendiente del APROBADO |

**Versión robusta al merge:** `main` + 1 antes; que no baje si `main` ya trae `(F-145, ` (correcto).

## Automejora (propuesta, no aplicada)

Si una feature de texto describe lo que hace otro servicio, contrastar con su **código** (no solo con su
documento ni con el encargo, que aquí traía la misma simplificación). Una línea en `reviewer.md`, paso 3.
