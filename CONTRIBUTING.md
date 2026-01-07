# Contributing to wanctl

Thanks for your interest in contributing to wanctl!

## Project Philosophy

This is a **power-user tool maintained by a sysadmin**, not enterprise software. It was built for personal use and shared with the community. Contributions are welcome, but please understand the context.

## How to Contribute

### Reporting Issues

1. **Search first** - Check if the issue already exists
2. **Provide details** - Include your setup (router model, RouterOS version, connection type)
3. **Include logs** - Attach relevant log output (sanitize sensitive info)
4. **Be specific** - "It doesn't work" isn't helpful; describe expected vs actual behavior

### Pull Requests

PRs are selectively accepted. Before submitting:

1. **Open an issue first** - Discuss the change before implementing
2. **Keep it focused** - One feature/fix per PR
3. **Test thoroughly** - This controls production network equipment
4. **Follow existing style** - Match the codebase conventions

### What Gets Accepted

- Bug fixes with clear reproduction steps
- Documentation improvements
- New router backend implementations (OpenWrt, pfSense, etc.)
- Performance improvements with benchmarks
- Security fixes

### What Probably Won't Get Accepted

- Major architectural changes without prior discussion
- Features that add significant complexity
- Changes that break backward compatibility
- "Improvements" to working code without clear benefit

## Development Setup

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed setup instructions.

Quick start:

```bash
# Clone the repo
git clone https://github.com/kevinb361/wanctl.git
cd wanctl

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pyflakes  # dev dependencies

# Run tests
pytest tests/ -v

# Run linting
pyflakes src/ tests/
```

## Code Style

- Python 3.10+ with type hints
- Follow existing patterns in the codebase
- Keep functions focused and well-documented
- No unnecessary dependencies

## Testing

Before submitting:

1. Test on actual hardware if possible
2. Verify with RouterOS (primary target)
3. Check that existing functionality isn't broken
4. Include test cases for new features

## Adding a New Router Backend

To add support for a new router platform:

1. Create `src/cake/backends/<platform>.py`
2. Implement the `RouterBackend` interface from `base.py`
3. Add to `__init__.py` factory function
4. Document the config schema
5. Test thoroughly before submitting

See `src/cake/backends/routeros.py` as a reference implementation.

## License

By contributing, you agree that your contributions will be licensed under GPL-2.0.

## Questions?

Open an issue for questions about contributing.
