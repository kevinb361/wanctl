# Phase 32: Backend Client Tests - Research

**Researched:** 2026-01-24
**Domain:** Python unit testing for HTTP/SSH clients with mocking
**Confidence:** HIGH

## Summary

This phase adds comprehensive unit tests for three backend client modules: `routeros_rest.py` (REST API client), `routeros_ssh.py` (SSH client), and `backends/base.py` + `backends/routeros.py` (backend abstraction layer). Current coverage is critically low (9%, 18%, 0% respectively) with a 90% threshold enforced in CI.

The standard approach uses pytest with `unittest.mock` for mocking `requests.Session` and `paramiko.SSHClient`. The project already uses this pattern extensively in `test_router_client.py`, which provides failover/transport selection tests using MagicMock. The new tests should follow the same patterns: mock external dependencies, test individual method behaviors, and verify error handling paths.

**Primary recommendation:** Use `unittest.mock.patch` with `MagicMock` for both `requests.Session` and `paramiko.SSHClient`, following existing project patterns in `test_router_client.py`.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=8.0.0 | Test framework | Already in project, standard Python testing |
| unittest.mock | stdlib | Mocking library | Built-in, no extra dependencies |
| pytest-cov | >=4.1.0 | Coverage reporting | Already in project, enforces 90% threshold |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| MagicMock | stdlib | Auto-spec mocking | For complex objects like Session, SSHClient |
| patch/patch.object | stdlib | Context manager/decorator mocking | For replacing module-level imports |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| unittest.mock | responses | responses specializes in requests mocking but adds dependency |
| unittest.mock | pytest-mock | Thinner wrapper, but project already uses unittest.mock |
| unittest.mock | requests-mock | Good for requests but not paramiko |
| Direct mocking | paramiko-mock | Specialized but adds dependency, overkill for simple tests |

**Installation:**
```bash
# No additional packages needed - all already in project
# pytest, pytest-cov, unittest.mock (stdlib)
```

## Architecture Patterns

### Recommended Test File Structure
```
tests/
├── test_routeros_rest.py      # REST client tests (NEW)
├── test_routeros_ssh.py       # SSH client tests (NEW)
├── test_backends.py           # Backend abstraction tests (NEW)
├── test_router_client.py      # Existing failover/transport tests
└── conftest.py                # Shared fixtures
```

### Pattern 1: Mock Session for REST Client
**What:** Mock `requests.Session` to test REST API client methods without network calls
**When to use:** All RouterOSREST tests
**Example:**
```python
# Source: project pattern from test_router_client.py
from unittest.mock import MagicMock, patch

class TestRouterOSREST:
    @pytest.fixture
    def mock_session(self):
        """Create mock requests Session."""
        session = MagicMock()
        response = MagicMock()
        response.ok = True
        response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
        session.get.return_value = response
        session.patch.return_value = response
        session.post.return_value = response
        return session

    @pytest.fixture
    def rest_client(self, mock_session):
        """Create REST client with mocked session."""
        with patch("wanctl.routeros_rest.requests.Session") as mock_sess_class:
            mock_sess_class.return_value = mock_session
            client = RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
            )
        client._session = mock_session  # Inject mock
        return client
```

### Pattern 2: Mock SSHClient for SSH Client
**What:** Mock `paramiko.SSHClient` to test SSH command execution
**When to use:** All RouterOSSSH tests
**Example:**
```python
# Source: standard paramiko mocking pattern
from unittest.mock import MagicMock, patch

class TestRouterOSSSH:
    @pytest.fixture
    def mock_ssh_client(self):
        """Create mock paramiko SSHClient."""
        client = MagicMock()
        transport = MagicMock()
        transport.is_active.return_value = True
        client.get_transport.return_value = transport

        # Mock exec_command return values
        stdin, stdout, stderr = MagicMock(), MagicMock(), MagicMock()
        stdout.read.return_value = b"output"
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        client.exec_command.return_value = (stdin, stdout, stderr)

        return client

    @pytest.fixture
    def ssh_client(self, mock_ssh_client):
        """Create SSH client with mocked paramiko."""
        with patch("wanctl.routeros_ssh.paramiko.SSHClient") as mock_class:
            mock_class.return_value = mock_ssh_client
            client = RouterOSSSH(
                host="192.168.1.1",
                user="admin",
                ssh_key="/path/to/key",
            )
        client._client = mock_ssh_client  # Inject mock
        return client
```

### Pattern 3: Abstract Base Class Testing
**What:** Test abstract methods via concrete implementation mocking
**When to use:** Testing RouterBackend base class
**Example:**
```python
# Source: standard ABC testing pattern
class ConcreteBackend(RouterBackend):
    """Concrete implementation for testing abstract base."""
    def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
        return True
    # ... implement all abstract methods minimally

def test_default_reset_queue_counters():
    """Test default implementation returns True."""
    backend = ConcreteBackend()
    assert backend.reset_queue_counters("queue") is True
```

### Anti-Patterns to Avoid
- **Patching at wrong scope:** Patch where used, not where defined (e.g., `wanctl.routeros_rest.requests` not `requests`)
- **Not resetting state between tests:** Use fixtures with proper cleanup
- **Testing implementation, not behavior:** Don't test that `_session.get` was called; test that `get_queue_stats` returns correct data
- **Ignoring edge cases:** Network failures, timeouts, malformed responses must be tested

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Request mocking | Custom response objects | MagicMock with `ok`, `json()`, `status_code` | Handles all response attributes |
| SSH channel mocking | Custom channel class | MagicMock with `recv_exit_status()` | Handles all channel methods |
| Timeout testing | sleep-based tests | pytest.raises with TimeoutError | More reliable, faster |
| Coverage gaps | Manual line counting | pytest-cov with fail_under=90 | Already configured in project |

**Key insight:** The `unittest.mock.MagicMock` class auto-generates attributes and methods on access, making it ideal for complex objects like `requests.Response` or `paramiko.Channel` without needing to implement every method.

## Common Pitfalls

### Pitfall 1: Patching requests.Session After Instance Creation
**What goes wrong:** Session is created in `__init__`, patch must happen before instantiation
**Why it happens:** Forgetting that `requests.Session()` is called in constructor
**How to avoid:** Patch before creating RouterOSREST, or inject mock session after creation
**Warning signs:** Tests pass but code coverage doesn't increase

### Pitfall 2: Missing Paramiko Transport Mock
**What goes wrong:** `_is_connected()` returns False because `get_transport()` returns None
**Why it happens:** Forgot to mock the transport chain
**How to avoid:** Always mock: `client.get_transport().is_active() -> True`
**Warning signs:** Tests trigger reconnection logic unexpectedly

### Pitfall 3: Not Testing Retry Logic
**What goes wrong:** Retry decorator `@retry_with_backoff` behavior untested
**Why it happens:** Mocks succeed on first call
**How to avoid:** Use `side_effect=[Exception, Exception, success]` to test retry paths
**Warning signs:** Coverage shows retry wrapper but not retry conditions

### Pitfall 4: Cache Pollution Between Tests
**What goes wrong:** ID cache (`_queue_id_cache`, `_mangle_id_cache`) persists
**Why it happens:** Same client instance reused across tests
**How to avoid:** Use fixtures that create fresh client instances per test
**Warning signs:** Tests pass individually but fail when run together

### Pitfall 5: Missing Error Path Coverage
**What goes wrong:** Only happy path tested, 90% threshold not met
**Why it happens:** Error handling branches need explicit testing
**How to avoid:** Test `response.ok = False`, `rc != 0`, `RequestException`, `SSHException`
**Warning signs:** Coverage report shows uncovered `except` blocks

## Code Examples

Verified patterns from project and official sources:

### REST API Command Execution
```python
# Source: wanctl/routeros_rest.py pattern
def test_run_cmd_success(rest_client, mock_session):
    """Test successful command execution."""
    response = MagicMock()
    response.ok = True
    response.json.return_value = [{"name": "WAN-Download", ".id": "*1"}]
    mock_session.get.return_value = response

    rc, stdout, stderr = rest_client.run_cmd('/queue tree print where name="WAN-Download"')

    assert rc == 0
    assert "WAN-Download" in stdout
    assert stderr == ""

def test_run_cmd_network_error(rest_client, mock_session):
    """Test network error handling."""
    import requests
    mock_session.get.side_effect = requests.RequestException("Connection refused")

    rc, stdout, stderr = rest_client.run_cmd("/queue tree print")

    assert rc == 1
    assert "Connection refused" in stderr
```

### SSH Command Execution
```python
# Source: wanctl/routeros_ssh.py pattern
def test_run_cmd_captures_output(ssh_client, mock_ssh_client):
    """Test command with output capture."""
    stdout = MagicMock()
    stdout.read.return_value = b"max-limit=500000000"
    stdout.channel.recv_exit_status.return_value = 0
    stderr = MagicMock()
    stderr.read.return_value = b""
    mock_ssh_client.exec_command.return_value = (MagicMock(), stdout, stderr)

    rc, out, err = ssh_client.run_cmd('/queue/tree/print detail where name="WAN-Download"', capture=True)

    assert rc == 0
    assert "max-limit=500000000" in out

def test_run_cmd_reconnects_on_lost_connection(ssh_client, mock_ssh_client):
    """Test automatic reconnection."""
    mock_ssh_client.get_transport.return_value.is_active.return_value = False

    ssh_client.run_cmd("/system identity print")

    mock_ssh_client.connect.assert_called()  # Should reconnect
```

### Backend Factory Testing
```python
# Source: wanctl/backends/__init__.py pattern
def test_get_backend_routeros(mock_config):
    """Test factory creates RouterOSBackend."""
    mock_config.router = {"type": "routeros", "host": "192.168.1.1", ...}

    with patch("wanctl.backends.routeros.RouterOSBackend.from_config") as mock_factory:
        mock_factory.return_value = MagicMock(spec=RouterBackend)
        backend = get_backend(mock_config)

    mock_factory.assert_called_once_with(mock_config)

def test_get_backend_unsupported_type(mock_config):
    """Test factory raises for unsupported type."""
    mock_config.router = {"type": "openwrt"}

    with pytest.raises(ValueError, match="Unsupported router type"):
        get_backend(mock_config)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mock individual methods | MagicMock auto-spec | Python 3.8+ | Less boilerplate |
| requests-mock library | unittest.mock.patch | Project convention | No extra dependency |
| Real SSH connections in tests | Mocked paramiko | Always for unit tests | Fast, deterministic |

**Deprecated/outdated:**
- `mock` library (external): Merged into stdlib as `unittest.mock` in Python 3.3
- `nose` testing: Superseded by pytest

## Open Questions

Things that couldn't be fully resolved:

1. **Coverage threshold per-file vs aggregate**
   - What we know: Project has 90% aggregate threshold
   - What's unclear: Whether individual files need 90% each
   - Recommendation: Aim for 90%+ per file to meet aggregate reliably

2. **Integration test scope**
   - What we know: This phase is unit tests only
   - What's unclear: Whether integration tests (real router) are needed later
   - Recommendation: Unit tests with mocks are sufficient for this phase

## Sources

### Primary (HIGH confidence)
- Project codebase: `test_router_client.py`, `test_router_command_utils.py` - existing test patterns
- Project codebase: `routeros_rest.py`, `routeros_ssh.py`, `backends/*.py` - code to test
- Python stdlib: `unittest.mock` documentation

### Secondary (MEDIUM confidence)
- [pytest monkeypatch documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) - official pytest mocking guide
- [requests-mock pytest integration](https://requests-mock.readthedocs.io/en/latest/pytest.html) - alternative approach reference
- [StackStorm paramiko test patterns](https://github.com/StackStorm/st2/blob/master/st2actions/tests/unit/test_paramiko_ssh.py) - production-grade SSH mocking example
- [paramiko official tests](https://github.com/paramiko/paramiko/blob/main/tests/test_client.py) - reference implementation

### Tertiary (LOW confidence)
- WebSearch results on pytest mocking best practices 2026

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Project already uses these tools, patterns established
- Architecture: HIGH - Follows existing `test_router_client.py` patterns exactly
- Pitfalls: HIGH - Based on actual code analysis and common mocking issues

**Research date:** 2026-01-24
**Valid until:** 60 days (testing patterns stable, project-specific)
