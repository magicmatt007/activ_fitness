"""Center class."""


class Center:
    """Center class."""

    def __init__(self, center_id, title):
        self.center_id = center_id
        self.title = title

    def __str__(self):
        return f"{self.center_id} {self.title}"

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        yield from {"center_id": self.center_id, "title": self.title}.items()

    @staticmethod
    def from_json(json_dct):
        """Create instance from JSON."""

        return Center(json_dct["centerId"], json_dct["title"])
