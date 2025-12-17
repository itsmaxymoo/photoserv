import functools
from django.core.cache import cache
from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from .models import WebRequest, IntegrationCaller


@shared_task
def call_web_request(web_request_id):
    web_request = WebRequest.objects.get(id=web_request_id)
    result = web_request.run(IntegrationCaller.EVENT_SCHEDULER)
    if not result.successful:
        raise Exception(str(web_request) + " - failed")

    return str(web_request) + " - success"


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
            
            # Increment the counter (or initialize to 1 if doesn't exist)
            try:
                new_count = cache.incr(counter_key)
            except ValueError:
                # Key doesn't exist, create it
                cache.set(counter_key, 1, timeout=delay + 60)
            
            # Schedule task to run after delay
            celery_task.apply_async(args=args, kwargs=kwargs, countdown=delay)
            return True

        wrapper.celery_task = celery_task
        return wrapper
    return decorator


def queue_web_requests(**kwargs):
    web_requests = WebRequest.objects.filter(active=True)
    for web_request in web_requests:
        call_web_request.delay(web_request.id)

    return "Queued web requests"


call_queue_web_requests = debounced_task(
    lambda *a, **k: "queue_web_requests",
    delay=settings.INTEGRATION_QUEUE_DELAY
)(queue_web_requests)
