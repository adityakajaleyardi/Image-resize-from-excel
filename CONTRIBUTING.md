# Contributing to Image Processor

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on code, not the coder
- Help others learn and grow

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/image-processor.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Create a virtual environment: `python -m venv venv`
5. Activate it: `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
6. Install dependencies: `pip install -r requirements.txt`

## Development Workflow

### Before Coding
- Check existing issues/PRs to avoid duplicates
- Create an issue to discuss major changes
- For small fixes, you can go straight to PR

### While Coding
- Follow PEP 8 style guide
- Add comments for complex logic
- Keep functions focused and testable
- Update docstrings
- Add/update tests as needed

### Code Style
- Use meaningful variable names
- Maximum line length: 120 characters
- Use type hints where practical
- Follow existing code patterns

## Testing

Before submitting:
```bash
# Run linting
flake8 image_processor.py

# Format code (optional)
black image_processor.py

# Test the script with sample data
python image_processor.py
```

## Commit Messages

Write clear commit messages:
```
feat: Add new image format support (XYZ)
fix: Correct timeout issue in URL download
docs: Update README with new configuration option
refactor: Simplify naming logic
test: Add unit tests for image resizing
```

Format: `[type]: [description]`

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `refactor` - Code refactoring
- `test` - Adding/updating tests
- `perf` - Performance improvements
- `chore` - Build/dependency updates

## Pull Request Process

1. Update README.md with any new features or changes
2. Update CHANGELOG.md with version and changes
3. Ensure code passes linting and formatting checks
4. Provide clear description of changes
5. Link related issues
6. Request review from maintainers

### PR Description Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Related Issues
Fixes #(issue number)

## Testing Done
Describe how you tested the changes.

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Tested with sample data
```

## Reporting Issues

When reporting bugs, include:
- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Sample data (if possible, anonymized)
- Error messages and logs

## Feature Requests

When suggesting features:
- Clear description of the feature
- Use cases and examples
- Expected behavior
- Potential implementation approach

## Documentation

- Keep README.md updated
- Add docstrings to functions
- Comment complex logic
- Document configuration options
- Include usage examples

## Release Process

Maintainers will:
1. Review and merge PRs
2. Update version numbers
3. Update CHANGELOG.md
4. Create GitHub release
5. Update documentation

## Questions?

- Open an issue for questions
- Check existing documentation
- Look at similar implementations in code

## Recognition

Contributors will be recognized in:
- CHANGELOG.md
- Contributors section (TBD)

Thank you for contributing! 🎉
