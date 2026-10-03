<!-- progress/impl_F-113.md -->
# F-113 · Informe del implementer · la categoría sale del capítulo

Rama `feature/F-113-categoria-capitulo-por-prefijo`. Spec aprobada el
2026-10-03: **D1 = A** (raíz por prefijo + intermedio de código exacto, manda el
más cercano), **D2 = contraste ligero** (T13-T15 fuera). Rigor `critico`.

## Fase RED

### T1 · dominio (R1-R6, R9), antes de que exista `categoria_partida.py`

```
$ python -m pytest tests/test_f113_categoria.py -q -p no:cacheprovider
________________ ERROR collecting tests/test_f113_categoria.py ________________
ImportError while importing test module 'C:\Users\pgris\PycharmProjects\datamart-seg-anual\tests\test_f113_categoria.py'.
tests\test_f113_categoria.py:25: in <module>
    from etl_sigrid.domain.categoria_partida import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.categoria_partida'
ERROR tests/test_f113_categoria.py
1 error in 0.44s
```

### T2 · R9 (el árbol publica `categoria`), con el módulo ya creado y `arbol_partidas.py` sin tocar

```
$ python -m pytest tests/test_f113_categoria.py -q -p no:cacheprovider
FAILED tests/test_f113_categoria.py::test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria[codigos0-esperadas0]
...(20 parametrizaciones de ese test)...
FAILED tests/test_f113_categoria.py::test_f113_r6_el_colapsado_pasa_la_categoria_sin_cambiarla
FAILED tests/test_f113_categoria.py::test_f113_r4_r6_intermedio_exacto_tras_un_colapsado
FAILED tests/test_f113_categoria.py::test_f113_r4_hermanos_no_se_contagian - ...
23 failed, 87 passed in 0.66s
$ python -m pytest tests/test_f113_categoria.py -q -p no:cacheprovider -k hermanos
E       AttributeError: 'Partida' object has no attribute 'categoria'
1 failed, 109 deselected in 0.25s
```

Tras T2: `pytest tests/test_f113_categoria.py tests/test_f052_arbol.py` → **135 passed in 0,42 s**.
