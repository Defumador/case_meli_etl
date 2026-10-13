# ETL Mercado Livre - Samsung Galaxy (Argentina)

Automação ETL em Python que consulta as APIs do Mercado Livre Argentina (MLA), extrai **produtos novos da linha Samsung Galaxy** (escolhido o modelo **S25 FE**), transforma os dados, carrega em PostgreSQL e responde às perguntas de negócio do Best Seller com queries SQL.

## Sumário
1. [Objetivo e perguntas do negócio](#1-objetivo-e-perguntas-do-negócio)
2. [Arquitetura](#2-arquitetura)
3. [Estrutura do projeto](#3-estrutura-do-projeto)
4. [Instalação](#4-instalação)
5. [Configuração](#5-configuração)
6. [Como executar](#6-como-executar)
7. [Modelo de dados](#7-modelo-de-dados)
8. [Perguntas e queries](#8-perguntas-e-queries)
9. [Endpoints da API Mercado Livre: status e documentação](#9-endpoints-da-api-mercado-livre-status-e-documentação)
10. [Auditoria e logs](#10-auditoria-e-logs)
11. [Decisões técnicas](#11-decisões-técnicas)
12. [Desafios encontrados](#12-desafios-encontrados)
13. [Tratamento de erros](#13-tratamento-de-erros)
14. [Oportunidades de melhoria](#14-oportunidades-de-melhoria)
15. [Material complementar](#15-material-complementar)

---

## 1. Objetivo e perguntas do negócio

O Best Seller de Mercado Libre Argentina precisa de dados sobre publicações de "Samsung Galaxy XXX" (modelo à escolha; neste projeto, o **S25 FE**). Perguntas a responder:

1. Há algum vendedor com múltiplas publicações? Com quantas?
2. Qual a média de vendas por vendedor?
3. Qual o preço médio em dólares?
4. Qual a porcentagem de artigos com garantia?
5. Quais métodos de envio (shipping) são oferecidos?

**Requisitos do case atendidos**

| Requisito | Como foi atendido |
|---|---|
| Python, execução local, código no GitHub | Projeto em Python executado com `python -m src.main` |
| Paginação de 50 registros | `page_size: 50` no `config.yaml`, aplicado em produtos e publicações |
| Limite opcional de registros | `max_products` e `max_items` (opcionais) |
| Somente produtos novos | `condition=new` enviado na busca de produtos |
| Banco local ou BigQuery | PostgreSQL |
| Campo `JOB_RUN` (DATETIME) em todas as tabelas | Coluna `job_run` (`TIMESTAMP` no PostgreSQL), com o mesmo valor para todos os registros de uma corrida |
| Esquema das tabelas | Seção 7 e arquivo `sql/ddl.sql` |
| Arquivo de configuração | `config/config.yaml` (URL da API, endpoints, paginação, termo de busca, moedas) |
| Credenciais fora do código | Variáveis de ambiente (`.env`) |
| Query por pergunta no README | Seção 8 (e `sql/queries.sql`) |
| Notebook (opcional) | `notebooks/meli_api_teste.ipynb` e `notebooks/analise_respostas.ipynb` |

## 2. Arquitetura

```
┌───────────────────────┐   ┌───────────┐   ┌─────────────┐   ┌──────────────┐
│ API Mercado Libre     │   │  EXTRACT  │   │  TRANSFORM  │   │     LOAD     │
│ /oauth/token          │ → │ produtos  │ → │ limpeza     │ → │ PostgreSQL   │
│ /products/search      │   │ publicações│  │ conversão   │   │ transação    │
│ /products/{id}/items  │   │ sellers   │   │ USD         │   │ única        │
│ /users                │   │ conversão │   │ outliers    │   └──────┬───────┘
│ /currency_conversions │   └───────────┘   │ garantia    │          │
└───────────────────────┘                   └─────────────┘   ┌──────▼───────┐
                                                              │  AUDITORIA   │
                                                              │  etl_runs    │
                                                              └──────┬───────┘
                                                                     │
                                                                Queries SQL 
```

**Fluxo de uma execução** (`src/main.py`)
1. Gera o `JOB_RUN` (data e hora da corrida) e configura o log da execução.
2. Carrega o `.env` e o `config.yaml`, validando as variáveis obrigatórias.
3. **Extract**
   - Pagina `/products/search` (50 por página) e já filtra por marca e modelo.
   - Para cada produto, pagina `/products/{id}/items` para obter as publicações.
   - Consulta os vendedores das publicações em lotes (`/users?ids=...`).
   - Obtém a taxa de conversão ARS → USD.
4. **Transform**: monta as tabelas `sellers`, `products` e `listings`, converte preços para USD, calcula a flag de garantia e marca outliers de preço.
5. **Load**: grava as três tabelas em **uma única transação** , usando o mesmo `job_run` em todos os registros.
6. **Auditoria**: registra o resultado da corrida em `etl_runs`, inclusive quando houve falha.

**Endpoints utilizados**

| Endpoint | Uso |
|---|---|
| `POST /oauth/token` | Token de acesso (`client_credentials`) |
| `GET /products/search` | Produtos do catálogo (busca por termo e site) |
| `GET /products/{id}/items` | Publicações de cada produto |
| `GET /users?ids=` | Dados dos vendedores (multiget) |
| `GET /currency_conversions/search` | Taxa de conversão ARS → USD |

## 3. Estrutura do projeto

```
├── config/
│   └── config.yaml
├── notebooks/
│   ├── api_test.ipynb            # teste de conexão e dos endpoints
│   └── analise_respostas.ipynb   # respostas às perguntas com pandas
├── sql/
│   ├── ddl.sql                   # criação das tabelas
│   └── queries.sql               # queries das perguntas
├── src/
│   ├── main.py                   # orquestração (python -m src.main) 
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   └── utils/
│       ├── api.py                # cliente HTTP: autenticação, retry, endpoints
│       ├── db.py                 # conexão com o PostgreSQL
│       ├── audit.py              # registro em etl_runs
│       ├── logger.py             # log em arquivo por execução + console
│       └── config.py             # carga e validação de .env + config.yaml
├── logs/                         # um arquivo por execução
├── .gitignore                    # .env e logs
├── .env.example
├── requirements.txt
└── README.md
```

## 4. Instalação

**Pré-requisitos**: Python 3.10+, PostgreSQL 16+ e uma aplicação criada em [developers.mercadolivre.com.br](https://developers.mercadolivre.com.br) (para obter `client_id` e `client_secret`).

```bash
# 1. Clonar o repositório
git clone https://github.com/Defumador/case_meli_etl.git
cd case_meli_etl

# 2. Ambiente virtual e dependências
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Banco de dados e tabelas
psql -U postgres -c "CREATE DATABASE meli_etl"
psql -U postgres -d meli_etl -f sql/ddl.sql

# 4. Variáveis de ambiente
copy .env.example .env
```

**Dependências** (`requirements.txt`): `requests`, `pyyaml`, `python-dotenv`, `psycopg2-binary`. Para os notebooks: `pandas`, `sqlalchemy`, e `jupyter`.

## 5. Configuração

### Variáveis de ambiente (`.env`)

O `.env.example` mostra as variáveis esperadas.

| Variável | Descrição | Obrigatória |
|---|---|---|
| `ML_CLIENT_ID` | Client ID da aplicação no Mercado Libre | Sim |
| `ML_CLIENT_SECRET` | Client secret da aplicação | Sim |
| `DB_HOST` | Host do PostgreSQL | Sim |
| `DB_PORT` | Porta | Não (padrão 5432) |
| `DB_NAME` | Nome do banco de dados | Sim |
| `DB_USER` | Usuário | Sim |
| `DB_PASSWORD` | Senha | Sim |

### Parâmetros (`config/config.yaml`)

```yaml
api:
  base_url: 'https://api.mercadolibre.com'
  timeout: 10                    # segundos por chamada (recomendado 10s)
  retries: 3                     # tentativas em 429/5xx
  endpoints:
    token: '/oauth/token'
    products_search: '/products/search'
    product_items: '/products/{product_id}/items'
    currency_conversions: '/currency_conversions/search'
    users: '/users'

product:
  query: 'S25 FE'                # modelo(s): texto ou lista
  brand: 'Samsung'               # opcional
  condition: 'new'               # opcional
  category: 'CELLPHONES'         # opcional (domain_id = <site>-<category>)
  attributes:                    # opcional (atributos únicos a serem retornados)
    - 'RAM' 
    - 'INTERNAL_MEMORY' 
    - 'COLOR'  

search:
  site: 'MLA'
  page_size: 50
  max_offset: 100                # limite imposto pela API
  multi_get: 20                  # sellers por chamada
  max_products: 1000             # opcional
  max_items: 1000                # opcional

currency:
  from: ARS
  to: USD

outliers:
  iqr_factor: 1.5
```

A **URL da API e os endpoints** ficam em `api`. São **opcionais**: `brand`, `condition`, `category`, `max_products` e `max_items`. Sem os dois últimos limites, o ETL extrai tudo o que a API permitir; sem `condition` ou `category`, o parâmetro não é enviado à API.

## 6. Como executar

Da **raiz do projeto**:

```bash
python -m src.main
```

Ao terminar o log completo da execução está em `logs/etl_AAAA-MM-DD_HH-MM-SS.log`.

Execute sempre com `-m` e a partir da raiz: rodar `python src/main.py` causa `ModuleNotFoundError: No module named 'src'`.

## 7. Modelo de dados

Todas as tabelas têm `job_run` (`TIMESTAMP`, equivalente ao DATETIME do enunciado) como **última coluna**, com o mesmo valor para todos os registros de uma corrida. O histórico das execuções é preservado, por isso `job_run` faz parte das chaves primárias. 

DDL completo em [`sql/ddl.sql`](sql/ddl.sql).

### `sellers`
| Campo | Tipo | Descrição |
|---|---|---|
| `seller_id` | BIGINT | ID do vendedor (PK) |
| `nickname` | VARCHAR(100) | Nome do vendedor |
| `site_id` | VARCHAR(5) | Site (MLA) |
| `user_type` | VARCHAR(30) | Tipo de usuário (ex.: brand) |
| `reputation_level_id` | VARCHAR(30) | Nível de reputação (`seller_reputation.level_id`) |
| `transactions_total` | INT | Transações históricas (`seller_reputation.transactions.total`) |
| `site_status` | VARCHAR(30) | Status no site (`status.site_status`) |
| `job_run` | TIMESTAMP | Data/hora da corrida (PK) |

### `products`
| Campo | Tipo | Descrição |
|---|---|---|
| `product_id` | VARCHAR(20) | ID do produto de catálogo (PK) |
| `name` | TEXT | Nome do produto |
| `parent_id` | VARCHAR(20) | Produto pai |
| `domain_id` | VARCHAR(30) | Domínio (ex.: MLA-CELLPHONES) |
| `brand` | VARCHAR(50) | Atributo BRAND |
| `line` | VARCHAR(50) | Atributo LINE |
| `model` | VARCHAR(50) | Atributo MODEL |
| `attributes` | JSONB | Atributos únicos |
| `quality_type` | VARCHAR(20) | Qualidade da ficha do produto |
| `job_run` | TIMESTAMP | Data/hora da corrida (PK) |

### `listings`
| Campo | Tipo | Descrição |
|---|---|---|
| `item_id` | VARCHAR(20) | ID da publicação (PK) |
| `site_id` | VARCHAR(5) | Site |
| `product_id` | VARCHAR(20) | Produto de catálogo de origem |
| `seller_id` | BIGINT | Vendedor |
| `accepts_mercadopago` | BOOLEAN | Aceita Mercado Pago |
| `price` | NUMERIC(14,2) | Preço na moeda original |
| `currency_id` | VARCHAR(5) | Moeda original |
| `condition` | VARCHAR(10) | Condição (`new`) |
| `listing_type_id` | VARCHAR(30) | Tipo de publicação |
| `logistic_type` | VARCHAR(30) | Método de envio (`shipping.logistic_type`) |
| `warranty` | TEXT | Texto da garantia |
| `user_product_id` | VARCHAR(30) | ID de user product |
| `total_sales` | INT | Vendas (a API não informa: fica nulo) |
| `price_converted` | NUMERIC(14,2) | Preço convertido |
| `converted_currency` | VARCHAR(5) | Moeda da conversão |
| `is_outlier` | BOOLEAN | Preço atípico (método IQR) |
| `has_warranty` | BOOLEAN | Possui garantia |
| `job_run` | TIMESTAMP | Data/hora da corrida (PK) |

### `etl_runs` (controle de execução)
| Campo | Tipo | Descrição |
|---|---|---|
| `job_run` | TIMESTAMP | Data/hora da corrida (PK) |
| `search_term` | VARCHAR(200) | Termo de busca utilizado |
| `status` | VARCHAR(10) | `SUCCESS` ou `FAILED` |
| `execution_seconds` | NUMERIC(10,2) | Tempo de execução |
| `status_sellers` | VARCHAR(12) | `LOADED`, `FAILED` ou `NOT_LOADED` |
| `status_products` | VARCHAR(12) | `LOADED`, `FAILED` ou `NOT_LOADED` |
| `status_listings` | VARCHAR(12) | `LOADED`, `FAILED` ou `NOT_LOADED` |
| `log_path` | VARCHAR(100) | Caminho do log da execução |
| `error_message` | TEXT | Mensagem de erro, se houver |

## 8. Perguntas e queries

Todas consideram a **última corrida** (`MAX(job_run)`). 
As mesmas queries estão em [`sql/queries.sql`](sql/queries.sql) e a versão em pandas, em `notebooks/analise_respostas.ipynb`.

### 8.1 Há algum vendedor com múltiplas publicações? Com quantas?

```sql
SELECT
    s.nickname,
    l.seller_id,
    COUNT(*) AS total_listings
FROM listings l
LEFT JOIN sellers s
       ON s.seller_id = l.seller_id
      AND s.job_run = l.job_run
WHERE l.job_run = (SELECT MAX(job_run) FROM listings)
GROUP BY s.nickname, l.seller_id
HAVING COUNT(*) > 1
ORDER BY total_listings DESC;
```

### 8.2 Qual a média de vendas por vendedor?

A API **não informa a quantidade vendida por publicação** (`total_sales` fica nulo), então a média calculada a partir das publicações resulta em zero.

```sql
SELECT
    s.nickname,
    l.seller_id,
    COALESCE(SUM(l.total_sales), 0)::NUMERIC / COUNT(*) AS avg_sales
FROM listings l
LEFT JOIN sellers s
       ON s.seller_id = l.seller_id
      AND s.job_run = l.job_run
WHERE l.job_run = (SELECT MAX(job_run) FROM listings)
GROUP BY s.nickname, l.seller_id
ORDER BY avg_sales DESC;
```

### 8.3 Qual o preço médio em dólares?

Desconsidera os outliers de preço (`is_outlier = FALSE`).

```sql
SELECT
    l.converted_currency AS currency,
    ROUND(AVG(l.price_converted), 2) AS avg_price,
    MIN(l.price_converted)           AS min_price,
    MAX(l.price_converted)           AS max_price
FROM listings l
WHERE l.job_run = (SELECT MAX(job_run) FROM listings)
  AND l.is_outlier = FALSE
GROUP BY l.converted_currency;
```

### 8.4 Qual a porcentagem de artigos com garantia?

```sql
SELECT
    COUNT(*) FILTER (WHERE l.has_warranty)     AS with_warranty,
    COUNT(*) FILTER (WHERE NOT l.has_warranty) AS no_warranty,
    ROUND(COUNT(*) FILTER (WHERE l.has_warranty)::NUMERIC / COUNT(*) * 100, 2) AS warranty_coverage
FROM listings l
WHERE l.job_run = (SELECT MAX(job_run) FROM listings);
```

### 8.5 Quais métodos de envio são oferecidos?

```sql
SELECT
    l.logistic_type,
    COUNT(*) AS listings,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER () * 100, 2) AS percentage
FROM listings l
WHERE l.job_run = (SELECT MAX(job_run) FROM listings)
GROUP BY l.logistic_type
ORDER BY listings DESC;
```

### Resultados da corrida de `2026-10-12 14:28:43`

| Pergunta | Resultado |
|---|---|
| 1. Vendedores com múltiplas publicações | 36 vendedores, com até 7 publicações |
| 2. Média de vendas por vendedor | Não disponível via API (`total_sales` nulo) |
| 3. Preço médio em USD (sem outliers) | US$ 984,45 |
| 4. Publicações com garantia | 79,75% |
| 5. Métodos de envio | `xd_drop_off` 56,33% · `drop_off` 21,52% · `fulfillment` 13,29% · `cross_docking` 8,86% |

## 9. Endpoints da API Mercado Livre: status e documentação

Status observado nos testes do projeto (`notebook/meli_api_teste.ipynb` e logs do ETL), em outubro de 2026. A API muda com frequência: reexecute o notebook antes de tomar qualquer decisão com base nesta tabela.

| Endpoint | Status | Comentário | Documentação |
|---|---|---|---|
| `POST /oauth/token` | 200 | Token por `client_credentials` funcionou nos testes. As credenciais ficam no `.env`. | [Authentication and Authorization](https://developers.mercadolibre.com.ar/en_us/es_ar/authentication-and-authorization) |
| `GET /sites/{site}/search` | 403 | Endpoint indicado no case. Bloqueado mesmo com token, por isso foi substituído pelo fluxo de catálogo. Não localizei uma página específica da busca. | [Erro 403](https://developers.mercadolibre.com.mx/error-403) |
| `GET /currencies` | 200 | Lista as moedas. Não é usado no ETL (a taxa vem direto de `/currency_conversions`). | [Locations and currencies](https://developers.mercadolibre.com.mx/en_us/locations-and-currencies) |
| `GET /currency_conversions/search` | 200 | `from=ARS&to=USD` devolve o campo `ratio`, usado para calcular `price_converted`. | [Locations and currencies](https://developers.mercadolibre.com.mx/en_us/locations-and-currencies) |
| `GET /products/search` | 200 (400 com `offset` > 100) | Devolve **produtos de catálogo**, não publicações. | [Products search](https://developers.mercadolibre.com.ar/en_us/products-search) |
| `GET /products/{id}/items` | 200 (404 sem publicações) | Fonte das publicações.  Não traz `total_sales` nem `sold_quantity`. | [Catalog competition](https://developers.mercadolibre.com.ar/devsite/catalog-competition-gs) |
| `GET /users?ids=` | 200 | Multiget de vendedores (nickname, reputação, transações). | [Manage users](https://developers.mercadolibre.com.ar/en_us/services-manage-users) |
| `GET /items?ids=` e `/items/bulk` | Não validado | Testado com ids de catálogo, parents id e product user id, e tudo retornou 404. Não são usados no ETL. | [Consult items](https://developers.mercadolibre.com.mx/en_us/list-products/) |

### Observações

- **Autenticação**: a página de autenticação descreve a troca do código de autorização por um access token. O fluxo `client_credentials`, usado no projeto, funcionou nos testes, mas não o vi descrito nessa página.
- **Documentação desatualizada**: a página de catálogo mostra `sold_quantity` no exemplo de resposta de `/products/{id}/items`, mas as respostas reais do projeto não trazem esse campo. A página indica última atualização em 2023.
- **Filtros de `/products/{id}/items`**: a mesma página lista os filtros aceitos (preço, frete, `seller_id`, entre outros),  `condition` não está entre eles (mas funciona).

## 10. Auditoria e logs

- **`etl_runs`**: uma linha por execução, com termo de busca, status geral, tempo de execução e o status de cada tabela. A auditoria usa uma conexão própria, então o registro é gravado mesmo quando a carga faz rollback.
  - `LOADED`: tabela gravada.
  - `FAILED`: tabela que gerou o erro.
  - `NOT_LOADED`: não gravada (a transação única desfaz as demais, e falhas antes do load também resultam nisso).
- **Logs**: um arquivo por execução, `logs/etl_AAAA-MM-DD_HH-MM-SS.log`, correspondente ao `JOB_RUN`, além da saída no console. Respostas HTTP de erro (4xx) registram o corpo da resposta da API para facilitar o diagnóstico. 

## 11. Decisões técnicas

| Decisão | Motivo |
|---|---|
| Separação em extract, transform e load | Responsabilidade única; facilita manutenção e testes |
| Cliente da API isolado (`utils/api.py`), com URL e endpoints no `config.yaml` | Concentra autenticação e retry; se a API mudar, basta ajustar a configuração |
| Autenticação OAuth `client_credentials` | Os endpoints exigem token de acesso |
| Retry com espera crescente e respeito ao `Retry-After` | Lida com erros 429 e 5xx sem derrubar o ETL |
| Paginação em um gerador reutilizável (`_paginate`) | Evita código duplicado para produtos e publicações |
| Limites opcionais (`max_products`, `max_items`) | Permite testes rápidos sem perder a opção de extrair tudo |
| Filtro por categoria, marca e modelo | A busca do catálogo traz produtos relacionados, variações e modelos parecidos |
| Atributos específicos dos produtos armazenados em uma coluna JSONB | Permite armazenar atributos variáveis, definidos no `config.yaml`, sem criar novas colunas para cada característica. Essa abordagem facilita a integração de diferentes categorias de produtos |
| Multiget de sellers (`/users?ids=`) | Reduz o número de chamadas |
| Carga em transação única | Evita carga parcial: grava todas as tabelas ou nenhuma |
| Insert em lote (`execute_values`) | Mais rápido que um INSERT por linha |
| Histórico por `JOB_RUN` | Permite comparar corridas; as queries filtram pela mais recente |
| Preço convertido para USD, nulo se a moeda não tiver taxa | Prefere nulo a um valor convertido errado |
| Outliers marcados, não removidos (IQR) | Preserva o dado original; a média usa só os não outliers |
| Garantia: campo `warranty` com fallback em `sale_terms` | Cobre as publicações em que o campo vem vazio |
| Auditoria em conexão separada | O registro da falha sobrevive ao rollback |
| Log por execução | Fácil rastrear uma corrida específica pelo `JOB_RUN` |
| `.env` para segredos e `config.yaml` para parâmetros | Atende ao requisito de não deixar credenciais no código |

## 12. Desafios encontrados

- **Endpoints do case indisponíveis**: os endpoints indicados no enunciado (como `/search` e `/items`) não responderam como descrito. A solução foi migrar para os endpoints de catálogo (`/products/search` e `/products/{id}/items`) e consultar os vendedores em `/users`. Isso exigiu um passo a mais: a busca devolve **produtos de catálogo**, e as publicações são obtidas produto a produto.
- **Autenticação obrigatória**: as chamadas exigem access token; foi implementado o fluxo `client_credentials`.
- **Limite de paginação da API**: em `/products/search`, o `offset` máximo aceito é 100. O ETL respeita o limite, registra um aviso e segue com o que foi coletado, sem erro.
- **Resultados que não são o modelo desejado**: dos 245 produtos alcançáveis, apenas 31 passaram no filtro de categoria, marca e modelo. Categoria é aplicada na chamada e o filtro marca/modelo é aplicado página a página no `extract.py`.
- **Produtos sem publicações**: cerca de um terço dos produtos filtrados (10 de 31, nesse teste) retornou 404 em `/products/{id}/items`. É um caso esperado no catálogo e é tratado como informação, não como erro.
- **Quantidade vendida indisponível**: a API não devolve `total_sales` por publicação. 
- **Preços atípicos**: publicações com preços muito fora da faixa distorcem a média; por isso foram marcadas com `is_outlier` pelo método IQR e excluídas da média.

## 13. Tratamento de erros

- **Retry com espera crescente** para 429 e 5xx, com timeout em toda chamada.
- **Falha em uma página de produtos**: registra o erro e segue com o que já foi coletado.
- **Falha em um produto** (publicações): 404 é informativo; 400 encerra a paginação daquele produto; outros erros são registrados e o ETL continua nos demais.
- **Falha em um lote de sellers**: o lote é pulado e registrado.
- **Variáveis de ambiente ausentes ou vazias**: validadas no início, mostrando só os nomes.
- **Nenhuma publicação extraída**: a execução é abortada antes do load, para não gravar uma corrida vazia.
- **Falha no load**: rollback completo e registro em `etl_runs` indicando qual tabela falhou.
- **Falha da própria auditoria**: é registrada no log, sem esconder o erro original.
- **Código de saída 1** em caso de falha, útil para agendadores.

## 14. Oportunidades de melhoria

- **Busca segmentada** para superar o limite de `offset` (por exemplo, uma consulta utilizando atributos).
- **Fonte alternativa para vendas por publicação**, de modo a responder a pergunta 2.
- **Priorizar a carga de listings**, permitindo recuperar retroativamente os dados das demais tabelas.
- **Orquestração** (Airflow ou cron) com alerta de falha.
- **Migração para BigQuery**. 
- **Dashboard em Looker Studio**.
- **Testes** do `transform`.
- **Validação do esquema** das respostas da API.
- **Outliers por produto ou modelo**, em vez de global.
- **Dockerização** do ETL.

## 15. Material complementar

- **Notebook de teste da API**: `notebooks/meli_api_teste.ipynb`.
- **Notebook de análise (pandas)**: `notebooks/analise_respostas.ipynb`.
