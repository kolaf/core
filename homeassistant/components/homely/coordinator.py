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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .homely_device import HomelyDevice

_LOGGER = logging.getLogger(__name__)

MAXIMUM_CONTIGUOUS_CONNECTION_ERRORS = 2


class HomelyHomeCoordinator(DataUpdateCoordinator):
    """A Homely location."""

    alarm_entity: Entity

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
        self.contiguous_connection_errors: int = 0

    def websocket_callback(
        self, single_location: SingleLocation, device: Device, states: list[State]
    ):
        """Update devices that are received through web socket streaming."""
        if device is not None:
            _LOGGER.debug("Received update %s", device)
            self.devices[device.id].update(device)
            for entity in self.devices[device.id].entities:
                entity.schedule_update_ha_state(force_refresh=True)
        if single_location is not None:
            # If the single_location is updated it means that we have received an alarm state change.
            # The SingleLocation object is updated by the homelypy library, so we only need to trigger the entity to read the new data
            if self.alarm_entity:
                _LOGGER.debug("Received update for alarm state")
                self.location.alarm_state = single_location.alarm_state
                self.location.alarm_state_last_updated = (
                    single_location.alarm_state_last_updated
                )
                self.alarm_entity.schedule_update_ha_state(force_refresh=True)

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
        try:
            self.location = await self.hass.async_add_executor_job(
                self.homely.get_location, self.location.location_id
            )
            self.contiguous_connection_errors = 0
        except ConnectionError:
            # The API can be a bit flaky, but we are probably still connected to the websocket.
            # We therefore hold back a bit on raising the error until it has happened a few times in a row.
            self.contiguous_connection_errors += 1
            _LOGGER.warning(
                "Error connecting to the Homely API. This is failure number %d in a row, over maximum of %d contiguous errors",
                self.contiguous_connection_errors,
                MAXIMUM_CONTIGUOUS_CONNECTION_ERRORS,
            )
            if self.contiguous_connection_errors > MAXIMUM_CONTIGUOUS_CONNECTION_ERRORS:
                _LOGGER.error(
                    "The number of contiguous errors is too large, raising the exception"
                )
                raise
            _LOGGER.info(
                "The number of contiguous errors is below the limit, swallowing the error and hope this resolves itself"
            )
