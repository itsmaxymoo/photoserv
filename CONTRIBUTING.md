# Contributing to Photoserv

# 1.0 Branch Committed Changes:

* update refs to old repo
* Publishing Schedule
* Remove integration: scan for plugins
* UI/frontend permissions
* Integrations subscribe to a publishing channel
* All integrations shall be python based
* Photo calendar shall be based on publishing channels
* Rename 'core' to 'media'
* Newer API schema
    * Session Auth supported
    * Read/write endpoints for resources (admin api)
    * Write requires permission on API key
    * User based API
    * media.full_api_access
* Authentication is now enforced; no anonymous mode.
* Implement publishing channels; publishing logic fully owned by Media
* A photo shall not be published until all sizes are generated
* Remove "Create Multiple" photos.
* Official icon/logo
* new namespace
* breaking: most api endpoints return results in results element
* Channel fork

## Development

### Setup

1. Create venv
2. `npm ci`
3. `./dev.sh`

### Secret Environment Variables

* `IS_CONTAINER` - Set to `true` to simulate running in Docker (you likely don't want to use this)
* `PLUGINS_PATH` - Override default plugin directory (`./plugins`) for local development... i.e pointing to a cloned copy of the plugins repository.

### Testing

**Always add or update tests for code changes**.

```bash
python manage.py test
```

Run tests before every commit.

## Coding Standards

**YOUR PR WILL BE REJECTED IF THESE STANDARDS ARE NOT MET.**

### In General

* NO EMOJIS in source code, commit messages, Markdown documentation.

### Python

* Follow PEP 8 for imports (top of file)

### Templates

* Use DaisyUI theme variables. Do not explicitly color text or elements.
* Do not add border radius styles or classes.

Example:

```html
<!-- Good: Uses theme color -->
<button class="btn btn-primary">Submit</button>

<!-- Bad: Explicit colors -->
<button class="bg-blue-500 text-white rounded-lg">Submit</button>

<!-- Bad: Border radius -->
<div class="rounded-md">Content</div>
```

### Documentation

* Use `*` for bullet lists.
* There should be a blank line between headings and the following text.

### Before Committing

0. Understand your code will be under the MIT License.
1. Run `python manage.py test`
2. Verify all tests pass
3. Review code style guidelines above

## TODO (Wanted Contributions)

* Automatic albums based on photo data/metadata (e.g., camera model, location)
* Real implementation of a dashboard (home app)?... This is very low priority.
* Photo map
* Bulk photo editing for select actions

## Project Structure

```
photoserv/
├── api_key/           # API key management and DRF authentication
├── core/              # Legacy migration bridge retained for upgrades to 1.0
├── errorhtml/         # Custom HTTP error handlers
├── home/              # Root URL redirect
├── iam/               # Users, authentication, groups, and permissions
├── integration/       # Integration plugin configuration, execution, and history
├── job_overview/      # Celery task monitoring UI
├── media/             # Photos, albums, tags, sizes, channels, and REST API
├── official_plugins/  # Integration plugins bundled with Photoserv
├── photoserv/         # Project settings, URL configuration, and Celery setup
├── photoserv_plugin/  # Plugin API and base classes
├── plugins/           # Locally installed integration plugins (don't upload stuff here)
├── templates/         # HTML templates
├── static/            # CSS, JavaScript, images, and other static assets
└── docs/              # Project documentation and screenshots
```

## Resources

* **README.md** - Installation and configuration
* **Swagger** - `https://<your-instance>/swagger` (API documentation)
* **GitHub** - https://github.com/itsmaxymoo/photoserv
