<!-- progress/spec_F-135.md -->
# F-135 · Mediciones de la spec (spec-author, 2026-10-09)

Todo medido el 2026-10-09 contra el Postgres de **Azure** (`sigrid_dm`, PostgreSQL
16.15) con `PostgresClient.filas_solo_lectura` (transacción `READ ONLY`), **sin el
bootstrap idempotente del cliente** (`_bootstrap_done = True` en el script: así ni
siquiera corre el `CREATE SCHEMA IF NOT EXISTS`). Ni un GRANT, ni un REVOKE, ni una
escritura. Sigrid no hizo falta: todo lo necesario ya está en `raw` y `contabilidad`.
**Aquí solo hay recuentos y agregados**: ni nombres, ni NIF, ni importes de nadie.
Scripts y salida completa: fuera del repositorio (scratchpad de la sesión), por
privacidad y porque se reproducen con las consultas de esta página.

Vocabulario (el de la spec):
- **CR** (cuenta restringida entera) = prefijos `640 641 642 643 644 645 649 465 466 476
  460 461 544 4753`. Los de Juan más `641/643/644/645` (indemnizaciones y otras
  retribuciones: «restringe de más»).
- **AP** (asiento de personal) = asiento cuyos apuntes son TODOS de clase `NORMAL` y
  que tiene algún apunte en CR **o** un concepto que casa `\mn[oóÓ]minas?\M` (medido
  con `[oó]` y `~*`; la `Ó` explícita es por si el plegado de mayúsculas no la alcanza).
- **Apunte restringido** = apunte de un AP **o** de una cuenta CR (en cualquier clase).

## 1. Base: el mayor hoy

`contabilidad.mayor`: **2.175.286 apuntes**, 791.354 asientos, 38 empresas, 2008-2026.
Ocupa **744 MB** (con índices); `saldos_cuenta_mes` 52 MB (401.565 filas);
`plan_cuentas` 20 MB. La base `sigrid_dm` pesa 35 GB. `build_contabilidad` tarda de
media **590 s** (máx. 653) en las 10 últimas nocturnas.

## 2. Por criterio de Juan (cuenta por prefijo, en todo el mayor)

| Prefijo | Apuntes | Asientos | Cuentas | Empresas | NORMAL | REGULARIZ. | CIERRE/APERT./S.INI |
|---|---:|---:|---:|---:|---:|---:|---:|
| 640 | 2.868 | 1.396 | 24 | 18 | 2.759 | 109 | 0 |
| 642 | 2.045 | 1.178 | 18 | 17 | 1.961 | 84 | 0 |
| 649 | 1.066 | 1.042 | 16 | 13 | 994 | 72 | 0 |
| 465 | 16.488 | 3.769 | 42 | 19 | 16.280 | 0 | 208 |
| 466 | 155 | 143 | 7 | 3 | 138 | 0 | 17 |
| 476 | 5.282 | 3.150 | 20 | 18 | 5.126 | 0 | 156 |
| 4751 | 9.232 | 8.271 | 68 | 32 | 8.787 | 0 | 445 |
| 460 | 1.801 | 590 | 93 | 7 | 1.417 | 0 | 384 |
| 461 | 567 | 514 | 4 | 3 | 537 | 0 | 30 |
| 544 | 226 | 96 | 15 | 2 | 127 | 0 | 99 |
| 4753 | 2.756 | 1.190 | 121 | 13 | 1.662 | 0 | 1.094 |
| 570 | 21.997 | 12.899 | 475 | 19 | 18.332 | 0 | 3.665 |
| **Total** | **64.483** | 28.135 | 903 | 38 | 58.120 | 265 | 6.098 |

Cercanas que Juan no cita: `641` 129 apuntes (102 dentro de AP), `643` 49 (46), `645` 2;
`4750` 878, `4752` 374, `4754-4759` 174 (impuestos, NO de personal: fuera).

## 3. Cómo se reconoce un «asiento de nómina» con el dato

- **No hay marca de origen**: `asi.ori` vale 0 en todos (ya medido en F-056), y la clase
  del apunte solo distingue cierre/apertura/regularización. Se reconoce **por las
  cuentas que contiene**, y el concepto ayuda poco.
- **Trampa medida**: 243 asientos NO normales (regularización, cierre, apertura) llevan
  cuentas 640-476. Si contaran como «de nómina», el asiento de regularización de cada
  empresa y año arrastraría **todo** el grupo 6 y 7. Por eso AP exige clase `NORMAL`.

| Definición (asientos NORMAL) | Asientos | Apuntes |
|---|---:|---:|
| N1: con 640/642/649 (el devengo) | 2.405 | 20.272 |
| N2: con 640/642/649/465/466/476 (devengo + pagos de nómina y de SS) | 6.880 | 46.600 |
| N2 sin N1 (solo pagos: 465 contra banco, 476 contra banco) | 4.475 | 26.328 |
| Concepto «nómina» (cualquiera) | 2.579 | 28.683 |
| Concepto «nómina» SIN cuentas N2 (se cuela con el criterio de cuentas) | 371 | 1.617 |
| N2 SIN concepto «nómina» (el concepto solo no basta) | 4.673 | 19.535 |
| Concepto «nómina» que queda fuera tras añadir 460/461/544/4753 al AP | 109 | 229 |

Lo que se cuela por cuentas (los 371 de concepto sin N2): 460 (881 apuntes), 572 (426),
626 comisiones bancarias (162), 475 (122): anticipos de nómina y sus pagos. Por eso AP
añade 460/461/544/4753 y el concepto.

**Los conceptos SÍ llevan nombres**: en 465 hay 7.279 conceptos distintos para 16.488
apuntes; en 2025, 59 de 365 apuntes de 465 contienen los apellidos de un recurso
persona de `personal.recursos`. El dato por trabajador vive en el concepto y en el pago.

## 4. Variantes (lo que la spec restringe)

| Variante | Apuntes | Asientos | Empresas |
|---|---:|---:|---:|
| V1 literal de Juan (N2 entero + 640-476, 460, 461, 544, 4753 enteras) | 51.245 | 8.678 | 25 |
| **V2 recomendada** (AP + CR enteras) | **55.504** | **8.791** | 25 |
| V2 que no está en V1 | 4.258 | 1.656 con algún apunte nuevo | |
| V1 que no está en V2 | 0 | | |

V2 es el **2,55 %** del mayor. Por ejercicio (apuntes / asientos): 2008 1.726/311 ·
2009 1.398/289 · 2010 1.164/240 · 2011 1.287/272 · 2012 1.398/283 · 2013 2.048/301 ·
2014 1.741/413 · 2015 1.519/287 · 2016 1.478/261 · 2017 3.571/332 · 2018 5.355/434 ·
2019 7.925/671 · 2020 6.796/742 · 2021 4.040/720 · 2022 3.169/661 · 2023 2.839/649 ·
2024 3.216/734 · 2025 2.872/648 · 2026 1.962/543.
Por empresa (apuntes): emp 1 35.360 (2008-2026); 28 6.446; 18 3.226; 10 2.946; 13 2.114;
4 1.198; 16 907; 27 795; 30 487; 12 474; 31 392; 23 294; 22 213; 21 188; 39 102; 17 102;
y 9 empresas más con menos de 70 cada una.

## 5. Qué SOBRA restringiendo el asiento entero (V2, dentro de N2)

Asientos N2 por tamaño: 5.027 de 1-4 apuntes, 1.051 de 5-10, 705 de 11-50, 95 de
51-200, 2 de más de 200. Apuntes de N2 por familia: personal (64x, 465, 466, 476, 475,
460, 461, 544, 570, 471) 30.492; tesorería (57x, 520, 626) 8.833; **ajenos**: grupo 4
4.207 (400, 410, 414, 430...), grupo 6 no 64 1.294, grupo 7 528, grupo 2 505, grupo 5
480, grupo 3 194, grupo 1 62. **1.906 de 6.880 asientos N2 llevan alguna cuenta ajena**
(603 de ellos con concepto de nómina): asientos mixtos (remesas que pagan nóminas y
proveedores a la vez, asientos de traspaso). Restringirlos enteros oculta ~7.270 apuntes
que no son de personal: es el «restringe de más» de Juan, y se afina después.

**Cuentas mixtas** (con apuntes restringidos y visibles), por prefijo y con más de 30
restringidos: 572 bancos 59 cuentas (7.653 restringidos / 100.302 visibles), 472 IVA
44 (1.986 / 138.722), 475 21 (1.483 / 855), 520 32 (1.271 / 56.209), 414 153 (1.266 /
12.724), 626 11 (1.030 / 23.151), 400 147 (761 / 8.239), 410 97 (718 / 3.642), 570 124
(207 / 12.031), 600 6 (152 / 173.224)... **71 prefijos** en total. Consecuencia: el
`saldo_acumulado` de esas cuentas, calculado sobre el mayor completo y filtrado después,
**delataría** lo restringido (la diferencia entre dos acumulados consecutivos menos el
importe visible). Hay que recalcularlo sobre lo visible.
Cuentas que quedan restringidas ENTERAS: 465 (42), 476 (20), 475 (126: las 121 de 4753
y 5 más de 475x cuyos apuntes caen todos en AP), 640 (24), 642 (18), 460 (93), 649 (16), 461 (4), 544 (15), 466 (7), 641
(6), 643 (3) y **19 cuentas 410** cuyos únicos apuntes están en AP.

`saldos_cuenta_mes`: **17.872 filas** (de 401.565) tienen algún apunte restringido;
11.809 enteras y 6.063 parciales (estas son las que hay que marcar `incompleto`).
`plan_cuentas`: **521 cuentas de nivel 5** bajo prefijos CR. Con forma de nombre de
persona («Apellidos, Nombre», proxy imperfecto): 4753 38 de 141, 476 17 de 32, 544 5 de
35, 466 4 de 20, 460 2 de 111; y **4751 62 de 101** (fuera de CR: ver D12).

### 570, cajas
509 cuentas de nivel 5, todas con «caja» en el nombre, 25 con forma de nombre de
persona. Con V2 tocan AP **124 cuentas 570**: 12.238 apuntes en total, **207 dentro de
AP**. Restringir esas 124 cuentas enteras (D9) ocultaría 12.031 apuntes más.

### 4751
9.232 apuntes en 68 cuentas; 1.490 dentro de N2 (17 cuentas). El resto son retenciones
de profesionales y la liquidación trimestral a Hacienda: Juan las deja fuera.

## 6. Objetos publicados y `raw` donde aparecen esas filas

| Objeto | Qué hay | Lo lee hoy el rol general |
|---|---|---|
| `contabilidad.mayor` | 55.504 apuntes V2 | sí |
| `contabilidad.saldos_cuenta_mes` | 17.872 filas | sí |
| `contabilidad.plan_cuentas` | 521 cuentas CR con nombre | sí |
| `retenciones.apuntes_contables` | **8 apuntes** de 5 AP, 4 proveedores, 19.963,11 € en valor absoluto; cuentas de retención de proveedor (`prv.cueretide`), ninguna CR; ningún concepto de nómina | sí |
| `retenciones.cuentas_proveedor` | 0 cuentas CR | sí |
| `compras.vencimientos` | 0 efectos en cuentas CR (solo facturas de compra) | sí |
| `mart`, `cierre`, `stg`, `maestro`, `descompuestos` | no leen `raw.apu` ni el mayor | sí |
| `raw.apu` | los 55.504 | **sí** |
| `raw.apa` | **100.502 de 716.007** (14 %) son reparto analítico de apuntes restringidos (`apuide` y `conide` dan la misma cifra): 920 cuentas analíticas, 56 centros | **sí** |
| `raw.pag` | **37.048 efectos en cuentas 465** (pago de nómina) a **1.015 terceros**, **34.191 con cuenta bancaria**; 4753 3; 466 1 | **sí** |
| `raw.rac` | 46.006 de 2.519.080 en AP | **sí** |
| `raw.con` | 8.522 cabeceras de AP (2.347 con concepto de nómina) y los nombres de las 521 cuentas CR | **sí** |
| `raw.asi` | totales debe/haber de cada AP (8.791) | **sí** |
| `raw.hmores` | 332.728 líneas de parte; 322.093 con precio, 321.883 con total (coste por persona) | **sí** |
| `raw.cob` | 0 en cuentas CR | sí |
| `raw.emp`, `res`, `reshor`, `emphis` | revocadas por F-068/F-074 | no |

`personal.partes_lineas` (`precio`, `importe`) y `personal.recursos_tipos_hora`
(`precio_coste`) publican el coste por persona, legible por el rol general por decisión
del 2026-09-22 (fuera del alcance de Juan: D10).

## 7. Quién lee hoy y por qué mecanismo

- `pg_roles`: un solo rol de lectura de esta base, `mcp_sigrid_dm_ro` (login). No hay
  `pbi_sigrid_dm_ro` (F-087 pendiente) ni ningún rol que represente «los que tienen ese
  rol». RLS: 0 políticas en la base.
- `information_schema.table_privileges` del rol: SELECT en **todas** las tablas de 12
  esquemas (`contabilidad` 3/3, `raw` 68/72, `personal` 6/6, `retenciones` 15/15...).
  Las 4 de `raw` sin permiso: `emp`, `emphis`, `res`, `reshor`.
- ACL (`relacl`, `nspacl`): **todas las concesiones al rol las hizo `sigrid_dm_etl`**
  (`mcp_sigrid_dm_ro=r/sigrid_dm_etl`), ninguna el administrador: la nocturna puede
  revocarlas sola. Privilegios por defecto puestos para 11 esquemas; `raw` ya no (F-068).
- La base no concede `TEMP` ni `CREATE` al rol (`datacl` solo `c`; `public` solo `U`):
  no puede crear funciones, ni siquiera en `pg_temp`.
- Mecanismo: `apply_grants` cada noche concede `PG_CONSUMPTION_SCHEMAS` (12 esquemas,
  `raw` incluido) y revoca `PG_EXCLUDED_TABLES`; `infra/sql/02_roles.sql` hace lo mismo
  al provisionar, como administrador.
- El MCP (`mcp-bbdd`) tiene su lista blanca: **`raw` está fuera**, `contabilidad`
  dentro. Pero la credencial la usa también Power BI, que no tiene lista blanca:
  `raw` hoy solo lo protege lo que el rol tenga revocado.
- `POWERBI.md` (el modelo documentado) solo lee `mart`; no prueba que ningún informe
  lea `raw` (lo comprueba el humano: D3).

## 9. Aprobada por el humano (2026-10-11)

El humano preguntó por las alternativas (vista filtrada, RLS, dos mitades, enmascarar
columnas, filtrar en el MCP), si separar en dos esquemas dificulta la lectura de la IA y
qué pegas tiene, y con las respuestas del líder APROBÓ la spec («con estas respuestas
apruebo»), con D1-D12 según la recomendación de `design.md` §8 y esta PRECISIÓN suya:

> «el rol admin debe leer como hasta hoy, el rol general, con esta restricción».

Cómo se aplica (requisito para el implementer y el reviewer):
- **Rol general** (`mcp_sigrid_dm_ro`, MCP y Power BI): `contabilidad` restringida
  (V2) y sin `raw`, como dice la spec.
- **Admin**: el dueño y el administrador de la base siguen leyéndolo todo, sin ningún
  cambio. El rol autorizado nuevo (`sigrid_dm_restringido_ro`) lee en
  `contabilidad_restringida` el mayor y sus saldos **con el mismo contenido, las mismas
  columnas y las mismas cifras que `contabilidad` tiene hoy**: ni una fila menos, ni una
  columna distinta. Se comprueba en el MANUAL (recuento y suma de debe/haber de la copia
  completa = los de `contabilidad.mayor` antes del despliegue).
- Regla dura en el diccionario: el mayor COMPLETO se lee SOLO de
  `contabilidad_restringida`; no se suman los dos esquemas.

Pendientes que NO bloquean la implementación (precondiciones del despliegue o preguntas
para Juan): D9, confirmar que ningún informe de Power BI lee `raw` (si alguno lo lee, se
aplica la variante B de D3); D11 quién tiene «ese rol»; D10 si el coste por persona de
`personal` también se restringe.
