"""Platform for sensor integration."""
import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import pytz

from . import MyUpdateCoordinator
from .activ_fitness.api_class import Api
from .base_sensors import BaseSensorCourse
from .const import CHECKINS_DEVICE_ID, COURSES_SHOWN, DOMAIN, SensorType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up entry."""
    _LOGGER.warning("Hello from sensor, async_setup_entry")

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    def course_template(course_no):
        return [
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.TITLE,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.INSTRUCTOR,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.LOCATION,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.START,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.MAX_PERSONS,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.ACTUAL_PERSONS,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.BOOKING_LEVEL,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.COURSE_ID,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.BOOKABLE,
                coordinator=coordinator,
            ),
            CourseSensor(
                course_no=course_no,
                sensor_type=SensorType.BOOKED,
                coordinator=coordinator,
            ),
        ]

    new_entities = [
        CheckinsTotalSensor(coordinator=coordinator),
        CheckinsTotalTotalSensor(coordinator=coordinator),
        LastCheckinSensor(coordinator=coordinator),
    ]

    for i in range(COURSES_SHOWN):
        new_entities.extend(course_template(course_no=i))

    async_add_entities(new_entities)


class CourseSensor(BaseSensorCourse, SensorEntity):
    """Representation of a Course Sensor."""

    # def __init__(self,**kwargs):
    def __init__(self, course_no, sensor_type, coordinator: MyUpdateCoordinator):
        """Initialize the sensor. Pass coordinator to CoordinatorEntity."""
        # super().__init__(**kwargs)
        super().__init__(
            course_no=course_no, sensor_type=sensor_type, coordinator=coordinator
        )

        if self._sensor_type == SensorType.START:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        # self._attr_device_class = SensorDeviceClass.
        if self._sensor_type in [SensorType.ACTUAL_PERSONS, SensorType.MAX_PERSONS]:
            self._attr_native_unit_of_measurement = "people"
        if self._sensor_type in [SensorType.BOOKING_LEVEL]:
            self._attr_native_unit_of_measurement = PERCENTAGE
        if self._sensor_type in [SensorType.COURSE_ID]:
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

        self._attributes = {"course_id": course.course_id_tac}
        if self._sensor_type == SensorType.START:
            self._attributes.update(
                {"start_str": datetime.datetime.strftime(course.start_obj, "%a %H:%M")}
            )

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
        _LOGGER.warning("Hello from native_value")

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        course = data.courses[self._course_no]

        timezone = pytz.timezone("Europe/Zurich")
        # self._attr_device_class = SensorDeviceClass.TIMESTAMP
        # self._last_checkin = tz.localize(datetime.datetime.fromisoformat("2022-12-15T17:45:00"))

        match self._sensor_type:
            case SensorType.TITLE:
                return course.title
            case SensorType.START:
                return timezone.localize(course.start_obj)
            case SensorType.INSTRUCTOR:
                return course.instructor
            case SensorType.LOCATION:
                return course.center_name
            case SensorType.MAX_PERSONS:
                return int(course.max_persons)
            case SensorType.ACTUAL_PERSONS:
                return int(course.actual_persons)
            case SensorType.BOOKING_LEVEL:
                return round(course.actual_persons / course.max_persons * 100, 0)
            case SensorType.COURSE_ID:
                return course.course_id_tac
            case SensorType.BOOKABLE:
                return course.bookable
            case SensorType.BOOKED:
                bookings = data.bookings
                return course.course_id_tac in [
                    b.course_id_tac for b in bookings
                ]  # use bookings api to get the state
                return (
                    course.booked
                )  # this is always false. If a logged in user has a booked course, is only visible in the bookings api
            case _:
                return None


class CheckinsTotalSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    # _attr_name = "Checkins Total"
    # _attr_unique_id = f"activ_fitness_checkin_id"
    # _attr_entity_id = f"{Platform.SENSOR}.activ_fitness_checkin"

    def __init__(self, coordinator: MyUpdateCoordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        # self.entity_id = f"{Platform.SENSOR}.{DOMAIN}_checkin"
        self._attr_unique_id = f"{DOMAIN}_checkin_id"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "Checkins"

        _LOGGER.warning(
            "sensor.__init__:  %s, %s", self.entity_id, self._attr_unique_id
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, CHECKINS_DEVICE_ID)
            },
            name="Checkins",
            manufacturer="Activ Fitness",
            suggested_area="Activ Fitness",
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Total (Increasing)"
        # return 'Checkins Total'

    @property
    def native_value(self):
        """Return the state of the sensor."""

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        return data.checkins_in_period


class CheckinsTotalTotalSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    # _attr_name = "Checkins Total"
    # _attr_unique_id = f"activ_fitness_checkin_id"
    # _attr_entity_id = f"{Platform.SENSOR}.activ_fitness_checkin"

    def __init__(self, coordinator: MyUpdateCoordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_has_entity_name = True
        # self.entity_id = f"{Platform.SENSOR}.{DOMAIN}_checkin"
        self._attr_unique_id = f"{DOMAIN}_checkin_id_total"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "Checkins"

        _LOGGER.warning(
            "sensor.__init__:  %s, %s", self.entity_id, self._attr_unique_id
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, CHECKINS_DEVICE_ID)
            },
            name="Checkins",
            manufacturer="Activ Fitness",
            suggested_area="Activ Fitness",
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Total (Total)"
        # return 'Checkins Total'

    @property
    def native_value(self):
        """Return the state of the sensor."""

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data
        return data.checkins_in_period


class LastCheckinSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator: MyUpdateCoordinator):
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
            name="Checkins",
            manufacturer="Activ Fitness",
            suggested_area="Activ Fitness",
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Last"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.warning("LastCheckinSensor: Hello from native_value")

        # if self.coordinator.data is not None:
        if not self.coordinator.data:
            return None
        data: Api = self.coordinator.data

        timezone = pytz.timezone("Europe/Zurich")
        if data.last_checkin is not None:
            return timezone.localize(data.last_checkin)
        return False
