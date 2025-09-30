from drf_spectacular.extensions import OpenApiAuthenticationExtension

class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'api_key.authentication.APIKeyAuthentication'  # full dotted path!
    name = 'APIKeyAuth'  # this will show up in the schema

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API Key",
        }
