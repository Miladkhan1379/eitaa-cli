from __future__ import annotations

import math
import mimetypes
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any

from eitaa_cli.errors import EitaaError
from eitaa_cli.services.messages import random_long
from eitaa_cli.services.peers import input_peer_to_peer

if TYPE_CHECKING:
    from eitaa_cli.client import EitaaClient


class MediaService:
    def __init__(self, client: EitaaClient) -> None:
        self.client = client

    async def upload(self, path: Path, *, peer: dict[str, Any] | None = None) -> dict[str, Any]:
        path = path.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        is_big = size >= 10 * 1024 * 1024
        if size > 64 * 1024 * 1024:
            part_size = 512 * 1024
        elif size < 100 * 1024:
            part_size = 32 * 1024
        else:
            part_size = 256 * 1024
        parts = max(1, math.ceil(size / part_size))
        if parts > 4000:
            raise EitaaError(f"file requires {parts} parts; the Eitaa Web limit is 4000")
        file_id = secrets.randbits(63) or 1
        plain_peer = input_peer_to_peer(peer) if peer else None
        with path.open("rb") as handle:
            for index in range(parts):
                chunk = handle.read(part_size)
                params: dict[str, Any] = {
                    "file_id": file_id,
                    "file_part": index,
                    "bytes": chunk,
                    "totalFileSize": size,
                }
                if plain_peer:
                    params["peer"] = plain_peer
                if is_big:
                    params["file_total_parts"] = parts
                    await self.client.invoke("upload.saveBigFilePart", params, kind="upload")
                else:
                    await self.client.invoke("upload.saveFilePart", params, kind="upload")
        if is_big:
            return {"_": "inputFileBig", "id": file_id, "parts": parts, "name": path.name}
        return {
            "_": "inputFile",
            "id": file_id,
            "parts": parts,
            "name": path.name,
            "md5_checksum": "",
        }

    async def send_file(
        self,
        peer_reference: str | dict[str, Any],
        path: Path,
        *,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        as_document: bool = False,
        voice: bool = False,
        duration: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> dict[str, Any]:
        peer = await self.client.peers.resolve(peer_reference)
        uploaded = await self.upload(path, peer=peer)
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        is_photo = mime_type.startswith("image/") and mime_type not in {
            "image/gif",
            "image/webp",
        }
        if is_photo and not as_document:
            media: dict[str, Any] = {"_": "inputMediaUploadedPhoto", "file": uploaded}
        else:
            attributes: list[dict[str, Any]] = [
                {"_": "documentAttributeFilename", "file_name": path.name}
            ]
            if voice or mime_type.startswith("audio/"):
                attributes.append(
                    {
                        "_": "documentAttributeAudio",
                        "voice": voice,
                        "duration": max(0, duration),
                    }
                )
            elif mime_type.startswith("video/"):
                attributes.append(
                    {
                        "_": "documentAttributeVideo",
                        "supports_streaming": True,
                        "duration": max(0, duration),
                        "w": max(0, width),
                        "h": max(0, height),
                    }
                )
            media = {
                "_": "inputMediaUploadedDocument",
                "file": uploaded,
                "mime_type": mime_type,
                "attributes": attributes,
                "force_file": as_document,
            }
        params: dict[str, Any] = {
            "peer": peer,
            "media": media,
            "message": caption,
            "random_id": random_long(),
            "silent": silent,
        }
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await self.client.invoke("messages.sendMedia", params)

    async def send_album(
        self,
        peer_reference: str | dict[str, Any],
        paths: list[Path],
        *,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
    ) -> dict[str, Any]:
        if not paths:
            raise ValueError("album requires at least one file")
        if len(paths) > 10:
            raise ValueError("Eitaa albums support at most 10 files")
        peer = await self.client.peers.resolve(peer_reference)
        items: list[dict[str, Any]] = []
        for index, original_path in enumerate(paths):
            path = original_path.expanduser().resolve()
            uploaded = await self.upload(path, peer=peer)
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if mime_type.startswith("image/") and mime_type not in {"image/gif", "image/webp"}:
                pending_media: dict[str, Any] = {
                    "_": "inputMediaUploadedPhoto",
                    "file": uploaded,
                }
            else:
                attributes: list[dict[str, Any]] = [
                    {"_": "documentAttributeFilename", "file_name": path.name}
                ]
                if mime_type.startswith("video/"):
                    attributes.append(
                        {
                            "_": "documentAttributeVideo",
                            "supports_streaming": True,
                            "duration": 0,
                            "w": 0,
                            "h": 0,
                        }
                    )
                pending_media = {
                    "_": "inputMediaUploadedDocument",
                    "file": uploaded,
                    "mime_type": mime_type,
                    "attributes": attributes,
                }
            uploaded_media = await self.client.invoke(
                "messages.uploadMedia", {"peer": peer, "media": pending_media}
            )
            items.append(
                {
                    "_": "inputSingleMedia",
                    "media": _message_media_to_input(uploaded_media),
                    "random_id": random_long(),
                    "message": caption if index == 0 else "",
                }
            )
        params: dict[str, Any] = {
            "peer": peer,
            "multi_media": items,
            "silent": silent,
        }
        if reply_to is not None:
            params["reply_to_msg_id"] = reply_to
        return await self.client.invoke("messages.sendMultiMedia", params)

    async def download_message(
        self,
        peer_reference: str | dict[str, Any],
        message_id: int,
        output: Path,
    ) -> Path:
        message = await self.client.messages.get_by_id(peer_reference, message_id)
        if not message:
            raise EitaaError(f"message {message_id} was not found")
        media = message.get("media") or {}
        location, size, suggested = _location_from_media(media)
        output = output.expanduser()
        if output.exists() and output.is_dir():
            output = output / suggested
        elif output.suffix == "" and not output.exists():
            output.mkdir(parents=True, exist_ok=True)
            output = output / suggested
        output.parent.mkdir(parents=True, exist_ok=True)
        await self.download(location, size=size, output=output)
        return output

    async def download(
        self, location: dict[str, Any], *, size: int, output: Path, chunk_size: int = 512 * 1024
    ) -> None:
        offset = 0
        with output.open("wb") as handle:
            while offset < size:
                response = await self.client.invoke(
                    "upload.getFile",
                    {
                        "location": location,
                        "offset": offset,
                        "limit": min(chunk_size, size - offset),
                        "cdn_supported": False,
                    },
                    kind="download",
                )
                if response.get("_") != "upload.file":
                    raise EitaaError(f"unsupported download response: {response.get('_')}")
                chunk = response.get("bytes", b"")
                if not chunk:
                    break
                handle.write(chunk)
                offset += len(chunk)
        if size and output.stat().st_size < size:
            raise EitaaError(
                f"download stopped at {output.stat().st_size} of {size} bytes: {output}"
            )


def _message_media_to_input(media: dict[str, Any]) -> dict[str, Any]:
    predicate = media.get("_")
    if predicate == "messageMediaPhoto" and media.get("photo"):
        photo = media["photo"]
        return {
            "_": "inputMediaPhoto",
            "id": {
                "_": "inputPhoto",
                "id": photo["id"],
                "access_hash": photo["access_hash"],
                "file_reference": photo["file_reference"],
            },
        }
    if predicate == "messageMediaDocument" and media.get("document"):
        document = media["document"]
        return {
            "_": "inputMediaDocument",
            "id": {
                "_": "inputDocument",
                "id": document["id"],
                "access_hash": document["access_hash"],
                "file_reference": document["file_reference"],
            },
        }
    raise EitaaError(f"messages.uploadMedia returned unsupported media: {predicate}")


def _location_from_media(media: dict[str, Any]) -> tuple[dict[str, Any], int, str]:
    if media.get("_") == "messageMediaDocument" and media.get("document"):
        document = media["document"]
        name = _document_filename(document) or f"document-{document['id']}"
        return (
            {
                "_": "inputDocumentFileLocation",
                "id": document["id"],
                "access_hash": document["access_hash"],
                "file_reference": document["file_reference"],
                "thumb_size": "",
            },
            int(document.get("size", 0)),
            name,
        )
    if media.get("_") == "messageMediaPhoto" and media.get("photo"):
        photo = media["photo"]
        sizes = [size for size in photo.get("sizes", []) if size.get("_") != "photoSizeEmpty"]
        if not sizes:
            raise EitaaError("photo has no downloadable sizes")
        largest = max(sizes, key=lambda item: int(item.get("size", 0)))
        extension = ".jpg"
        return (
            {
                "_": "inputPhotoFileLocation",
                "id": photo["id"],
                "access_hash": photo["access_hash"],
                "file_reference": photo["file_reference"],
                "thumb_size": largest.get("type", "x"),
            },
            int(largest.get("size", 0)),
            f"photo-{photo['id']}{extension}",
        )
    raise EitaaError(f"message has no downloadable photo/document media: {media.get('_')}")


def _document_filename(document: dict[str, Any]) -> str | None:
    for attribute in document.get("attributes", []):
        if attribute.get("_") == "documentAttributeFilename":
            return str(attribute.get("file_name") or "") or None
    mime = str(document.get("mime_type") or "")
    extension = mimetypes.guess_extension(mime) or ""
    return f"document-{document.get('id')}{extension}"
