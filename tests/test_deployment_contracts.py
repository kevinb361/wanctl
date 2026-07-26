"""Contract tests for Dockerfile and runtime dependency validation.

These tests ensure deployment artifacts stay in sync with pyproject.toml,
which is the single source of truth for dependencies and version.

Contract violations caught:
- Dependency added to pyproject.toml but missing from Dockerfile pip install
- Version spec drift between pyproject.toml and Dockerfile
- Dockerfile LABEL version out of sync with pyproject.toml
- Dockerfile COPY paths that don't resolve to real files
- Runtime dependency not importable or below minimum version
"""

import importlib
import importlib.metadata
import re
import tomllib
from pathlib import Path

import pytest
from packaging.version import Version

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent

# Map pyproject package names to Python import names where they differ
_IMPORT_NAME_MAP: dict[str, str] = {
    "pyyaml": "yaml",
}


def _load_pyproject() -> dict:
    """Parse pyproject.toml from project root."""
    pyproject_path = _PROJECT_ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


def _parse_dependency(dep_str: str) -> tuple[str, str, str]:
    """Parse 'requests>=2.31.0' into (package_name, operator, version)."""
    match = re.match(r"^([a-zA-Z0-9_-]+)([><=!]+)(.+)$", dep_str.strip())
    if not match:
        raise ValueError(f"Cannot parse dependency string: {dep_str!r}")
    return match.group(1), match.group(2), match.group(3)


def _load_dockerfile() -> str:
    """Read docker/Dockerfile from project root."""
    dockerfile_path = _PROJECT_ROOT / "docker" / "Dockerfile"
    return dockerfile_path.read_text()


# ---------------------------------------------------------------------------
# Module-level data for parametrized tests
# ---------------------------------------------------------------------------

_PYPROJECT = _load_pyproject()
_RUNTIME_DEPS = [_parse_dependency(d) for d in _PYPROJECT["project"]["dependencies"]]


# ---------------------------------------------------------------------------
# Dockerfile contract tests
# ---------------------------------------------------------------------------


class TestDockerfileDependencyContract:
    """Validate Dockerfile stays in sync with pyproject.toml."""

    def test_docker_uses_frozen_project_runtime(self):
        """Docker installs the package from pyproject.toml + uv.lock, not a duplicate list."""
        dockerfile = _load_dockerfile()

        assert "COPY pyproject.toml uv.lock /opt/wanctl/" in dockerfile
        assert "COPY scripts/install-python-runtime.sh" in dockerfile
        assert "install-python-runtime.sh /opt/wanctl" in dockerfile
        assert "uv==0.11.29" in dockerfile
        for pkg_name, _, _ in _RUNTIME_DEPS:
            assert not re.search(rf"^\s+{re.escape(pkg_name)}[><=]", dockerfile, re.MULTILINE)

    def test_label_version_matches_pyproject(self):
        """Dockerfile LABEL version matches pyproject.toml [project].version."""
        dockerfile = _load_dockerfile()
        pyproject_version = _PYPROJECT["project"]["version"]

        match = re.search(r'LABEL\s+version="([^"]+)"', dockerfile)
        assert match, "No LABEL version= found in Dockerfile"

        dockerfile_version = match.group(1)
        assert dockerfile_version == pyproject_version, (
            f"Version mismatch: Dockerfile LABEL={dockerfile_version!r}, "
            f"pyproject.toml={pyproject_version!r}"
        )

    def test_copy_paths_resolve_to_files(self):
        """Each Dockerfile COPY source glob resolves to at least one real file."""
        dockerfile = _load_dockerfile()
        copy_lines = re.findall(r"^COPY\s+(\S+)", dockerfile, re.MULTILINE)

        # Filter to source code paths (skip docker/entrypoint.sh etc.)
        source_globs = [p for p in copy_lines if p.startswith("src/")]

        assert source_globs, "No src/ COPY paths found in Dockerfile"

        for glob_pattern in source_globs:
            matches = list(_PROJECT_ROOT.glob(glob_pattern))
            assert matches, f"Dockerfile COPY source {glob_pattern!r} resolves to zero files"

    def test_no_storage_copy_in_dockerfile(self):
        """Storage module exists locally but is NOT deployed via Dockerfile COPY.

        The storage/ subdirectory is not needed in production containers.
        If a COPY for storage/ is added to Dockerfile, this test catches it
        so the decision is deliberate.
        """
        dockerfile = _load_dockerfile()
        copy_lines = re.findall(r"^COPY\s+(\S+)", dockerfile, re.MULTILINE)
        storage_copies = [p for p in copy_lines if "storage" in p.lower()]

        # Verify storage module does exist (so this test stays meaningful)
        storage_dir = _PROJECT_ROOT / "src" / "wanctl" / "storage"
        assert storage_dir.is_dir(), "Storage module no longer exists -- this test can be removed"

        assert not storage_copies, (
            f"Dockerfile copies storage module (not deployed): {storage_copies}"
        )


# ---------------------------------------------------------------------------
# Runtime dependency version tests
# ---------------------------------------------------------------------------


class TestRuntimeDependencyVersions:
    """Verify all runtime dependencies are importable and meet version specs."""

    @pytest.mark.parametrize(
        "pkg_name,op,min_version",
        _RUNTIME_DEPS,
        ids=[d[0] for d in _RUNTIME_DEPS],
    )
    def test_dependency_importable(self, pkg_name, op, min_version):
        """Each runtime dependency from pyproject.toml is importable."""
        import_name = _IMPORT_NAME_MAP.get(pkg_name.lower(), pkg_name.lower())
        try:
            importlib.import_module(import_name)
        except ImportError:
            pytest.fail(
                f"Runtime dependency {pkg_name!r} (import as {import_name!r}) is not importable"
            )

    @pytest.mark.parametrize(
        "pkg_name,op,min_version",
        _RUNTIME_DEPS,
        ids=[d[0] for d in _RUNTIME_DEPS],
    )
    def test_dependency_meets_version_spec(self, pkg_name, op, min_version):
        """Each runtime dependency meets the minimum version from pyproject.toml."""
        installed_version_str = importlib.metadata.version(pkg_name)
        installed = Version(installed_version_str)
        minimum = Version(min_version)

        assert installed >= minimum, (
            f"{pkg_name} installed version {installed_version_str} "
            f"does not meet requirement {op}{min_version}"
        )
