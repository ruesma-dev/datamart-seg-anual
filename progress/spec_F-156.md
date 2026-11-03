# F-156 · Mediciones de la spec (postventa entera)

Spec-author, 2026-11-03, 15:36-15:46 UTC (fuera de la ventana 00:00-05:00). Todo en SOLO
LECTURA: Sigrid por `sigrid-api` (`SigridApiClient.leer_sql`, `POST /api/sql/read`,
`truncated` comprobado en cada respuesta: `False` en todas salvo una de muestra con tope
2.000 que no se usa para ninguna cifra) y el Postgres de Azure con
`pg._bootstrap_done = True; pg.filas_solo_lectura(...)`. Ninguna escritura, ningún build.
Scripts en el scratchpad de la sesión (no versionados). Diseño: `specs/F-156-postventa/`.

## 1. Qué tablas existen y cuáles tienen datos (Sigrid, `sys.partitions`)

| Tabla | Filas | Qué es | ¿Entra? |
|---|---:|---|---|
| `upv` | 1.328 | Unidad Postventa (`con.tip` **707**) | sí |
| `rcp` | 22.179 | Reclamación = la incidencia = el «parte de reclamación» (`con.tip` **708**, series `RS<aa>.<mm>/`, `RP20`) | sí |
| `rcpint` | 24.909 | Intervinientes (oficio de obra, causante); **1.499 huérfanos** de `rcp` | sí |
| `tar` | 16.434 | Tareas (`con.tip` **47**); **13.767 con `rcpide`** (serie `REP2…`), 2.666 son tareas de obra sin reclamación | sí, filtrada `rcpide > 0` |
| `tarres` | 13.768 | Recurso/oficio de la tarea (`obrofcide` en el 100 %); 13.767 de tareas de reclamación | sí, filtrada |
| `obrofc` | 1.084 | Oficio de la obra con su proveedor (21 obras, 973 con proveedor) | sí |
| `auxrcp` | 3 | Clases: 0001 Vicios o defectos, 0002 Habitabilidad/Instalaciones, 0003 Estructura | sí |
| `auxtrcp` | 4 | Tipos: 0001 PREVENTA, 0002 PRIMER LISTADO POSTVENTA, 0003 POST VENTA, 0004 VISITA DE CORTESIA | sí |
| `auxofc` | 135 | Oficios | sí |
| `prmtpl` | 257 | Tipologías (la de la unidad, `upv.obrtplide`; `ubica` = ubicaciones válidas) | sí |
| `per` | 666 | Personas (contacto, quien reclama). 193 con DNI, **200 con credenciales i-Sigrid** | solo D1=A, 5 columnas, filtrada (362 referenciadas) |
| `auxgra` | 48 | Clases de gráfico (PV001-PV006 son de postventa) | sí |
| `log` | 8,59 M | Bitácora del ERP; 78.642 de los tres tipos | sí, filtrada a 659 (D8) |
| `act`, `actseg`, `actent`, `uve`, `uveref`, `auxuvetip`, `auxuvetpl`, `prm`, `cve`, `cveuve`, `alquve`, `ctd`, `rcx`, `contie`, `tartar`, `auxtarcla`, `auxacttip`, `auxacteve` | **0** | vacías | no |

Ya en `raw` y útiles: `con` (708: 23.681 filas en `raw`, **1.502 cabeceras sin fila en `rcp`**,
borradas), `conext` (entera: `RCPCLI` = referencia `PVI-` en 5.099; `02`/`03` en 7.424 sin
valor; `MR01`/`MR02` 123), `conest` (27 estados de 707/708/47), `rac`, `rcg`/`gra` (hoy solo
compras), `usu`, `prv`, `hmores`. Las candidatas `uve`/`uveref`/`auxuvetip` del backlog
están VACÍAS: la relación unidad de venta <-> unidad postventa no existe en Sigrid.

## 2. Volumen por empresa y obra

- **Empresa**: las 22.179 reclamaciones y los 15.986 enlaces de gráficos son de la empresa 1.
- **Unidades**: 1.328 en 18 obras (1.326 cuelgan de una obra `tip 42`). Estado (707): 515
  PRE «En preventa», 813 GAR «En garantía», 0 TG.
- **Reclamaciones por obra** (17 obras con alguna): 0594 4.072 · 0592 3.808 · 0627 3.154 ·
  0656 2.365 · 0620 1.970 · 0680 1.591 · 0677 1.370 · 0651 1.006 · 0634 983 · 0615 861 ·
  0609 693 · 0595 291 · 0626 7 · POSTV2 3 · 0593 1 · 0646 1 · 0642 0. 849 unidades distintas.
- **Por año** (`con.fec`; `rcp.fec` coincide salvo 5): 2020 2.758 · 2021 5.051 · 2022 6.546 ·
  2023 1.151 · 2024 1.287 · 2025 2.317 · 2026 3.069.

## 3. Columnas con datos

- **`rcp`** (22.179): hora 22.136 · propietario 16.888 · quien reclama 16.832 · contacto
  2.758 · **`tel` y `ele` 0** · `tex` 21.349 (máx. 2.484 bytes) · clase 6.950 (15.229 sin
  clase) · motivo 1.239 · forma 20.234 (valores 0: 1.945, 1: 12.810, 3: 7.424; solo el 1
  tiene nombre documentado, «Escrita») · **`fecpre` 0 · `solrcp` 0** · tipo 22.178 ·
  ubicación 22.088 · urgencia 7.434 (Normal 6.264, Urgente 1.170) · oficio 18.241.
- **`upv`** (1.328): propietario 999 · persona de contacto 994 · `fecini`/`fecfin`/`fecfin1`
  876 · `fecini2`/`fecfin2`/`fecini3` 644 · `fecesc` 816 · `fecfpl` 634 · `fecvtec` 767 ·
  `fecvtecpre` 639 · tipología 1.100 · `restel` 751 · `resele` 871 · `espacios` 637 · `tex` 3.
  Garantía: `fecfin1` de 2021-12-31 a 2027-09-18 (vigente hoy en 319), `fecfin2` hasta
  2029-09-18 (493). Para estructura solo hay inicio (`fecini3`), no fin.
- **`tar`** de reclamación (13.767): `empide` 13.365 (todos `con.tip` 43, empleado) ·
  fechas estimadas 690/457 · `feclim` 690 · `can`/`porcen` 457 · `tex` 13.767 · `priori`
  13.767. **Coste y venta a 0 en el 100 %**, sin contrato ni pedido. Estados: 20 IELA
  13.078 (cifra de toda `tar`), 21 IENV 234, 23 IREC 456; 0 en las 2.666 sin reclamación.
- **`tarres`**: solo `obrofcide` (el oficio-proveedor de la tarea); fechas, cantidades y
  estado a 0. El oficio de la tarea coincide con el de la reclamación en 12.682 de 13.767.
- **`rcpint`**: oficio de obra en el 100 %, causante 8.520, 23.592 reclamaciones citadas.

## 4. Estado e histórico (para F-132/F-153)

Catálogo (`conest`, ya en `raw`): **708** 1 SAT Sin atender · 3 PTE Pendiente · 5 TER
Terminada · 7 NPR No procede · 9 CER Cerrada. **707** 1 PRE · 5 GAR · 10 TG. **47** 19
estados (1 DELA … 43 PREC); en uso 20, 21 y 23.

| `rcp` por estado | Docs | Desde | Con paso en `rac` | Último paso = estado |
|---|---:|---|---:|---:|
| 1 SAT | 2.015 | 2021-01 | **0** | - |
| 3 PTE | 577 | 2021-06 | 577 | 577 |
| 5 TER | 3.901 | 2022-07 | 3.901 | 3.901 |
| 7 NPR | 819 | 2021-06 | 819 | 819 |
| 9 CER | 14.867 | 2020-11 | 14.866 | **14.208** |

- `rac` de 708: 37.669 pasos de 20.163 reclamaciones (2021-01-05 a hoy); en `raw` 37.644.
  Transiciones: 1→3 14.909 · 3→5 7.716 · 3→9 5.731 · 1→9 4.895 · 5→9 3.585 · 3→7 456 ·
  1→7 363 · 3→3 14. `rac` de 47: 1.156 pasos (690 tareas, hasta 2022-08); de 707: 923.
- **Los 658 CER cuyo último paso no es 9** (429 desde PTE, 229 desde TER) los cerró la
  aplicación `postventa-incidencias` (F-009): escribe `con.est` y `dbo.log`, **no `rac`**.
  Los 658 tienen en `dbo.log` su línea `Cerrar parte (postventa-incidencias)` (659 líneas,
  2026-09-11 a hoy, enlazadas por `tip` + `cod` + `emp`; `cod` es único en 708). Crecerán.
- `dbo.log` de los tres tipos: 708 57.766 · 47 18.092 · 707 2.784. Su `tex` y su `res`
  llevan el texto libre de la incidencia en las líneas de cambio de campo: no se trae entero.

## 5. Gráficos (documentos y fotos)

Mismo mecanismo que `compras.documento_adjuntos` (F-090/F-138/F-139): `rcg` (enlace) + `gra`
(metadatos, binario en `ruesma_rep`, `gra.ima` NULL en todos los de postventa).

| Tipo | Enlaces | Documentos | Clases (`gratipide`) |
|---|---:|---:|---|
| 708 reclamación | 14.459 | 8.653 | PV001 Fotos de incidencias 6.696 · **PV002 Fotos Reparaciones 4.427** · sin clase 3.343 (en 708) · PV006 Ficha inmueble · PV004 Informes |
| 707 unidad | 828 | 821 | PV006 820 · PV002 3 · 0 5 |
| 47 tarea | 699 | 682 | PV004 Informes 699 |

Total 15.986, todos empresa 1, de 2021 a 2026. Extensiones: pdf 9.133, jpg/jpeg 6.371, png
165, vídeo (mp4/mov/3gp) 188, heic 39, jfif 85, zip/rar 4, msg 2. **3.874 se llaman «PARTE
FIRMADO»**: el parte firmado por el cliente, con su **DNI manuscrito** dentro
(`azure-apps/postventa_incidencias.md` §3 bis y §7). Leerlos con el filtro: 0,5 s por
página de 10.000.

## 6. Datos personales

- Propietario (`rcp.cliide`, `upv.cliide`): `con` de tipos 40 (15.718) y 4 (1.153); su nombre
  es `con.res`. Contactos (`per`): 362 personas referenciadas; `per` trae DNI, credenciales
  i-Sigrid (`esiglog`, `esigpas`, `clamai`), direcciones y observaciones: nunca entran.
- Texto libre: patrón de teléfono en 10 `rcp.tex` y 5 `con.res` de 708; correo en 1 y 1; DNI
  0; en `tar.tex` 0. `upv.restel`/`resele` son contacto directo (751/871).

## 7. Coste de postventa

**No hay enlace incidencia -> coste en Sigrid**: `tar.costot`/`ventot` 0, `tar.ctride`/`dcpide` 0,
`hmores.taride` 0 de 335.254. El coste vive en obras de postventa (`POSTV`/`POSTV2` de la
empresa 1, `0004`/`POSTV2` de otras) —`hmores`: 6.955 líneas en POSTV2 (emp 1), 421 y 34 en
las otras— y en 81 partidas con «postventa» en el nombre (`raw.obrparpar`). Ya está en `mart`.

## 8. Coste de la ingesta y del build

Lecturas de 10.000 filas completas: `rcp` 0,9 s · `tar` 0,7 s · `rcpint` 0,2 s · `upv` entera
0,2 s · `gra` de postventa 0,5 s. Las 13 tablas nuevas suman ~78.000 filas (~10 páginas):
**~15 s de lectura y < 30 s de build** sobre una ventana de horas; < 10 MB en una base de
36 GB (disco 64 GB). Ninguna tiene `tiemod` salvo los catálogos `aux*`, y la nocturna es
`--full`: carga completa.

## 9. Lo que hay alrededor (otros repositorios)

- `postventa-incidencias` (doc en `azure-apps/postventa_incidencias.md`) LEE estas tablas y
  ESCRIBE en Sigrid (cierres, gráficos PV002, partes `RS…` con `RCPCLI = PVI-…`). Su F-048
  («los datos de posventa al datamart», `pending`) es de SU base `postventa`, no de Sigrid:
  no se solapa con F-156 y PostgreSQL no cruza bases.
- `mcp-bbdd/config/config.yaml`: `seguridad.esquemas_permitidos` es una lista fija (15
  esquemas, la fija su `test_f022_esquema_compras_restringida.py`) y `adjuntos.indice` admite
  UN objeto (`compras.documento_adjuntos`) con `origenes` por familia.
