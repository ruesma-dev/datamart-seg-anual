# F-074 — Las nueve tablas medidas contra Sigrid (exploración, 2026-09-09)

Medición de solo lectura vía `SigridApiClient.leer_sql` (dev) e
`INFORMATION_SCHEMA`. **No se ha tocado ningún fichero del ETL.** Ninguna de las
nueve está declarada hoy en `config/tables_sigrid.yaml` (56 tablas, cero
coincidencias): el alcance de F-074 son nueve altas, y las nueve existen en
`dbo` como `BASE TABLE` con el nombre exacto del enunciado.

## Tabla resumen

| tabla | filas | cols | `ide` | único | `tiemod` | col. texto | ancho medio (SQL) | PG estimado |
|---|---:|---:|:--:|:--:|:--:|---|---:|---:|
| `auxdpt` | 7 | 8 | sí | sí | **sí** (float) | — | 44 B | < 0,1 MB |
| `auxhor` | 60 | 23 | sí | sí | **sí** (float) | — | 96 B | < 0,1 MB |
| `auxrestip` | 37 | 10 | sí | sí | **sí** (float) | — | 58 B | < 0,1 MB |
| `cet` | 40 | 69 | sí | sí | **NO** | `dir`, `dirtex` | 271 B | < 0,1 MB |
| `pro` | **55.179** | 108 | sí | sí | **NO** | `tex`, `esigurl1/2`, `esigpromt`, `carprotex` (vacías) | 411 B | ~27 MB |
| `reshor` | 8.949 | 11 | sí | sí | **NO** | — | 60 B | ~1 MB |
| `emphis` | 1.633 | 117 | sí | sí | **NO** | `notas` (1 fila, 6 B) | 459 B | ~0,9 MB |
| `dcaprodes` | **850.985** | 7 | sí | sí | **NO** | — | 37 B | ~81 MB |
| `ctrprodes` | **424.475** | 8 | sí | sí | **NO** | — | 42 B | ~43 MB |

`ide` es `int` y **único** (`COUNT(*)` = `COUNT(DISTINCT ide)` en las nueve):
sirve de cursor de paginación sin reservas.

**Solo tres tienen `tiemod`**, comprobado en `INFORMATION_SCHEMA` y no supuesto:
`auxdpt`, `auxhor`, `auxrestip`, en `float` (fecha serie, rango 39.771–46.234) y
**poblado al 100 %**. Las otras seis **no tienen ninguna columna de tipo fecha**:
en las nueve no hay ni un `datetime`, y lo que parece fecha (`fec`, `fecalt`,
`fecult`, `fecultact`) es `int` `YYYYMMDD`. No hay sustituto de `tiemod`: en esas
seis, `incremental_column: null` **declarado**.

## Las dos comprobaciones que dejó pendientes el censo

- **`cet.cod` NO existe.** El recuento sobre `INFORMATION_SCHEMA.COLUMNS` con
  `TABLE_NAME='cet' AND COLUMN_NAME='cod'` devuelve **0**; la única columna
  parecida es `res`. El documento de Sigrid se equivoca, el censo de F-072 tenía
  razón, y cualquier join a `cet` va por `ide`.
- **Las dos grandes, confirmadas y algo mayores** que el censo: `dcaprodes`
  **850.985** (censo 850.977) y `ctrprodes` **424.475** (censo 424.454). Ninguna
  tiene `tiemod`, y eso es lo que condiciona F-074.

## Bloques YAML propuestos (listos para pegar)

```yaml
  # --- F-074: maestros de personal y horas ---
  - source_table: auxdpt
    target_table: auxdpt
    id_column: ide
    incremental_column: tiemod   # existe y poblado al 100 % (7/7)
    where: null
    exclude_columns: []
    # Departamentos (7 filas). Decodifica emphis.dptide.
  - source_table: auxhor
    target_table: auxhor
    id_column: ide
    incremental_column: tiemod   # existe y poblado al 100 % (60/60)
    where: null
    exclude_columns: []
    # Horarios/conceptos de hora (60 filas). reshor.horide -> auxhor.ide.
  - source_table: auxrestip     # tipos de recurso (37 filas)
    target_table: auxrestip
    id_column: ide
    incremental_column: tiemod   # existe y poblado al 100 % (37/37)
    where: null
    exclude_columns: []
  - source_table: cet
    target_table: cet
    id_column: ide
    incremental_column: null     # VERIFICADO: cet no tiene tiemod ni columna fecha
    where: null
    exclude_columns:
      - repnom      # datos personales del representante legal, poblados en
      - repno1      # 18 de las 40 filas; no entran al datamart
      - repap1
      - repap2
      - repdni      # DNI
      - repcar
      - dirtex      # text ilimitado, 1 fila con 48 bytes; sin uso en seguimiento
    # Centros de trabajo / empresas propias (40 filas). Sin `cod`: join por ide.
  - source_table: pro
    target_table: pro
    id_column: ide
    incremental_column: null     # VERIFICADO: pro no tiene tiemod (fecultact es int YYYYMMDD)
    where: null
    exclude_columns:
      - esigurl1    # modulo e-commerce de Sigrid, 0 filas con contenido
      - esigurl2    # idem
      - esigpromt   # idem
      - carprotex   # text de caracteristicas, 0 filas con contenido
    # Maestro de articulos, 55.179 filas y 108 columnas. Reparto por `cla`:
    # 9->19.448, 11->17.807, 10->16.614, 3->1.308, 13->2.
  - source_table: reshor
    target_table: reshor
    id_column: ide
    incremental_column: null     # VERIFICADO: reshor no tiene tiemod
    where: null
    exclude_columns: []
    # SENSIBLE (nomina): precio/hora por recurso. 8.949 filas, 2.061 recursos, 58
    # horarios, 2.036 con precio <> 0. Fuera del rol del MCP.
  - source_table: emphis
    target_table: emphis
    id_column: ide
    incremental_column: null     # VERIFICADO: emphis no tiene tiemod (fec es int YYYYMMDD)
    where: null
    exclude_columns:
      - notas       # texto libre sobre el empleado: 1 fila, 6 bytes, dato personal
    # SENSIBLE (nomina): historico de contrato. 1.633 filas, 1.017 empleados, fec
    # de 19891102 a 20260601. Fuera del rol del MCP, como emp y res en F-068.
  # --- F-074: desgloses de documento (las grandes) ---
  - source_table: dcaprodes    # 850.985 filas; docproide -> dcapro.ide
    target_table: dcaprodes
    id_column: ide
    incremental_column: null     # VERIFICADO: dcaprodes no tiene tiemod. Carga por MAX(ide).
    where: null
    exclude_columns: []
    page_size: 10000             # 7 columnas estrechas: 10.000 filas en 0,7 s medidos
  - source_table: ctrprodes
    target_table: ctrprodes
    id_column: ide
    incremental_column: null     # VERIFICADO: ctrprodes no tiene tiemod. Carga por MAX(ide).
    where: null
    exclude_columns: []
    page_size: 10000             # 8 columnas estrechas; medido 10.000 filas en 0,5 s
    # 424.475 filas. docproide -> ctrpro.ide.
```

## Riesgos

1. **Seis de las nueve cargarán solo por `MAX(ide)`.** Sin `tiemod`, una fila
   *modificada* en Sigrid no vuelve a bajar: solo llegan las nuevas. Es el mismo
   agujero de `com`/`comlin`/`comprv`, salvo que aquí se declara a la cara. Un
   `ingest --full` periódico es barato en `cet`, `reshor`, `emphis` y `pro`; en
   `dcaprodes`/`ctrprodes` no, y son desgloses donde `can` sí se corrige.
   **Decisión pendiente para el humano.**
2. **Disco: +155 MB estimados** (dcaprodes ~81, ctrprodes ~43, pro ~27, resto
   < 3) sobre los **25 GB** que ocupa hoy la base en el disco de 64 GB: +0,6 %,
   no mueve la puerta. Calculado con la anchura media real (`DATALENGTH`), 24 B
   de cabecera de tupla y el índice de PK.
3. **Ventana nocturna: +3 a 6 min.** Cronometrado: 10.000 filas de `dcaprodes`
   en 0,7 s y de `ctrprodes` en 0,5 s → ~86 y ~43 páginas, ~90 s de HTTP entre
   las dos. El cuello real es el `COPY` al Postgres B2s (hoy fuera de su B1ms
   hasta el 2026-09-20).
4. **Dato sensible: `reshor` y `emphis`.** Precio/hora por recurso e histórico
   de contrato de 1.017 empleados: **fuera del rol del MCP**, como `emp` y `res`
   en F-068. `cet` trae además el DNI del representante legal; la propuesta lo
   excluye en origen, más barato que protegerlo luego.
5. **Ninguna columna pesada de verdad.** Las 8 columnas `text` están casi vacías
   (`cet.dir` 2,1 KB en total, `emphis.notas` 6 B, las cinco de `pro` entre 0 y
   12 B): las exclusiones son por privacidad y módulo muerto, no por peso.
