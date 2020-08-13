"""Data update coordinator for shark iq vacuums."""

import asyncio
import logging
from typing import Any, Dict, Iterable, Optional, Tuple

from gekitchen import (
    EVENT_APPLIANCE_STATE_CHANGE,
    EVENT_APPLIANCE_INITIAL_UPDATE,
    ErdCodeType,
    GeAppliance,
    GeClient
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, EVENT_ALL_APPLIANCES_READY, UPDATE_INTERVAL
from .api_auth import AsyncConfigEntryAuth
from .appliance_api import ApplianceApi, get_appliance_api_type

_LOGGER = logging.getLogger(__name__)


class GeKitchenUpdateCoordinator(DataUpdateCoordinator):
    """Define a wrapper class to update Shark IQ data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, auth_handler: AsyncConfigEntryAuth) -> None:
        """Set up the SharkIqUpdateCoordinator class."""
        self._hass = hass
        self._config_entry = config_entry
        self._auth_handler = auth_handler
        self._xmpp_credentials = Optional[Dict]
        self.client = None  # type: Optional[GeClient]
        self._appliance_apis = {}  # type: Dict[str, ApplianceApi]

        # Some record keeping to let us know when we can start generating entities
        self._got_roster = True
        self.initialization_future = asyncio.Future()

        super().__init__(hass, _LOGGER, name=DOMAIN)

    def create_ge_client(self, xmpp_credentials: Dict, loop: Optional[asyncio.AbstractEventLoop]) -> GeClient:
        """
        Create a new GeClient object with some helfpull callbacks.

        :param xmpp_credentials: XMPP credentials
        :param loop: Event loop
        :return: GeClient
        """
        client = GeClient(xmpp_credentials, event_loop=loop)
        client.add_event_handler(EVENT_APPLIANCE_INITIAL_UPDATE, self.on_device_initial_update)
        client.add_event_handler(EVENT_APPLIANCE_STATE_CHANGE, self.on_device_update)
        client.add_event_handler('roster_update', self.on_roster_update)
        return client

    @property
    def appliances(self) -> Iterable[GeAppliance]:
        return self.client.appliances.values()

    @property
    def appliance_apis(self) -> Dict[str, ApplianceApi]:
        return self._appliance_apis

    @staticmethod
    def _get_appliance_api(appliance: GeAppliance) -> ApplianceApi:
        api_type = get_appliance_api_type(appliance.appliance_type)
        return api_type(appliance)

    def regenerate_appliance_apis(self):
        """Regenerate the appliance_apis dictionary, adding elements as necessary."""
        for jid, appliance in self.client.appliances.keys():
            if jid not in self._appliance_apis:
                self._appliance_apis[jid] = self._get_appliance_api(appliance)

    async def get_new_client(self):
        if self.client is not None:
            self.client.disconnect()
        if not self._xmpp_credentials:
            self._xmpp_credentials = await self._auth_handler.async_get_xmpp_credentials()

        loop = self._hass.loop
        self.client = GeClient(self._xmpp_credentials, event_loop=loop)

    def start_client(self):
        """Start a new GeClient in the HASS event loop."""
        self.get_new_client()
        asyncio.ensure_future(self.client.process_in_running_loop(), loop=self._hass.loop)

    async def on_device_update(self, data: Tuple[GeAppliance, Dict[ErdCodeType, Any]]):
        """Let HA know there's new state."""
        appliance, _ = data
        try:
            api = self.appliance_apis[appliance.jid.bare]
        except KeyError:
            return
        for entity in api.entities:
            entity.async_write_ha_state()

    @property
    def all_appliances_updated(self) -> bool:
        """True if all appliances have had an initial update."""
        return all([a.initialized for a in self.appliances])

    async def on_roster_update(self, _):
        """When there's a roster update, mark it and maybe trigger all ready."""
        self._got_roster = True
        self.maybe_trigger_all_ready()

    async def on_device_initial_update(self, appliance: GeAppliance):
        """When an appliance first becomes ready, let the system know and schedule periodic updates."""
        self.maybe_trigger_all_ready()
        while self.client.is_connected() and appliance.available:
            await asyncio.sleep(UPDATE_INTERVAL)
            appliance.request_update()

    def maybe_trigger_all_ready(self):
        """See if we're all ready to go, and if so, let the games begin."""
        if self.initialization_future.done():
            # Been here, done this
            return
        if self._got_roster and self.all_appliances_updated:
            self.initialization_future.set_result(True)
            self.client.event(EVENT_ALL_APPLIANCES_READY, None)
