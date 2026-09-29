<!-- progress/review_F-083.md -->
# F-083 · review · el estado de la FACTURA y sus dos fechas

Revisión completa (pasada 1) de `887000b..049992b`, 12 ficheros. Árbol limpio,
HEAD `049992b307dd3aa878cb9ebaf7244c038d90a5e7`. No he tocado código ni rama.

## Veredicto: **APROBADO**

Con una condición que no es mía sino de la propia ficha: **el criterio 6 sigue
abierto** y solo lo cierra el humano (ver «Lo que falta para cerrar»). **Rigor
`estandar`, declarado**: exige fase RED, cobertura ≥ 80 % y mutación.

## Comprobado por mi cuenta, no leyendo el informe

- `bash harness/init.sh`: **exit 0**. `4879 passed, 188 skipped in 514,00 s`;
  `PUERTA COBERTURA [OK] 94,3 %` (901/955); `PUERTA TAMAÑO [OK]` (impl 220/220).
- **Contra la base (solo lectura, MCP)**: `maestro.estados_documento` con
  `tipo_documento = 15` da **21 filas y 21 `estado_id` distintos** —el par es
  único, como afirma la guarda—; `FRARET` existe; `REC` (1) y `REC_ADM` (110) se
  llaman **los dos «Recibida»**, y `APR` (10) y `APR_DG` (115) «Aprobado pago»:
  el aviso de filtrar por mnemónico y no por literal es exacto. Y
  `compras.facturas` publica hoy **165.866 filas / 165.866 `factura_id` / 3 sin
  `fecha`**: el número que el criterio 3 obliga a conservar.
- **Coherencia interna**: los 18 estados del reparto suman **exactamente
  165.866** y los que quedan bajo 50 son ocho; y 165.866 − 80 − 3,
  36.771 + 129.012 y los seis tramos del desfase dan los tres **165.783**.
- **Alcance de mutación recalculado**: `alcance_de_feature('F-083',
  base='main')` (merge-base `d6809a1`) devuelve `lineas={}`. Vacío de verdad.

## Los diez puntos pedidos con lupa

1. **Grano**: `LEFT JOIN LATERAL (… WHERE ce.tip = 15 AND ce.est = con.est ORDER
   BY ce.ide LIMIT 1) est ON TRUE` **no puede multiplicar por construcción**,
   aunque el catálogo trajera mañana un par repetido. Dos tests lo vigilan.
2. **Columnas**: comparé los alias contra los de `887000b`. Las diez de siempre
   idénticas y en su orden, las cinco al final, **`fecha` con su expresión**.
3. **La pareja**: `…la_union_es_por_la_pareja_y_nunca_solo_por_estado_id` falla
   si cae `tip = 15`, si cae `est = con.est` y si el `WHERE` se queda con una
   condición. Es el test que el criterio 2 pedía por su nombre.
4. **`con.est`, no `dcf`**: lo exige `…se_lee_de_la_superclase_con`.
5. **Las tres fechas: suficiente, no solo descriptivo.** Cada ficha dice qué es,
   de qué campo sale y **nombra a sus dos hermanas**: `fecha` → «la de ALTA,
   **no** la que el proveedor pone», «la MISMA que `fecha_alta`»; `fecha_factura`
   → «**No es `fecha_alta`** ni **`fecha`**», más un aviso de dato sucio que
   nadie pidió (desfase de −89.824 a +3.804 días: un MIN/MAX sin acotar da
   basura); `fecha_alta` → «la misma columna que `fecha`». Lo blinda
   `…cada_fecha_se_distingue_de_las_otras_dos`: no se afloja sin verlo en rojo.
6. **Aviso cruzado**: la ficha de `estado` lo dice **en su propia columna**
   nombrando `compras.vencimientos.estado_pago`, y la de `estado_pago` devuelve
   el aviso hacia `compras.facturas.estado`. Más de lo que pedía el criterio 5.
7. **Mediciones**: estado informado 165.866/165.866, 0 huérfanos, los 18 estados
   presentes y los **tres sin usar**; `fecdoc` 99,95 %; separación 77,8 %,
   mediana 4, p95 42, >90 días 3.352. Y FRARET = cero como **respuesta correcta**.
8. **Los tres tests ajenos: ninguno se relaja.** F-073: el hash se rebaselina,
   que es el caso que el guardián preveía, y sigue guardando; **comprobé que el
   `sha256` del fichero en HEAD es el que el test declara**, no uno inventado.
   F-079 R5: partir por `^version:` **corrige** el test (subir a 24 sin
   changelog seguiría fallando). F-080 R21: lo que R21 prohíbe es **publicar**
   ahí un objeto de F-080, y un comentario no publica.
9. **Cambio mínimo en el fichero de F-067**: aislé lo ejecutable, **14 líneas
   añadidas** (5 columnas, lateral de 7, un índice); las otras 33, comentario.
10. **Versión 23**: el árbol venía en 22 (la base publica 21 porque publicar es
    escritura del humano); changelog escrito y diccionario con las 15 columnas
    del SQL, en su orden, y **969** en total.

## Checkpoints

**C1** — [x] `init.sh` exit 0. [x] Los nueve ficheros del arnés existen.

**C2** — [x] Una sola `in_progress`: F-083. [x] Rama correcta. [x] `current.md`
con su sección y sus MANUAL. [x] Ninguna `done` nueva sin resumen. *Observación*:
`current.md` va por **1.153 líneas y 20 secciones**, con features cerradas
(F-072, F-073, F-078): higiene del líder al mergear, no de F-083.

**C3** — [x] Arquitectura: **ni una línea de Python de producción**; el SQL sigue
en su capa con numeración `NN_`. [x] Primera línea con la ruta en los dos
ficheros nuevos. [x] Sin `print()`, TODOs, secretos ni dependencias nuevas.
[x] Semántica Sigrid: superclase, `tip = 15` y fechas por `fn_sigrid_date`.
**C3 bis — N/A justificado**: no toca `docs/referencia/`, nada que barrer.

**C4** — [x] Los once criterios trazados (tabla abajo). [x] Ni red ni BBDD: mi
`grep` de `psycopg|httpx|requests|socket|urllib|connect\(|SigridApiClient|
PostgresClient` sobre los dos ficheros de F-083 sale **vacío**. [x] MANUAL en
`current.md` con su comando exacto. [x] Dobles: ninguno nuevo. *Observación*:
los 24 tests van **sin marca de criterio** en el nombre; la trazabilidad está en
los docstrings y la doy por buena, pero es un paso atrás respecto del `cN` de
F-081 (ver automejora).

**C4 bis** — [x] `rigor` declarado. [x] **Fase RED**: traza real,
`30 failed, 23 passed in 0,82 s` sobre el árbol en `5f2ec80`, con el
`AssertionError` completo de los tres centrales; los 23 verdes son los de
no-regresión y que pasaran ya es lo correcto. [x] **Cobertura** `[OK] 94,3 %`,
*con un matiz*: la puerta mide contra `dev`, así que esas 955 líneas son de
F-073/F-078/F-080/F-081 y **ese 94,3 % no habla de F-083**. [x] **Mutación: N/A
justificado por alcance vacío, comprobado y no leído.** La **prueba de control**
la resuelve el diff: ninguno de los 12 ficheros es Python de producción (4 son de
test; el resto `.sql`, `.yaml`, `.json`, `.md`), así que el cero es estructural y
no puede venir de un generador roto; no existe `progress/mutacion_F-083.md`, y es
correcto. **RM1–RM6 y los 60 s: N/A, no hay campaña.** [x] «Evidencias» con sus
cuatro números. **C4 ter — N/A**: no hay `harness/rutas_sensibles.json`.

**C5** — [x] `tasks.md`: **N/A justificado** (`sdd=false`); el plan de cinco
tareas vive en el informe y hay **un commit `F-083 Tn:` por tarea**. [x] Árbol
limpio. [x] `features.json` con F-083 `in_progress`, su estado real hasta que el
humano cierre el 6.

## Cobertura: criterio → test

| # | Qué lo cubre |
|---|---|
| 1 | `…publica_el_estado_de_la_factura[3]`, `…se_lee_de_la_superclase_con`, `…filtra_el_tipo_de_documento` |
| 2 | `…la_union_es_por_la_pareja_y_nunca_solo_por_estado_id` |
| 3 y 9 | `…ninguna_columna_de_siempre_desaparece[10]`, `…van_primero_y_en_su_orden`, `…fecha_conserva_su_expresion`, `…el_universo_no_se_filtra`, `…no_puede_multiplicar_filas`, `…publica_la_fecha_de_la_propia_factura`, `…de_alta_con_nombre_inequivoco`, `…salen_de_campos_distintos` |
| 4 y 11 | `…declara_que_hay_estados_sin_usar`, `…el_lateral_es_left`, `…avisa_de_que_las_dos_fechas_casi_nunca_coinciden`, + T1 del informe |
| 5 | `…nombra_las_dos_columnas_que_se_confunden`, `…el_estado_dice_que_no_es_el_del_efecto` |
| 10 | `…cada_fecha_declara_de_donde_sale[3]`, `…se_distingue_de_las_otras_dos[3]`, `…se_conserva_por_compatibilidad` |
| 6, 7, 8 | 6 **ABIERTO — MANUAL (humano)**; 7 verificado a mano en las fichas de F-067 y F-083; 8 este informe |

## Lo que falta para cerrar (no lo hace un agente)

**F-083 no pasa a `done` todavía**: el criterio 6 exige respuesta por el MCP, y el
MCP lee la tabla construida. Lo ejecuta el humano, en este orden:
`python main.py build-compras`, `check-unicidad`, `publicar-diccionario`.
`check-unicidad` es el único que confirma **en la base** lo que aquí solo se pudo
comprobar sobre el SELECT en solo lectura. Después, la pregunta del correo por el
MCP **sin explicarle nada en el prompt**.

## Dos recomendaciones (no bloquean) y una automejora

1. **`estado_codigo` y `estado_pago_codigo` no son la misma clase de cosa**: en
   `compras.facturas` el primero es el **mnemónico de texto** y el número es
   `estado_id`; en `compras.vencimientos`, `estado_pago_codigo` es el **número**
   (10 = Pagado), verificado en la base. Una frase en `estado_codigo` cerraría
   la última rendija.
2. **La ficha de F-067 sigue diciendo «26 estados» para el tipo 15** y hoy son
   **21 medidos**: cifra vieja del 2026-09-06 que F-083 editó y dejó pasar.
3. **Automejora (no aplicada)**: CONVENTIONS y C4 exigen `test_fXXX_rN_*`, que
   presupone requisitos EARS; en `sdd=false` no los hay y cada feature improvisa
   (F-078 `rN`, F-081 `cN`, F-083 ninguna). Propongo que CONVENTIONS fije
   `test_fXXX_cN_*` para `sdd=false` y que C4 lo cite.
