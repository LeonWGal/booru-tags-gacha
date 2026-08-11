def normalize_tag(tag):
    """Canonical form for comparing user-entered tags against site tags.

    Users type "ai generated" while sites store "ai_generated" or
    "ai-generated"; comparing normalized forms makes exclusion filters
    match all of these spellings.
    """
    return str(tag).strip().lstrip('-').lower().replace(' ', '_').replace('-', '_')


class BooruException(Exception):
    pass


class BooruNotFoundException(BooruException):
    pass


class BooruConnectionException(BooruException):
    """Raised when the site cannot be reached (network/timeout errors)."""
    pass


class BooruPost:
    """Normalized representation of a post, regardless of the source site."""

    def __init__(self, id, file_url, tags, post_url, rating=None, score=0):
        self.id = id
        self.file_url = file_url
        self.tags = tags
        self.rating = rating
        self.score = score
        # Populated directly by clients that expose it in the post payload
        # (e.g. Danbooru). Clients that don't must be queried separately
        # via get_artist_tags().
        self.artist_tags = []
        self._post_url = post_url

    def __str__(self):
        return self._post_url

    def get_tags(self):
        return self.tags


class BooruClient:
    """Common interface every site adapter implements."""

    def image_headers(self, url):
        """Headers used to download an image from this site's CDN.

        The browser-ish default works for the Gelbooru-DAPI family; sites
        whose CDN rejects fake browser User-Agents override this.
        """
        return {"User-Agent": "Mozilla/5.0", "Referer": url}

    async def random_post(self, tags=None, exclude_tags=None):
        raise NotImplementedError

    async def get_artist_tags(self, tags):
        """Return the subset of `tags` that are artist tags.

        Only needed for sites that don't already expose artist tags on the
        BooruPost returned by random_post().
        """
        return []
