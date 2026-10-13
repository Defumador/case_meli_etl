import logging
import sys
import time
from datetime import datetime

from src.utils.audit import build_table_status, log_run
from src.utils.config import load_config
from src.utils.api import MELIClient
from src.utils.logger import setup_logging

from src.extract import extract_all
from src.load import LoadError, load_all
from src.transform import transform_all

logger = logging.getLogger('etl')


def _search_term(cfg):
    query = cfg['product']['query']
    return ', '.join(query) if isinstance(query, (list, tuple)) else str(query)


def main():
    start = time.time()
    job_run = datetime.now().replace(microsecond=0)   
    log_path = setup_logging(job_run)
    logger.info('Iniciando ETL | JOB_RUN=%s', job_run)

    cfg = load_config()                               
    term = _search_term(cfg)

    try:
        client = MELIClient(cfg)

        products, listings, sellers, conversion = extract_all(client, cfg)
        if not listings:
            raise RuntimeError('Nenhuma publicação extraída; abortando antes do load')

        data = transform_all(products, listings, sellers, conversion, cfg)

        load_all(data, job_run)

        log_run(job_run, term, 'SUCCESS', time.time() - start,
                build_table_status(success=True), log_path)
        logger.info('ETL finalizado com sucesso em %.1fs', time.time() - start)

    except Exception as e:
        failed_table = e.table if isinstance(e, LoadError) else None
        log_run(job_run, term, 'FAILED', time.time() - start,
                build_table_status(failed_table=failed_table), log_path, str(e)[:500])
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logger.exception('ETL falhou')
        sys.exit(1)
