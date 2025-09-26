# Photoserv

Photoserv is an application for photographers, artists, or similar who want a system to act as a single source of truth
for their publicly published photos.

| | |
| --- | --- |
| ![Photo detail](docs/screenshots/photo_detail.png) | ![Album detail](docs/screenshots/album_detail.png) |
| ![Size list](docs/screenshots/size_list.png) | ![API Key list](docs/screenshots/api_key_list.png) |

## Features

* Upload and categorize photos by albums and tags.
* Extract metadata from photos for consumption in other systems.
* Exposes a REST api for applications and integrations to interact with your data.
    * For example, a photo portfolio website in Astro.js can consume this.
* Define multiple sizes for your photos to be available in.
* OIDC and simple auth optional.

## Configuration

Configure the environment variables; `cp example.env .env`

```env
# openssl rand -hex 64
APP_KEY=""

DEBUG_MODE=false # always false in production

TIME_ZONE=America/New_York

DATABASE_ENGINE=postgres # postgres or sqlite
DATABASE_USER=photoserv
DATABASE_PASSWORD=photoserv
DATABASE_NAME=photoserv
DATABASE_HOST=database
DATABASE_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

ALLOWED_HOSTS=127.0.0.1,localhost

SIMPLE_AUTH=True

OIDC_NAME=Single Sign On Button Label
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_AUTHORIZATION_ENDPOINT=
OIDC_TOKEN_ENDPOINT=
OIDC_USER_ENDPOINT=
OIDC_JWKS_ENDPOINT=
OIDC_SIGN_ALGO=RS256 # optional
```

OIDC Callback URL: `<your-photoserv-root>/login/oidc/callback/`  
Example: `https://photoserv.maxloiacono.com/login/oidc/callback/`

## Installation

* `docker compose up -d`

## Roadmap

1. Better documentation
2. ~~Mobile layout~~
3. ~~Add feature to hide photos from the UI~~
4. Consistency checker
5. API documentation
6. Security/traefik documentation
7. ~~Album Parents~~
8. Jobs overview
9. ~~API response metadata~~
10. ~~EV comp filter~~
11. 1.0 release
12. 1.1: Webhooks
13. 1.2: Social integration
