"""Courselist class."""

import json

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
    def from_json_str(json_str):
        """Create instance from JSON."""
        content_dct = json.loads(json_str)
        courses_lst = content_dct["courses"]

        courses_obj_lst = []
        for course in courses_lst:
            courses_obj_lst.append(Course.from_json(course))

        return Courselist(courses_obj_lst)
