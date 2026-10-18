<!-- progress/impl_F-144.md -->
# F-144 · Informe del implementer · regla `R-EMPRESA-POR-DEFECTO`

Rama `feature/F-144-empresa-por-defecto` desde `main` (`d3b2869`). sdd=false, rigor
`estandar`. Orden del humano (2026-10-18): «en general si no se indica empresa es
construcciones ruesma. es criterio general».

## Qué cambió

| Fichero | Cambio |
|---|---|
| `config/diccionario/00_global.yaml` | Regla dura nueva `R-EMPRESA-POR-DEFECTO` (bloqueante), justo detrás de `R-CODIGO-POR-EMPRESA`; ésta gana una frase final que remite a la nueva; `version: 54 → 55` y entrada `# version 55 (F-144, 2026-10-18)` en la cabecera, detrás de la 54 |
| `tests/test_f144_empresa_por_defecto.py` | Test nuevo (14 casos), escrito antes que la regla |
| `tests/test_f141_perfil_restringido.py` | Los dos tests R29 fijan la versión 54 (`VERSION_F141`) en vez de compararla con `main` (ver desviación) |
| `harness/features.json`, `BACKLOG.md` | F-144 `pending → in_progress` (script Python, `indent=2`, `ensure_ascii=False`, `newline='\n'`; `python -I harness/backlog.py`) |
| `progress/current.md` | Nota de la sesión |

Lo que dice la regla, en resumen: criterio GENERAL (no solo códigos); sin empresa en la
pregunta se entiende Construcciones Ruesma, `empresa_id = 1`, y se filtra en todo objeto con
empresa; la columna es `empresa_id` salvo `maestro.centros_coste.empresa`; los hechos que solo
llevan `obra_id` se filtran por la `empresa_id` de su ficha en `maestro.obras` o por la
`clave_obra` que empieza por `1-`; la IA DICE que lo ha supuesto (con una frase modelo); no se
aplica si se pide otra empresa (Porsan es la 28), varias, el grupo o una UTE; nunca se suman
empresas sin decirlo; `stg`/`mart`/`cierre`/`descompuestos` no tienen empresa y ahí manda
`R-UNIVERSO-OBRA`. Título (80 caracteres, tope de F-141: 87): «Sin empresa en la pregunta, es
Construcciones Ruesma (empresa_id = 1), y se dice».

## Comprobación en Azure (solo lectura)

`main._get_pg()` con `pg._bootstrap_done = True` y `filas_solo_lectura` (transacción `READ ONLY`),
host verificado `*.postgres.database.azure.com`, base `sigrid_dm`. Resultado real:

- `SELECT DISTINCT empresa_id, nombre_empresa FROM maestro.obras WHERE empresa_id IN (1,28)` →
  `(1, 'CONSTRUCCIONES RUESMA')`, `(28, 'PORSAN E HIJOS CONSTRUCCIONES SL')`.
- `information_schema.columns` con `column_name IN ('empresa','empresa_id')` fuera de `raw`: 25
  objetos con `empresa_id` (`compras` ×6, `contabilidad` ×4, `contabilidad_restringida` ×3,
  `maestro` ×3, `personal.recursos`, `retenciones` ×4, `tesoreria` ×2, `tesoreria_restringida` ×1) y
  uno con `empresa`: `maestro.centros_coste`. En `stg`, `mart`, `cierre`, `descompuestos` y `aux`:
  ninguna columna `empresa_id` (y ninguna `%empresa%`).
- Ninguna escritura, ningún DDL (sin bootstrap).

## Decisiones de diseño

1. **`ambito` por ESQUEMA**: `[maestro, compras, retenciones, personal, contabilidad,
   contabilidad_restringida, tesoreria, tesoreria_restringida]`, los ocho esquemas que tienen
   empresa (medido arriba). Es criterio general, así que alcanza a todo el esquema (como
   `R-FRESCURA`), no a una lista de objetos. Fuera: `compras_restringida` (sin columna de empresa
   ni `obra_id` medido) y `stg`/`mart`/`cierre`/`descompuestos` (sin empresa; la regla lo dice). El
   test `test_f006_r11_los_ambitos_reales_apuntan_a_algo_que_existe` lo valida en verde.
2. **Posición**: inmediatamente detrás de `R-CODIGO-POR-EMPRESA` (el test lo fija).
3. **Test de versión sin depender de `main`**: `>= 55` y la entrada `# version 55 (F-144,
   2026-10-18): `, el patrón de F-139 (`>= 53`). Comparar con `main` es lo que rompió F-141.
4. Texto sin tildes, como el resto del YAML; la frase modelo de la IA va entre comillas latinas.

## Desviación respecto al encargo (justificada)

**`main` estaba en ROJO antes de empezar.** El `bash harness/init.sh` inicial (en `main`, recién
creada la rama sin cambios) dio `1 failed, 7921 passed, 248 skipped` en 2218 s:
`test_f141_r29_version_la_siguiente_a_la_de_main` exigía `version >= version_de_main + 1`, cierto en
la rama de F-141 pero falso tras su merge (54 >= 55). Y su pareja
`test_f141_r29_la_historia_de_versiones_cuenta_f141` buscaba `# version {VIGENTE} (F-141, `, que
F-144 rompería al subir a 55. Como F-144 tiene que subir la versión, el arreglo está dentro de su
alcance: ambos fijan `VERSION_F141 = 54`. **No se debilitan**: siguen exigiendo que la versión no
baje de la de F-141 y que F-141 tenga su entrada en la historia; lo que se quita es una condición
que solo podía ser cierta en una rama. No hay ningún test que cuente las reglas (25/26): se buscó
(`len(...reglas)`, `== 2[5-7]`) y solo hay comparaciones con `len(dicc.reglas)`, que se ajustan solas.

## Fase RED (obligatoria, rigor `estandar`)

Test escrito antes que la regla, con el YAML aún en v54. Comando y salida real (recortada a las
líneas de error; la traza completa son 188 líneas, una por caso):

```
$ .venv/Scripts/python -m pytest tests/test_f144_empresa_por_defecto.py -q
FFFFFFFFFFFFFF                                                           [100%]
__________________ test_f144_la_regla_existe_y_es_bloqueante __________________
>       regla = _reglas()[CODIGO]
E       KeyError: 'R-EMPRESA-POR-DEFECTO'
tests\test_f144_empresa_por_defecto.py:40: KeyError
___________ test_f144_la_regla_va_junto_a_la_del_codigo_por_empresa ___________
>       assert codigos.index(CODIGO) == codigos.index("R-CODIGO-POR-EMPRESA") + 1
E       ValueError: 'R-EMPRESA-POR-DEFECTO' is not in list
tests\test_f144_empresa_por_defecto.py:49: ValueError
______________ test_f144_la_regla_dice_lo_que_decidio_el_humano _______________
>       texto = _plano(_reglas()[CODIGO]["regla"])
E       KeyError: 'R-EMPRESA-POR-DEFECTO'
tests\test_f144_empresa_por_defecto.py:53: KeyError
________________ test_f144_el_motivo_cita_la_orden_del_humano _________________
E       KeyError: 'R-EMPRESA-POR-DEFECTO'
tests\test_f144_empresa_por_defecto.py:70: KeyError
_______ test_f144_el_ambito_alcanza_a_todo_esquema_con_empresa[maestro] _______
E       KeyError: 'R-EMPRESA-POR-DEFECTO'
tests\test_f144_empresa_por_defecto.py:81: KeyError
  (... lo mismo para compras, retenciones, personal, contabilidad,
   contabilidad_restringida, tesoreria y tesoreria_restringida ...)
_______________ test_f144_el_codigo_por_empresa_remite_a_la_nueva ______________
E       AssertionError: assert '`R-EMPRESA-POR-DEFECTO`' in 'En Sigrid las obras y los recursos son POR EMPRESA: el mismo codigo existe una vez por empresa --Ruesma (1), Porsan (...de la ficha de SU empresa y no se traducen. Contar obras por codigo es contar `es_ficha_principal`, y hay que decirlo.'
tests\test_f144_empresa_por_defecto.py:86: AssertionError
________________ test_f144_version_55_y_su_entrada_de_cabecera ________________
E       AssertionError: F-144 sube la versión a 55
E       assert 54 >= 55
E        +  where 54 = int(54)
tests\test_f144_empresa_por_defecto.py:90: AssertionError
14 failed in 1.72s
```

Y el RED del test de F-141 que se arregla (en la rama, antes de tocar nada):

```
$ .venv/Scripts/python -m pytest tests/test_f141_perfil_restringido.py -q -k r29
tests\test_f141_perfil_restringido.py:1658: AssertionError
FAILED tests/test_f141_perfil_restringido.py::test_f141_r29_version_la_siguiente_a_la_de_main
1 failed, 1 passed, 139 deselected in 0.84s
```

GREEN, tras la regla y el arreglo:

```
$ .venv/Scripts/python -m pytest tests/test_f144_empresa_por_defecto.py tests/test_f141_perfil_restringido.py tests/test_f102_obra_principal.py tests/test_f107_contrapartidas_cuentas.py tests/test_f139_limite.py -q
327 passed, 86 warnings in 8.93s
$ .venv/Scripts/python -m pytest tests/ -q -k "f006 or diccionario" -x
2852 passed, 246 skipped, 5390 deselected, 32 warnings in 233.67s (0:03:53)
```

## Sabotajes manuales (árbol restaurado con `git checkout` tras cada uno)

| Sabotaje en `00_global.yaml` | Resultado |
|---|---|
| `severidad: bloqueante → aviso` en la regla nueva | `1 failed, 13 passed`: `assert 'aviso' == 'bloqueante'` |
| «La IA DICE en la respuesta» → «La IA puede decir» | `1 failed, 13 passed`: `assert 'DICE en la respuesta' in ...` |

## Fuera de alcance

- Publicar el diccionario y reiniciar el MCP (orden expresa del líder: va tras el merge).
- `abrir_adjunto` de `mcp-bbdd` no cambia (la empresa sale de la fila del índice).
- `azure-apps/datamart_seg_anual.md`: no se toca hasta que v55 esté publicada (el documento
  registra versiones DESPLEGADAS, p. ej. «diccionario v54» en F-141).

## Verificaciones MANUAL pendientes (tras el merge, con orden del humano)

1. `python main.py publicar-diccionario` contra Azure y `check-diccionario` OK (esperado: 27 reglas).
2. Reiniciar el MCP (`mcp-bbdd`) para que sirva v55, y avisar a `mcp-bbdd`.
3. Anotar v55 y la regla en `azure-apps/datamart_seg_anual.md`.
4. Prueba de humo en el MCP: una pregunta sin empresa debe filtrar `empresa_id = 1` y decirlo.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados (`bash harness/init.sh`, final) | **VERDE**: `8239 passed, 249 skipped, 2205 warnings`; `[OK] pytest en verde`, `PUERTA TAMAÑO` OK (impl 154/220), rama correcta |
| Cobertura de las líneas cambiadas | `PUERTA COBERTURA: N/A` (F-144 no cambia líneas Python de producción frente a main; solo YAML y tests) |
| Mutantes generados / supervivientes | **No aplica**: `python -m harness.mutacion --feature F-144` → «ALCANCE VACÍO en F-144: ni una línea de producción que mutar» (0 ficheros, 0 líneas; salida con código 2, sin informe a propósito). Los dientes se prueban con los dos sabotajes de arriba |
| Tiempo de la suite | 1011,57 s (0:16:51), el que imprime pytest dentro de `init.sh` |
| `init.sh` inicial (en `main`) | ROJO: `1 failed, 7921 passed, 248 skipped` en 2218,18 s (el test R29 de F-141) |
