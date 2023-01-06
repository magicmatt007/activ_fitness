"""Centers class."""

import json

from .center import Center


class Centers:
    """Centers class."""

    def __init__(self, centers, centers_by_id, centers_by_name):
        self.centers: list[Center] = centers
        self.centers_by_id: dict = centers_by_id
        self.centers_by_name: dict = centers_by_name

    @staticmethod
    def from_json_str(json_str):
        """Create instance from JSON."""
        content_json = json.loads(json_str)
        centers_lst = []
        for center in content_json:
            if center["title"] == "Activ Fitness":
                centers_lst = center["centers"]

        centers_obj_lst = []
        for center in centers_lst:
            centers_obj_lst.append(Center.from_json(center))

        centers_by_id = {c.center_id: c.title for c in centers_obj_lst}
        centers_by_name = {c.title: c.center_id for c in centers_obj_lst}

        return Centers(centers_obj_lst, centers_by_id, centers_by_name)
