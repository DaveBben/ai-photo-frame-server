"""The iTunes lookup picks the track whose title and artist words overlap the request most.

Card (docs/tasks/local-ai/task.md): the frame sends Shazam's title and artist, which often
differ from iTunes' spelling: "Guess (feat. Billie Eilish)" against "Guess featuring Billie
Eilish", "Lady Gaga, Bruno Mars" against "Lady Gaga & Bruno Mars". The exact-title rule
gave those songs no album cover. Examples below are iTunes results seen on 2026-09-17.
"""

import httpx
import respx
from vlm_fakes import COVER_600, ITUNES_SEARCH, ITUNES_TRACK, cover_jpeg

from local_shazam.itunes_client import ItunesClient


def _track(title: str, artist: str, album: str) -> dict[str, object]:
    return {
        **ITUNES_TRACK,
        "trackName": title,
        "artistName": artist,
        "collectionName": album,
    }


async def _find(song: str, artist: str, *tracks: dict[str, object]) -> str | None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ITUNES_SEARCH, params__contains={"entity": "song"}).mock(
            return_value=httpx.Response(
                200, json={"resultCount": len(tracks), "results": list(tracks)}
            )
        )
        mock.get(ITUNES_SEARCH, params__contains={"entity": "musicArtist"}).mock(
            return_value=httpx.Response(200, json={"resultCount": 0, "results": []})
        )
        mock.get(COVER_600).respond(200, content=cover_jpeg())
        found = await ItunesClient().find_song(song, artist)
    return None if found is None else found[0]


def _album(facts: str | None) -> str | None:
    if facts is None:
        return None
    return next(line for line in facts.splitlines() if line.startswith("Album: "))


async def test_featured_artist_written_differently_still_matches() -> None:
    facts = await _find(
        "Guess (feat. Billie Eilish)",
        "Charli xcx & Billie Eilish",
        _track(
            "Guess featuring Billie Eilish",
            "Charli xcx & Billie Eilish",
            "Guess - Single",
        ),
    )

    assert _album(facts) == "Album: Guess - Single"


async def test_artists_joined_by_a_comma_match_artists_joined_by_an_ampersand() -> None:
    facts = await _find(
        "Die With A Smile",
        "Lady Gaga, Bruno Mars",
        _track("Die With A Smile", "Lady Gaga & Bruno Mars", "MAYHEM"),
    )

    assert _album(facts) == "Album: MAYHEM"


async def test_track_sharing_no_artist_word_is_never_picked() -> None:
    karaoke = _track(
        "Unlock It (Originally Performed by Charli XCX, Kim Petras & Jay Park)",
        "Backing Business",
        "Pristine Karaoke, Vol. 37",
    )
    real = _track("Unlock It (feat. Kim Petras and Jay Park)", "Charli xcx", "Pop 2")

    facts = await _find("Unlock It", "Charli XCX, Kim Petras, Jay Park", karaoke, real)

    assert _album(facts) == "Album: Pop 2"


async def test_highest_overlap_wins_over_an_earlier_result() -> None:
    vacation = _track(
        "Espresso (On Vacation Version)", "Sabrina Carpenter", "Espresso EP"
    )
    single = _track("Espresso", "Sabrina Carpenter", "Short n' Sweet")

    facts = await _find("Espresso", "Sabrina Carpenter", vacation, single)

    assert _album(facts) == "Album: Short n' Sweet"


async def test_equal_overlap_keeps_the_earlier_result() -> None:
    album = _track("Midnight City", "M83", "Hurry Up, We're Dreaming")
    ep = _track("Midnight City", "M83", "Midnight City - EP")

    facts = await _find("Midnight City", "M83", album, ep)

    assert _album(facts) == "Album: Hurry Up, We're Dreaming"


async def test_overlap_below_one_half_is_no_match() -> None:
    # {365, charli, xcx} against {party, 4, u, charli, xcx}: 2 shared of 6 words.
    facts = await _find(
        "365", "Charli XCX", _track("party 4 u", "Charli xcx", "how i'm feeling now")
    )

    assert facts is None
