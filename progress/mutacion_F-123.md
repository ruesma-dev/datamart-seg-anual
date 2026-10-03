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

## Método (reproducible desde este informe)

- Worktree desechable (`git worktree add --detach`) del HEAD medido; por cada
  mutante: se lee el fichero, se exige que el texto ORIGINAL aparezca una sola
  vez, se sustituye por el MUTADO, se ejecutan `tests/test_f123_origenes.py`,
  `test_f097_descompuestos.py`, `test_f097_planificador.py` y
  `test_f120_factor.py` **sin `-x`** (`-q --tb=no`), se cuentan los `FAILED` y
  se restaura el fichero. Línea base antes y después. En serie: **1 worker**.
- Los pares de la tabla son los textos EXACTOS sustituidos, sin la sangría
  inicial; ` ⏎ ` es un salto de línea (el ancla de dos líneas solo hace único
  el texto: cambia la línea que difiere entre original y mutado, la segunda en
  M06 y la primera en las demás). `fichero:línea` es la línea donde empieza el
  texto original.
- 21 mutantes, todos evaluados (sin muestreo: son todo el alcance).

| Métrica | Valor |
|---|---|
| SHA de HEAD medido | `8d49a5f93edde44217bdbaa162c8cf4c0a7927d3` (lo posterior solo toca `progress/` y `tasks.md`) |
| Línea base antes / después | 280 passed, 3 skipped en **5,7 s** / 280 passed, 3 skipped en 3,3 s |
| Tiempo total (2026-10-03, sin `-x`) | **96 s**, de 3,8 a 6,2 s por mutante |
| Primera ejecución (2026-10-02, con `-x`) | 21/21 muertos en 241 s (6,0-16,3 s por mutante) |
| Workers | 1 (en serie) |
| Los 3 `skipped` | los de `azure-apps`, que no está junto al worktree |

## Resultado: 21 generados, 21 muertos, 0 supervivientes

| Mutante | Fichero:línea | Original | Mutado | Fallos | Tests que caen |
|---|---|---|---|---|---|
| M01 | `02_lineas_coste.sql:103` | `CONSTRAINT ck_lineas_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO',` | `CONSTRAINT ck_lineas_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_INICIAL',` | 3 | r5_ningun_sql_nombra_el_origen_viejo, r6_los_dos_check_son_los_origenes, F-097 r12_lineas_con_origen_restringido |
| M02 | `02_lineas_coste.sql:128` | `CONSTRAINT ck_cuadre_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO',` | `CONSTRAINT ck_cuadre_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_INICIAL',` | 2 | r5_ningun_sql_nombra_el_origen_viejo, r6_los_dos_check_son_los_origenes |
| M03 | `02_lineas_coste.sql:148` | `AND pg_get_constraintdef(oid) LIKE '%MASTER_INICIAL%') THEN ⏎ ALTER TABLE descompuestos.lineas` | `AND pg_get_constraintdef(oid) NOT LIKE '%MASTER_INICIAL%') THEN ⏎ ALTER TABLE descompuestos.lineas` | 1 | r15_migracion_de_cada_tabla[lineas-ck_lineas_origen] |
| M04 | `02_lineas_coste.sql:150` | `UPDATE descompuestos.lineas SET origen = 'MASTER_ESTUDIO' WHERE origen = 'MASTER_INICIAL';` | *(línea borrada)* | 2 | r15_migracion_de_cada_tabla[lineas-ck_lineas_origen], r16_migracion_idempotente |
| M05 | `02_lineas_coste.sql:159` | `UPDATE descompuestos.cuadre_partida SET origen = 'MASTER_ESTUDIO'` | `UPDATE descompuestos.cuadre_partida SET origen = 'MASTER_PRE_ABC'` | 1 | r15_migracion_de_cada_tabla[cuadre_partida-ck_cuadre_origen] |
| M06 | `02_lineas_coste.sql:151` | `ALTER TABLE descompuestos.lineas ADD CONSTRAINT ck_lineas_origen ⏎ CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO',` | `ALTER TABLE descompuestos.lineas ADD CONSTRAINT ck_lineas_origen ⏎ CHECK (origen IN ('ESTUDIO', 'PLANIF_JO',` | 1 | r15_migracion_de_cada_tabla[lineas-ck_lineas_origen] |
| M07 | `02_lineas_coste.sql:211` | `WHERE v.obra_id = t.obra_id AND v.fase_num = 0);` | `WHERE v.obra_id = t.obra_id AND v.fase_num = 1);` | 1 | r9_r11_estudio_excluye_las_obras_con_version_0 |
| M08 | `02_lineas_coste.sql:210` | `AND NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v ⏎ WHERE v.obra_id = t.obra_id` | `AND EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v ⏎ WHERE v.obra_id = t.obra_id` | 1 | r9_r11_estudio_excluye_las_obras_con_version_0 |
| M09 | `02_lineas_coste.sql:211` | `WHERE v.obra_id = t.obra_id AND v.fase_num = 0);` | `WHERE v.obra_id = t.partida_id AND v.fase_num = 0);` | 1 | r9_r11_estudio_excluye_las_obras_con_version_0 |
| M10 | `02_lineas_coste.sql:147` | `AND conrelid = 'descompuestos.lineas'::regclass` | `AND conrelid = 'descompuestos.cuadre_partida'::regclass` | 1 | r15_migracion_de_cada_tabla[lineas-ck_lineas_origen] |
| M11 | `02_lineas_coste.sql:158` | `ALTER TABLE descompuestos.cuadre_partida DROP CONSTRAINT ck_cuadre_origen;` | *(línea borrada)* | 2 | r15_migracion_de_cada_tabla[cuadre_partida-ck_cuadre_origen], r16_migracion_idempotente |
| M12 | `03_lineas_master.sql:89` | `CASE WHEN v.fase_num = 0 THEN 'MASTER_ESTUDIO'` | `CASE WHEN v.fase_num = 0 THEN 'MASTER_PRE_ABC'` | 2 | r4_master_0_con_su_origen_nuevo, F-097 r17_origen_de_cada_version |
| M13 | `03_lineas_master.sql:131` | `AND l.origen IN ('MASTER_ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO');` | `AND l.origen IN ('MASTER_PRE_ABC', 'MASTER_PLANIF_JO');` | 2 | r4_master_0_con_su_origen_nuevo, F-097 r21_borra_e_inserta_lineas_y_cuadre_del_lote |
| M14 | `04_elementos.sql:40` | `FILTER (WHERE origen = 'MASTER_ESTUDIO') AS lineas_master_estudio` | `FILTER (WHERE origen = 'ESTUDIO') AS lineas_master_estudio` | 2 | r7_elementos_columna_renombrada_en_su_sitio, F-097 r22_catalogo_de_elementos |
| M15 | `04_elementos.sql:63` | `a.lineas_master_estudio::INTEGER AS lineas_master_estudio,` | `a.lineas_master_estudio::INTEGER AS lineas_master_inicial,` | 2 | r7_elementos_columna_renombrada_en_su_sitio, F-097 r22_catalogo_de_elementos |
| M16 | `05_cuadre.sql:75` | `WHERE o.origen = 'PLANIF_JO'` | `WHERE o.origen = 'ESTUDIO'` | 2 | r10_cuadre_de_la_fase_viva_por_obra, F-097 r23_estudio_sustituido_por_la_planificacion |
| M17 | `05_cuadre.sql:76` | `OR NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v` | `AND NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v` | 2 | r10_cuadre_de_la_fase_viva_por_obra, F-097 r23_estudio_sustituido_por_la_planificacion |
| M18 | `05_cuadre.sql:77` | `WHERE v.obra_id = h.obra_id AND v.fase_num = 0);` | `WHERE v.obra_id = h.obra_id AND v.fase_num <> 0);` | 2 | r10_cuadre_de_la_fase_viva_por_obra, F-097 r23_estudio_sustituido_por_la_planificacion |
| M19 | `06_views.sql:66` | `FROM descompuestos.lineas WHERE origen = 'MASTER_ESTUDIO';` | `FROM descompuestos.lineas WHERE origen = 'ESTUDIO';` | 2 | r14_vistas_la_nueva_con_las_mismas_columnas, F-097 r24_cada_vista_con_su_origen |
| M20 | `06_views.sql:65` | `es_porcentaje, porcentaje, base_porcentaje, factor ⏎ FROM descompuestos.lineas WHERE origen = 'MASTER_ESTUDIO';` | `es_porcentaje, porcentaje, base_porcentaje ⏎ FROM descompuestos.lineas WHERE origen = 'MASTER_ESTUDIO';` | 1 | r14_vistas_la_nueva_con_las_mismas_columnas |
| M21 | `descompuestos.py:58` | `ORIGENES = ("ESTUDIO", "PLANIF_JO", "MASTER_ESTUDIO",` | `ORIGENES = ("ESTUDIO", "PLANIF_JO", "MASTER_INICIAL",` | 4 | r6_dominio_origenes_exactos, F-097 r12_lineas_con_origen_restringido, F-097 r22_catalogo_de_elementos, F-097 r12_los_cinco_origenes |

## Lo que esta campaña NO prueba

Los tests de F-123 sobre SQL son de TEXTO (fijan la expresión exacta, como los
de F-097 y F-120): matan cualquier cambio del texto, pero no demuestran que la
expresión haga lo que debe contra datos. Eso lo cubre el contraste de T8 en
PostgreSQL 16 local (`progress/impl_F-123.md`, sección T8): la previsión de la
spec sale exacta, la migración actúa una sola vez y R11 da 0 parejas. Y el
coste conocido del enfoque: una reescritura equivalente del SQL también los
pone en rojo (falso positivo, no falso verde).
