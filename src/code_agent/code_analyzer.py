"""Code analyzer module for repository analysis and convention extraction.

This module provides functionality to analyze codebases, identify target files,
extract coding conventions, and build context for code generation without requiring git.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Analyzes repository structure, conventions, and patterns."""

    # Common directories to exclude from analysis
    DEFAULT_EXCLUDE_PATTERNS = [
        "__pycache__",
        ".git",
        ".github",
        ".venv",
        "venv",
        "env",
        ".env",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "*.egg-info",
        "dist",
        "build",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "*.pyd",
    ]

    def __init__(self, repo_path: str) -> None:
        """Initialize code analyzer.

        Args:
            repo_path: Path to repository root directory
        """
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        if not self.repo_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo_path}")

        logger.info(f"Initialized CodeAnalyzer for: {self.repo_path}")

    # ============================================================================
    # File Discovery
    # ============================================================================

    def find_python_files(self, exclude_patterns: list[str] | None = None) -> list[str]:
        """Find all Python files in the repository.

        Args:
            exclude_patterns: Additional patterns to exclude (extends DEFAULT_EXCLUDE_PATTERNS)

        Returns:
            List of relative file paths (strings) to Python files
        """
        exclude = self.DEFAULT_EXCLUDE_PATTERNS.copy()
        if exclude_patterns:
            exclude.extend(exclude_patterns)

        python_files = []
        try:
            for py_file in self.repo_path.rglob("*.py"):
                # Check if file should be excluded
                relative_path = py_file.relative_to(self.repo_path)
                if self._should_exclude(relative_path, exclude):
                    continue

                python_files.append(str(relative_path))

            logger.info(f"Found {len(python_files)} Python files in repository")
            return sorted(python_files)

        except Exception as e:
            logger.error(f"Error finding Python files: {e}")
            raise

    def find_related_files(self, file_path: str, max_files: int = 10) -> list[str]:
        """Find related files for context (same directory, imports, tests, etc.).

        Args:
            file_path: Relative path to the target file
            max_files: Maximum number of related files to return

        Returns:
            List of related file paths (relative)
        """
        target_file = self.repo_path / file_path
        if not target_file.exists():
            logger.warning(f"Target file does not exist: {file_path}")
            return []

        related_files = []

        try:
            # 1. Files in the same directory
            same_dir_files = [
                str(f.relative_to(self.repo_path))
                for f in target_file.parent.glob("*.py")
                if f != target_file and f.is_file()
            ]
            related_files.extend(same_dir_files[:5])

            # 2. __init__.py in parent directory
            parent_init = target_file.parent / "__init__.py"
            if parent_init.exists() and parent_init != target_file:
                related_files.append(str(parent_init.relative_to(self.repo_path)))

            # 3. Test files (if target is not a test)
            if "test" not in file_path.lower():
                test_patterns = [
                    f"test_{target_file.name}",
                    f"{target_file.stem}_test.py",
                    f"tests/test_{target_file.name}",
                ]
                for pattern in test_patterns:
                    test_candidates = list(self.repo_path.rglob(pattern))
                    for test_file in test_candidates:
                        related_files.append(str(test_file.relative_to(self.repo_path)))

            # 4. Files that import this module (expensive, so limited)
            try:
                module_name = self._get_module_name(file_path)
                if module_name:
                    importing_files = self._find_files_importing_module(module_name, limit=3)
                    related_files.extend(importing_files)
            except Exception as e:
                logger.debug(f"Could not find importing files: {e}")

            # Remove duplicates and limit
            unique_related = list(dict.fromkeys(related_files))
            result = [f for f in unique_related if f != file_path][:max_files]

            logger.info(f"Found {len(result)} related files for {file_path}")
            return result

        except Exception as e:
            logger.error(f"Error finding related files for {file_path}: {e}")
            return []

    def get_project_structure(
        self, max_depth: int = 3, include_files: bool = True
    ) -> dict[str, Any]:
        """Get directory tree structure of the project.

        Args:
            max_depth: Maximum depth to traverse
            include_files: Whether to include files in the structure

        Returns:
            Dictionary representing the directory tree structure
        """
        try:
            structure = self._build_tree_structure(
                self.repo_path, max_depth=max_depth, include_files=include_files
            )
            logger.info("Built project structure tree")
            return structure

        except Exception as e:
            logger.error(f"Error building project structure: {e}")
            raise

    # ============================================================================
    # Codebase Analysis
    # ============================================================================

    def analyze_codebase(self, target_area: str | None = None) -> dict[str, Any]:
        """Analyze codebase structure and patterns.

        Args:
            target_area: Optional specific directory/module to focus analysis on

        Returns:
            Dictionary with analysis results including structure, conventions, and statistics
        """
        try:
            analysis: dict[str, Any] = {
                "repository_path": str(self.repo_path),
                "target_area": target_area,
                "statistics": {},
                "structure": {},
                "conventions": {},
                "dependencies": {},
            }

            # Find all Python files
            python_files = self.find_python_files()

            # Filter to target area if specified
            if target_area:
                python_files = [f for f in python_files if f.startswith(target_area.strip("/"))]

            # Statistics
            analysis["statistics"] = {
                "total_python_files": len(python_files),
                "total_lines": 0,
                "total_functions": 0,
                "total_classes": 0,
            }

            # Analyze a sample of files for conventions
            sample_size = min(20, len(python_files))
            sample_files = python_files[:sample_size]

            for file_path in sample_files:
                try:
                    content = (self.repo_path / file_path).read_text(encoding="utf-8")
                    analysis["statistics"]["total_lines"] += len(content.splitlines())
                    analysis["statistics"]["total_functions"] += len(
                        re.findall(r"^\s*def\s+\w+", content, re.MULTILINE)
                    )
                    analysis["statistics"]["total_classes"] += len(
                        re.findall(r"^\s*class\s+\w+", content, re.MULTILINE)
                    )
                except Exception as e:
                    logger.debug(f"Could not analyze {file_path}: {e}")

            # Extract conventions from sample files
            analysis["conventions"] = self.extract_conventions(sample_files)

            # Get project structure
            analysis["structure"] = self.get_project_structure(max_depth=2)

            # Detect dependencies
            analysis["dependencies"] = self._detect_dependencies()

            logger.info(f"Completed codebase analysis ({len(python_files)} files)")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing codebase: {e}")
            raise

    def identify_target_files(self, requirements: list[str], max_results: int = 10) -> list[str]:
        """Identify files that should be modified based on requirements.

        Args:
            requirements: List of requirement strings to analyze
            max_results: Maximum number of files to return

        Returns:
            List of file paths that likely need modification
        """
        try:
            # Extract keywords from requirements
            keywords = self._extract_keywords_from_requirements(requirements)
            logger.debug(f"Extracted keywords: {keywords}")

            # Find Python files
            python_files = self.find_python_files()

            # Score files based on keyword matches
            file_scores = []
            for file_path in python_files:
                score = self._score_file_relevance(file_path, keywords)
                if score > 0:
                    file_scores.append((file_path, score))

            # Sort by score descending
            file_scores.sort(key=lambda x: x[1], reverse=True)

            # Return top matches
            target_files = [f for f, _ in file_scores[:max_results]]

            logger.info(f"Identified {len(target_files)} target files from requirements")
            return target_files

        except Exception as e:
            logger.error(f"Error identifying target files: {e}")
            raise

    # ============================================================================
    # Convention Extraction
    # ============================================================================

    def extract_conventions(self, file_paths: list[str]) -> dict[str, Any]:
        """Extract coding conventions from a list of files.

        Args:
            file_paths: List of relative file paths to analyze

        Returns:
            Dictionary with detected conventions
        """
        try:
            conventions: dict[str, Any] = {
                "naming_style": {},
                "import_style": {},
                "docstring_style": {},
                "class_patterns": {},
                "type_hints_usage": {},
            }

            # Collect samples
            naming_samples: dict[str, list[str]] = {
                "functions": [],
                "classes": [],
                "variables": [],
            }
            import_samples: list[str] = []
            docstring_samples: list[str] = []
            has_type_hints = 0
            total_functions = 0

            for file_path in file_paths:
                try:
                    full_path = self.repo_path / file_path
                    if not full_path.exists():
                        continue

                    content = full_path.read_text(encoding="utf-8")

                    # Extract naming patterns
                    naming_samples["functions"].extend(
                        re.findall(r"^\s*def\s+(\w+)", content, re.MULTILINE)
                    )
                    naming_samples["classes"].extend(
                        re.findall(r"^\s*class\s+(\w+)", content, re.MULTILINE)
                    )

                    # Extract import patterns
                    imports = re.findall(
                        r"^(?:from\s+[\w.]+\s+)?import\s+.+$", content, re.MULTILINE
                    )
                    import_samples.extend(imports[:5])  # Sample first 5 imports

                    # Extract docstrings
                    docstrings = re.findall(r'^\s*"""(.+?)"""', content, re.MULTILINE | re.DOTALL)
                    docstring_samples.extend(docstrings[:3])

                    # Check type hints
                    functions = re.findall(r"^\s*def\s+\w+\s*\([^)]*\)", content, re.MULTILINE)
                    total_functions += len(functions)
                    has_type_hints += sum(1 for f in functions if "->" in f or ":" in f)

                except Exception as e:
                    logger.debug(f"Could not extract conventions from {file_path}: {e}")

            # Analyze naming conventions
            conventions["naming_style"] = {
                "functions": self._detect_naming_convention(naming_samples["functions"]),
                "classes": self._detect_naming_convention(naming_samples["classes"]),
            }

            # Analyze import style
            conventions["import_style"] = self._analyze_import_style(import_samples)

            # Analyze docstring style
            conventions["docstring_style"] = self._analyze_docstring_style(docstring_samples)

            # Type hints usage
            type_hint_percentage = (
                (has_type_hints / total_functions * 100) if total_functions > 0 else 0
            )
            conventions["type_hints_usage"] = {
                "percentage": round(type_hint_percentage, 1),
                "recommendation": "used" if type_hint_percentage > 50 else "minimal",
            }

            logger.info(f"Extracted conventions from {len(file_paths)} files")
            return conventions

        except Exception as e:
            logger.error(f"Error extracting conventions: {e}")
            raise

    # ============================================================================
    # Context Building
    # ============================================================================

    def build_context_for_generation(
        self,
        target_files: list[str],
        max_tokens: int = 8000,
        include_related: bool = True,
    ) -> str:
        """Build context string for LLM code generation.

        Args:
            target_files: List of target file paths
            max_tokens: Approximate maximum tokens for context (rough estimate: 4 chars = 1 token)
            include_related: Whether to include related files for context

        Returns:
            Context string with file contents and structure information
        """
        try:
            context_parts = []
            chars_used = 0
            max_chars = max_tokens * 4  # Rough approximation

            # Add project structure overview
            structure = self.get_project_structure(max_depth=2, include_files=False)
            structure_str = self._format_structure_for_context(structure)
            context_parts.append("## Project Structure\n\n" + structure_str)
            chars_used += len(structure_str)

            # Add conventions
            if target_files:
                conventions = self.extract_conventions(target_files[:5])
                conventions_str = self._format_conventions_for_context(conventions)
                context_parts.append("\n\n## Code Conventions\n\n" + conventions_str)
                chars_used += len(conventions_str)

            # Add target files content
            context_parts.append("\n\n## Target Files\n")

            files_to_include = target_files.copy()
            if include_related:
                # Add some related files
                for target_file in target_files[:2]:  # Limit to avoid explosion
                    related = self.find_related_files(target_file, max_files=2)
                    files_to_include.extend(related)

            # Remove duplicates while preserving order
            files_to_include = list(dict.fromkeys(files_to_include))

            # Include file contents up to max_chars
            for file_path in files_to_include:
                if chars_used >= max_chars:
                    break

                try:
                    full_path = self.repo_path / file_path
                    if not full_path.exists():
                        continue

                    content = full_path.read_text(encoding="utf-8")
                    file_section = f"\n### {file_path}\n\n```python\n{content}\n```\n"

                    # Check if adding this file would exceed limit
                    if chars_used + len(file_section) > max_chars:
                        # Try to include partial content
                        remaining_chars = max_chars - chars_used - 200  # Leave some buffer
                        if remaining_chars > 500:  # Only if meaningful amount
                            lines = content.splitlines()
                            partial_content = "\n".join(
                                lines[: remaining_chars // 50]
                            )  # Approx lines
                            file_section = f"\n### {file_path} (partial)\n\n```python\n{partial_content}\n... (truncated)\n```\n"
                            context_parts.append(file_section)
                        break

                    context_parts.append(file_section)
                    chars_used += len(file_section)

                except Exception as e:
                    logger.debug(f"Could not include {file_path} in context: {e}")

            final_context = "".join(context_parts)

            logger.info(
                f"Built context for {len(target_files)} target files "
                f"({len(final_context)} chars, ~{len(final_context) // 4} tokens)"
            )
            return final_context

        except Exception as e:
            logger.error(f"Error building context: {e}")
            raise

    # ============================================================================
    # Private Helper Methods
    # ============================================================================

    def _should_exclude(self, path: Path, exclude_patterns: list[str]) -> bool:
        """Check if a path should be excluded based on patterns."""
        path_str = str(path)
        for pattern in exclude_patterns:
            # Handle glob-style patterns
            if "*" in pattern:
                pattern_regex = pattern.replace("*", ".*")
                if re.search(pattern_regex, path_str):
                    return True
            else:
                if pattern in path.parts or path_str.endswith(pattern):
                    return True
        return False

    def _build_tree_structure(
        self,
        directory: Path,
        current_depth: int = 0,
        max_depth: int = 3,
        include_files: bool = True,
    ) -> dict[str, Any]:
        """Recursively build directory tree structure."""
        if current_depth >= max_depth:
            return {"type": "directory", "truncated": True}

        structure: dict[str, Any] = {"type": "directory", "children": {}}

        try:
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))

            for item in items:
                # Skip excluded items
                relative = item.relative_to(self.repo_path)
                if self._should_exclude(relative, self.DEFAULT_EXCLUDE_PATTERNS):
                    continue

                if item.is_dir():
                    structure["children"][item.name] = self._build_tree_structure(
                        item, current_depth + 1, max_depth, include_files
                    )
                elif include_files and item.is_file():
                    # Only include Python files and important config files
                    if item.suffix == ".py" or item.name in [
                        "pyproject.toml",
                        "requirements.txt",
                        "setup.py",
                        "Dockerfile",
                        ".env.example",
                    ]:
                        structure["children"][item.name] = {
                            "type": "file",
                            "size": item.stat().st_size,
                        }

        except PermissionError:
            structure["error"] = "Permission denied"

        return structure

    def _get_module_name(self, file_path: str) -> str | None:
        """Convert file path to Python module name."""
        try:
            path = Path(file_path)
            parts_list = list(path.parts)

            # Remove .py extension
            if parts_list[-1].endswith(".py"):
                parts_list[-1] = parts_list[-1][:-3]

            # Skip __init__ in module name
            if parts_list[-1] == "__init__":
                parts_list = parts_list[:-1]

            # Convert to module path
            module_name = ".".join(parts_list)
            return module_name

        except Exception:
            return None

    def _find_files_importing_module(self, module_name: str, limit: int = 5) -> list[str]:
        """Find files that import a specific module."""
        importing_files = []

        python_files = self.find_python_files()
        for file_path in python_files[:50]:  # Limit search to avoid being too slow
            try:
                content = (self.repo_path / file_path).read_text(encoding="utf-8")
                # Check for import statements
                import_pattern = (
                    f"(?:from\\s+{re.escape(module_name)}|import\\s+{re.escape(module_name)})"
                )
                if re.search(import_pattern, content):
                    importing_files.append(file_path)
                    if len(importing_files) >= limit:
                        break
            except Exception:
                continue

        return importing_files

    def _extract_keywords_from_requirements(self, requirements: list[str]) -> set[str]:
        """Extract relevant keywords from requirements."""
        keywords: set[str] = set()

        # Common technical terms to extract
        for req in requirements:
            # Extract words that look like identifiers or technical terms
            words = re.findall(r"\b[a-z_][a-z0-9_]*\b", req.lower())

            # Filter out common words
            stopwords = {
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "from",
                "as",
                "is",
                "was",
                "are",
                "were",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "should",
                "could",
                "may",
                "might",
                "must",
                "can",
                "this",
                "that",
                "these",
                "those",
            }

            keywords.update(w for w in words if w not in stopwords and len(w) > 2)

        return keywords

    def _score_file_relevance(self, file_path: str, keywords: set[str]) -> int:
        """Score a file's relevance to requirements based on keywords."""
        score = 0

        # Check file path
        path_lower = file_path.lower()
        for keyword in keywords:
            if keyword in path_lower:
                score += 5  # Path match is strong signal

        # Check file content
        try:
            content = (self.repo_path / file_path).read_text(encoding="utf-8").lower()
            for keyword in keywords:
                # Count occurrences (capped)
                count = min(content.count(keyword), 10)
                score += count

        except Exception:
            pass

        return score

    def _detect_naming_convention(self, names: list[str]) -> str:
        """Detect the predominant naming convention from a list of names."""
        if not names:
            return "unknown"

        # Count patterns
        snake_case = sum(1 for name in names if "_" in name and name.islower())
        camel_case = sum(
            1 for name in names if name[0].islower() and any(c.isupper() for c in name)
        )
        pascal_case = sum(1 for name in names if name[0].isupper())

        # Determine predominant style
        total = len(names)
        if snake_case / total > 0.6:
            return "snake_case"
        elif camel_case / total > 0.6:
            return "camelCase"
        elif pascal_case / total > 0.6:
            return "PascalCase"
        else:
            return "mixed"

    def _analyze_import_style(self, import_samples: list[str]) -> dict[str, Any]:
        """Analyze import statement patterns."""
        if not import_samples:
            return {"style": "unknown", "examples": []}

        relative_imports = sum(1 for imp in import_samples if "from ." in imp)

        grouped_imports = sum(1 for imp in import_samples if "," in imp)

        return {
            "relative_imports_percentage": round(relative_imports / len(import_samples) * 100, 1),
            "uses_grouped_imports": grouped_imports > 0,
            "examples": import_samples[:3],
        }

    def _analyze_docstring_style(self, docstring_samples: list[str]) -> dict[str, Any]:
        """Analyze docstring patterns."""
        if not docstring_samples:
            return {"style": "unknown", "detected": False}

        # Detect common styles
        google_style = sum(
            1 for ds in docstring_samples if "Args:" in ds or "Returns:" in ds or "Raises:" in ds
        )
        numpy_style = sum(1 for ds in docstring_samples if "Parameters" in ds or "--------" in ds)
        sphinx_style = sum(1 for ds in docstring_samples if ":param" in ds or ":type" in ds)

        total = len(docstring_samples)
        if google_style / total > 0.5:
            style = "Google"
        elif numpy_style / total > 0.5:
            style = "NumPy"
        elif sphinx_style / total > 0.5:
            style = "Sphinx"
        else:
            style = "mixed/simple"

        return {
            "style": style,
            "detected": True,
            "sample_count": len(docstring_samples),
        }

    def _detect_dependencies(self) -> dict[str, list[str]]:
        """Detect project dependencies from common files."""
        dependencies: dict[str, list[str]] = {"pyproject.toml": [], "requirements.txt": []}

        try:
            # Check pyproject.toml
            pyproject_path = self.repo_path / "pyproject.toml"
            if pyproject_path.exists():
                content = pyproject_path.read_text(encoding="utf-8")
                # Extract dependencies from [project.dependencies]
                deps = re.findall(r'^\s*"([^"]+)"', content, re.MULTILINE)
                dependencies["pyproject.toml"] = [
                    d.split("[")[0].split("==")[0].split(">=")[0] for d in deps[:10]
                ]

            # Check requirements.txt
            requirements_path = self.repo_path / "requirements.txt"
            if requirements_path.exists():
                content = requirements_path.read_text(encoding="utf-8")
                deps = [
                    line.strip().split("==")[0].split(">=")[0]
                    for line in content.splitlines()
                    if line.strip() and not line.startswith("#")
                ]
                dependencies["requirements.txt"] = deps[:10]

        except Exception as e:
            logger.debug(f"Could not detect dependencies: {e}")

        return dependencies

    def _format_structure_for_context(self, structure: dict[str, Any]) -> str:
        """Format structure dictionary as readable tree."""
        lines = []

        def format_tree(node: dict[str, Any], prefix: str = "", is_last: bool = True) -> None:
            if node.get("type") == "directory":
                children = node.get("children", {})
                items = list(children.items())

                for i, (name, child) in enumerate(items):
                    is_last_child = i == len(items) - 1
                    connector = "└── " if is_last_child else "├── "
                    lines.append(f"{prefix}{connector}{name}")

                    if child.get("type") == "directory":
                        extension = "    " if is_last_child else "│   "
                        format_tree(child, prefix + extension, is_last_child)

        format_tree(structure)
        return "\n".join(lines[:50])  # Limit lines

    def _format_conventions_for_context(self, conventions: dict[str, Any]) -> str:
        """Format conventions dictionary as readable text."""
        lines = []

        # Naming conventions
        if "naming_style" in conventions:
            lines.append("**Naming Conventions:**")
            for key, value in conventions["naming_style"].items():
                lines.append(f"- {key}: {value}")

        # Import style
        if "import_style" in conventions:
            lines.append("\n**Import Style:**")
            import_style = conventions["import_style"]
            if import_style.get("examples"):
                lines.append(f"- Examples: {import_style['examples'][0]}")

        # Docstring style
        if "docstring_style" in conventions:
            ds = conventions["docstring_style"]
            if ds.get("detected"):
                lines.append(f"\n**Docstring Style:** {ds.get('style', 'unknown')}")

        # Type hints
        if "type_hints_usage" in conventions:
            th = conventions["type_hints_usage"]
            lines.append(
                f"\n**Type Hints:** {th.get('recommendation', 'unknown')} ({th.get('percentage', 0)}% coverage)"
            )

        return "\n".join(lines)
