# MEXC Exchange Integration

This document describes the MEXC exchange integration for Money Maker, including API key setup, supported features, sync behavior, and known limitations.

## Overview

The MEXC integration allows you to automatically sync your cryptocurrency holdings and trade history from the MEXC exchange into your Money Maker portfolio.

## API Key Setup

### Creating MEXC API Keys

1. Log in to your [MEXC](https://www.mexc.com) account
2. Navigate to **Account** → **API Management**
3. Click **Create API Key**
4. Give your API key a name (e.g., "Money Maker")
5. Enable the following permissions:
   - **Read Info** - Required for reading account balances and trade history
   - **Spot Trading** - Required if you want to sync trade history
6. Complete any security verification (2FA, email confirmation)
7. Copy the **API Key** and **Secret Key** - **Important**: The secret key will only be shown once!

### Security Recommendations

- **IP Whitelisting**: If possible, whitelist the IP address(es) of your Money Maker instance
- **Limited Permissions**: Only enable permissions you actually need (read-only is sufficient for syncing)
- **API Key Rotation**: Regularly rotate your API keys (recommended every 90 days)
- **Never share** your API keys or commit them to version control

### Connecting to Money Maker

Once you have your API credentials:

1. Go to **Settings** → **Exchange Connections**
2. Click **Add Connection** → **MEXC**
3. Enter your API Key and Secret Key
4. Click **Test Connection** to verify credentials
5. If successful, click **Save Connection**

Or via API:

```bash
curl -X POST http://localhost/api/v1/exchanges/mexc/connect \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "is_active": true
  }'
```

## Supported Features

### Holdings Sync

- **Real-time Balance**: Fetch current spot wallet balances
- **Free vs Locked**: Distinguishes between available (free) and locked (in orders) balances
- **Asset Discovery**: Automatically creates assets in your MEXC portfolio
- **Zero-balance Filtering**: Excludes assets with zero balance

### Transaction History

- **Trade Import**: Imports all spot trading history
- **Buy/Sell Detection**: Automatically categorizes trades as buy or sell
- **Fee Tracking**: Records trading fees in the quote asset
- **Timestamp Preservation**: Maintains original trade timestamps

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/exchanges/mexc/connect` | POST | Create new MEXC connection |
| `/api/v1/exchanges/mexc/test-connection` | POST | Test API credentials |
| `/api/v1/exchanges/mexc/connection` | GET | Get connection details |
| `/api/v1/exchanges/mexc/connection` | PUT | Update connection |
| `/api/v1/exchanges/mexc/connection` | DELETE | Remove connection |
| `/api/v1/exchanges/mexc/sync` | POST | Sync holdings and transactions |
| `/api/v1/exchanges/mexc/holdings` | GET | Get real-time holdings |

## Sync Behavior

### Automatic Sync

- Connections are checked periodically (if enabled)
- Sync is triggered automatically when you connect for the first time
- Subsequent syncs require manual trigger or scheduled job

### Manual Sync

```bash
# Sync holdings only
curl -X POST http://localhost/api/v1/exchanges/mexc/sync \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "sync_transactions": false
  }'

# Sync holdings and all transactions
curl -X POST http://localhost/api/v1/exchanges/mexc/sync \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "sync_transactions": true
  }'

# Sync with date range
curl -X POST http://localhost/api/v1/exchanges/mexc/sync \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "sync_transactions": true,
    "transaction_start_date": "2024-01-01T00:00:00Z"
  }'
```

### Data Mapping

| MEXC Field | Money Maker Field | Notes |
|------------|-------------------|-------|
| `asset` | `Asset.symbol` | Uppercase symbol |
| `free` | Calculated | Available balance |
| `locked` | Calculated | Balance in orders |
| `free + locked` | `Asset.quantity` | Total balance |
| `symbol` | Transaction notes | Trading pair |
| `isBuyer` | `Transaction.transaction_type` | "buy" or "sell" |
| `price` | `Transaction.price` | Trade price |
| `qty` | `Transaction.quantity` | Trade quantity |
| `commission` | `Transaction.fees` | Trading fee |
| `time` | `Transaction.timestamp` | Unix timestamp (ms) |

### Duplicate Prevention

- Holdings are always updated to current values (no duplicates possible)
- Transactions are matched by trade ID stored in notes field
- Re-syncing the same period will not create duplicate transactions

## Rate Limits

MEXC API has the following rate limits:

- **General endpoints**: 1200 requests per minute per IP
- **Order-related endpoints**: 100 requests per 10 seconds per user

The integration implements:

- **Request throttling**: 100ms minimum between requests
- **Automatic retry**: Exponential backoff on rate limit errors
- **Max retries**: 3 retries before failing

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid API credentials` | Wrong API key or secret | Verify credentials in MEXC dashboard |
| `Failed to connect to MEXC` | Network or API issue | Check internet connection, try again |
| `Rate limit exceeded` | Too many requests | Wait and retry, reduce sync frequency |
| `Sync failed: API error` | MEXC API returned error | Check MEXC API status page |

### Troubleshooting

1. **Verify API Key Permissions**: Ensure "Read Info" permission is enabled
2. **Check IP Restrictions**: If using IP whitelist, ensure your server IP is allowed
3. **Test Credentials**: Use the test-connection endpoint before saving
4. **Check Logs**: Application logs contain detailed error information

## Known Limitations

### Current Limitations

1. **Spot Trading Only**: Margin, futures, and savings products are not supported
2. **No Withdrawal/Deposit History**: Only trade history is imported
3. **No Real-time Updates**: Manual sync or scheduled job required for updates
4. **Symbol Parsing**: Complex trading pairs may not be parsed correctly (see below)

### Symbol Parsing

The integration attempts to extract the base asset from MEXC trading pairs:

- `BTCUSDT` → `BTC`
- `ETHUSDC` → `ETH`
- `ADABTC` → `ADA`

Known quote assets: `USDT`, `USDC`, `BTC`, `ETH`

If you trade pairs with other quote assets, the base asset detection may be incorrect. In these cases, the full symbol will be used as the asset symbol.

## Security Notes

### Credential Storage

- API keys are encrypted before storage (implementation-specific)
- Keys are never logged or exposed in API responses
- Keys are only decrypted during active sync operations

### Best Practices

1. **Use read-only API keys** when possible
2. **Enable 2FA** on your MEXC account
3. **Monitor API usage** in MEXC dashboard
4. **Revoke unused keys** regularly
5. **Never share** API keys in support tickets or public forums

## API Reference

### MEXC API Documentation

- [MEXC API Documentation](https://mexcdevelop.github.io/apidocs/spot_v3_en/)
- Endpoints used:
  - `GET /api/v3/account` - Account information and balances
  - `GET /api/v3/myTrades` - Trade history

### Authentication

The integration uses HMAC-SHA256 signature authentication:

1. Timestamp and recvWindow are added to request parameters
2. Query string is constructed and signed with API secret
3. Signature is included in request

Example signature generation (Python):

```python
import hmac
import hashlib
import time

api_secret = "your_api_secret"
query_string = f"timestamp={int(time.time() * 1000)}&recvWindow=5000"

signature = hmac.new(
    api_secret.encode('utf-8'),
    query_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

## Support

For issues or questions regarding the MEXC integration:

1. Check this documentation first
2. Review application logs for error details
3. Verify MEXC API status: https://status.mexc.com
4. Contact support with your account ID and error details

## Changelog

### Version 1.0.0

- Initial MEXC integration
- Holdings sync support
- Transaction history import
- Rate limiting and retry logic
- Error handling for common API errors
