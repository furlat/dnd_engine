"""Shared HTTP delivery for immutable installed-content descriptors."""

from typing import TypeVar

from fastapi import Request, Response

from dnd.content_system.pack_loader import LoadedContentSystem
from server.content_catalog import (
    ContentCatalogResponse,
    ContentManifestResponse,
    build_content_manifest,
    build_public_content_catalog,
    content_response_etag,
)

_ContentResponse = TypeVar(
    "_ContentResponse",
    ContentManifestResponse,
    ContentCatalogResponse,
)


def _conditional_content_response(
    *,
    request: Request,
    response: Response,
    payload: _ContentResponse,
    digest: str,
) -> _ContentResponse | Response:
    etag = content_response_etag(digest)
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=0, must-revalidate",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return payload


def serve_content_manifest(
    *,
    content_system: LoadedContentSystem,
    request: Request,
    response: Response,
) -> ContentManifestResponse | Response:
    """Serve one exact manifest with shared conditional-cache semantics."""
    manifest = build_content_manifest(content_system)
    return _conditional_content_response(
        request=request,
        response=response,
        payload=manifest,
        digest=manifest.content_set_digest,
    )


def serve_content_catalog(
    *,
    content_system: LoadedContentSystem,
    request: Request,
    response: Response,
) -> ContentCatalogResponse | Response:
    """Serve one exact public catalog with shared conditional-cache semantics."""
    catalog = build_public_content_catalog(content_system)
    return _conditional_content_response(
        request=request,
        response=response,
        payload=catalog,
        digest=catalog.catalog_digest,
    )
