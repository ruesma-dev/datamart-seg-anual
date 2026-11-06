<!-- specs/F-158-hotfix-devengo-negativo/requirements.md -->
# F-158 · Requisitos · Hotfix del céntimo negativo en el coste por contrato

Diagnóstico medido en solo lectura el 2026-11-05: `progress/spec_F-158.md`. Resumen: en
`_dev_reparto` (`sql/tesoreria/07_devengo_pendiente.sql`, paso 5) el pendiente y el personal de
cada partida se reparten en sus meses redondeando cada uno por su lado; con una cuota de personal
de 0,999999 el último mes queda con más personal que pendiente (1-0707, partida 392521, 2027-10:
8.249,97 frente a 8.250,02) y el paso 5 bis publica -0,05 sin contrato. La guarda R50 tumba la
transacción entera desde la nocturna del 04-11.

Alcance: SOLO el reparto del personal en los meses (paso 5) y lo que lo fija. Ni la cuota
(`cuota_personal`), ni `pendiente_personal` de la partida, ni el reparto por contratos (5 bis), ni
la guarda R50 cambian.

## Requisitos

R1. El sistema debe repartir el personal pendiente de cada partida de COSTE en los meses del
reparto POR ACUMULADO sobre el pendiente ya repartido: en el mes `m`, `ROUND(pp x A(m) / p, 2) -
ROUND(pp x A(m-1) / p, 2)`, con `p` el pendiente de la partida, `pp` su `pendiente_personal`,
`A(m)` la suma del pendiente repartido hasta `m` inclusive (orden de mes) y `A(0)` = 0.

R2. MIENTRAS la cuota de personal esté en [0, 1] y el pendiente del mes sea ≥ 0, el sistema debe
dar en cada mes `0 ≤ importe_personal ≤ pendiente del mes`.

R3. El sistema debe hacer que la suma del personal repartido de cada partida sea su
`pendiente_personal` exacta, al céntimo (la guarda de la suma del paso 5 sigue pasando).

R4. CUANDO la cuota de una partida sea 1, el sistema debe dar en cada mes un personal igual a su
pendiente; CUANDO sea 0, un personal 0 en cada mes.

R5. CUANDO una partida no tenga perfil (todo al primer mes pendiente, D19-A), el sistema debe dar
a esa única fila todo su `pendiente_personal`, como hoy.

R6. CUANDO se reconstruya `tesoreria` con los datos del caso real (la partida 392521 de 1-0707:
pendiente 57.749,95, cuota 0,999999, perfil de 12 meses), ENTONCES ningún (partida, mes) de
categoría distinta de CP debe tener `pendiente - personal` < 0, y el reparto por contrato no
debe tener ninguna fila negativa. Test de regresión con esos números, en RED con el algoritmo de
hoy (último mes 8.249,97 / 8.250,02) y en verde con el nuevo.

R7. El dominio (`etl_sigrid/domain/proyeccion_caja.py`) debe tener la función pura que hace R1 y
el SQL debe seguir su fórmula letra a letra (test sobre el texto de `07`), como
`repartir_por_contratos` con `_dev_ctr_reparto`.

R8. SI el pendiente del mes es negativo (un mes negativo del plan de V, como 1-0702 en 2026-11),
ENTONCES el sistema debe seguir mandándolo entero a la fila sin contrato, sin cambio de
comportamiento (decisión D2 de `progress/spec_F-158.md`).

R9. El sistema NO debe cambiar las guardas R14, R50 ni R58, ni la cuota, ni el pendiente de la
partida: test que las fija sobre el texto de `07`.

R10. La ficha de `importe_pendiente_personal` (`devengo_pendiente_obra_mes`) debe decir que se
reparte por acumulado sobre `importe_pendiente` y que nunca lo supera en un mes; la de
`devengo_pendiente_contrato_mes`, que la fila sin contrato solo es negativa por un mes negativo
del plan; el diccionario sube de versión (D3).

R11. El despliegue es MANUAL del humano (Azure, solo él escribe): imagen, job, `build-tesoreria`
suelto, `apply-grants` detrás y comprobación de que R50 pasa, con la vuelta atrás a `fbf43dd`
(`design.md` §6).
