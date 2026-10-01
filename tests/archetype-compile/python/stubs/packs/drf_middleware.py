"""harness: the request-id middleware frameworks/drf.md's handler and renderer read request.request_id from."""
import uuid


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        response = self.get_response(request)
        response["X-Request-Id"] = request.request_id
        return response
