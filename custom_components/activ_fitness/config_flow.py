"""Config flow for Activ Fitness integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.helpers.selector import selector
from homeassistant.helpers import aiohttp_client

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .activ_fitness.api_class import Api 
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
# data_schema=vol.Schema({vol.Required(ATTR_COUNTY): vol.In(self._options)}),

_centers = [
     "ACTIV FITNESS Aarau Bahnhof",
     "ACTIV FITNESS Aarau Industrie",
     "ACTIV FITNESS Abtwil SG Säntispark",
     "ACTIV FITNESS Schlieren",
     "ACTIV FITNESS Dietikon",
     "ACTIV FITNESS Altstetten Bhf."
]

_courses = [
     "BODYPUMP® 55'",
     "Pilates 55min",
     "Yoga 55'",
     "ZUMBA® 55'",
     "BODYPUMP 55min",
     "M.A.X.® 25'",
]


# STEP_USER_DATA_SCHEMA = vol.Schema( {
#         vol.Required("username"): str,
#         vol.Required("password"): str,
#         "centers": selector({
#                 "select": {
#                     "options": _centers,
#                     "multiple": True,
#                     "mode": "list"
#                 }
#             })
#     })

# STEP_2_SCHEMA = vol.Schema({
#         "courses": selector({
#                 "select": {
#                     "options": _courses,
#                     "multiple": True,
#                     "mode": "list"
#                 }
#             })
#     })

class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    # hub = PlaceholderHub(data["host"])

    # if not await hub.authenticate(data["username"], data["password"]):
    #     raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "Activ Fitness"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Activ Fitness."""

    VERSION = 1.1
    input_data = {}
    coursetitles_sorted = []


    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""


        session = aiohttp_client.async_get_clientsession(self.hass)
        ssl_context = False
        _api = Api(session=session,ssl_context=ssl_context)
        centers_dict = (await _api.get_center_ids()).centers_by_name
        centers_lst = list(centers_dict.keys())
        _LOGGER.warning(f"ConfigFlow - Centers by name: {centers_lst}")

        STEP_USER_DATA_SCHEMA = vol.Schema( {
        vol.Required("username"): str,
        vol.Required("password"): str,
        "centers": selector({
                "select": {
                    "options": centers_lst,
                    "multiple": True,
                    "mode": "list"
                }
            })
    })

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.input_data = user_input
            _LOGGER.warning(f"Selected centers: {user_input['centers']}")
            center_ids = [centers_dict[c]  for c in user_input['centers'] ]
            _LOGGER.warning(f"Selected center ids: {center_ids}")
            self.input_data.update({"center_ids":center_ids})


            self._coursetitles_sorted = sorted((await _api.get_course_list(centerIds=center_ids)).coursetitles)
            _LOGGER.warning(f"Courses in these centers: {self._coursetitles_sorted}")


            return await self.async_step_courses()
            # return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_courses(
            self, user_input: dict[str, Any] | None = None
        ) -> FlowResult:
            """Handle the initial step."""

            STEP_2_SCHEMA = vol.Schema({
                "courses": selector({
                "select": {
                    "options": self._coursetitles_sorted,
                    "multiple": True,
                    "mode": "list"
                }
            })
    })



            if user_input is None:
                return self.async_show_form(
                    step_id="courses", data_schema= STEP_2_SCHEMA
                )

            errors = {}

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.input_data.update(user_input)
                return self.async_create_entry(title=info["title"], data=self.input_data)

            return self.async_show_form(
                step_id="courses", data_schema=STEP_2_SCHEMA, errors=errors
            )



class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
