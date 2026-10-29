.PHONY: install lint format test skills-test web web-build refresh ci

install:            ## Python package with dev tools, and the site's packages
	pip install -e ".[dev]"
	cd web && npm ci

lint:               ## ruff
	ruff check .

format:             ## ruff fix + format
	ruff check --fix . && ruff format indtrader tests

test:               ## offline test suite
	python3 -m pytest -q

skills-test:        ## project skills' offline tests
	cd .claude/skills && python3 -m unittest discover -s tests

web:                ## site in dev mode
	cd web && npm run dev

web-build:          ## production build of the site
	cd web && npm run build

refresh:            ## export both desks to public/ and web/data/
	scripts/refresh_dashboard.sh

ci: lint test skills-test web-build
