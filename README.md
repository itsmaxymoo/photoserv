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

## Installation

* `docker compose up -d`

## Configuration

//