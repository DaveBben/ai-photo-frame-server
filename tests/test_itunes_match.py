"""The iTunes lookup uses only a track whose title and artist match the request.

Bug (docs/tasks/local-ai/task.md): live on 2026-09-17, "365" by Charli XCX was restyled
from the cover of "party 4 u", iTunes search's top result, because find_song took the
first result whatever its title. 365 is on BRAT and appears in the artist's catalog
lookup but not in the search results.
"""

import httpx
import respx
from vlm_fakes import COVER_600, ITUNES_SEARCH, ITUNES_TRACK, cover_jpeg

from local_shazam.itunes_client import ItunesClient

LOOKUP = "https://itunes.apple.com/lookup"


def _results(*tracks: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200, json={"resultCount": len(tracks), "results": list(tracks)}
    )


async def test_first_search_result_with_the_requested_title_and_artist_is_used() -> (
    None
):
    other_song = {**ITUNES_TRACK, "trackName": "bury a friend"}
    other_artist = {
        **ITUNES_TRACK,
        "artistName": "2CELLOS",
        "collectionName": "Dedicated",
    }
    match = {**ITUNES_TRACK, "trackName": "BAD GUY", "collectionName": "The Match"}
    with respx.mock(assert_all_called=False) as mock:
        search = mock.get(ITUNES_SEARCH).mock(
            return_value=_results(other_song, other_artist, match)
        )
        lookup = mock.get(LOOKUP).mock(return_value=_results())
        mock.get(COVER_600).respond(200, content=cover_jpeg())

        found = await ItunesClient().find_song("bad guy", "Billie Eilish")

    assert found is not None
    assert "Album: The Match" in found[0].splitlines()
    assert search.call_count == 1
    assert lookup.call_count == 0


async def test_no_match_in_search_or_the_artists_catalog_is_no_catalog_data() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ITUNES_SEARCH, params__contains={"entity": "song"}).mock(
            return_value=_results({**ITUNES_TRACK, "trackName": "bury a friend"})
        )
        mock.get(ITUNES_SEARCH, params__contains={"entity": "musicArtist"}).mock(
            return_value=_results(
                {"artistName": "Billie Eilish", "artistId": 1065981054}
            )
        )
        lookup = mock.get(LOOKUP, params__contains={"id": "1065981054"}).mock(
            return_value=_results(
                {"wrapperType": "artist"},
                {**ITUNES_TRACK, "wrapperType": "track", "trackName": "ocean eyes"},
            )
        )

        found = await ItunesClient().find_song("bad guy", "Billie Eilish")

    assert found is None
    assert lookup.call_count == 1
