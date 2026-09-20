"""Courselist class."""

from .course import Course


class Courselist:
    """Courselist class."""

    def __init__(self, courses):
        self.courses: list[Course] = courses

    @property
    def coursetitles(self):
        """Property Course Titles as set."""
        return {c.title for c in self.courses}

    @property
    def courses_bookable(self):
        """Property if course is bookable."""
        return [c for c in self.courses if c.bookable]

    @staticmethod
    def from_groupx_json_list(classes_json_lst, center_name):
        """Create instance from a list of Netpulse GroupXClass JSON objects."""
        courses_obj_lst = [
            Course.from_groupx_json(course, center_name) for course in classes_json_lst
        ]
        return Courselist(courses_obj_lst)
