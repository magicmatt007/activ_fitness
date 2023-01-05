"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from homeassistant.const import Platform
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.helpers import entity_platform

from homeassistant.core import callback

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from . import MyUpdateCoordinator
from .activ_fitness.api_class import Api 

from .const import DOMAIN, COURSENAME, Sensor_Type,COURSES_SHOWN,LOCATION_PREFIX
from .bases_sensor import BaseSensorCourse


_LOGGER = logging.getLogger(__name__)

from typing import Literal, final

# SCAN_INTERVAL = timedelta(seconds=10)

# async def async_setup_entry(hass, config_entry, async_add_devices):
async def async_setup_entry(hass: HomeAssistant,config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):

    # TODO: Read how to implement the polling API: 
    # https://developers.home-assistant.io/docs/integration_fetching_data
    # and here: https://github.com/thebino/rki_covid/blob/master/custom_components/rki_covid/__init__.py
    # and even better here: https://github.com/cyberjunky/home-assistant-garmin_connect/blob/main/custom_components/garmin_connect/sensor.py

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]


    new_entities = []
    for i in range(COURSES_SHOWN):
        new_entities.append(Course_Binary_Sensor(course_no=i,sensor_type=Sensor_Type.BOOKED,coordinator=coordinator))

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


class Course_Binary_Sensor(BaseSensorCourse, BinarySensorEntity):

    # def __init__(self,**kwargs):
    def __init__(self,course_no,sensor_type,coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        # super().__init__(**kwargs)    
        super().__init__(course_no=course_no,sensor_type=sensor_type,coordinator=coordinator)

        self.entity_id = f"{Platform.BINARY_SENSOR}.{DOMAIN}_{COURSENAME.lower()}_{self._course_no}_{self._sensor_type}"
        self._attr_has_entity_name = False # Needs to be False so the automated UI from "Add to Dashboard" really uses the current updated name


    @property
    def is_on(self):
        """Return the state of the sensor."""
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        course = data.courses[self._course_no]
        bookings = data.bookings
        if course.course_id_tac in [b.course_id_tac for b in bookings]:
            return True
        else:
            return False

    @property
    def name(self):
        """Return the name of the sensor."""
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]
        _booked_str = 'BOOKED' if self.is_on else 'NOT BOOKED'
        return f'{course.title} {course.start_str} in {course.center_name.replace(LOCATION_PREFIX,"")} with {course.instructor} - {_booked_str}'

    async def book(self):
        _LOGGER.warning(f"hello from book service in binary_sensor {self.entity_id}")

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]
        if course.bookable and not course.booked:
            await data.login(user=self.coordinator.username,pwd=self.coordinator.password)
            await data.book_course(course_id=course.course_id_tac)
            await self.coordinator.async_refresh()
            _LOGGER.warning(f"Course {course} booked")
        else:
            _LOGGER.warning(f"Course {course} not bookable yet. Try again later")

    async def cancel(self) -> None:
        _LOGGER.warning(f"hello from cancel service in binary_sensor {self.entity_id}")
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        course = data.courses[self._course_no]
        course_id = course.course_id_tac
        booking_ids = [b.booking_id_tac for b in data.bookings if b.course_id_tac == course_id]
        if len(booking_ids)==1:
            await data.cancel_course(booking_id=booking_ids[0])
            await self.coordinator.async_refresh()
            _LOGGER.warning(f"Course {course} with booking id {booking_ids[0]} cancelled")
        else:
            _LOGGER.warning(f"Course {course} was not booked")