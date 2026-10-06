"""Photoserv plugin that performs a configured HTTP request on global changes."""

import urllib.error
import urllib.request

from photoserv_plugin import PhotoservPlugin


__plugin_name__ = "Web Request"
__plugin_uuid__ = "4a6b6fb6-5d66-4d9e-9ad8-1eb5a374eaad"
__plugin_version__ = "1.0.0"
__plugin_author__ = "Max Loiacono"
__plugin_website__ = "https://github.com/itsmaxymoo/photoserv"

__plugin_config__ = {
    "url": "(string, required) URL to request",
    "method": "(string, required) HTTP method, for example GET or POST",
    "headers": "(object, optional) HTTP request headers",
    "body": "(string, optional)",
}


class WebRequestPlugin(PhotoservPlugin):
    """Dispatch a configured HTTP request for each global change event."""

    def __init__(self, config, photoserv):
        super().__init__(config, photoserv)

        self.url = self._required_string(config, "url")
        self.method = self._required_string(config, "method").upper()
        self.headers = config.get("headers", {})
        self.body = config.get("body", "")

        if not isinstance(self.headers, dict):
            raise ValueError("headers must be an object")
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in self.headers.items()):
            raise ValueError("headers must contain only string keys and values")
        if not isinstance(self.body, str):
            raise ValueError("body must be a string")

    @staticmethod
    def _required_string(config, key):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value

    def on_global_change(self, **kwargs):
        """Make the configured request when Photoserv has a global change."""
        request = urllib.request.Request(
            self.url,
            data=self.body.encode("utf-8") if self.body else None,
            headers=self.headers,
            method=self.method,
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                self.logger.info(
                    "Web request completed: %s %s returned %s %s\n%s",
                    self.method,
                    self.url,
                    response.status,
                    response.reason,
                    response_body,
                )
        except urllib.error.HTTPError as error:
            response_body = error.read().decode("utf-8", errors="replace")
            self.logger.error(
                "Web request failed: %s %s returned %s %s\n%s",
                self.method,
                self.url,
                error.code,
                error.reason,
                response_body,
            )
            raise
        except urllib.error.URLError as error:
            self.logger.error("Web request failed: %s %s: %s", self.method, self.url, error.reason)
            raise
