"""Data update coordinator for the SimpleFIN integration."""

from datetime import datetime, timedelta, timezone
from typing import Any, override

from simplefin4py import Account, FinancialData, SimpleFin
from simplefin4py.exceptions import SimpleFinAuthError, SimpleFinPaymentRequiredError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir
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
        # Clear any existing repair issues for simplefin so they do not clutter the Repairs dashboard
        self._clear_repair_issues()

        try:
            data = await self.client.fetch_data()
            
            # Directly apply errors to matching accounts so binary_sensor updates
            if isinstance(data, FinancialData):
                self._apply_errors_to_accounts(data)
            
            return data
        except SimpleFinAuthError as err:
            raise ConfigEntryError("Authentication failed") from err

        except SimpleFinPaymentRequiredError as err:
            raise UpdateFailed(
                "There is a billing issue with your SimpleFin"
                " account, contact SimpleFin to address"
                " this issue"
            ) from err

    def _clear_repair_issues(self) -> None:
        """Clear any existing simplefin repair issues from Home Assistant."""
        try:
            issue_reg = ir.async_get(self.hass)
            issues_to_delete = [
                issue_id
                for (domain, issue_id) in issue_reg.issues
                if domain == "simplefin"
            ]
            for issue_id in issues_to_delete:
                ir.async_delete_issue(self.hass, "simplefin", issue_id)
        except Exception as err:
            LOGGER.debug("Could not clear repair issues: %s", err)

    def _apply_errors_to_accounts(self, data: FinancialData) -> None:
        """Update possible_error flag and error details on all relevant accounts."""
        errors = getattr(data, "errors", []) or []

        for account in data.accounts:
            org_name = (getattr(account.org, "name", "") or "").strip().lower()
            org_domain = (getattr(account.org, "domain", "") or "").strip().lower()
            acc_name = (getattr(account, "name", "") or "").strip().lower()

            matched_errors: list[str] = []

            for error in errors:
                error_clean = error.strip()
                error_lower = error_clean.lower()

                inst_name = self._extract_institution_from_error(error_clean)
                inst_lower = inst_name.lower() if inst_name else ""

                is_match = False
                if inst_lower and (inst_lower in org_name or org_name in inst_lower):
                    is_match = True
                elif org_name and (org_name in error_lower or error_lower in org_name):
                    is_match = True
                elif org_domain and len(org_domain) > 3 and org_domain in error_lower:
                    is_match = True
                elif acc_name and acc_name in error_lower:
                    is_match = True

                if is_match:
                    matched_errors.append(error_clean)
                    LOGGER.warning(
                        "Setting possible_error=True on account '%s' (%s): %s",
                        getattr(account, "name", "Account"),
                        getattr(account.org, "name", "Institution"),
                        error_clean,
                    )

            if self._is_account_stale(account):
                stale_msg = f"Account has not updated in over 48 hours (last balance date: {account.balance_date})"
                matched_errors.append(stale_msg)
                LOGGER.warning(
                    "Setting possible_error=True on stale account '%s' (%s)",
                    getattr(account, "name", "Account"),
                    getattr(account.org, "name", "Institution"),
                )

            if matched_errors:
                account.possible_error = True
                account.error_message = "; ".join(matched_errors)

    def _extract_institution_from_error(self, error: str) -> str | None:
        """Extract institution name from error messages like 'Connection to PNC Bank may need attention. Auth required'."""
        if "Connection to " in error:
            parts = error.split("Connection to ", 1)
            if len(parts) > 1:
                after = parts[1]
                for delimiter in [
                    " may need attention",
                    " requires attention",
                    " requires",
                    " has an issue",
                    " failed",
                    ":",
                    ".",
                ]:
                    if delimiter in after:
                        after = after.split(delimiter, 1)[0]
                institution_name = after.strip()
                if institution_name:
                    return institution_name
        return None

    def _is_account_stale(self, account: Account) -> bool:
        """Check if an account has not been updated within a reasonable time."""
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
