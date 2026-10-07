# Web Request Plugin

Runs a configured HTTP request whenever Photoserv emits a global change event. It does not subscribe to photo publish or unpublish events.

## Configuration

Configure the plugin with a JSON object:

```json
{
  "url": "https://example.com/hooks/photoserv",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer ${WEBHOOK_TOKEN}",
    "Content-Type": "application/json"
  },
  "body": "{\"event\": \"photoserv.global_change\"}"
}
```

Environment variables in configuration strings use `${VARIABLE_NAME}` syntax.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `url` | string | Yes | Destination URL. |
| `method` | string | Yes | HTTP method, such as `GET`, `POST`, `PUT`, or `DELETE`. |
| `headers` | object | No | HTTP headers as string key/value pairs. Defaults to `{}`. |
| `body` | string | No | UTF-8 request body. Defaults to an empty string. |

## Behavior

Enable **Receive global events** for this integration. On every global change, the plugin sends one request using the configured URL, method, headers, and body. A non-2xx response or connection error marks the integration run as failed and records the response or error in its log.
