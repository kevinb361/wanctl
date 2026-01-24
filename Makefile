.PHONY: test coverage lint type format ci clean

# Run tests without coverage
test:
	.venv/bin/pytest tests/ -v

# Run tests with coverage + HTML report
coverage:
	.venv/bin/pytest tests/ --cov=src --cov=tests --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "HTML report: coverage-report/index.html"

# Linting
lint:
	.venv/bin/ruff check src/ tests/

# Type checking
type:
	.venv/bin/mypy src/wanctl/

# Format code
format:
	.venv/bin/ruff format src/ tests/

# All CI checks (lint, type, test)
ci: lint type test

# Clean build artifacts
clean:
	rm -rf .coverage coverage-report/ *.egg-info/ dist/ build/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
