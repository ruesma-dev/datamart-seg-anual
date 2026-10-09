<!-- progress/contraste_F-132.md -->
# F-132 · Contraste foto diaria ↔ rac (D6: 14 noches, hasta el 2026-10-22)

Cada ejecución, fechada, con la salida tal cual de `python main.py contraste-estados`
(solo lectura). Criterio para retirar la foto (D6): 0 `DISCREPANCIA` sin explicar.

## 2026-10-09 08:41 UTC · tras desplegar la fase A (imagen `r20261009-0858`) · 2 noches

```
Contraste foto diaria <-> rac · SOLO LECTURA, transacciones READ ONLY
observado_en (UTC)  | tipo        | grupo    | clase             | documentos
2026-10-08 00:03:01 | CONTRATO    | CAMBIO   | PASO              | 4
2026-10-08 00:03:01 | CONTRATO    | CAMBIO   | DESHECHO          | 2
2026-10-08 00:03:01 | CONTRATO    | CAMBIO   | VUELTA_AL_INICIAL | 3
2026-10-08 00:03:01 | CONTRATO    | NO VISTO | ALTA              | 1
2026-10-08 00:03:01 | CONTRATO    | NO VISTO | IDA_Y_VUELTA      | 4
2026-10-08 00:03:01 | FACTURA     | CAMBIO   | PASO              | 210
2026-10-08 00:03:01 | FACTURA     | CAMBIO   | DESHECHO          | 7
2026-10-08 00:03:01 | FACTURA     | CAMBIO   | FUERA_DE_PROCESO  | 4
2026-10-08 00:03:01 | FACTURA     | NO VISTO | ALTA              | 88
2026-10-09 00:02:57 | CONTRATO    | CAMBIO   | PASO              | 12
2026-10-09 00:02:57 | CONTRATO    | CAMBIO   | DESHECHO          | 4
2026-10-09 00:02:57 | CONTRATO    | NO VISTO | ALTA              | 9
2026-10-09 00:02:57 | CONTRATO    | NO VISTO | IDA_Y_VUELTA      | 8
2026-10-09 00:02:57 | FACTURA     | CAMBIO   | PASO              | 239
2026-10-09 00:02:57 | FACTURA     | CAMBIO   | DESHECHO          | 7
2026-10-09 00:02:57 | FACTURA     | NO VISTO | ALTA              | 151
Resultado: 0 DISCREPANCIA sin explicar.
```

Código de salida 0. La noche del 08-10 ya no da exactamente lo de la spec (214/7/0
facturas, 5 idas y vueltas): con la historia NETA, un paso deshecho DESPUÉS reclasifica
la noche (4 facturas pasan de PASO a FUERA_DE_PROCESO, un contrato deja de ser IDA Y
VUELTA). Lo avisó el implementer (`impl_F-132.md` §6.4). Sigue sin ninguna discrepancia.

## 2026-10-09 · CONTRASTE CERRADO por decisión del humano (D6 acortada, D7 = BORRAR)

El humano, con la salida de arriba delante (2 noches, 492 cambios, **0
`DISCREPANCIA`**), ordenó el 2026-10-09 «bórrala ya» y confirmó el plan
(«adelante»): **D6 se acorta** y el contraste se cierra con estas 2 noches en vez
de las 14 previstas (hasta el 2026-10-22); **D7 = BORRAR** la foto
(`progress/spec_F-132.md` §8). No se relanza el contraste: la Fase B retira el
propio comando `contraste-estados` junto con las tablas que lee, así que esta es
su última ejecución. Lo que se acepta perder: la noche en que se DESHIZO un paso
(~9 al día; los 4 + 7 DESHECHO de contrato y los 7 + 7 de factura de arriba)
hasta que F-105 lo traiga de `dbo.log`, y las tres noches de foto (07, 08 y 09-10).
