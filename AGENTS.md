# Photoserv AGENTS.md file

## Dev environment tips
- Use the secret environment variable PLUGINS_PATH to point to your local plugins folder if necessary.
- Never use emojis anywhere in your output.
- Follow PEP 8 guidelines for imports (top of file), with the only exception being importing integration within the core PhotoForm.
- Do not explicitly color text or other elements in HTML templates; instead use the builtin DaisyUI theme colors but only when appropriate.
- Do not add any border radius styles or classes.
- DO NOT use conventional commit messages; leave that to the maintainers.

## Testing instructions
- Be sure to source the local `.venv` before running tests.
- To test: run `python manage.py test`.
- Add or update tests for the code you change, even if nobody asked.

## PR instructions
- Title format: [Photoserv] <Title>
- Always run `python manage.py test` before committing.
