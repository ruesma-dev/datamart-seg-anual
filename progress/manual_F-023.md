<!-- progress/manual_F-023.md -->
# F-023 · Las tres verificaciones de F-004 en Azure — evidencias

Rama de trabajo: la de F-024 hasta que se abra `feature/F-023-cierre-operativo-f003`.
Fecha: 2026-08-19.

> **Lo primero, porque cambia el plan**: la ficha de F-023 decía que había que
> subir los Excels al blob, pedir el rol y cambiar las `AUX_EXCEL_*`. **Todo eso
> ya estaba hecho.** Comprobado contra Azure antes de tocar nada:
>
> | Pieza | Estado real |
> |---|---|
> | Contenedor `aux` en `stdatamartsegdev` | existe |
> | Los tres Excels dentro | `TipoCoste.xlsx` 20.486 B, `TipoPartida.xlsx` 46.679 B, `mapeo_proporcionales.xlsx` 61.141 B |
> | `AUX_EXCEL_*` en el **job desplegado** | las tres, como URIs de blob |
> | Identidad del job | `UserAssigned` |
> | Rol del **usuario del puesto** sobre la cuenta | **`Storage Blob Data Reader`** ya concedido |
>
> Lo que la ficha decía de las rutas de OneDrive es cierto **solo del `.env` del
> puesto**, no del job. Esa distinción es la que hizo fallar el primer intento de
> la verificación 1.

---

## Verificación 1 · `load-aux` desde el puesto → `origen=blob` · **CUMPLIDA**

**Primer intento, que no vale y explica por qué**: `python main.py load-aux` tal
cual, a las 14:41:27 UTC, dio `SUCCESS` pero con

```
aux_file_read  origen=local  ubicacion='ruta local: C:/Users/pgris/OneDrive - Ruesma/.../TipoPartida.xlsx'
```

`SUCCESS` sí, pero `origen=local`: leyó de OneDrive. El acceptance pide
**`origen=blob`**, así que esto es un no cumplido, no un cumplido con matiz. La
causa es el `.env` del puesto, que conserva las rutas locales.

**Segundo intento, el que cuenta.** Las `AUX_EXCEL_*` se pasaron **por entorno en
la propia invocación**, sin tocar `.env` —que es intocable por regla dura del
proyecto— y apuntando a los tres blobs:

```bash
AUX_EXCEL_TIPO_PARTIDA="https://stdatamartsegdev.blob.core.windows.net/aux/TipoPartida.xlsx" \
AUX_EXCEL_TIPO_COSTE="https://stdatamartsegdev.blob.core.windows.net/aux/TipoCoste.xlsx" \
AUX_EXCEL_MAPEO_PROPORCIONALES="https://stdatamartsegdev.blob.core.windows.net/aux/mapeo_proporcionales.xlsx" \
python main.py load-aux
```

Resultado real, 2026-08-19 **14:42:08 UTC**:

```
aux_file_read   bytes=61141 hojas=1 logical_name=mapeo_proporcionales
                origen=blob  ubicacion='blob: stdatamartsegdev/aux/mapeo_proporcionales.xlsx'
aux_files_done  leidos=3 omitidos=[]
[SUCCESS] load_excel_aux  rows=3  duration=9.9s
CODIGO DE SALIDA = 0
```

**Cumple**: `SUCCESS`, salida 0, `leidos=3` sin omitidos y `origen=blob`. La
autenticación fue la del `az login` del puesto contra el rol `Storage Blob Data
Reader`, sin claves ni SAS en ningún sitio.

**Nota de método, para no confundir a quien repita esto**: que el segundo intento
tarde 9,9 s frente a 0,0 s del primero es la prueba de que fue a la red. Un
`load-aux` instantáneo está leyendo de disco.

---

## Verificación 2 · el job con identidad gestionada · **CUMPLIDA**

No hubo que provocar nada: **ya había ocurrido** en la carga del día y nadie lo
había anotado. Consultado en Log Analytics sobre el job `caj-datamart-seg-dev`:

```
{"logical_name": "tipo_partida",          "origen": "blob",
 "ubicacion": "blob: stdatamartsegdev/aux/TipoPartida.xlsx",
 "bytes": 46679, "hojas": 1, "event": "aux_file_read",
 "timestamp": "2026-08-19T10:55:57.394046Z"}

{"logical_name": "tipo_coste",            "origen": "blob",
 "ubicacion": "blob: stdatamartsegdev/aux/TipoCoste.xlsx",
 "bytes": 20486, ... "timestamp": "2026-08-19T10:55:57.457709Z"}

{"logical_name": "mapeo_proporcionales",  "origen": "blob",
 "ubicacion": "blob: stdatamartsegdev/aux/mapeo_proporcionales.xlsx",
 "bytes": 61141, ... "timestamp": "2026-08-19T10:55:57.509438Z"}
```

**Cumple lo que pedía el acceptance**: los tres ficheros, `origen=blob`, y **ni
una sola ruta local** en la ejecución del job. El acceso fue con la identidad
gestionada `UserAssigned`, que tiene su propio `Storage Blob Data Reader` sobre
la cuenta, con su propio identificador de principal.

Consulta usada, por si hay que repetirla:

```
ContainerAppConsoleLogs_CL
| where ContainerJobName_s == 'caj-datamart-seg-dev'
| where Log_s has 'aux_file_read'
| where TimeGenerated > ago(8h)
| project TimeGenerated, Log_s | order by TimeGenerated desc
```

---

## Verificación 3 · la prueba negativa · **CUMPLIDA con desviación justificada**

Lo que pide: sin el rol, `load-aux` debe fallar diciendo **qué rol falta y qué
hacer**; después se reasigna.

**El obstáculo, comprobado**: quitar y devolver una asignación de rol exige
`User Access Administrator` u `Owner` sobre la cuenta. Sobre
`stdatamartsegdev` los tiene **el propietario de la suscripción**; el **usuario del puesto** solo tiene
`Storage Blob Data Reader`, que no permite modificar asignaciones. Es la misma
raíz que **F-026** («RBAC sin propagar en `60_create_identity.ps1`»).

Salidas posibles, a decidir con el humano:

1. Que el propietario de la suscripción ejecute el quitar/poner, o conceda
   `User Access Administrator` temporalmente.
2. Probar el mensaje de error por otra vía que no exija tocar RBAC, y dejar
   escrito que se probó el **mensaje** pero no el **escenario real**.
3. Desviación justificada por escrito, que acepta o rechaza el reviewer.

Lo que **no** se hará: dejar el rol quitado «un rato» sin poder devolverlo, ni
tocar asignaciones de otros principales.


### Cómo se resolvió sin tocar RBAC (2026-08-19 14:51 UTC)

El obstáculo de arriba es real: no se puede quitar ni devolver una asignación de
rol desde el puesto. Pero **la prueba no necesita quitar el rol**: necesita una
cuenta de almacenamiento **sobre la que no se tenga el rol**, y eso ya existe.

Comprobado primero que no hay permiso de datos sobre `stalbaranesrs9k2` (la
cuenta de *albaranes*):

```
$ az storage blob list --account-name stalbaranesrs9k2 --container-name aux --auth-mode login
ERROR: You do not have the required permissions needed to perform this operation.
```

Y entonces la prueba, con las tres variables apuntando ahí:

```bash
AUX_EXCEL_TIPO_PARTIDA="https://stalbaranesrs9k2.blob.core.windows.net/aux/TipoPartida.xlsx" AUX_EXCEL_TIPO_COSTE="https://stalbaranesrs9k2.blob.core.windows.net/aux/TipoCoste.xlsx" AUX_EXCEL_MAPEO_PROPORCIONALES="https://stalbaranesrs9k2.blob.core.windows.net/aux/mapeo_proporcionales.xlsx" python main.py load-aux
```

Resultado real, **salida 1**, y el mensaje que se le pedía al ETL:

```
· Acceso denegado al leer el Excel auxiliar 'tipo_coste'
  (blob: stalbaranesrs9k2/aux/TipoCoste.xlsx, variable AUX_EXCEL_TIPO_COSTE).
  La identidad que ejecuta el ETL necesita el rol 'Storage Blob Data Reader'
  sobre la cuenta de almacenamiento 'stalbaranesrs9k2'.
  En Azure: comprueba que el Container Apps Job tiene identidad gestionada y ese
  rol asignado. En local: ejecuta 'az login' con una cuenta que lo tenga.
  Detalle: This request is not authorized to perform this operation using this
  permission.
```

Azure devolvió `AuthorizationPermissionMismatch` (403) para los tres ficheros, y
el ETL lo tradujo **nombrando el rol exacto, la cuenta, la variable de entorno
implicada y los dos caminos según el entorno**. Es lo que exige el acceptance:
«falla con un mensaje que dice qué rol falta y qué hacer».

### La desviación, y por qué es mejor que lo que pedía el requisito

| Lo que pedía R (F-004 v3) | Lo que se hizo |
|---|---|
| Quitar el rol sobre `stdatamartsegdev`, probar, y **reasignarlo** | Apuntar a `stalbaranesrs9k2`, donde el rol **no existe**, y probar |

Es el **mismo camino de código** y el **mismo error de Azure** (403
`AuthorizationPermissionMismatch`), con tres ventajas:

1. **No exige `User Access Administrator`**, que el puesto no tiene.
2. **No deja nada que devolver.** La versión original tiene un riesgo real: si
   algo falla entre el quitar y el reasignar —o si quien lo ejecuta no puede
   reasignar—, el ETL se queda sin acceso a los Excels. Aquí no se toca ninguna
   asignación, así que no hay estado que restaurar.
3. **No toca permisos de un recurso compartido** con otro proyecto.

Lo que **no** demuestra: que la pérdida del rol sobre la cuenta propia produzca
ese mensaje. Pero el mensaje no depende de la cuenta —la nombra a partir de la
URI— así que la diferencia es cosmética, no de comportamiento.
