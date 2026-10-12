-- DDL - ETL Mercado Livre (PostgreSQL)
-- Observação: JOB_RUN (DATETIME no enunciado) é TIMESTAMP no PostgreSQL.
-- O histórico é preservado por corrida, por isso job_run faz parte das PKs.

-- Sellers das publicações extraídas
CREATE TABLE IF NOT EXISTS sellers (
    seller_id            BIGINT       NOT NULL,
    nickname             VARCHAR(100),
    site_id              VARCHAR(5),
    user_type            VARCHAR(30),
    reputation_level_id  VARCHAR(30),
    transactions_total   INT,
    site_status          VARCHAR(30),
    job_run              TIMESTAMP    NOT NULL,
    PRIMARY KEY (seller_id, job_run)
);

-- Produtos do catálogo
CREATE TABLE IF NOT EXISTS products (
    product_id       VARCHAR(20)  NOT NULL,
    name             TEXT,
    parent_id        VARCHAR(20),
    domain_id        VARCHAR(30),
    brand            VARCHAR(50),
    line             VARCHAR(50),
    model            VARCHAR(50),
    ram              VARCHAR(20),
    internal_memory  VARCHAR(20),
    color            VARCHAR(50),
    quality_type     VARCHAR(20),
    job_run          TIMESTAMP    NOT NULL,
    PRIMARY KEY (product_id, job_run)
);

-- Publicações de cada produto
-- total_sales: a API não informa, a coluna fica nula
CREATE TABLE IF NOT EXISTS listings (
    item_id              VARCHAR(20)   NOT NULL,
    site_id              VARCHAR(5),
    product_id           VARCHAR(20),
    seller_id            BIGINT,
    accepts_mercadopago  BOOLEAN,
    price                NUMERIC(14,2),
    currency_id          VARCHAR(5),
    condition            VARCHAR(10),
    listing_type_id      VARCHAR(30),
    logistic_type        VARCHAR(30),
    warranty             TEXT,
    user_product_id      VARCHAR(30),
    total_sales          INT,
    price_converted      NUMERIC(14,2),
    converted_currency   VARCHAR(5),
    is_outlier           BOOLEAN,
    has_warranty         BOOLEAN,
    job_run              TIMESTAMP     NOT NULL,
    PRIMARY KEY (item_id, job_run)
);
CREATE INDEX IF NOT EXISTS idx_listings_job_run ON listings (job_run);

-- Controle de execução do ETL 
CREATE TABLE IF NOT EXISTS etl_runs (
    job_run            TIMESTAMP     PRIMARY KEY,
    search_term        VARCHAR(200),
    status             VARCHAR(10)   NOT NULL,
    execution_seconds  NUMERIC(10,2),
    status_sellers     VARCHAR(12),
    status_products    VARCHAR(12),
    status_listings    VARCHAR(12),
    log_path           VARCHAR(100),
    error_message      TEXT
);
