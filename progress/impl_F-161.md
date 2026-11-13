# F-161 · Informe del implementer (`estandar`)

Rama `feature/F-161-versiones-sin-reparto`, worktree `agent-a6aed2aa041e4084f`, base `64b7c92`
(mismo código de `etl_sigrid/` que `491fbf1`: `git diff --stat 491fbf1 HEAD -- etl_sigrid` vacío).

## Fase RED (T1)

Tests escritos ANTES del código. Comandos y salida real (2026-11-13):

```
$ .venv/Scripts/python.exe -m pytest tests/test_f161_dominio.py -q
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.master_versiones'
ERROR tests/test_f161_dominio.py
1 error in 0.43s

$ .venv/Scripts/python.exe -m pytest tests/test_f161_sql.py tests/test_f161_diccionario.py -q
83 failed, 3 passed in 6.31s
```

Las 3 que pasan en RED son guardas de «no cambia» (D4), verdes por construcción:
`test_f161_r6_fuera_del_sello_y_de_la_ventana`, `test_f161_r10_el_resto_de_02_no_cambia` y
`test_f161_r20_ningun_objeto_nuevo_queda_pendiente`.

Trazas de los requisitos centrales:

```
$ pytest "tests/test_f161_sql.py::test_f161_r10_02_filtra_reparto_y_las_dos_fechas" --tb=short
E   AssertionError: assert 'SELECT obra_...siones_master' == 'SELECT obra_...a IS NOT NULL'
E     - sion_tex, tipo_master FROM mart.master_versiones_tipadas WHERE tiene_reparto AND version_fec_creacion IS NOT NULL AND version_fec_efectiva IS NOT NULL
E     + sion_tex, CASE WHEN version_tex IS NULL OR length(trim(version_tex)) = 0 THEN 'Sin clasificar' WHEN UPPER(version_tex) LIKE '%ABC%' ...

$ pytest "...::test_f161_r9_06_ya_no_construye_el_catalogo" "...::test_f161_r10_la_cuatrimestral_de_fin_obra_filtra_reparto" --tb=line
test_f161_sql.py:412: assert 'CREATE TABL...ones_tipadas' not in "DROP VIEW I... consulta.';"
E   assert "WHERE v.tipo_master = 'Cuatrimestral' AND v.tiene_reparto" in "SELECT v.obra_id, MAX(v.version) AS version_cuatrimestral FROM mart.master_versiones_tipadas v WHERE v.tipo_master = 'Cuatrimestral' GROUP BY v.obra_id"

Errores agregados (83 fallos):
     23 AssertionError: no existe etl_sigrid\infrastructure\postgres\sql\mart\01b_master_versiones.sql
     19 AssertionError: 01_ddl.sql no crea stg.master_versiones
     12 AssertionError: no existe etl_sigrid\infrastructure\postgres\sql\stg\10_master_versiones.sql
      2 ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.postgres.master_versiones_sql'
      2 AssertionError: assert 'todas las versiones con lineas' in 'Una fila por (`obra_id`, ... y solo versiones con fecha efectiva resuelta.'
```

`tests/test_f161_sandbox.py` no tiene fase RED propia: sin `F161_SANDBOX_DSN` hace `skip`.
