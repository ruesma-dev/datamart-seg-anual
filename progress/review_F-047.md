<!-- progress/review_F-047.md -->
Revisión **incremental desde `ac8a426` (pasada 3)**: delta `ac8a426..aebdf10`,
3 ficheros, +11/-7. Nada de código, tests, campaña ni `azure-apps` cambió en
este delta —verificado, no supuesto—, así que lo aprobado en las pasadas 1 y 2
queda dado por bueno. `init.sh` y la suite se ejecutan enteros, como cada pasada.
El detalle de las pasadas anteriores vive en el historial de este fichero
(commits `ac8a426` y `aebdf10`).

# F-047 (absorbe F-044) · Review · pasada 3 · rigor `critico`

## Veredicto: **APROBADO**, con tres condiciones de cierre pendientes

El bloqueante de la pasada 2 está resuelto y las dos correcciones que pedí están
aplicadas. **No queda ningún cambio requerido.**

Las tres pendientes son **escrituras contra producción**, están planteadas al
humano y **sin respuesta todavía**: no son incumplimientos del trabajo, y por eso
no bloquean la aprobación. **El orden importa** y es este:

1. **Construir y desplegar imagen nueva.** Sin esto los otros dos maquillan el
   síntoma: la nocturna volvería a destruir la vista esa misma noche. Hoy el job
   `caj-datamart-seg-dev` corre `r20260818-2146`, del 18 de agosto, y **nada de
   F-047 ni de F-006 está en producción**.
2. **Dejar correr una nocturna** (o lanzar `build-cierre` a mano para recrear
   `cierre.v_pbi_planif_vs_real` hoy; autorizado por el humano el 2026-08-28 y
   bloqueado por el clasificador de permisos de la sesión).
3. **`publicar-diccionario`** (versión 10), **el último**. `R-FRESCURA` promete
   que la fecha de build de los cuatro «siempre es consultable», y
   `_meta.v_frescura` no tiene hoy ni una fila de `build_compras` ni de
   `build_retenciones`. Publicarlo antes de que corra una noche dejaría al MCP
   sirviendo una regla **bloqueante** que manda a una consulta vacía: una mentira
   nueva del tipo que F-047 vino a matar.

Con las tres hechas quedan cubiertos los dos criterios que hoy se cumplen en el
repositorio y no en producción: **F-047·2** (la vista existe y
`check-diccionario` deja de reportar la huérfana) y **F-044·1/·5**.

## Lo verificado en esta pasada

**1. `init.sh` en VERDE, medido entero.** Lo ejecuté yo: **2.581 pasados, 128
saltados**, 405,9 s. `PUERTA COBERTURA` **[OK] 100,0 % (259/259 líneas
cambiadas)**, umbral 80 %, nivel `critico`. `PUERTA TAMAÑO` **[OK]** (impl
220/220, review 140/140). Cero fallos.

Los tres recuentos de `current.md` están y son los reales, comprobados contra el
diccionario cargado, no contra el texto: **103 objetos, 798 columnas, 46 fichas
de consumo**. El test que los vigila vuelve a pasar y **no se tocó**, que era lo
correcto: el guardián de F-006 hizo su trabajo dos veces seguidas.

Buena la salida del segundo intento, además: `102 objetos` desaparece del fichero
sustituido por «**103 fichas y 102 construidas**», que dice lo mismo sin disparar
un test deliberadamente literal. Cero ocurrencias de la cadena, verificado.

**2. F-041, quinto defecto: reescrito, y dice lo que tiene que decir.** Lo leí en
`features.json`. Recoge los cuatro puntos: que lo demostrado es que **el defecto
2 opera también en serie**; que es **bidireccional** («pudo igual importar
bytecode MUTADO del 3 y matarlo por el motivo equivocado, que es un FALSO MUERTO
EN SERIE, la dirección peligrosa»); que **la serie no es inmune, solo no se ha
visto uno todavía**; que la regla sobre el modo paralelo **sigue en pie tal
cual**; y que lo que cierra esto es el **criterio de aceptación 5**, no una regla
operativa. Nada que objetar.

**3. F-049: los dos apuntes recogidos, y el primero como cuarto criterio.** El
criterio 4 —«Decidido y escrito DÓNDE vive el análisis del superviviente, para
que la herramienta pueda saber que está resuelto sin adivinar»— es exactamente el
contrato que faltaba. El solape con F-041 queda anotado en la descripción.
`rigor: estandar`, prioridad 8: me cuadran, por lo dicho en la pasada 2.

`BACKLOG.md` está regenerado y coherente con `features.json`. `azure-apps` sigue
en `e4f0f9b` con el árbol limpio.

## Checkpoints · veredicto final

| | | Nota |
|---|---|---|
| **C1** | `[x]` | `init.sh` exit 0, suite entera en verde; los siete ficheros obligatorios existen |
| **C2** | `[x]` | una sola `in_progress`; rama `feature/F-047-nocturna-desfasada`; `current.md` solo de la sesión activa, con lo verificado contra la base |
| **C3** | `[x]` | ruta en la 1ª línea de los 8 ficheros nuevos; sin `print()` de debug ni secretos; capas respetadas (dominio sin infraestructura) |
| **C3 bis** | `N/A` | **justificado**: el diff no toca `docs/referencia/`; `git log --diff-filter=A` no añade ningún PDF/ofimática en la rama |
| **C4** | `[x]` | los 9 criterios (F-047 **y** F-044) trazados; 48 funciones / 77 casos `test_f047_*`; ninguno toca red ni BBDD |
| **C4 bis** | `[x]` | rigor `critico` cumplido; ver abajo |
| **C4 ter** | `N/A` | **justificado**: no existe `harness/rutas_sensibles.json`; sin declaración el bloque es N/A por diseño |
| **C5** | `[x]` | commits `F-047 Tn:`; `tasks.md` N/A (`sdd=false`); `features.json` refleja el estado real y con su salto de línea final |

**C4 bis, resumen de las tres pasadas.** Fase RED con trazas reales pegadas.
Cobertura 100 % de las líneas cambiadas. Campaña de mutación **recalculada de
forma independiente** por mí: alcance **831 líneas en 12 ficheros** y **70
mutantes**, idénticos a los del informe; los **7 supervivientes verificados uno a
uno** como mutantes reales, con el mismo operador y el mismo texto
original→mutado. **Cero supervivientes finales** (15 encontrados, 15 con test,
cero equivalentes declarados), que es la exigencia dura de `critico`. RM1–RM6
recorridos: campaña no reejecutada por durar 2 h 32 min, y dicho por escrito.

## Barrido de secretos

Ejecutado por mí en la pasada 1 sobre los 37 ficheros del diff (contraseñas y
cadenas de conexión, claves y tokens, GUID, IPs internas, correos, base64 largo):
**cero secretos**. `.env` no trackeado. El delta de esta pasada no añade nada.

## Nota para el cierre

La feature entrega el arreglo **y el guardián que impide que vuelva a pasar en
silencio**: `check-declarados` contrasta lo que `sql/**` declara contra el
catálogo real y hace salir `run-all` con código 1. Verifiqué que el
`config/objetos_pendientes.yaml` vacío es real —parser contrastado contra un
regex independiente: 72 objetos idénticos, cero diferencia— y que el trinquete
rompe la puerta en los dos sentidos.

Queda escrito, porque es lo que más fácil se olvida: **hasta que se despliegue
imagen nueva, todo esto vive en el repositorio y no en la nocturna.** El
documento de `azure-apps` ya lo dice en presente y con el aviso al principio, que
era el hallazgo que motivó el rechazo de la pasada 1.
