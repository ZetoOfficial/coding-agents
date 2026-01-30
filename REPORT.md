# Coding Agents - Полный обзор проекта

## Содержание

- [Введение](#введение)
- [Архитектура и компоненты](#архитектура-и-компоненты)
- [Работа с GitHub Issues](#работа-с-github-issues)
- [Работа с Pull Requests](#работа-с-pull-requests)
- [Итеративный процесс улучшения](#итеративный-процесс-улучшения)
- [Примеры использования](#примеры-использования)
- [Лучшие практики](#лучшие-практики)
- [Расширенные возможности](#расширенные-возможности)
- [Ограничения и обход проблем](#ограничения-и-обход-проблем)

## Введение

**Coding Agents** — это система автоматизации полного цикла разработки программного обеспечения (SDLC), построенная на базе AI и GitHub Actions. Проект решает реальные задачи разработчиков:

- **Автоматизация рутинных задач**: Система берет на себя простые реализации features, багфиксы, рефакторинг
- **Ускорение code review**: AI-агент анализирует PR и дает детальные комментарии быстрее, чем человек
- **Постоянное качество кода**: Каждый PR проходит через унифицированный pipeline проверок
- **Снижение нагрузки на команду**: Автоматические итерации по фидбеку освобождают время разработчиков

### Ключевые преимущества

1. **Полная автоматизация**: От issue до merged PR — без ручного вмешательства
2. **Встроенное качество**: Линтинг, тесты, безопасность, type checking
3. **Адаптивность**: Система учится на вашем codebase и coding conventions
4. **Прозрачность**: Каждое действие логируется, каждое решение объясняется
5. **Безопасность**: Множество проверок на security issues и secrets protection

### Основные компоненты

Система состоит из двух интеллектуальных агентов:

1. **Code Agent** — превращает GitHub issues в рабочий код
2. **Reviewer Agent** — анализирует pull requests и дает feedback

Оба агента работают через GitHub Actions и используют LLM (Large Language Models) для принятия решений.

## Архитектура и компоненты

### Общая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Repository                        │
│                                                             │
│  ┌───────────┐      ┌──────────────┐      ┌─────────────┐ │
│  │  Issues   │─────▶│ GitHub       │─────▶│ Pull        │ │
│  │           │      │ Actions      │      │ Requests    │ │
│  └───────────┘      └──────────────┘      └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                    │                     │
         ▼                    ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Code Agent    │  │  CI Pipeline    │  │ Reviewer Agent  │
│                 │  │                 │  │                 │
│ • Requirement   │  │ • Ruff linting  │  │ • CI analysis   │
│   analysis      │  │ • Black format  │  │ • Diff review   │
│ • Code gen      │  │ • MyPy types    │  │ • Inline        │
│ • Validation    │  │ • Pytest tests  │  │   comments      │
│ • Git ops       │  │ • Bandit sec    │  │ • Approval      │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                     │
         │                    ▼                     │
         │           ┌─────────────────┐            │
         │           │  CI Artifacts   │            │
         │           │  (JSON reports) │            │
         │           └────────┬────────┘            │
         │                    │                     │
         └────────────────────┴─────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Feedback Loop   │
                    │  (max 5 iters)   │
                    └──────────────────┘
```

### Code Agent - детальная архитектура

```
Input: GitHub Issue #123
  ↓
┌────────────────────────────────────────────────────┐
│ 1. REQUIREMENT ANALYSIS (LLM)                      │
│    • Extract requirements                          │
│    • Identify acceptance criteria                  │
│    • Determine target files                        │
│    • Classify task type (feature/bug/refactor)    │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 2. CODEBASE ANALYSIS (Static)                      │
│    • Scan directory structure                      │
│    • Read related files                            │
│    • Extract coding conventions                    │
│    • Build dependency graph                        │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 3. CODE GENERATION (LLM)                           │
│    • Generate complete file contents               │
│    • Follow existing patterns                      │
│    • Include imports and dependencies              │
│    • Add type hints and docstrings                 │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 4. VALIDATION PIPELINE                             │
│    ├─ Syntax check (AST compilation)              │
│    ├─ Security scan (8+ patterns)                 │
│    ├─ File reference check                        │
│    └─ Backup creation                             │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 5. GIT OPERATIONS                                  │
│    • Create branch: agent/issue-123                │
│    • Apply changes with rollback support          │
│    • Commit with descriptive message              │
│    • Push to remote                               │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 6. PR CREATION                                     │
│    • Create pull request                          │
│    • Link to original issue                       │
│    • Add labels: agent:iteration-1                │
│    • Post summary comment                         │
└────────────────────┬───────────────────────────────┘
                     ↓
Output: Pull Request #456
```

### Reviewer Agent - детальная архитектура

```
Input: Pull Request #456 (opened/updated)
  ↓
┌────────────────────────────────────────────────────┐
│ CI PIPELINE (parallel jobs)                        │
│                                                    │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│ │ quality-     │  │ test-and-    │  │ Security │ │
│ │ checks       │  │ security     │  │ Scan     │ │
│ │              │  │              │  │          │ │
│ │ • ruff       │  │ • pytest     │  │ • bandit │ │
│ │ • black      │  │ • coverage   │  │ • pip-   │ │
│ │ • mypy       │  │              │  │   audit  │ │
│ └──────┬───────┘  └──────┬───────┘  └────┬─────┘ │
│        │                 │                │       │
│        └─────────────────┴────────────────┘       │
│                          ↓                        │
│                 ┌────────────────┐                │
│                 │ Upload         │                │
│                 │ Artifacts      │                │
│                 │ (JSON)         │                │
│                 └────────┬───────┘                │
└──────────────────────────┼────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────┐
│ 1. CI ARTIFACT PARSING                             │
│    • Download all artifacts                        │
│    • Parse JSON reports                            │
│    • Categorize failures                           │
│    • Extract error messages                        │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 2. DIFF ANALYSIS (LLM)                             │
│    • Fetch PR diff                                 │
│    • Analyze changes per file                      │
│    • Check against requirements                    │
│    • Identify potential issues                     │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 3. REVIEW GENERATION (LLM)                         │
│    • Overall summary                               │
│    • Quality score (0-100)                         │
│    • Blocking vs non-blocking issues               │
│    • Inline comments with line numbers            │
│    • Recommendations                               │
└────────────────────┬───────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────┐
│ 4. REVIEW POSTING (Idempotent)                     │
│    • Dismiss old bot reviews                       │
│    • Post new review (APPROVE/REQUEST_CHANGES)     │
│    • Create inline comments                        │
│    • Update summary comment (with HTML marker)     │
└────────────────────┬───────────────────────────────┘
                     ↓
Output: Review posted, decision made (approve/changes)
```

### Модули и их взаимодействие

#### Common (Shared utilities)

```python
src/common/
├── config.py           # Централизованная конфигурация
│   └── AgentConfig     # Pydantic модель с секретами и валидацией
├── models.py           # Все Pydantic модели системы
│   ├── Issue           # Представление GitHub issue
│   ├── PullRequest     # Представление PR
│   ├── RequirementAnalysis  # Результат анализа требований
│   ├── CodeChanges     # Изменения кода
│   └── ReviewOutput    # Результат review
└── state_manager.py    # Управление состоянием итераций
    └── IssueState      # JSON-based state в .agent-state/
```

#### Code Agent

```python
src/code_agent/
├── cli.py              # Typer CLI - точка входа
│   ├── init()         # Проверка конфигурации
│   ├── process_issue()  # Обработка issue
│   ├── apply_feedback() # Применение фидбека
│   └── status()       # Статус issue
├── orchestrator.py     # Основная логика агента
│   └── CodeAgentOrchestrator
│       ├── process_issue_to_pr()
│       └── apply_reviewer_feedback()
├── github_client.py    # Обертка над PyGithub
│   └── GitHubClient
│       ├── get_issue()
│       ├── create_pull_request()
│       ├── post_comment()
│       └── add_labels()
├── llm_client.py       # Унифицированный LLM интерфейс
│   ├── call_llm_structured()  # OpenAI/YandexGPT
│   └── RateLimiter    # Sliding window rate limiting
├── prompts.py          # Централизованные промпты
│   ├── format_requirement_analysis_prompt()
│   ├── format_code_generation_prompt()
│   └── format_feedback_application_prompt()
├── code_analyzer.py    # Анализ codebase
│   └── CodebaseAnalyzer
│       ├── analyze_structure()
│       └── extract_conventions()
└── code_modifier.py    # Git операции и валидация
    └── CodeModifier
        ├── apply_changes()
        ├── validate_security()
        └── commit_and_push()
```

#### Reviewer Agent

```python
src/reviewer_agent/
├── reviewer.py         # Typer CLI - точка входа
│   └── review()       # Основная команда review
├── orchestrator.py     # Основная логика reviewer
│   └── ReviewerOrchestrator
│       └── review_pull_request()
├── ci_analyzer.py      # Парсинг CI артефактов
│   └── CIAnalyzer
│       ├── parse_ruff()
│       ├── parse_pytest()
│       ├── parse_mypy()
│       └── parse_bandit()
└── analysis_engine.py  # LLM-based анализ diff
    └── AnalysisEngine
        ├── analyze_diff()
        └── generate_review()
```

## Работа с GitHub Issues

### Жизненный цикл Issue

```
┌──────────────────┐
│ Create Issue     │  Developer creates issue with clear requirements
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ Add label: agent:implement                           │
│ (manually or via comment: /agent implement)          │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ TRIGGER: code-agent.yml workflow                     │
│ • GitHub Actions starts                              │
│ • Installs dependencies (uv sync)                    │
│ • Runs: process-issue --issue-number <N>             │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ Code Agent Processing (~3-7 minutes)                 │
│ 1. Fetch issue from GitHub API                       │
│ 2. LLM analyzes requirements                         │
│ 3. Scan codebase for context                         │
│ 4. LLM generates code                                │
│ 5. Validate syntax and security                      │
│ 6. Create branch, commit, push                       │
│ 7. Create PR with link to issue                      │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ SUCCESS: PR created                                  │
│ • Comment posted to issue                            │
│ • Issue labeled: agent:in-progress                   │
│ • PR labeled: agent:iteration-1                      │
│ • PR description includes requirements               │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ FAILURE: Error occurred                              │
│ • Error message posted to issue                      │
│ • Label: agent:error                                 │
│ • Workflow logs available for debugging              │
└──────────────────────────────────────────────────────┘
```

### Формат Issue - лучшие практики

Для получения качественного результата issue должен содержать:

#### 1. Четкое описание задачи

```markdown
## Description
Need to add user authentication to the web application using JWT tokens.
```

#### 2. Требования (Requirements)

```markdown
## Requirements
- Users should be able to register with email and password
- Users should be able to log in and receive JWT token
- Token should expire after 24 hours
- Protected routes should verify token validity
- Use bcrypt for password hashing
```

#### 3. Критерии приемки (Acceptance Criteria)

```markdown
## Acceptance Criteria
- [ ] POST /api/register endpoint accepts email and password
- [ ] POST /api/login endpoint returns JWT token
- [ ] GET /api/profile requires valid token in Authorization header
- [ ] Invalid/expired tokens return 401 status
- [ ] Passwords are never stored in plain text
- [ ] All endpoints have proper error handling
```

#### 4. Технические детали (опционально)

```markdown
## Technical Details
- Use PyJWT library for token generation
- Store hashed passwords in `users` table
- Token secret should be in environment variable JWT_SECRET
- Add middleware to verify tokens on protected routes
```

#### 5. Файлы для изменения (опционально)

```markdown
## Files to Modify
- `src/auth/routes.py` - add authentication endpoints
- `src/auth/middleware.py` - create JWT verification middleware
- `src/models/user.py` - add User model
- `tests/test_auth.py` - add authentication tests
```

### Примеры хороших и плохих Issues

#### ❌ Плохой пример

```markdown
Title: Add auth

Description: We need authentication in the app.
```

**Проблемы:**
- Нет конкретики (какой тип аутентификации?)
- Нет требований
- Нет критериев приемки
- LLM будет гадать, что именно нужно

#### ✅ Хороший пример

```markdown
Title: Implement JWT authentication for API endpoints

## Description
Add JWT-based authentication to protect API endpoints. Users should be able
to register, log in, and access protected resources using bearer tokens.

## Requirements
1. User registration endpoint (email + password)
2. User login endpoint (returns JWT)
3. Token validation middleware for protected routes
4. Password hashing with bcrypt
5. Token expiration after 24 hours

## Acceptance Criteria
- [ ] POST /api/auth/register creates new user
- [ ] POST /api/auth/login returns valid JWT
- [ ] Protected routes verify token from Authorization header
- [ ] Expired/invalid tokens return 401 Unauthorized
- [ ] Passwords stored as bcrypt hashes
- [ ] Unit tests for all auth functions
- [ ] Integration tests for auth flow

## Technical Details
- Use PyJWT library for token generation/validation
- Store JWT_SECRET in environment variables
- Token payload should include: user_id, email, exp
- Add AuthMiddleware to verify tokens
- Use Python 3.11 type hints

## Files Expected to Change
- src/auth/__init__.py (new)
- src/auth/routes.py (new)
- src/auth/middleware.py (new)
- src/auth/utils.py (new)
- src/models/user.py (new)
- tests/test_auth.py (new)
- requirements.txt (add PyJWT, bcrypt)

## Security Considerations
- Never log passwords or tokens
- Use secure random for token generation
- Implement rate limiting on login attempts
- Validate email format
- Enforce password strength requirements
```

### Управление Issues через labels

Система использует labels для отслеживания состояния:

| Label | Значение | Когда добавляется |
|-------|----------|-------------------|
| `agent:implement` | Триггер для Code Agent | Вручную или через комментарий `/agent implement` |
| `agent:in-progress` | Агент работает над issue | Code Agent начал обработку |
| `agent:iteration-N` | Текущая итерация (1-5) | При создании/обновлении PR |
| `agent:max-iterations` | Достигнут лимит итераций | После 5 неудачных попыток |
| `agent:stuck` | Система зациклилась | Обнаружены повторяющиеся ошибки |
| `agent:error` | Произошла ошибка | При любой критической ошибке |

### Команды через комментарии

Вместо добавления labels можно использовать комментарии:

```markdown
/agent implement
```

Это автоматически:
1. Добавит label `agent:implement`
2. Запустит workflow `code-agent.yml`

### Проверка статуса Issue

Локально можно проверить статус:

```bash
uv run python -m src.code_agent.cli status --issue-number 123
```

Вывод покажет:
- Текущее состояние (pending/in-progress/completed/stuck)
- Количество итераций
- Связанные PR
- Последние ошибки (если есть)

## Работа с Pull Requests

### Жизненный цикл Pull Request

```
┌──────────────────────────────────────────────────────┐
│ PR Created (by Code Agent or manually)               │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ TRIGGER: reviewer-agent.yml workflow                 │
│ (on: pull_request types: [opened, synchronize])     │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ JOB 1: quality-checks (parallel)                     │
│ • ruff check --output-format=json                    │
│ • black --check --diff                               │
│ • mypy --output=json                                 │
│ Upload: quality-report.json                          │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ JOB 2: test-and-security (parallel)                  │
│ • pytest --cov --json-report                         │
│ • bandit -r src/ -f json                             │
│ • pip-audit --format=json                            │
│ Upload: test-report.json, security-report.json       │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ JOB 3: ai-review (depends on jobs 1 & 2)             │
│ • Download all artifacts                             │
│ • Run: reviewer review --pr-number <N> --post-review │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ Reviewer Agent Processing (~2-5 minutes)             │
│ 1. Parse CI artifacts (JSON reports)                 │
│ 2. Fetch PR diff from GitHub                         │
│ 3. LLM analyzes changes vs requirements              │
│ 4. Generate review with inline comments              │
│ 5. Calculate quality score                           │
│ 6. Decide: APPROVE or REQUEST_CHANGES                │
└────────┬─────────────────────────────────────────────┘
         │
         ├─────────────────┬────────────────────────────┐
         │                 │                            │
         ▼                 ▼                            ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ APPROVE     │  │ REQUEST_CHANGES  │  │ COMMENT (info only)  │
│             │  │                  │  │                      │
│ • Quality   │  │ • CI failures    │  │ • Minor suggestions  │
│   score >80 │  │ • Logic issues   │  │ • Non-blocking       │
│ • No        │  │ • Security       │  │                      │
│   blocking  │  │   issues         │  │                      │
│   issues    │  │ • Blocking       │  │                      │
└─────┬───────┘  └────────┬─────────┘  └────────┬─────────────┘
      │                   │                      │
      │                   │                      │
      ▼                   ▼                      ▼
┌──────────┐      ┌────────────────┐      ┌────────────┐
│ Ready to │      │ TRIGGER:       │      │ Review and │
│ merge    │      │ feedback-loop  │      │ merge      │
│ (manual) │      │ .yml           │      │ manually   │
└──────────┘      └────────┬───────┘      └────────────┘
                           │
                           ▼
                  (See Feedback Loop section)
```

### CI Pipeline - детальное описание

#### Job 1: quality-checks

```yaml
steps:
  - name: Ruff Linting
    run: |
      uv run ruff check src/ \
        --output-format=json \
        > ruff-report.json || true

  - name: Black Formatting
    run: |
      uv run black src/ --check --diff \
        > black-report.txt || true

  - name: MyPy Type Checking
    run: |
      uv run mypy src/ \
        --output=json \
        > mypy-report.json || true

  - name: Upload Quality Report
    uses: actions/upload-artifact@v3
    with:
      name: quality-report
      path: |
        ruff-report.json
        black-report.txt
        mypy-report.json
```

**Что проверяется:**

- **Ruff**: Linting (PEP8, imports, naming, security patterns)
- **Black**: Code formatting consistency
- **MyPy**: Type hints correctness

**Формат артефактов:**

```json
// ruff-report.json
[
  {
    "type": "error",
    "message": "Undefined name `foo`",
    "location": {
      "file": "src/main.py",
      "row": 42,
      "column": 10
    },
    "code": "F821"
  }
]

// mypy-report.json
[
  {
    "file": "src/main.py",
    "line": 42,
    "column": 10,
    "severity": "error",
    "message": "Argument 1 has incompatible type \"str\"; expected \"int\""
  }
]
```

#### Job 2: test-and-security

```yaml
steps:
  - name: Run Tests
    run: |
      uv run pytest tests/ \
        --cov=src \
        --cov-report=json \
        --json-report \
        --json-report-file=pytest-report.json || true

  - name: Security Scan (Bandit)
    run: |
      uv run bandit -r src/ \
        -f json \
        -o bandit-report.json || true

  - name: Dependency Audit
    run: |
      uv run pip-audit \
        --format=json \
        > pip-audit-report.json || true

  - name: Upload Test & Security Reports
    uses: actions/upload-artifact@v3
    with:
      name: test-security-report
      path: |
        pytest-report.json
        coverage.json
        bandit-report.json
        pip-audit-report.json
```

**Что проверяется:**

- **Pytest**: Unit/integration tests, coverage
- **Bandit**: Security vulnerabilities (hardcoded secrets, SQL injection, etc.)
- **pip-audit**: Known vulnerabilities in dependencies

**Формат артефактов:**

```json
// pytest-report.json
{
  "tests": [
    {
      "nodeid": "tests/test_auth.py::test_login_success",
      "outcome": "passed",
      "duration": 0.123
    },
    {
      "nodeid": "tests/test_auth.py::test_login_invalid",
      "outcome": "failed",
      "call": {
        "longrepr": "AssertionError: Expected 401, got 200"
      }
    }
  ],
  "summary": {
    "passed": 45,
    "failed": 2,
    "total": 47
  }
}

// bandit-report.json
{
  "results": [
    {
      "filename": "src/utils.py",
      "line_number": 15,
      "issue_severity": "HIGH",
      "issue_confidence": "HIGH",
      "issue_text": "Use of eval() is dangerous",
      "test_id": "B307"
    }
  ]
}
```

#### Job 3: ai-review

```yaml
steps:
  - name: Download CI Artifacts
    uses: actions/download-artifact@v3
    with:
      path: ci-reports/

  - name: Run AI Review
    run: |
      uv run python -m src.reviewer_agent.reviewer review \
        --pr-number ${{ github.event.pull_request.number }} \
        --artifact-dir ci-reports/ \
        --output review.json \
        --post-review
    env:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

**Что происходит:**

1. Скачиваются все CI артефакты
2. Reviewer Agent:
   - Парсит JSON отчеты
   - Анализирует diff через LLM
   - Генерирует review
3. Постит review в GitHub с inline комментариями

### Структура AI Review

Review состоит из нескольких частей:

#### 1. Summary Comment

Постится как общий комментарий к PR:

```markdown
## 🤖 AI Code Review

**Overall Quality Score**: 72/100

### Summary
The implementation adds JWT authentication as requested. Code structure is good,
but there are some issues that need to be addressed before merging.

### Issues Found

#### 🔴 Blocking Issues (3)
1. **Security**: Hardcoded JWT secret in `src/auth/utils.py:15`
2. **Test Failure**: `test_auth.py::test_login_invalid` failed (401 expected, got 200)
3. **Type Error**: Missing type hint for `verify_token` return value

#### 🟡 Non-Blocking Issues (2)
1. **Code Quality**: `src/auth/routes.py:42` - line too long (120 chars, max 100)
2. **Coverage**: Auth middleware not covered by tests (0% coverage)

### CI Results
- ✅ Linting: 2 warnings (non-blocking)
- ❌ Tests: 2/47 failed
- ❌ Type Checking: 1 error
- ❌ Security: 1 high-severity issue
- ✅ Dependencies: No vulnerabilities

### Recommendations
1. Move JWT_SECRET to environment variables
2. Fix failed test in `test_auth.py`
3. Add type hints to all auth functions
4. Add tests for auth middleware

---
**Decision**: REQUEST_CHANGES

<!-- AGENT_REVIEW_ID:abc123 -->
```

#### 2. Inline Comments

Постятся как review comments к конкретным строкам:

```python
# src/auth/utils.py, line 15
JWT_SECRET = "my-secret-key-12345"  # ⚠️ Security issue

# AI Comment (posted to line 15):
# 🔴 BLOCKING: Hardcoded JWT secret detected
#
# Severity: HIGH
#
# **Issue**: JWT secret is hardcoded in the source code. This is a security
# vulnerability as anyone with access to the repository can see the secret.
#
# **Fix**: Move the secret to environment variables:
# ```python
# import os
# JWT_SECRET = os.environ.get('JWT_SECRET')
# if not JWT_SECRET:
#     raise ValueError('JWT_SECRET environment variable is required')
# ```
#
# **Reference**: OWASP A02:2021 – Cryptographic Failures
```

#### 3. Review Decision

GitHub review может иметь 3 статуса:

1. **APPROVE** (✅)
   - Quality score ≥ 80
   - Нет blocking issues
   - Все тесты проходят
   - Нет критичных security issues

2. **REQUEST_CHANGES** (❌)
   - Quality score < 80
   - Есть blocking issues
   - Тесты падают
   - Найдены security issues

3. **COMMENT** (💬)
   - Информационный review
   - Только рекомендации
   - Не блокирует merge

### Интерпретация CI результатов

Reviewer Agent анализирует CI артефакты и категоризирует проблемы:

| Категория | Blocking? | Примеры |
|-----------|-----------|---------|
| **Test Failures** | ✅ Да | Failed tests, coverage < 70% |
| **Security Issues (High/Medium)** | ✅ Да | Hardcoded secrets, SQL injection, eval() |
| **Security Issues (Low)** | ❌ Нет | Weak cryptography, insecure random |
| **Type Errors** | ✅ Да | MyPy errors |
| **Linting Errors** | ❌ Нет | PEP8 violations, naming issues |
| **Formatting Issues** | ❌ Нет | Black formatting |
| **Dependency Vulnerabilities (Critical/High)** | ✅ Да | CVEs in dependencies |
| **Dependency Vulnerabilities (Medium/Low)** | ❌ Нет | Minor CVEs with workarounds |

### Ручная работа с PR после review

#### Сценарий 1: APPROVE - готов к merge

```bash
# Option A: Merge через GitHub UI
# Click "Merge pull request" button

# Option B: Merge через gh CLI
gh pr merge 456 --squash --delete-branch
```

#### Сценарий 2: REQUEST_CHANGES - нужны исправления

**Вариант 1: Automatic feedback loop (рекомендуется)**

Система автоматически применит фидбек если:
- PR создан Code Agent
- Есть label `agent:iteration-N` где N < 5
- Review от бота (user: github-actions[bot])

**Вариант 2: Manual fixes**

```bash
# 1. Checkout PR branch
gh pr checkout 456

# 2. Make fixes based on review comments
# Edit files...

# 3. Run local checks
uv run ruff check src/
uv run pytest tests/

# 4. Commit and push
git add .
git commit -m "Fix: address review feedback"
git push

# 5. CI will run again, reviewer will re-analyze
```

#### Сценарий 3: COMMENT - информационный review

Review не блокирует merge, можно:
- Применить рекомендации и push
- Игнорировать и merge как есть
- Обсудить в комментариях

## Итеративный процесс улучшения

### Feedback Loop Workflow

```
┌──────────────────────────────────────────────────────┐
│ Reviewer posts REQUEST_CHANGES review                │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ TRIGGER: feedback-loop.yml workflow                  │
│ (on: pull_request_review types: [submitted])        │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ Check Conditions                                     │
│ • Review is REQUEST_CHANGES?                         │
│ • Review from github-actions[bot]?                   │
│ • PR has label agent:iteration-N where N < 5?        │
│ • PR not labeled agent:max-iterations or agent:stuck?│
└────────┬─────────────────────────────────────────────┘
         │
         ├──── Conditions not met ────> Exit (no action)
         │
         ▼ Conditions met
┌──────────────────────────────────────────────────────┐
│ Run: apply-feedback --pr-number <N>                  │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ Code Agent: Apply Feedback (~3-5 minutes)            │
│                                                      │
│ 1. Fetch PR and linked issue                         │
│ 2. Parse all review comments                         │
│ 3. Parse CI failure messages                         │
│ 4. LLM: Generate fixes                               │
│ 5. Validate fixes (syntax, security)                 │
│ 6. Commit and push to PR branch                      │
│ 7. Update iteration label (N → N+1)                  │
│ 8. Post feedback summary comment                     │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ TRIGGER: CI Pipeline again (PR updated)              │
│ • quality-checks                                     │
│ • test-and-security                                  │
│ • ai-review                                          │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ Reviewer posts new review                            │
│ → If still issues: loop again (up to 5 iterations)   │
│ → If approved: ready to merge                        │
│ → If max iterations: add agent:max-iterations label  │
│ → If stuck: add agent:stuck label                    │
└──────────────────────────────────────────────────────┘
```

### Ограничение итераций

Система предотвращает бесконечные циклы через:

#### 1. Maximum Iterations (5)

```python
# State stored in .agent-state/issue-123.json
{
  "issue_number": 123,
  "pr_number": 456,
  "current_iteration": 5,
  "max_iterations": 5,
  "status": "max_iterations_reached"
}
```

При достижении лимита:
- Добавляется label `agent:max-iterations`
- Постится комментарий с объяснением
- Workflow не запускается при следующих reviews
- Требуется ручное вмешательство

**Как продолжить после достижения лимита:**

```bash
# Option 1: Manual fix and remove label
# 1. Fix issues manually
# 2. Remove agent:max-iterations label
# 3. Comment: /agent implement

# Option 2: Increase limit (not recommended)
# Edit .github/workflows/code-agent.yml
env:
  MAX_ITERATIONS: 10  # Default: 5
```

#### 2. Stuck Detection

Система отслеживает последние 3 review:

```python
# .agent-state/issue-123.json
{
  "review_history": [
    {
      "iteration": 3,
      "issues": ["test_login failed", "hardcoded secret in utils.py"]
    },
    {
      "iteration": 4,
      "issues": ["test_login failed", "hardcoded secret in utils.py"]
    },
    {
      "iteration": 5,
      "issues": ["test_login failed", "hardcoded secret in utils.py"]
    }
  ],
  "stuck_detected": true,
  "stuck_reason": "Same issues repeated 3 times (70% similarity)"
}
```

Если 70%+ issues повторяются 3 раза подряд:
- Добавляется label `agent:stuck`
- Постится детальное объяснение проблемы
- Workflow останавливается
- Требуется анализ root cause

**Типичные причины "зацикливания":**

1. **Недостаточно информации в issue**
   - Fix: Уточнить requirements и acceptance criteria

2. **LLM не понимает ошибку**
   - Fix: Добавить technical details в issue

3. **Несовместимые требования**
   - Fix: Пересмотреть требования в issue

4. **Ошибка в тестах (ложное срабатывание)**
   - Fix: Исправить тесты вручную

5. **Проблема в окружении (CI)**
   - Fix: Проверить GitHub Actions, dependencies

### Стратегии применения feedback

Система использует разные стратегии в зависимости от типа feedback:

#### 1. CI Failures

```python
# Input: Parsed CI artifacts
{
  "test_failures": [
    {
      "test": "test_auth.py::test_login_invalid",
      "error": "AssertionError: Expected 401, got 200"
    }
  ],
  "lint_errors": [
    {
      "file": "src/auth/routes.py",
      "line": 42,
      "code": "E501",
      "message": "line too long (120 > 100 characters)"
    }
  ]
}

# Strategy:
# 1. Focus on test failures first (highest priority)
# 2. Fix lint errors second
# 3. Validate all fixes locally before pushing
```

#### 2. Review Comments

```python
# Input: Inline review comments
[
  {
    "file": "src/auth/utils.py",
    "line": 15,
    "body": "🔴 BLOCKING: Hardcoded JWT secret...",
    "severity": "BLOCKING"
  },
  {
    "file": "src/auth/routes.py",
    "line": 42,
    "body": "🟡 Consider using async/await here...",
    "severity": "NON_BLOCKING"
  }
]

# Strategy:
# 1. Address BLOCKING comments first
# 2. Group related comments (same file)
# 3. Apply fixes in order: security → logic → style
# 4. NON_BLOCKING comments may be skipped if no clear fix
```

#### 3. Requirement Gaps

```python
# Input: Unmet requirements from review
{
  "requirements_not_met": [
    "Token should expire after 24 hours",
    "Protected routes should verify token validity"
  ]
}

# Strategy:
# 1. Re-analyze original issue for context
# 2. Generate additional code to meet requirements
# 3. Ensure new code doesn't break existing functionality
```

### Viewing iteration history

```bash
# Local check of iteration state
uv run python -m src.code_agent.cli status --issue-number 123

# Output:
# Issue #123: "Implement JWT authentication"
# Status: in_progress
# Current iteration: 3/5
# PR: #456
#
# Iteration History:
# 1. Initial implementation (Quality: 65/100)
#    - Issues: Hardcoded secret, test failures
# 2. Applied feedback (Quality: 72/100)
#    - Fixed: Hardcoded secret
#    - Remaining: Test failures
# 3. Applied feedback (Quality: 85/100)
#    - Fixed: All tests passing
#    - Status: APPROVED
```

## Примеры использования

### Пример 1: Простой багфикс

**Issue #101:**

```markdown
Title: Fix incorrect status code in login endpoint

## Description
The login endpoint returns 200 OK even when credentials are invalid.
It should return 401 Unauthorized.

## Requirements
- POST /api/login should return 401 when credentials are wrong
- Error response should include message: "Invalid credentials"

## Acceptance Criteria
- [ ] Invalid credentials return 401 status
- [ ] Response includes error message
- [ ] Test `test_auth.py::test_login_invalid` passes
```

**Workflow:**

```bash
# 1. User adds label: agent:implement
# 2. Code Agent runs (~2 minutes)
#    - Analyzes issue
#    - Finds src/auth/routes.py
#    - Changes return status 200 → 401
#    - Commits and creates PR #102

# 3. CI runs (~3 minutes)
#    - All checks pass
#    - Reviewer approves (Quality: 95/100)

# 4. Manual merge
gh pr merge 102 --squash

# Total time: ~5 minutes
```

### Пример 2: Новая фича с итерациями

**Issue #202:**

```markdown
Title: Add password reset functionality

## Requirements
- POST /api/password-reset/request accepts email
- System generates reset token, sends email
- POST /api/password-reset/confirm accepts token + new password
- Tokens expire after 1 hour
- One-time use tokens

## Acceptance Criteria
- [ ] Request endpoint validates email format
- [ ] Reset email sent with token link
- [ ] Confirm endpoint validates token
- [ ] Expired tokens rejected
- [ ] Used tokens rejected
- [ ] Password updated in database
- [ ] All endpoints have tests
```

**Workflow:**

```bash
# 1. User adds label: agent:implement

# Iteration 1 (~7 minutes)
# - Code Agent generates full implementation
# - Creates PR #203
# - CI runs: 2 test failures, 1 security issue
# - Reviewer: REQUEST_CHANGES (Quality: 60/100)
#   Issues:
#   - Token generation not cryptographically secure
#   - Tests for token expiration missing
#   - Email sending not mocked in tests

# Iteration 2 (~5 minutes)
# - Feedback Loop applies fixes automatically
# - Fixes: Uses secrets.token_urlsafe() for tokens
# - Adds: Tests for expiration
# - Adds: Email mock in tests
# - CI runs: 1 test failure remains
# - Reviewer: REQUEST_CHANGES (Quality: 75/100)
#   Issues:
#   - test_reset_expired_token fails (timing issue)

# Iteration 3 (~3 minutes)
# - Feedback Loop applies fix
# - Fixes: Adds time.sleep() in test
# - CI runs: All pass
# - Reviewer: APPROVE (Quality: 88/100)

# Manual merge
gh pr merge 203 --squash

# Total time: ~15 minutes, 3 iterations
```

### Пример 3: Рефакторинг

**Issue #303:**

```markdown
Title: Refactor authentication module to use dependency injection

## Description
Current auth code has tight coupling. Refactor to use dependency injection
pattern for better testability.

## Requirements
- Extract dependencies (DB, email service) into injectable interfaces
- Update all auth endpoints to accept dependencies
- Add dependency injection container
- Update tests to use mocked dependencies

## Acceptance Criteria
- [ ] All auth functions accept dependencies as parameters
- [ ] Abstract interfaces defined for DB and email
- [ ] DI container configured in main.py
- [ ] All existing tests still pass
- [ ] New tests for mocked dependencies
- [ ] No behavioral changes (refactor only)
```

**Workflow:**

```bash
# 1. User adds label: agent:implement

# Iteration 1 (~10 minutes)
# - Code Agent analyzes complex requirements
# - Generates refactored code
# - Creates PR #304
# - CI runs: Multiple issues
# - Reviewer: REQUEST_CHANGES (Quality: 50/100)
#   Issues:
#   - Import errors in auth/routes.py
#   - Type hints missing for new interfaces
#   - Tests failing due to signature changes
#   - DI container not integrated in main.py

# Iteration 2 (~7 minutes)
# - Feedback Loop applies fixes
# - Fixes: Imports, adds type hints
# - Updates: All tests with new signatures
# - Remaining: DI container integration incomplete
# - Reviewer: REQUEST_CHANGES (Quality: 68/100)

# Iteration 3 (~5 minutes)
# - Feedback Loop completes DI integration
# - CI runs: All pass
# - Reviewer: APPROVE (Quality: 82/100)

# Manual merge
gh pr merge 304 --squash

# Total time: ~22 minutes, 3 iterations
```

### Пример 4: Застревание и ручное вмешательство

**Issue #404:**

```markdown
Title: Add user profile photo upload

## Requirements
- POST /api/profile/photo accepts multipart/form-data
- Validates file type (JPEG, PNG only)
- Resizes to 500x500px
- Stores in S3 bucket
- Updates user.photo_url in database
```

**Workflow:**

```bash
# Iteration 1
# - Code Agent implements upload
# - CI: Test failure (S3 mock not configured)
# - Reviewer: REQUEST_CHANGES

# Iteration 2
# - Feedback Loop adds S3 mock
# - CI: Different test failure (PIL import error)
# - Reviewer: REQUEST_CHANGES

# Iteration 3
# - Feedback Loop adds Pillow to requirements
# - CI: Still failing (same error)
# - Reviewer: REQUEST_CHANGES

# Iteration 4
# - Feedback Loop regenerates same fix
# - CI: Still failing
# - Reviewer: REQUEST_CHANGES

# System detects stuck (70% similarity in last 3 iterations)
# Label added: agent:stuck
# Comment posted:
#   "System appears stuck. Last 3 iterations had similar issues:
#    - PIL import error persists
#    Possible causes:
#    - Dependency not installed in CI environment
#    - Requirements.txt not committed
#    Manual intervention recommended."

# MANUAL FIX:
# 1. Developer checks out PR branch
git checkout agent/issue-404

# 2. Realizes issue: requirements.txt not in git
git add requirements.txt
git commit -m "chore: add Pillow dependency to requirements.txt"
git push

# 3. Remove stuck label
gh pr edit 405 --remove-label agent:stuck

# 4. Trigger new review
gh pr review 405 --approve

# 5. Merge
gh pr merge 405 --squash
```

## Лучшие практики

### Для авторов Issues

#### 1. Пишите четкие требования

✅ **Хорошо:**
```markdown
## Requirements
- API endpoint should accept JSON payload with fields: name, email, age
- Validate email format using regex
- Return 400 if validation fails
- Store user in PostgreSQL database
```

❌ **Плохо:**
```markdown
## Requirements
- Add user registration
```

#### 2. Добавляйте acceptance criteria

Это помогает Reviewer Agent проверить полноту реализации:

```markdown
## Acceptance Criteria
- [ ] Endpoint responds to POST /api/users
- [ ] Email validation rejects invalid formats
- [ ] Database transaction rolls back on error
- [ ] Returns 201 on success with user ID
- [ ] Unit tests for validation logic
- [ ] Integration test for full flow
```

#### 3. Указывайте целевые файлы (если знаете)

```markdown
## Files to Modify
- src/api/users.py (add endpoint)
- src/models/user.py (update model)
- tests/test_users.py (add tests)
```

#### 4. Документируйте edge cases

```markdown
## Edge Cases
- What if email already exists? → Return 409 Conflict
- What if database is down? → Return 503 Service Unavailable
- What if name contains special characters? → Allow, but sanitize
```

#### 5. Ссылайтесь на существующие паттерны

```markdown
## Technical Details
- Follow same pattern as existing auth endpoints in src/auth/
- Use same error response format as defined in src/common/errors.py
- Database connection via src/db/connection.py pool
```

### Для работы с PR

#### 1. Проверяйте CI перед merge

Даже если reviewer одобрил, убедитесь что:
- ✅ Все тесты проходят
- ✅ Coverage не упал
- ✅ Нет security warnings
- ✅ Linting чистый

#### 2. Ревьюйте код даже после AI approval

AI может пропустить:
- Архитектурные проблемы
- Бизнес-логику
- Неоптимальные решения
- Нарушение domain-specific правил

#### 3. Оставляйте feedback для улучшения системы

Если AI сделал что-то неправильно:

```markdown
@github-actions This implementation is correct but overcomplicated.
In our codebase we prefer using the simpler pattern from src/common/utils.py.
Please update.
```

Система учтет это в следующей итерации.

#### 4. Используйте draft PRs для экспериментов

```bash
# Create draft PR to test without triggering full CI
gh pr create --draft --title "WIP: Testing auth refactor"

# When ready, mark as ready for review
gh pr ready 456
```

### Для настройки системы

#### 1. Настройте правильные permissions

GitHub token должен иметь:
- `repo` (полный доступ к repository)
- `pull_requests: write`
- `issues: write`
- `contents: write`

#### 2. Оптимизируйте LLM costs

```yaml
# .github/workflows/code-agent.yml
env:
  OPENAI_MODEL: gpt-4o-mini  # Cheaper, faster
  # vs
  # OPENAI_MODEL: gpt-4o      # More capable, expensive
```

Рекомендация:
- Простые задачи: `gpt-4o-mini`, `gpt-3.5-turbo`
- Сложные задачи: `gpt-4o`, `gpt-4-turbo`

#### 3. Настройте rate limiting

```python
# .env
MAX_LLM_REQUESTS_PER_MINUTE=10  # Default
# Decrease if hitting rate limits
# Increase if you have higher quota
```

#### 4. Кастомизируйте iteration limits

```yaml
# .github/workflows/code-agent.yml
env:
  MAX_ITERATIONS: 5  # Default
  # Increase for complex features
  # Decrease for simple bugfixes
```

#### 5. Включите security checks

```python
# .env
ENABLE_SECURITY_CHECKS=true  # Always true in production
```

Проверяемые паттерны:
- Hardcoded secrets
- SQL injection
- Command injection
- Unsafe YAML/pickle
- Use of eval/exec
- Subprocess with shell=True

## Расширенные возможности

### Webhook Server Mode (Production)

Для production использования рекомендуется переключиться на webhook server режим:

**Преимущества:**
- ⚡ Быстрее (~100ms response vs 30s+ в Actions)
- 💰 Дешевле (не тратятся GitHub Actions minutes)
- 📊 Лучший мониторинг (Prometheus metrics)
- 🔄 Горизонтальное масштабирование (add workers)
- 🛡️ Выше GitHub API rate limits (App: 5000/hr vs PAT: 1000/hr)

**Setup:**

```bash
# 1. Create GitHub App
# - https://github.com/settings/apps/new
# - Subscribe to: issues, pull_request, pull_request_review
# - Generate private key

# 2. Configure secrets
# .env.production
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
GITHUB_APP_INSTALLATION_ID=12345678
WEBHOOK_SECRET=your-webhook-secret
REDIS_URL=redis://redis:6379/0
WEBHOOK_SERVER_URL=https://your-domain.com

# 3. Deploy with Docker Compose
docker-compose -f docker-compose.production.yml up -d

# 4. Switch workflows
# Rename reviewer-agent.yml → reviewer-agent-local.yml
# Rename reviewer-agent-webhook.yml → reviewer-agent.yml

# 5. Configure GitHub App webhook URL
# https://your-domain.com/webhooks/github
```

**Monitoring:**

```bash
# Health check
curl https://your-domain.com/health

# Prometheus metrics
curl https://your-domain.com/metrics

# RQ queue status
docker-compose exec worker rq info
```

### Custom Security Rules

Добавьте свои security patterns:

```python
# src/code_agent/code_modifier.py

SECURITY_PATTERNS = [
    # ... existing patterns ...

    # Custom pattern
    {
        "name": "Internal API key pattern",
        "pattern": r"INTERNAL_API_KEY\s*=\s*['\"][\w-]+['\"]",
        "severity": "HIGH",
        "message": "Hardcoded internal API key detected"
    }
]
```

### Custom CI Checks

Добавьте дополнительные проверки в pipeline:

```yaml
# .github/workflows/reviewer-agent.yml

- name: Custom Security Scan
  run: |
    # Your custom security tool
    uv run custom-scanner src/ --output=json > custom-report.json || true

- name: Upload Custom Report
  uses: actions/upload-artifact@v3
  with:
    name: custom-report
    path: custom-report.json
```

Затем обновите CI analyzer:

```python
# src/reviewer_agent/ci_analyzer.py

def parse_custom_report(self, report_path: Path) -> List[Issue]:
    """Parse custom security scanner report."""
    # Implementation
```

### Multi-Repository Support

Для работы с несколькими репозиториями:

```bash
# Run agent for different repos
GITHUB_REPOSITORY=org/repo1 uv run python -m src.code_agent.cli process-issue 123
GITHUB_REPOSITORY=org/repo2 uv run python -m src.code_agent.cli process-issue 456
```

Или используйте webhook server с несколькими installations.

### Custom LLM Providers

Добавьте свой LLM provider:

```python
# src/code_agent/llm_client.py

def call_custom_llm(
    prompt: str,
    response_model: Type[T],
    config: AgentConfig
) -> T:
    """Call custom LLM provider."""
    # Your implementation
    pass
```

## Ограничения и обход проблем

### Известные ограничения

#### 1. Поддержка только Python проектов

**Ограничение**: Syntax validation, security checks работают только для Python.

**Обход**:
- Отключите validation для других языков
- Добавьте свои validators в `code_modifier.py`

#### 2. Размер контекста LLM

**Ограничение**: Большие файлы (>10K строк) могут не поместиться в контекст.

**Обход**:
- Разбейте большие файлы на модули
- Используйте более новые модели с большим контекстом
- Укажите конкретные функции для изменения в issue

#### 3. Зависимость от CI артефактов

**Ограничение**: Reviewer работает только если CI успешно загрузил артефакты.

**Обход**:
- Проверьте что CI jobs не падают до artifact upload
- Используйте `continue-on-error: true` для non-critical checks
- Добавьте fallback: если артефактов нет, reviewer работает только с diff

#### 4. Стоимость LLM API

**Ограничение**: Частые запросы могут быть дорогими.

**Обход**:
- Используйте дешевые модели для простых задач (gpt-4o-mini)
- Кешируйте LLM responses (not implemented yet)
- Ограничьте количество итераций
- Используйте open-source модели (требует self-hosting)

### Типичные проблемы

#### Проблема: "Code Agent создает неправильный код"

**Причины:**
- Issue недостаточно детальный
- LLM не понял codebase conventions
- Нет примеров existing code

**Решение:**
1. Добавьте больше деталей в issue
2. Укажите файлы-примеры для reference
3. Добавьте coding guidelines в CLAUDE.md

#### Проблема: "Reviewer слишком строгий"

**Причины:**
- Quality threshold слишком высокий
- Non-blocking issues считаются blocking

**Решение:**
```python
# src/reviewer_agent/orchestrator.py

# Adjust quality threshold
APPROVAL_THRESHOLD = 70  # Default: 80

# Adjust severity classification
def is_blocking(issue: Issue) -> bool:
    # Custom logic
    pass
```

#### Проблема: "Система зацикливается"

**Причины:**
- Issue requirements противоречивы
- Тесты написаны неправильно
- LLM не понимает ошибку

**Решение:**
1. Проверьте issue на противоречия
2. Проверьте тесты вручную
3. Добавьте technical context в issue
4. Если не помогает: manual fix + remove stuck label

#### Проблема: "GitHub API rate limit"

**Причины:**
- Слишком много requests к GitHub API
- PAT токен имеет низкий лимит (1000/hour)

**Решение:**
1. Используйте `GITHUB_TOKEN` из Actions (5000/hour)
2. Переключитесь на GitHub App mode (5000/hour per installation)
3. Добавьте rate limiting в github_client.py
4. Уменьшите частоту workflows

#### Проблема: "LLM API timeout"

**Причины:**
- Большой контекст (длинные файлы)
- Provider перегружен

**Решение:**
1. Увеличьте timeout в llm_client.py
2. Уменьшите размер контекста (передавайте только relevant code)
3. Используйте retry with exponential backoff (уже реализовано)
4. Переключитесь на более быстрый provider

---

## Заключение

**Coding Agents** — это мощная система автоматизации SDLC, которая:

- ✅ Автоматизирует рутинные задачи разработки
- ✅ Обеспечивает постоянное качество кода через CI/CD
- ✅ Ускоряет code review с помощью AI
- ✅ Интегрируется с существующими GitHub workflows
- ✅ Масштабируется от простых багфиксов до сложных фич

**Когда использовать:**
- Простые feature implementations
- Bugfixes
- Refactoring
- Adding tests
- Improving documentation

**Когда НЕ использовать:**
- Критичные security-related изменения (требуют human review)
- Архитектурные решения (требуют design discussion)
- Большие breaking changes (требуют careful planning)

**Следующие шаги:**

1. Настройте систему в своем репозитории
2. Создайте первый issue для тестирования
3. Наблюдайте за процессом и улучшайте prompts
4. Постепенно увеличивайте complexity задач
5. Переключитесь на webhook server для production

Система постоянно развивается и улучшается. Вносите свои изменения и делитесь опытом!

---

**Полезные ссылки:**

- 📖 [README.md](README.md) - Quick Start Guide
- 🛠️ [CLAUDE.md](CLAUDE.md) - Development Guide (for Claude Code)
- 🐛 [Issues](https://github.com/ZetoOfficial/coding-agents/issues) - Report bugs
- 💬 [Discussions](https://github.com/ZetoOfficial/coding-agents/discussions) - Ask questions