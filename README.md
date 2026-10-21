# SimpleFin Integration for Home Assistant

A custom component for [Home Assistant](https://www.home-assistant.io/) providing enhanced financial account tracking via the [SimpleFIN Bridge](https://www.simplefin.org/) service.

## Improvements & Fixes in this Fork

1. **Enhanced Institution Name Matching**: Bidirectional comparison and error-message parsing for institution names (e.g. "Connection to [Institution] may need attention").
2. **Persistent Error Reporting**: Integrates with Home Assistant's Repair Issue Registry to surface sync errors directly in the Repairs dashboard.
3. **Stale Account Detection**: Automatically warns when account data has not updated within a 48-hour threshold.
4. **HACS Compatible**: Fully structured with `custom_components/simplefin/` and `hacs.json` for installation and updates through HACS.

## Installation via HACS

1. In Home Assistant, open **HACS** > **Integrations**.
2. Click the three dots (⋮) in the top right corner and select **Custom repositories**.
3. Add repository URL:
   ```text
   https://github.com/hfbauman/ha-simplefin
   ```
4. Set Type to **Integration** and click **Add**.
5. Find **SimpleFIN** in HACS, click **Download**, and restart Home Assistant.

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **SimpleFIN**.
3. Enter your SimpleFIN **Claim Token** or **Access URL**.
