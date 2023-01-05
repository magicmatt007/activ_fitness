"""Platform for sensor integration."""
import logging

_LOGGER = logging.getLogger(__name__)

import random

import datetime,pytz
from homeassistant.const import Platform,PERCENTAGE

from homeassistant.helpers.entity import Entity,DeviceInfo


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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
from .bases_sensor import BaseSensorCourse

# SCAN_INTERVAL = datetime.timedelta(seconds=10)

async def async_setup_entry(hass: HomeAssistant,config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    _LOGGER.warning("Hello from sensor, async_setup_entry")

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    def course_template(course_no):
        return [
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.TITLE,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.INSTRUCTOR,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.LOCATION,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.START,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.MAX_PERSONS,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.ACTUAL_PERSONS,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.BOOKING_LEVEL,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.COURSE_ID,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.BOOKABLE,coordinator=coordinator),
        Course_Sensor(course_no=course_no,sensor_type=Sensor_Type.BOOKED,coordinator=coordinator),
        ]

    new_entities = [CheckinsTotalSensor(coordinator=coordinator),
                    LastCheckinSensor(coordinator=coordinator)]

    for i in range(COURSES_SHOWN):
        new_entities.extend(course_template(course_no=i))

    async_add_entities(new_entities)

    


class Course_Sensor(BaseSensorCourse,SensorEntity):
    """Representation of a Course Sensor."""    

    # def __init__(self,**kwargs):
    def __init__(self,course_no,sensor_type,coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        # super().__init__(**kwargs)    
        super().__init__(course_no=course_no,sensor_type=sensor_type,coordinator=coordinator)

        if self._sensor_type == Sensor_Type.START:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        # self._attr_device_class = SensorDeviceClass.
        if self._sensor_type in [Sensor_Type.ACTUAL_PERSONS,Sensor_Type.MAX_PERSONS]:
            self._attr_native_unit_of_measurement = "people"
        if self._sensor_type in [Sensor_Type.BOOKING_LEVEL]:
            self._attr_native_unit_of_measurement = PERCENTAGE
        if self._sensor_type in [Sensor_Type.COURSE_ID]:
            # self._attr_entity_registry_visible_default = False
            self._attr_entity_registry_enabled_default = False
        # if self._sensor_type in [Sensor_Type.START]:
        #     self._attr_extra_state_attributes = {
        #     'course_id': data.courses[self._course_no].course_id_tac
        # }


    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]

        self._attributes ={
            'course_id': course.course_id_tac            
        }
        if self._sensor_type == Sensor_Type.START:
            self._attributes.update({'start_str': datetime.datetime.strftime(course.start_obj,'%a %H:%M')})

        return self._attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.warning("Hello from _handle_coordinator_update")
        _LOGGER.debug("Hello from _handle_coordinator_update")
        # Set default attributes
        # self._attr_extra_state_attributes = self._attrs

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        course = data.courses[self._course_no]

        # self._attr_extra_state_attributes["date_str"]= datetime.datetime.strftime(course.start_obj,'%a %H:%M')

        # # Only update the HA state machine if the vehicle reliably reports its lock state
        # if self.door_lock_state_available:
        #     self._attr_is_locked = self.vehicle.doors_and_windows.door_lock_state in {
        #         LockState.LOCKED,
        #         LockState.SECURED,
        #     }
        #     self._attr_extra_state_attributes[
        #         "door_lock_state"
        #     ] = self.vehicle.doors_and_windows.door_lock_state.value

        super()._handle_coordinator_update()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.warning(f"Hello from native_value")
        
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        course = data.courses[self._course_no]

        tz = pytz.timezone('Europe/Zurich')
        # self._attr_device_class = SensorDeviceClass.TIMESTAMP
        # self._last_checkin = tz.localize(datetime.datetime.fromisoformat("2022-12-15T17:45:00"))

        match self._sensor_type:
            case Sensor_Type.TITLE: return course.title
            case Sensor_Type.START: return tz.localize(course.start_obj) 
            case Sensor_Type.INSTRUCTOR: return course.instructor
            case Sensor_Type.LOCATION: return course.center_name
            case Sensor_Type.MAX_PERSONS: return int(course.max_persons)
            case Sensor_Type.ACTUAL_PERSONS: return int(course.actual_persons)
            case Sensor_Type.BOOKING_LEVEL: return round(course.actual_persons/course.max_persons*100,0)
            case Sensor_Type.COURSE_ID: return course.course_id_tac
            case Sensor_Type.BOOKABLE: return course.bookable
            case Sensor_Type.BOOKED:
                bookings = data.bookings 
                return course.course_id_tac in [b.course_id_tac for b in bookings]  # use bookings api to get the state
                return course.booked # this is always false. If a logged in user has a booked course, is only visible in the bookings api
            case _: return None


class CheckinsTotalSensor(CoordinatorEntity,SensorEntity):
    """Representation of a Sensor."""

    # _attr_name = "Checkins Total"
    # _attr_unique_id = f"activ_fitness_checkin_id"
    # _attr_entity_id = f"{Platform.SENSOR}.activ_fitness_checkin"

    def __init__(self,coordinator: MyUpdateCoordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        # self.entity_id = f"{Platform.SENSOR}.{DOMAIN}_checkin"
        self._attr_unique_id = f"{DOMAIN}_checkin_id"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "Checkins"


        _LOGGER.warning(f"sensor.__init__:  {self.entity_id}, {self._attr_unique_id}")

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, CHECKINS_DEVICE_ID)
            },
            name= f"Checkins",
            manufacturer= "Activ Fitness",
            suggested_area ="Activ Fitness",
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Total'
        # return 'Checkins Total'

    @property
    def native_value(self):
        """Return the state of the sensor."""

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        return data.checkins_in_period


class LastCheckinSensor(CoordinatorEntity,SensorEntity):
    """Representation of a Sensor."""

    def __init__(self,coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        # self.entity_id = f"{Platform.SENSOR}.{DOMAIN}_last_checkin"
        self._attr_unique_id = f"{DOMAIN}_last_checkin_id"
        self._attributes = None
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, CHECKINS_DEVICE_ID)
            },
            name= f"Checkins",
            manufacturer= "Activ Fitness",
            suggested_area ="Activ Fitness",
        )
   

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Last'
        return 'Last Checkin'

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.warning(f"LastCheckinSensor: Hello from native_value")
        
        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        
        tz = pytz.timezone('Europe/Zurich')
        if data.last_checkin is not None:
            return tz.localize(data.last_checkin)
        else:
            return False
        # return self._last_checkin  
