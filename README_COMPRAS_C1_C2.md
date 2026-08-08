# Tandas C1 + C2 — Módulo COMPRAS (proveedores, contratos, albaranes, facturas)

Módulo independiente en schema `compras`. Solo lee de `raw.*`; no toca
stg/mart/cierre ni ninguno de los archivos SQL existentes. Todos los importes
SIN IVA. Series reales de Ruesma soportadas: AC (albarán), PROF (proforma /
certificación de subcontrata), NTC (nota), FR/FRGG (factura), AB/ABGG (abono).

## Contenido del ZIP

```
config/tables_sigrid_compras_snippet.yaml     ← bloque a PEGAR en tu YAML
etl_sigrid/infrastructure/postgres/sql/compras/
    00_setup.sql        schema + funciones (serie, tipo_documento, fechas)
    01_documentos.sql   contratos/albaranes/facturas (cabeceras + líneas)
    02_fact_linea.sql   compras.fact_compras_linea (hechos unificados)
    03_views.sql        4 vistas de negocio
patches/main_py_patch_compras.py              ← bloque a PEGAR en main.py
```

## Instalación (3 pasos manuales + ejecución)

### 1. YAML
Abre `config/tables_sigrid.yaml` y pega al final de la lista `tables:` el
contenido de `config/tables_sigrid_compras_snippet.yaml` (las 9 entradas,
respetando la indentación).

⚠️ Revisa la entrada existente de `con`: si tiene un `where` filtrando por
`tip`, amplíalo para incluir 5, 13, 14, 15 y 44 (los con de proveedores y
documentos de compra). Si no tiene filtro, no toques nada.

### 2. main.py
Abre `patches/main_py_patch_compras.py`, copia todo el bloque de comandos y
pégalo en `main.py` justo ANTES de `if __name__ == "__main__":`.

### 3. SQL
Copia la carpeta `etl_sigrid/infrastructure/postgres/sql/compras/` completa
a tu proyecto (es carpeta nueva).

### 4. Ejecutar

```powershell
python main.py ingest            # trae las 9 tablas nuevas (~10-15 min la 1ª vez)
python main.py build-compras     # construye el schema compras

# Verificaciones
python main.py inspect-contrato-consumo --umbral 90        # contratos agotándose
python main.py inspect-contrato-consumo --codigo CTSB25/0709
python main.py inspect-proveedores-obra --obra 0707 --anio 2026
python main.py inspect-albaranes-sin-facturar --obra 0707
```

`build-compras` NO requiere stage: lee de raw directamente.
Para reconstruir: `reset-compras` + `build-compras`.

## Modelo

```
compras.contratos / contrato_lineas      (ctr + ctrpro)
compras.albaranes / albaran_lineas       (dca + dcapro; tipo AC/PROF/NTC)
compras.facturas  / factura_lineas       (dcf + dcfpro; tipo FR/AB)
compras.fact_compras_linea               (todo unificado, grano línea)

compras.v_pbi_contrato_consumo           contratado / albaranado / proforma /
                                         facturado / pendiente facturar /
                                         consumido / disponible / % consumido
compras.v_pbi_proveedor_obra             proveedor × obra × año
compras.v_pbi_albaranes_sin_facturar     operativa de pendientes (via canfac)
compras.v_pbi_partida_coste              coste incurrido por partida
```

Trazabilidad resuelta línea a línea:
- albarán → contrato: `dcapro.linoriide → ctrpro.ide` (docoritip=44)
- factura → albarán:  `dcfpro.linoriide → dcapro.ide` (docoritip=14)
- factura → contrato directo: `dcfpro.linoriide → ctrpro.ide` (docoritip=44)

Pendiente de facturar por línea de albarán = `tot × (1 − canfac/can)`
(campo nativo dcapro.canfac; sin reconstruir enlaces).

La obra/partida de una factura hereda de la línea de albarán origen cuando la
factura no la informa.

## Validación realizada

Escenario completo ejecutado contra PostgreSQL real (embebido):
contrato 1.000 € → albarán AC 500 € (parcialmente facturado via canfac) +
proforma PROF 100 € → facturas 320 € + abono −20 € + factura directa contra
contrato 50 €. Resultados al céntimo:
contratado 1.000 / albaranado 500 / proforma 100 / facturado 350 /
pendiente facturar 280 / consumido 650 / disponible 350 / 65,00 %.
Las 4 vistas verificadas, incluida la herencia de partida en facturas y el
signo negativo de abonos.

## Notas y límites conocidos

- `dcapropar`/`dcfpropar` (desglose de partidas) NO se usan: están vacías en
  Ruesma; la partida viene en la línea.
- Ingesta incremental por cursor de ide: los updates de `canfac` en líneas
  antiguas NO llegan con el incremental. Igual que con el seguimiento, el
  refresh fiable es `ingest --full` (el job nocturno de Azure lo hará así).
- `fecha` de los documentos = `con.fec`. Si detectas que algún documento usa
  otra fecha operativa (p.ej. dca.fecdoc distinta de con.fec), dímelo y
  añadimos la columna.
- Las cabeceras dca/dcf se leen con columnas mínimas confirmadas
  (ide, ctride, comide, entide, entcif, entref). Si tu raw trae más columnas
  útiles, son ampliables sin reingesta.

## Siguiente paso natural

- Comparativos (com/comlin/comprv) quedan ingeridos pero sin explotar en
  vistas: cuando quieras "qué comparativos hay y cuál ganó", se añade una
  vista sobre ellos (Tanda C3).
- Integración con el job de Azure: añadir `build-compras` a la cadena del
  run-all del despliegue (Tanda D1).
- Documentar el schema compras en ESQUEMA_BBDD_SEGUIMIENTO.md para el MCP.
