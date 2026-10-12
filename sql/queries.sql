-- 1) Há algum vendedor com múltiplas publicações? Se sim, com quantas?

-- 36 vendedores com mais de uma publicação, até 7 publicações 
-- job_run = 2026-10-12 14:28:43.000
SELECT 
	s.nickname, 
	l.seller_id,
	COUNT(*) total_listings
FROM listings l
LEFT JOIN sellers s 
	ON s.seller_id = l.seller_id
	AND s.job_run = l.job_run
WHERE l.job_run = (SELECT MAX(job_run) FROM	listings)
GROUP BY 
	s.nickname, 
	l.seller_id
HAVING COUNT(*) > 1
ORDER BY total_listings DESC; 


-- 2) Média de vendas por vendedor?

-- API não retorna a quantidade vendida
-- job_run = 2026-10-12 14:28:43.000
SELECT 
	s.nickname, 
	l.seller_id,
	COALESCE(SUM(l.total_sales),0)::NUMERIC / COUNT(*) avg_sales
FROM listings l
LEFT JOIN sellers s 
	ON s.seller_id = l.seller_id
	AND s.job_run = l.job_run
WHERE l.job_run = (SELECT MAX(job_run) FROM	listings)
GROUP BY 
	s.nickname, 
	l.seller_id
ORDER BY avg_sales DESC; 


-- 3) Qual é o preço médio em dólares?

-- Preço médio USD 984.45
-- job_run = 2026-10-12 14:28:43.000
SELECT 
	l.converted_currency currency,
	ROUND(AVG(l.price_converted),2) avg_price,
	MIN(l.price_converted) min_price,
	MAX(l.price_converted) max_price
FROM listings l
WHERE l.job_run = (SELECT MAX(job_run) FROM	listings)
	AND l.is_outlier = FALSE
GROUP BY 
	l.converted_currency;

	
-- 4) Porcentagem de artigos com garantia?

-- 79.75% tem algum tipo de garantia 
-- job_run = 2026-10-12 14:28:43.000
SELECT
	COUNT(*) FILTER (WHERE l.has_warranty) with_warranty,
	COUNT(*) FILTER (WHERE NOT l.has_warranty) no_warranty,
	ROUND(COUNT(*) FILTER (WHERE l.has_warranty)::NUMERIC / COUNT(*) * 100, 2)  warranty_coverage 
FROM listings l 
WHERE l.job_run = (SELECT MAX(job_run) FROM	listings);


-- 5) Métodos de envio oferecidos?

-- xd_drop_off (56.33%), fulfillment (13.29%), drop_off (21.52%), cross_docking (8.86%)
-- job_run = 2026-10-12 14:28:43.000
SELECT
	l.logistic_type,
	COUNT(*) listings,
	ROUND(COUNT(*)::NUMERIC / SUM(COUNT (*)) OVER () * 100, 2) percentage
FROM listings l 
WHERE l.job_run = (SELECT MAX(job_run) FROM	listings)
GROUP BY 
	l.logistic_type;
