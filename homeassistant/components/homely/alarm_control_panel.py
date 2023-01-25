"""Support for Abode Security System alarm control panels."""
from __future__ import annotations

from homelypy.devices import AlarmStates

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HomelyHomeCoordinator

ICON = "mdi:security"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Homely alarm control panel device."""
    homely_home: HomelyHomeCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([HomelyAlarm(homely_home)])


class HomelyAlarm(alarm.AlarmControlPanelEntity):
    """An alarm_control_panel implementation for Homely."""

    _attr_icon = ICON
    _attr_code_arm_required = True
    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature(0)
        # AlarmControlPanelEntityFeature.ARM_HOME
        # | AlarmControlPanelEntityFeature.ARM_AWAY
        # | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(
        self,
        coordinator: HomelyHomeCoordinator,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__()
        self.coordinator = coordinator
        self.coordinator.alarm_entity = self

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.coordinator.location.alarm_state == AlarmStates.DISARMED.value:
            return STATE_ALARM_DISARMED
        if self.coordinator.location.alarm_state == AlarmStates.ARMED_AWAY.value:
            return STATE_ALARM_ARMED_AWAY
        if self.coordinator.location.alarm_state == AlarmStates.ARMED_STAY.value:
            return STATE_ALARM_ARMED_HOME
        if self.coordinator.location.alarm_state == AlarmStates.ARMED_NIGHT.value:
            return STATE_ALARM_ARMED_NIGHT
        if self.coordinator.location.alarm_state in (
            AlarmStates.ARM_STAY_PENDING.value,
            AlarmStates.ARM_PENDING.value,
            AlarmStates.ARM_NIGHT_PENDING.value,
        ):
            print("Alarm arming")
            return STATE_ALARM_ARMING
        if self.coordinator.location.alarm_state == AlarmStates.ALARM_PENDING.value:
            return STATE_ALARM_PENDING
        if self.coordinator.location.alarm_state == AlarmStates.BREACHED.value:
            return STATE_ALARM_TRIGGERED
        return None

    # def alarm_disarm(self, code: str | None = None) -> None:
    #     """Send disarm command."""
    #     # Not supported
    #     pass

    # def alarm_arm_home(self, code: str | None = None) -> None:
    #     """Send arm home command."""
    #     # Not supported
    #     pass

    # def alarm_arm_away(self, code: str | None = None) -> None:
    #     """Send arm away command."""
    #     # Not supported
    #     pass

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {}
