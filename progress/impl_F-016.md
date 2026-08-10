<!-- progress/impl_F-016.md -->
# F-016 · Refuerzo de tests para los huecos de riesgo alto de F-005 — Informe del implementer

**Rama:** `feature/F-016-refuerzo-tests-f005` · **Rigor:** `estandar` ·
**sdd:** false (los criterios son los `acceptance` de `harness/features.json`)
· **Fecha:** 2026-08-10.

> Informe EN CURSO. Se escribe por secciones según avanza el trabajo.

## 1. Qué resuelve esta feature

La línea base de mutación de F-005 (`progress/mutacion_F-005.md`, generada por
F-015) dejó **101 mutantes y 55 supervivientes (45,5 %)**, de los que **6 son
de riesgo ALTO**. F-005 está declarada `critico` y hoy no pasaría su propio
nivel. Esta feature cierra **solo esos 6**, sin tocar código de producción:
lo que falta no es código, son tests.

Los seis, tal y como los nombra la línea base (§ «Los seis de riesgo ALTO»):

| # | Ubicación en la línea base (árbol de `c7500d4`) | Qué queda sin fijar |
|---|---|---|
| 1 | `config/settings.py:103` | valor por defecto de `auto_create_db` en la configuración |
| 2 | `postgres_client.py:78` | valor por defecto de `auto_create_db` en el cliente |
| 3 | `postgres_client.py:201` | la conexión administrativa se abre en autocommit |
| 4 | `fingerprint.py:334` | igualdad de valores de **texto** al comparar huellas |
| 5 | `fingerprint.py:405` | clasificación de una diferencia como **FALLO** |
| 6 | `main.py:388` | detección de un paso **fallido** del pipeline |

## 2. PENDIENTE — ficheros tocados

## 3. PENDIENTE — fase RED

## 4. PENDIENTE — campaña de mutación

## 5. PENDIENTE — Evidencias
