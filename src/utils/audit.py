import logging

from src.load import TABLES
from src.utils.db import get_connection

logger = logging.getLogger(__name__)

LOADED, FAILED, NOT_LOADED = 'LOADED', 'FAILED', 'NOT_LOADED'


def build_table_status(success=False, failed_table=None):
    # sucesso: todas LOADED
    # falha no load: tabela com erro fica FAILED e as outras NOT_LOADED
    # falha antes do load: todas NOT_LOADED
    status = {table: NOT_LOADED for table in TABLES}
    if success:
        status = {table: LOADED for table in TABLES}
    elif failed_table in status:
        status[failed_table] = FAILED
    return status


def log_run(job_run, search_term, status, execution_seconds,
            table_status, log_path, error_message=None):
    query = '''
        INSERT INTO etl_runs
            (job_run, search_term, status, execution_seconds, status_sellers,
            status_products, status_listings, error_message, log_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    '''
    values = (
        job_run, search_term, status, round(execution_seconds, 2),
        table_status['sellers'], table_status['products'],
        table_status['listings'], error_message, log_path
    )

    try:
        conn = get_connection()
        with conn, conn.cursor() as cur:
            cur.execute(query, values)
        conn.close()
        logger.info('Auditoria registrada: %s', status)
    except Exception:
        logger.exception('Não foi possível gravar a auditoria')
