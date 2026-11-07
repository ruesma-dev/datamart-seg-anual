# F-159 · Requisitos · Hotfix 2: un mes negativo del plan de V se amplifica en el reparto

Diagnóstico medido en solo lectura el 2026-11-07: `progress/spec_F-159.md`. Resumen: el paso 5
de `sql/tesoreria/07_devengo_pendiente.sql` (`_dev_reparto`) reparte el pendiente de cada partida
en proporción a su plan de V con pesos CON SIGNO. La V13 de 1-0710 (creada en Sigrid el 06-11)
trae en la partida 404326 un plan de -1.079,94 / +1.080,00 tras el cierre: `total_perfil` 0,06 y
noviembre recibe -19.438.920,00. El paso 5 bis lo manda sin contrato y R50 tumba la noche del
07-11. Es la clase de la D2 de F-158 (mes negativo del plan) en su forma amplificada; el borde de
la observación 3 de `review_F-158.md` (último mes negativo por redondeo) está latente.

Alcance: SOLO cómo se reparte el pendiente (y el pendiente con coeficientes) de una partida en
sus meses (paso 5), su espejo en el dominio, dos guardas de diagnóstico y las fichas. Ni el plan
de `stg`, ni el pendiente de la partida, ni la cuota ni el reparto del personal (F-158), ni el
reparto por contratos (5 bis), ni la condición de R14, R50 o R58 cambian.

Decisiones recomendadas que estos requisitos asumen (D1-D6 de `progress/spec_F-159.md`): **D1 = A**
(envolvente), **D2 = acumulado**, **D3 = sí**, **D5 = v74**.

## Requisitos

R1. El sistema debe calcular, para cada partida con pendiente y perfil (los meses tras el cierre
con plan de V distinto de 0, como hoy), su plan acumulado `W(m)` en orden de mes y el peso
acumulado ENVOLVENTE `W'(m) = max(0, min de W(k) para k ≥ m)`: un mes negativo se absorbe en los
meses anteriores y `W'` nunca baja.

R2. El sistema debe repartir el pendiente `p` de la partida POR ACUMULADO sobre esa envolvente: el
mes `m` recibe `A(m) - A(m-1)`, con `A(m) = ROUND(p x W'(m) / total_perfil, 2)`, `A(0) = 0` y, en el
último mes del perfil, `A = p` sin redondear. Igual para `pendiente_con_coeficientes` (VENTA).

R3. MIENTRAS `p` ≥ 0 y tenga dos decimales, el sistema debe dar en cada (partida, mes) del
reparto `0 ≤ importe ≤ p`, y la suma de la partida debe ser `p` exacta (la guarda R14 sigue
pasando con su texto de hoy).

R4. MIENTRAS el plan de V tras el cierre no tenga meses negativos, el sistema debe dar el mismo
reparto que hoy salvo el redondeo: ningún mes salvo el último cambia más de 0,01 € y el último
recoge la diferencia (medido el 07-11: 3.040 filas cambian, ninguna más de 0,11 €).

R5. CUANDO el plan neto tras el cierre sea ≤ 0 o no haya perfil, el sistema debe mandar todo el
pendiente al primer mes pendiente marcado como retraso, como hoy (D19-A de F-140).

R6. CUANDO se reproduzca el caso real de 1-0710 (partida 404326: pendiente 1.080,00, plan
-1.079,94 en 2026-11 y +1.080,00 en 2026-12), ENTONCES el sistema debe dar 0,00 en 2026-11 y
1.080,00 en 2026-12. Test de regresión con esos números, en RED con el algoritmo de `93fc38c`
(-19.438.920,00 / +19.440.000,00) y en verde con el nuevo.

R7. El personal de cada (partida, mes) debe seguir saliendo por acumulado sobre el pendiente del
mes (F-158, `repartir_personal` sin cambios) y quedar en [0, pendiente del mes] también con
perfiles con signo (test de invariantes con semilla fija).

R8. El dominio (`repartir_pendiente` de `etl_sigrid/domain/proyeccion_caja.py`) debe hacer R1-R5
y el SQL debe seguir su fórmula letra a letra (test sobre el texto de `07`), como F-158 con
`repartir_personal`.

R9. SI tras el paso 5 algún (partida, mes) tiene pendiente negativo, o personal fuera de [0,
pendiente del mes], ENTONCES el sistema debe fallar ANTES de vaciar la obra-mes, con la obra, la
partida, el mes y el importe en el mensaje (D3).

R10. SI la guarda R50 falla, ENTONCES su mensaje debe nombrar, además de los dos recuentos, la
primera fila negativa (obra, mes, categoría, contrato, importe); su condición no cambia (D3).

R11. El sistema NO debe cambiar `stg.plan_mensual`, `importe_plan_restante` (sigue siendo el plan
de V con su signo), el pendiente ni la cuota de la partida, el paso 5 bis ni las condiciones de
R14, R50 y R58: test que las fija sobre el texto de `07`.

R12. La ficha de `importe_pendiente` (`devengo_pendiente_obra_mes`) debe decir que el reparto
sigue el plan NETO acumulado de V (un mes negativo se absorbe en los anteriores) por acumulado y
que nunca es negativo; la de `devengo_pendiente_contrato_mes` deja de decir que la fila sin
contrato puede ser negativa; el diccionario sube a la v74 (D5).

R13. El despliegue es MANUAL del humano (Azure, solo él escribe): reproducción en solo lectura
antes, imagen, job, `build-tesoreria` suelto, `apply-grants` y comprobación, con la vuelta atrás a
`93fc38c` (`design.md` §6).
