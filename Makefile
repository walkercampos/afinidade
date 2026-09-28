# Comandos do dia a dia. Rode `make` para ver a lista.
.DEFAULT_GOAL := ajuda
TEST_DATABASE_URL ?= postgresql://matchmaking:matchmaking@localhost:5432/matchmaking_test

ajuda: ## Lista os comandos
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

instalar: ## Instala dependências de desenvolvimento e os hooks de pre-commit
	pip install -r requirements-dev.txt pre-commit
	pre-commit install

db: ## Sobe só o PostgreSQL local (Docker) para desenvolvimento e testes
	docker compose up -d db

rodar: ## Roda a API com recarga automática (requer .env)
	set -a && . ./.env && set +a && uvicorn app.main:app --reload

lint: ## Verifica estilo, imports e problemas comuns de segurança
	ruff check .
	ruff format --check .

formatar: ## Corrige automaticamente o que o lint consegue
	ruff check --fix .
	ruff format .

testar: ## Roda todos os testes (o banco de teste é APAGADO)
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) pytest -q --cov

testar-js: ## Testes unitários do front-end (precisa só do Node)
	npm test

e2e: ## Testes no navegador (precisa da API rodando com EMAIL_PROVEDOR=arquivo: make rodar)
	npm ci && npx playwright install chromium
	E2E_URL=http://localhost:8000 E2E_EMAILS=emails-dev npm run e2e

auditar: ## Procura vulnerabilidades conhecidas nas dependências
	pip-audit -r requirements.txt

verificar: lint testar testar-js auditar ## Tudo o que o CI roda

migracao: ## Cria o arquivo da próxima migração: make migracao nome=descricao_curta
	@test -n "$(nome)" || (echo "use: make migracao nome=descricao_curta" && exit 1)
	@n=$$(ls db/migrations | tail -1 | cut -c1-4); prox=$$(printf "%04d" $$(expr $$n + 1)); \
	arq=db/migrations/$${prox}_$(nome).sql; echo "-- $${prox}: $(nome)" > $$arq; echo "criado $$arq"

moderador: ## Dá o papel de moderador(a): make moderador apelido=fulano
	python -m app.admin moderador $(apelido)

.PHONY: ajuda instalar db rodar lint formatar testar testar-js e2e auditar verificar migracao moderador
