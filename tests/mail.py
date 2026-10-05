"""Synthetic job-alert emails and an in-memory S3 for the inbox tests."""

from __future__ import annotations

from email.message import EmailMessage
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError


def email(body: str, subtype: str = "html", subject: str = "New jobs for you") -> bytes:
    message = EmailMessage()
    message["From"] = "Example Careers <alerts@careers.example.com>"
    message["To"] = "alerts@inbox.test"
    message["Subject"] = subject
    message.set_content(body, subtype=subtype)
    return message.as_bytes()


class Body:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        self.closed = True


class FakeS3:
    """An in-memory stand-in for the boto3 S3 client, paging two keys at a time."""

    def __init__(self, objects: dict[str, bytes], fail: str | None = None) -> None:
        self.objects = dict(objects)
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.bodies: list[Body] = []

    def _check(self, name: str, kwargs: dict[str, Any]) -> None:
        self.calls.append((name, kwargs))
        if self.fail == name:
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, name)
        if self.fail == f"{name}-transport":
            raise BotoCoreError

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        self._check("list_objects_v2", kwargs)
        keys = sorted(k for k in self.objects if k.startswith(kwargs["Prefix"]))
        start = int(kwargs.get("ContinuationToken", "0"))
        page = keys[start : start + 2]
        more = start + 2 < len(keys)
        result: dict[str, Any] = {"IsTruncated": more}
        if page:
            result["Contents"] = [{"Key": k} for k in page]
        if more:
            result["NextContinuationToken"] = str(start + 2)
        return result

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self._check("get_object", kwargs)
        body = Body(self.objects[kwargs["Key"]])
        self.bodies.append(body)
        return {"Body": body}

    def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        self._check("delete_object", kwargs)
        del self.objects[kwargs["Key"]]
        return {}
