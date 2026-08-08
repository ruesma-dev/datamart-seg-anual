# Fix — build-retenciones fallaba por raw.dvfpro

## Qué pasaba

```
[FALLO ] 01_movimientos.sql: no existe la relación «raw.dvfpro»
```

Usé `raw.dvfpro` (líneas de factura de venta) para deducir la obra de los
cobros con retención, pero **no añadí esa tabla al YAML**. Fallo mío: escribí
el SQL contra una tabla que el pipeline no ingiere.

## La solución

Los SQL del módulo ahora son **defensivos**: `00_setup.sql` comprueba si
`raw.dcfpro` y `raw.dvfpro` existen y crea una vista fuente para cada una
(pasarela si existe, vista vacía si no). `01_movimientos.sql` consulta esas
vistas en lugar de las tablas directamente.

Resultado: **el módulo se construye igual sin `dvfpro`**. Solo pierde el
respaldo de atribución de obra para los cobros que no traen `cenide`, y esos
quedan contados en `sin_obra_asignada`. La vía principal (`cenide` del efecto)
cubría el 98 % de los casos según el diagnóstico.

Al construir verás avisos informativos como:

```
NOTICE: retenciones: respaldo de obra por dcfpro ACTIVO
NOTICE: retenciones: raw.dvfpro no existe; respaldo de obra para CLIENTE
        desactivado (solo cenide)
```

## Instalación

Sustituye los 3 SQL de
`etl_sigrid/infrastructure/postgres/sql/retenciones/` y relanza:

```powershell
python main.py build-retenciones
```

No hace falta reingerir nada. `main.py` y el YAML no cambian.

## Opcional — activar el respaldo completo

Si quieres que también los cobros sin `cenide` queden atribuidos a su obra,
añade `dvf` y `dvfpro` a la ingesta (son pequeñas: 15.423 y 28.789 filas).
El snippet está en `config/tables_sigrid_venta_snippet.yaml`.

```powershell
# pegar las 2 entradas al final de tables: en tu tables_sigrid.yaml
python scripts\fix_exclusiones_yaml.py --tabla dvf
python scripts\fix_exclusiones_yaml.py --tabla dvfpro
python main.py ingest
python main.py build-retenciones     # el respaldo se activa solo
```

Además deja el terreno preparado para la Tanda 5 (facturación de venta),
que necesitará esas mismas tablas.

## Corrección: `inspect-todo` no existe

En los pasos anteriores te propuse `python main.py inspect-todo`. Ese comando
no está en tu `main.py` — lo arrastré por error de sesiones antiguas. Para
comprobar que el pipeline de siempre sigue bien, usa los tuyos:

```powershell
python main.py inspect-month --codigo 0664 --mes 2024-12-01
python main.py inspect-mart --codigo 0664
```

(o `python main.py --help` para ver la lista exacta)
