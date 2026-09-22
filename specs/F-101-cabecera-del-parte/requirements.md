<!-- specs/F-101-cabecera-del-parte/requirements.md -->
# F-101 · Requisitos (EARS)

HOTFIX de F-057. Pedido por Juan Romero el 2026-09-22 (tres correos). Rigor
`estandar`. **Todas las cifras de aquí están MEDIDAS el 2026-09-22/23 contra
Sigrid vivo por `sigrid-api` en solo lectura** y contra el Postgres de
desarrollo en solo lectura; el detalle está en `progress/spec_F-101.md`.

Tres hechos que gobiernan todo lo demás y que no se pueden suponer:

1. **El parte es `con.tip = 35`** (6.886 documentos). Código, descripción,
   fecha, estado, baja y última modificación salen de `raw.con`
   (R-SIGRID-CON); `raw.hmo` solo aporta `obride`, `cenide`, `ano` y `mes`.
2. **`con.cod` NO es único**: 6.886 partes con 6.258 códigos distintos, 569
   códigos repetidos que afectan a 1.197 partes. El grano es `parte_id`.
3. **El usuario que crea el parte NO existe** en `con` (19 columnas, ninguna
   de usuario) ni en `hmo` (16 columnas, ninguna de usuario). Está en
   `dbo.log` (8.472.098 filas, 35.684 de `tip = 35`), tabla NO ingerida.

## A · `personal.partes` — la cabecera

- **R1.** El sistema debe publicar `personal.partes`, una tabla con **una fila
  por cabecera de parte de trabajo** (6.886), con clave primaria `parte_id`
  igual al `ide` de origen.
- **R2.** El sistema debe publicar `codigo_parte` desde `raw.con.cod`
  (informado en las 6.886, formato `PT26/00336`).
- **R3.** SI alguien agrupa por `codigo_parte`, ENTONCES el sistema debe haber
  declarado en la ficha que **el código está repetido en 569 valores (1.197
  partes)** y que la clave es `parte_id`, no el código.
- **R4.** El sistema debe publicar `descripcion` desde `raw.con.res` (6.883 de
  6.886). NO se usa `con.tex`: solo 3 partes lo traen, 660 bytes en total.
- **R5.** El sistema debe publicar `fecha` (desde `con.fec`, 6.885 informadas,
  1 fuera de rango), `anio` (desde `hmo.ano`, 6.865 informados, **27 fuera de
  1990-2030**) y `mes` (desde `hmo.mes`, 6.884, **2 fuera de 1-12**).
- **R6.** El sistema debe publicar la obra y el centro de coste **de cabecera**
  con nombres que no se puedan confundir con los de la línea
  (`obra_cabecera_id`, 6.845 informados sobre 539 obras;
  `centro_coste_cabecera_id`, 6.839), y la ficha debe decir para qué sirve
  cada una: **la de la línea imputa coste, la de cabecera audita** (patrón
  F-093).
- **R7.** El sistema debe publicar `estado_id` (`con.est`) y `estado`
  traducido contra `raw.conest` filtrando `tip = 35`: 1 `REG` «En registro»
  (647), 3 `CER` «Cerrado» (541), 10 `IMP` «Imputado» (5.698).
- **R8.** El sistema debe publicar `activo` y `fecha_baja` desde `con.fecbaj`
  (218 partes de baja), con el mismo vocabulario que `personal.recursos`, y
  **no debe filtrar por ellos**.
- **R9.** El sistema debe publicar `fecha_modificacion` desde `con.tiemod`
  (fecha serie, 6.885 informadas), convertida con una función local del
  esquema. Época verificada por dos vías: `MAX(con.tiemod)` global = 46287,88
  → 2026-09-22, y el parte más antiguo, 39784,75 → 2008-11-21 con
  `con.fec = 20081130`.
- **R10.** El sistema debe publicar `num_lineas` y `lineas_en_otra_obra`, el
  recuento de líneas cuya obra difiere de la de la cabecera: **615 líneas en
  14 partes**. Esa columna es lo que hace contestable «en cuántos partes
  discrepan» sin escribir un JOIN.
- **R11.** El sistema NO debe publicar `hmo.feccie`, `hmo.cla` ni
  `hmo.caaide`, porque **valen 0 en las 6.886 filas**, ni `hmo.reside`,
  informado en 6.
- **R12.** MIENTRAS el usuario que crea el parte solo viva en `dbo.log`, el
  sistema NO debe publicarlo y la ficha debe declarar dónde está y por qué no
  se trae (tabla de 8,47 M de filas, no ingerida; es otra feature).

## B · `personal.partes_lineas` — el código y el texto en la línea

- **R13.** El sistema debe añadir `codigo_parte` a `personal.partes_lineas`,
  tomado de `raw.con` por `hmores.hmoide` (0 líneas de 330.941 apuntan a una
  cabecera inexistente).
- **R14.** SI alguien intenta resolverlo uniendo la cabecera, ENTONCES el test
  `test_f057_r12_obra_de_la_linea_no_de_la_cabecera` debe seguir en verde:
  **`02_partes_lineas.sql` no puede nombrar `raw.hmo`**.
- **R15.** El sistema debe decidir con cifras si ingiere `hmores.tex`, hoy
  excluido. Medido: informado en **13.390 de 330.941 líneas (4,05 %)**,
  **284.080 bytes (277 KiB)** en total, máximo 318 bytes, media 0,86 B/fila
  sobre los 320,3 B/fila que ya pesa `raw.hmores` (**+0,27 %** sobre sus 101 MB
  de datos), y presente en 2.306 de los 6.873 partes con líneas.
- **R16.** DONDE se ingiera `hmores.tex`, el sistema debe publicarlo como
  `texto_linea` y la ficha debe advertir que es **texto libre que puede llevar
  nombres de persona** (medido: «Angelita Cavero»), lo que refuerza que viva en
  `personal`, el esquema restringible.

## C · `personal.recursos_tipos_hora` — los precios de la ficha

- **R17.** El sistema debe publicar `personal.recursos_tipos_hora` desde
  `raw.reshor` (8.959 filas, 2.063 recursos, 58 tipos de hora), con clave
  primaria `reshor_id` igual al `ide` de origen.
- **R18.** SI alguien toma `(recurso_id, tipo_hora_id)` por clave, ENTONCES la
  ficha debe declarar que **hay 17 pares repetidos** (16 con el mismo precio,
  1 —recurso 947513, tipo 27— con dos precios distintos), así que la clave de
  negocio declarada es `reshor_id`.
- **R19.** El sistema debe publicar la descripción del tipo de hora
  (`auxhor.res`), su código (`auxhor.cod`) y su **unidad derivada de
  `auxhor.medide`** con el MISMO `CASE` que `02_partes_lineas.sql` (1 HORA,
  2 DIA, 3 MES, 19 UD, ELSE 'DESCONOCIDA'): 18/8/18/16 de los 60 tipos.
- **R20.** SI un tipo de hora no está en el catálogo, ENTONCES el sistema debe
  publicar la fila con unidad `DESCONOCIDA` en vez de perderla: el `JOIN` a
  `auxhor` debe ser `LEFT` (**3 filas** lo necesitan hoy).
- **R21.** El sistema debe publicar `precio_coste` (`pre`, informado en 2.037),
  `precio_venta` (`preven`, **informado en 3**, con la ficha avisándolo),
  `cantidad_defecto` (`candef`, 1.614), `cuenta_analitica_id` (`caaide`,
  3.198) y `orden` (`pos`, 8.959).
- **R22.** El sistema NO debe publicar `prenom` (decisión expresa del humano
  del 2026-09-22: distinto de 0 en **2** de 8.959 filas y podría ser nómina
  real), ni `cuaide` ni `proide`, que **valen 0 en las 8.959**.
- **R23.** El sistema debe publicar `es_por_defecto`, cierto cuando
  `res.horide` coincide con el tipo de hora de la fila (`res.horide` informado
  en 2.035 de 2.618 recursos y en 850 de 1.354 personas, 0 huérfanos contra
  `auxhor`), y la ficha debe declarar que **4 recursos tienen un defecto sin
  fila en `reshor`**, así que en ellos ninguna fila lo marca.
- **R24.** El sistema debe declarar en la ficha que **Sigrid no guarda
  histórico de precios aquí**: `reshor` no tiene fechas ni `tiemod`, así que no
  hay vigencia y estos son los precios de HOY.
- **R25.** El sistema debe declarar en la ficha, con la cifra, que el precio de
  la ficha y el imputado **no coinciden**: de 279.034 líneas comparables,
  **156.819 (56,2 %) llevan un precio distinto** del configurado. Es la
  pregunta de Juan (el caso Jaime Rabadán) y solo se contesta contra las
  líneas.

## D · Propagación e integridad

- **R26.** CUANDO se ejecuta `python main.py build-personal`, el sistema debe
  construir los dos objetos nuevos dentro de `build_personal`, y un fallo de
  ese paso NO debe bloquear la nocturna (`personal` sigue sin tener
  dependientes).
- **R27.** CUANDO se ejecuta `python main.py check-declarados`, el sistema debe
  encontrar en la base los dos objetos nuevos **sin añadir nada** a
  `config/objetos_pendientes.yaml` (hoy `[]`, y es un trinquete que solo baja).
- **R28.** El sistema debe dar ficha completa a los dos objetos nuevos y a las
  columnas nuevas de `partes_lineas` en `config/diccionario/personal.yaml`,
  con `clave_negocio` y `relaciones` para que `check-unicidad` y
  `check-relaciones` los cubran, y debe subir `version` en `personal.yaml` y en
  `00_global.yaml` (hoy 26).
- **R29.** CUANDO se ejecuta `bash harness/init.sh`, el sistema debe terminar
  en verde, con un test trazable (`test_f101_rN_...`) por cada requisito de
  arriba y sin tocar red ni BBDD.
- **R30.** CUANDO cambie lo que el proyecto expone, el sistema debe actualizar
  `azure-apps/datamart_seg_anual.md` en el mismo trabajo (hoy lista tres
  objetos de `personal`; pasarán a cinco).
