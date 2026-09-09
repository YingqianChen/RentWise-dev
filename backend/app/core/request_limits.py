"""Bound HTTP body bytes before parsing JSON or multipart file contents."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

JSON_BODY_LIMIT = 256 * 1024
UPLOAD_BODY_LIMIT = 32 * 1024 * 1024


class RequestBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        is_upload = scope["method"] == "POST" and scope["path"].endswith("/candidates/import")
        limit = UPLOAD_BODY_LIMIT if is_upload else JSON_BODY_LIMIT
        lengths = [value for key, value in scope["headers"] if key.lower() == b"content-length"]
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit():
                return await JSONResponse({"detail": "Invalid Content-Length header."}, status_code=400)(
                    scope, receive, send
                )
            # Bound header parsing too; int() on an enormous decimal must not 500.
            if len(lengths[0]) > 12 or int(lengths[0]) > limit:
                return await JSONResponse({"detail": "Request body is too large."}, status_code=413)(
                    scope, receive, send
                )
        size = 0

        async def limited_receive():
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    raise HTTPException(status_code=413, detail="Request body is too large.")
            return message

        return await self.app(scope, limited_receive, send)
