"""S42 listing completeness uses mocked HTTP only, with synthetic file metadata."""

import json

import httpx
import pytest
import respx

from app.connectors.base import PlatformError
from app.connectors.canvas.client import CanvasClient
from app.connectors.canvas.connector import _Run
from tests.canvas_fake import API, BASE, fx
from tests.connector.test_s11_canvas_connector import connector, ctx


def files(n):
    template = fx("files_12345")[0]
    return [{**template, "id": 90000 + i, "display_name": f"Synthetic {i}.pdf"} for i in range(n)]


@pytest.mark.parametrize("count", [99, 100, 101])
async def test_s42_t01_cap_boundary_sets_only_truncated_listing_incomplete(count):
    context = ctx()
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses/12345/files").respond(json=files(count))
        async with httpx.AsyncClient() as http:
            run = _Run(
                connector(max_files_per_course=100),
                CanvasClient(BASE, context.secret, http),
                context,
            )
            got = [r async for r in run.files("12345")]
    assert len(got) == min(count, 100)
    assert (("12345", "materials") in context.incomplete) == (count > 100)
    assert ("23456", "materials") not in context.incomplete


async def test_s42_t02_module_fallback_is_never_authoritative_for_absence():
    context = ctx()
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses/12345/files").respond(403, json={})
        router.get(f"{API}/courses/12345/modules").respond(json=[])
        async with httpx.AsyncClient() as http:
            run = _Run(connector(), CanvasClient(BASE, context.secret, http), context)
            assert [r async for r in run.files("12345")] == []
    assert ("12345", "materials") in context.incomplete


@pytest.mark.parametrize("detail_status", [403, 404])
async def test_s42_t02_missing_module_detail_marks_incomplete(detail_status):
    context = ctx()
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses/12345/modules").respond(
            json=[{"items": [{"type": "File", "content_id": 90000}]}]
        )
        router.get(f"{API}/courses/12345/files/90000").respond(detail_status, json={})
        async with httpx.AsyncClient() as http:
            run = _Run(connector(), CanvasClient(BASE, context.secret, http), context)
            assert [r async for r in run.module_files("12345", 100)] == []
    assert ("12345", "materials") in context.incomplete


async def test_s42_t02_module_cap_marks_incomplete():
    context = ctx()
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses/12345/modules").respond(
            json=[
                {
                    "items": [
                        {"type": "File", "content_id": 90000},
                        {"type": "File", "content_id": 90001},
                    ]
                }
            ]
        )
        router.get(f"{API}/courses/12345/files/90000").respond(json=files(1)[0])
        async with httpx.AsyncClient() as http:
            run = _Run(connector(), CanvasClient(BASE, context.secret, http), context)
            assert len([r async for r in run.module_files("12345", 1)]) == 1
    assert ("12345", "materials") in context.incomplete


@pytest.mark.parametrize("payload", [{}, {"error": "synthetic"}, None, "not a list"])
async def test_s42_t03_invalid_list_response_is_failure(payload):
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses").respond(
            content=json.dumps(payload), headers={"content-type": "application/json"}
        )
        context = ctx()
        async with httpx.AsyncClient() as http:
            client = CanvasClient(BASE, context.secret, http)
            with pytest.raises(PlatformError):
                _ = [x async for x in client.paginate("/api/v1/courses")]


async def test_s42_t03_malformed_json_is_platform_failure():
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{API}/courses").respond(
            content="{", headers={"content-type": "application/json"}
        )
        context = ctx()
        async with httpx.AsyncClient() as http:
            client = CanvasClient(BASE, context.secret, http)
            with pytest.raises(PlatformError, match="invalid list response"):
                _ = [x async for x in client.paginate("/api/v1/courses")]


@pytest.mark.parametrize("extra", [False, True])
async def test_s42_t01_cap_boundary_across_pages(extra):
    context = ctx()
    with respx.mock(assert_all_called=False) as router:

        def page(request):
            if request.url.params.get("page") == "2":
                return httpx.Response(200, json=files(101)[100:] if extra else [])
            return httpx.Response(
                200,
                json=files(100),
                headers={
                    "Link": f'<{API}/courses/12345/files?page=2>; rel="next"',
                },
            )

        route = router.get(f"{API}/courses/12345/files").mock(side_effect=page)
        async with httpx.AsyncClient() as http:
            run = _Run(
                connector(max_files_per_course=100),
                CanvasClient(BASE, context.secret, http),
                context,
            )
            assert len([r async for r in run.files("12345")]) == 100
        assert route.call_count == 2
    assert (("12345", "materials") in context.incomplete) == extra
