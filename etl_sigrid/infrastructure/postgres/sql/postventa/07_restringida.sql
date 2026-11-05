-- etl_sigrid/infrastructure/postgres/sql/postventa/07_restringida.sql
-- ============================================================================
-- F-156 · `postventa_restringida` (R23-R24): LOS DATOS PERSONALES DE POSTVENTA.
--
-- ACCESO RESTRINGIDO. Autorización del humano: «d1 ok», chat del 2026-11-03
-- (D1 = A). Solo la leen el perfil POSTVENTA (`sigrid_dm_perfil_postventa_ro`)
-- y el TOTAL (por el grupo autorizado); el estándar, Power BI y el perfil
-- restringido la tienen VETADA (`apply_grants`, F-156 R28-R30).
--
--   contactos_incidencia  por incidencia: el propietario (`rcp.cliide`, su
--                         nombre es `con.res`), quien reclama (`recide`) y el
--                         contacto (`cntide`): nombre, teléfonos y correo de
--                         `raw.per`, y los avisos de la propia incidencia.
--   contactos_unidad      por unidad: propietario, persona de contacto,
--                         teléfono y correo de la unidad (`restel`, `resele`),
--                         avisos y horarios.
--   textos                los textos ÍNTEGROS (sin máscara) de incidencias y
--                         tareas: descripción, descripción larga y motivo.
--
-- DE `raw.per` SOLO SALEN `nom`, `tel`, `tel2` y `ele` (R24): la ingesta ni
-- siquiera trae el DNI, las credenciales, las direcciones ni las observaciones,
-- y un test falla si este SQL lee otra columna de `per` (alias pr, pc y pu).
--
-- Lee `raw` y `postventa` (lo publica este mismo paso).
-- ============================================================================

DROP TABLE IF EXISTS postventa_restringida.contactos_incidencia CASCADE;
CREATE TABLE postventa_restringida.contactos_incidencia AS
SELECT
    i.incidencia_id                                 AS incidencia_id,
    i.codigo_incidencia                             AS codigo_incidencia,
    NULLIF(r.cliide, 0)                             AS propietario_id,
    NULLIF(BTRIM(cp.res), '')                       AS propietario_nombre,
    NULLIF(r.recide, 0)                             AS reclamante_id,
    NULLIF(BTRIM(pr.nom), '')                       AS reclamante_nombre,
    NULLIF(BTRIM(pr.tel), '')                       AS reclamante_telefono,
    NULLIF(BTRIM(pr.tel2), '')                      AS reclamante_telefono_2,
    NULLIF(BTRIM(pr.ele), '')                       AS reclamante_correo,
    NULLIF(r.cntide, 0)                             AS contacto_id,
    NULLIF(BTRIM(pc.nom), '')                       AS contacto_nombre,
    NULLIF(BTRIM(pc.tel), '')                       AS contacto_telefono,
    NULLIF(BTRIM(pc.tel2), '')                      AS contacto_telefono_2,
    NULLIF(BTRIM(pc.ele), '')                       AS contacto_correo,
    NULLIF(BTRIM(r.tel), '')                        AS telefonos_avisos,
    NULLIF(BTRIM(r.ele), '')                        AS correo_avisos
FROM      postventa.incidencias i
JOIN      raw.rcp r ON r.ide = i.incidencia_id
LEFT JOIN raw.con cp ON cp.ide = NULLIF(r.cliide, 0)
LEFT JOIN raw.per pr ON pr.ide = NULLIF(r.recide, 0)
LEFT JOIN raw.per pc ON pc.ide = NULLIF(r.cntide, 0);

ALTER TABLE postventa_restringida.contactos_incidencia ADD PRIMARY KEY (incidencia_id);

COMMENT ON TABLE postventa_restringida.contactos_incidencia IS
'ACCESO RESTRINGIDO (perfil postventa y total; autorizacion del humano, d1 ok, 2026-11-03). Las personas de cada incidencia de postventa (F-156): propietario, quien reclama y contacto, con nombre, telefonos y correo. Nunca el DNI. Se cruza con postventa.incidencias por incidencia_id.';

DROP TABLE IF EXISTS postventa_restringida.contactos_unidad CASCADE;
CREATE TABLE postventa_restringida.contactos_unidad AS
SELECT
    un.unidad_id                                    AS unidad_id,
    un.codigo_unidad                                AS codigo_unidad,
    NULLIF(u.cliide, 0)                             AS propietario_id,
    NULLIF(BTRIM(cp.res), '')                       AS propietario_nombre,
    NULLIF(u.peride, 0)                             AS contacto_id,
    NULLIF(BTRIM(pu.nom), '')                       AS contacto_nombre,
    NULLIF(BTRIM(pu.tel), '')                       AS contacto_telefono,
    NULLIF(BTRIM(pu.tel2), '')                      AS contacto_telefono_2,
    NULLIF(BTRIM(pu.ele), '')                       AS contacto_correo,
    NULLIF(BTRIM(u.restel), '')                     AS telefono_unidad,
    NULLIF(BTRIM(u.resele), '')                     AS correo_unidad,
    COALESCE(u.avi_tfno <> 0, FALSE)                AS aviso_telefono,
    COALESCE(u.avi_mail <> 0, FALSE)                AS aviso_correo,
    COALESCE(u.hor_man <> 0, FALSE)                 AS horario_manana,
    COALESCE(u.hor_tar <> 0, FALSE)                 AS horario_tarde,
    COALESCE(u.hor_otr <> 0, FALSE)                 AS horario_otros,
    NULLIF(BTRIM(u.texohor), '')                    AS texto_otro_horario
FROM      postventa.unidades un
JOIN      raw.upv u ON u.ide = un.unidad_id
LEFT JOIN raw.con cp ON cp.ide = NULLIF(u.cliide, 0)
LEFT JOIN raw.per pu ON pu.ide = NULLIF(u.peride, 0);

ALTER TABLE postventa_restringida.contactos_unidad ADD PRIMARY KEY (unidad_id);

COMMENT ON TABLE postventa_restringida.contactos_unidad IS
'ACCESO RESTRINGIDO (perfil postventa y total; autorizacion del humano, d1 ok, 2026-11-03). Las personas de cada unidad postventa (F-156): propietario, persona de contacto, telefono y correo de la unidad, avisos y horarios. Nunca el DNI. Se cruza con postventa.unidades por unidad_id.';

DROP TABLE IF EXISTS postventa_restringida.textos CASCADE;
CREATE TABLE postventa_restringida.textos AS
SELECT
    i.incidencia_id                                 AS documento_id,
    708                                             AS tipo_documento_codigo,
    i.codigo_incidencia                             AS codigo_documento,
    NULLIF(BTRIM(c.res), '')                        AS descripcion,
    NULLIF(BTRIM(r.tex), '')                        AS descripcion_larga,
    NULLIF(BTRIM(r.motrcp), '')                     AS motivo
FROM postventa.incidencias i
JOIN raw.rcp r ON r.ide = i.incidencia_id
JOIN raw.con c ON c.ide = i.incidencia_id
UNION ALL
SELECT
    ta.tarea_id                                     AS documento_id,
    47                                              AS tipo_documento_codigo,
    ta.codigo_tarea                                 AS codigo_documento,
    NULLIF(BTRIM(c.res), '')                        AS descripcion,
    NULLIF(BTRIM(t.tex), '')                        AS descripcion_larga,
    NULL::TEXT                                      AS motivo
FROM postventa.tareas ta
JOIN raw.tar t ON t.ide = ta.tarea_id
JOIN raw.con c ON c.ide = ta.tarea_id;

ALTER TABLE postventa_restringida.textos ADD PRIMARY KEY (documento_id);

COMMENT ON TABLE postventa_restringida.textos IS
'ACCESO RESTRINGIDO (perfil postventa y total; autorizacion del humano, d1 ok, 2026-11-03). Los textos INTEGROS, sin mascara, de incidencias (708) y tareas (47) de postventa (F-156): descripcion, descripcion larga y motivo. En postventa van con telefonos y correos enmascarados.';
