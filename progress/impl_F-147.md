# F-147 · Informe del implementer

> Presupuesto del contexto del MCP: resumen y entrega por regla, contenido
> revisado, enrutado a 2 preguntas y una puerta con trinquete. Rama
> `feature/F-147-presupuesto-contexto-mcp`. Rigor `estandar`.

## T2 · Medida ANTES (árbol de `main` = v58 publicada)

Fórmula de R17 (lo que `contexto_bbdd` servirá ENTERO; sin los rótulos de
`mcp-bbdd`). Script: `medir_antes.py` en el scratchpad de la sesión (lee el
árbol con el cargador real y `filas_contexto`).

| Parte | Hoy (MCP sin F-029: reglas enteras, todas las preguntas) | Fórmula R17 sobre la v58 |
|---|---:|---:|
| Reglas (27) | 46.287 (`codigo+titulo+regla+motivo`) | 2.233 (sin `resumen`: solo código y título) |
| Enrutado (114 fichas, 283 preguntas) | 18.102 | 13.886 (2 primeras) |
| Bloques de `_meta.diccionario_contexto` | 13.668 | 13.668 |
| **Total** | **78.057** | 29.787 (no comparable: aún no hay resúmenes) |

Bloques: `esquemas` 10.549, `convenciones` 1.367, `ordenes_de_magnitud` 1.264,
`ejes` 453, `ocultar` 35.

**Azure (solo lectura, `_bootstrap_done = True` + `filas_solo_lectura`,
2026-10-22)**: v58, hash `65df8f9a7a01`, 234 objetos, 27 reglas. Reglas 46.287
(regla 29.401 + motivo 14.653); bloques 13.668 (mismas cifras por bloque);
enrutado 114 fichas, 283 preguntas: 2.913 de claves + 15.189 de preguntas =
18.102 (con 2 por ficha, 2.913 + 10.973 = 13.886). **Coincide al carácter con
el árbol.** Columnas hoy de `_meta.diccionario_reglas`: `codigo, titulo,
severidad, ambito, regla, motivo, orden`.

`contexto_bbdd()` entero NO se pudo medir: el conector MCP `bbdd-ruesma-azure`
no conecta en esta sesión (404). Los ~86.000 de la spec (78.057 + rótulos y
epígrafes de `mcp-bbdd`) siguen siendo la referencia; la medida servida
después del despliegue es MANUAL (T14).
