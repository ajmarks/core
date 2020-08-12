"""The ge_kitchen integration."""

import asyncio
import async_timeout

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from gekitchen.const import OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET
from . import api_auth, config_flow
from .const import (
    AUTH_HANDLER,
    COORDINATOR,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from .update_coordinator import GeKitchenUpdateCoordinator

# CONFIG_SCHEMA = vol.Schema(
#     {
#         DOMAIN: vol.Schema(
#             {
#                 vol.Required(CONF_CLIENT_ID): cv.string,
#                 vol.Required(CONF_CLIENT_SECRET): cv.string,
#             }
#         )
#     },
#     extra=vol.ALLOW_EXTRA,
# )

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the ge_kitchen component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            OAUTH2_CLIENT_ID,
            OAUTH2_CLIENT_SECRET,
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up ge_kitchen from a config entry."""
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth_handler = api_auth.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )
    coordinator = GeKitchenUpdateCoordinator(hass, entry, auth_handler)
    coordinator.get_new_client()
    coordinator.start_client()
    with async_timeout.timeout(20):
        await coordinator.initialization_future

    hass.data[DOMAIN][entry.entry_id] = {
        AUTH_HANDLER: auth_handler,
        COORDINATOR: coordinator,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
