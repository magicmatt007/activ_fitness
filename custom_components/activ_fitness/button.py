"""Platform for sensor integration."""
import logging

_LOGGER = logging.getLogger(__name__)

import random

import datetime,pytz
from homeassistant.const import Platform

from homeassistant.helpers.entity import Entity,DeviceInfo

from homeassistant.components.button import (
    ButtonEntity,
) 
from homeassistant.core import callback


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

from .const import DOMAIN, COURSENAME,CHECKINS_DEVICE_ID,MANUFACTURER,SUGGESTED_AREA,Sensor_Type,SENSOR_NAMES,COURSES_SHOWN
from .bases_sensor import BaseEntityCourse

# SCAN_INTERVAL = datetime.timedelta(seconds=10)

async def async_setup_entry(hass: HomeAssistant,config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    _LOGGER.warning("Hello from sensor, async_setup_entry")

    # coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    coordinator: MyUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    new_entities = []
    for i in range(COURSES_SHOWN):
        new_entities.append(BookButton(course_no=i,coordinator=coordinator))
        new_entities.append(CancelButton(course_no=i,coordinator=coordinator))

    async_add_entities(new_entities)

class BookButton(BaseEntityCourse,ButtonEntity):
    """ Book Button """

    def __init__(self,course_no,coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        super().__init__(course_no=course_no,coordinator=coordinator)

        self._state = None
        self._attr_unique_id = f"{Platform.BUTTON}.{DOMAIN}_{COURSENAME.lower()}_{course_no}_book"
        self._attr_has_entity_name = True
        self._attr_name = f"Book"

    async def async_press(self) -> None:
        """Handle the button press."""
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]
        if course.bookable and not course.booked:
            await data.book_course(course_id=course.course_id_tac)
            await self.coordinator.async_refresh()
            _LOGGER.warning(f"Course {course} booked")
        else:
            _LOGGER.warning(f"Course {course} not bookable yet. Try again later")

class CancelButton(BaseEntityCourse,ButtonEntity):
    """ Cancel Button """

    def __init__(self,course_no,coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        super().__init__(course_no=course_no,coordinator=coordinator)

        self._state = None
        self._attr_unique_id = f"{Platform.BUTTON}.{DOMAIN}_{COURSENAME.lower()}_{course_no}_cancel"
        self._attr_has_entity_name = True
        self._attr_name = f"Cancel"

    async def async_press(self) -> None:
        """Handle the button press."""
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

