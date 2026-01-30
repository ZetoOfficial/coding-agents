# Coding Agents - Автоматизация SDLC с помощью AI

AI-система для автоматизации жизненного цикла разработки (SDLC), которая работает через GitHub Actions. Состоит из двух агентов:
- **Code Agent** — автоматически реализует фичи из GitHub issues
- **Reviewer Agent** — анализирует pull requests и оставляет детальные review

## Что умеет система

- **Автоматическая реализация фич**: Превращает GitHub issues в рабочий код и pull requests
- **AI code review**: Комплексный анализ PR с inline комментариями
- **Итеративное улучшение**: Автоматически применяет фидбек reviewer до 5 итераций
- **CI/CD интеграция**: Проверки качества (linting, тесты, безопасность) перед review
- **Поддержка разных LLM**: Работает с OpenAI GPT или YandexGPT
- **Защита от зацикливания**: Обнаруживает повторяющиеся ошибки и останавливается
- **Фокус на безопасность**: Встроенные проверки безопасности кода

## Быстрый старт

### Требования

- Python 3.11+
- Git
- GitHub токен
- OpenAI API key или YandexGPT API key

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/ZetoOfficial/coding-agents.git
cd coding-agents

# 2. Установить uv (менеджер пакетов)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Установить зависимости
uv sync

# 4. Настроить окружение
cp .env.example .env
# Отредактировать .env - добавить API ключи
```

Обязательные переменные окружения в `.env`:
```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxx          # GitHub токен
GITHUB_REPOSITORY=owner/repo           # Формат owner/repo
OPENAI_API_KEY=sk-xxxxxxxxxxxx         # Или YANDEX_API_KEY
```

### Локальное использование

**Инициализация**:
```bash
uv run python -m src.code_agent.cli init
```

**Обработать issue**:
```bash
uv run python -m src.code_agent.cli process-issue 123
```

**Применить фидбек к PR**:
```bash
uv run python -m src.code_agent.cli apply-feedback 456
```

**Проверить статус**:
```bash
uv run python -m src.code_agent.cli status 123
```

**Ревью PR** (требуется CI артефакты):
```bash
uv run python -m src.reviewer_agent.reviewer review \
  --pr-number 456 \
  --artifact-dir ./ci-reports/ \
  --output review.json \
  --post-review
```

### Использование через Docker

**Собрать образ**:
```bash
docker-compose build
```

**Запустить Code Agent**:
```bash
# Обработать issue
docker-compose run --rm agent-dev process-issue 123

# Применить фидбек
docker-compose run --rm agent-dev apply-feedback 456

# Проверить статус
docker-compose run --rm agent-dev status 123
```

**Запустить Reviewer Agent**:
```bash
docker-compose run --rm reviewer-dev review \
  --pr-number 456 \
  --artifact-dir /app/ci-reports \
  --output review.json \
  --post-review
```

**Интерактивная оболочка**:
```bash
docker-compose run --rm agent-dev bash
```

## Настройка GitHub Actions

### 1. Добавить секреты

Перейти в **Settings → Secrets and variables → Actions** и добавить:

- `OPENAI_API_KEY` (или `YANDEX_API_KEY`) — API ключ LLM провайдера
- `YANDEX_FOLDER_ID` (если используете YandexGPT) — Yandex Cloud folder ID

### 2. Опциональные переменные

Перейти в **Settings → Secrets and variables → Actions → Variables**:

- `LLM_PROVIDER` — `openai` (по умолчанию) или `yandex`
- `MAX_ITERATIONS` — Максимум итераций (по умолчанию `5`)

### 3. Workflows активируются автоматически

Workflows в `.github/workflows/` запускаются автоматически:

- **code-agent.yml** — когда issue получает label `agent:implement`
- **reviewer-agent.yml** — когда PR открывается или обновляется
- **feedback-loop.yml** — когда reviewer запрашивает изменения

### 4. Как использовать

1. Создать GitHub issue с четкими требованиями
2. Добавить label `agent:implement` (или комментарий `/agent implement`)
3. Подождать ~5 минут — Code Agent создаст PR
4. CI автоматически запустится и проверит код
5. Reviewer Agent проанализирует и оставит review
6. При необходимости система автоматически применит фидбек (до 5 итераций)

## Основные команды

### Code Agent CLI

```bash
# Инициализация (проверка настроек)
uv run python -m src.code_agent.cli init

# Обработать issue (создать PR)
uv run python -m src.code_agent.cli process-issue <номер_issue>

# Применить фидбек reviewer (обновить PR)
uv run python -m src.code_agent.cli apply-feedback <номер_pr>

# Проверить статус issue
uv run python -m src.code_agent.cli status [номер_issue]

# Показать версию
uv run python -m src.code_agent.cli version
```

### Reviewer Agent CLI

```bash
# Проанализировать PR и оставить review
uv run python -m src.reviewer_agent.reviewer review \
  --pr-number <номер> \
  --artifact-dir <путь_к_CI_артефактам> \
  --output <файл.json> \
  [--post-review] \
  [--issue-number <номер>]

# Опубликовать сохраненный review
uv run python -m src.reviewer_agent.reviewer post \
  --review-file <файл.json> \
  --pr-number <номер>
```

### Проверки качества кода

```bash
# Линтинг
uv run ruff check src/

# Авто-исправление
uv run ruff check src/ --fix

# Форматирование
uv run black src/

# Проверка типов
uv run mypy src/

# Сканирование безопасности
uv run bandit -r src/

# Запустить все проверки
uv run ruff check src/ && uv run black src/ && uv run mypy src/ && uv run bandit -r src/
```

### Тестирование

```bash
# Запустить все тесты
uv run pytest tests/ -v

# С отчетом о покрытии
uv run pytest tests/ -v --cov=src --cov-report=html

# Конкретный тест
uv run pytest tests/test_github_client.py -v
```

## Конфигурация

Основные настройки в `.env`:

```bash
# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPOSITORY=owner/repo
DEFAULT_BRANCH=master

# LLM провайдер
LLM_PROVIDER=openai                    # или yandex
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini               # или gpt-4o

# Или для YandexGPT:
# YANDEX_API_KEY=xxxxxxxxxxxx
# YANDEX_FOLDER_ID=xxxxxxxxxxxx
# YANDEX_MODEL=yandexgpt-latest

# Поведение агента
MAX_ITERATIONS=5                        # Максимум итераций (1-10)
AGENT_TIMEOUT_MINUTES=30
ENABLE_SECURITY_CHECKS=true

# Логирование
LOG_LEVEL=INFO                          # DEBUG, INFO, WARNING, ERROR
```

Полный список настроек смотрите в `.env.example`.

## Структура проекта

```
src/
├── common/              # Общие утилиты
│   ├── config.py       # Конфигурация
│   └── models.py       # Pydantic модели
├── code_agent/         # Code Agent
│   ├── cli.py         # CLI интерфейс
│   ├── github_client.py
│   ├── llm_client.py
│   └── ...
└── reviewer_agent/     # Reviewer Agent
    ├── reviewer.py    # CLI интерфейс
    └── ...

.github/workflows/      # GitHub Actions
├── code-agent.yml
├── reviewer-agent.yml
└── feedback-loop.yml
```

## Безопасность

Система автоматически проверяет код на:
- Hardcoded секреты (API ключи, пароли, токены)
- SQL injection уязвимости
- Использование `eval()` / `exec()`
- Небезопасные subprocess вызовы
- Уязвимые зависимости

Все секреты автоматически фильтруются из логов.

## Поддержка

- 📖 Подробная документация: [REPORT.md](REPORT.md)
- 🛠️ Для разработчиков: [CLAUDE.md](CLAUDE.md)
- 🐛 Сообщить о проблеме: [GitHub Issues](https://github.com/ZetoOfficial/coding-agents/issues)
