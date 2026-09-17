"""Client for the iTunes Search API: a song's catalog facts and album cover."""

import httpx

_SEARCH_URL = "https://itunes.apple.com/search"


class ItunesClient:
    """Looks up the top iTunes match for a song."""

    async def find_song(self, song: str, artist: str) -> tuple[str, bytes] | None:
        """Return the top match's catalog facts and 600x600 cover JPEG.

        Returns None when iTunes has no match, answers an error, or cannot be reached.
        """
        try:
            async with httpx.AsyncClient() as client:
                search = await client.get(
                    _SEARCH_URL,
                    params={"term": f"{song} {artist}", "entity": "song", "limit": "1"},
                )
                search.raise_for_status()
                results = search.json()["results"]
                if not results:
                    return None
                track = results[0]
                cover = await client.get(
                    track["artworkUrl100"].replace("100x100bb.jpg", "600x600bb.jpg")
                )
                cover.raise_for_status()
        except httpx.HTTPError:
            return None
        facts = (
            f"Track: {track['trackName']}\n"
            f"Artist: {track['artistName']}\n"
            f"Album: {track.get('collectionName')}\n"
            f"Genre: {track.get('primaryGenreName')}\n"
            f"Released: {track['releaseDate'][:10]}"
        )
        return facts, cover.content
