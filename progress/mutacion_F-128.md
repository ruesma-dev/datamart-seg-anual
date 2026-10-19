<!-- progress/mutacion_F-128.md -->
# F-128 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-128` el 2026-10-19 01:25.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/cabecera_compra.py` | 528 |
| **Total** | **528** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 22 |
| Mutantes evaluados | 20 |
| Muertos | 20 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 52.5 s |
| SHA de HEAD medido | `546885acdd295d4b234b3bf2088aae33acf6445a` |
| Línea base (s) — `.` | 33.2 |
| Media por mutante evaluado (s) | 2.6 |
| Timeout efectivo por mutante (s) | 120 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | sí — 20 de 22 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.


## Nota del implementer (pasada 2): suite ACOTADA, la misma para base y mutantes

Repetida el 2026-10-18 a las 23:23-23:25 UTC sobre HEAD `546885a` (el SHA de la tabla), por el
cambio 3 del review. La campaña por defecto (`python -m harness.mutacion --feature F-128
--ficheros etl_sigrid/domain/cabecera_compra.py`) no se puede usar: con 4 workers aborta con
«LÍNEA BASE SIN TERMINAR» (la suite entera no cabe en los 600 s), y el arnés indica acotarla.
Se acota a los CUATRO ficheros que importan el módulo (`grep -rl cabecera_compra`); ningún otro
test lo importa, así que la acotación no puede volver muerto a un superviviente.

La pasada 1 estaba MAL MEDIDA: `EjecutorPytest.linea_base` sustituye los `argumentos` por
`ARGUMENTOS_LINEA_BASE`, así que la base corrió la suite ENTERA (573 s) y los mutantes la acotada.
Aquí la base recibe la MISMA acotación con una subclase en el script, sin tocar
`harness/mutacion.py`. Invocación exacta (desde la raíz del repositorio, `python mut2.py`):

```python
import sys
from harness import mutacion as m
ACOTACION = ("tests/test_f128_dominio.py", "tests/test_f128_sql.py",
             "tests/test_f128_restringida.py", "tests/test_f128_diccionario.py")
class EjecutorAcotado(m.EjecutorPytest):
    def linea_base(self, timeout_s):  # la base, con la MISMA acotación que los mutantes
        return self.correr(timeout_s, (*m.ARGUMENTOS_LINEA_BASE, *ACOTACION))
ej = EjecutorAcotado(raiz=".", argumentos=["-x", "-q", "--tb=no", "-p", "no:cacheprovider", *ACOTACION])
sys.exit(m.main(["--feature", "F-128", "--ficheros", "etl_sigrid/domain/cabecera_compra.py"], ejecutor=ej))
```

**Tiempos, separados**: línea base 33,2 s (verde); «Tiempo total» 52,5 s INCLUYE la base, así que
los 20 mutantes costaron **19,3 s, ~1,0 s cada uno**, en serie (con `ejecutor` el arnés no
paraleliza: la fila «Workers 4» es el valor por defecto, no lo usado; la «media» de 2,6 s divide el
total con la base entre 20). Es coherente y no es un atajo: con `-x`, cada mutante cae ya en
`tests/test_f128_dominio.py`, el primer fichero, y nunca llega a `test_f128_diccionario.py` (el
caro: 30,6 s solo). Medido aparte con `PYTHONDONTWRITEBYTECODE=1`: recoger los cuatro ficheros
(`pytest --collect-only`) cuesta 1,0 s y correr `test_f128_dominio.py` entero, 0,9 s.
