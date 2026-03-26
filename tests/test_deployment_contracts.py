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


def _extract_pip_install_deps(dockerfile_text: str) -> list[str]:
    """Extract package specs from the pip install --no-cache-dir block.

    Parses continuation lines (ending with backslash) after 'pip install'.
    Returns list of 'package>=version' strings.
    """
    lines = dockerfile_text.splitlines()
    in_pip_block = False
    deps: list[str] = []

    for line in lines:
        stripped = line.strip()

        if "pip install" in stripped:
            in_pip_block = True
            # The pip install line itself may have deps after flags
            # e.g., "RUN pip install --no-cache-dir \"
            # Usually just flags on this line, deps on continuation lines
            continue

        if in_pip_block:
            # Remove trailing backslash for continuation
            dep_part = stripped.rstrip("\\").strip()
            if dep_part and not dep_part.startswith("#"):
                deps.append(dep_part)
            # Stop if line doesn't end with backslash (end of block)
            if not stripped.endswith("\\"):
                in_pip_block = False

    return deps


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

    def test_all_pyproject_deps_in_dockerfile(self):
        """Every package from pyproject.toml dependencies appears in Dockerfile pip install."""
        dockerfile = _load_dockerfile()
        pip_deps = _extract_pip_install_deps(dockerfile)
        pip_pkg_names = {_parse_dependency(d)[0].lower() for d in pip_deps}

        pyproject_pkg_names = {name.lower() for name, _, _ in _RUNTIME_DEPS}

        missing = pyproject_pkg_names - pip_pkg_names
        assert not missing, (
            f"Dependencies in pyproject.toml but missing from Dockerfile pip install: {missing}"
        )

    def test_version_specs_match(self):
        """Version specs in Dockerfile match pyproject.toml exactly."""
        dockerfile = _load_dockerfile()
        pip_deps = _extract_pip_install_deps(dockerfile)
        pip_specs = {
            _parse_dependency(d)[0].lower(): f"{_parse_dependency(d)[1]}{_parse_dependency(d)[2]}"
            for d in pip_deps
        }

        for pkg_name, op, version in _RUNTIME_DEPS:
            expected_spec = f"{op}{version}"
            actual_spec = pip_specs.get(pkg_name.lower())
            assert actual_spec is not None, (
                f"Package {pkg_name!r} not found in Dockerfile pip install"
            )
            assert actual_spec == expected_spec, (
                f"Version spec mismatch for {pkg_name}: "
                f"pyproject.toml has {expected_spec!r}, Dockerfile has {actual_spec!r}"
            )

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
