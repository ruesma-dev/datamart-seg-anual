<!-- progress/spec_F-127.md -->
# F-127 · Informe del spec-author (2026-11-20)

Spec: `specs/F-127-mayor-analitico/`. Rama `feature/F-127-mayor-analitico` desde `dev` `2114f2e`.
Contra Azure SOLO lecturas: `raw` no está al alcance del MCP (`contexto_bbdd`: «`raw` no se consulta
desde el MCP»), así que se leyó con el cliente del ETL desde el checkout principal
(`pg = main._get_pg(); pg._bootstrap_done = True; pg.filas_solo_lectura(sql, 240)`, transacción
`READ ONLY`), sin escribir nada en ninguna base ni en el checkout. Sobre el `raw` de la nocturna
del 2026-11-20. **Ningún nombre ni NIF**: solo códigos y recuentos.

## 1. Dónde vive el mayor analítico y cómo se enlaza

| Qué | Medida |
|---|---|
| Tabla | `raw.apa` («Desglose analítico»), 722.631 filas, 2008-2026, 28 empresas (empresa 1: 685.568, 94,9 %) |
| `cenide` | 722.511 (99,98 %); 0 sin su fila en `raw.cen`; = centro de su cuenta analítica en 722.456 (44 distintos, 4 cuentas sin centro) |
| `cueide` (la cuenta ANALÍTICA, índice a `caa`; no hay `caaide` en `apa`) | 722.504 (99,98 %), 24.817 cuentas; 0 sin su fila en `raw.caa`; empresa de la cuenta = la del asiento en el 100 % |
| `apuide` | 639.034 (88,4 %); 0 huérfanos en `raw.apu` |
| `conide` | 100 %: `con.tip = 20` (asiento) en 639.034 = exactamente las filas con `apuide`; `con.tip = 32` en **83.597** filas de **5.766 asientos ANALÍTICOS puros** (código `ANA…`, 2009-01-01 a 2026-07-31, 4 empresas), sin apunte financiero |
| `obride` / `obr` / `ori` / `canal` | 0 / 142 / 0 / 0 en todas |
| Fecha | `apa.fec` = `apu.fec` en 639.030 de 639.034 |
| Asiento | `apa.conide` = `apu.asiide` en 639.008 de 639.034 (26 distintos) |
| Centro | `apa.cenide` = `apu.cenide` en 571.349: el resto es el REPARTO (34.628 apuntes con varias líneas) |
| Desglose | 472.427 apuntes con desglose; el de 470.652 (99,6 %) suma exactamente su debe y su haber |
| Concepto | `apa.res` = `apu.res` en 617.093 de 639.034 (96,6 %) |
| Tabla `Movimientos.caaide` | es la conciliación BANCARIA (Concilia Movimientos), no el mayor analítico |

**El saldo SÍ se suma.** Los 639.034 apuntes financieros enlazados son todos de clase `NORMAL` en
`contabilidad_restringida.mayor`: la analítica no tiene CIERRE, APERTURA ni REGULARIZACIÓN (567
filas mencionan «apertura», «cierre» o «regulariz» en el concepto, todas sobre apuntes NORMAL).
`debe - haber` acumulado es el saldo. No es partida doble: debe 1.072,16 M, haber 1.103,66 M (cargos
del grupo 6: 621.069 filas; abonos del grupo 7: 16.713).

## 2. Las cuentas de contrapartida (CP) de los trabajadores

`raw.res.caaconide`: 2.001 recursos, **853 cuentas CP** (423 de un solo recurso, 430 compartidas por
hasta 8). 835 tienen movimiento en `apa`: 168.121 filas, 8 centros, debe 92,33 M, haber 84,27 M.

| Origen del movimiento en una CP | Filas | Importe |
|---|---|---|
| Apunte de nómina (`640`, `642`, `641`, `649`, `465`) | 90.368 | debe 87,9 M (640: 66,3 M; 642: 21,4 M) |
| Otros apuntes (`628`, `629`, `621`, `600`, `627`… suministros, móvil, vehículo) | ~39.140 | debe ~4,6 M |
| Asientos ANALÍTICOS `ANA` (`con.tip = 32`): el abono de los partes | 38.612 | haber 84,26 M |

**El aviso de Juan, medido.** El asiento de nómina SÍ cargó las CP hasta **marzo de 2026**
(~0,9-1,1 M/mes; 859 filas en 2026-03) y **no carga nada desde abril de 2026**. El abono de los
partes (asientos `ANA`) iba a ~0,9-1,0 M/mes hasta enero de 2026, 0,73 M en febrero, 31-44 mil €/mes
de marzo a julio y **nada desde agosto**, mientras los partes (`hmores`) siguen a ~1,1 M/mes.

**Cuadre de prueba (2025)**, abono `ANA` en cada CP frente a `SUM(hmores.tot)` de los recursos con esa
CP: 238 cuentas en los dos lados, **162 cuadran al euro y 168 al 1 %**; en total 11.622.909 frente a
12.016.833 (96,7 %). Por mes, de 898.742 / 906.215 (2025-01) a 1.022.493 / 1.034.590 (2025-12).

**La obra de un abono de CP.** 5.444 de los 5.766 asientos `ANA` cargan a UN solo centro (37.202 de
las 38.612 filas CP); 316 a dos; 6 a tres o cuatro. Sus cargos: 44.985 filas, 3.633 cuentas, 470
centros, 44.981 con obra. Debe = haber en 3.637 de los 5.766 asientos `ANA`.

## 3. Las tres condiciones de restringido (R23 de F-135)

C1 = el `apuide` es un apunte restringido de `contabilidad_restringida.mayor`; C2 = el `conide` es un
asiento de personal (todos sus apuntes `NORMAL` y alguno restringido); C3 = la cuenta es una CP.

| C1 | C2 | C3 | Filas | Cuentas | Centros |
|---|---|---|---|---|---|
| no | no | no | 544.330 | 23.928 | 722 |
| no | no | sí | 77.752 | 791 | 3 |
| sí | sí | no | 10.180 | 160 | 52 |
| sí | sí | sí | 90.369 | 762 | 7 |

C1 y C2 coinciden fila a fila: 100.549 (eran 100.502 de 716.007 el 2026-10-09). **La tercera, la
nueva, añade 77.752 filas.** Restringidas: **178.301 (24,7 %), 995 cuentas, 57 centros**. Cuentas
mixtas (filas restringidas y visibles): **106**; solo restringidas 889; solo visibles 23.822. Fuera
de las 853 CP, **16 cuentas** reciben abonos en asientos `ANA` (346 filas, 531.733 €): **7 en los
centros de las CP** (324 filas, 481.679 €), con toda probabilidad CP de antes que el recurso ya no
declara; 8 en centros de obra (19 filas, 48.641 €) y 1 sin obra (3 filas), que parecen cargos
corregidos de obra (D7).

## 4. Datos personales

- **La descripción de la CP lleva el nombre del trabajador**: de 853, 207 contienen el nombre
  completo de su recurso y 758 su primera palabra (~89 %). Hoy ya la publica
  `maestro.cuentas_analiticas` (F-107), que leen el estándar y el perfil restringido (D5).
- Conceptos: en las filas de CP, 2 con el nombre completo; en los cargos de los asientos `ANA`
  (1.386 conceptos distintos), 0.
- **PENDIENTE** (la consulta pasó de 240 s): nombres en los 21.941 conceptos de `apa` que difieren del
  de su apunte. Consulta exacta, como dueño y en solo lectura, sin límite de tiempo:
  `WITH n AS (SELECT DISTINCT upper(trim(cr.res)) nom FROM raw.res r JOIN raw.con cr ON cr.ide = r.ide
  WHERE r.caaconide <> 0 AND length(trim(cr.res)) >= 10), v AS (SELECT DISTINCT upper(a.res) t FROM
  raw.apa a JOIN raw.apu p ON p.ide = a.apuide WHERE a.res IS DISTINCT FROM p.res) SELECT count(*),
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM n WHERE strpos(v.t, n.nom) > 0)) FROM v;`

## 5. Coste contra la ventana nocturna

`raw.apa` ocupa 130 MB. El SELECT equivalente al build del mayor completo (todas las uniones, las tres
condiciones y los dos acumulados) da 722.631 filas = `count(DISTINCT ide)` en **4,0 s**.
`build_contabilidad` tardó 1.029-1.194 s en las cinco últimas noches; la nocturna, 303-321 min
(fin 05:04-05:21 UTC). Estimado: **+1 a 3 min** (CREATE, índices, dos copias) y **~0,5 GB** de disco
(el mayor completo ocupa 780 MB por 2,17 M filas), sobre 37 GB de base. Se mide en T13.

## 6. Hallazgos para el líder

1. **Pasar F-127 a `spec_ready` pone en rojo `tests/test_f135_sql.py::test_f135_r23_…`**, que exige
   `status in ("pending", "todo")`. Es un test de otra feature: el spec-author no lo toca. Arreglo
   propuesto, como el del 2026-11-19: que acepte también los estados del flujo SDD.
2. La obligación de F-141 («añadirlo a `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES`») está superada por
   F-146: publicado en `contabilidad`, el perfil restringido no lo ve por esquema, y añadirlo a la
   lista HARÍA FALLAR la nocturna (R7 rechaza excluir lo de un esquema que no se le concede). D3.
3. La fuga de nombres por `maestro.cuentas_analiticas` es anterior a F-127 (D5).

## Preguntas a Juan (borrador, NO enviado)

> Juan, preparando el mayor analítico (las cuentas CP de los trabajadores) hemos visto tres cosas
> en Sigrid que solo tú puedes aclarar:
>
> 1. **Nómina en las CP.** El asiento de nómina sí cargaba las cuentas CP hasta marzo de 2026
>    (alrededor de 1 M€ al mes) y desde abril ya no. ¿Fue un cambio decidido en abril? Para leer el
>    saldo de una CP, ¿a partir de qué fecha vale tu aviso de que la nómina no entra?
> 2. **Imputación de partes.** El asiento analítico que imputa los partes a las obras (los
>    asientos «ANA», que abonan la CP) se hacía cada mes hasta enero de 2026; desde marzo casi no
>    hay y desde agosto ninguno, mientras los partes siguen registrándose (~1,1 M€ al mes).
>    ¿Se ha dejado de hacer, está pendiente o se hace ahora de otra manera?
> 3. **«Lo que queda por repartir».** ¿Es el saldo de la CP (lo cargado por nómina menos lo
>    abonado por partes) en un periodo? ¿Qué periodo quieres ver?
