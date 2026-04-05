.PHONY: test coverage lint type format ci dead-code check-deps clean security security-deps security-code security-secrets security-licenses

# Run tests without coverage
test:
	.venv/bin/pytest tests/ -v

# Run tests with coverage + HTML report
coverage:
	.venv/bin/pytest tests/ --cov=src --cov=tests --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "HTML report: coverage-report/index.html"

# Run tests with coverage enforcement (used by CI)
coverage-check:
	.venv/bin/pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90

# Linting
lint:
	.venv/bin/ruff check src/ tests/

# Type checking
type:
	.venv/bin/mypy src/wanctl/

# Format code
format:
	.venv/bin/ruff format src/ tests/

# All CI checks (lint, type, coverage, dead-code, check-deps)
ci: lint type coverage-check dead-code check-deps

# Dead code detection (vulture + ruff F401)
dead-code:
	.venv/bin/vulture src/wanctl/ vulture_whitelist.py
	.venv/bin/ruff check src/ tests/ --select F401

# Dependency audit (unused pip packages in [dependencies] and [optional-dependencies])
# Pip name -> import name mapping (update when adding/removing deps):
#   requests -> requests | pyyaml -> yaml | paramiko -> paramiko
#   tabulate -> tabulate | icmplib -> icmplib
#   textual -> textual | httpx -> httpx | pyroute2 -> pyroute2
check-deps:
	@echo "Checking for unused pip dependencies..."
	@UNUSED=""; \
	for pair in "requests:requests" "pyyaml:yaml" "paramiko:paramiko" \
	            "tabulate:tabulate" "icmplib:icmplib" \
	            "textual:textual" "httpx:httpx" "pyroute2:pyroute2"; do \
	    pkg=$${pair%%:*}; imp=$${pair##*:}; \
	    if ! grep -rq "import $${imp}\b\|from $${imp}" src/wanctl/; then \
	        UNUSED="$${UNUSED} $${pkg}"; \
	    fi; \
	done; \
	if [ -n "$${UNUSED}" ]; then \
	    echo "FAIL: Unused dependencies:$${UNUSED}"; exit 1; \
	else \
	    echo "All runtime dependencies are imported"; \
	fi

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
# Note: LGPL allowed (paramiko) - weak copyleft permits library use without affecting wanctl's license
security-licenses:
	@echo "Checking license compliance..."
	.venv/bin/pip-licenses --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0"
