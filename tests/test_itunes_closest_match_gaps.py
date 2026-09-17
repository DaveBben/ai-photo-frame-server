"""Gaps in the iTunes word-overlap match that tests/test_itunes_closest_match.py leaves open.

These pin each joining word that is ignored, the one-half threshold itself, and the
shared-artist-word rule on a track whose words otherwise overlap enough.
"""

import httpx
import pytest
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


async def _album(song: str, artist: str, *tracks: dict[str, object]) -> str | None:
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
    if found is None:
        return None
    return next(line for line in found[0].splitlines() if line.startswith("Album: "))


@pytest.mark.parametrize(
    "joining_word", ["feat", "featuring", "ft", "with", "and", "the", "a"]
)
async def test_joining_word_does_not_lower_the_overlap(joining_word: str) -> None:
    # Ignoring the joining word, both tracks overlap fully and the earlier one wins.
    with_joining_word = _track(f"Hello {joining_word}", "Adele", "25")
    plain = _track("Hello", "Adele", "Hello - Single")

    album = await _album("Hello", "Adele", with_joining_word, plain)

    assert album == "Album: 25"


async def test_overlap_of_exactly_one_half_matches() -> None:
    # {365, charli, xcx} against {365, charli, xcx, club, mix, edit}: 3 shared of 6 words.
    album = await _album(
        "365", "Charli XCX", _track("365 club mix edit", "Charli xcx", "BRAT remixed")
    )

    assert album == "Album: BRAT remixed"


async def test_enough_overlap_without_a_shared_artist_word_is_no_match() -> None:
    # {unlock, it, charli, xcx} against {unlock, it, charli, xcx, backing, business}: 4 of 6.
    album = await _album(
        "Unlock It",
        "Charli XCX",
        _track("Unlock It Charli XCX", "Backing Business", "Pristine Karaoke"),
    )

    assert album is None


async def test_enough_overlap_without_a_shared_title_word_is_no_match() -> None:
    # Live 2026-09-17: search for "365 Charli XCX" lists "Apple" from BRAT.
    # {365, charli, xcx} against {apple, charli, xcx}: 2 shared of 4 words.
    album = await _album("365", "Charli XCX", _track("Apple", "Charli xcx", "BRAT"))

    assert album is None


async def test_shared_title_and_artist_words_below_one_half_is_no_match() -> None:
    # {365, charli, xcx} against {365, charli, xcx, club, mix, edit, remix}: 3 of 7 words.
    album = await _album(
        "365",
        "Charli XCX",
        _track("365 club mix edit remix", "Charli xcx", "BRAT remixed"),
    )

    assert album is None
