-- Schéma VoltEye : PostgreSQL + TimescaleDB (séries temporelles) + pgvector (documents de l'assistant)
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

-- Référentiel ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS site (
    id          serial PRIMARY KEY,
    code        text UNIQUE NOT NULL,          -- identifiant court utilisé dans les sujets MQTT
    name        text NOT NULL,
    kind        text NOT NULL,                 -- 'usine' (site de référence) ou 'zone' (zone industrielle)
    sector      text,
    factories   int DEFAULT 1,
    lat         double precision,
    lon         double precision
);

CREATE TABLE IF NOT EXISTS meter (                -- NILM : un seul compteur par site
    id          serial PRIMARY KEY,
    site_id     int NOT NULL REFERENCES site (id),
    name        text NOT NULL
);

CREATE TABLE IF NOT EXISTS machine (
    id          serial PRIMARY KEY,
    site_id     int NOT NULL REFERENCES site (id),
    mtype       text NOT NULL,
    name        text NOT NULL,
    label       text,
    p_rated_kw  real,
    pf          real
);

-- Séries temporelles -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS measurement (          -- 1 ligne par seconde et par compteur
    time        timestamptz NOT NULL,
    meter_id    int NOT NULL,
    p_kw        real,
    q_kvar      real,
    pf          real,
    thd         real,
    estimated   jsonb                          -- puissance estimée par machine (désagrégation)
);
SELECT create_hypertable('measurement', 'time', chunk_time_interval => interval '1 day', if_not_exists => true);
CREATE INDEX IF NOT EXISTS measurement_meter_time ON measurement (meter_id, time DESC);

CREATE TABLE IF NOT EXISTS event (                -- démarrages et arrêts reconnus
    time        timestamptz NOT NULL,
    meter_id    int NOT NULL,
    direction   text,
    delta_kw    real,
    mtype       text,
    confidence  real,
    proba       jsonb,
    waveform    real[],                        -- extrait de 40 ms (différence après - avant)
    gradcam     real[]                         -- carte Grad-CAM 32 x 32 de la décision du CNN
);
SELECT create_hypertable('event', 'time', chunk_time_interval => interval '7 days', if_not_exists => true);

CREATE TABLE IF NOT EXISTS machine_load (         -- énergie horaire de chaque machine (désagrégée)
    time        timestamptz NOT NULL,
    site_id     int NOT NULL,
    mtype       text NOT NULL,
    kwh         real,
    thd         real
);
SELECT create_hypertable('machine_load', 'time', chunk_time_interval => interval '30 days', if_not_exists => true);

CREATE TABLE IF NOT EXISTS context_hourly (       -- calendrier et météo du site
    time        timestamptz NOT NULL,
    site_id     int NOT NULL,
    temperature real,
    production  boolean,
    holiday     boolean,
    ramadan     boolean
);
SELECT create_hypertable('context_hourly', 'time', chunk_time_interval => interval '30 days', if_not_exists => true);

CREATE TABLE IF NOT EXISTS forecast (
    time        timestamptz NOT NULL,
    site_id     int NOT NULL,
    p10         real,
    p50         real,
    p90         real,
    actual      real,
    baseline    real
);
SELECT create_hypertable('forecast', 'time', chunk_time_interval => interval '30 days', if_not_exists => true);

-- Résultats d'analyse ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomaly (
    day             date NOT NULL,
    site_id         int NOT NULL,
    mtype           text NOT NULL,
    energy_kwh      real,
    expected_kwh    real,
    score           real,
    alert           boolean,
    cause           text,
    excess_cost_tnd real,
    period          text,
    PRIMARY KEY (day, site_id, mtype)
);

CREATE TABLE IF NOT EXISTS health (
    day         date NOT NULL,
    site_id     int NOT NULL,
    mtype       text NOT NULL,
    thd         real,
    drift       real,
    health      real,
    days_left   real,
    alert       boolean,
    PRIMARY KEY (day, site_id, mtype)
);

CREATE TABLE IF NOT EXISTS schedule_day (         -- planning optimisé d'un jour (usine)
    day         date PRIMARY KEY,
    data        jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS grid_day (             -- VoltEye Grid : trois stratégies pour un jour d'été
    day         date PRIMARY KEY,
    data        jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS metric (               -- résultats d'évaluation (un document par module)
    name        text PRIMARY KEY,
    data        jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_chunk (            -- documents approuvés pour l'assistant (RAG)
    id          serial PRIMARY KEY,
    source      text NOT NULL,
    title       text,
    content     text NOT NULL,
    embedding   vector(384)
);

-- Agrégats continus ------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS measurement_15min
WITH (timescaledb.continuous) AS
SELECT time_bucket('15 minutes', time) AS bucket, meter_id,
       avg(p_kw) AS p_kw, max(p_kw) AS p_max_kw, avg(thd) AS thd
FROM measurement GROUP BY bucket, meter_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS machine_load_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', time) AS day, site_id, mtype, sum(kwh) AS kwh, avg(thd) AS thd
FROM machine_load GROUP BY day, site_id, mtype
WITH NO DATA;

SELECT add_continuous_aggregate_policy('measurement_15min', start_offset => interval '2 hours',
       end_offset => interval '1 minute', schedule_interval => interval '1 minute', if_not_exists => true);

-- Compression des anciennes mesures
ALTER TABLE measurement SET (timescaledb.compress, timescaledb.compress_segmentby = 'meter_id');
SELECT add_compression_policy('measurement', interval '7 days', if_not_exists => true);

-- Rôle en lecture seule pour l'outil SQL de l'assistant
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'volteye_lecture') THEN
        CREATE ROLE volteye_lecture LOGIN PASSWORD 'lecture';
    END IF;
END $$;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO volteye_lecture;
