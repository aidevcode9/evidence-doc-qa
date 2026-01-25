# Contributing to Evidence-Bound

Thank you for your interest in contributing to Evidence-Bound! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and constructive in all interactions. We welcome contributors of all experience levels.

## Getting Started

1. **Fork the repository** and clone it locally
2. **Set up the development environment** following the [README](README.md)
3. **Create a branch** for your changes: `git checkout -b feature/your-feature`

## Development Workflow

### Test-Driven Development (TDD)

We enforce TDD for all features:

```
RED    → Write a test that fails (proves the test works)
GREEN  → Write minimum code to pass
REFACTOR → Clean up while keeping tests green
COMMIT → Only after all tests pass
```

### Code Quality

Before submitting a PR, ensure all quality gates pass:

```bash
# Linting
ruff check apps/ --fix
ruff format apps/

# Type checking
mypy apps/api/app --strict

# Tests
pytest tests/ -v

# Evaluations
pytest evals/ -v
```

### Commit Messages

Use conventional commit format:

```
type(scope): description

# Types: feat, fix, test, docs, refactor, chore
# Examples:
feat(retrieval): add hybrid BM25+vector search
fix(evidence): handle empty citation spans
test(policy): add confidence threshold tests
docs(readme): update installation instructions
```

## Pull Request Process

1. **Update documentation** if you've changed APIs or behavior
2. **Add tests** for new functionality
3. **Ensure all CI checks pass**
4. **Request review** from maintainers
5. **Address feedback** promptly

### PR Title Format

```
type(scope): Short description
```

### PR Description

Include:
- **Summary**: What does this PR do?
- **Motivation**: Why is this change needed?
- **Testing**: How was this tested?
- **Breaking Changes**: Any breaking changes?

## Architecture Guidelines

### Core Invariants

These must never be violated:

1. **Every answer requires citations** - No response without evidence
2. **Confidence threshold is enforced** - Below 0.70 = refusal
3. **No PII in logs** - All logging uses `telemetry.py` redaction
4. **Multi-tenant isolation** - Every query scoped by `tenant_id` + `matter_id`

### Key Files

Before modifying these, discuss with maintainers:

- `app/policy.py` - Pre/post-LLM gates
- `app/evidence.py` - Citation validation
- `app/retrieval.py` - Search logic
- `app/config.py` - Environment configuration

### Adding New Features

1. Check if a similar feature exists in `REQUIREMENTS.md`
2. Create a feature request issue first for major changes
3. Follow the existing patterns in the codebase
4. Add both unit tests and integration tests

## Reporting Issues

### Bug Reports

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs (with PII redacted)

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternatives considered

## Questions?

- Open a [GitHub Issue](https://github.com/YOUR_USERNAME/evidence-doc-qa/issues)
- Check existing documentation in `/docs`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
