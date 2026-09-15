<!-- progress/impl_F-078.md -->
# F-078 · Materializar FactCPTipologia · informe de implementación

Rama `feature/F-078-materializar-cp-tipologia`. Rigor **`critico`**, `sdd=false`:
el contrato son los diez `acceptance` de la ficha. Sin `tasks.md`, así que el
plan va aquí arriba para que el trabajo se pueda retomar si me cortan a mitad.

## Plan de tareas (un commit por tarea, `F-078 Tn: ...`)

- **T1** · Plan en este informe y apertura de la sección F-078 en
  `progress/current.md`.
- **T2** · Fase RED del SQL: `tests/test_f078_sql.py` sobre el TEXTO del SQL
  (tres tablas, las tres vistas leyendo de ellas, la lógica de negocio movida
  verbatim). Traza del fallo pegada.
- **T3** · `sql/mart/06_cp_tipologia.sql`: las tres tablas y las tres vistas.
  `build_mart_step` encadena el fichero y **cuenta las filas** de
  `mart.fact_cp_tipologia`.
- **T4** · Fase RED + `check-cp-tipologia`: la comparación cifra a cifra de la
  vista de antes contra la tabla nueva, como comando repetible
  (`cp_tipologia_sql.py` + `main.py`), para que el criterio 3 lo pueda ejecutar
  el humano cuando la nocturna acabe.
- **T5** · Diccionario: fichas de las tres tablas nuevas, las tres vistas
  actualizadas, **`R-COSTE-CONSULTA` corregida**, referencias de `cierre.yaml`,
  `stg.yaml` y `00_global.yaml`, versión 22 con su changelog, y los tests de
  F-006 / F-079 que hoy fijan lo contrario.
- **T6** · `azure-apps/datamart_seg_anual.md` y `docs/`.
- **T7** · `bash harness/init.sh` en verde, campaña de mutación y cierre del
  informe con la sección «Evidencias».

## Estado

T1 en curso.
