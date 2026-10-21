"""Binary Sensor for SimpleFin."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from simplefin4py import Account

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

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
        value_fn=lambda account: account.possible_error or False,
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
    
    # Add a check for stale accounts to address silent upstream stalls
    if hasattr(sf_coordinator, '_is_account_stale'):
        for account in accounts:
            if sf_coordinator._is_account_stale(account):
                async_create_issue(
                    hass,
                    domain="simplefin",
                    issue_id=f"stale_account_{account.id}",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="stale_account",
                    translation_placeholders={
                        "account_name": getattr(account, "name", "Account"),
                        "institution": getattr(account.org, "name", "Institution") if getattr(account, "org", None) else "Unknown",
                    },
                )

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
        return self.entity_description.value_fn(self.account_data)
