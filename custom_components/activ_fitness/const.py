"""Constants for the Activ Fitness integration."""

# from enum import Enum
from homeassistant.backports.enum import StrEnum

DOMAIN = "activ_fitness"
UPDATE_INTERVAL = 60 * 15  # in seconds
COURSENAME = "Course"
COURSES_SHOWN = 5
CHECKINS_DEVICE_ID = "checkins_id"


MANUFACTURER = "Activ Fitness"
SUGGESTED_AREA = "Activ Fitness"
LOCATION_PREFIX = "ACTIV FITNESS "


class SensorType(StrEnum):
    """SensorType class."""

    TITLE = "title"
    START = "start"
    INSTRUCTOR = "instructor"
    LOCATION = "location"
    MAX_PERSONS = "max_persons"
    ACTUAL_PERSONS = "actual_persons"
    BOOKING_LEVEL = "booking_level"
    COURSE_ID = "course_id"
    BOOKABLE = "bookable"
    BOOKED = "booked"


SENSOR_NAMES = {
    SensorType.TITLE: "Title",
    SensorType.START: "Start",
    SensorType.INSTRUCTOR: "Instructor",
    SensorType.LOCATION: "Location",
    SensorType.MAX_PERSONS: "Persons Max.",
    SensorType.ACTUAL_PERSONS: "Persons Act.",
    SensorType.BOOKING_LEVEL: "Booking Level",
    SensorType.COURSE_ID: "Course Id",
    SensorType.BOOKABLE: "Bookable",
    SensorType.BOOKED: "Booked",
}
