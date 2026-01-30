"""CI artifact parser for analyzing test, lint, type, security, and dependency results."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from src.common.models import (
    TestFailure,
    LintError,
    SecurityIssue,
)

logger = logging.getLogger(__name__)


def parse_ci_artifacts(artifact_dir: str) -> Dict[str, Any]:
    """Parse CI artifacts from JSON reports.

    Parses JSON reports from various CI tools:
    - pytest: test results
    - ruff: linting results
    - mypy: type checking results
    - bandit: security scan results
    - pip-audit: dependency vulnerability results

    Args:
        artifact_dir: Directory containing CI artifact JSON files

    Returns:
        Dictionary with parsed results for each tool:
        {
            "pytest": {"status": "success|failure", "passed": int, "failed": int, ...},
            "ruff": {"status": "success|failure", "error_count": int, "errors": [...]},
            "mypy": {"status": "success|failure", "error_count": int, "errors": [...]},
            "bandit": {"status": "success|failure", "issues": [...]},
            "pip_audit": {"status": "success|failure", "vulnerabilities": [...]},
            "coverage": {"status": "success|failure", "total_percent": float}
        }
    """
    artifact_path = Path(artifact_dir)

    if not artifact_path.exists():
        logger.warning(f"Artifact directory does not exist: {artifact_dir}")
        return _empty_ci_results()

    results = {
        "pytest": _parse_pytest(artifact_path),
        "ruff": _parse_ruff(artifact_path),
        "mypy": _parse_mypy(artifact_path),
        "bandit": _parse_bandit(artifact_path),
        "pip_audit": _parse_pip_audit(artifact_path),
        "coverage": _parse_coverage(artifact_path),
    }

    logger.info(f"Parsed CI artifacts from {artifact_dir}")
    return results


def categorize_failures(ci_results: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize CI failures into test, lint, type, security, and dependency categories.

    Args:
        ci_results: Dictionary returned from parse_ci_artifacts

    Returns:
        Dictionary with categorized failures:
        {
            "tests": [{"test_name": str, "file": str, "line": int|None, "message": str}],
            "lint": [{"file": str, "line": int, "column": int, "code": str, "message": str}],
            "types": [{"file": str, "line": int, "column": int, "message": str}],
            "security": [{"file": str, "line": int, "severity": str, "message": str}],
            "dependencies": [{"package": str, "vulnerability": str, "severity": str}]
        }
    """
    categorized = {
        "tests": [],
        "lint": [],
        "types": [],
        "security": [],
        "dependencies": [],
    }

    # Categorize test failures
    pytest_results = ci_results.get("pytest", {})
    if pytest_results.get("status") == "failure":
        for failure in pytest_results.get("failures", []):
            categorized["tests"].append({
                "test_name": failure.get("test_name", "unknown"),
                "file": failure.get("file", "unknown"),
                "line": failure.get("line"),
                "message": failure.get("message", "Test failed"),
            })

    # Categorize lint errors
    ruff_results = ci_results.get("ruff", {})
    if ruff_results.get("status") == "failure":
        for error in ruff_results.get("errors", []):
            categorized["lint"].append({
                "file": error.get("file", "unknown"),
                "line": error.get("line", 0),
                "column": error.get("column", 0),
                "code": error.get("code", ""),
                "message": error.get("message", ""),
            })

    # Categorize type errors
    mypy_results = ci_results.get("mypy", {})
    if mypy_results.get("status") == "failure":
        for error in mypy_results.get("errors", []):
            categorized["types"].append({
                "file": error.get("file", "unknown"),
                "line": error.get("line", 0),
                "column": error.get("column", 0),
                "message": error.get("message", ""),
            })

    # Categorize security issues
    bandit_results = ci_results.get("bandit", {})
    if bandit_results.get("status") == "failure":
        for issue in bandit_results.get("issues", []):
            categorized["security"].append({
                "file": issue.get("filename", "unknown"),
                "line": issue.get("line", 0),
                "severity": issue.get("severity", "MEDIUM"),
                "message": issue.get("message", ""),
            })

    # Categorize dependency vulnerabilities
    pip_audit_results = ci_results.get("pip_audit", {})
    if pip_audit_results.get("status") == "failure":
        for vuln in pip_audit_results.get("vulnerabilities", []):
            categorized["dependencies"].append({
                "package": vuln.get("package", "unknown"),
                "vulnerability": vuln.get("id", "unknown"),
                "severity": vuln.get("severity", "MEDIUM"),
            })

    logger.info(
        f"Categorized failures: tests={len(categorized['tests'])}, "
        f"lint={len(categorized['lint'])}, types={len(categorized['types'])}, "
        f"security={len(categorized['security'])}, dependencies={len(categorized['dependencies'])}"
    )

    return categorized


def _parse_pytest(artifact_path: Path) -> Dict[str, Any]:
    """Parse pytest JSON report.

    Expected format: pytest --json-report output
    """
    pytest_file = artifact_path / "pytest-report.json"

    if not pytest_file.exists():
        logger.debug("pytest report not found")
        return {"status": "unknown", "passed": 0, "failed": 0, "total": 0, "failures": []}

    try:
        with open(pytest_file, "r") as f:
            data = json.load(f)

        summary = data.get("summary", {})
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 0)

        failures = []
        for test in data.get("tests", []):
            if test.get("outcome") in ["failed", "error"]:
                call = test.get("call", {})
                failures.append({
                    "test_name": test.get("nodeid", "unknown"),
                    "file": test.get("nodeid", "").split("::")[0] if "::" in test.get("nodeid", "") else "unknown",
                    "line": test.get("lineno"),
                    "message": call.get("longrepr", "Test failed"),
                    "traceback": call.get("longrepr"),
                })

        status = "success" if failed == 0 else "failure"

        return {
            "status": status,
            "passed": passed,
            "failed": failed,
            "total": total,
            "failures": failures,
        }

    except Exception as e:
        logger.error(f"Failed to parse pytest report: {e}")
        return {"status": "unknown", "passed": 0, "failed": 0, "total": 0, "failures": []}


def _parse_ruff(artifact_path: Path) -> Dict[str, Any]:
    """Parse ruff JSON report.

    Expected format: ruff check --output-format=json
    """
    ruff_file = artifact_path / "ruff-report.json"

    if not ruff_file.exists():
        logger.debug("ruff report not found")
        return {"status": "unknown", "error_count": 0, "errors": []}

    try:
        with open(ruff_file, "r") as f:
            content = f.read()

        # Skip non-JSON lines from uv output (Building, Uninstalled, etc.)
        # Find the first '[' which marks the beginning of JSON array
        json_start = content.find('[')
        if json_start == -1:
            logger.debug("No JSON array found in ruff report")
            return {"status": "unknown", "error_count": 0, "errors": []}

        data = json.loads(content[json_start:])

        # Ruff outputs a list of violations
        errors = []
        for violation in data:
            errors.append({
                "file": violation.get("filename", "unknown"),
                "line": violation.get("location", {}).get("row", 0),
                "column": violation.get("location", {}).get("column", 0),
                "code": violation.get("code", ""),
                "message": violation.get("message", ""),
                "severity": "error" if violation.get("code", "").startswith("E") else "warning",
            })

        error_count = len(errors)
        status = "success" if error_count == 0 else "failure"

        return {
            "status": status,
            "error_count": error_count,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Failed to parse ruff report: {e}")
        return {"status": "unknown", "error_count": 0, "errors": []}


def _parse_mypy(artifact_path: Path) -> Dict[str, Any]:
    """Parse mypy JSON report.

    Expected format: mypy --output=json
    """
    mypy_file = artifact_path / "mypy-report.json"

    if not mypy_file.exists():
        logger.debug("mypy report not found")
        return {"status": "unknown", "error_count": 0, "errors": []}

    try:
        with open(mypy_file, "r") as f:
            # Mypy outputs one JSON object per line
            lines = f.readlines()

        errors = []
        for line in lines:
            if not line.strip():
                continue

            try:
                error = json.loads(line)
                errors.append({
                    "file": error.get("file", "unknown"),
                    "line": error.get("line", 0),
                    "column": error.get("column", 0),
                    "message": error.get("message", ""),
                    "severity": error.get("severity", "error"),
                })
            except json.JSONDecodeError:
                continue

        error_count = len([e for e in errors if e.get("severity") == "error"])
        status = "success" if error_count == 0 else "failure"

        return {
            "status": status,
            "error_count": error_count,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Failed to parse mypy report: {e}")
        return {"status": "unknown", "error_count": 0, "errors": []}


def _parse_bandit(artifact_path: Path) -> Dict[str, Any]:
    """Parse bandit JSON report.

    Expected format: bandit -f json
    """
    bandit_file = artifact_path / "bandit-report.json"

    if not bandit_file.exists():
        logger.debug("bandit report not found")
        return {"status": "unknown", "issues": []}

    try:
        with open(bandit_file, "r") as f:
            data = json.load(f)

        issues = []
        for result in data.get("results", []):
            issues.append({
                "severity": result.get("issue_severity", "MEDIUM"),
                "confidence": result.get("issue_confidence", "MEDIUM"),
                "test_id": result.get("test_id", ""),
                "test_name": result.get("test_name", ""),
                "filename": result.get("filename", "unknown"),
                "line": result.get("line_number", 0),
                "code": result.get("code", ""),
                "message": result.get("issue_text", ""),
            })

        # Consider it a failure if there are HIGH severity issues
        high_severity = [i for i in issues if i["severity"] == "HIGH"]
        status = "failure" if high_severity else ("success" if not issues else "success")

        return {
            "status": status,
            "issues": issues,
        }

    except Exception as e:
        logger.error(f"Failed to parse bandit report: {e}")
        return {"status": "unknown", "issues": []}


def _parse_pip_audit(artifact_path: Path) -> Dict[str, Any]:
    """Parse pip-audit JSON report.

    Expected format: pip-audit --format=json
    """
    pip_audit_file = artifact_path / "pip-audit-report.json"

    if not pip_audit_file.exists():
        logger.debug("pip-audit report not found")
        return {"status": "unknown", "vulnerabilities": []}

    try:
        with open(pip_audit_file, "r") as f:
            data = json.load(f)

        vulnerabilities = []
        for package in data.get("dependencies", []):
            package_name = package.get("name", "unknown")
            for vuln in package.get("vulns", []):
                vulnerabilities.append({
                    "package": package_name,
                    "id": vuln.get("id", "unknown"),
                    "severity": vuln.get("severity", "MEDIUM"),
                    "description": vuln.get("description", ""),
                    "fixed_version": ", ".join(vuln.get("fix_versions", [])),
                })

        status = "failure" if vulnerabilities else "success"

        return {
            "status": status,
            "vulnerabilities": vulnerabilities,
        }

    except Exception as e:
        logger.error(f"Failed to parse pip-audit report: {e}")
        return {"status": "unknown", "vulnerabilities": []}


def _parse_coverage(artifact_path: Path) -> Dict[str, Any]:
    """Parse coverage JSON report.

    Expected format: coverage json
    """
    coverage_file = artifact_path / "coverage.json"

    if not coverage_file.exists():
        logger.debug("coverage report not found")
        return {"status": "unknown", "total_percent": 0.0}

    try:
        with open(coverage_file, "r") as f:
            data = json.load(f)

        totals = data.get("totals", {})
        total_percent = totals.get("percent_covered", 0.0)

        # Consider it success if coverage > 0 (we'll check thresholds elsewhere)
        status = "success" if total_percent >= 0 else "unknown"

        return {
            "status": status,
            "total_percent": total_percent,
            "lines_covered": totals.get("covered_lines", 0),
            "lines_total": totals.get("num_statements", 0),
        }

    except Exception as e:
        logger.error(f"Failed to parse coverage report: {e}")
        return {"status": "unknown", "total_percent": 0.0}


def _empty_ci_results() -> Dict[str, Any]:
    """Return empty CI results structure."""
    return {
        "pytest": {"status": "unknown", "passed": 0, "failed": 0, "total": 0, "failures": []},
        "ruff": {"status": "unknown", "error_count": 0, "errors": []},
        "mypy": {"status": "unknown", "error_count": 0, "errors": []},
        "bandit": {"status": "unknown", "issues": []},
        "pip_audit": {"status": "unknown", "vulnerabilities": []},
        "coverage": {"status": "unknown", "total_percent": 0.0},
    }
