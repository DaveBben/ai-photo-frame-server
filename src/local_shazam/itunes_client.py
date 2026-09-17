"""Client for the iTunes Search API: a song's catalog facts and album cover."""

from typing import Any

import httpx

_SEARCH_URL = "https://itunes.apple.com/search"
_LOOKUP_URL = "https://itunes.apple.com/lookup"


def _matching_track(
    results: list[dict[str, Any]], song: str, artist: str
) -> dict[str, Any] | None:
    """Return the first track titled song whose artist contains artist, both ignoring case."""
    for result in results:
        if (
            result.get("wrapperType") != "artist"
            and result["trackName"].casefold() == song.casefold()
            and artist.casefold() in result["artistName"].casefold()
        ):
            return result
    return None


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
                track = _matching_track(search.json()["results"], song, artist)
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
                    track = _matching_track(catalog.json()["results"], song, artist)
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
