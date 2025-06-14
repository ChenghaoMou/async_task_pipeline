package_name := "async-task-pipeline"
python := "python"
uv := "uv"
uvx := "uvx"

install:
    {{ uv }} sync

install-dev:
    {{ uv }} sync --all-extras --dev

clean:
    find . -type f -name "*.pyc" -delete
    find . -type d -name "*cache*" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    rm -rf build/ dist/ sites/ .coverage htmlcov/

format:
    {{ uvx }} ruff format .

lint:
    {{ uvx }} ruff check .

fix-lint:
    {{ uvx }} ruff check --fix .

type-check:
    {{ uv }} run mypy --show-traceback src/

test:
    {{ uv }} run pytest -v

test-cov:
    {{ uv }} run pytest --cov=src --cov-report=html --cov-report=term-missing --cov-report xml:coverage.xml

pre-commit-install:
    {{ uvx }} pre-commit install

pre-commit:
    {{ uvx }} pre-commit run --all-files

check: format fix-lint type-check test

doc:
    {{ uv }} run mkdocs build --clean

build:
    rm -rf dist/
    {{ uv }} build

publish-test: build
    {{ uv }} publish --index testpypi

publish: build
    {{ uv }} publish --username __token__ --keyring-provider subprocess --publish-url 'https://upload.pypi.org/legacy/?async_task_pipeline'

dev-setup: install-dev pre-commit-install
    @echo "Development environment setup complete!"
    @echo "Run 'just check' to run all quality checks"

version:
    {{ uvx }} bump-my-version show-bump --config-file pyproject.toml

version-patch:
    {{ uvx }} bump-my-version bump patch

version-minor:
    {{ uvx }} bump-my-version bump minor

version-major:
    {{ uvx }} bump-my-version bump major


tox:
    {{ uvx }} tox

tox-lint:
    {{ uvx }} tox -e lint

tox-type-check:
    {{ uvx }} tox -e type-check

tox-cov:
    {{ uvx }} tox -e cov

tox-clean:
    {{ uvx }} tox -e clean
    rm -rf .tox/

check-all: format lint type-check test tox
