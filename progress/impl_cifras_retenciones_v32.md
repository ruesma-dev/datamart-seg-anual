# Cifras de `retenciones` tras el primer build de F-095 · diccionario v32

Tarea sin feature, pedida por el humano el 2026-09-25. Rama
`chore/cifras-retenciones-v32` desde `main` (26503b9). Solo texto: ningun SQL,
ninguna clave ni estructura de ficha cambiada.

## Que cambio

- `config/diccionario/retenciones.yaml` (fichas de F-095):
  - `cuentas_proveedor`: 2.250 cuentas el 2026-09-25; 1.669 con apuntes.
  - `apuntes_contables`: 49.520 apuntes; cierre/apertura 8.870 por lado; R5 0
    cuentas fuera (sobre las 1.669 con apuntes); reparto real de `via_obra`
    (sustituye la «verificacion MANUAL»); clases ALTA 26.852 / 25,72 M, BAJA
    4.856 / -17,58 M, SALDO_INICIAL 72 / 642.775,50; prescrito 329.278,72.
  - `saldo_contable`: total 8.778.606,70 (6.468 filas, 1.669 proveedores);
    **fila sin obra -1.739.408,96** (sustituye la «verificacion MANUAL»).
  - `fin_obra`: 198 / 150 de 922 y cobertura y plazo sobre la viva remedidos.
  - `v_cuadre_proveedor`: reparto e importes reales por categoria; FERMALUX
    comprobado.
  - Las cifras de la spec y del 2026-09-24 quedan como «Historico» con fecha.
- `config/diccionario/00_global.yaml`: `version: 32`, entrada de changelog en
  la cabecera y `fuente` del orden de magnitud contable con la cifra del 25-09
  y un aviso nuevo (una cifra de ~10,5 M EUR es haber sumado solo por obra).
  `valor_aproximado` sigue en 8760000 (lo fija `tests/test_f095_...:843` y
  8,78 M esta dentro del orden).

## Medicion (SOLO LECTURA, Postgres del `.env`, 2026-09-25 ~06:50 UTC)

Sobre el build `build_retenciones` SUCCESS 05:48:30-05:49:35 UTC (de
`_meta.etl_runs`). Conexion con `filas_solo_lectura` (transaccion `READ ONLY`)
y sin auto-bootstrap. Todas las cifras del lider cuadran al centimo.

| Medida | Resultado |
|---|---|
| Apuntes / cuentas con apuntes / R5 | 49.520 / 1.669 / 0 |
| Altas por via | FACTURA 21,38 M (83,1 %), APUNTE 2,57 M (10,0 %), PUO 0,14 M, EFECTO 0,01 M, SIN_OBRA 1.620.277,30 (6,3 %) → con obra 93,7 % |
| Bajas por via | APUNTE -12,16 M (69,1 %), PUO -0,65 M, EFECTO -0,62 M, FACTURA -0,17 M, SIN_OBRA -3.989.080,14 (22,7 %) → con obra 77,3 % |
| `saldo_contable` total | 8.778.606,70 (6.468 filas) |
| Fila sin obra | 590 filas (476 con saldo ≠ 0), **-1.739.408,96**; con obra 10.518.015,66 |
| Viva en efectos (PROVEEDOR) | 7.765 efectos, 8.362.932,53 |
| Cuadre (diferencia) | CUADRA 520 (5.081.179,16; dif 0,72) · SIN_EFECTOS_VIVOS 81 +989.141,26 · SIN_SALDO_CONTABLE 38 -196.914,74 · CONTABILIDAD_MAYOR 41 +97.117,40 · EFECTOS_MAYOR 81 -473.670,76 · total +415.673,88 |
| Fin de obra (922) | INICIO_GARANTIA 198, ULTIMO_CIERRE 150, NULL 574 |
| Fin de obra sobre la viva | 97 / 5.026.655,18 (60,1 %) · 67 / 3.120.260,42 (37,3 %) · sin fecha 15 / 100.351,55 (8 terminadas, 42.647,96) · sin obra 115.665,38 |
| `fuente_plazo` sobre la viva con obra (8.247.267,15) | RETENCION 81 / 3.335.767,86 (40,4 %) · GARANTIA 12 / 1.834.299,50 (22,2 %) · FIJO_12 86 / 3.077.199,79 (37,3 %); en las 922: 144 / 34 / 744 |

**Hallazgo a subrayar**: la fila sin obra es NEGATIVA. Sumar
`saldo_contable` (o `v_retencion_contable_obra`) filtrando `obra_id IS NOT NULL`
da 10,52 M EUR, 1,74 M mas que el saldo real. Queda escrito en la ficha y en el
orden de magnitud; no cambia ningun SQL.

## Verificacion

- YAML de las dos fichas carga con `yaml.safe_load`.
- `bash harness/init.sh`: ver el resultado real al pie.

## Fuera de alcance / pendiente (lider)

- `publicar-diccionario` (version 32), `check-diccionario`, reiniciar el MCP,
  merge a `main`. No hecho aqui, por instruccion.
- Las fichas de F-094 de `retenciones` (`movimientos`, `v_pbi_*`) no se tocan.
