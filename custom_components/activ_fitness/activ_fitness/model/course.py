"""Course class."""

import datetime
import time
import zoneinfo

CLUB_TIMEZONE = zoneinfo.ZoneInfo("Europe/Zurich")

# Netpulse GroupX "availableActions" that mean the exerciser can book this class right now.
BOOKABLE_ACTIONS = {"ADD_TO_CLASS", "ADD_TO_CLASS_PURCHASE_NEEDED"}


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
        center_name,
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
        self.center_name = center_name

    def __str__(self):
        return f"{self.start_end_str} {self.title} {self.center_name} {self.instructor} {self.actual_persons}/{self.max_persons} Bookable: {self.bookable} Course Id: {self.course_id_tac} Booked: {self.booked} Booking Id: {self.booking_id_tac}"

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
    def _epoch_ms_to_naive_local_iso(epoch_ms: int) -> str:
        """Convert a UTC epoch-ms timestamp to a naive Europe/Zurich local ISO string.

        Naive (tzinfo stripped) because sensor.py later does pytz_tz.localize(course.start_obj).
        """
        aware = datetime.datetime.fromtimestamp(epoch_ms / 1000, tz=CLUB_TIMEZONE)
        return aware.replace(tzinfo=None).isoformat()

    def apply_details(self, json_dct):
        """Set `bookable` from GET /np/company/{club}/class/{id}?exerciserUuid=...

        Unlike the class list, this response has the booking window
        (details.bookingWindowStart/End) and the exerciser's availableActions.
        `bookable` means "open for booking": inside the window and, unless the
        user has booked it already, offering an add action. It stays True for a
        booked class inside the window, as with the old API.
        """
        details = json_dct.get("details") or {}
        attendee = json_dct.get("attendeeDetails") or {}
        now_ms = time.time() * 1000
        window_start = details.get("bookingWindowStart")
        window_end = details.get("bookingWindowEnd")
        in_window = (window_start is None or now_ms >= window_start) and (
            window_end is None or now_ms < window_end
        )
        if self.booked:
            self.bookable = in_window
        else:
            actions = set(attendee.get("availableActions") or [])
            self.bookable = in_window and bool(actions & BOOKABLE_ACTIONS)

    @staticmethod
    def from_groupx_json(json_dct, center_name):
        """Create instance from a Netpulse GroupXClass JSON object.

        See GET /np/company/{clubUuid}/classes and GET /np/exerciser/{uuid}/schedule.
        """
        brief = json_dct["brief"]
        attendee = json_dct.get("attendeeDetails") or {}

        instructor_dct = brief.get("instructor") or {}
        instructor = instructor_dct.get("fullName") or ""

        is_booked = bool(attendee.get("booked", False))
        max_persons = brief.get("maxCapacity") or 0
        actual_persons = brief.get("totalBooked") or 0
        start_ms = brief["startDateTime"]

        # "bookable" is not in the class list: the booking window and the available
        # actions are only in the single-class lookup, see apply_details(). Until
        # that has been applied, the class counts as not bookable.
        bookable = False

        course_id = brief["id"]

        return Course(
            center_id=brief.get("clubUuid"),
            course_id_tac=course_id,
            title=brief["name"],
            instructor=instructor,
            start=Course._epoch_ms_to_naive_local_iso(start_ms),
            end=Course._epoch_ms_to_naive_local_iso(brief["endDateTime"]),
            max_persons=max_persons,
            actual_persons=actual_persons,
            boooked=is_booked,
            bookable=bookable,
            # The new API has no separate booking id - the class id itself identifies
            # both the class and (if booked) the booking, so re-use it here.
            booking_id_tac=course_id,
            center_name=center_name,
        )
