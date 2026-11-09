-- etl_sigrid/infrastructure/postgres/sql/ventas/07_guardas.sql
-- ============================================================================
-- F-040 · VENTAS (8/8): LA GUARDA (R24, R25).
--
-- Un solo bloque DO que tumba el paso (RAISE EXCEPTION, con la cifra) si lo
-- construido no es lo que dice `raw` o si algo personal ha quedado en el
-- esquema general. El paso termina FAILED y la noche sigue: nadie depende de
-- `build_ventas` y `R-FRESCURA` avisa de que `ventas` viene de una noche
-- anterior.
--
-- R25 · CUADRE CON `raw`:
--   * recuentos: `ventas.facturas` y `ventas_restringida.factura_cabecera`
--     = `raw.dvf`; `ventas.factura_lineas` = `raw.dvfpro`;
--     `ventas.certificaciones` = `raw.cer`;
--     `ventas_restringida.clientes_contacto` = `raw.cli`. Un JOIN que
--     duplique o pierda filas se ve aqui.
--   * Σ `base` de `ventas.facturas` = Σ `raw.dvf.totbas`, al centimo.
--   * las cuatro columnas de los recargos suman Σ `cuo` de los recargos de
--     las facturas (y de las certificaciones) que existen: el reparto de
--     `ventas.fn_clase_recargo` no pierde ni duplica nada, sea cual sea
--     `CLASES_GARANTIA` (D4).
-- R24 · NADA PERSONAL EN `ventas`:
--   * ningun `cif` de `ventas.clientes` ni `cif_cliente` de `ventas.facturas`
--     de una persona fisica o con forma de NIF de persona (el patron de
--     `PATRON_NIF_PERSONA`);
--   * ninguna `descripcion` de linea de una factura de persona fisica;
--   * ninguna columna del esquema `ventas` cuyo nombre empiece por un prefijo
--     de `PREFIJOS_PROHIBIDOS_EN_VENTAS` (los de `ventas_restringida`).
--
-- Lee de: ventas.*, ventas_restringida.*, raw.dvf, raw.dvfpro, raw.cer,
--         raw.cli, raw.dvfrec, raw.cerrec, information_schema.columns.
-- Escribe en: nada.
-- ============================================================================

DO $$
DECLARE
    v_publicadas BIGINT;
    v_origen     BIGINT;
    v_publicado  NUMERIC;
    v_esperado   NUMERIC;
    v_columnas   TEXT;
BEGIN
    -- R25 · recuentos frente a raw -----------------------------------------
    v_publicadas := (SELECT count(*) FROM ventas.facturas);
    v_origen     := (SELECT count(*) FROM raw.dvf);
    IF v_publicadas <> v_origen THEN
        RAISE EXCEPTION 'F-040 R25: ventas.facturas tiene % filas y raw.dvf %', v_publicadas, v_origen;
    END IF;

    v_publicadas := (SELECT count(*) FROM ventas.factura_lineas);
    v_origen     := (SELECT count(*) FROM raw.dvfpro);
    IF v_publicadas <> v_origen THEN
        RAISE EXCEPTION 'F-040 R25: ventas.factura_lineas tiene % filas y raw.dvfpro %', v_publicadas, v_origen;
    END IF;

    v_publicadas := (SELECT count(*) FROM ventas.certificaciones);
    v_origen     := (SELECT count(*) FROM raw.cer);
    IF v_publicadas <> v_origen THEN
        RAISE EXCEPTION 'F-040 R25: ventas.certificaciones tiene % filas y raw.cer %', v_publicadas, v_origen;
    END IF;

    v_publicadas := (SELECT count(*) FROM ventas_restringida.clientes_contacto);
    v_origen     := (SELECT count(*) FROM raw.cli);
    IF v_publicadas <> v_origen THEN
        RAISE EXCEPTION 'F-040 R25: ventas_restringida.clientes_contacto tiene % filas y raw.cli %', v_publicadas, v_origen;
    END IF;

    v_publicadas := (SELECT count(*) FROM ventas_restringida.factura_cabecera);
    v_origen     := (SELECT count(*) FROM raw.dvf);
    IF v_publicadas <> v_origen THEN
        RAISE EXCEPTION 'F-040 R25: ventas_restringida.factura_cabecera tiene % filas y raw.dvf %', v_publicadas, v_origen;
    END IF;

    -- R25 · la base, al centimo ---------------------------------------------
    v_publicado := (SELECT COALESCE(SUM(base), 0) FROM ventas.facturas);
    v_esperado  := (SELECT COALESCE(SUM(COALESCE(totbas, 0)::NUMERIC(18, 2)), 0) FROM raw.dvf);
    IF v_publicado <> v_esperado THEN
        RAISE EXCEPTION 'F-040 R25: la base de ventas.facturas suma % y la de raw.dvf %', v_publicado, v_esperado;
    END IF;

    -- R25 · el reparto de los recargos en cuatro columnas ---------------------
    v_publicado := (SELECT COALESCE(SUM(importe_coeficientes + retencion_garantia + retencion_retesp + retencion_otras), 0) FROM ventas.facturas);
    v_esperado  := (SELECT COALESCE(SUM(r.cuo::NUMERIC(18, 2)), 0) FROM raw.dvfrec r JOIN raw.dvf f ON f.ide = r.docide);
    IF v_publicado <> v_esperado THEN
        RAISE EXCEPTION 'F-040 R25: los recargos de ventas.facturas suman % y los de raw.dvfrec %', v_publicado, v_esperado;
    END IF;

    v_publicado := (SELECT COALESCE(SUM(importe_coeficientes + retencion_garantia + retencion_retesp + retencion_otras), 0) FROM ventas.certificaciones);
    v_esperado  := (SELECT COALESCE(SUM(r.cuo::NUMERIC(18, 2)), 0) FROM raw.cerrec r JOIN raw.cer k ON k.ide = r.docide);
    IF v_publicado <> v_esperado THEN
        RAISE EXCEPTION 'F-040 R25: los recargos de ventas.certificaciones suman % y los de raw.cerrec %', v_publicado, v_esperado;
    END IF;

    -- R24 · ningun CIF de persona fisica en ventas ----------------------------
    v_publicadas := (SELECT count(*) FROM ventas.clientes WHERE cif IS NOT NULL AND (es_persona_fisica OR COALESCE(ventas.fn_cif_normalizado(cif) ~ '^[0-9KLMXYZ][0-9]{7}[A-Z]$', FALSE)));
    IF v_publicadas <> 0 THEN
        RAISE EXCEPTION 'F-040 R24: ventas.clientes publica el CIF de % personas fisicas', v_publicadas;
    END IF;

    v_publicadas := (SELECT count(*) FROM ventas.facturas WHERE cif_cliente IS NOT NULL AND (es_persona_fisica OR COALESCE(ventas.fn_cif_normalizado(cif_cliente) ~ '^[0-9KLMXYZ][0-9]{7}[A-Z]$', FALSE)));
    IF v_publicadas <> 0 THEN
        RAISE EXCEPTION 'F-040 R24: ventas.facturas publica el CIF de una persona fisica en % facturas', v_publicadas;
    END IF;

    -- R24 · ninguna descripcion de linea de persona fisica --------------------
    v_publicadas := (SELECT count(*) FROM ventas.factura_lineas l JOIN ventas.facturas f ON f.factura_id = l.factura_id WHERE f.es_persona_fisica AND l.descripcion IS NOT NULL);
    IF v_publicadas <> 0 THEN
        RAISE EXCEPTION 'F-040 R24: ventas.factura_lineas publica la descripcion de % lineas de personas fisicas', v_publicadas;
    END IF;

    -- R24 · ninguna columna personal en el esquema ventas ---------------------
    SELECT count(*), string_agg(table_name || '.' || column_name, ', ' ORDER BY table_name, column_name)
      INTO v_publicadas, v_columnas
      FROM information_schema.columns
     WHERE table_schema = 'ventas'
       AND (column_name LIKE 'direccion%' OR column_name LIKE 'telefono%' OR column_name LIKE 'correo%' OR column_name LIKE 'cif_cabecera%' OR column_name LIKE 'nombre_cabecera%');
    IF v_publicadas <> 0 THEN
        RAISE EXCEPTION 'F-040 R24: el esquema ventas tiene % columnas personales: %', v_publicadas, v_columnas;
    END IF;
END $$;
