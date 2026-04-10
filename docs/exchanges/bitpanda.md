# Bitpanda Integration

This document describes the Bitpanda exchange integration for Money Maker.

## Overview

Bitpanda is a European cryptocurrency broker that allows users to buy, sell, and store cryptocurrencies, crypto indices, and precious metals. This integration enables you to sync your Bitpanda cryptocurrency holdings and trade history into Money Maker.

## Supported Features

| Feature | Status | Description |
|---------|--------|-------------|
| Portfolio Sync | ✅ | Sync cryptocurrency wallet balances |
| Transaction Import | ✅ | Import buy/sell trades |
| Fiat Wallets | ✅ | View fiat currency balances |
| Rate Limit Handling | ✅ | Automatic retry with backoff |
| Error Handling | ✅ | Comprehensive error messages |

## API Key Setup

### Obtaining API Credentials

1. **Log in to your Bitpanda account** at https://www.bitpanda.com
2. **Go to Settings** → API Keys
3. **Create a new API key** with the following permissions:
   - **Read** (required for portfolio sync and trade history)
   - Do NOT enable withdrawal permissions (not needed and less secure)
4. **Copy the API key** immediately - it will not be shown again
5. **Store it securely** - Money Maker will encrypt it in the database

**Security Notes:**
- Bitpanda uses API key-only authentication (no secret required)
- API keys are stored encrypted in the database
- Only create keys with read permissions for maximum security
- Never share your API key with anyone

### Configuration

1. Go to **Settings > Exchange Connections** in Money Maker
2. Click **Add Connection**
3. Select **Bitpanda** from the list
4. Enter your **API key** (API secret field can be left empty)
5. Click **Validate** to test the connection
6. Save the connection

## Sync Behavior

### Holdings Sync

When you sync your Bitpanda connection, the following data is imported:

- **Cryptocurrencies**: Symbol (e.g., BTC, ETH), name, balance, available balance
- **Wallet IDs**: Internal Bitpanda wallet identifiers
- **Fiat Wallets**: EUR and other fiat currency balances (if fiat wallet sync is enabled)

The sync process:
1. Authenticates with Bitpanda API using your API key
2. Fetches your cryptocurrency wallet balances
3. Fetches fiat wallet balances (optional)
4. Normalizes the data to Money Maker's format
5. Stores the holdings in your portfolio

### Transaction Import

Trade sync imports your historical cryptocurrency trades:

- **Transaction types**: Buy, sell
- **Data imported**: Symbol, type, quantity, price, fees, timestamp
- **Default range**: Last 90 days (configurable: 1-365 days)

The sync process:
1. Fetches trades within the specified date range
2. Normalizes trade data to standard format
3. Stores transactions linked to your assets

## Rate Limits

Bitpanda implements rate limiting to prevent API abuse:

| Endpoint | Limit | Window |
|----------|-------|--------|
| Account Info | 100 | per minute |
| Wallets | 100 | per minute |
| Trades | 100 | per minute |
| Fiat Wallets | 100 | per minute |

When rate limits are hit, the integration will:
1. Raise a `BitpandaRateLimitError`
2. Include the `Retry-After` header value if provided
3. Fail gracefully with a user-friendly message

**Best practices:**
- Don't sync more frequently than every 5 minutes
- Use the `last_synced_at` timestamp to avoid unnecessary syncs
- Implement exponential backoff in your sync scheduling

## Error Handling

The integration handles various error scenarios:

### Authentication Errors (`BitpandaAuthError`)

- Invalid API key
- Revoked API key
- Insufficient permissions

**Resolution:** Verify your API key is correct and has not been revoked. Generate a new key if necessary.

### Rate Limit Errors (`BitpandaRateLimitError`)

- Too many requests
- Includes `retry_after` seconds to wait

**Resolution:** Wait for the specified time before retrying.

### API Errors (`BitpandaAPIError`)

- Network issues
- Server errors (5xx)
- Invalid responses

**Resolution:** Retry the request or check Bitpanda's service status.

## API Endpoints

The integration exposes the following REST API endpoints:

### List Supported Exchanges
```
GET /api/v1/exchanges/supported
```

Returns a list of all supported exchanges and their capabilities.

### List Connections
```
GET /api/v1/exchanges/connections
Authorization: Bearer <token>
```

Returns all exchange connections for the authenticated user.

### Create Connection
```
POST /api/v1/exchanges/connections
Authorization: Bearer <token>
Content-Type: application/json

{
  "exchange_name": "bitpanda",
  "api_key": "your_api_key",
  "api_secret": "",
  "is_active": true
}
```

Creates a new Bitpanda connection. The `api_secret` field is not required for Bitpanda.

### Validate Credentials
```
POST /api/v1/exchanges/validate
Content-Type: application/json

{
  "exchange_name": "bitpanda",
  "api_key": "your_api_key",
  "api_secret": ""
}
```

Validates API credentials without creating a connection.

### Sync Data
```
POST /api/v1/exchanges/bitpanda/sync/{connection_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "sync_transactions": true,
  "transaction_days": 90
}
```

Syncs portfolio data and trades from Bitpanda.

## Known Limitations

1. **Price Data**: Current prices are not fetched directly - they would require separate API calls to price endpoints
2. **Crypto Indices**: Index products may not be fully supported yet
3. **Metals**: Precious metals holdings are not currently imported (only cryptocurrencies)
4. **Savings Plans**: Automatic savings plan transactions are imported as regular trades
5. **Withdrawals/Deposits**: External transfers may not be tracked in trade history

## Troubleshooting

### Connection Fails Validation

1. Verify API key is correct (no extra spaces)
2. Check that your Bitpanda account is active
3. Ensure the API key has read permissions
4. Check the error message for specific issues

### Sync Returns Empty Data

1. Verify you have cryptocurrency holdings in your Bitpanda account
2. Check that the connection is active
3. Review the sync logs for errors
4. Try syncing with a different date range

### Rate Limit Errors

1. Reduce sync frequency
2. Wait for the retry-after period
3. Check if other integrations are also using the API
4. Contact Bitpanda if limits are too restrictive

### API Key Issues

**Error: "Authentication failed: Invalid API key"**
- The API key may have been revoked
- Generate a new API key in Bitpanda settings
- Ensure you're using the full key (they are long strings)

## Testing

The integration includes comprehensive tests in `backend/tests/test_bitpanda.py`:

```bash
# Run Bitpanda tests
cd backend
pytest tests/test_bitpanda.py -v
```

Tests cover:
- Authentication (success/failure)
- Portfolio sync
- Trade import
- Rate limiting
- Error handling
- Data normalization

## Security Considerations

1. **API Credentials**: Stored encrypted in the database
2. **HTTPS Only**: All API calls use HTTPS
3. **Read-Only Keys**: Integration only requires read permissions
4. **No Credential Logging**: API keys are never logged
5. **User Isolation**: Users can only access their own connections
6. **API Key Rotation**: Recommended to rotate keys every 90 days

## Support

For issues with the Bitpanda integration:

1. Check the troubleshooting section above
2. Review the application logs for error details
3. File an issue in the Money Maker repository
4. Contact Bitpanda support for API-related issues: https://www.bitpanda.com/en/contact

## Future Enhancements

Planned improvements for the Bitpanda integration:

- [ ] Support for crypto indices
- [ ] Precious metals holdings sync
- [ ] Savings plan tracking
- [ ] Deposit/withdrawal history
- [ ] Real-time price updates via polling
- [ ] Multi-currency support beyond EUR
- [ ] Webhook support for trade notifications (if Bitpanda adds webhooks)
