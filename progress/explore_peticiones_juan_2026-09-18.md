# Exploracion — las tres mediciones de la 4a devolucion de Juan Romero

Fecha: 2026-09-18 · Solo lectura contra Sigrid via `sigrid-api`. Sin escrituras,
sin tocar el ETL, sin commit. Cifras medidas hoy, no estimadas.

Base de referencia medida: **166.009 facturas de compra** (`con.tip = 15`, y
`dcf` tiene exactamente las mismas 166.009 filas). El encargo hablaba de
165.866; la diferencia son las altas de estos dias.

## 1 · El enlace factura -> asiento: EXISTE y es casi total

**La tabla es `rac` ("Contabilizacion de documentos"), que HOY NO SE INGIERE.**
No es `apu.doc`, ni `apu.jus`, ni un `docide` en `asi`.

### Los candidatos del encargo: descartados con cifra

Sobre las 2.163.486 filas de `apu`: **`apu.doc` informado en 7.016 (0,32 %)**,
**`apu.jus` en 0**, **`apu.docnum` en 0** y `apu.empide` en 1.027.534 (47,5 %),
que ademas es la ENTIDAD, no la factura. `asi` no tiene ninguna columna de
documento: sus 7 columnas son `ide`, `deb`, `hab`, `ori`, `canal`, `cptide`,
`pexide`. Hipotesis probada y **negativa**: no hay enlace factura->asiento
dentro de `apu` ni de `asi`.

### El enlace que si existe

`rac`: 2.503.151 filas, 16 columnas escalares salvo `tex` (`ide`, `conide`,
`asiide`, `res`, `est1`, `est2`, `usu`, `fec`, `hor`, `dogide`...). Es el **log
del flujo de aprobacion** de cualquier documento: `conide` es el documento,
`asiide` el asiento que genero el paso, `res` el nombre del paso.

- **165.845 de 166.009 facturas tienen asiento: el 99,90 %.**
- Grano limpio: **exactamente 1 fila con `asiide <> 0` por factura** (165.845,
  ninguna con 2) y **1 sola factura por asiento** (165.845 asientos, todos con
  n = 1). No multiplica en ninguno de los dos sentidos.
- Las 165.845 casan al 100 % contra `asi` (`LEFT JOIN`, cero huerfanos).
- Las 868.913 filas de `rac` sobre facturas son los pasos del circuito
  (`Comprobar factura` 129.878, `Aprobar factura` ~500.000, **`Contabilizar
  factura` 130.861, de las que 129.825 traen el asiento**).
- Las **164 facturas sin asiento** (0,10 %) son la cola viva: 29 de 2026 con
  `est` 20/25 (pendientes hoy mismo) y el resto en goteo por 17 anios.

El resto de la cadena ya esta ingerido: `apu.asiide` da los apuntes (**595.258
cuelgan de asientos de factura**, 27,5 % de `apu`), `apu.cueide` la cuenta
(**595.257 de 595.258 informados, casan al 100 % contra `cua`**, ya ingerida) y
`apu.cenide` el centro de coste (209.488, 35,2 %).

### La fecha real de contabilizacion: hay DOS, y no son la misma

1. **Fecha contable del asiento** = `con.fec` del asiento. Y **no hacen falta
   dos saltos**: `apu.fec` coincide con `con.fec` del asiento en **2.163.189 de
   2.163.486 apuntes (99,99 %)**, cero apuntes sin fecha. Esto **corrige la
   ficha de F-056**, que daba por hecho el doble salto.
2. **Fecha operativa** = `rac.fec` (cuando el usuario lanzo el paso, con
   `rac.usu` al lado). Coinciden solo en 12.056 de 165.845 (7,3 %): `rac.fec`
   es posterior en 153.409 (92,5 %) y anterior en 380. Repartida: mismo dia o
   antes 12.436, **mismo mes 133.389 (80,4 %)**, mes posterior o mas 20.020.

Negocio querra la (1) para cuadrar con contabilidad y la (2) para medir el
retardo del circuito. Publicar las dos cuesta lo mismo.

### Ruta alternativa: `regiva`, mas pobre

`regiva` (Registro de IVA, tampoco ingerida): 307.266 filas, `apuide` al 100 %,
`docide` al 98,4 %, `asifec` al 100 %, y toca **165.834 facturas (99,89 %)**.
Pero **abre en abanico** (una fila por tipo de IVA) y al cruzarla con `rac`
solo 199.502 de 284.023 combinaciones (70,2 %) apuntan al mismo asiento. Util
para el IVA soportado, no como enlace principal. **`rac` gana.**

### Lo que NO cuadra todavia (dicho con la cifra)

Facturas de 2025: `dcf` suma bases 113.357.327, IVA 6.839.148, `totdoc`
120.196.475 y `tot` 117.065.836. El **debe** de los apuntes de esos asientos
suma **136.099.465**, un **13,2 % por encima de `totdoc`**. El saldo
(debe - haber) es 0: los asientos cuadran solos. Hipotesis sin comprobar: los
abonos (serie `AB`) invierten debe/haber y el `SUM(deb)` los suma en vez de
restarlos. **La feature cierra ese cuadre antes de publicar importes; el enlace
en si no esta en duda.**

## 2 · El documento adjunto: SI ESTA EN SIGRID, en 103.799 facturas

Juan barrio el diccionario del datamart y no encontro nada. Correcto: no esta
publicado. **Pero en Sigrid si esta**, en dos tablas que no se ingieren.

- **`gra`** ("Graficos"): **285.735 filas**; utiles `nom` (varchar 255, nombre
  del fichero), `nomori`, `cod` (varchar 128, clave del repositorio), `fec`,
  `usu`, `cla`, `ima` (binario), `vin`.
- **`rcg`** ("Graficos en conceptos"): **286.150 filas**, 7 columnas escalares
  (`ide`, `con`, `gra`, `pos`, `cla`, `feclee`, `fecalt`). Puente concepto <->
  grafico, 201.026 conceptos distintos.

### Que guarda exactamente

**No es el binario y no es una ruta de red: es un identificador de repositorio
externo.** Medido sobre las 285.735 filas de `gra`:
`vin <> 0` (vinculado) en **285.697 (99,99 %)** y **solo 71 filas (0,02 %)
llevan el binario dentro** (`DATALENGTH(ima) > 0`, 12,8 MB en total): el
contenido real vive fuera. `cod` informado al 100 % y **practicamente unico
(285.734 valores distintos sobre 285.735 filas)**, con forma medida
`202609181420515461.jmbecedas` = marca de tiempo + usuario que subio el
fichero. `nom` informado en 285.726 (99,997 %), max. 171 caracteres, muestra
real de facturas `telefonica d 4328 09 OFICINA 915135156.pdf`, y **casi todo
`.pdf`**: las 12 terminaciones mas frecuentes en facturas son `*.pdf`. La raiz
fisica del repositorio **no esta en la base**: la unica candidata,
`sisapl.ruta`, esta **vacia (0 filas)**; es configuracion de la aplicacion.

### Cobertura sobre facturas

**103.799 de 166.009 facturas (62,5 %) tienen al menos un adjunto**, con
132.094 relaciones en `rcg` (1,27 por factura: 80.038 con 1, 21.547 con 2,
2.214 con 3 o mas, maximo 25). Por anio la historia es nitida: **cero hasta
2016**, arranque en 2017 (491 de 7.921) y 2018 (1.545 de 12.072), y **desde
2019 del 93 al 99 %**: 2019 11.665/13.787 · 2020 11.521/12.327 · 2021
11.653/11.932 · 2022 10.549/10.698 · 2023 13.542/13.780 · 2024 15.341/15.599 ·
2025 15.120/15.317 · 2026 12.368/12.455. **De 2019 en adelante: 101.759 de
105.895 = 96,1 %**, que es justo el tramo util para lo que Juan pide.

### Lo que NO sirve, una linea cada uno

- **`arc`** ("Archivo de disco"): **0 filas**. Vacia.
- **`dog`** ("Documento"): 58.340 filas, pero **`conide`, `entide` y `obride` a
  0 en el 100 %** y **ninguna cuelga de una factura**: es el documental de
  homologacion (24,4 GB declarados en `gratam`, cero binario dentro). Su puente
  **`condog`** tiene **16 filas**, 13 conceptos y **0 facturas**.

## 3 · El maestro de productos: existe, con nombre; la familia NO es `auxfam`

- **`pro`: 55.179 filas, 108 columnas.** Confirmado lo que manda
  `R-SIGRID-CON`: **`pro` NO tiene `cod` ni `res` ni `nom`** (verificado en
  `INFORMATION_SCHEMA`). Es Propiedad de `con` y el nombre sale de ahi.
- El JOIN por `ide` es perfecto: **0 productos huerfanos**, `con.cod` informado
  en 55.179 (100 %) y **`con.res` en 55.165 (99,97 %)**.
- **`pro.famide` esta a 0 en las 55.179 filas y `auxfam` tiene 0 filas.** La
  familia por esa via **no existe**. Hipotesis del encargo: descartada.
- La clasificacion viva es **`pro.natide` -> `auxpronat`** (Naturaleza del
  producto), **informada en 54.609 de 55.179 (98,97 %)**, 294 naturalezas en
  uso sobre 514 del catalogo, y `auxpronat` **ya se ingiere**. Aviso medido:
  sus literales estan duplicados —514 filas, solo **334 `res` distintos**—, asi
  que agrupar por `natide` no es agrupar por nombre; decidirlo en la spec.
- Cobertura en lineas: **`dcfpro`** 1.094.551 lineas, 997.435 con `proide`
  (91,1 %), **las 997.435 casan contra `pro` (100 %)**; **`dcapro`** 1.153.191
  lineas, 1.147.673 con `proide` (99,5 %), **las 1.147.673 casan (100 %)**.
- Nada que ingerir: `pro`, `con` y `auxpronat` ya estan en `raw`. **Es trabajo
  de capa de negocio, no de ingesta.**

## Resumen para fichar las features

| peticion | veredicto | coste de ingesta |
|----------|-----------|------------------|
| Factura -> asiento -> cuenta | **VIABLE, 99,90 %** | ingerir `rac` (2,5 M filas, 16 col.). `asi`, `apu`, `cua` ya estan |
| Fecha de contabilizacion | **VIABLE, dos fechas** | ninguna extra: `apu.fec` ya vale (99,99 %); `rac.fec`+`rac.usu` vienen con `rac` |
| Documento adjunto | **VIABLE: 62,5 % global, 96,1 % desde 2019** | ingerir `gra` **excluyendo `ima`, `pul`, `tex`, `cam`** y `rcg` (286 k filas) |
| Maestro de productos | **VIABLE, 99,97 % con nombre** | **cero**: `pro`, `con` y `auxpronat` ya ingeridos |

Cuatro advertencias para quien redacte las specs: (1) `rac` **no tiene
`tiemod`**, igual que `apu`, asi que se trae entera o no se trae; (2) `gra`
tiene dos columnas `image` (`ima`, `pul`) y dos `text` (`tex`, `cam`) que hay
que excluir en `tables_sigrid.yaml`; (3) el desfase de importes del 13,2 % en
2025 se cierra **antes** de publicar euros; (4) `gra.cod` es el identificador,
pero la **raiz del repositorio no esta en la base** y hay que preguntarsela a
Sistemas para construir un enlace navegable.
