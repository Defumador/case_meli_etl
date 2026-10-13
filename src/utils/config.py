import logging
import os
from pathlib import Path
import yaml
from dotenv import find_dotenv, load_dotenv

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / 'config' / 'config.yaml'

REQUIRED_CONFIG = {
    'api': ['base_url', 'endpoints'],
    'product': ['query'],
    'search': ['site', 'page_size', 'multi_get'],
    'currency': ['from', 'to'],
}

REQUIRED_ENDPOINTS = [
    'token', 'products_search', 'product_items',
    'currency_conversions', 'users'
]

REQUIRED_ENV = [
    'ML_CLIENT_ID', 'ML_CLIENT_SECRET',
    'DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
]  


def load_config(path=DEFAULT_CONFIG_PATH):
    env_file = find_dotenv(usecwd=True)
    if env_file:
        load_dotenv(env_file)
        logger.info('Variáveis de ambiente carregadas de %s', env_file)
    else:
        logger.warning('Arquivo .env não encontrado; usando só as variáveis do sistema')

    path = Path(path)
    try:
        with open(path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error('Arquivo de configuração não encontrado: %s', path)
        raise
    except yaml.YAMLError:
        logger.exception('Config inválido (YAML malformado): %s', path)
        raise
    logger.info('Configuração carregada de %s', path)

    _validate_config(cfg)

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        logger.error('Variáveis de ambiente faltando: %s', missing)
        raise EnvironmentError(f'Variáveis de ambiente faltando: {missing}')

    return cfg


def _validate_config(cfg):
    problems = []
    for section, keys in REQUIRED_CONFIG.items():
        block = (cfg or {}).get(section)
        if not isinstance(block, dict):
            problems.append(f'seção "{section}" ausente')
            continue
        problems += [f'{section}.{key}' for key in keys if block.get(key) in (None, '')]

    endpoints = ((cfg or {}).get('api') or {}).get('endpoints') or {}
    problems += [f'api.endpoints.{name}' for name in REQUIRED_ENDPOINTS if not endpoints.get(name)]

    if problems:
        logger.error('config.yaml incompleto: %s', problems)
        raise ValueError(f'config.yaml incompleto: {problems}')
