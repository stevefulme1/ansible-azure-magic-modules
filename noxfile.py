"""Nox sessions for Azure Magic Modules CI."""

import os
import shutil
import subprocess
from pathlib import Path

import nox

nox.options.sessions = ["generate", "lint", "sanity"]
nox.options.reuse_existing_virtualenvs = True

PROJECT_ROOT = Path(__file__).resolve().parent
DEFINITIONS_DIR = str(PROJECT_ROOT / "definitions")
OUTPUT_DIR = str(PROJECT_ROOT / "output")
TEMPLATES_DIR = str(PROJECT_ROOT / "generator" / "templates")

# Collection namespace/name used to scaffold ansible-test structure
COLLECTION_NAMESPACE = "azure"
COLLECTION_NAME = "azcollection"


@nox.session(python="3.12")
def generate(session: nox.Session) -> None:
    """Regenerate modules from definitions and verify they compile."""
    session.install("jinja2>=3.1", "pyyaml>=6.0")

    # Clean previous output
    out = Path(OUTPUT_DIR)
    if out.exists():
        shutil.rmtree(out)

    session.run(
        "python", "-m", "generator",
        "-d", DEFINITIONS_DIR,
        "-o", OUTPUT_DIR,
        "-t", TEMPLATES_DIR,
        env={"PYTHONPATH": str(PROJECT_ROOT)},
    )

    # Syntax check all generated files
    py_files = sorted(out.glob("*.py"))
    for py_file in py_files:
        session.run("python", "-c", f"import py_compile; py_compile.compile('{py_file}', doraise=True)")

    session.log(f"Generated and verified {len(py_files)} modules")


@nox.session(python="3.12")
def lint(session: nox.Session) -> None:
    """Run ansible-lint and pycodestyle on generated modules."""
    session.install("ansible-core>=2.16", "ansible-lint>=24.2", "pycodestyle>=2.11")

    out = Path(OUTPUT_DIR)
    if not out.exists() or not list(out.glob("*.py")):
        session.error("No generated modules found — run 'nox -s generate' first")

    # pycodestyle (E402 is expected for Ansible modules)
    session.run(
        "pycodestyle",
        "--max-line-length=120",
        "--ignore=E402,E501",
        *[str(f) for f in sorted(out.glob("*.py"))],
    )

    # ansible-lint on generated modules
    session.run(
        "ansible-lint",
        "--profile", "production",
        "--exclude", "generator/",
        "--exclude", "definitions/",
        *[str(f) for f in sorted(out.glob("*.py"))],
        success_codes=[0, 2],  # 2 = warnings only
    )


@nox.session(python="3.12")
def sanity(session: nox.Session) -> None:
    """Run ansible-test sanity checks on generated modules.

    ansible-test requires a specific directory layout under
    ansible_collections/<namespace>/<name>/, so this session
    scaffolds a temporary collection tree, copies generated modules
    into it, and runs the sanity suite.
    """
    session.install("ansible-core>=2.16")

    out = Path(OUTPUT_DIR)
    if not out.exists() or not list(out.glob("*.py")):
        session.error("No generated modules found — run 'nox -s generate' first")

    # Build the collection tree in a temp directory
    base = Path(session.create_tmp()) / "ansible_collections" / COLLECTION_NAMESPACE / COLLECTION_NAME
    plugins_dir = base / "plugins" / "modules"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # Minimal galaxy.yml
    galaxy = base / "galaxy.yml"
    galaxy.write_text(
        f"---\nnamespace: {COLLECTION_NAMESPACE}\nname: {COLLECTION_NAME}\n"
        f"version: 0.1.0\nreadme: README.md\nauthors:\n  - Generated\n"
        f"description: Temporary collection for sanity testing\n",
        encoding="utf-8",
    )

    # Minimal meta/runtime.yml
    meta_dir = base / "meta"
    meta_dir.mkdir(exist_ok=True)
    (meta_dir / "runtime.yml").write_text(
        "---\nrequires_ansible: '>=2.16.0'\n",
        encoding="utf-8",
    )

    # __init__.py files
    (base / "plugins" / "__init__.py").touch()
    (plugins_dir / "__init__.py").touch()

    # module_utils stub so imports resolve
    mu_dir = base / "plugins" / "module_utils"
    mu_dir.mkdir(exist_ok=True)
    (mu_dir / "__init__.py").touch()
    (mu_dir / "azure_rm_common.py").write_text(
        "class AzureRMModuleBase:\n    pass\n",
        encoding="utf-8",
    )

    # Copy generated modules
    for py_file in sorted(out.glob("*.py")):
        shutil.copy2(py_file, plugins_dir / py_file.name)

    # ansible-test requires a git repo to discover targets
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "ci", "GIT_AUTHOR_EMAIL": "ci@ci",
        "GIT_COMMITTER_NAME": "ci", "GIT_COMMITTER_EMAIL": "ci@ci",
    }
    subprocess.run(["git", "init"], cwd=str(base), capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=str(base), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(base), capture_output=True, check=True, env=git_env,
    )

    # Run ansible-test sanity from the collection root
    session.chdir(str(base))
    session.run(
        "ansible-test", "sanity",
        "--python", "3.12",
        "--skip-test", "import",           # azure deps not installed
        "--skip-test", "pylint",           # stubs won't satisfy pylint
        "--skip-test", "validate-modules", # doc_fragments require real azure collection
        "--skip-test", "ansible-doc",      # doc_fragments require real azure collection
        env={"ANSIBLE_COLLECTIONS_PATH": str(base.parent.parent.parent)},
    )


@nox.session(python="3.12")
def validate(session: nox.Session) -> None:
    """Validate all YAML definitions without generating."""
    session.install("jinja2>=3.1", "pyyaml>=6.0")
    session.run(
        "python", "-m", "generator",
        "-d", DEFINITIONS_DIR,
        "--validate",
        env={"PYTHONPATH": str(PROJECT_ROOT)},
    )


@nox.session(python="3.12")
def ci(session: nox.Session) -> None:
    """Run the full CI pipeline: generate → lint → sanity."""
    session.notify("generate")
    session.notify("lint")
    session.notify("sanity")
