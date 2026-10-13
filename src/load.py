import logging

from psycopg2.extras import execute_values, Json

from src.utils.db import get_connection

logger = logging.getLogger(__name__)

TABLES = {
    'sellers': [
        'seller_id', 'nickname', 'site_id', 'user_type',
        'reputation_level_id', 'transactions_total', 'site_status', 'job_run',
    ],
    'products': [
        'product_id', 'name', 'parent_id', 'domain_id', 'brand', 'line',
        'model', 'attributes', 'quality_type', 'job_run',
    ],
    'listings': [
        'item_id', 'site_id', 'product_id', 'seller_id', 'accepts_mercadopago',
        'price', 'currency_id', 'condition', 'listing_type_id', 'logistic_type',
        'warranty', 'user_product_id', 'total_sales', 'price_converted',
        'converted_currency', 'is_outlier', 'has_warranty', 'job_run',
    ],
}


class LoadError(Exception):
    def __init__(self, table, error):
        super().__init__(f"Falha ao carregar a tabela '{table}': {error}")
        self.table = table


def load_table(cur, table, rows, job_run):
    # Insere em lote
    if not rows:
        logger.warning('Nenhum registro para %s', table)
        return 0

    columns = TABLES[table]
    values = [
        tuple(
            job_run if col == 'job_run'
            else Json(row.get('attributes') or {})
            if table == 'products' and col == 'attributes'
            else row.get(col)
            for col in columns
        )
        for row in rows
    ]
    query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s"
    execute_values(cur, query, values, page_size=500)

    logger.info('%s: %s registros inseridos', table, len(values))
    return len(values)


def load_all(data, job_run):
    # Carrega todas as tabelas numa única transação.
    # Se uma tabela falhar, faz rollback de todas e levanta LoadError.
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:       
            for table in TABLES:
                try:
                    load_table(cur, table, data.get(table, []), job_run)
                except Exception as e:
                    raise LoadError(table, e) from e
    except LoadError:
        logger.exception('Erro no load; rollback executado')
        raise
    finally:
        conn.close()
