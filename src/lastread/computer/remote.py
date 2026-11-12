"""Server mode's half of a sync: send the small database, ask which books
belong in the collection; and the books for the Mac app (/api/app/). The
upload token is the only credential."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .. import __version__


class ServerError(Exception):
    """Something the person can act on; str() is the message."""

    def __init__(self, message: str, status: int = 0, said: str = ""):
        super().__init__(message)
        self.status = status
        self.said = said  # the server's own words for a refusal, {"error": ...}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an answer, not somewhere to go: urllib would carry the
    upload token along to wherever a proxy in front of the server points,
    its sign-in page on another host or plain http included."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # the 3xx then comes back as an HTTPError, with its Location


class Server:
    def __init__(self, url: str, token: str, opener=None):
        self.url = url.rstrip("/")
        self.host = urlparse(self.url).hostname or self.url
        self._token = token
        self._open = opener or urllib.request.build_opener(_NoRedirect).open

    def _request(
        self, method: str, path: str, body: bytes | None = None, timeout: int = 60, content_type: str = "", with_type: bool = False
    ):
        """(status, body), or with with_type (status, body, media type, what
        the X-Lastread header says)."""
        headers = {"Authorization": "Bearer " + self._token, "User-Agent": f"lastread/{__version__}"}  # the server notes it
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.url + path, data=body, method=method, headers=headers)
        try:
            with self._open(req, timeout=timeout) as r:
                if with_type:  # the type is text/plain when none was sent
                    return r.status, r.read(), r.headers.get_content_type(), r.headers.get("X-Lastread") or ""
                return r.status, r.read()
        except urllib.error.HTTPError as ex:
            detail = ex.read()[:300].decode("utf-8", "replace")
            said = ""
            try:
                said = json.loads(detail).get("error", "")
            except (ValueError, AttributeError):
                pass
            detail = said or detail
            if 300 <= ex.code < 400:
                to = urlparse(ex.headers.get("Location") or "").hostname or "another address"
                raise ServerError(
                    f"{self.host} sent this computer on to {to} instead of answering, as a sign-in proxy does. Nothing was "
                    "sent there. Give the server's own https address in setup, and let its proxy pass /upload, /collection "
                    "and /api/app/ through.",
                    ex.code,
                ) from ex
            if ex.code == 401:
                raise ServerError(
                    f"{self.host} does not know this computer. Add its hash under Settings, Devices (run setup to see it).", 401
                ) from ex
            if ex.code == 413:
                raise ServerError(f"{self.host} refused the upload: too large.", 413) from ex
            raise ServerError(f"{self.host} answered {ex.code}: {str(detail)[:120]}", ex.code, said) from ex
        except (urllib.error.URLError, OSError) as ex:
            reason = getattr(ex, "reason", ex)
            raise ServerError(f"Could not reach {self.host} ({reason}).") from ex

    def upload(self, gz_path: str) -> dict:
        """Send the gzipped database. Returns what the server imported."""
        with open(gz_path, "rb") as fh:
            body = fh.read()
        _, raw = self._request("PUT", "/upload", body, timeout=120, content_type="application/gzip")
        try:
            return json.loads(raw)
        except ValueError as ex:
            raise ServerError(f"{self.host} gave an answer that is not from lastread.") from ex

    def knows_me(self) -> bool:
        """Whether the server knows this computer's token. ServerError when it
        cannot be reached, or answers as lastread never does: any other
        site's page, or a proxy's sign-in page, is not "it knows me"."""
        try:
            self.collection(timeout=15)
        except ServerError as ex:
            if ex.status == 401:
                return False
            raise
        return True

    def collection(self, timeout: int = 60) -> tuple[str, list[str]] | None:
        """(name, book ids) of the collection to keep on the Kobo, or None
        when the reader set no collection name. ServerError for an answer
        lastread never gives, such as a proxy's sign-in page: read as a
        collection, it would empty the one on the Kobo. A server from 0.27
        on says in a header that the answer is its own; an older one is
        believed when nothing in the answer looks like a page."""
        status, raw, kind, said = self._request("GET", "/collection", timeout=timeout, with_type=True)
        text = raw.decode("utf-8", "replace")
        if status == 204 or not text.strip():
            return None
        lines = text.split("\n")
        if kind != "text/plain" or (said != "collection" and any(line.strip().startswith("<") for line in lines)):
            raise ServerError(f"{self.host} gave an answer that is not from lastread.")
        return lines[0].strip(), [i for i in lines[1:] if i.strip()]

    def app(self, method: str, path: str, payload: dict | None = None) -> dict:
        """One of the server's answers for the Mac app (/api/app/), as JSON.
        A refusal comes back in the server's words; a server or proxy that
        does not answer these paths is said to be one."""
        body = json.dumps(payload).encode() if payload is not None else None
        try:
            _, raw = self._request(method, "/api/app/" + path, body, content_type="application/json" if body else "")
        except ServerError as ex:
            if ex.said and ex.status in (400, 404, 409, 502):
                raise ServerError(ex.said, ex.status) from ex
            if ex.status in (403, 404, 405):
                raise ServerError(self._not_for_the_app(), ex.status) from ex
            raise
        try:
            return json.loads(raw)
        except ValueError as ex:  # a sign-in page: the proxy did not let the path through
            raise ServerError(self._not_for_the_app()) from ex

    def _not_for_the_app(self) -> str:
        return (
            f"{self.host} does not answer the app's questions about books: the server is older than 0.15.0, "
            "or its proxy does not route /api/app/ past the sign-in."
        )

    def cover(self, path: str) -> bytes | None:
        """A cover the server keeps, by the path its answer gave; None when it has none."""
        if not path.startswith("/api/app/cover?"):
            return None
        try:
            _, raw = self._request("GET", path, timeout=30)
        except ServerError as ex:
            if ex.status == 404:
                return None
            raise
        return raw if raw[:2] == b"\xff\xd8" else None  # a JPEG, not a sign-in page
