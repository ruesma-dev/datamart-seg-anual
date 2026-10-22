# F-147 · Informe del implementer

> Presupuesto del contexto del MCP: resumen y entrega por regla, contenido
> revisado, enrutado a 2 preguntas y una puerta con trinquete. Rama
> `feature/F-147-presupuesto-contexto-mcp`. Rigor `estandar`. Commits
> `357c20a` (T2) .. `b00d69f` (T13); `azure-apps` `db0b5c5` (commit local).

## Qué cambió

- **Contrato `_meta.diccionario_reglas`** (T4): `resumen` y `entrega` AL FINAL;
  las 7 columnas de antes intactas. `01_diccionario.sql`: bloque `DO` que añade
  columnas y `CHECK` solo si faltan (nunca `ADD COLUMN IF NOT EXISTS`, que toma
  `ACCESS EXCLUSIVE` siempre), `CHECK ... NOT VALID` y `VALIDATE` cuando ninguna
  fila lo incumple (petición A de `mcp-bbdd`). Las `fuera_mcp` no se publican y
  `n_reglas` cuenta solo las publicadas (R6, petición C).
- **Dominio** (`etl_sigrid/domain/diccionario.py`): `Regla.resumen/entrega` +
  `publicable`; `ENTREGAS`, `RESUMEN_MIN/MAX`, `PARA_QUE_SIRVE_MAX`,
  `MAX_PREGUNTAS_ENRUTADO`, `HOLGURA_TRINQUETE`; validación R2/R3/R16;
  `presupuesto_contexto` y `veredicto_presupuesto`; doce reglas obligatorias.
- **Cargador**: claves `resumen`, `entrega` (sin ella, `resumen`).
- **Contenido v59** (T8-T11): las 21 reglas de `revision_reglas.md` (20
  publicadas), `R-PERFILES` entera, `R-SIGRID-CON` `fuera_mcp`, `R-OBRA-ACTIVA`
  = obra viva de F-025 (consulta verificada en Azure en solo lectura: 41 obras,
  todas empresa 1, la cifra de la spec), `R-COMPRAS-SIN-IVA` corregida,
  `R-ALBARAN-ABSURDO` mínima; detalle a las fichas (18 fichas «mezcla las 38
  empresas» con su camino comprobado, cuenta bancaria, recuentos, coste de
  consulta en `stg.plan_mensual`/`compras.fact_compras_linea` y 60 s en
  `mart.v_fact_periodificado`); códigos retirados sustituidos en 12 ficheros;
  convenciones, cabecera de `compras.yaml`, 11 `para_que_sirve` ≤ 350, 12
  fichas con las 2 primeras preguntas reordenadas (ninguna borrada).
- **Docs**: ARCHITECTURE, CONVENTIONS, ficha de `_meta.diccionario_reglas`
  (columnas nuevas) y `azure-apps/datamart_seg_anual.md` (R21).

## Decisiones y desviaciones (justificadas)

1. **`RESUMEN_MAX = 250`, no 300 (R2).** Es el `CHECK` que pidió `mcp-bbdd`
   (petición A, aceptada por el líder): con 300 un resumen de 280 pasaría
   `init.sh` y reventaría la publicación en Azure. Un test ata el número al DDL.
   `R-VENTA-COEFICIENTES` y `R-PERFILES` se acortaron sin perder contenido.
2. **`R-PERFILES` (petición B)**: `entrega: entera`, texto corto (regla+motivo ≤
   1.000, test) y ámbito = unión de las cuatro fundidas, que incluye objetos que
   el restringido SÍ lee (`compras.documento_alarmas`, `compras.vencimientos`,
   `compras.v_facturas_pago`, `compras.v_control_forma_pago`,
   `compras.documento_procesos`, `compras.documento_adjuntos`,
   `retenciones.apuntes_contables`). Un filtro «no servir reglas cuyo ámbito el
   perfil no puede leer» la sigue sirviendo. No se dejó vacío: el validador
   (R9) exige ámbito, y vaciarlo quitaría el aviso de las fichas.
3. **R13 «umbral de 1.000 M€»** se escribe «mil millones de euros»: con cifras
   chocaría con la prohibición de «M€» y de separador de miles de la misma R13.
4. **R8 excluye también `harness/features.json`**: su texto es el de
   `BACKLOG.md` (que la spec excluye), generado desde él.
5. **Historia en comentarios de `00_global.yaml`**: los nombres retirados se
   cambiaron por descripciones («la regla del perfil restringido (hoy
   `R-PERFILES`)») para cumplir R8 sin falsear la historia.
6. **`15_alarmas_liquidatoria.sql`**: además del comentario, el literal del
   `COMMENT ON TABLE compras.documento_alarmas` citaba el código; se cambió el
   texto del comentario de tabla (sin cambio de SQL ni de datos).
7. **`R-IMPORTE-MES` queda `resumen`** (la tabla la marcaba «candidata a
   entera»; D1 no lo decidió y su resumen ya basta).
8. **Tests de features anteriores reescritos** (F-006, F-037, F-123, F-128,
   F-135, F-136, F-138, F-141, F-146): comprobaban texto de las reglas fundidas
   o retiradas; ahora comprueban lo mismo donde vive (R-PERFILES o la ficha),
   sin rebajar ninguna aserción de contenido.

## Prueba del DDL contra PostgreSQL real

Clúster PG16 DESECHABLE en el puesto (`initdb` en el scratchpad, puerto 55433,
parado al terminar): tabla de la v58 con filas (DDL de `main`) + DDL nuevo.
Script `probar_ddl.py` del scratchpad; salida real resumida:

```
tras DDL nuevo: (...,orden,resumen,entrega, [('..._entrega_check', True), ('..._resumen_check', False)])
filas viejas: [('R-A', '', 'resumen'), ('R-B', '', 'resumen')]
INSERT de una imagen anterior (sin resumen): RECHAZADO (CheckViolation ... diccionario_reglas_resumen_check)
resumen de 251 / en blanco: RECHAZADO ; entrega fuera_mcp: RECHAZADO ; 250 entera: ACEPTADO
3) Siguiente publicacion: el DDL valida -> [('..._entrega_check', True), ('..._resumen_check', True)]
4) Tercera vez, con un lector en transaccion abierta (lock_timeout 3s): DDL OK en 0.02s
5) Base vacia: el DDL desde cero, dos veces: columnas y CHECK validados
```

**Consecuencia de despliegue**: con el `CHECK`, una imagen anterior no puede
publicar. El job va a la imagen nueva ANTES de la primera publicación
(`progress/current.md`, MANUAL).

## Fase RED (trazas reales)

`.venv/Scripts/python.exe -m pytest tests/test_f147_resumen_reglas.py -q`
(T3; primero `ImportError: cannot import name 'ENTREGAS'`; con solo las
constantes añadidas):

```
FAILED tests/test_f147_resumen_reglas.py::test_f147_r6_c_n_reglas_cuenta_solo_las_publicadas
FAILED tests/test_f147_resumen_reglas.py::test_f147_r6_publicar_manda_nueve_columnas_y_sin_las_fuera_mcp
E       TypeError: Regla.__init__() got an unexpected keyword argument 'resumen'
E       AssertionError: assert [] == ['resumen', 'entrega']
28 failed, 3 passed in 47.28s
```

`.venv/Scripts/python.exe -m pytest tests/test_f147_presupuesto_contexto.py -q` (T5):

```
E   ImportError: cannot import name 'HOLGURA_TRINQUETE' from 'etl_sigrid.domain.diccionario'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.72s
```

`.venv/Scripts/python.exe -m pytest tests/test_f147_contenido.py -q` (T7):

```
FAILED tests/test_f147_contenido.py::test_f147_r7_quedan_las_21_reglas_decididas
FAILED tests/test_f147_contenido.py::test_f147_r12_la_regla_nombra_los_totales_con_iva
FAILED tests/test_f147_contenido.py::test_f147_r16_ningun_esquema_del_arbol_pasa_de_350
E       AssertionError: assert {'R-ABONO-NEG...SIN-IVA', ...} == {'R-ALBARAN-A...-ORIGEN', ...}
E         Extra items in the left set: 'R-TESORERIA-RESTRINGIDA'
47 failed, 14 passed in 13.40s
```

GREEN: `test_f147_resumen_reglas.py` 31 passed; `test_f147_presupuesto_contexto.py`
14 passed; `test_f147_contenido.py` 61 passed (tras T12).

## T2 / T14 · Medida antes y después (fórmula de R17)

| Parte | v58 hoy (reglas enteras, todas las preguntas) | v59 con el MCP de hoy (sin F-029) | v59, fórmula R17 (con F-029) |
|---|---:|---:|---:|
| Reglas | 46.287 (27) | 24.561 (20 publicadas, enteras) | 7.107 |
| Enrutado | 18.102 (283 preguntas) | 18.102 | 13.901 (2 por ficha) |
| Bloques | 13.668 (`esquemas` 10.549) | 8.505 (`esquemas` 5.931) | 8.505 |
| **Total** | **78.057** | **51.168 (−34 %)** | **29.513 (−62 %)** |

Azure (solo lectura, 2026-10-22) coincide al carácter con el árbol de la v58:
reglas 46.287, bloques 13.668, enrutado 2.913 + 15.189. `contexto_bbdd()` entero
no se pudo medir: el conector MCP `bbdd-ruesma-azure` no conecta en esta sesión
(404); los ~86.000 de la spec incluyen los rótulos de `mcp-bbdd`. La medida
servida tras el despliegue es MANUAL (`progress/current.md`).
`PRESUPUESTO_MAX = 29_513` con su historia en el test (T12).

## Fuera de alcance / pendiente

- Código de `mcp-bbdd` (su F-029: servir `resumen`, detalle en `describir_tabla`,
  recorte del enrutado). Sin ella el ahorro es el −34 %.
- Despliegue (imagen, job, publicación, comprobaciones): MANUAL, en
  `progress/current.md`.

## Evidencias

PENDIENTE de `bash harness/init.sh` y de la campaña de mutación (se completa al
terminar).
