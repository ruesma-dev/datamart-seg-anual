<!-- progress/mutacion_F-164.md -->
# F-164 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-164 --base main --workers 3 --con-seleccion` el 2026-11-17 14:06.

## Alcance

Origen del diff: **rama** (`95a7c022f371b5a2e62455f6dc175a64bc6e8c50` .. `feature/F-164-partes-firmados-restringidos`).

| Fichero | Líneas en alcance | Mutantes generados |
|---|---|---|
| `etl_sigrid/domain/postventa.py` | 72 | 15 |
| **Total** | **72** | **15** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 15 |
| Mutantes evaluados | 10 |
| Muertos | 10 |
| Supervivientes | 0 (0 podados sin ejecutar, 0 medidos) |
| Timeouts | 0 |
| Indeterminados | 0 |
| Timeouts repasados en serie | 0: ningún mutante agotó el reloj |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 17065.2 s |
| SHA de HEAD medido | `0311c3900358c21b7b1afe49d2f3166dc0d6b4ec` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-164_78d4hoho/wk_0` | 2990.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-164_78d4hoho/wk_1` | 3023.7 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-164_78d4hoho/wk_2` | 2995.2 |
| Media por mutante evaluado (s) | 1706.5 |
| Timeout efectivo por mutante (s) | 5400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 5400 |
| Workers | 3 |
| Un mutante por línea | sí — 15 generados → 10 candidatos, uno por línea |
| Muestreo | no: campaña completa (10 candidatos ≤ tope 100 del nivel `critico`) |
| Selección de tests | activa — mapa línea -> tests, poda y subconjuntos validados |
| SHA del mapa | `0311c3900358c21b7b1afe49d2f3166dc0d6b4ec` |
| Medición del mapa (s) | `.`: 4901.2 |
| Tests en la suite | `.`: 16058 |
| Tamaño medio del subconjunto | 74.8 tests (4 mutantes) |
| Revalidados con la suite entera | 0 (0 murieron al revalidar) |
| Subconjuntos descartados | 0 |
| Podados (sin ejecutar) | 0 |
| Tiempo ahorrado por la poda (s) — derivado: podados × línea base | 0.0 |
| Media por mutante juzgado con la suite entera (s) | 2761.7 (6 mutantes) |

## Cómo se juzgó

- **PODADO**: ningún proceso medido ejecuta la sentencia del mutante, así que no puede cambiar ninguna ejecución; es superviviente sin escribirlo ni correr nada. Un PODADO necesita la misma justificación escrita que uno medido. Riesgo residual: un subproceso que no hereda el entorno o usa otro intérprete no se mide, y sus líneas parecerían no ejecutadas; `--sin-seleccion` lo descarta.
- El **muerto** del subconjunto **no se revalida**: ese subconjunto se corrió antes SIN mutar y salió verde, así que el test que cae lo hace por el mutante, y ese test también está en la suite entera.
- Lo que el subconjunto no mata (superviviente, timeout, indeterminado) **sí se revalida** con la suite entera y el mutante aún aplicado: que no caiga ninguno de sus tests no prueba que no caiga ninguno de la suite, y el veredicto que cuenta es el de la suite entera.
- El **timeout** por mutante sigue saliendo de la **línea base** de la suite entera: es la única medida tomada con la contención de los W workers; un subconjunto no tiene base propia, medirla costaría más de lo que ahorra, y un mutante que cuelga cuelga igual con dos tests que con doscientos.


## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.


## Análisis (implementer)

**Cómo se lanzó.** La primera campaña, lanzada por el implementer anterior, murió durante
la noche del 2026-11-16 sin dejar informe. Esta la lanzó el **líder** como proceso
independiente de la sesión, sobre HEAD `0311c39` (APPROVED de la review principal, pasada 2):

```
.venv\Scripts\python.exe -m harness.mutacion --feature F-164 --con-seleccion --timeout 5400 --workers 3
```

De 09:22:23 a 14:06:52 hora local del 2026-11-17: **17065,2 s (4 h 44 min)**, `rc=0`. La
mayor parte es fija: el mapa línea -> tests (4901 s) y las tres líneas base (~3000 s cada una).

**Los 5 generados que no se evaluaron (15 -> 10).** El nivel `critico` reduce a **uno por
línea** (`reducir_por_linea`, semilla 20261030): las líneas 267, 270 y 272 tenían más de un
mutante y se sorteó uno. Quedaron fuera `267 veracidad` (`if not tip:`), `270 veracidad`
(`if not documento:`), `272 negacion` (`if not (...)`), `272 comparacion` (`not in
LISTA_ABIERTA`) y `272 logico` (`or` en vez de `and`). Lo comprobé regenerando los mutantes con
`generar_mutantes` sobre el fichero: salen exactamente esos 15.

**Reverificación EN SERIE de los 10 muertos.** Mientras F-041 siga `pending`, la campaña
paralela puede dar falsos muertos. Cada mutante se aplicó a mano, uno a uno, sobre
`etl_sigrid/domain/postventa.py` (copia de seguridad fuera del repositorio, restaurada tras
cada uno) y se ejecutó:

```
.venv/Scripts/python.exe -m pytest tests/test_f164_dominio.py tests/test_f164_sql.py tests/test_f164_diccionario.py -q -p no:cacheprovider -x
```

Sin mutar: `271 passed in 1.56s`. Al terminar, `git diff --exit-code etl_sigrid/` limpio.

| # | Línea · operador | Mutación | Primer test que cae | Muerto en serie |
|---|---|---|---|---|
| 1 | 216 · entero | `GRATIPIDE_FOTOS_INCIDENCIA` 34 -> 35 | `test_f164_r1_la_lista_abierta_son_tres_parejas` | sí |
| 2 | 217 · entero | `GRATIPIDE_INFORMES` 37 -> 38 | `test_f164_r1_la_lista_abierta_son_tres_parejas` | sí |
| 3 | 218 · entero | `GRATIPIDE_FICHA_INMUEBLE` 39 -> 40 | `test_f164_r1_la_lista_abierta_son_tres_parejas` | sí |
| 4 | 246 · logico | `(texto or "")` -> `(texto and "")` | `test_f164_r8_los_siete_partes_quedan_en_reparacion[708-34-RS25.07 - 0321 FIRMADO.pdf-PARTE FIRMADO]` | sí |
| 5 | 252 · negacion | `if not _RE_SENAL_FIRMA.search(...)` | `test_f164_r5_una_clase_nueva_no_abre_nada` | sí |
| 6 | 253 · booleano | `return True` -> `return False` | `test_f164_r8_los_siete_partes_quedan_en_reparacion[708-34-RS25.07 - 0321 FIRMADO.pdf-PARTE FIRMADO]` | sí |
| 7 | 254 · comparacion | `is not None` -> `is None` | `test_f164_r5_una_clase_nueva_no_abre_nada` | sí |
| 8 | 267 · comparacion | `if tip is None` -> `is not None` | `test_f164_r5_una_clase_nueva_no_abre_nada` | sí |
| 9 | 270 · comparacion | `if documento is None` -> `is not None` | `test_f164_r8_los_siete_partes_quedan_en_reparacion[708-None-VIV 1 - RS24.11-0123.pdf-PARTE FIRMADO]` | sí |
| 10 | 272 · not | quita el `not` de `senal_parte_firmado` | `test_f164_r8_los_siete_partes_quedan_en_reparacion[708-34-RS25.07 - 0321 FIRMADO.pdf-PARTE FIRMADO]` | sí |

Todos caen en `tests/test_f164_dominio.py` (con `-x`, el primero que falla; puede haber más).
Ninguno necesitó otro fichero de tests.

**Conclusión frente a C4 bis.** 10 evaluados, 10 muertos en la campaña paralela y los 10
confirmados en serie: **cero supervivientes, cero timeouts, ningún falso muerto**. No hay
superviviente que justificar. Los 5 no evaluados lo son por la regla de uno por línea del nivel,
no por poda ni por timeout.
