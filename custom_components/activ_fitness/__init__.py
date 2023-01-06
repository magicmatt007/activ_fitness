"""The example sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# from .activ_fitness import api
from .activ_fitness.api_class import Api
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

ATTR_NAME = "entity_id"
DEFAULT_NAME = "<enter course id>"


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up is called when Home Assistant is loading our component."""

    session = aiohttp_client.async_get_clientsession(hass)
    ssl_context = False
    _api = Api(session=session, ssl_context=ssl_context)

    # hass.data[DOMAIN] = _api
    # hass.data.setdefault(DOMAIN, {})[entry.entry_id] = my_api

    # Service book_course
    async def book_course(call: ServiceCall):
        """Handle the service call book_course."""

        entity_ids = call.data.get(ATTR_NAME, DEFAULT_NAME)
        # entity_ids = call.target
        _LOGGER.warning("book_course: %s", entity_ids)

        attributes = hass.states.get(entity_ids[0]).attributes
        _LOGGER.warning("book_course attributes: %s", attributes)
        course_id = attributes["course_id"]
        _LOGGER.warning("book_course id: %s", course_id)

        await hass.states.async_set("activ_fitness.book_course", entity_ids)

    # Service book_course
    async def get_course_list(call: ServiceCall):
        """Handle the service call book_course."""

        courselist = await _api.get_course_list(
            coursetitles=[""], center_ids=[23, 33, 54]
        )
        _LOGGER.warning("get_course_list: %s", courselist.courses_bookable)
        _LOGGER.warning(
            "get_course_list: %s", courselist.courses_bookable[0].course_id_tac
        )

        hass.states.async_set("activ_fitness.get_courselist", courselist.courses)

    # Register above services:
    hass.services.async_register(DOMAIN, "book_course", book_course)
    hass.services.async_register(DOMAIN, "get_course_list", get_course_list)

    # username = entry.data['username']

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry."""
    username = entry.data["username"]
    centers = entry.data["centers"]
    center_ids = entry.data["center_ids"]
    courses = entry.data["courses"]
    _LOGGER.warning("User input %s %s %s %s", username, centers, center_ids, courses)

    # #TO DO: get Api object:
    # my_api = "dummy_api"
    # # hass.data[DOMAIN][entry.entry_id] = my_api
    # hass.data.setdefault(DOMAIN, {})[entry.entry_id] = my_api

    # # hass.data[DOMAIN] = my_api

    coordinator = MyUpdateCoordinator(
        hass, entry, selected_centers=center_ids, selected_course_names=courses
    )
    await coordinator.async_config_entry_first_refresh()
    # await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # if unload_ok:
    #     hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class MyUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self,
        hass,
        entry: ConfigEntry,
        selected_centers: list[int],
        selected_course_names: list[str],
    ):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Activ Fitness",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry = entry
        self.username = entry.data["username"]
        self.password = entry.data["password"]

        self.selected_course_names = selected_course_names
        self.selected_centers = selected_centers
        session = aiohttp_client.async_get_clientsession(hass)
        ssl_context = False
        self._api = Api(session=session, ssl_context=ssl_context)

    async def _async_update_data(self) -> Api | None:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        _LOGGER.warning("Hello from _async_update_data")
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            # selected_centers= [54] # 54 = Schlieren, 96 = Olten
            # selected_course_names = ["BODYPUMP® 55'"]

            async with async_timeout.timeout(15):
                await self._api.login(user=self.username, pwd=self.password)
                await self._api.get_center_ids()
                await self._api.get_course_list(
                    coursetitles=self.selected_course_names,
                    center_ids=self.selected_centers,
                )
                await self._api.get_bookings()
                await self._api.get_checkins()
                return self._api

        # except ApiAuthError as err:
        #     # Raising ConfigEntryAuthFailed will cancel future updates
        #     # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        #     raise ConfigEntryAuthFailed from err
        # except ApiError as err:
        #     raise UpdateFailed(f"Error communicating with API: {err}")
        except Exception as error:
            _LOGGER.error("Error %s in MyCoordinator _async_update_data", error)

        # return self._api
        # return {"update": "Hello update!"}
