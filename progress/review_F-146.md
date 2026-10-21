<!-- progress/review_F-146.md -->
Revisión completa (pasada 1) · `main...fd471a6` + `azure-apps` `79bb47b` y `eda420c`

# F-146 · Review · el perfil restringido sin contabilidad (+ ampliación: adjuntos convertidos)

- **Veredicto: APROBADO (APPROVED).** Sin cambios requeridos; seis observaciones no bloqueantes (O1-O6).
- **Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura y mutación.
- `sdd=false`: se valida contra `description` y los 6 `acceptance` (ampliación incluida). Sin `tasks.md` (N/A
  por la nota de cabecera de CHECKPOINTS); commits `F-146 Tn: …` (11).

## Qué se verificó y cómo

- `bash harness/init.sh` **entero, tal cual**, sobre `fd471a6`: **exit 0**, `8516 passed, 254 skipped` en
  2851 s; `PUERTA COBERTURA: [OK] 100.0% (1/1)`; `PUERTA TAMAÑO` OK (impl 203/220); `BACKLOG.md al día`;
  barrido de dobles de F-025 en verde. Coincide con lo que declara el implementer. Árbol limpio después.
- **(A) Configuración y nocturna.** `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS` sin `contabilidad`, excluidas `""`,
  `.env.example` igual. `apply_grants` sin cambio de lógica: lo ajeno sale de `esquemas_ajenos(catálogo)`, así
  que `contabilidad` entra en `apply_veto` → `build_veto_statements` (REVOKE en tablas, **USAGE** y privilegio
  por defecto) y en la postcondición `lecturas_indebidas` para grupo y login. Leído en
  `apply_grants_step.py` l.236-262 y `grants.py` l.212-256.
- **Una tabla nueva de `contabilidad` no le llega:** no se le concede (no está en la lista), el veto del
  esquema la cubre al nacer (USAGE + default privileges) y `objetos_vigilados` solo busca en los esquemas del
  perfil (`SQL_OBJETOS_VIGILADOS`, `n.nspname = ANY(%s)`), así que tampoco hace fallar la nocturna. El cambio
  del fake de F-141 (filtrar vigilados por esquema) reproduce ese SQL real: correcto.
- **Estándar y total no cambian:** `DEFAULT_CONSUMPTION/VETOED/TOTAL_VETOED` intactos (diff de `settings.py`
  solo toca el bloque del restringido); test R3 y sabotajes S4/S6 abajo.
- **`retenciones` igual:** sigue en la lista (test `r1_retenciones_sigue_dentro`, sabotaje M3); ninguna línea
  de `sql/retenciones/` ni de su diccionario cambia.
- **Riesgo nuevo que comprobé yo (no lo cita el informe):** `contabilidad` pasa a ser objetivo de R13 (vistas
  del perfil que leen lo que no ve). Si alguna vista de `mart/cierre/compras/retenciones/…` leyera una tabla de
  `contabilidad`, la nocturna fallaría. Barrido: fuera de `sql/contabilidad/` ningún `.sql`/`.py` de producción
  referencia una relación `contabilidad.*` (solo comentarios; `descompuestos` copia `fn_fecha` a propósito y
  `SQL_VISTAS_QUE_FILTRAN` solo mira `pg_class`). Sin riesgo en lo que declara el repositorio (ver O5).
- **`02_roles.sql`:** nueve esquemas en los tres arrays, fuera el bucle `excluida_r`, veto del catálogo con
  los DOS concedentes alcanzando `contabilidad`, comprobación final con `contabilidad` en el grupo `f` y
  `apuntes_restringidos_mes` añadida. T2b (quitar «nueve» de dos comentarios por el test R25 de F-057) es una
  redacción, no un debilitamiento: la comprobación de los arrays de ese test sigue intacta.
- **Tests de otras features, antes/después** (solo dos `assert` retirados, ambos sustituidos por otros más
  fuertes o equivalentes):
  - F-141 R7: la lista de inválidas ahora **añade** `contabilidad.mayor` como errata esperada (más estricto).
  - F-141 R22: si no hay excluidas por defecto exige que NO exista el bucle (`excluidas is None`); con
    excluidas, la comprobación de antes intacta. Aceptable.
  - F-141 R11/R12/R23/R26/R28: listas al día; R28 añade `plan_cuentas` y `apuntes_restringidos_mes` (más).
  - F-128 R22: tras el merge mira el diff del propio `Merge F-128` contra su primer padre. Lo comprobé:
    `a24bf34` existe en `main` y ese diff sobre los tres ficheros es **vacío**. Misma garantía.
  - F-139 R2/R6: cambian «SIN CONVERTIR»/«sin convertir» por «F-028»/«TEXTO por pagina»/«como IMAGEN» y
    añaden «SIN CONVERTIR» y «como binario» a los caducados: siguen la decisión del humano, no la rebajan.
- **(B) Ampliación, contrastada con `azure-apps/mcp_bbdd.md`** (l.33-46, 232, 254-262, 725-747) **y el código
  de `mcp-bbdd`** (solo lectura): `paginas_por_defecto: int = 10` (`domain/conversion.py` l.290,
  `config/settings.py` l.966), `horas_vida: 24` (`config/config.yaml` l.447), ejemplo `paginas="11-20"`
  (config.yaml l.48), Graph convierte la ofimática ≤2 MB, `.msg` y `.xlsx` grandes por extracción en el
  servidor, escaneos/imágenes como imagen, enlace solo para quien lo pidió (`invite` por oid). La ficha, la
  v58, ARCHITECTURE y H6/H8/H11/H13 dicen exactamente eso. **COMO LO PIDE intacto**: la clave
  `{"emp","cod"}`, los tres casos del respaldo con la empresa 1, `SIN_BINARIO`, `ORIGEN_AMBIGUO` y
  `respaldo=empresa_defecto` siguen literales (y H5 de `azure-apps` igual).
- **Barrido de lo caducado** (`sin convertir|como binario|incrustad`, fuera de `progress/`, `specs/`, `tests/`):
  solo quedan la entrada histórica v53 (l.584), la propia v58 que lo niega y textos de `raw.gra.ima` ajenos.
- **Diccionario v58 robusto al merge:** `version: 58`; test `version_la_siguiente_a_la_de_main` (main+1 antes
  del merge, `>=` después si `main` ya trae `(F-146, `) y `historia_de_versiones` (`# version 58 (F-146, `).
- **`azure-apps`:** `79bb47b` y `eda420c` tocan SOLO `datamart_seg_anual.md` (`git show --stat`), sin push;
  fila del restringido honesta («F-146 sin desplegar: hasta su apply-grants sigue leyendo…»); R30 de F-141 en
  verde dentro del `init.sh`.
- **Secuencia MANUAL** en `progress/current.md`: 8 pasos en orden (imagen y job ANTES de publicar y de
  `apply-grants`, con el porqué), comandos exactos; `infra/70_build_image.ps1` y `85_update_job.ps1` existen.
  El `.env` del puesto no fija `PG_PERFIL_RESTRINGIDO_*` (comprobado con `grep -c`: 0) ni `infra/` tampoco.

### Sabotajes propios (copia `git archive HEAD` en el scratchpad; el árbol real no se tocó)

Base de la copia: todo verde salvo `test_f141_r24_…` (usa `git ls-files`; la copia no tiene `.git`).

| # | Sabotaje | Tests que caen |
|---|---|---|
| S1 | `esquemas_ajenos`: `suyos = set(esquemas) \| {'contabilidad'}` | 6 (f146 r2×2, f141 r12, r11_r12, r19, r13) |
| S2 | ficha de adjuntos: vuelve «y lo entrega SIN CONVERTIR» | 2 (f146 t6 `ya_no_dice…`, f139 r2) |
| S3 | ficha: `respaldo=empresa_defecto` → `respaldo=otro` | 1 (f146 t6 `la_clave_y_el_respaldo…`) |
| S4 | el ESTÁNDAR veta `contabilidad` (`DEFAULT_VETOED_SCHEMAS`) | 4 (f146 r2×3, **r3**) |
| S5 | `plan_cuentas` sin el aviso del restringido | 3 (f146 r5, f141 r28×2) |
| S6 | el TOTAL veta `contabilidad` (`DEFAULT_TOTAL_VETOED_SCHEMAS`) | 4 (f146 r2×3, **r3**) |
| S7 | `02_roles.sql` 5 quinquies a: `'contabilidad'` en el array del GRANT | 2 (f146 r4, f141 r22) |
| S8 | `R-PERFIL-RESTRINGIDO`: «SI lee … `contabilidad.plan_cuentas`» | 2 (f146 r5×2) |

## Checkpoints

| Checkpoint | Estado | Motivo |
|---|---|---|
| C1 init.sh exit 0 / ficheros del arnés | [x] / [x] | ejecutado entero en esta pasada |
| C2 una sola `in_progress` / rama `feature/F-146-…` | [x] / [x] | init.sh lo valida |
| C2 current.md solo la sesión activa | [x] | la entrada de F-146 es la nueva; lo demás, previo a la rama |
| C2 toda `done` en history.md | [x] | F-146 no está `done` |
| C3 hexagonal / SQL en su capa | [x] | sin código nuevo: constantes, comentarios y SQL de provisión en `infra/sql` |
| C3 primera línea con ruta | [x] | test nuevo e informe la llevan |
| C3 sin prints, TODOs, secretos ni dependencias | [x] | revisado el diff; sin IP, GUID ni contraseña |
| C3 semántica Sigrid | N/A | no toca cálculos de ámbito/fase/importes: solo permisos y textos |
| C3 bis | N/A | no añade ni cambia nada en `docs/referencia/` |
| C4 cada acceptance con test que pasa | [x] | tabla de cobertura abajo |
| C4 unit tests sin red ni BBDD | [x] | clientes simulados; `git` y `azure-apps` como lectura de ficheros |
| C4 MANUAL en current.md con comando exacto | [x] | 8 pasos |
| C4 dobles comparados con el original | [x] | `test_f025_*` (barrido automático) en verde; fakes nuevos sin métodos ajenos |
| C4 bis rigor declarado | [x] | `estandar` |
| C4 bis fase RED | [x] | trazas reales de T1 (5 fallos, 18 en la campaña completa) y de T6a (5 fallos) |
| C4 bis cobertura | [x] | `[OK] 100.0% (1/1)` |
| C4 bis mutación | [x] | ver abajo: cero mutantes legítimo + campaña manual reproducida |
| C4 bis muertos comprobados / tiempo / RM1-RM6 | N/A | no hay informe de mutación: la herramienta aborta con «CERO MUTANTES» y no escribe; nada que reejecutar ni mutante equivalente que juzgar. RM6: no se quitó ninguna guarda |
| C5 tasks.md | N/A | `sdd=false`, sin `tasks.md`; commits `F-146 Tn:` |

**Mutación.** Recalculé el alcance con `harness.alcance` (`main...HEAD`): producción = `settings.py` 18
líneas, `apply_grants_step.py` 3, `grants.py` 11 (las 32 del informe); `generar_mutantes` sobre ellas: **0**.
Prueba de control (sin exclusión de alcance): el generador sí produce mutantes en los ficheros de test del
diff (3, 14, 123), así que no está roto: el cero es legítimo (cadenas, comentarios y docstrings). La evidencia
sustitutiva son 4 mutantes manuales; **reproduje tres al pie de lo descrito** con el mismo conjunto de tests
(F-141+F-146+F-128 restringida+F-135+F-136): M1 → 8 fallos, M3 → 6, M4 → 1 (`r4_02_roles…`). Coinciden.

## Cobertura acceptance → test

| Acceptance | Tests |
|---|---|
| 1 sin `contabilidad`, vetada entera (USAGE), tabla nueva no llega | `test_f146_r1_*`, `r2_la_nocturna_le_veta…`, `r2_una_tabla_nueva…`, `r2_si_aun_lee…`, `r4_*` |
| 2 estándar y total no cambian | `test_f146_r3_el_estandar_y_el_total_no_cambian` (Azure: MANUAL paso 6) |
| 3 fichas, regla, v58 robusta al merge | `test_f146_r5_*` (8), `test_f141_r26/r28` |
| 4 `azure-apps` + R30 | `test_f146_r6_azure_apps…`, `test_f141_r30_*` |
| 5 ampliación: adjuntos convertidos, clave intacta | `test_f146_t6_*` (6), `test_f139_r2/r6` |
| 6 init.sh verde + MANUAL | init.sh de esta pasada; `progress/current.md` |

## Observaciones (no bloqueantes)

- **O1.** La tabla de mutantes manuales no trae fichero:línea ni el texto exacto original→mutado que pide el
  protocolo para campañas manuales. Los reproduje igual (eran inequívocos), pero la próxima vez, la fila completa.
- **O2.** `azure-apps` cita los adjuntos 305078, 304800 y 304883: solo el 299624 aparece en algún repositorio
  (`mcp-bbdd/specs/F-028…`); los otros tres vienen del aviso por chat. Que el líder confirme que son los del aviso.
- **O3.** Previo a F-146, en `azure-apps/datamart_seg_anual.md`: l.1382 dice «la futura `abrir_adjunto`» y H1
  la nombra sin `paginas`. Arreglar en la próxima que toque esa sección.
- **O4.** La ficha no dice el tope de 20 páginas por llamada ni que sin Graph llega sin enlace (lo dice la
  herramienta del MCP). Opcional.
- **O5.** Riesgo residual fuera del repositorio: una vista creada a mano en Azure que leyera `contabilidad` haría
  fallar `apply-grants` (R13). El paso 5 de la secuencia (esperar `filtraciones_restringido = ok`) lo detectaría.
- **O6.** Nuestra F-142 sigue `pending` en el backlog con el trabajo hecho por `mcp-bbdd`: decisión del líder.

## Automejora (propuesta, no aplicada)

En `reviewer.md`, sección de mutación: cuando la herramienta aborta con «CERO MUTANTES» y el implementer aporta
mutantes manuales como evidencia sustitutiva, decir explícitamente que se les aplica la regla de campaña MANUAL
(fila con fichero:línea y texto exacto). Hoy queda a interpretación si es «sustitución» o «complemento».
