import datetime

from ..centers_dct import centers_manual


class Course:
    """Course data class."""

    def __init__(
        self,
        center_id,
        course_id_tac,
        title,
        instructor,
        start,
        end,
        max_persons,
        actual_persons,
        boooked,
        bookable,
        booking_id_tac,
    ):
        self.center_id = center_id
        self.course_id_tac = course_id_tac
        self.title = title
        self.instructor = instructor
        self.start = start
        self.start_obj = datetime.datetime.fromisoformat(start)
        self.start_str = self.start_obj.strftime("%a %H:%M")
        self.end = end
        self.end_obj = datetime.datetime.fromisoformat(end)
        self.end_str = self.end_obj.strftime("%a %H:%M")
        self.start_end_str = (
            f"{self.start_obj.strftime('%a %H:%M')}-{self.end_obj.strftime('%H:%M')}"
        )
        self.max_persons = max_persons
        self.actual_persons = actual_persons
        self.booked = boooked
        self.bookable = bookable
        self.booking_id_tac = booking_id_tac
        self.center_name = centers_manual[self.center_id]

    def __str__(self):
        return f"{self.start_end_str} {self.title} {centers_manual[self.center_id]} {self.instructor} {self.actual_persons}/{self.max_persons} Bookable: {self.bookable} Course Id: {self.course_id_tac} Booked: {self.booked} Booking Id: {self.booking_id_tac}"

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        yield from {
            "center_id": self.center_id,
            "course_id_tac": self.course_id_tac,
            "title": self.title,
            "instructor": self.instructor,
            "start": self.start,
            "end": self.end,
            "max_persons": self.max_persons,
            "actual_persons": self.actual_persons,
            "booked": self.booked,
            "bookable": self.bookable,
            "booking_id_tac": self.booking_id_tac,
        }.items()

    @staticmethod
    def from_json(json_dct):
        """Create instance from JSON."""
        return Course(
            json_dct["centerId"],
            json_dct["courseIdTac"],
            json_dct["title"],
            json_dct["instructor"],
            json_dct["start"],
            json_dct["end"],
            json_dct["maxPersons"],
            json_dct["actualPersons"],
            json_dct["booked"],
            json_dct["bookable"],
            json_dct["bookingIdTac"],
        )
