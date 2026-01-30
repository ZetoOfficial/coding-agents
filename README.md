# Coding Agents - Automated SDLC System

An AI-powered Software Development Lifecycle (SDLC) automation system that runs entirely within GitHub Actions. The system consists of two agents: a **Code Agent** that implements features from GitHub issues, and a **Reviewer Agent** that analyzes pull requests and provides feedback.

## Features

- **Automated Issue Implementation**: Converts GitHub issues into working code and pull requests
- **AI-Powered Code Review**: Comprehensive PR analysis with inline comments
- **Iterative Refinement**: Automatically applies reviewer feedback up to 5 iterations
- **CI/CD Integration**: Runs quality checks (linting, tests, security) before review
- **Multiple LLM Support**: Works with OpenAI GPT-4o-mini or YandexGPT
- **Stuck Loop Detection**: Prevents infinite iteration cycles
- **Security Focused**: Built-in security checks and secret protection
- **Docker Support**: Containerized for local development and testing

## Architecture

```
┌─────────────────┐
│  GitHub Issue   │
│ (label: agent:  │
│   implement)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Code Agent Workflow           │
│                                 │
│  1. Analyze Issue → LLM         │
│  2. Analyze Codebase            │
│  3. Generate Code → LLM         │
│  4. Validate (syntax, security) │
│  5. Create Branch & Commit      │
│  6. Push & Create PR            │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   CI Pipeline (PR opened)       │
│                                 │
│  • Ruff (linting)               │
│  • Black (formatting)           │
│  • MyPy (type checking)         │
│  • Pytest (tests + coverage)    │
│  • Bandit (security scan)       │
│  • pip-audit (dependencies)     │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Reviewer Agent Workflow       │
│                                 │
│  1. Parse CI Artifacts          │
│  2. Analyze Diff → LLM          │
│  3. Check Requirements          │
│  4. Generate Review             │
│  5. Post to PR (inline comments)│
└────────┬────────────────────────┘
         │
         ▼
    ┌────┴────┐
    │Approve? │
    └─┬────┬──┘
      │    │
     Yes   No
      │    │
      │    ▼
      │  ┌─────────────────────────┐
      │  │  Feedback Loop Workflow │
      │  │                         │
      │  │ 1. Parse Feedback → LLM │
      │  │ 2. Generate Fixes       │
      │  │ 3. Apply & Push         │
      │  │ 4. Increment Iteration  │
      │  └───────┬─────────────────┘
      │          │
      │          └──────┐ (if iter < 5)
      │                 │
      ▼                 ▼
   Merge          Trigger CI again
```

## Quick Start

### Prerequisites

- Python 3.11+
- Git
- GitHub account with repository access
- OpenAI API key or YandexGPT API key

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/your-org/coding-agents.git
cd coding-agents
```

2. **Install dependencies**:
```bash
# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env and add your credentials
```

Required environment variables:
- `GITHUB_TOKEN`: GitHub personal access token
- `GITHUB_REPOSITORY`: Repository in format `owner/repo`
- `OPENAI_API_KEY` or `YANDEX_API_KEY`: LLM provider API key

### Local Usage

**Initialize the agent**:
```bash
uv run python -m src.code_agent.cli init
```

**Process an issue**:
```bash
uv run python -m src.code_agent.cli process-issue --issue-number 123
```

**Review a PR** (requires CI artifacts):
```bash
uv run python -m src.reviewer_agent.reviewer review \
  --pr-number 456 \
  --artifact-dir ./ci-reports/ \
  --output review.json \
  --post-review
```

**Check agent status**:
```bash
uv run python -m src.code_agent.cli status --issue-number 123
```

### Docker Usage

**Build the image**:
```bash
docker-compose build
```

**Run Code Agent**:
```bash
docker-compose run --rm agent-dev process-issue --issue-number 123
```

**Run Reviewer Agent**:
```bash
docker-compose run --rm reviewer-dev review --pr-number 456 --artifact-dir /app/ci-reports
```

**Interactive shell**:
```bash
docker-compose run --rm agent-dev bash
```

## GitHub Actions Setup

### 1. Add Secrets to Repository

Go to repository **Settings → Secrets and variables → Actions** and add:

- `OPENAI_API_KEY` or `YANDEX_API_KEY`: Your LLM provider API key
- `YANDEX_FOLDER_ID` (if using YandexGPT): Your Yandex Cloud folder ID

### 2. Add Variables (Optional)

Go to **Settings → Secrets and variables → Actions → Variables** tab:

- `LLM_PROVIDER`: `openai` (default) or `yandex`
- `MAX_ITERATIONS`: Maximum iteration count (default: `5`)

### 3. Workflows Are Automatically Active

The workflows in `.github/workflows/` will trigger automatically:

- **code-agent.yml**: Triggers when issue is labeled `agent:implement`
- **reviewer-agent.yml**: Triggers on PR open/update
- **feedback-loop.yml**: Triggers when reviewer requests changes

### 4. Usage

**To implement an issue**:
1. Create a GitHub issue with clear requirements
2. Add the label `agent:implement`
3. Wait for the Code Agent to create a PR (~5 minutes)

**The system will then**:
1. Create a PR with the implementation
2. Run CI checks (linting, tests, security)
3. Reviewer Agent analyzes and posts review
4. If changes needed, Feedback Loop applies fixes
5. Repeat up to 5 iterations or until approved

## Configuration

### Environment Variables

See `.env.example` for all available options.

**Core settings**:
- `GITHUB_TOKEN`: GitHub authentication
- `GITHUB_REPOSITORY`: Target repository
- `LLM_PROVIDER`: `openai` or `yandex`
- `MAX_ITERATIONS`: Iteration limit (1-10)
- `DEFAULT_BRANCH`: Base branch for PRs
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`

**OpenAI settings**:
- `OPENAI_API_KEY`: API key
- `OPENAI_MODEL`: Model name (default: `gpt-4o-mini`)

**YandexGPT settings**:
- `YANDEX_API_KEY`: API key
- `YANDEX_MODEL`: Model URI
- `YANDEX_FOLDER_ID`: Yandex Cloud folder ID

### Agent Behavior

**Iteration Control**:
- Maximum iterations: 5 (configurable)
- Stuck detection: Triggers if same errors repeat 3 times
- Manual override: Remove `agent:max-iterations` label to resume

**Security**:
- Syntax validation before every commit
- Security pattern detection (secrets, SQL injection, eval/exec)
- Dependency vulnerability scanning
- Secret filtering in logs

## Project Structure

```
coding-agents/
├── src/
│   ├── common/                    # Shared utilities
│   │   ├── config.py             # Configuration management
│   │   └── models.py             # Pydantic data models
│   ├── code_agent/               # Code Agent
│   │   ├── cli.py               # CLI orchestration
│   │   ├── github_client.py     # GitHub API wrapper
│   │   ├── llm_client.py        # LLM provider interface
│   │   ├── prompts.py           # LLM prompt templates
│   │   ├── state_manager.py     # State tracking
│   │   ├── code_analyzer.py     # Codebase analysis
│   │   └── code_modifier.py     # Code changes & git ops
│   └── reviewer_agent/           # Reviewer Agent
│       ├── reviewer.py          # Main reviewer CLI
│       ├── ci_analyzer.py       # CI artifact parser
│       └── analysis_engine.py   # Diff analysis
├── .github/workflows/            # GitHub Actions workflows
│   ├── code-agent.yml           # Issue → PR automation
│   ├── reviewer-agent.yml       # CI + AI review
│   └── feedback-loop.yml        # Feedback application
├── tests/                        # Test suite
├── .agent-state/                 # Agent iteration state (gitignored)
├── pyproject.toml               # Python dependencies
├── Dockerfile                    # Container image
├── docker-compose.yml           # Local development
└── README.md                    # This file
```

## How It Works

### Code Agent Flow

1. **Issue Analysis**: Fetches issue from GitHub, uses LLM to extract requirements, acceptance criteria, and target files
2. **Codebase Analysis**: Scans repository structure, identifies relevant files, extracts coding conventions
3. **Code Generation**: Uses LLM with repository context to generate complete file contents
4. **Validation**: Checks Python syntax, security patterns, and file references
5. **Git Operations**: Creates branch, applies changes with backup/rollback, commits with descriptive message
6. **PR Creation**: Creates pull request, adds labels (`agent:iteration-1`, `agent:in-progress`), links to issue

### Reviewer Agent Flow

1. **CI Artifact Parsing**: Reads JSON reports from ruff, pytest, mypy, bandit, pip-audit
2. **Failure Categorization**: Groups failures by type (tests, lint, types, security, dependencies)
3. **Diff Analysis**: Uses LLM to analyze code changes against original requirements
4. **Requirement Checking**: Verifies all requirements from issue are fulfilled
5. **Review Generation**: Creates comprehensive review with:
   - Overall summary and quality score
   - Blocking vs non-blocking issues
   - Inline comments mapped to specific lines
   - CI results summary
6. **Idempotent Posting**: Dismisses old bot reviews, posts new review, updates summary comment

### Feedback Loop Flow

1. **Trigger**: Activated when Reviewer Agent posts `REQUEST_CHANGES` review
2. **Iteration Check**: Verifies current iteration < 5, exits if limit reached
3. **Feedback Parsing**: Extracts all review comments and CI failures
4. **Fix Generation**: Uses LLM to interpret feedback and generate targeted fixes
5. **Application**: Applies fixes with same validation as initial implementation
6. **Label Update**: Increments iteration label, updates PR status

## Iteration Control & Safety

### Maximum Iterations

The system enforces a hard limit of 5 iterations to prevent infinite loops:

- Each iteration increments the `agent:iteration-N` label
- At iteration 5, the system posts a warning and adds `agent:max-iterations` label
- Manual intervention required to continue

### Stuck Detection

The system detects when it's stuck in a loop:

- Monitors last 3 review histories for similar errors
- Uses string similarity (70% threshold) to detect repeating patterns
- Adds `agent:stuck` label and exits gracefully

### Manual Override

To resume after max iterations or stuck:
1. Review the PR and issue manually
2. Make necessary changes or fix root cause
3. Remove `agent:max-iterations` or `agent:stuck` label
4. Comment `/agent implement` to restart

## Security Features

### Secret Protection

- Secrets never logged or exposed in outputs
- Custom log filter redacts tokens, API keys, passwords
- Pydantic `SecretStr` for sensitive configuration

### Code Security Checks

The system detects and blocks:
- Hardcoded API keys, tokens, passwords
- SQL injection patterns
- Use of `eval()` / `exec()`
- Subprocess with `shell=True`
- Unsafe YAML/pickle usage
- AWS credentials in code
- Private keys (SSH/RSA)

### Repository Safety

- All file operations validate paths are within repository
- Backup/rollback for all code changes
- Syntax validation before every commit
- Fork protection: AI reviewer only runs on same-repo PRs

## Troubleshooting

### Code Agent Issues

**Issue: "Max iteration limit reached"**
- Review the PR and issue manually
- Check if requirements are unclear or contradictory
- Remove `agent:max-iterations` label to resume

**Issue: "Syntax validation failed"**
- Check LLM generated valid Python
- Review the issue requirements for ambiguity
- May need to simplify requirements

**Issue: "Security check failed"**
- Review generated code for security issues
- Check if hardcoded credentials were added
- Verify no dangerous patterns (eval, shell=True)

### Reviewer Agent Issues

**Issue: "CI artifacts not found"**
- Ensure CI workflows completed before reviewer runs
- Check artifact upload/download steps in workflows
- Verify artifact retention hasn't expired

**Issue: "Review not posted"**
- Check GitHub token has `pull_requests: write` permission
- Verify PR is from same repo (not a fork)
- Check workflow logs for API errors

### General Issues

**Issue: "LLM API errors"**
- Verify API key is correct and has credits
- Check rate limiting (default: 10 requests/minute)
- Review LLM provider status page

**Issue: "GitHub API rate limit"**
- Wait for rate limit to reset (1 hour)
- Use `GITHUB_TOKEN` from Actions (5000 req/hour)
- Avoid rapid iteration triggers

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_github_client.py -v
```

### Code Quality

```bash
# Linting
uv run ruff check src/

# Formatting
uv run black src/

# Type checking
uv run mypy src/

# Security scan
uv run bandit -r src/
```

### Adding New Features

1. Update relevant module in `src/code_agent/` or `src/reviewer_agent/`
2. Add tests in `tests/`
3. Update documentation
4. Run quality checks
5. Test locally with Docker
6. Create PR for review

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all quality checks pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [OpenAI GPT-4o-mini](https://openai.com/) and [YandexGPT](https://cloud.yandex.com/en/services/yandexgpt)
- Uses [PyGithub](https://github.com/PyGithub/PyGithub) for GitHub API
- Powered by [uv](https://github.com/astral-sh/uv) for fast Python package management
