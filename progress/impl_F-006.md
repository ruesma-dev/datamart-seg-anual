<!-- progress/impl_F-006.md -->
# F-006 · Informe de implementación — bloques A, B, C y D

> Rama `feature/F-006-mcp-azure`. Alcance de este encargo: **Fase 0 (comprobar)
> y bloques A, B, C y D** de `specs/F-006-mcp-azure/tasks.md` (T3 a T14).
> Los bloques E a K **no** entran, y en particular **no se ha tocado nada de
> permisos, `REVOKE`, firewall ni Azure**, ni se ha abierto ninguna conexión a
> la base: el `.env` de este puesto apunta a `psql-albaranes-rs9k2`, servidor
> compartido con `albaranes` y `partes` en producción.

Este fichero se va escribiendo **a medida que avanza el trabajo**, no al final:
es la memoria que sobrevive a un corte de sesión.

---

## Fase 0 · Comprobación (T1, T2)

| Tarea | Estado | Comprobación |
|---|---|---|
| **T1** · DA-1 a DA-6 cerradas | ✅ ya hecha | `specs/F-006-mcp-azure/requirements.md` §12: las seis con su resolución, todas con la recomendación de la spec. Commit `962fb52` |
| **T2** · `"rigor": "critico"` en la ficha | ✅ ya hecha | Commit `cab50ab`. `bash harness/init.sh` imprime `niveles: critico, ...` y `BACKLOG.md` está al día |

`bash harness/init.sh` de partida: **verde**, 798 tests, rama
`feature/F-006-mcp-azure`.

---

## Fase RED (rigor `critico`)

Las trazas reales del fallo **antes** de existir el código, con el comando
exacto. No hay resúmenes: va la salida pegada.

### T3 · `etl_sigrid/domain/diccionario.py` — entidades y `validar()` (R2–R8)

```
$ python -m pytest tests/test_f006_formato.py -q
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_f006_formato.py _________________
ImportError while importing test module 'C:\Users\pgris\PycharmProjects\datamart-seg-anual\tests\test_f006_formato.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
..\..\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_f006_formato.py:20: in <module>
    from etl_sigrid.domain.diccionario import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.diccionario'
=========================== short test summary info ===========================
ERROR tests/test_f006_formato.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
```

---

## Evidencias

*(se completa al terminar los cuatro bloques)*

### T4 · `derivar_avisos()` y las validaciones R9 / R11 / R12

```
$ python -m pytest tests/test_f006_reglas.py tests/test_f006_formato.py -q
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_f006_reglas.py __________________
ImportError while importing test module 'C:\Users\pgris\PycharmProjects\datamart-seg-anual\tests\test_f006_reglas.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
..\..\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_f006_reglas.py:19: in <module>
    from etl_sigrid.domain.diccionario import (
E   ImportError: cannot import name 'CODIGOS_REGLAS_OBLIGATORIAS' from 'etl_sigrid.domain.diccionario'
=========================== short test summary info ===========================
ERROR tests/test_f006_reglas.py
ERROR tests/test_f006_formato.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 0.18s
```

Verde tras el código: `78 passed in 0.12s`.
