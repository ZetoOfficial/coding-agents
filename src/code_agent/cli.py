"""Main CLI for the Code Agent - orchestrates all modules for automated SDLC."""

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.common.config import load_config, AgentConfig
from src.common.models import (
    RequirementAnalysis,
    CodeGeneration,
    FeedbackInterpretation,
    AgentState,
)
from src.code_agent.github_client import GitHubClient
from src.code_agent.llm_client import call_llm_structured
from src.code_agent.state_manager import StateManager
from src.code_agent.code_analyzer import CodeAnalyzer
from src.code_agent.code_modifier import CodeModifier
from src.code_agent.prompts import (
    format_issue_analysis_prompt,
    format_code_generation_prompt,
    format_feedback_interpretation_prompt,
)

app = typer.Typer(
    name="code-agent",
    help="Automated Code Agent for GitHub-integrated SDLC",
    add_completion=False,
)

console = Console()
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================


def setup_rich_logging(log_level: str = "INFO") -> None:
    """Setup rich console logging."""
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def print_header(text: str) -> None:
    """Print a formatted header."""
    console.print(Panel(text, style="bold blue"))


def print_success(text: str) -> None:
    """Print success message."""
    console.print(f"[bold green]✓[/bold green] {text}")


def print_error(text: str) -> None:
    """Print error message."""
    console.print(f"[bold red]✗[/bold red] {text}")


def print_info(text: str) -> None:
    """Print info message."""
    console.print(f"[bold blue]ℹ[/bold blue] {text}")


def get_repo_path() -> str:
    """Get the current repository path."""
    return str(Path.cwd())


# ============================================================================
# Main Commands
# ============================================================================


@app.command()
def process_issue(
    issue_number: int = typer.Argument(..., help="GitHub issue number to process"),
    repo_path: Optional[str] = typer.Option(
        None, "--repo", "-r", help="Path to repository (defaults to current directory)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force processing even if iteration limit reached"
    ),
) -> None:
    """Process a GitHub issue and create/update a pull request.

    This command will:
    1. Fetch the issue from GitHub
    2. Check iteration count and exit if limit reached
    3. Parse issue requirements with LLM
    4. Analyze codebase to identify target files
    5. Generate code changes with LLM
    6. Validate syntax and security
    7. Create/checkout branch (agent/issue-{number}-iter-{N})
    8. Apply changes to files
    9. Commit and push
    10. Create PR (or update if exists)
    11. Add iteration labels and link to issue
    """
    print_header(f"Processing Issue #{issue_number}")

    try:
        # Load configuration
        config = load_config()
        setup_rich_logging(config.log_level)
        logger.info(f"Starting process-issue for issue #{issue_number}")

        # Initialize components
        repo_path_str = repo_path or get_repo_path()
        github_client = GitHubClient(config)
        state_manager = StateManager()
        code_analyzer = CodeAnalyzer(repo_path_str)
        code_modifier = CodeModifier(repo_path_str)

        # Step 1: Fetch issue
        print_info(f"Fetching issue #{issue_number}...")
        issue = github_client.fetch_issue(issue_number)
        print_success(f"Fetched issue: {issue.title}")

        # Step 2: Check iteration count
        label_names = [label.name for label in issue.labels]
        current_iteration = github_client.get_iteration_from_labels(label_names)

        if current_iteration >= config.max_iterations and not force:
            print_error(
                f"Iteration limit reached ({current_iteration}/{config.max_iterations}). "
                f"Use --force to override."
            )
            logger.warning(
                f"Issue #{issue_number} reached iteration limit: {current_iteration}"
            )
            sys.exit(1)

        next_iteration = current_iteration + 1
        print_info(f"Starting iteration {next_iteration}/{config.max_iterations}")

        # Step 3: Parse issue with LLM
        print_info("Analyzing issue requirements...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Calling LLM for requirement analysis...", total=None)

            prompt = format_issue_analysis_prompt(issue.title, issue.body)
            analysis: RequirementAnalysis = call_llm_structured(
                prompt=prompt,
                response_model=RequirementAnalysis,
                config=config,
            )
            progress.update(task, completed=True)

        print_success(f"Identified {len(analysis.requirements)} requirements")
        logger.info(f"Analysis: {len(analysis.requirements)} requirements, complexity: {analysis.complexity}")

        # Step 4: Analyze codebase to identify files
        print_info("Analyzing codebase...")
        if analysis.target_files:
            target_files = analysis.target_files
        else:
            # Use code analyzer to identify target files
            target_files = code_analyzer.identify_target_files(
                analysis.requirements, max_results=10
            )

        print_success(f"Identified {len(target_files)} target files")
        logger.info(f"Target files: {target_files}")

        # Step 5: Build context and generate code
        print_info("Building codebase context...")
        codebase_context = code_analyzer.build_context_for_generation(
            target_files=target_files,
            max_tokens=8000,
            include_related=True,
        )

        print_info("Generating code changes...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Calling LLM for code generation...", total=None)

            # For first file, get current content if it exists
            current_content = ""
            file_path = target_files[0] if target_files else ""
            if file_path:
                try:
                    current_content = (Path(repo_path_str) / file_path).read_text()
                except Exception as e:
                    logger.debug(f"Could not read {file_path}: {e}")

            prompt = format_code_generation_prompt(
                requirements=analysis.requirements,
                acceptance_criteria=analysis.acceptance_criteria,
                constraints=analysis.technical_constraints,
                codebase_context=codebase_context,
                file_path=file_path,
                current_content=current_content,
            )

            code_gen: CodeGeneration = call_llm_structured(
                prompt=prompt,
                response_model=CodeGeneration,
                config=config,
            )
            progress.update(task, completed=True)

        total_changes = len(code_gen.files_to_modify) + len(code_gen.files_to_create)
        print_success(f"Generated changes for {total_changes} files")
        logger.info(f"Code generation: {code_gen.explanation[:100]}...")

        # Step 6: Validate changes
        print_info("Validating generated code...")

        # Validate file references
        is_valid, errors = code_modifier.validate_file_references(code_gen, repo_path_str)
        if not is_valid:
            print_error("File reference validation failed:")
            for error in errors:
                console.print(f"  - {error}")
            sys.exit(1)

        # Combine all changes for validation and application
        all_changes = {**code_gen.files_to_modify, **code_gen.files_to_create}

        # Validate syntax and security
        validation_warnings = []
        for file_path, content in all_changes.items():
            if file_path.endswith(".py"):
                is_valid, error = code_modifier.validate_python_syntax(file_path, content)
                if not is_valid:
                    print_error(f"Syntax validation failed for {file_path}: {error}")
                    sys.exit(1)

                is_safe, security_issues = code_modifier.validate_generated_code_security(
                    file_path, content
                )
                if not is_safe:
                    validation_warnings.extend(security_issues)

        if validation_warnings:
            print_info(f"Security warnings ({len(validation_warnings)}):")
            for warning in validation_warnings[:5]:  # Show first 5
                console.print(f"  - {warning}")

        print_success("Code validation passed")

        # Step 7: Create/checkout branch
        branch_name = f"{config.work_branch_prefix}{issue_number}-iter-{next_iteration}"
        print_info(f"Creating branch: {branch_name}")

        if code_modifier.branch_exists(branch_name):
            logger.info(f"Branch {branch_name} already exists, checking out")
            code_modifier.repo.git.checkout(branch_name)
        else:
            code_modifier.create_branch(branch_name, config.default_branch)

        print_success(f"Checked out branch: {branch_name}")

        # Step 8: Apply changes
        print_info(f"Applying changes to {len(all_changes)} files...")
        success, messages = code_modifier.apply_changes_with_validation(
            all_changes, repo_path_str
        )

        if not success:
            print_error("Failed to apply changes:")
            for msg in messages:
                console.print(f"  - {msg}")
            sys.exit(1)

        print_success(f"Applied changes to {len(all_changes)} files")

        # Step 9: Commit
        print_info("Creating commit...")
        commit_message = code_modifier.generate_commit_message(
            issue_number=issue_number,
            issue_title=issue.title,
            iteration=next_iteration,
            changes=all_changes,
        )

        commit_sha = code_modifier.create_commit(
            message=commit_message,
            files=list(all_changes.keys()),
        )
        print_success(f"Created commit: {commit_sha[:8]}")

        # Step 10: Push
        print_info(f"Pushing branch: {branch_name}")
        code_modifier.push_branch(branch_name)
        print_success(f"Pushed to remote")

        # Step 11: Create or update PR
        print_info("Managing pull request...")

        # Check if PR already exists for this issue
        existing_pr = None
        try:
            # Try to find existing PR by searching for the issue number
            # This is a simplified approach - you might want to store PR number in state
            for pr_num in range(1, 100):  # Check recent PRs
                try:
                    pr = github_client.fetch_pull_request(pr_num)
                    if pr.issue_number == issue_number and pr.state == "open":
                        existing_pr = pr
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Error searching for existing PR: {e}")

        if existing_pr:
            print_info(f"PR #{existing_pr.number} already exists, updating labels...")
            pr_number = existing_pr.number

            # Update iteration label
            old_label = f"iteration-{current_iteration}"
            new_label = f"iteration-{next_iteration}"
            github_client.update_issue_labels(
                issue_number=pr_number,
                labels_to_add=[new_label, "agent:in-progress"],
                labels_to_remove=[old_label],
            )
        else:
            # Create new PR
            pr_title = f"[Agent] {issue.title}"
            pr_body = f"""## Automated Implementation

**Issue:** #{issue_number}
**Iteration:** {next_iteration}

### Implementation Summary
{code_gen.explanation}

### Changes Made
- Modified: {len(code_gen.files_to_modify)} file(s)
- Created: {len(code_gen.files_to_create)} file(s)

### Requirements Addressed
{chr(10).join(f'- {req}' for req in analysis.requirements)}

---
*This PR was automatically generated by the Code Agent*
"""

            pr = github_client.create_pull_request(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch=config.default_branch,
                issue_number=issue_number,
            )
            pr_number = pr.number

            print_success(f"Created PR #{pr_number}")

            # Add labels
            github_client.update_issue_labels(
                issue_number=pr_number,
                labels_to_add=[f"iteration-{next_iteration}", "agent:in-progress"],
                labels_to_remove=[],
            )

        # Step 12: Link PR to issue
        comment = f"""✅ **Code Agent Update**

Created PR #{pr_number} for this issue (iteration {next_iteration}).

**Summary:** {code_gen.explanation}

**Branch:** `{branch_name}`
**Commit:** {commit_sha[:8]}

The PR is ready for review. CI/CD checks will run automatically.
"""
        github_client.add_issue_comment(issue_number, comment)
        print_success(f"Added comment to issue #{issue_number}")

        # Update state
        state_manager.update_state(
            issue_number=issue_number,
            pr_number=pr_number,
            iteration=next_iteration,
            status="in_progress",
        )

        print_header(f"✅ Successfully processed issue #{issue_number}")
        console.print(f"\n[bold]PR URL:[/bold] {pr.html_url if 'pr' in locals() else f'#{pr_number}'}")
        console.print(f"[bold]Branch:[/bold] {branch_name}")
        console.print(f"[bold]Iteration:[/bold] {next_iteration}/{config.max_iterations}\n")

        logger.info(f"Successfully completed process-issue for issue #{issue_number}")

    except KeyboardInterrupt:
        print_error("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Failed to process issue: {str(e)}")
        logger.exception(f"Error processing issue #{issue_number}")
        sys.exit(1)


@app.command()
def apply_feedback(
    pr_number: int = typer.Argument(..., help="GitHub PR number to process feedback for"),
    repo_path: Optional[str] = typer.Option(
        None, "--repo", "-r", help="Path to repository (defaults to current directory)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force processing even if iteration limit reached"
    ),
) -> None:
    """Process review feedback and update the PR.

    This command will:
    1. Fetch PR and review comments
    2. Parse feedback with LLM
    3. Check iteration limit
    4. Generate fixes based on feedback
    5. Apply changes
    6. Commit and push
    7. Increment iteration label
    """
    print_header(f"Applying Feedback for PR #{pr_number}")

    try:
        # Load configuration
        config = load_config()
        setup_rich_logging(config.log_level)
        logger.info(f"Starting apply-feedback for PR #{pr_number}")

        # Initialize components
        repo_path_str = repo_path or get_repo_path()
        github_client = GitHubClient(config)
        state_manager = StateManager()
        code_analyzer = CodeAnalyzer(repo_path_str)
        code_modifier = CodeModifier(repo_path_str)

        # Step 1: Fetch PR and feedback
        print_info(f"Fetching PR #{pr_number}...")
        pr = github_client.fetch_pull_request(pr_number)
        print_success(f"Fetched PR: {pr.title}")

        # Get issue number
        issue_number = pr.issue_number
        if not issue_number:
            print_error("PR is not linked to an issue")
            sys.exit(1)

        # Check iteration limit
        label_names = [label.name for label in pr.labels]
        current_iteration = github_client.get_iteration_from_labels(label_names)

        if current_iteration >= config.max_iterations and not force:
            print_error(
                f"Iteration limit reached ({current_iteration}/{config.max_iterations}). "
                f"Use --force to override."
            )
            sys.exit(1)

        next_iteration = current_iteration + 1
        print_info(f"Processing feedback for iteration {next_iteration}/{config.max_iterations}")

        # Parse review feedback
        print_info("Parsing review feedback...")
        feedback = github_client.parse_review_feedback(pr_number)

        if not feedback:
            print_info("No review feedback found")
            logger.info(f"No feedback to process for PR #{pr_number}")
            return

        print_success(f"Found {len(feedback)} feedback items")

        # Get original issue for context
        issue = github_client.fetch_issue(issue_number)

        # Step 2: Interpret feedback with LLM
        print_info("Interpreting feedback with LLM...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing feedback...", total=None)

            # Get current code from PR files
            files_changed = github_client.get_pr_files_changed(pr_number)
            current_code = "\n\n".join(
                f"File: {fc.path}\n```\n{fc.patch or '(no patch)'}\n```"
                for fc in files_changed[:5]  # Limit to first 5 files
            )

            # Combine feedback
            review_comments = "\n".join(feedback)

            prompt = format_feedback_interpretation_prompt(
                requirements=[issue.body],
                current_code=current_code,
                review_comments=review_comments,
                blocking_issues=[],  # We could extract these from review comments
                ci_failures={},  # We could fetch CI status
            )

            interpretation: FeedbackInterpretation = call_llm_structured(
                prompt=prompt,
                response_model=FeedbackInterpretation,
                config=config,
            )
            progress.update(task, completed=True)

        print_success("Interpreted feedback")
        console.print(f"\n[bold]Analysis:[/bold] {interpretation.what_went_wrong[:200]}...")
        console.print(f"[bold]Fix approach:[/bold] {interpretation.how_to_fix[:200]}...\n")

        # Step 3: Generate fixes
        print_info("Generating fixes...")

        # Build context
        target_files = interpretation.files_to_modify
        codebase_context = code_analyzer.build_context_for_generation(
            target_files=target_files,
            max_tokens=8000,
            include_related=True,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating code fixes...", total=None)

            # Create requirements from feedback interpretation
            fix_requirements = [
                interpretation.what_went_wrong,
                interpretation.how_to_fix,
            ]

            prompt = format_code_generation_prompt(
                requirements=fix_requirements,
                acceptance_criteria=["Address all review feedback", "Pass all CI checks"],
                constraints=["Maintain existing functionality", "Follow code conventions"],
                codebase_context=codebase_context,
            )

            code_gen: CodeGeneration = call_llm_structured(
                prompt=prompt,
                response_model=CodeGeneration,
                config=config,
            )
            progress.update(task, completed=True)

        total_changes = len(code_gen.files_to_modify) + len(code_gen.files_to_create)
        print_success(f"Generated fixes for {total_changes} files")

        # Step 4: Validate and apply changes
        all_changes = {**code_gen.files_to_modify, **code_gen.files_to_create}

        print_info("Validating changes...")
        for file_path, content in all_changes.items():
            if file_path.endswith(".py"):
                is_valid, error = code_modifier.validate_python_syntax(file_path, content)
                if not is_valid:
                    print_error(f"Syntax validation failed: {error}")
                    sys.exit(1)

        print_success("Validation passed")

        # Checkout PR branch
        print_info(f"Checking out branch: {pr.head_branch}")
        code_modifier.repo.git.checkout(pr.head_branch)

        # Apply changes
        print_info(f"Applying fixes to {len(all_changes)} files...")
        success, messages = code_modifier.apply_changes_with_validation(
            all_changes, repo_path_str
        )

        if not success:
            print_error("Failed to apply changes:")
            for msg in messages:
                console.print(f"  - {msg}")
            sys.exit(1)

        print_success("Applied fixes")

        # Step 5: Commit and push
        print_info("Creating commit...")
        commit_message = f"""fix: Address review feedback for #{issue_number}

Iteration {next_iteration}: Applied fixes based on reviewer feedback

Fixes:
{interpretation.how_to_fix}

Related to PR #{pr_number}
"""

        commit_sha = code_modifier.create_commit(
            message=commit_message,
            files=list(all_changes.keys()),
        )
        print_success(f"Created commit: {commit_sha[:8]}")

        print_info("Pushing changes...")
        code_modifier.push_branch(pr.head_branch)
        print_success("Pushed to remote")

        # Step 6: Update labels
        print_info("Updating PR labels...")
        old_label = f"iteration-{current_iteration}"
        new_label = f"iteration-{next_iteration}"
        github_client.update_issue_labels(
            issue_number=pr_number,
            labels_to_add=[new_label],
            labels_to_remove=[old_label],
        )

        # Add comment
        comment = f"""🔧 **Applied Reviewer Feedback (Iteration {next_iteration})**

**Analysis:** {interpretation.what_went_wrong}

**Fixes Applied:** {interpretation.how_to_fix}

**Commit:** {commit_sha[:8]}

Ready for re-review.
"""
        github_client.add_issue_comment(pr_number, comment)

        # Update state
        state_manager.update_state(
            issue_number=issue_number,
            pr_number=pr_number,
            iteration=next_iteration,
            status="in_progress",
        )

        print_header(f"✅ Successfully applied feedback to PR #{pr_number}")
        console.print(f"\n[bold]Commit:[/bold] {commit_sha[:8]}")
        console.print(f"[bold]Iteration:[/bold] {next_iteration}/{config.max_iterations}\n")

        logger.info(f"Successfully applied feedback for PR #{pr_number}")

    except KeyboardInterrupt:
        print_error("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Failed to apply feedback: {str(e)}")
        logger.exception(f"Error applying feedback for PR #{pr_number}")
        sys.exit(1)


@app.command()
def init(
    repo_path: Optional[str] = typer.Option(
        None, "--repo", "-r", help="Path to repository (defaults to current directory)"
    ),
) -> None:
    """Initialize .agent-state directory and validate configuration.

    This command will:
    1. Create .agent-state directory if it doesn't exist
    2. Validate configuration (API keys, repo access, etc.)
    3. Verify GitHub authentication
    4. Check LLM provider connection
    """
    print_header("Initializing Code Agent")

    try:
        # Load configuration
        config = load_config()
        setup_rich_logging(config.log_level)

        repo_path_str = repo_path or get_repo_path()

        # Step 1: Create state directory
        print_info("Creating state directory...")
        state_manager = StateManager()
        print_success(f"State directory ready: {state_manager.state_dir}")

        # Step 2: Validate repository
        print_info("Validating repository...")
        try:
            code_modifier = CodeModifier(repo_path_str)
            print_success(f"Repository: {repo_path_str}")
            print_success(f"Current branch: {code_modifier.get_current_branch()}")
        except Exception as e:
            print_error(f"Invalid repository: {str(e)}")
            sys.exit(1)

        # Step 3: Validate GitHub authentication
        print_info("Validating GitHub authentication...")
        try:
            github_client = GitHubClient(config)
            # Try to fetch repo info
            repo_info = github_client.repo
            print_success(f"GitHub: Connected to {config.github_repository}")
            print_success(f"Repository: {repo_info.name} ({repo_info.default_branch})")
        except Exception as e:
            print_error(f"GitHub authentication failed: {str(e)}")
            sys.exit(1)

        # Step 4: Validate LLM provider
        print_info(f"Validating LLM provider ({config.llm_provider})...")
        try:
            from src.code_agent.llm_client import create_llm_client

            llm_client = create_llm_client(config)
            print_success(f"LLM: {config.llm_provider} configured")

            if config.llm_provider == "openai":
                print_success(f"Model: {config.openai_model}")
            elif config.llm_provider == "yandex":
                print_success(f"Model: {config.yandex_model}")

        except Exception as e:
            print_error(f"LLM provider validation failed: {str(e)}")
            sys.exit(1)

        # Step 5: Display configuration summary
        console.print("\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Repository: {config.github_repository}")
        console.print(f"  Default Branch: {config.default_branch}")
        console.print(f"  Max Iterations: {config.max_iterations}")
        console.print(f"  LLM Provider: {config.llm_provider}")
        console.print(f"  Log Level: {config.log_level}")

        print_header("✅ Code Agent initialized successfully")

        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Create a GitHub issue with your requirements")
        console.print("  2. Run: [cyan]code-agent process-issue <issue_number>[/cyan]")
        console.print("  3. Review the generated PR")
        console.print("  4. CI/CD will automatically analyze the PR")
        console.print("  5. If needed, run: [cyan]code-agent apply-feedback <pr_number>[/cyan]\n")

    except KeyboardInterrupt:
        print_error("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Initialization failed: {str(e)}")
        logger.exception("Error during initialization")
        sys.exit(1)


@app.command()
def status(
    issue_number: Optional[int] = typer.Argument(None, help="Issue number to check status for"),
) -> None:
    """Show status of agent processing for an issue or all issues."""
    print_header("Agent Status")

    try:
        state_manager = StateManager()

        if issue_number:
            # Show status for specific issue
            state = state_manager.load_state(issue_number)
            if not state:
                print_info(f"No state found for issue #{issue_number}")
                return

            console.print(f"\n[bold]Issue #{state.issue_number}[/bold]")
            console.print(f"  Status: {state.status}")
            console.print(f"  Iteration: {state.iteration}")
            if state.pr_number:
                console.print(f"  PR: #{state.pr_number}")
            console.print(f"  Started: {state.started_at.strftime('%Y-%m-%d %H:%M')}")
            console.print(f"  Updated: {state.updated_at.strftime('%Y-%m-%d %H:%M')}")

            if state.errors:
                console.print(f"\n  [bold]Errors ({len(state.errors)}):[/bold]")
                for error in state.errors[-3:]:  # Show last 3
                    console.print(f"    - {error[:100]}...")

        else:
            # Show status for all issues
            issue_numbers = state_manager.list_all_states()

            if not issue_numbers:
                print_info("No agent states found")
                return

            console.print(f"\n[bold]Found {len(issue_numbers)} tracked issues[/bold]\n")

            for issue_num in issue_numbers:
                state = state_manager.load_state(issue_num)
                if state:
                    status_color = {
                        "pending": "yellow",
                        "in_progress": "blue",
                        "completed": "green",
                        "failed": "red",
                        "stuck": "red",
                    }.get(state.status, "white")

                    console.print(
                        f"  Issue #{state.issue_number}: "
                        f"[{status_color}]{state.status}[/{status_color}] "
                        f"(iteration {state.iteration})"
                    )

    except Exception as e:
        print_error(f"Failed to retrieve status: {str(e)}")
        sys.exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    from importlib.metadata import version as get_version

    try:
        pkg_version = get_version("coding-agents")
    except Exception:
        pkg_version = "unknown"

    console.print(f"\n[bold]Code Agent[/bold] version {pkg_version}")
    console.print("Automated SDLC System with GitHub Integration\n")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
