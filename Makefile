.PHONY: help install install-dev clean lint format test type-check pre-commit build publish publish-test clean-build tox tox-lint tox-type-check tox-cov tox-clean check-all
.DEFAULT_GOAL := help

# Variables
PACKAGE_NAME := async-task-pipeline
PYTHON := python
UV := uv
UVX := uvx

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	$(UV) sync

install-dev: ## Install development dependencies
	$(UV) sync --all-extras --dev

clean: ## Clean up cache files and build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/

format: ## Format code with ruff
	$(UVX) ruff format .
	$(UVX) ruff check --fix .

lint: ## Lint code with ruff
	$(UVX) ruff check .

type-check: ## Run type checking with mypy
	$(UVX) --with pydantic mypy src/

test: ## Run tests with pytest
	$(UV) run pytest -v

test-cov: ## Run tests with coverage
	$(UV) run pytest --cov=async_task_pipeline --cov-report=html --cov-report=term-missing

pre-commit-install: ## Install pre-commit hooks
	$(UVX) pre-commit install

pre-commit: ## Run pre-commit checks on all files
	$(UVX) pre-commit run --all-files

check: format lint type-check test ## Run all checks (format, lint, type-check, test)

clean-build: clean ## Clean and prepare for build
	rm -rf dist/

build: clean-build ## Build the package
	$(UV) build

publish-test: build ## Publish to TestPyPI
	$(UV) publish --index testpypi

publish: build ## Publish to PyPI
	$(UV) publish --username __token__ --keyring-provider subprocess --publish-url 'https://upload.pypi.org/legacy/?async_task_pipeline'

dev-setup: install-dev pre-commit-install ## Set up development environment
	@echo "Development environment setup complete!"
	@echo "Run 'make check' to run all quality checks"

version-patch: ## Bump patch version
	$(UV) run bump-my-version bump patch

version-minor: ## Bump minor version
	$(UV) run bump-my-version bump minor

version-major: ## Bump major version
	$(UV) run bump-my-version bump major

watch-test: ## Run tests in watch mode
	$(UV) run ptw

tox: ## Run tests across all Python versions with tox
	$(UVX) tox

tox-lint: ## Run linting with tox
	$(UVX) tox -e lint

tox-type-check: ## Run type checking with tox
	$(UVX) tox -e type-check

tox-cov: ## Run coverage tests with tox
	$(UVX) tox -e cov

tox-clean: ## Clean tox environments
	$(UVX) tox -e clean
	rm -rf .tox/

check-all: format lint type-check test tox ## Run all checks including tox multi-version testing
