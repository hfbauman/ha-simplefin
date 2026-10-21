"""Binary Sensor for SimpleFin."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from simplefin4py import Account

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SimpleFinConfigEntry
from .entity import SimpleFinEntity


@dataclass(frozen=True, kw_only=True)
class SimpleFinBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a sensor entity."""

    value_fn: Callable[[Account], bool]


SIMPLEFIN_BINARY_SENSORS: tuple[SimpleFinBinarySensorEntityDescription, ...] = (
    SimpleFinBinarySensorEntityDescription(
        key="possible_error",
        translation_key="possible_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda account: getattr(account, "possible_error", False) or False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SimpleFinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SimpleFIN sensors for config entries."""

    sf_coordinator = config_entry.runtime_data
    accounts = sf_coordinator.data.accounts

    async_add_entities(
        SimpleFinBinarySensor(
            sf_coordinator,
            sensor_description,
            account,
        )
        for account in accounts
        for sensor_description in SIMPLEFIN_BINARY_SENSORS
    )


class SimpleFinBinarySensor(SimpleFinEntity, BinarySensorEntity):
    """Extends SimpleFinEntity with Binary Sensor specific logic."""

    entity_description: SimpleFinBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Use this to get the correct value."""
        return bool(self.entity_description.value_fn(self.account_data))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}
        error_msg = getattr(self.account_data, "error_message", None)
        if error_msg:
            attrs["error_message"] = error_msg
        return attrs
