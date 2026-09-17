"""Gaps in the iTunes title-and-artist match that the bug's tests leave open.

Bug (docs/tasks/local-ai/task.md): live on 2026-09-17, "365" by Charli XCX was restyled
from the cover of "party 4 u". These tests pin the artist fallback's requests, the case
folding of the requested title and artist, and error answers during the fallback.
"""

import httpx
import pytest
import respx
from vlm_fakes import COVER_600, ITUNES_SEARCH, ITUNES_TRACK, cover_jpeg

from local_shazam.itunes_client import ItunesClient

LOOKUP = "https://itunes.apple.com/lookup"
ARTIST = {"artistName": "Billie Eilish", "artistId": 1065981054}


def _results(status: int, *results: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        status, json={"resultCount": len(results), "results": list(results)}
    )


async def test_artist_fallback_asks_for_one_artist_and_up_to_200_songs() -> None:
    with respx.mock() as mock:
        mock.get(ITUNES_SEARCH, params__contains={"entity": "song"}).mock(
            return_value=_results(200)
        )
        artists = mock.get(
            ITUNES_SEARCH, params__contains={"entity": "musicArtist"}
        ).mock(return_value=_results(200, ARTIST))
        catalog = mock.get(LOOKUP).mock(
            return_value=_results(200, {"wrapperType": "artist"}, ITUNES_TRACK)
        )
        mock.get(COVER_600).respond(200, content=cover_jpeg())

        found = await ItunesClient().find_song("bad guy", "Billie Eilish")

    assert found is not None
    assert dict(artists.calls.last.request.url.params) == {
        "term": "Billie Eilish",
        "entity": "musicArtist",
        "limit": "1",
    }
    assert dict(catalog.calls.last.request.url.params) == {
        "id": "1065981054",
        "entity": "song",
        "limit": "200",
    }


async def test_requested_title_and_artist_match_in_any_case() -> None:
    track = {**ITUNES_TRACK, "trackName": "Bad guy", "artistName": "Billie EILISH"}
    with respx.mock() as mock:
        mock.get(ITUNES_SEARCH).mock(return_value=_results(200, track))
        mock.get(COVER_600).respond(200, content=cover_jpeg())

        found = await ItunesClient().find_song("bad GUY", "BILLIE eilish")

    assert found is not None
    assert "Track: Bad guy" in found[0].splitlines()


@pytest.mark.parametrize(
    ("artist_status", "catalog_status"),
    [(503, 200), (200, 503)],
    ids=["artist-search-error", "catalog-lookup-error"],
)
async def test_error_answer_during_the_artist_fallback_is_no_catalog_data(
    artist_status: int, catalog_status: int
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ITUNES_SEARCH, params__contains={"entity": "song"}).mock(
            return_value=_results(200)
        )
        mock.get(ITUNES_SEARCH, params__contains={"entity": "musicArtist"}).mock(
            return_value=_results(artist_status, ARTIST)
        )
        mock.get(LOOKUP).mock(return_value=_results(catalog_status, ITUNES_TRACK))
        mock.get(COVER_600).respond(200, content=cover_jpeg())

        found = await ItunesClient().find_song("bad guy", "Billie Eilish")

    assert found is None
