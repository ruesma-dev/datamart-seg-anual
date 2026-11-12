<!-- specs/F-162-obra-duplicada-ruesma/requirements.md -->
# F-162 · Requisitos · El seguimiento lleva TODAS las fichas de obra, cada una con su empresa

Diagnóstico de partida: `progress/explore_0721_obra_duplicada.md`. Hay dos fichas 0721, la
2759553 de Construcciones Ruesma (`con.emp` = 1, 9.165 líneas) y la 2855829 de PORSAN (empresa 28,
vacía). `stg/03_obras.sql` se queda con UNA ficha por código y elige la de PORSAN.

**Modelo del humano (2026-11-11), no se discute** (sustituye al primer planteamiento de esta spec,
«elegir una ficha»): «Debes leer los proyectos en ambas empresas. No tener que elegir: cada uno con
su propia empresa, sin cruces entre empresas. Lo que pasa es que, al preguntar la IA, hay que
decirle que puede ser el mismo proyecto en ambas empresas y que por defecto coja este. Ruesma debe
tener la obra 0721 y PORSAN también.» Y el criterio del proyecto por defecto: «en caso de duda,
Construcciones Ruesma por delante, salvo que se diga lo contrario; los datos deciden antes que la
duda». Es el modelo de F-106 (`harness/features.json`) aplicado al SEGUIMIENTO.

**Medido** (spec-author, Azure, solo lectura, 2026-11-11 16:30-16:45 UTC): el universo pasa de 585
a **634 fichas** (585 códigos); entran 49 fichas, **4 con filas de plan**: 12-0252, 25-0517,
1-0606 y 1-0721. Ninguna ficha de hoy sale. Detalle en `design.md` §5.

Fuera: recursos, partes y compras de otras empresas (se quedan en F-106); F-161 (versiones sin
`planif`, que afecta a la 0721); el modelo de Power BI, que es del humano (D3).

## Requisitos · el universo (`stg.obras`)

R1. `stg.obras` debe tener UNA fila por FICHA de obra real (`raw.obr JOIN raw.con`) de TODAS las
empresas, sin desempate: los mismos filtros de hoy (lista cerrada de códigos administrativos,
`con.cod !~ '[0-9]{5,}'`, código nulo o vacío) y ninguno más.

R2. CUANDO un código tenga fichas en varias empresas, ENTONCES `stg.obras` debe tener una fila por
cada una (la 0721: 2759553 de la empresa 1 y 2855829 de la 28).

R3. `stg.obras` debe publicar, AL FINAL y en este orden, `empresa_id INTEGER NULL` (`con.emp`),
`clave_obra VARCHAR` (`<empresa>-<codigo>`, como `maestro.v_obra_fichas`) y `es_por_defecto
BOOLEAN NOT NULL`, en el `CREATE TABLE` y en la migración de la tabla de Azure. Ninguna columna de
hoy cambia de nombre, tipo ni posición; el `INSERT` nombra sus columnas.

R4. `clave_negocio` sigue siendo `obra_id`; la clave alternativa pasa de `codigo_obra` a
`clave_obra` y a (`empresa_id`, `codigo_obra`), y `check-unicidad` la vigila.

## Requisitos · el proyecto por defecto

R5. `es_por_defecto` debe ser TRUE en exactamente UNA ficha por código: (1) la de la empresa 1 si
existe; (2) si solo hay una ficha, esa; (3) si hay varias y ninguna es de la empresa 1, la de MÁS
líneas de presupuesto (`raw.obrparpre` por `obride`, contadas antes de unir), después `tiemod`
DESC NULLS LAST y después `ide` DESC.

R6. La marca de vigente `conext` 15 NO debe intervenir en `es_por_defecto` (razonado en design §3.2).

R7. El dominio debe tener la función pura del criterio (`etl_sigrid/domain/ficha_obra.py`) y el
SQL debe seguirla criterio a criterio (test sobre el texto).

R8. `maestro.obras` debe publicar `es_por_defecto` como última columna: la de `stg.obras` para las
fichas del seguimiento y, fuera de él (códigos administrativos y de 5+ dígitos), la de
`es_ficha_principal` (D1).

## Requisitos · lo que cuelga de `stg.obras`

R9. `stg.partidas`, `stg.presupuesto`, `stg.plan_mensual`, `stg.plan_mensual_fase0` y `stg.fases`
no deben cambiar ni una fila (ya se construyen para todas las fichas).

R10. `mart`, `cierre` y lo que los lee (`tesoreria`, `retenciones`, `personal.en_seguimiento`)
deben ir por `obra_id`: cada ficha con lo suyo, sin cruces ni consolidación entre empresas. Ningún
SQL del repositorio agrega ni cruza por `codigo_obra` sin `obra_id` (medido, design §4).

R11. `mart.v_pbi_dim_obra` y `cierre.v_pbi_cierre_cabecera` deben publicar al final `empresa_id`,
`clave_obra` y `es_por_defecto`, y `obra_label` debe distinguir las fichas de un mismo código (D3).

R12. Los comandos de inspección de `main.py` que buscan en `stg.obras` por código con `fetchone`
(`list-master-cierre`, `inspect-cierre`, `inspect-indirectos-detalle`, `inspect-generales-detalle`,
`inspect-cabecera`, `inspect-planif-vs-real`) deben aceptar el código (ficha por defecto) o la
`clave_obra` (`28-0721`) por un solo ayudante, y `find-obra` debe mostrar la empresa.

## Requisitos · la IA (diccionario; `mcp-bbdd` no cambia)

R13. `R-EMPRESA-POR-DEFECTO` debe decir que el mismo código puede ser la misma obra en varias
empresas; que, sin empresa en la pregunta, una obra se lee en su ficha `es_por_defecto` y se dice;
que nunca se suman fichas de empresas distintas sin decirlo; que si la ficha por defecto no tiene
datos y otra del mismo código sí, se avisa; y su `ambito` debe alcanzar a `stg`, `mart` y `cierre`.

R14. `R-UNIVERSO-OBRA` debe dejar de decir «deduplica por `conext` 15»: `stg.obras` tiene una fila
por ficha y difiere de `maestro.obras` solo en los filtros de código. `R-CODIGO-POR-EMPRESA` debe
alcanzar a `stg.obras`, `mart.v_pbi_dim_obra` y `cierre.v_pbi_cierre_cabecera`.

R15. Las fichas de `stg.obras`, `maestro.obras`, `mart.v_pbi_dim_obra`, `cierre.v_pbi_cierre_cabecera`
y la columna `codigo_obra` de `mart.fact_seguimiento_mensual` y `cierre.fact_cierre_mensual` deben
decir que el código no es único entre empresas y cómo se llega a la ficha por defecto.

R16. Las preguntas de aceptación de «la obra X» sobre `stg`, `mart` y `cierre` (P4, P6, P7, P10,
P11, P14) deben llevar `R-EMPRESA-POR-DEFECTO` en `reglas_implicadas`, y P9 debe contar fichas
por defecto.

R17. Lo servido debe respetar `PRESUPUESTO_MAX` de `tests/test_f147_presupuesto_contexto.py` y los
topes de `test_f147_contenido.py`; el diccionario sube de versión con su nota.

## Requisitos · guardas, cobertura y features vecinas

R18. Caen a propósito, con su motivo escrito en el propio test: `test_f102_r7_stg_obras_es_identico_al_de_main`,
`test_f073_r26_no_toca_el_desempate_de_stg_obras`, `test_f102_r7_el_guarda_de_f073_sigue_en_pie` y
los dos `test_f102_r18_*`, que exigen la lista «0581, 0606, 0671, 0720» en la ficha.

R19. Las cuatro excepciones de cobertura de F-053 (0517, 0252, 0720 y 0606) deben salir y
`EXCEPCIONES_MAX` bajar de 23 a 19, una vez medido en el despliegue que no saltan.

R20. Los textos que dicen «`stg.obras` no cambia» o «elige una ficha por código» deben decir lo
nuevo: `maestro.yaml`, comentarios de `sql/maestro/00_setup.sql` y `01_obras.sql`,
`docs/ARCHITECTURE.md`, `CLAUDE.md` si lo dice y `azure-apps/datamart_seg_anual.md`.

R21. F-053 se propone cerrar como absorbida y F-106 se enmienda con el texto de design §8.

## Requisitos · medición y despliegue (MANUAL del humano)

R22. Antes y después, sobre el MISMO `raw` (job puntual sin ingesta): fichas por código, las
huellas `mart`, `cierre`, `dimension` y `plan_obra` y el recuento de design §5. Lo de hoy no
cambia; solo GANAN datos 1-0721, 12-0252, 25-0517 y 1-0606; en `dimension` y `plan_obra` solo
cambia la etiqueta `codigo_obra` de las fichas nuevas.

R23. Test de sandbox (`F162_SANDBOX_DSN`, `skip` sin él): `01_ddl.sql` y `03_obras.sql` reales
contra un `raw` mínimo con los casos de R2, R5 y R6.

R24. El despliegue y la vuelta atrás son MANUALES del humano (design §7), fuera de 00:00-05:00 UTC.
