"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import MyUpdateCoordinator
from .activ_fitness.api_class import Api
from .base_sensors import BaseSensorCourse
from .const import COURSENAME, COURSES_SHOWN, DOMAIN, LOCATION_PREFIX, SensorType

_LOGGER = logging.getLogger(__name__)


# SCAN_INTERVAL = timedelta(seconds=10)

# async def async_setup_entry(hass, config_entry, async_add_devices):
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up entry."""

    # TO DO: Read how to implement the polling API:
    # https://developers.home-assistant.io/docs/integration_fetching_data
    # and here: https://github.com/thebino/rki_covid/blob/master/custom_components/rki_covid/__init__.py
    # and even better here: https://github.com/cyberjunky/home-assistant-garmin_connect/blob/main/custom_components/garmin_connect/sensor.py

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    new_entities = []
    for i in range(COURSES_SHOWN):
        new_entities.append(
            CourseBinarySensor(
                course_no=i, sensor_type=SensorType.BOOKED, coordinator=coordinator
            )
        )

    async_add_entities(new_entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "book",
        {},
        "book",
    )

    platform.async_register_entity_service(
        "cancel",
        {},
        "cancel",
    )

    platform.async_register_entity_service(
        "toggle_booking",
        {},
        "toggle_booking",
    )


class CourseBinarySensor(BaseSensorCourse, BinarySensorEntity):
    """Course Binary Sensor class."""

    # def __init__(self,**kwargs):
    def __init__(self, course_no, sensor_type, coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        # super().__init__(**kwargs)
        super().__init__(
            course_no=course_no, sensor_type=sensor_type, coordinator=coordinator
        )

        self.entity_id = f"{Platform.BINARY_SENSOR}.{DOMAIN}_{COURSENAME.lower()}_{self._course_no}_{self._sensor_type}"
        self._attr_has_entity_name = False  # Needs to be False so the automated UI from "Add to Dashboard" really uses the current updated name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        # course = data.courses[self._course_no]
        # bookings = data.bookings
        # if course.course_id_tac in [b.course_id_tac for b in bookings]:
        #     return True
        # return False

        return data.is_booked(self._course_no)

    # @property
    # def state(self):
    #     if self.is_on:
    #         return "booked"
    #     return "not booked"

    @property
    def name(self):
        """Return the name of the sensor."""
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]
        _booked_str = "BOOKED" if self.is_on else "NOT BOOKED"
        _bookable_str = (
            "BOOKABLE" if data.courses[self._course_no].bookable else "NOT BOOKABLE"
        )
        # return f'{course.title} {course.start_str} in {course.center_name.replace(LOCATION_PREFIX,"")} with {course.instructor} - {_booked_str}'
        return f'{course.title} {course.start_str} in {course.center_name.replace(LOCATION_PREFIX,"")} with {course.instructor} - {_bookable_str}'

    async def book(self):
        """Book course."""
        _LOGGER.warning("hello from book service in binary_sensor %s", self.entity_id)

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]
        if data.is_booked(self._course_no):
            _LOGGER.warning("Course %s already booked", course)
            return
        if not course.bookable:
            _LOGGER.warning("Course %s not bookable yet. Try again later", {course})
            return

        await data.login(user=self.coordinator.username, pwd=self.coordinator.password)
        await data.book_course(course_id=course.course_id_tac)
        await self.coordinator.async_refresh()
        _LOGGER.warning("Course %s booked", course)

    async def cancel(self) -> None:
        """Cancel course."""
        _LOGGER.warning("hello from cancel service in binary_sensor %s", self.entity_id)
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        course = data.courses[self._course_no]
        course_id = course.course_id_tac
        booking_ids = [
            b.booking_id_tac for b in data.bookings if b.course_id_tac == course_id
        ]
        if len(booking_ids) == 1:
            await data.cancel_course(booking_id=booking_ids[0])
            await self.coordinator.async_refresh()
            _LOGGER.warning(
                "Course %s with booking id %s cancelled", course, booking_ids[0]
            )
        else:
            _LOGGER.warning("Course %s was not booked", course)

    async def toggle_booking(self) -> None:
        """Toggle course booking"""
        _LOGGER.warning(
            "hello from toggle_booking service in binary_sensor %s", self.entity_id
        )

        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]

        _LOGGER.warning("course.bookable: %s", course.bookable)
        _LOGGER.warning(
            "course.booked: %s",
            data.is_booked(self._course_no),
        )

        if course.bookable:
            if not data.is_booked(self._course_no):
                # Book course:
                await self.book()
                _LOGGER.warning("Course %s booked via toggle")
            else:
                # Cancel course:
                await self.cancel()
                _LOGGER.warning("Course %s cancelled", course)
        else:
            _LOGGER.warning(
                "Course %s not bookable yet (toggle). Try again later", course
            )
