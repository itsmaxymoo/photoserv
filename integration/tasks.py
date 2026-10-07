import functools
from django.core.cache import cache
from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from .models import IntegrationCaller, IntegrationPlugin, RunResult
from .services import discover_plugin_modules
from datetime import timedelta
from django.utils import timezone


@shared_task
def call_integration_plugin_signal(signal_name, data=None, channel_id=None):
    """
    Call plugin methods based on signal name.
    
    Passes serialized data to plugins instead of model instances to:
    - Prevent direct database access
    - Maintain API compatibility
    - Avoid exposing internal implementation details

    Args:
        signal_name: Name of the integration method to call
        data: Optional dict of serialized data to pass to the plugin method
        channel_id: Dispatch photo events only to integrations subscribed to this channel.
    """
    plugins = IntegrationPlugin.objects.filter(active=True)
    if signal_name != "on_global_change":
        plugins = plugins.filter(channel_id=channel_id)
    
    called_count = 0
    for plugin in plugins:
        if not plugin.valid:
            continue

        try:
            # Build method args based on signal name
            if signal_name != "on_global_change":
                method_args = (data,)
            else:
                method_args = (data,) if data else ()
            
            plugin.run(
                IntegrationCaller.EVENT_SCHEDULER,
                method_name=signal_name,
                method_args=method_args
            )
            called_count += 1
        except Exception:
            # Continue even if one plugin fails
            pass

    return f"Called {signal_name} on {called_count} plugins"


def debounced_task(key_generator, delay=settings.INTEGRATION_QUEUE_DELAY):
    """
    Debounced task decorator using a counter-based approach.
    Increments a counter on each call, decrements after delay.
    Only executes if counter reaches 0 after decrement.
    """
    def decorator(func):
        @shared_task(bind=True, track_started=False, name=f"{func.__module__}.{func.__name__}")
        @functools.wraps(func)
        def celery_task(self, *args, **kwargs):
            # Generate the debounce key
            key = key_generator(*args, **kwargs)
            counter_key = f"debounce:{key}:counter"
            
            # Decrement the counter
            try:
                count = cache.decr(counter_key)
            except ValueError:
                # Key doesn't exist or isn't an integer, ignore this task
                raise Ignore()
            
            # If counter is 0, execute the task (we're the last one)
            if count == 0:
                cache.delete(counter_key)
                return func(*args, **kwargs)
            else:
                # Someone else called after us, ignore
                raise Ignore()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate the debounce key
            key = key_generator(*args, **kwargs)
            counter_key = f"debounce:{key}:counter"
            
            # Set a reasonable timeout that gets refreshed on every call
            # This prevents memory leaks while ensuring the key lives long enough
            timeout = delay + 3600  # delay + 1 hour buffer
            
            try:
                cache.incr(counter_key)
                # Refresh timeout on every increment - key lives as long as calls keep coming
                cache.touch(counter_key, timeout=timeout)
            except ValueError:
                # Key doesn't exist, create it
                cache.set(counter_key, 1, timeout=timeout)
            
            # Schedule task to run after delay
            celery_task.apply_async(args=args, kwargs=kwargs, countdown=delay)
            return True

        wrapper.celery_task = celery_task
        return wrapper
    return decorator


def queue_global_integrations(*args, **kwargs):
    """Queue active integration plugins subscribed to global events."""
    call_integration_plugin_signal.delay("on_global_change")

    return "Queued global integration dispatch."


call_queue_global_integrations = debounced_task(
    lambda *a, **k: "queue_global_integrations",
    delay=30 if settings.DEBUG else settings.INTEGRATION_QUEUE_DELAY
)(queue_global_integrations)


@shared_task
def scan_plugins():
    """
    Scan the configured plugin directories for new plugin modules.
    Creates IntegrationPlugin entries for any modules that don't already have one.
    """
    created_count = 0
    for module in discover_plugin_modules():
        if not IntegrationPlugin.objects.filter(module=module).exists():
            try:
                IntegrationPlugin.objects.create(
                    module=module,
                    active=False  # Start as inactive for safety
                )
                created_count += 1
            except Exception:
                # Skip if there's an error creating the plugin
                continue
    
    return f"Scanned plugins directory. Created {created_count} new plugin entries."


@shared_task
def consistency():
    # Delete all integration run results older than 1 year
    one_year_ago = timezone.now() - timedelta(days=365)
    deleted_count, _ = RunResult.objects.filter(
        start_timestamp__lt=one_year_ago
    ).delete()

    # Delete all run results with a null plugin reference
    deleted_null_count, _ = RunResult.objects.filter(
        integration_plugin__isnull=True
    ).delete()

    return f"Deleted {deleted_count} old run results and {deleted_null_count} run results with null plugin reference."
