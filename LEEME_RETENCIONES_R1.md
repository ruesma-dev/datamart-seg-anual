# Tanda R1 — Módulo RETENCIONES (+ compras ya integrado)

Archivos COMPLETOS, acumulativos sobre tus versiones reales:
main.py y config/tables_sigrid.yaml incluyen COMPRAS (C1/C2) y RETENCIONES (R1).

```
main.py                                    3.053 líneas · 42 comandos
config/tables_sigrid.yaml                  31 tablas
etl_sigrid/.../sql/compras/    (4 SQL)     sin cambios respecto a C1/C2
etl_sigrid/.../sql/retenciones/(3 SQL)     NUEVO
```

Tus 33 comandos originales intactos (verificado: 0 perdidos).

## El modelo, confirmado contra Sigrid

Una retención de garantía es un EFECTO con `retide` <> 0:

| | Tabla | Nace de | Volumen real |
|---|---|---|---|
| Se la practicamos a un PROVEEDOR | `pag` | factura compra (tip 15) | 25.124 efectos · **34,7 M€ vivos** |
| Nos la practica un CLIENTE | `cob` | factura venta (tip 11) | 2.219 efectos · **21,9 M€ vivos** |

- `tot` = importe retenido (puede ser negativo: ajustes)
- `fecven` = fecha prevista de devolución
- `fecrea` = 0 → VIVA; <> 0 → ya liquidada en esa fecha
- `cenide` = obra (en Ruesma cada obra es su propio centro de coste)
- `padide` = SIEMPRE 0 → la devolución NO encadena efectos
- La regla contractual está en `obrctr.coegar` (5.0 = 5 %), en 497 contratos

Los avales (`avr`/`ava`) NO se usan en Ruesma (0 y 1 filas): descartados.

## Instalación

1. Sustituye `main.py` y `config/tables_sigrid.yaml`.
2. Copia la carpeta `sql/retenciones/` (y `sql/compras/` si aún no la tenías).

```powershell
python main.py ingest              # trae cob, pag, rec (y compras si faltaban)
python main.py build-retenciones

python main.py inspect-retenciones --sentido PROVEEDOR
python main.py inspect-retenciones --obra 0707
python main.py inspect-retenciones --entidad GARSAN
python main.py inspect-retenciones-vencidas --sentido CLIENTE
```

`build-retenciones` no necesita stage: lee de raw directamente.

## Modelo generado

```
retenciones.tipos          catálogo (raw.rec + nombre desde raw.con)
retenciones.movimientos    1 fila por efecto, ambos sentidos unificados

retenciones.v_pbi_retencion_entidad     saldo por proveedor / cliente
retenciones.v_pbi_retencion_obra        ambos sentidos por obra + posición neta
retenciones.v_pbi_retenciones_vivas     detalle de lo aún retenido
retenciones.v_pbi_retenciones_vencidas  vencidas sin liquidar, con antigüedad
retenciones.v_pbi_retencion_resumen     foto global por sentido
```

Columnas clave de `movimientos`: `sentido`, `entidad_nombre`, `entidad_cif`,
`codigo_obra`, `importe`, `fecha_prevista_devolucion`, `fecha_devolucion_real`,
`estado` (VIVA/LIQUIDADA), `vencida_sin_liquidar`, `dias_desde_vencimiento`.

## Dos decisiones de diseño que conviene conocer

**1. Atribución a obra sin doble conteo.** La obra se resuelve primero por
`cenide` del propio efecto; si falta, por las líneas del documento origen y
SOLO si todas apuntan a la misma obra (si la factura reparte entre varias, se
deja NULL y se informa en `num_obras_documento`). Unir directamente el efecto a
las líneas multiplicaría el importe por el número de líneas de la factura.

**2. Doble lectura del saldo.** Se exponen a la vez:
- `saldo_vivo` = suma de efectos con `fecrea = 0` (lectura principal).
- `neto_practicado` = suma de todos los efectos, cargos menos abonos.

Conviven porque hay importes negativos (hasta −54.742 € en cobros): parte de
las devoluciones podrían registrarse como efecto negativo en lugar de marcarse
con `fecrea`. Si para alguna entidad las dos cifras divergen mucho, mira el
detalle en `v_pbi_retenciones_vivas`: indica que allí se usó el otro mecanismo.

## Validación realizada

Ejecutado contra PostgreSQL real con 10 escenarios: retención viva, vencida,
liquidada, importe negativo, obra por `cenide`, obra deducida por líneas,
factura multi-obra (obra NULL), y efectos sin retención (excluidos).
Todas las cifras cuadran al céntimo, incluida la posición neta por obra.

## Punto de atención para la primera ejecución real

El ratio de liquidadas es bajísimo: 608 de 25.124 en proveedores (2,4 %) y
42 de 2.219 en clientes (1,9 %). Puede ser real (las retenciones se acumulan
durante años), pero conviene contrastar un caso concreto contra Sigrid: coge
una retención que sepas devuelta y comprueba si aparece como LIQUIDADA. Si
aparece como VIVA, la devolución se registra por el mecanismo del importe
negativo y habría que cambiar la lectura principal a `neto_practicado`.
