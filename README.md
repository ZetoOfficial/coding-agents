# Coding Agents - AI-система автоматизации SDLC

[![Production Status](https://img.shields.io/badge/status-production-success)](https://agents.zetoqqq.ru)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Полностью автоматизированная система разработки**, которая превращает GitHub Issues в готовый, протестированный и проверенный код без участия человека.

🌐 **Демо:** [agents.zetoqqq.ru](https://agents.zetoqqq.ru)

---

## 🎯 Что это?

Автоматизированная агентная система, реализующая **полный цикл разработки ПО (SDLC)** внутри GitHub:

```
Issue с задачей → Анализ → Генерация кода → PR → CI/CD → AI Review → Исправления → Готовый код
```

Система работает как **настоящая команда разработчиков**:
- **Code Agent** - разработчик, который пишет код по требованиям
- **Reviewer Agent** - ревьюер, который проверяет качество и соответствие требованиям
- **Feedback Loop** - итеративное улучшение до достижения приемлемого качества

### 🚀 Основные возможности

- ✅ **Автоматическая реализация задач** из GitHub Issues
- ✅ **AI-ревью кода** с инлайн-комментариями и анализом CI
- ✅ **Итеративное улучшение** до 5 итераций с защитой от зацикливания
- ✅ **Production-ready развертывание** через webhook + GitHub App
- ✅ **CI/CD интеграция** с автоматическими проверками качества
- ✅ **Проверка безопасности** кода на уязвимости
- ✅ **Масштабируемая архитектура** с Redis + RQ Workers

---

## 📊 Архитектура решения

### Режим работы: GitHub App + Webhook Server

Система развернута на **agents.zetoqqq.ru** и работает через GitHub App webhooks:

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Repository                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐         │
│  │  Issue   │ -> │    PR    │ -> │   CI/CD      │         │
│  │ created  │    │  opened  │    │ (ruff,pytest)│         │
│  └────┬─────┘    └────┬─────┘    └──────┬───────┘         │
└───────┼───────────────┼─────────────────┼──────────────────┘
        │               │                 │
        │ webhook       │ webhook         │ webhook
        ▼               ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Production Server (agents.zetoqqq.ru)                      │
│                                                             │
│  ┌─────────────────────────────────────────────────┐       │
│  │  FastAPI Webhook Server (port 8000)             │       │
│  │  • GitHub App аутентификация (JWT)              │       │
│  │  • Webhook signature validation                 │       │
│  │  • Высокая производительность (<100ms response) │       │
│  └──────────────────┬──────────────────────────────┘       │
│                     │ enqueue task                         │
│                     ▼                                       │
│  ┌─────────────────────────────────────────────────┐       │
│  │  Redis Task Queue                               │       │
│  │  • Персистентное хранилище (AOF)                │       │
│  │  • Управление очередью задач                    │       │
│  │  • Хранение состояний итераций                  │       │
│  └──────────────────┬──────────────────────────────┘       │
│                     │ process async                        │
│                     ▼                                       │
│  ┌─────────────────────────────────────────────────┐       │
│  │  RQ Workers (2x replicas)                       │       │
│  │                                                 │       │
│  │  Worker 1:           Worker 2:                 │       │
│  │  ├─ Code Agent       ├─ Reviewer Agent         │       │
│  │  ├─ LLM Integration  ├─ CI Analyzer            │       │
│  │  ├─ Git Operations   ├─ Diff Analysis          │       │
│  │  └─ State Manager    └─ Review Posting         │       │
│  └─────────────────────────────────────────────────┘       │
│                     │                                       │
│                     ▼ post results                          │
└─────────────────────┼──────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub API                                                 │
│  • Create branches & commits                               │
│  • Create pull requests                                    │
│  • Post reviews & comments                                 │
│  • Manage labels & iterations                              │
└─────────────────────────────────────────────────────────────┘
```

### Преимущества webhook-архитектуры

| **GitHub Actions Mode** | **Webhook Server Mode** ⭐ |
|------------------------|---------------------------|
| ❌ Тратит GitHub Actions минуты | ✅ Не использует CI минуты для AI |
| ❌ 1000 API запросов/час (PAT) | ✅ 5000 API запросов/час (App) |
| ❌ Последовательная обработка | ✅ Параллельная обработка (2+ workers) |
| ❌ Нет мониторинга | ✅ RQ Dashboard + health checks |
| ❌ Сложно масштабировать | ✅ Горизонтальное масштабирование |

---

## 🔄 Полный SDLC цикл

### 1️⃣ Создание задачи

Пользователь создает GitHub Issue с описанием задачи:

```markdown
Title: Добавить функцию валидации email

Требования:
- Создать функцию validate_email(email: str) -> bool
- Использовать regex для проверки формата
- Добавить unit-тесты
- Обработать edge cases (пустая строка, None)
```

### 2️⃣ Code Agent: Анализ и реализация

**Webhook:** GitHub отправляет событие `issues.labeled` → FastAPI → Redis Queue

**Worker обрабатывает:**

1. **Анализ требований** (LLM):
   ```python
   RequirementAnalysis {
       requirements: ["Функция validate_email", "Regex валидация", ...]
       target_files: ["src/utils.py", "tests/test_utils.py"]
       acceptance_criteria: [...]
   }
   ```

2. **Анализ кодовой базы:**
   - Сканирование структуры репозитория
   - Извлечение соглашений о коде (style guide)
   - Поиск похожих паттернов

3. **Генерация кода** (LLM с контекстом):
   ```python
   # src/utils.py
   import re
   from typing import Optional

   def validate_email(email: Optional[str]) -> bool:
       """Validate email address format."""
       if not email:
           return False
       pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
       return bool(re.match(pattern, email))
   ```

4. **Валидация:**
   - ✅ Python синтаксис (AST compilation)
   - ✅ Проверка безопасности (8+ паттернов)
   - ✅ Проверка ссылок на файлы

5. **Git операции:**
   ```bash
   git checkout -b agent/issue-123
   # Apply changes with backup/rollback
   git commit -m "Add email validation function"
   git push origin agent/issue-123
   ```

6. **Создание PR:**
   - Описание с чеклистом требований
   - Связь с оригинальным Issue (#123)
   - Метки: `agent:iteration-1`, `agent:in-progress`

### 3️⃣ CI/CD: Проверки качества

GitHub Actions запускает pipeline:

```yaml
quality-checks:
  - ruff check (linting)
  - black --check (formatting)
  - mypy (type checking)

test-and-security:
  - pytest (tests + coverage)
  - bandit (security scan)
  - pip-audit (dependencies)
```

Результаты сохраняются как JSON артефакты.

### 4️⃣ Reviewer Agent: AI-анализ

**Webhook:** GitHub отправляет событие `pull_request.opened` → FastAPI → Redis Queue

**Worker обрабатывает:**

1. **Парсинг CI артефактов:**
   ```python
   CIResults {
       lint_errors: [...],
       test_failures: [...],
       security_issues: [...],
       coverage: 85.5
   }
   ```

2. **Анализ diff** (LLM):
   - Сравнение изменений с требованиями Issue
   - Проверка на соответствие code style
   - Оценка качества реализации

3. **Генерация ревью:**
   ```python
   ReviewOutput {
       decision: "APPROVE" | "REQUEST_CHANGES",
       quality_score: 8.5,
       blocking_issues: [...],
       inline_comments: [
           InlineComment {
               path: "src/utils.py",
               line: 10,
               body: "Отлично! Обработка edge case для None."
           }
       ]
   }
   ```

4. **Публикация в GitHub:**
   - GitHub Review с inline комментариями
   - Summary comment с оценкой качества
   - Обновление меток

### 5️⃣ Feedback Loop: Итеративное улучшение

**Если ревью = "REQUEST_CHANGES":**

**Webhook:** `pull_request_review.submitted` → FastAPI → Redis Queue

**Worker обрабатывает:**

1. **Проверка итерации:**
   ```python
   current_iteration = 1
   if current_iteration >= MAX_ITERATIONS (5):
       add_label("agent:max-iterations")
       exit()
   ```

2. **Парсинг фидбека:**
   - Все комментарии ревьюера
   - CI failures из артефактов
   - Контекст оригинальных требований

3. **Генерация исправлений** (LLM):
   ```python
   FixPlan {
       issues_to_fix: [
           "Добавить обработку пустой строки",
           "Исправить lint ошибку на строке 15"
       ],
       files_to_modify: ["src/utils.py"]
   }
   ```

4. **Применение и push:**
   ```bash
   # Apply fixes to existing branch
   git add src/utils.py
   git commit -m "Apply reviewer feedback (iteration 2)"
   git push origin agent/issue-123
   ```

5. **Обновление меток:**
   - Удалить `agent:iteration-1`
   - Добавить `agent:iteration-2`
   - Триггер CI снова → возврат к шагу 3

### 6️⃣ Завершение

**Если ревью = "APPROVE":**

- ✅ Метка `agent:approved`
- ✅ PR готов к мерджу
- ✅ Комментарий в Issue с результатами

**Защита от зацикливания:**

- **Max iterations:** 5 итераций → метка `agent:max-iterations`
- **Stuck detection:** 3 одинаковых ошибки подряд → метка `agent:stuck`
- **Manual override:** Удалить метку и прокомментировать `/agent implement`

---

## 🚀 Быстрый старт

### Вариант 1: Использование production webhook-сервера

Если у вас уже развернут webhook-сервер на **agents.zetoqqq.ru**:

1. **Установите GitHub App** на ваш репозиторий
2. **Добавьте секреты** в Settings → Secrets:
   ```
   OPENAI_API_KEY=sk-...
   ```
3. **Создайте Issue** с меткой `agent:implement`
4. **Готово!** Система автоматически создаст PR

### Вариант 2: Локальное развертывание

```bash
# 1. Клонирование
git clone https://github.com/ZetoOfficial/coding-agents.git
cd coding-agents

# 2. Установка зависимостей
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 3. Конфигурация
cp .env.example .env
# Отредактируйте .env с вашими credentials

# 4. Запуск
docker-compose up -d

# 5. Проверка
curl http://localhost:8000/health
```

### Вариант 3: Развертывание на VPS

```bash
# На сервере (Ubuntu/Debian)
git clone <repo> /opt/coding-agents
cd /opt/coding-agents
cp .env.example.production .env.production
# Отредактируйте .env.production

docker-compose -f docker-compose.production.yml up -d

# Проверка
curl http://localhost:8000/health
```

Полная инструкция: [docs/DEPLOYMENT.ru.md](docs/DEPLOYMENT.ru.md)

---

## 📁 Структура проекта

```
coding-agents/
├── src/
│   ├── common/                      # Общие компоненты
│   │   ├── config.py               # Pydantic конфигурация с валидацией
│   │   ├── models.py               # Все data models (Issue, PR, Review)
│   │   └── state_manager.py        # Управление состояниями итераций
│   │
│   ├── code_agent/                 # Code Agent (Issue → PR)
│   │   ├── cli.py                  # CLI интерфейс (Typer)
│   │   ├── orchestrator.py         # Основная логика агента
│   │   ├── github_client.py        # PyGithub обертка
│   │   ├── llm_client.py           # Унифицированный LLM клиент
│   │   ├── prompts.py              # Централизованные промпты
│   │   ├── code_analyzer.py        # Анализ кодовой базы
│   │   └── code_modifier.py        # Git + валидация + безопасность
│   │
│   ├── reviewer_agent/             # Reviewer Agent (PR analysis)
│   │   ├── reviewer.py             # CLI интерфейс
│   │   ├── orchestrator.py         # Основная логика ревьюера
│   │   ├── ci_analyzer.py          # Парсинг CI артефактов
│   │   └── analysis_engine.py      # LLM-анализ diff
│   │
│   └── webhook_server/             # GitHub App webhook server
│       ├── app.py                  # FastAPI приложение
│       ├── webhook_handler.py      # Обработка GitHub webhooks
│       ├── event_router.py         # Роутинг событий к агентам
│       ├── github_app_auth.py      # JWT аутентификация GitHub App
│       ├── tasks.py                # RQ async задачи
│       └── middleware.py           # Логирование + rate limiting
│
├── .github/workflows/              # CI/CD
│   ├── code-agent.yml              # Issue processing (fallback)
│   ├── reviewer-agent.yml          # CI checks (quality)
│   └── build-and-deploy.yml        # Auto-deploy на production
│
├── tests/                          # Тесты
├── docs/                           # Документация
│   ├── README.ru.md                # Русская документация
│   ├── DEPLOYMENT.ru.md            # Инструкция по развертыванию
│   ├── DEPLOYMENT_WEBHOOK.md       # Webhook-специфичная настройка
│   └── QUICKSTART.md               # Быстрый старт (5 минут)
│
├── Dockerfile.production           # Multi-stage (web + worker)
├── docker-compose.production.yml   # Production stack
├── pyproject.toml                  # Python dependencies (uv)
└── CLAUDE.md                       # Инструкции для Claude Code
```

---

## 🛠 Технические детали

### Stack

**Backend:**
- Python 3.11+ (async/await, type hints)
- FastAPI (webhooks)
- Redis (queue + state storage)
- RQ (async workers)
- PyGithub (GitHub API)

**LLM Integration:**
- OpenAI GPT-4o-mini (primary)
- YandexGPT (alternative)
- Structured output (Pydantic models)

**CI/CD:**
- GitHub Actions (quality checks)
- Docker + Docker Compose
- GitHub Container Registry (ghcr.io)

**Tools:**
- ruff (linting)
- black (formatting)
- mypy (type checking)
- pytest (testing + coverage)
- bandit (security scan)
- pip-audit (dependency scan)

### Ключевые особенности реализации

#### 1. Structured LLM Output

Все взаимодействия с LLM используют Pydantic для type-safe ответов:

```python
from src.common.models import RequirementAnalysis
from src.code_agent.llm_client import call_llm_structured

analysis: RequirementAnalysis = call_llm_structured(
    prompt=prompt_text,
    response_model=RequirementAnalysis,
    config=config,
)
# Гарантированно корректная структура + валидация
```

#### 2. Безопасность

**Проверка кода на 8+ паттернов:**
- Hardcoded credentials (API keys, tokens, passwords)
- SQL injection patterns
- eval()/exec() usage
- shell=True in subprocess
- Unsafe YAML/pickle loading
- AWS credentials
- SSH/RSA private keys

**Защита секретов:**
- Pydantic SecretStr для конфиденциальных данных
- Автоматическая фильтрация в логах
- Webhook signature validation (constant-time comparison)

#### 3. GitHub App Authentication

```python
# JWT токен для GitHub App
jwt_token = generate_jwt(app_id, private_key)

# Installation access token (1 час TTL)
installation_token = get_installation_token(
    jwt_token, installation_id
)

# Rate limits: 5000 запросов/час (vs 1000 для PAT)
```

#### 4. Idempotent Operations

Все операции с GitHub идемпотентны:
- Комментарии используют HTML markers для обновления
- Reviews dismissal перед новым постингом
- Label operations проверяют существование

#### 5. State Management

```python
# .agent-state/issue-123.json
{
    "issue_number": 123,
    "iteration": 2,
    "pr_number": 456,
    "review_history": [...],
    "stuck_count": 0,
    "last_error": null
}
```

---

## 📈 Результаты и метрики

### Соответствие требованиям ТЗ

| Требование | Статус | Реализация |
|-----------|--------|-----------|
| Полный SDLC цикл | ✅ | Issue → Code → PR → CI → Review → Fixes |
| Code Agent CLI | ✅ | Typer-based CLI + orchestrator |
| AI Reviewer в CI/CD | ✅ | GitHub Actions + webhook trigger |
| Итерационные правки | ✅ | До 5 итераций с feedback loop |
| Защита от зацикливания | ✅ | Max iterations + stuck detection |
| Python 3.11+ | ✅ | Python 3.11 с type hints |
| LLM интеграция | ✅ | OpenAI GPT-4o-mini + YandexGPT |
| Quality checks | ✅ | ruff, black, mypy, pytest, bandit |
| Docker | ✅ | Multi-stage Dockerfile + compose |
| **Дополнительно:** Облачное развертывание | ✅ | agents.zetoqqq.ru (VPS) |

### Производительность

- **Webhook response time:** <100ms
- **Issue → PR:** ~3-5 минут
- **Review generation:** ~2-3 минуты
- **Feedback application:** ~2-3 минуты
- **Полный цикл (1 итерация):** ~10 минут

### Качество кода

- **Test coverage:** 70%+ (настраивается)
- **Linting:** 100% (ruff + black)
- **Type safety:** 100% (mypy strict)
- **Security:** Автоматический scan (bandit + pip-audit)

---

## 🧪 Примеры использования

### Пример 1: Простая функция

**Issue:**
```markdown
Добавить функцию для вычисления факториала

Требования:
- Функция factorial(n: int) -> int
- Рекурсивная реализация
- Обработка n=0 и n<0
- Unit тесты
```

**Результат:**
- ✅ PR создан за 4 минуты
- ✅ Тесты проходят (coverage 100%)
- ✅ AI Review: "от меня ок" (quality: 9/10)
- ✅ 1 итерация

### Пример 2: API endpoint

**Issue:**
```markdown
Добавить REST API endpoint для регистрации пользователей

Требования:
- POST /api/users/register
- Валидация email и пароля
- Хеширование пароля (bcrypt)
- FastAPI + SQLAlchemy
- Тесты с pytest
```

**Результат:**
- ✅ PR создан за 6 минут
- ❌ Reviewer: "поправь моменты выше"
  - Нет проверки на дубликат email
  - Слабая валидация пароля
- ✅ Fixes применены за 3 минуты
- ✅ AI Review: "от меня ок" (quality: 8.5/10)
- ✅ 2 итерации

### Пример 3: Рефакторинг

**Issue:**
```markdown
Рефакторинг функции parse_config()

Проблемы:
- Слишком сложная (McCabe complexity 15)
- Нет type hints
- Плохая обработка ошибок

Требования:
- Разбить на меньшие функции
- Добавить type hints
- Улучшить error handling
- Сохранить обратную совместимость
```

**Результат:**
- ✅ PR создан за 7 минут
- ✅ Complexity снижен до 5
- ✅ Все существующие тесты проходят
- ✅ AI Review: "от меня ок" (quality: 9/10)
- ✅ 1 итерация

---

## 📚 Дополнительная документация

- **[QUICKSTART.md](docs/QUICKSTART.md)** - Быстрый старт за 5 минут
- **[DEPLOYMENT.ru.md](docs/DEPLOYMENT.ru.md)** - Подробное руководство по развертыванию
- **[DEPLOYMENT_WEBHOOK.md](docs/DEPLOYMENT_WEBHOOK.md)** - Настройка webhook-сервера на VPS
- **[CLI_USAGE.md](docs/CLI_USAGE.md)** - Справочник команд CLI
- **[EXAMPLES.md](docs/EXAMPLES.md)** - Реальные примеры использования
- **[CLAUDE.md](CLAUDE.md)** - Инструкции для Claude Code

---

## 🔧 Конфигурация

### Основные переменные окружения

```bash
# GitHub App (для webhook mode)
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_APP_INSTALLATION_ID=12345678
GITHUB_REPOSITORY=owner/repo
WEBHOOK_SECRET=<random-secret>

# Redis
REDIS_URL=redis://redis:6379/0

# LLM Provider
LLM_PROVIDER=openai                # или yandex
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Agent Configuration
MAX_ITERATIONS=5                   # Лимит итераций (1-10)
AGENT_TIMEOUT_MINUTES=30          # Таймаут операций
DEFAULT_BRANCH=master             # Базовая ветка для PR
MIN_COVERAGE_PERCENT=70.0         # Минимальное покрытие тестами
ENABLE_SECURITY_CHECKS=true       # Проверки безопасности

# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                   # text или json
```

Полный список: [.env.example](.env.example)

---

## 🎓 Обучение и развитие

### Текущие возможности

- ✅ Python проекты (полная поддержка)
- ✅ Функции и модули
- ✅ API endpoints (FastAPI)
- ✅ Рефакторинг существующего кода
- ✅ Исправление багов
- ✅ Добавление тестов

### Roadmap

- 🔄 Поддержка других языков (Go, TypeScript, Rust)
- 🔄 Интеграция с Jira/Linear
- 🔄 Custom code style rules
- 🔄 Multi-repo refactoring
- 🔄 Architecture diagrams generation
- 🔄 Code documentation generation

---

## 🤝 Вклад в проект

Мы приветствуем вклад! Процесс:

1. **Fork** репозитория
2. **Создайте ветку** для фичи: `git checkout -b feature/amazing-feature`
3. **Commit** изменения: `git commit -m 'Add amazing feature'`
4. **Push** в ветку: `git push origin feature/amazing-feature`
5. **Создайте Pull Request**

### Guidelines

- Следуйте существующему code style
- Добавляйте тесты для новых фич
- Обновляйте документацию
- Запустите quality checks перед PR

---

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) для деталей.

---

## 🙏 Благодарности

**Технологии:**
- [OpenAI GPT-4o-mini](https://openai.com/) - LLM для генерации кода
- [YandexGPT](https://cloud.yandex.com/ru/services/yandexgpt) - Альтернативный LLM
- [PyGithub](https://github.com/PyGithub/PyGithub) - GitHub API
- [FastAPI](https://fastapi.tiangolo.com/) - Webhook server
- [Redis + RQ](https://python-rq.org/) - Task queue
- [uv](https://github.com/astral-sh/uv) - Package management

**Inspiration:**
- GitHub Copilot Workspace
- Cursor.ai
- Devin AI

---

## 📞 Поддержка

**Issues и вопросы:**
- [GitHub Issues](https://github.com/ZetoOfficial/coding-agents/issues)
- [GitHub Discussions](https://github.com/ZetoOfficial/coding-agents/discussions)

**Production сервер:**
- URL: [agents.zetoqqq.ru](https://agents.zetoqqq.ru)
- Health: [agents.zetoqqq.ru/health](https://agents.zetoqqq.ru/health)
- Status: [![Production Status](https://img.shields.io/badge/status-production-success)](https://agents.zetoqqq.ru)

---

## 🏆 Статус проекта

**Версия:** 1.0.0
**Статус:** ✅ Production Ready
**Развертывание:** ✅ agents.zetoqqq.ru
**Тесты:** ✅ Passing
**Coverage:** ✅ 70%+
**Security:** ✅ Scanned

---

<div align="center">

**Сделано с ❤️ для автоматизации SDLC**

[Демо](https://agents.zetoqqq.ru) • [Документация](docs/) • [Issues](https://github.com/ZetoOfficial/coding-agents/issues)

</div>