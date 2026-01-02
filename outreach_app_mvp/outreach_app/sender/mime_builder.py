from __future__ import annotations

import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


def build_message(
    subject: str,
    body_text: str,
    to_email: str,
    from_email: str,
    attachments: list[str] | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = to_email
    msg["From"] = from_email
    msg.set_content(body_text)

    for p in attachments or []:
        path = Path(p)
        if not path.exists():
            continue
        ctype, encoding = mimetypes.guess_type(str(path))
        if ctype is None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=path.name,
            )
    return msg
