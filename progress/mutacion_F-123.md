<!-- progress/mutacion_F-123.md -->
# F-123 · Campaña de mutación (MANUAL, sobre el SQL)

Escrito a mano por el implementer el 2026-10-02: **no lo genera
`harness.mutacion`**, y por eso lo dice aquí arriba.

## Por qué no la del arnés

`python -m harness.mutacion --feature F-123` (HEAD `8d49a5f`) termina sin informe:

```
CERO MUTANTES en F-123: el alcance tiene 16 línea(s) de producción pero no se ha generado ni un mutante,
así que no se ha juzgado NADA. [...] Motivo: esas líneas no llevan código mutable —imports, docstrings,
declaraciones, cadenas—. Amplía el alcance o aporta la evidencia de otra forma, y dilo por escrito.
F-123: 3 fichero(s), 16 línea(s) de producción (origen rama, d4f58ea..feature/F-123-descompuestos-regla-origenes)
```

Las 16 líneas Python son la tupla `ORIGENES`, la ayuda de `main.py` y el
docstring del paso. **La lógica de F-123 es SQL**, que el arnés no muta. Ampliar
el alcance a módulos Python sin cambios mediría otra cosa; así que la evidencia
se aporta de otra forma: una campaña de mutantes escritos a mano sobre cada
línea de SQL cambiada (y la tupla del dominio).

## Método

- Worktree desechable del HEAD de la rama (`8d49a5f`) en el scratchpad; cada
  mutante se aplica, se ejecutan `tests/test_f123_origenes.py`,
  `test_f097_descompuestos.py`, `test_f097_planificador.py` y
  `test_f120_factor.py` (`-x`) y se restaura el fichero.
- Línea base antes y después: **280 passed, 3 skipped** (los 3 son de
  `azure-apps`, que no está junto al worktree).
- 21 mutantes, todos evaluados (no hay muestreo: son pocos y son todo el
  alcance). Tiempo total **241 s**, de 6,0 a 16,3 s por mutante.
- Script: `t8/mutacion_sql.py` del scratchpad de la sesión.

## Resultado: 21 generados, 21 muertos, 0 supervivientes

| Mutante | Fichero | Mutación | Lo mata |
|---|---|---|---|
| M01 | 02 | `CHECK` de `lineas` en el DDL con el origen viejo | `r5_ningun_sql_nombra_el_origen_viejo` |
| M02 | 02 | lo mismo en el `CHECK` de `cuadre_partida` | `r5` |
| M03 | 02 | guarda de la migración `LIKE` -> `NOT LIKE` | `r15_migracion_de_cada_tabla[lineas]` |
| M04 | 02 | sin el `UPDATE` de `lineas` en la migración | `r15[lineas]` |
| M05 | 02 | el `UPDATE` de `cuadre_partida` a `MASTER_PRE_ABC` | `r15[cuadre_partida]` |
| M06 | 02 | el `ADD CONSTRAINT` de `lineas` sin `MASTER_ESTUDIO` | `r15[lineas]` |
| M07 | 02 | `ESTUDIO`: `fase_num = 0` -> `= 1` | `r9_r11_estudio_excluye_las_obras_con_version_0` |
| M08 | 02 | `ESTUDIO`: `NOT EXISTS` -> `EXISTS` | `r9_r11` |
| M09 | 02 | `ESTUDIO`: `v.obra_id = t.obra_id` -> `= t.partida_id` | `r9_r11` |
| M10 | 02 | la guarda de `lineas` mira el `conrelid` de `cuadre_partida` | `r15[lineas]` |
| M11 | 02 | sin el `DROP CONSTRAINT` de `cuadre_partida` | `r15[cuadre_partida]` |
| M12 | 03 | versión 0 -> `MASTER_PRE_ABC` | `r4_master_0_con_su_origen_nuevo` |
| M13 | 03 | el `DELETE` del lote sin `MASTER_ESTUDIO` | `r4` |
| M14 | 04 | `lineas_master_estudio` cuenta `ESTUDIO` | `r7_elementos_columna_renombrada_en_su_sitio` |
| M15 | 04 | la columna vuelve a llamarse como antes | `r7` |
| M16 | 05 | `o.origen = 'PLANIF_JO'` -> `'ESTUDIO'` | `r10_cuadre_de_la_fase_viva_por_obra` |
| M17 | 05 | `OR NOT EXISTS` -> `AND NOT EXISTS` | `r10` |
| M18 | 05 | `fase_num = 0` -> `<> 0` | `r10` |
| M19 | 06 | `v_pbi_master_estudio` publica `ESTUDIO` | `r14_vistas_la_nueva_con_las_mismas_columnas` |
| M20 | 06 | `v_pbi_master_estudio` sin `factor` | `r14` |
| M21 | dominio | `ORIGENES` con el nombre viejo | `r6_dominio_origenes_exactos` |

(Con `-x` se anota el primer test que cae; varios mutantes caen también en
otros, p. ej. M01/M02 en `r6_los_dos_check_son_los_origenes`.)

## Lo que esta campaña NO prueba

Los tests de F-123 sobre SQL son de TEXTO (fijan la expresión exacta, como los
de F-097 y F-120): matan cualquier cambio del texto, pero no demuestran que la
expresión haga lo que debe contra datos. Eso lo cubre el contraste de T8 en
PostgreSQL 16 local (`progress/impl_F-123.md`, sección T8): la previsión de la
spec sale exacta, la migración actúa una sola vez y R11 da 0 parejas. Y el
coste conocido del enfoque: una reescritura equivalente del SQL también los
pone en rojo (falso positivo, no falso verde).
