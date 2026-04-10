# MEXC Integration

This document describes the MEXC exchange integration for MoneyMaker.

## Overview

MEXC is a global cryptocurrency exchange offering spot and futures trading. This integration allows you to sync your MEXC cryptocurrency holdings and transaction history into MoneyMaker.

## Supported Features

- **Portfolio Sync**: Import your current cryptocurrency balances
- **Transaction Import**: Import your trade history (last 90 days by default)
- **Spot Trading Support**: Tracks spot market trades
- **Real-time Prices**: Fetches current prices for holdings

## API Key Setup

To connect your MEXC account, you need to create an API key:

1. **Log in to MEXC**: Go to [https://www.mexc.com](https://www.mexc.com) and sign in
2. **Access API Management**:
   - Click on your profile icon → **API Management**
   - Or go directly to: [https://www.mexc.com/user/openapi](https://www.mexc.com/user/openapi)
3. **Create a new API key**:
   - Click **"Create API"**
   - Give your API key a name (e.g., "MoneyMaker")
   - Set appropriate permissions:
     - ✅ **Read-only access** (recommended)
     - ❌ Disable trading permissions (not needed)
     - ❌ Disable withdrawal permissions (not needed)
4. **Configure IP Restrictions** (recommended):
   - Add your server's IP address to the whitelist
   - This adds an extra layer of security
5. **Save your credentials**:
   - Copy the **API Key** (starts with `mx`)
   - Copy the **Secret Key** (shown only once!)
   - Store them securely - the secret key cannot be retrieved later

## Adding Your MEXC Connection

Once you have your API credentials:

1. Go to **Settings → Exchange Connections**
2. Click **"Add Connection"**
3. Select **MEXC** from the dropdown
4. Enter your **API Key** and **API Secret**
5. Click **"Validate & Save"**

MoneyMaker will validate your credentials before saving.

## Sync Behavior

### Holdings Sync

- Fetches all non-zero balance assets
- Updates available and locked quantities
- Fetches current market prices for valuation

### Transaction Import

- Imports trades from the last 90 days by default
- Supports pagination for large trade histories
- Handles both buy and sell transactions
- Tracks fees in the fee asset currency

### Rate Limiting

MEXC enforces rate limits on API requests:

- **Weight-based limiting**: Each endpoint has a "weight" cost
- **Default limit**: 6000 weight per minute per IP
- **Retry behavior**: If rate limited, sync will fail with retry-after information
- **Best practice**: Avoid manual syncs more than once per hour

## Data Mapping

| MEXC Field | MoneyMaker Field | Notes |
|------------|------------------|-------|
| `asset` | `symbol` | e.g., "BTC" |
| `free` | `available` | Available balance |
| `locked` | `locked` | In orders or pending |
| `symbol` (trade) | `full_symbol` | e.g., "BTCUSDT" |
| `side` | `transaction_type` | "BUY" or "SELL" |
| `price` | `price` | Execution price |
| `qty` | `quantity` | Amount traded |
| `commission` | `fees` | Trading fee |
| `commissionAsset` | `fee_asset` | Asset used for fee |
| `time` (ms) | `timestamp` | Converted to datetime |

## Security Considerations

1. **Read-only API keys**: Always create read-only API keys for MoneyMaker
2. **IP whitelisting**: Restrict API access to your server's IP address
3. **No withdrawal permissions**: Ensure withdrawal permissions are disabled
4. **Secure storage**: API secrets are encrypted at rest in MoneyMaker

## Troubleshooting

### "Invalid API key" Error

- Verify the API key is copied correctly
- Check that the API key hasn't been deleted or expired
- Ensure you're using the correct environment (spot API)

### "IP not allowed" Error

- Check your IP whitelist settings in MEXC
- Your server's IP may have changed
- Remove IP restrictions temporarily to test

### "Rate limit exceeded" Error

- Wait 60 seconds before retrying
- Reduce sync frequency
- Check for other applications using the same API key

### Missing Transactions

- MEXC only returns trades from the last 90 days via API
- Large trade histories may require multiple syncs
- Ensure correct date range is selected

### Connection Valid but No Data

- Verify you have balances on MEXC
- Check if API key has correct permissions
- Some sub-accounts may require special configuration

## Known Limitations

1. **Historical data**: MEXC API only provides ~90 days of trade history
2. **Futures trading**: Not currently supported (spot trading only)
3. **Margin trading**: Not currently supported
4. **Deposit/Withdrawal history**: Not available via current API endpoints
5. **Sub-accounts**: Only main account data is synced

## API Documentation

For more details on the MEXC API:

- [MEXC API Documentation](https://mexcdevelop.github.io/apidocs/spot_v3_en/)
- [Spot Trading API](https://mexcdevelop.github.io/apidocs/spot_v3_en/#spot-account-information)
- [Rate Limits](https://mexcdevelop.github.io/apidocs/spot_v3_en/#limits)

## Support

If you encounter issues with the MEXC integration:

1. Check the troubleshooting section above
2. Verify your API key permissions
3. Review MEXC API status at [MEXC Status](https://www.mexc.com/support/status)
4. Open an issue with details about the error message
