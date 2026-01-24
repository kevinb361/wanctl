.PHONY: test coverage lint type format ci clean security security-deps security-code security-secrets security-licenses

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

# Run all security scans
security: security-deps security-code security-secrets security-licenses
	@echo "All security checks passed"

# Dependency vulnerability scan (pip-audit)
security-deps:
	@echo "Scanning dependencies for vulnerabilities..."
	.venv/bin/pip-audit

# Static security analysis (bandit)
security-code:
	@echo "Running static security analysis..."
	.venv/bin/bandit -r src/ -c pyproject.toml

# Secret detection (detect-secrets)
security-secrets:
	@echo "Checking for secrets..."
	.venv/bin/detect-secrets scan --baseline .secrets.baseline

# License compliance (pip-licenses)
security-licenses:
	@echo "Checking license compliance..."
	.venv/bin/pip-licenses --fail-on="GPL;AGPL;LGPL" --partial-match
