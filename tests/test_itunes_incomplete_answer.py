"""An iTunes answer the lookup cannot use counts as no catalog data, so the song look is still written.

Slice: captions, song looks and edit prompts from the local vision model
(docs/tasks/local-ai/task.md, item B). Found in review: a missing field or a non-JSON
body raised out of find_song and GET /aesthetic answered 500; a failed cover download
was not tested.
"""

import httpx
import pytest
import respx
from vlm_fakes import COVER_600, ITUNES_SEARCH, ITUNES_TRACK, cover_jpeg

from local_shazam.itunes_client import ItunesClient


def _without(key: str) -> dict[str, object]:
    return {
        "resultCount": 1,
        "results": [{k: v for k, v in ITUNES_TRACK.items() if k != key}],
    }


@pytest.mark.parametrize(
    ("search", "cover"),
    [
        (httpx.Response(200, json=_without("trackName")), None),
        (httpx.Response(200, json=_without("artistName")), None),
        (httpx.Response(200, json=_without("releaseDate")), None),
        (httpx.Response(200, json=_without("artworkUrl100")), None),
        (httpx.Response(200, text="<html>maintenance</html>"), None),
        (None, httpx.Response(404)),
        (None, httpx.ConnectError("cover unreachable")),
    ],
    ids=[
        "no-track-name",
        "no-artist-name",
        "no-release-date",
        "no-artwork-url",
        "not-json",
        "cover-404",
        "cover-unreachable",
    ],
)
async def test_unusable_itunes_answer_is_no_catalog_data(
    search: httpx.Response | None, cover: httpx.Response | Exception | None
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ITUNES_SEARCH).mock(
            return_value=search
            or httpx.Response(200, json={"resultCount": 1, "results": [ITUNES_TRACK]})
        )
        route = mock.get(COVER_600)
        if isinstance(cover, Exception):
            route.mock(side_effect=cover)
        else:
            route.mock(return_value=cover or httpx.Response(200, content=cover_jpeg()))

        found = await ItunesClient().find_song("bad guy", "Billie Eilish")

    assert found is None
