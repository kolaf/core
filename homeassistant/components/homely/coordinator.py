"""Coordinator for the Homely service."""
from datetime import timedelta
import logging
from threading import Thread

from homelypy.devices import Device, SingleLocation
from homelypy.homely import ConnectionFailedException, Homely
from homelypy.states import State
from requests import ConnectTimeout, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .homely_device import HomelyDevice

_LOGGER = logging.getLogger(__name__)


class HomelyHomeCoordinator(DataUpdateCoordinator):
    """A Homely location."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up data properties."""
        self.location_id = entry.data["location_id"]
        super().__init__(
            hass,
            _LOGGER,
            name=f"Homely {self.location_id}",
            update_interval=timedelta(minutes=5),
        )
        self.username = entry.data["username"]
        self.password = entry.data["password"]
        self.location: SingleLocation = None
        self.homely: Homely = None
        self.devices: dict[str, HomelyDevice] = {}

    def websocket_callback(self, device: Device, states: list[State]):
        """Update devices that are received through web socket streaming."""
        print(f"Received update {device}")
        self.devices[device.id].update(device)
        for entity in self.devices[device.id].entities:
            entity.schedule_update_ha_state(force_refresh=True)

    async def setup(self) -> None:
        """Perform initial setup."""
        self.homely = Homely(self.username, self.password)
        try:
            self.location = await self.hass.async_add_executor_job(
                self.homely.get_location, self.location_id
            )
        except (ConnectionFailedException, ConnectTimeout, HTTPError) as ex:
            raise ConfigEntryNotReady(f"Unable to connect to Homely: {ex}") from ex
        Thread(
            target=self.homely.run_socket_io,
            args=[self.location, self.websocket_callback],
        ).start()
        await self.update_devices()

    async def update_devices(self) -> None:
        """To be called in setup for initial configuration of devices."""
        for device in self.location.devices:
            self.devices[device.id] = HomelyDevice(device.id)
            self.devices[device.id].update(device)

    async def _async_update_data(self) -> None:
        self.location = await self.hass.async_add_executor_job(
            self.homely.get_location, self.location.location_id
        )
