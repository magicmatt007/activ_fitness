import json
from .Course import Course


class Bookings:
    """Bookings data class."""

    def __init__(self, courses):
        self.courses: list[Course] = courses

    @staticmethod
    def from_json_str(json_str):
        courses_lst = json.loads(json_str)

        courses_obj_lst: list[Course] = []
        for c in courses_lst:
            courses_obj_lst.append(Course.from_json(c))

        return Bookings(courses_obj_lst)
