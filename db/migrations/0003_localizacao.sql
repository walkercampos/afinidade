-- 0003: localização aproximada.
--
-- Só guardamos a célula geohash de 5 caracteres (~4,9 km x 4,9 km) e o CENTRO dessa célula.
-- As coordenadas enviadas pelo aparelho são descartadas na API antes de chegar aqui, e as
-- distâncias são sempre calculadas entre centros de célula: ninguém consegue, nem por
-- triangulação, saber mais do que "qual quadrado de ~5 km".
ALTER TABLE perfis
    ADD COLUMN geohash          text CHECK (geohash ~ '^[0123456789bcdefghjkmnpqrstuvwxyz]{5}$'),
    ADD COLUMN lat_aprox        double precision CHECK (lat_aprox BETWEEN -90 AND 90),
    ADD COLUMN lon_aprox        double precision CHECK (lon_aprox BETWEEN -180 AND 180),
    ADD COLUMN distancia_max_km smallint CHECK (distancia_max_km BETWEEN 5 AND 500),
    ADD CONSTRAINT localizacao_completa CHECK ((geohash IS NULL) = (lat_aprox IS NULL) AND (geohash IS NULL) = (lon_aprox IS NULL));

-- Pré-filtro por "caixa" de latitude antes do cálculo exato de distância.
CREATE INDEX perfis_lat_aprox_idx ON perfis (lat_aprox) WHERE visivel AND lat_aprox IS NOT NULL;

-- Distância em km entre dois pontos (fórmula de haversine).
CREATE OR REPLACE FUNCTION distancia_km(lat1 double precision, lon1 double precision,
                                        lat2 double precision, lon2 double precision)
RETURNS double precision LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT 2 * 6371.0088 * asin(sqrt(
        sin(radians(lat2 - lat1) / 2) ^ 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ^ 2
    ))
$$;
