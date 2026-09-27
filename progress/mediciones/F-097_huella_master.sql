-- progress/mediciones/F-097_huella_master.sql
-- F-097: huella por version del des del master (ambito 8). SOLO LECTURA contra Sigrid
-- (SQL Server 2012: HASHBYTES admite 8000 bytes, por eso primer y ultimo tramo +
-- longitud + can + pre; ciego a un cambio en mitad de un des de mas de 16000 bytes).
-- Toma 1: 2026-09-27 18:25 UTC -> F-097_huella_master_2026-09-27.csv
SELECT obride, fas, COUNT(*) filas, SUM(CAST(DATALENGTH(des) AS bigint)) bytes, SUM(CASE WHEN DATALENGTH(des) > 16000 THEN 1 ELSE 0 END) largas, CHECKSUM_AGG(CHECKSUM(ide, DATALENGTH(des), HASHBYTES('SHA2_256', SUBSTRING(CAST(des AS varchar(max)), 1, 8000)), HASHBYTES('SHA2_256', SUBSTRING(CAST(des AS varchar(max)), CASE WHEN DATALENGTH(des) > 8000 THEN DATALENGTH(des) - 7999 ELSE 1 END, 8000)), can, pre)) huella FROM obrparpre WHERE amb = 8 AND DATALENGTH(des) > 0 GROUP BY obride, fas
