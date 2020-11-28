.DEFAULT_GOAL := all

poetry_dev_bootstrap_file = .poetry_dev_up_to_date
poetry_prod_bootstrap_file = .poetry_prod_up_to_date


.PHONY: all
all: install-dev

# Build everything needed for deployment in production
.PHONY: build
build: install-prod

.PHONY: install-dev
install-dev: $(poetry_dev_bootstrap_file)
$(poetry_dev_bootstrap_file): poetry.lock
	touch $(poetry_dev_bootstrap_file).notyet
	poetry install --no-root
	poetry install --extras=code_coverage
	mv $(poetry_dev_bootstrap_file).notyet $(poetry_dev_bootstrap_file)
	@# Remove the prod bootstrap file, since we now have dev deps present.
	rm -f $(poetry_prod_bootstrap_file)

# Note this will actually *remove* any dev dependencies, if present
.PHONY: install-prod
install-prod: $(poetry_prod_bootstrap_file)
$(poetry_prod_bootstrap_file): poetry.lock
	touch $(poetry_prod_bootstrap_file).notyet
	poetry install --no-root --no-dev
	mv $(poetry_prod_bootstrap_file).notyet $(poetry_prod_bootstrap_file)
	@# Remove the dev bootstrap file, since the `--no-dev` removed any present dev deps
	rm -f $(poetry_dev_bootstrap_file)

# Run automatic code formatters/linters that don't require human input
# (might fix a broken `make check`)
.PHONY: fix
fix: install-dev
	poetry run black member
	poetry run isort --recursive member

.PHONY: check
check: lint test

.PHONY: lint
lint: install-dev
	poetry run black --fast --check member
	poetry run isort --recursive --check member
	poetry run pylint member

.PHONY: test
test: install-dev
	poetry run coverage run -m pytest

# Production webservers won't run this way, so install dev dependencies
.PHONY: run
run: install-dev
	FLASK_APP=autoapp.py poetry run flask run

.PHONY: clean
clean:
	rm -f $(poetry_dev_bootstrap_file)
	rm -f $(poetry_prod_bootstrap_file)
	find . -name '*.pyc' -delete
