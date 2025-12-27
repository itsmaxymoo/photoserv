# Contributing to Photoserv

See **[AGENTS.md](AGENTS.md)** for AI assistant guidelines.

## Environment Setup

### Development
```bash
# Clone and enter directory
git clone https://github.com/photoserv/photoserv.git
cd photoserv

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp example.env .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Start development server
./dev.sh
```

### Secret Environment Variables
* `IS_CONTAINER` - Set to `true` when running in Docker (auto-detected in most cases)
* `PLUGINS_PATH` - Override default plugin directory for local development

## Architecture Overview

### Django Apps
* **core** - Photos, albums, tags, sizes, metadata. Core business logic and Celery tasks.
* **api_key** - API key generation and authentication for REST API.
* **public_rest_api** - Read-only REST API (DRF) for external consumption. Requires API key.
* **integration** - Plugin system (user-uploadable Python) and webhooks. Event-driven architecture.
* **iam** - User authentication (simple auth + OIDC).
* **job_overview** - Celery task monitoring UI.
* **home** - Placeholder for dashboard functionality.

### Hierarchy (Respect it)

* **Core** contains core business logic and models. It only depends on "utility" apps.
    * Caveat: `core.PhotoForm` imports from `integration` because I couldn't find a better way to do this.
    It is done in such a way to avoid circular dependency and provide loose-ish coupling.
* **Public REST API** depends on core to expose read-only endpoints for external consumption (including integration).
* **Integration** depends on core and public_rest_api to extend functionality via plugins and webhooks.
* **Home** is a placeholder for dashboard functionality and depends on core.
* **All other apps** are utility apps with no dependencies on core or each other. They can be lifted right into other projects if needed.

### Key Concepts
* **Publishing workflow**: Photos publish when `publish_date <= now()` and `hidden=False`. Triggers signals.
* **Multi-size generation**: Celery tasks generate configured photo sizes on upload.
* **Plugin system**: Sandboxed Python plugins respond to `on_photo_publish`, `on_photo_unpublish`, `on_global_change`.
* **Signals**: Django signals (`photo_published`, `photo_unpublished`) drive integrations.


## Testing

**Always add or update tests for code changes**, even if not requested.

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run all tests
python manage.py test

# Run specific app tests
python manage.py test core
python manage.py test integration
```

Run tests before every commit.

## Code Style

### Python
* Follow PEP 8 for imports (top of file)
* Exception: Importing `integration` within `core.PhotoForm` is allowed to avoid circular dependency and loose-ish coupling.

### HTML/CSS
* Use DaisyUI theme colors only when appropriate. Do not explicitly color text or elements.
* Do not add border radius styles or classes.
* Tailwind compiler searches system-installed Python modules in Docker. If adding Python dependencies, bump Python version in `app.css` to match Dockerfile.

### Templates
```html
<!-- Good: Uses theme color -->
<button class="btn btn-primary">Submit</button>

<!-- Bad: Explicit colors -->
<button class="bg-blue-500 text-white rounded-lg">Submit</button>

<!-- Bad: Border radius -->
<div class="rounded-md">Content</div>
```

## Pull Requests

### Title Format
```
[Photoserv] <feat/fix>: Brief description
```

Examples:
* `[Photoserv] Add photo view counter`
* `[Photoserv] Fix plugin execution error handling`
* `[Photoserv] Update DaisyUI theme colors`

### Before Committing
0. Understand your code will be under the MIT License.
1. Run `python manage.py test`
2. Verify all tests pass
3. Review code style guidelines above
4. **DO NOT** use conventional commit messages; leave that to the maintainers.

## Wanted Features/Fixes

### Bugs
* Field error text renders white, should be red
* OIDC reauthorization redirect drops POST requests, essentially losing form submissions.

### Feature Requests
* **Photo Calendar**: Month-by-month grid showing upcoming photos by publish date. Photos listed chronologically within each day. Add link on photo form and before photo "Create" buttons (style: `btn-secondary`).

## Project Structure

```
photoserv/
├── api_key/           # API key management
├── core/              # Photos, albums, tags (core logic)
├── iam/               # User authentication
├── integration/       # Plugins & webhooks
├── job_overview/      # Celery task monitoring
├── public_rest_api/   # REST API endpoints
├── home/              # Dashboard
├── photoserv/         # Django settings
├── photoserv_plugin/  # Plugin base classes
├── plugins/           # User-uploaded plugins
├── templates/         # HTML templates
├── static/            # CSS/JS assets
└── content/           # Photo storage (Docker volume)
```

## Resources

* **README.md** - Installation and configuration
* **AGENTS.md** - AI assistant guidelines
* **Swagger** - `https://<your-instance>/swagger` (API documentation)
* **GitHub** - https://github.com/photoserv/photoserv
