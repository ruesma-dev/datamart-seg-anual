<!-- specs/F-162-obra-duplicada-ruesma/requirements.md -->
# F-162 · Requisitos · Hotfix: la ficha de obra que gana el desempate de `stg.obras`

Diagnóstico: `progress/explore_0721_obra_duplicada.md`. En Sigrid hay dos fichas 0721, la
2759553 (Construcciones Ruesma, `con.emp` = 1, 9.165 líneas de `raw.obrparpre`) y la 2855829
(PORSAN, empresa 28, vacía, alta del 19-10-2026). Ninguna tiene `conext` 15, así que
`stg/03_obras.sql` elige por `tiemod` la de PORSAN, y la 0721 sale del seguimiento.

**Criterio del humano (2026-11-11), no se discute:** «en caso de duda debe ir siempre por
delante Construcciones Ruesma, salvo que se diga explícitamente lo contrario». La «duda» es
SOLO cuando los datos no deciden.

**Medido** (spec-author, 2026-11-11 11:05 UTC, solo lectura, Azure): con el orden nuevo
cambian **tres** códigos y ninguno más. Detalle y arrastre en `design.md` §5.

| Código | Hoy (`obra_id`, empresa, líneas) | Con F-162 |
|---|---|---|
| 0721 | 2855829, 28, 0 | 2759553, 1, 9.165 |
| 0252 | 587639, 1, 22 | 650280, 12 (UTE CP Primo de Rivera), 28.511 |
| 0517 | 1060846, 1, 207 | 1088657, 25 (UTE Colegio Seseña), 158.737 |

Alcance: el desempate de `stg.obras`, su columna nueva `empresa_id`, las fichas y textos que
describen esa elección, y las dos excepciones de cobertura que el cambio deja sin objeto.
NO entran F-106 (seguimiento por empresa), F-161 (versiones sin `planif`), la 0606 ni la 0720.

## Requisitos · el desempate

R1. El sistema debe dejar en `stg.obras` UNA ficha por `codigo_obra`, la primera según este
orden y solo este: (1) marcada en `raw.conext` con `cod = '15'`; (2) MÁS líneas de presupuesto
(filas de `raw.obrparpre` con ese `obride`, todos los ámbitos y fases); (3) Construcciones
Ruesma (`con.emp = 1`) antes que cualquier otra empresa; (4) `con.tiemod` DESC NULLS LAST;
(5) `obr.ide` DESC.

R2. CUANDO un código tenga dos fichas sin marca 15, una con líneas de presupuesto y otra sin
ellas, más reciente y de otra empresa (el caso 0721), ENTONCES el sistema debe elegir la que
tiene líneas. Test de regresión con los datos de la 0721, en RED con el `03_obras.sql` de `main`
(`17b41ec`) y en verde con el nuevo.

R3. CUANDO dos fichas empaten en (1) y (2) y solo una sea de la empresa 1, ENTONCES el sistema
debe elegir la de la empresa 1 aunque la otra tenga `tiemod` más reciente e `ide` mayor.

R4. El sistema debe aplicar cada criterio solo cuando empatan todos los anteriores: (1) manda
sobre (2) aunque la marcada esté vacía; (2) sobre (3) aunque la de más líneas sea de una UTE;
(3) sobre (4); (4) sobre (5). Test parametrizado, un par de fichas por frontera.

R5. SI una ficha no tiene ninguna línea en `raw.obrparpre`, ENTONCES el sistema debe contarla
con 0 líneas (no NULL) y no debe perderla ni duplicarla: el recuento se agrega por `obride`
ANTES de unirlo, y la marca 15 es un `EXISTS` (dos filas cod 15 no multiplican la ficha).

R6. El sistema NO debe cambiar los filtros de código de `03_obras.sql`: la lista cerrada de
códigos administrativos, `con.cod !~ '[0-9]{5,}'`, el código nulo o vacío y `activa = TRUE`.

R7. El dominio debe tener la función pura del orden (`etl_sigrid/domain/ficha_obra.py`) y el
`ORDER BY` del `ROW_NUMBER` de `03_obras.sql` debe seguirla criterio a criterio, en el mismo
orden (test sobre el texto del SQL, como F-158 R7).

## Requisitos · la columna `empresa_id`

R8. `stg.obras` debe publicar `empresa_id INTEGER NULL`, la `con.emp` de la ficha elegida, como
ÚLTIMA columna (detrás de `_built_at`), tanto en el `CREATE TABLE` como en la migración de la
tabla que ya existe en Azure (`ALTER TABLE ... ADD COLUMN`), de modo que su posición sea la
misma en una base nueva y en Azure.

R9. El `INSERT` de `03_obras.sql` debe nombrar sus columnas (ya lo hace) e incluir `empresa_id`;
ninguna otra columna cambia de nombre, tipo ni posición.

R10. CUANDO se construya `stg.obras`, ENTONCES `empresa_id` debe ser la empresa de la ficha
elegida: 1 en la 0721, 12 en la 0252 y 25 en la 0517 con los datos de hoy (sandbox, R18).

## Requisitos · documentación

R11. La cabecera de `03_obras.sql` debe explicar el orden de R1, el criterio del humano con su
fecha, por qué las líneas van antes que la empresa (0252 y 0517) y por qué la empresa va antes
que `tiemod` (0721); y retirar los porcentajes «Caso 1/2/3» que ya no describen el orden.

R12. La ficha de `stg.obras` (`config/diccionario/stg.yaml`) debe describir la regla de R1, la
columna `empresa_id` (con su relación a `maestro.obras`) y la lista actualizada de códigos en
que `stg.obras` y `maestro.obras.es_ficha_principal` eligen distinto (design §5.4).

R13. Los textos que hoy dicen «`stg.obras` no cambia» o citan la lista vieja «0581, 0606, 0671
y 0720» deben decir la nueva: fichas de `maestro.yaml`, comentarios de `sql/maestro/00_setup.sql`
y `01_obras.sql`, `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` (design §2).

R14. El diccionario debe subir de versión en `00_global.yaml`, con su nota de cambio.

## Requisitos · guardas y cobertura

R15. La guarda `test_f102_r7_stg_obras_es_identico_al_de_main` (hash de `03_obras.sql`) debe
retirarse con su motivo escrito en el propio test: F-162 cambia el fichero a propósito y sus
tests fijan ahora el desempate. Las otras guardas de F-102 R7 y la de F-073 R26 siguen.

R16. CUANDO la 0252 y la 0517 publiquen su ficha con datos, ENTONCES sus dos excepciones de
`config/cobertura_excepciones.yaml` (las de F-053) deben salir y `EXCEPCIONES_MAX` bajar de 23
a 21 en `tests/test_f052_cobertura.py` (trinquete: solo baja).

## Requisitos · medición y despliegue (MANUAL del humano)

R17. Antes y después del despliegue, sobre el MISMO `raw` (job puntual sin ingesta), el sistema
debe medir: las fichas elegidas por código (solo cambian 0252, 0517 y 0721), las huellas
`mart`, `cierre`, `dimension` y `plan_obra` y el recuento por objeto de design §5. Fuera de esos
tres códigos, diferencia CERO; `plan_obra` idéntica entera.

R18. Test de sandbox (`F162_SANDBOX_DSN`, `skip` sin él): el `03_obras.sql` real contra un `raw`
mínimo con los casos de R2-R5 y R10. Es la prueba de comportamiento del SQL; los tests sin base
son el oráculo y el texto.

R19. El despliegue es MANUAL del humano (Azure: solo él escribe), con los pasos y la vuelta
atrás de `design.md` §6, fuera de 00:00-05:00 UTC.
