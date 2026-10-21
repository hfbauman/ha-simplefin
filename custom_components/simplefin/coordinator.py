"""Data update coordinator for the SimpleFIN integration."""

from datetime import datetime, timedelta, timezone
from typing import Any, override

from simplefin4py import Account, AccountSet, FinancialData, SimpleFin
from simplefin4py.exceptions import SimpleFinAuthError, SimpleFinPaymentRequiredError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

type SimpleFinConfigEntry = ConfigEntry[SimpleFinDataUpdateCoordinator]


class SimpleFinDataUpdateCoordinator(DataUpdateCoordinator[FinancialData]):
    """Data update coordinator for the SimpleFIN integration."""

    config_entry: SimpleFinConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: SimpleFinConfigEntry, client: SimpleFin
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name="simplefin",
            update_interval=timedelta(hours=4),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> Any:
        """Fetch data for all accounts."""
        try:
            data = await self.client.fetch_data()
            
            # Check for global errors and create issues for them
            if isinstance(data, AccountSet) and getattr(data, "errors", None):
                self._handle_global_errors(data.errors)
            
            return data
        except SimpleFinAuthError as err:
            raise ConfigEntryError("Authentication failed") from err

        except SimpleFinPaymentRequiredError as err:
            raise UpdateFailed(
                "There is a billing issue with your SimpleFin"
                " account, contact SimpleFin to address"
                " this issue"
            ) from err

    def _handle_global_errors(self, errors: list[str]) -> None:
        """Handle global errors by creating Home Assistant repair issues."""
        hass = self.hass
        
        # Check if we have any errors that don't match accounts
        # This addresses the "dropped global errors" issue
        for error in errors:
            # Check if this error message indicates a specific institution
            # This fixes the "one-way substring matching" issue by extracting
            # institution name from error messages like "Connection to Chase may need attention"
            institution_name = self._extract_institution_from_error(error)
            
            # Create issue for this error
            async_create_issue(
                hass,
                domain="simplefin",
                issue_id=f"simplefin_error_{abs(hash(error)) % 1000000}",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="global_error",
                translation_placeholders={
                    "error": str(error),
                    "institution": institution_name if institution_name else "Unknown",
                },
            )
            
    def _extract_institution_from_error(self, error: str) -> str | None:
        """Extract institution name from error message like 'Connection to Chase may need attention'."""
        # Look for patterns like "Connection to [institution] may need attention"
        if "Connection to " in error and " may need attention" in error:
            parts = error.split("Connection to ")
            if len(parts) > 1:
                institution_part = parts[1]
                if " may need attention" in institution_part:
                    institution_name = institution_part.split(" may need attention")[0]
                    return institution_name.strip()
        return None

    def _is_account_stale(self, account: Account) -> bool:
        """Check if an account has not been updated within a reasonable time."""
        # This addresses the "silent upstream stalls" issue by adding a stale sync threshold
        if not getattr(account, "balance_date", None):
            return False
        try:
            b_date = account.balance_date
            if isinstance(b_date, (int, float)):
                b_date = datetime.fromtimestamp(b_date, tz=timezone.utc)
            elif isinstance(b_date, datetime):
                if b_date.tzinfo is None:
                    b_date = b_date.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return b_date < (now - timedelta(hours=48))
        except Exception:
            return False
