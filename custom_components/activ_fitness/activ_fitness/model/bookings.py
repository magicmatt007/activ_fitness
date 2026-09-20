"""Bookings class"""

from .course import Course


class Bookings:
    """Bookings data class."""

    def __init__(self, courses):
        self.courses: list[Course] = courses

    @staticmethod
    def from_groupx_json_list(classes_json_lst, centers_by_id):
        """Create instance from GET /np/exerciser/{uuid}/schedule (a list of GroupXClass)."""
        courses_obj_lst: list[Course] = []
        for course in classes_json_lst:
            club_uuid = course["brief"].get("clubUuid")
            center_name = centers_by_id.get(club_uuid, club_uuid)
            courses_obj_lst.append(Course.from_groupx_json(course, center_name))

        return Bookings(courses_obj_lst)
