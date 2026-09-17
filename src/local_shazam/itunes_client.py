"""Client for the iTunes Search API: a song's catalog facts and album cover."""

import re
from typing import Any

import httpx

_SEARCH_URL = "https://itunes.apple.com/search"
_LOOKUP_URL = "https://itunes.apple.com/lookup"


_STOP_WORDS = {"feat", "featuring", "ft", "with", "and", "the", "a"}


def _words(text: str) -> set[str]:
    """Return text's casefolded runs of letters and digits, minus joining words such as feat."""
    return set(re.findall(r"[^\W_]+", text.casefold())) - _STOP_WORDS


def _closest_track(
    results: list[dict[str, Any]], song: str, artist: str
) -> dict[str, Any] | None:
    """Return the track whose title and artist words overlap song and artist the most.

    Overlap is shared words over all words. A track qualifies only when its title shares a
    word with song, its artist shares a word with artist, and the overlap is at least one
    half. The earlier track wins a tie.
    """
    wanted = _words(song) | _words(artist)
    best, best_score = None, 0.0
    for result in results:
        if (
            result.get("wrapperType") == "artist"
            or not _words(song) & _words(result["trackName"])
            or not _words(artist) & _words(result["artistName"])
        ):
            continue
        found = _words(result["trackName"]) | _words(result["artistName"])
        score = len(wanted & found) / len(wanted | found)
        if score > best_score:
            best, best_score = result, score
    return best if best_score >= 0.5 else None


class ItunesClient:
    """Looks up the iTunes track matching a song's title and artist."""

    async def find_song(self, song: str, artist: str) -> tuple[str, bytes] | None:
        """Return the matching track's catalog facts and 600x600 cover JPEG.

        Searches for the song first. When no search result matches, looks through the artist's catalog.
        Returns None when no track matches, iTunes answers an error or an incomplete result, or cannot be reached.
        """
        try:
            async with httpx.AsyncClient() as client:
                search = await client.get(
                    _SEARCH_URL,
                    params={
                        "term": f"{song} {artist}",
                        "entity": "song",
                        "limit": "25",
                    },
                )
                search.raise_for_status()
                track = _closest_track(search.json()["results"], song, artist)
                if track is None:
                    artists = await client.get(
                        _SEARCH_URL,
                        params={"term": artist, "entity": "musicArtist", "limit": "1"},
                    )
                    artists.raise_for_status()
                    catalog = await client.get(
                        _LOOKUP_URL,
                        params={
                            "id": artists.json()["results"][0]["artistId"],
                            "entity": "song",
                            "limit": "200",
                        },
                    )
                    catalog.raise_for_status()
                    track = _closest_track(catalog.json()["results"], song, artist)
                if track is None:
                    return None
                cover = await client.get(
                    track["artworkUrl100"].replace("100x100bb.jpg", "600x600bb.jpg")
                )
                cover.raise_for_status()
            facts = (
                f"Track: {track['trackName']}\n"
                f"Artist: {track['artistName']}\n"
                f"Album: {track.get('collectionName')}\n"
                f"Genre: {track.get('primaryGenreName')}\n"
                f"Released: {track['releaseDate'][:10]}"
            )
        # ValueError: a non-JSON body. KeyError: a result missing a field used above.
        # IndexError: the artist search found no artist.
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            return None
        return facts, cover.content
