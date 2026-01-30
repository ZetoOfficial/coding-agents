"""Code modification and validation module for safe code changes and git operations."""

import logging
import os
import re
import shutil
import tempfile
import py_compile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import git
from git import Repo, GitCommandError

from src.common.models import CodeGeneration

logger = logging.getLogger(__name__)


class CodeModifier:
    """Handles code validation, modification, and git operations."""

    # Security patterns to check for
    SECURITY_PATTERNS = {
        "hardcoded_api_key": (
            r"(?i)(api[_-]?key|apikey|api[_-]?secret|token)\s*[=:]\s*['\"][a-zA-Z0-9_-]{20,}['\"]",
            "Possible hardcoded API key or token detected",
            "HIGH",
        ),
        "hardcoded_password": (
            r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]+['\"]",
            "Possible hardcoded password detected",
            "HIGH",
        ),
        "sql_injection": (
            r"(?i)(execute|executemany|cursor\.execute)\s*\([^)]*%s[^)]*\)",
            "Possible SQL injection vulnerability (string formatting in query)",
            "MEDIUM",
        ),
        "eval_usage": (
            r"\beval\s*\(",
            "Use of eval() detected - potential code injection risk",
            "HIGH",
        ),
        "exec_usage": (
            r"\bexec\s*\(",
            "Use of exec() detected - potential code injection risk",
            "HIGH",
        ),
        "shell_true": (
            r"subprocess\.\w+\([^)]*shell\s*=\s*True",
            "subprocess with shell=True detected - potential command injection",
            "HIGH",
        ),
        "pickle_usage": (
            r"import\s+pickle|from\s+pickle\s+import",
            "Use of pickle detected - potential code execution risk with untrusted data",
            "MEDIUM",
        ),
        "yaml_unsafe": (
            r"yaml\.load\([^)]*\)",
            "Unsafe yaml.load() usage - use yaml.safe_load() instead",
            "MEDIUM",
        ),
    }

    def __init__(self, repo_path: str) -> None:
        """Initialize code modifier with repository path.

        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        try:
            self.repo = Repo(repo_path)
            logger.info(f"Initialized CodeModifier for repository: {repo_path}")
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Path is not a valid git repository: {repo_path}")

    # ============================================================================
    # Code Validation
    # ============================================================================

    def validate_python_syntax(
        self, file_path: str, content: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate Python syntax by attempting to compile the code.

        Args:
            file_path: Path to the file (for error reporting)
            content: Python code content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Create a temporary file to compile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(content)

        try:
            # Try to compile the file
            py_compile.compile(tmp_path, doraise=True)
            logger.debug(f"Syntax validation passed for: {file_path}")
            return True, None

        except py_compile.PyCompileError as e:
            error_msg = f"Syntax error in {file_path}: {e.msg} at line {e.exc_value}"
            logger.warning(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during syntax validation for {file_path}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {tmp_path}: {e}")

    def validate_generated_code_security(
        self, file_path: str, content: str
    ) -> Tuple[bool, List[str]]:
        """Check generated code for common security issues.

        Args:
            file_path: Path to the file being checked
            content: Code content to validate

        Returns:
            Tuple of (is_safe, list_of_issues)
        """
        issues = []

        for pattern_name, (pattern, message, severity) in self.SECURITY_PATTERNS.items():
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                # Calculate line number
                line_num = content[: match.start()].count("\n") + 1
                issue = f"[{severity}] Line {line_num}: {message}"
                issues.append(issue)
                logger.warning(f"Security issue in {file_path}: {issue}")

        # Check for AWS credentials patterns
        if re.search(r"(?i)aws[_-]?secret[_-]?access[_-]?key", content):
            issues.append(
                "[HIGH] Potential AWS credentials detected - ensure proper secret management"
            )

        # Check for private keys
        if re.search(r"-----BEGIN (RSA |DSA )?PRIVATE KEY-----", content):
            issues.append("[HIGH] Private key detected in code - this should never be committed")

        is_safe = len(issues) == 0
        if is_safe:
            logger.debug(f"Security validation passed for: {file_path}")
        else:
            logger.warning(f"Security validation found {len(issues)} issues in: {file_path}")

        return is_safe, issues

    def validate_file_references(
        self, generated_code: CodeGeneration, repo_path: str
    ) -> Tuple[bool, List[str]]:
        """Validate that file references in generated code are valid.

        Checks that:
        - Files to modify actually exist
        - Directories for new files exist or can be created
        - No attempts to modify files outside the repository

        Args:
            generated_code: CodeGeneration model with file changes
            repo_path: Path to repository root

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        repo_path_obj = Path(repo_path).resolve()

        # Check files to modify
        for file_path in generated_code.files_to_modify.keys():
            full_path = (repo_path_obj / file_path).resolve()

            # Security check: ensure file is within repository
            try:
                full_path.relative_to(repo_path_obj)
            except ValueError:
                errors.append(
                    f"Security: File to modify is outside repository: {file_path}"
                )
                continue

            # Check if file exists
            if not full_path.exists():
                errors.append(f"File to modify does not exist: {file_path}")

        # Check files to create
        for file_path in generated_code.files_to_create.keys():
            full_path = (repo_path_obj / file_path).resolve()

            # Security check: ensure file is within repository
            try:
                full_path.relative_to(repo_path_obj)
            except ValueError:
                errors.append(
                    f"Security: File to create is outside repository: {file_path}"
                )
                continue

            # Check if file already exists
            if full_path.exists():
                errors.append(
                    f"File to create already exists (use modify instead): {file_path}"
                )
                continue

            # Check if parent directory exists or can be created
            parent_dir = full_path.parent
            if not parent_dir.exists():
                # This is OK - we'll create it
                logger.debug(f"Parent directory will be created: {parent_dir}")

        is_valid = len(errors) == 0
        if is_valid:
            logger.info("File reference validation passed")
        else:
            logger.warning(f"File reference validation found {len(errors)} errors")

        return is_valid, errors

    # ============================================================================
    # Code Application
    # ============================================================================

    def apply_changes_with_validation(
        self, changes: Dict[str, str], repo_path: str
    ) -> Tuple[bool, List[str]]:
        """Apply code changes with validation and backup/rollback support.

        This method:
        1. Creates backups of files to be modified
        2. Validates syntax for each Python file
        3. Applies changes
        4. Validates security
        5. Rolls back on any errors

        Args:
            changes: Dictionary mapping file paths to new content
            repo_path: Path to repository root

        Returns:
            Tuple of (success, list_of_errors_or_messages)
        """
        repo_path_obj = Path(repo_path).resolve()
        backup_dir = None
        modified_files = []
        errors = []

        try:
            # Create backup directory
            backup_dir = tempfile.mkdtemp(prefix="code_backup_")
            logger.info(f"Created backup directory: {backup_dir}")

            # Step 1: Backup and validate all files
            for file_path, new_content in changes.items():
                full_path = (repo_path_obj / file_path).resolve()

                # Backup existing file if it exists
                if full_path.exists():
                    backup_path = Path(backup_dir) / file_path
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(full_path, backup_path)
                    logger.debug(f"Backed up: {file_path}")

                # Validate Python syntax
                if file_path.endswith(".py"):
                    is_valid, error = self.validate_python_syntax(file_path, new_content)
                    if not is_valid:
                        errors.append(f"Syntax validation failed for {file_path}: {error}")
                        raise ValueError(f"Syntax error in {file_path}")

                    # Validate security
                    is_safe, security_issues = self.validate_generated_code_security(
                        file_path, new_content
                    )
                    if not is_safe:
                        # Log security issues but don't fail (these are warnings)
                        for issue in security_issues:
                            logger.warning(f"Security check in {file_path}: {issue}")
                            errors.append(f"Security warning in {file_path}: {issue}")

            # Step 2: Apply all changes
            for file_path, new_content in changes.items():
                full_path = (repo_path_obj / file_path).resolve()

                # Create parent directories if needed
                full_path.parent.mkdir(parents=True, exist_ok=True)

                # Write new content
                full_path.write_text(new_content, encoding="utf-8")
                modified_files.append(file_path)
                logger.info(f"Applied changes to: {file_path}")

            logger.info(f"Successfully applied changes to {len(modified_files)} files")
            return True, [f"Successfully modified {len(modified_files)} files"]

        except Exception as e:
            # Rollback changes
            logger.error(f"Error applying changes: {e}. Rolling back...")
            errors.append(f"Error during application: {str(e)}")

            if backup_dir and os.path.exists(backup_dir):
                for file_path in modified_files:
                    backup_path = Path(backup_dir) / file_path
                    if backup_path.exists():
                        full_path = repo_path_obj / file_path
                        shutil.copy2(backup_path, full_path)
                        logger.info(f"Rolled back: {file_path}")

            return False, errors

        finally:
            # Clean up backup directory
            if backup_dir and os.path.exists(backup_dir):
                try:
                    shutil.rmtree(backup_dir)
                    logger.debug(f"Cleaned up backup directory: {backup_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up backup directory: {e}")

    # ============================================================================
    # Git Operations
    # ============================================================================

    def create_branch(self, branch_name: str, base_branch: str) -> None:
        """Create a new branch from base branch.

        Args:
            branch_name: Name of the new branch
            base_branch: Name of the base branch to branch from

        Raises:
            GitCommandError: If branch creation fails
        """
        try:
            # Ensure we're on the base branch and it's up to date
            if self.repo.active_branch.name != base_branch:
                self.repo.git.checkout(base_branch)
                logger.info(f"Checked out base branch: {base_branch}")

            # Pull latest changes
            try:
                self.repo.git.pull("origin", base_branch)
                logger.info(f"Pulled latest changes from origin/{base_branch}")
            except GitCommandError as e:
                logger.warning(f"Could not pull latest changes: {e}")

            # Create and checkout new branch
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()

            logger.info(f"Created and checked out branch: {branch_name}")

        except GitCommandError as e:
            logger.error(f"Failed to create branch {branch_name}: {e}")
            raise

    def create_commit(self, message: str, files: List[str]) -> str:
        """Create a git commit with specified files.

        Args:
            message: Commit message
            files: List of file paths to include in commit

        Returns:
            Commit SHA

        Raises:
            GitCommandError: If commit creation fails
        """
        try:
            # Stage specified files
            if files:
                self.repo.index.add(files)
                logger.debug(f"Staged {len(files)} files for commit")
            else:
                raise ValueError("No files specified for commit")

            # Create commit
            commit = self.repo.index.commit(message)
            commit_sha = commit.hexsha

            logger.info(f"Created commit {commit_sha[:8]}: {message}")
            return commit_sha

        except GitCommandError as e:
            logger.error(f"Failed to create commit: {e}")
            raise

    def push_branch(self, branch_name: str) -> None:
        """Push branch to remote repository.

        Args:
            branch_name: Name of the branch to push

        Raises:
            GitCommandError: If push fails
        """
        try:
            # Push to origin
            origin = self.repo.remote("origin")
            origin.push(refspec=f"{branch_name}:{branch_name}")

            logger.info(f"Pushed branch to origin: {branch_name}")

        except GitCommandError as e:
            logger.error(f"Failed to push branch {branch_name}: {e}")
            raise

    def generate_commit_message(
        self,
        issue_number: int,
        issue_title: str,
        iteration: int,
        changes: Dict[str, str],
    ) -> str:
        """Generate a descriptive commit message.

        Args:
            issue_number: GitHub issue number
            issue_title: Title of the issue
            iteration: Current iteration number
            changes: Dictionary of file changes

        Returns:
            Formatted commit message
        """
        # Count changes by type
        modifications = len([f for f in changes.keys() if Path(self.repo_path / f).exists()])
        additions = len(changes) - modifications

        # Build commit message
        lines = []
        lines.append(f"feat: Address issue #{issue_number} - {issue_title}")
        lines.append("")

        if iteration > 1:
            lines.append(f"Iteration {iteration}: Applying reviewer feedback")
        else:
            lines.append("Initial implementation")

        lines.append("")
        lines.append("Changes:")
        if modifications > 0:
            lines.append(f"- Modified {modifications} file(s)")
        if additions > 0:
            lines.append(f"- Added {additions} file(s)")

        lines.append("")
        lines.append(f"Related to issue #{issue_number}")

        message = "\n".join(lines)
        logger.debug(f"Generated commit message: {message[:100]}...")

        return message

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def get_current_branch(self) -> str:
        """Get the name of the current active branch.

        Returns:
            Current branch name
        """
        return self.repo.active_branch.name

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists locally.

        Args:
            branch_name: Name of the branch to check

        Returns:
            True if branch exists, False otherwise
        """
        return branch_name in [b.name for b in self.repo.branches]

    def get_modified_files(self) -> List[str]:
        """Get list of modified files in working directory.

        Returns:
            List of modified file paths
        """
        modified_files = [item.a_path for item in self.repo.index.diff(None)]
        return modified_files

    def get_staged_files(self) -> List[str]:
        """Get list of staged files.

        Returns:
            List of staged file paths
        """
        staged_files = [item.a_path for item in self.repo.index.diff("HEAD")]
        return staged_files

    def is_clean(self) -> bool:
        """Check if working directory is clean (no uncommitted changes).

        Returns:
            True if clean, False otherwise
        """
        return not self.repo.is_dirty()

    def reset_to_commit(self, commit_sha: str, hard: bool = False) -> None:
        """Reset repository to a specific commit.

        Args:
            commit_sha: SHA of commit to reset to
            hard: If True, discard all changes (git reset --hard)

        Raises:
            GitCommandError: If reset fails
        """
        try:
            if hard:
                self.repo.git.reset("--hard", commit_sha)
                logger.warning(f"Hard reset to commit: {commit_sha}")
            else:
                self.repo.git.reset(commit_sha)
                logger.info(f"Soft reset to commit: {commit_sha}")

        except GitCommandError as e:
            logger.error(f"Failed to reset to commit {commit_sha}: {e}")
            raise


def create_code_modifier(repo_path: str) -> CodeModifier:
    """Factory function to create CodeModifier instance.

    Args:
        repo_path: Path to git repository

    Returns:
        CodeModifier instance

    Raises:
        ValueError: If repo_path is invalid
    """
    return CodeModifier(repo_path)
