
""" Base Sensors """

import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity,DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from . import MyUpdateCoordinator
from .activ_fitness.api_class import Api 

from .const import DOMAIN, COURSENAME,MANUFACTURER,SUGGESTED_AREA,SENSOR_NAMES

class BaseEntityCourse(CoordinatorEntity,Entity):
    """Representation of a Base Entity related to Courses."""

    def __init__(self,course_no,coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator


        # Shared attributes of course sensor types:
        self._course_no = course_no # used as device identifier. Incremental numbers 1,2,3,4,...

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Use course_no as unique identifier to group sensors as a Course Device:
                (DOMAIN, self._course_no)
            },
            name= f"{COURSENAME} {self._course_no}",
            manufacturer= MANUFACTURER,
            suggested_area = SUGGESTED_AREA,
        )

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        self._attributes ={
            'course_id': data.courses[self._course_no].course_id_tac
        }
        return self._attributes

class BaseSensorCourse(BaseEntityCourse):
    """Representation of a Base Sensor related to Courses."""

    def __init__(self,course_no,sensor_type,coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        super().__init__(course_no=course_no,coordinator=coordinator)

        # Shared attributes of course sensor types:
        self._sensor_type = sensor_type

        self._attr_has_entity_name = True
        self._state = None
        # self.entity_id = f"{Platform.SENSOR}.{DOMAIN}_{COURSENAME.lower()}_{course_no}_{sensor_type}"
        # self._attr_unique_id = self.entity_id 
        self._attr_unique_id = f"{Platform.SENSOR}.{DOMAIN}_{COURSENAME.lower()}_{course_no}_{sensor_type}"
        self._attr_name = f"{SENSOR_NAMES[sensor_type]}"
        # self._attr_name = f"{COURSENAME} {course_no} {SENSOR_NAMES[sensor_type]}"