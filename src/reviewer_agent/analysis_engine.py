"""Analysis engine for PR diff analysis and comment generation."""

import logging
import re
from typing import List, Dict, Any, Optional

from src.common.models import ReviewComment
from src.common.config import AgentConfig
from src.code_agent.llm_client import call_llm_text

logger = logging.getLogger(__name__)


def analyze_pr_diff(diff: str, requirements: List[str], config: AgentConfig) -> Dict[str, Any]:
    """Analyze PR diff to understand code changes and quality.

    Uses LLM to analyze the diff and provide structured feedback about:
    - What was changed and why
    - Code quality issues
    - Potential bugs
    - Best practice violations

    Args:
        diff: Unified diff string from PR
        requirements: List of requirements from the original issue
        config: Agent configuration for LLM access

    Returns:
        Dictionary with analysis results:
        {
            "summary": str,
            "changes_made": List[str],
            "potential_issues": List[str],
            "quality_assessment": str,
        }
    """
    if not diff or not diff.strip():
        logger.warning("Empty diff provided for analysis")
        return {
            "summary": "No changes detected",
            "changes_made": [],
            "potential_issues": ["No code changes found in PR"],
            "quality_assessment": "Cannot assess - no changes",
        }

    # Build analysis prompt
    prompt = f"""Analyze this pull request diff and provide a brief assessment.

Requirements to fulfill:
{chr(10).join(f"- {req}" for req in requirements)}

Diff:
```diff
{diff[:8000]}  # Limit diff size for token constraints
```

Provide a concise analysis covering:
1. What changes were made (2-3 sentences)
2. Any potential issues or concerns (list format)
3. Overall quality assessment (1 sentence)

Format as:
SUMMARY: <summary>
CHANGES:
- <change 1>
- <change 2>
ISSUES:
- <issue 1> (or "None" if no issues)
QUALITY: <assessment>
"""

    try:
        response = call_llm_text(prompt, config)

        # Parse response
        analysis = _parse_diff_analysis(response)

        logger.info(f"Analyzed diff: {len(analysis['changes_made'])} changes, "
                   f"{len(analysis['potential_issues'])} potential issues")

        return analysis

    except Exception as e:
        logger.error(f"Failed to analyze diff with LLM: {e}")
        return {
            "summary": "Analysis failed",
            "changes_made": ["Unable to analyze changes"],
            "potential_issues": [f"Analysis error: {str(e)}"],
            "quality_assessment": "Cannot assess due to analysis failure",
        }


def check_requirements_fulfillment(
    pr_data: Dict[str, Any],
    requirements: List[str],
) -> Dict[str, bool]:
    """Check which requirements are fulfilled by the PR.

    Simple heuristic-based checking:
    - Looks for keywords from requirements in changed files
    - Checks if files mentioned in requirements were modified
    - Returns best-effort fulfillment mapping

    Args:
        pr_data: Dictionary with PR information including files_changed and diff
        requirements: List of requirement strings

    Returns:
        Dictionary mapping each requirement to fulfillment status
    """
    if not requirements:
        return {}

    files_changed = pr_data.get("files_changed", [])
    diff = pr_data.get("diff", "")

    fulfillment = {}

    for req in requirements:
        # Extract potential file names or keywords from requirement
        req_lower = req.lower()

        # Check if requirement mentions specific files that were changed
        file_mentioned = any(
            file_path in req_lower or Path(file_path).stem.lower() in req_lower
            for file_path in files_changed
        )

        # Check if key terms from requirement appear in diff
        key_terms = _extract_key_terms(req)
        terms_in_diff = any(term.lower() in diff.lower() for term in key_terms)

        # Simple heuristic: fulfilled if either condition is met
        fulfillment[req] = file_mentioned or terms_in_diff

    fulfilled_count = sum(fulfillment.values())
    logger.info(f"Requirements fulfillment: {fulfilled_count}/{len(requirements)} met")

    return fulfillment


def find_diff_position(
    diff_data: Dict[str, Any],
    file_path: str,
    line_number: int,
) -> Optional[int]:
    """Find the position in unified diff for a given file and line number.

    GitHub uses diff position (not line numbers) for PR review comments.
    This function converts absolute line number to diff position.

    Args:
        diff_data: Parsed diff information with file patches
        file_path: Path to the file
        line_number: Absolute line number in the new version

    Returns:
        Diff position (1-indexed) or None if not found
    """
    # Get the patch for this file
    file_patches = diff_data.get("files", {})
    patch = file_patches.get(file_path)

    if not patch:
        logger.debug(f"No patch found for file: {file_path}")
        return None

    # Parse the patch to find the position
    position = _calculate_diff_position(patch, line_number)

    if position:
        logger.debug(f"Found diff position {position} for {file_path}:{line_number}")
    else:
        logger.debug(f"Could not find diff position for {file_path}:{line_number}")

    return position


def generate_line_comments(
    ci_results: Dict[str, Any],
    diff_data: Dict[str, Any],
) -> List[ReviewComment]:
    """Generate inline review comments for CI failures.

    Creates ReviewComment objects for each CI failure that can be mapped
    to a specific line in the PR diff.

    Args:
        ci_results: Categorized CI results from categorize_failures
        diff_data: Parsed diff data with file patches

    Returns:
        List of ReviewComment objects with file path, position, and message
    """
    comments = []

    # Process lint errors
    for lint_error in ci_results.get("lint", []):
        comment = _create_comment_for_lint(lint_error, diff_data)
        if comment:
            comments.append(comment)

    # Process type errors
    for type_error in ci_results.get("types", []):
        comment = _create_comment_for_type(type_error, diff_data)
        if comment:
            comments.append(comment)

    # Process security issues
    for security_issue in ci_results.get("security", []):
        comment = _create_comment_for_security(security_issue, diff_data)
        if comment:
            comments.append(comment)

    # Process test failures (harder to map to specific lines, but try)
    for test_failure in ci_results.get("tests", []):
        comment = _create_comment_for_test(test_failure, diff_data)
        if comment:
            comments.append(comment)

    logger.info(f"Generated {len(comments)} inline review comments from CI results")

    return comments


def _parse_diff_analysis(response: str) -> Dict[str, Any]:
    """Parse LLM response for diff analysis."""
    summary = ""
    changes = []
    issues = []
    quality = ""

    # Extract sections using regex
    summary_match = re.search(r"SUMMARY:\s*(.+?)(?=CHANGES:|$)", response, re.DOTALL)
    if summary_match:
        summary = summary_match.group(1).strip()

    changes_match = re.search(r"CHANGES:\s*(.+?)(?=ISSUES:|$)", response, re.DOTALL)
    if changes_match:
        changes_text = changes_match.group(1).strip()
        changes = [line.strip("- ").strip() for line in changes_text.split("\n") if line.strip().startswith("-")]

    issues_match = re.search(r"ISSUES:\s*(.+?)(?=QUALITY:|$)", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1).strip()
        if issues_text.lower() != "none":
            issues = [line.strip("- ").strip() for line in issues_text.split("\n") if line.strip().startswith("-")]

    quality_match = re.search(r"QUALITY:\s*(.+?)$", response, re.DOTALL)
    if quality_match:
        quality = quality_match.group(1).strip()

    return {
        "summary": summary or "No summary provided",
        "changes_made": changes or ["Changes detected but not parsed"],
        "potential_issues": issues or [],
        "quality_assessment": quality or "No quality assessment provided",
    }


def _extract_key_terms(requirement: str) -> List[str]:
    """Extract key terms from a requirement string.

    Args:
        requirement: Requirement description

    Returns:
        List of key terms (function names, class names, keywords)
    """
    # Remove common words and extract potential identifiers
    common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                   "of", "with", "by", "from", "that", "this", "should", "must", "will"}

    words = re.findall(r'\b\w+\b', requirement.lower())
    key_terms = [w for w in words if w not in common_words and len(w) > 3]

    # Also look for snake_case or camelCase identifiers
    identifiers = re.findall(r'\b[a-z_][a-z0-9_]*\b|\b[A-Z][a-zA-Z0-9]*\b', requirement)
    key_terms.extend(identifiers)

    return list(set(key_terms))


def _calculate_diff_position(patch: str, line_number: int) -> Optional[int]:
    """Calculate diff position from patch and line number.

    Args:
        patch: Unified diff patch for a file
        line_number: Target line number in new version

    Returns:
        Diff position (1-indexed) or None
    """
    if not patch:
        return None

    position = 0
    current_new_line = 0

    for line in patch.split("\n"):
        position += 1

        # Skip diff header lines
        if line.startswith("@@"):
            # Parse hunk header to get starting line
            match = re.search(r'\+(\d+)', line)
            if match:
                current_new_line = int(match.group(1)) - 1
            continue

        if line.startswith("-"):
            # Deleted line, doesn't affect new line count
            continue
        elif line.startswith("+"):
            # Added line
            current_new_line += 1
            if current_new_line == line_number:
                return position
        else:
            # Context line
            current_new_line += 1
            if current_new_line == line_number:
                return position

    return None


def _create_comment_for_lint(lint_error: Dict[str, Any], diff_data: Dict[str, Any]) -> Optional[ReviewComment]:
    """Create review comment for lint error."""
    file_path = lint_error.get("file", "")
    line = lint_error.get("line", 0)

    if not file_path or not line:
        return None

    position = find_diff_position(diff_data, file_path, line)

    # Only create comment if the file is part of the PR diff
    if position is None:
        return None

    message = (
        f"**Linting Error ({lint_error.get('code', 'unknown')})**\n\n"
        f"{lint_error.get('message', 'Linting issue detected')}\n\n"
        f"Please fix this linting issue."
    )

    return ReviewComment(
        path=file_path,
        position=position,
        line=line if not position else None,
        body=message,
        severity="blocking",
    )


def _create_comment_for_type(type_error: Dict[str, Any], diff_data: Dict[str, Any]) -> Optional[ReviewComment]:
    """Create review comment for type error."""
    file_path = type_error.get("file", "")
    line = type_error.get("line", 0)

    if not file_path or not line:
        return None

    position = find_diff_position(diff_data, file_path, line)

    # Only create comment if the file is part of the PR diff
    if position is None:
        return None

    message = (
        f"**Type Error**\n\n"
        f"{type_error.get('message', 'Type checking issue detected')}\n\n"
        f"Please fix this type error."
    )

    return ReviewComment(
        path=file_path,
        position=position,
        line=line if not position else None,
        body=message,
        severity="blocking",
    )


def _create_comment_for_security(security_issue: Dict[str, Any], diff_data: Dict[str, Any]) -> Optional[ReviewComment]:
    """Create review comment for security issue."""
    file_path = security_issue.get("file", "")
    line = security_issue.get("line", 0)

    if not file_path or not line:
        return None

    position = find_diff_position(diff_data, file_path, line)

    # Only create comment if the file is part of the PR diff
    if position is None:
        return None

    severity_level = security_issue.get("severity", "MEDIUM")
    severity_map = {"HIGH": "blocking", "MEDIUM": "non-blocking", "LOW": "suggestion"}

    message = (
        f"**Security Issue ({severity_level})**\n\n"
        f"{security_issue.get('message', 'Security concern detected')}\n\n"
        f"Please review and address this security concern."
    )

    return ReviewComment(
        path=file_path,
        position=position,
        line=line if not position else None,
        body=message,
        severity=severity_map.get(severity_level, "non-blocking"),
    )


def _create_comment_for_test(test_failure: Dict[str, Any], diff_data: Dict[str, Any]) -> Optional[ReviewComment]:
    """Create review comment for test failure."""
    file_path = test_failure.get("file", "")
    line = test_failure.get("line")

    if not file_path:
        return None

    # If we don't have a specific line, we can't create an inline comment
    if not line:
        return None

    position = find_diff_position(diff_data, file_path, line)

    # Only create comment if the file is part of the PR diff
    if position is None:
        return None

    message = (
        f"**Test Failure**\n\n"
        f"Test: `{test_failure.get('test_name', 'unknown')}`\n\n"
        f"{test_failure.get('message', 'Test failed')}\n\n"
        f"Please fix the failing test or update the implementation."
    )

    return ReviewComment(
        path=file_path,
        position=position,
        line=line if not position else None,
        body=message,
        severity="blocking",
    )


# Import Path for file path operations
from pathlib import Path
