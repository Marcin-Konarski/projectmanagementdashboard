# Project Management Profiles Dashboard

Backend API built with FastAPI and SQLModel.

## Local Development Workflow

This project uses `ruff` for fast Python linting and formatting, along with `pre-commit` hooks to ensure code quality before pushing.

### 1. Install Dependencies
Make sure you have installed both standard and development dependencies:
```bash
pip install -r backend/requirements.txt
pip install -r backend/requirements.dev.txt
```

### 2. Set Up Pre-commit Hooks
To automatically run format checks exactly like the CI pipeline before every commit, install the hooks:
```bash
pre-commit install
```
Now, whenever you run `git commit`, `ruff` will automatically format and lint your staged files.

### 3. Usage (Manual Commands)
If you want to manually run standard code quality checks:
* **Linting:**
  ```bash
  ruff check .
  ```
  *(To automatically fix safe issues: `ruff check --fix .`)*

* **Formatting:**
  ```bash
  ruff format .
  ```

* **Running Tests:**
  ```bash
  PYTHONPATH=. pytest tests/
  ```

### Continuous Integration
A GitHub Action is configured (`.github/workflows/ci.yml`) to verify:
- Complete test suite passes.
- Code conforms strictly to `ruff`'s standards.
- Successful builds push a docker image to Docker Hub (ensure `DOCKER_HUB_PASSWORD` is configured as a GitHub Secret).
