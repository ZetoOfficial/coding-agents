"""Centralized prompt templates for LLM interactions."""

from typing import Dict, List, Any


ISSUE_ANALYSIS_PROMPT = """You are an expert software engineer analyzing a GitHub issue to extract implementation requirements.

Issue Title: {title}

Issue Body:
{body}

Analyze this issue and extract the following information in JSON format:
1. **requirements**: List of specific, actionable requirements (what needs to be done)
2. **acceptance_criteria**: How to verify the implementation is complete and correct
3. **technical_constraints**: Any technical limitations, dependencies, or requirements
4. **target_files**: Files that will likely need to be modified (use your best judgment based on the description)
5. **complexity**: "simple", "medium", or "complex"

Focus on concrete, implementable requirements. Be specific about what code changes are needed.

Output valid JSON matching this schema:
{{
    "requirements": ["requirement 1", "requirement 2", ...],
    "acceptance_criteria": ["criterion 1", "criterion 2", ...],
    "technical_constraints": ["constraint 1", "constraint 2", ...],
    "target_files": ["path/to/file1.py", "path/to/file2.py", ...],
    "complexity": "simple|medium|complex"
}}
"""


CODE_GENERATION_PROMPT = """You are an expert software engineer implementing a feature based on requirements.

Requirements:
{requirements}

Acceptance Criteria:
{acceptance_criteria}

Technical Constraints:
{constraints}

Current Codebase Context:
{codebase_context}

Existing File Content (if modifying):
File: {file_path}
```
{current_content}
```

Related Files for Context:
{related_files}

Generate the complete implementation with the following:
1. **explanation**: Brief explanation of your approach and what changes you're making
2. **files_to_modify**: Complete new content for files being modified (full file, not patches)
3. **files_to_create**: Complete content for new files being created
4. **dependencies_needed**: Any new dependencies to add to pyproject.toml

Important guidelines:
- Provide COMPLETE file content, not diffs or patches
- Follow existing code style and conventions visible in the codebase
- Include proper docstrings and type hints
- Ensure code is syntactically valid Python
- Add appropriate error handling
- Keep it simple - don't over-engineer
- Only make changes directly requested, don't refactor unrelated code

Output valid JSON matching this schema:
{{
    "explanation": "what and why",
    "files_to_modify": {{
        "path/to/file.py": "complete file content..."
    }},
    "files_to_create": {{
        "path/to/new_file.py": "complete file content..."
    }},
    "dependencies_needed": ["package==version", ...]
}}
"""


REVIEW_GENERATION_PROMPT = """You are an expert code reviewer analyzing a pull request.

Original Issue Requirements:
{issue_requirements}

Original Issue Acceptance Criteria:
{acceptance_criteria}

Pull Request Changes:
{pr_diff}

CI/CD Results:
- Tests: {test_status} ({test_details})
- Linting: {lint_status} ({lint_details})
- Type Checking: {type_status} ({type_details})
- Security: {security_status} ({security_details})
- Coverage: {coverage}%

Files Changed:
{files_changed}

Analyze this PR and provide a comprehensive review covering:
1. Does it meet all the original requirements?
2. Are there any bugs, logic errors, or code quality issues?
3. Are there security concerns?
4. Does it follow best practices?
5. Are tests adequate?

Determine if this PR should be **APPROVED** or **CHANGES REQUESTED**.

Hard blocking criteria (must REQUEST_CHANGES if any fail):
- Test failures
- Syntax errors
- High-severity security issues
- Unfulfilled requirements
- Critical linting errors

Output valid JSON matching this schema:
{{
    "approve": true/false,
    "summary": "Overall assessment...",
    "blocking_issues": ["issue 1", "issue 2", ...],
    "non_blocking_issues": ["suggestion 1", "suggestion 2", ...],
    "line_comments": [
        {{
            "path": "file/path.py",
            "line": 42,
            "body": "Comment text...",
            "severity": "blocking|non-blocking|suggestion"
        }}
    ],
    "requirements_fulfilled": [true, false, ...],
    "overall_quality_score": 7.5
}}
"""


FEEDBACK_INTERPRETATION_PROMPT = """You are an expert software engineer interpreting code review feedback to fix issues.

Original Requirements:
{requirements}

Current Implementation:
{current_code}

Review Feedback:
{review_comments}

Blocking Issues:
{blocking_issues}

CI Failures:
{ci_failures}

Analyze the feedback and failures to determine:
1. **what_went_wrong**: Root cause analysis of the issues
2. **how_to_fix**: Specific steps to address each issue
3. **files_to_modify**: Which files need changes
4. **priority**: "high", "medium", or "low"

Be specific about what code changes are needed to address the feedback.

Output valid JSON matching this schema:
{{
    "what_went_wrong": "Analysis of root causes...",
    "how_to_fix": "Specific fix approach...",
    "files_to_modify": ["path/to/file1.py", "path/to/file2.py"],
    "priority": "high|medium|low"
}}
"""


CODEBASE_ANALYSIS_PROMPT = """You are analyzing a codebase to understand its structure and conventions.

Repository Structure:
{repo_structure}

Sample Files:
{sample_files}

Target Area: {target_area}

Analyze the codebase and identify:
1. Code style and conventions (naming, formatting, patterns)
2. Project structure and organization
3. Common patterns and idioms used
4. Testing patterns and practices
5. Files that would need modification for: {modification_goal}

Provide a structured analysis that will help generate consistent code."""


def format_issue_analysis_prompt(title: str, body: str) -> str:
    """Format the issue analysis prompt."""
    return ISSUE_ANALYSIS_PROMPT.format(title=title, body=body)


def format_code_generation_prompt(
    requirements: List[str],
    acceptance_criteria: List[str],
    constraints: List[str],
    codebase_context: str,
    file_path: str = "",
    current_content: str = "",
    related_files: str = "",
) -> str:
    """Format the code generation prompt."""
    return CODE_GENERATION_PROMPT.format(
        requirements="\n".join(f"- {r}" for r in requirements),
        acceptance_criteria="\n".join(f"- {c}" for c in acceptance_criteria),
        constraints="\n".join(f"- {c}" for c in constraints) if constraints else "None",
        codebase_context=codebase_context,
        file_path=file_path,
        current_content=current_content or "(new file)",
        related_files=related_files or "(none provided)",
    )


def format_review_generation_prompt(
    issue_requirements: List[str],
    acceptance_criteria: List[str],
    pr_diff: str,
    ci_results: Dict[str, Any],
    files_changed: List[str],
) -> str:
    """Format the review generation prompt."""
    return REVIEW_GENERATION_PROMPT.format(
        issue_requirements="\n".join(f"- {r}" for r in issue_requirements),
        acceptance_criteria="\n".join(f"- {c}" for c in acceptance_criteria),
        pr_diff=pr_diff[:5000],  # Limit diff size
        test_status=ci_results.get("pytest", {}).get("status", "unknown"),
        test_details=_format_test_details(ci_results.get("pytest", {})),
        lint_status=ci_results.get("ruff", {}).get("status", "unknown"),
        lint_details=_format_lint_details(ci_results.get("ruff", {})),
        type_status=ci_results.get("mypy", {}).get("status", "unknown"),
        type_details=_format_type_details(ci_results.get("mypy", {})),
        security_status=ci_results.get("bandit", {}).get("status", "unknown"),
        security_details=_format_security_details(ci_results.get("bandit", {})),
        coverage=ci_results.get("coverage", {}).get("total_percent", 0),
        files_changed="\n".join(f"- {f}" for f in files_changed),
    )


def format_feedback_interpretation_prompt(
    requirements: List[str],
    current_code: str,
    review_comments: str,
    blocking_issues: List[str],
    ci_failures: Dict[str, Any],
) -> str:
    """Format the feedback interpretation prompt."""
    return FEEDBACK_INTERPRETATION_PROMPT.format(
        requirements="\n".join(f"- {r}" for r in requirements),
        current_code=current_code[:3000],  # Limit code size
        review_comments=review_comments,
        blocking_issues="\n".join(f"- {i}" for i in blocking_issues),
        ci_failures=_format_ci_failures(ci_failures),
    )


def _format_test_details(pytest_results: Dict[str, Any]) -> str:
    """Format pytest results for prompt."""
    if not pytest_results:
        return "No test results"

    passed = pytest_results.get("passed", 0)
    failed = pytest_results.get("failed", 0)
    total = pytest_results.get("total", 0)

    if failed > 0:
        failures = pytest_results.get("failures", [])[:3]  # First 3 failures
        failure_msgs = "; ".join(f"{f.get('test_name', 'unknown')}" for f in failures)
        return f"{failed}/{total} failed: {failure_msgs}"

    return f"{passed}/{total} passed"


def _format_lint_details(ruff_results: Dict[str, Any]) -> str:
    """Format ruff results for prompt."""
    if not ruff_results:
        return "No lint results"

    error_count = ruff_results.get("error_count", 0)
    if error_count > 0:
        errors = ruff_results.get("errors", [])[:3]
        error_msgs = "; ".join(f"{e.get('code', 'unknown')}" for e in errors)
        return f"{error_count} errors: {error_msgs}"

    return "No errors"


def _format_type_details(mypy_results: Dict[str, Any]) -> str:
    """Format mypy results for prompt."""
    if not mypy_results:
        return "No type check results"

    error_count = mypy_results.get("error_count", 0)
    return f"{error_count} errors" if error_count > 0 else "No errors"


def _format_security_details(bandit_results: Dict[str, Any]) -> str:
    """Format bandit results for prompt."""
    if not bandit_results:
        return "No security scan results"

    issues = bandit_results.get("issues", [])
    high_severity = [i for i in issues if i.get("severity") == "HIGH"]

    if high_severity:
        return f"{len(high_severity)} high-severity issues found"

    return f"{len(issues)} issues found" if issues else "No issues"


def _format_ci_failures(ci_failures: Dict[str, Any]) -> str:
    """Format CI failures for prompt."""
    if not ci_failures:
        return "No CI failures"

    failures = []
    for check_name, result in ci_failures.items():
        if result.get("status") == "failure":
            failures.append(f"{check_name}: {result.get('details', 'failed')}")

    return "\n".join(failures) if failures else "No failures"
