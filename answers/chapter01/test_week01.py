"""week01 习题测试（≥5 例，全部 hermetic）。"""

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "week01_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

extract_dependency_names = _mod.extract_dependency_names  # type: ignore[attr-defined]
is_python_version_compatible = _mod.is_python_version_compatible  # type: ignore[attr-defined]
normalize_version_constraint = _mod.normalize_version_constraint  # type: ignore[attr-defined]
parse_requires_python = _mod.parse_requires_python  # type: ignore[attr-defined]
parse_scripts = _mod.parse_scripts  # type: ignore[attr-defined]
required_fields_present = _mod.required_fields_present  # type: ignore[attr-defined]


def test_parse_requires_python_present():
    text = '[project]\nname="demo"\nrequires-python=">=3.12"\n'
    assert parse_requires_python(text) == ">=3.12"


def test_parse_requires_python_missing():
    text = '[project]\nname="demo"\n'
    assert parse_requires_python(text) == ""


def test_parse_requires_python_invalid_toml():
    assert parse_requires_python("not toml [[") == ""


def test_required_fields_all_present():
    text = """
[project]
name="demo"
version="0.1.0"
requires-python=">=3.12"
dependencies=["fastapi>=0.1"]
"""
    assert required_fields_present(text) == []


def test_required_fields_missing_some():
    text = '[project]\nname="demo"\n'
    missing = required_fields_present(text)
    assert "version" in missing
    assert "requires-python" in missing
    assert "dependencies" in missing
    assert "name" not in missing


def test_required_fields_invalid_toml():
    missing = required_fields_present("[[bad")
    assert set(missing) == {"name", "version", "requires-python", "dependencies"}


def test_normalize_version_constraint_valid():
    assert normalize_version_constraint(">=3.12") is True
    assert normalize_version_constraint("==1.0.0") is True
    assert normalize_version_constraint("~=2.3") is True
    assert normalize_version_constraint("*") is True
    assert normalize_version_constraint("!=1.0") is True


def test_normalize_version_constraint_invalid():
    assert normalize_version_constraint("") is False
    assert normalize_version_constraint("hello") is False
    assert normalize_version_constraint(">>=1.0") is False
    assert normalize_version_constraint("3.12") is False  # bare version without operator


def test_parse_scripts_present():
    text = '[project.scripts]\nmeetingtotext="cli:main"\n'
    assert parse_scripts(text) == {"meetingtotext": "cli:main"}


def test_parse_scripts_missing():
    text = '[project]\nname="demo"\n'
    assert parse_scripts(text) == {}


def test_extract_dependency_names_order():
    text = """
[project]
name="demo"
dependencies=["fastapi>=0.115.0", "uvicorn[standard]>=0.34.0", "openai>=1.60.0"]
"""
    assert extract_dependency_names(text) == ["fastapi", "uvicorn", "openai"]


def test_extract_dependency_names_empty():
    text = '[project]\nname="demo"\ndependencies=[]\n'
    assert extract_dependency_names(text) == []


def test_is_python_version_compatible_basic():
    assert is_python_version_compatible(">=3.12", "3.12.0") is True
    assert is_python_version_compatible(">=3.12", "3.11.9") is False
    assert is_python_version_compatible("==3.12", "3.12.0") is True
    assert is_python_version_compatible("*", "2.7.0") is True
    assert is_python_version_compatible("~=3.12", "3.12.5") is True
    assert is_python_version_compatible("~=3.12", "3.13.0") is True
    assert is_python_version_compatible("~=3.12", "4.0.0") is False
