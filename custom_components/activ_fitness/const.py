"""Constants for the Activ Fitness integration."""

# from enum import Enum
from homeassistant.backports.enum import StrEnum

DOMAIN = "activ_fitness"
UPDATE_INTERVAL = 60 * 15 # in seconds
COURSENAME = "Course"
COURSES_SHOWN = 5
CHECKINS_DEVICE_ID ="checkins_id"


MANUFACTURER = "Activ Fitness"
SUGGESTED_AREA = "Activ Fitness"
LOCATION_PREFIX = "ACTIV FITNESS "

class Sensor_Type(StrEnum):
    TITLE = "title"
    START = "start"
    INSTRUCTOR = "instructor"
    LOCATION = "location"
    MAX_PERSONS = "max_persons"
    ACTUAL_PERSONS ="actual_persons"
    BOOKING_LEVEL ="booking_level"
    COURSE_ID ="course_id"
    BOOKABLE ="bookable"
    BOOKED ="booked"

SENSOR_NAMES = {
    Sensor_Type.TITLE: "Title",
    Sensor_Type.START: "Start",
    Sensor_Type.INSTRUCTOR: "Instructor",
    Sensor_Type.LOCATION:"Location",
    Sensor_Type.MAX_PERSONS: "Persons Max.",
    Sensor_Type.ACTUAL_PERSONS: "Persons Act.",
    Sensor_Type.BOOKING_LEVEL: "Booking Level",
    Sensor_Type.COURSE_ID: "Course Id",
    Sensor_Type.BOOKABLE: "Bookable",
    Sensor_Type.BOOKED: "Booked",
}