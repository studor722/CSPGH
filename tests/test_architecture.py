"""Architectural dependency-direction tests enforced by AST inspection."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append((node.lineno, module))
    return imports


def _is_forbidden(module_name: str, forbidden: tuple[str, ...]) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in forbidden
    )


def _assert_no_forbidden_imports(
    paths: list[Path], forbidden: tuple[str, ...], layer: str
) -> None:
    violations: list[str] = []
    for path in paths:
        rel = path.relative_to(ROOT)
        for lineno, mod in _imported_modules(path):
            if _is_forbidden(mod, forbidden):
                violations.append(f"{rel}:{lineno} imports forbidden module {mod!r}")
    assert not violations, f"{layer} layer dependency rule broken:\n" + "\n".join(
        violations
    )


def test_domain_layer_stays_pure():
    _assert_no_forbidden_imports(
        [ROOT / "app" / "domain.py"],
        (
            "fastapi",
            "sqlalchemy",
            "app.database",
            "app.repositories",
            "app.services",
            "app.controllers",
            "app.dependencies",
        ),
        "domain",
    )


def test_repository_layer_does_not_depend_on_services_or_web():
    repo_files = sorted((ROOT / "app" / "repositories").rglob("*.py"))
    _assert_no_forbidden_imports(
        repo_files,
        ("fastapi", "app.services", "app.controllers", "app.dependencies"),
        "repository",
    )


def test_service_layer_does_not_depend_on_fastapi_or_controllers():
    service_files = sorted((ROOT / "app" / "services").rglob("*.py"))
    _assert_no_forbidden_imports(
        service_files,
        ("fastapi", "app.controllers", "app.dependencies"),
        "service",
    )


def test_etl_layer_does_not_depend_on_web_or_service_layers():
    etl_files = sorted((ROOT / "etl").rglob("*.py"))
    _assert_no_forbidden_imports(
        etl_files,
        (
            "fastapi",
            "app.services",
            "app.repositories",
            "app.controllers",
            "app.dependencies",
        ),
        "etl",
    )


def test_presentation_layer_does_not_bypass_services():
    controller_files = sorted((ROOT / "app" / "controllers").rglob("*.py"))
    _assert_no_forbidden_imports(
        controller_files,
        (
            "sqlalchemy",
            "app.database",
            "app.repositories",
            "etl.import_who",
            "etl.import_worldbank",
            "etl.import_owid",
            "etl.extract_who",
            "etl.extract_worldbank",
            "etl.extract_owid",
            "etl.load",
            "etl.realtime_pipeline",
        ),
        "presentation",
    )

