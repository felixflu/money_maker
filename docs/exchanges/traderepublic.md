# Trade Republic Integration

This document describes the Trade Republic exchange integration for Money Maker.

## Overview

Trade Republic is a German neobroker that offers commission-free trading of ETFs, stocks, and cryptocurrencies. This integration allows you to sync your Trade Republic portfolio holdings and transaction history into Money Maker.

## Supported Features

| Feature | Status | Description |
|---------|--------|-------------|
| Portfolio Sync | ✅ | Sync ETF and cryptocurrency holdings |
| Transaction Import | ✅ | Import buy/sell transactions |
| Real-time Prices | ✅ | Fetch current market prices |
| Rate Limit Handling | ✅ | Automatic retry with backoff |
| Error Handling | ✅ | Comprehensive error messages |

## API Key Setup

### Obtaining API Credentials

**Note:** Trade Republic does not currently offer a public API. The integration uses the internal API endpoints that the Trade Republic mobile app uses.

To use this integration, you need to obtain your API credentials through one of these methods:

1. **Trade Republic API Access** (if available):
   - Contact Trade Republic support to request API access
   - They will provide you with an API key and secret

2. **Third-party tools** (unofficial):
   - Use tools like `pytr` to extract your credentials
   - **Warning:** This method is not officially supported by Trade Republic

### Configuration

1. Go to **Settings > Exchange Connections** in Money Maker
2. Click **Add Connection**
3. Select **Trade Republic** from the list
4. Enter your API key and secret
5. Click **Validate** to test the connection
6. Save the connection

## Sync Behavior

### Holdings Sync

When you sync your Trade Republic connection, the following data is imported:

- **ETFs**: ISIN, name, quantity, current price, total value
- **Cryptocurrencies**: Symbol, name, quantity, current price, total value

The sync process:
1. Authenticates with Trade Republic API
2. Fetches your current portfolio holdings
3. Normalizes the data to Money Maker's format
4. Stores the holdings in your portfolio

### Transaction Import

Transaction sync imports your historical trades:

- **Transaction types**: Buy, sell, dividend
- **Data imported**: Symbol, type, quantity, price, fees, timestamp
- **Default range**: Last 90 days (configurable: 1-365 days)

The sync process:
1. Fetches transactions within the specified date range
2. Normalizes transaction data
3. Stores transactions linked to your assets

## Rate Limits

Trade Republic implements rate limiting to prevent abuse:

| Endpoint | Limit | Window |
|----------|-------|--------|
| Authentication | 10 | per minute |
| Portfolio/Holdings | 30 | per minute |
| Transactions | 30 | per minute |

When rate limits are hit, the integration will:
1. Raise a `TradeRepublicRateLimitError`
2. Include the `Retry-After` header value
3. Fail gracefully with a user-friendly message

**Best practices:**
- Don't sync more frequently than every 5 minutes
- Use the `last_synced_at` timestamp to avoid unnecessary syncs
- Implement exponential backoff in your sync scheduling

## Error Handling

The integration handles various error scenarios:

### Authentication Errors (`TradeRepublicAuthError`)

- Invalid API key or secret
- Expired tokens
- Insufficient permissions

**Resolution:** Verify your API credentials and regenerate if necessary.

### Rate Limit Errors (`TradeRepublicRateLimitError`)

- Too many requests
- Includes `retry_after` seconds to wait

**Resolution:** Wait for the specified time before retrying.

### API Errors (`TradeRepublicAPIError`)

- Network issues
- Server errors (5xx)
- Invalid responses

**Resolution:** Retry the request or check Trade Republic's service status.

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
  "exchange_name": "trade_republic",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "is_active": true
}
```

Creates a new Trade Republic connection.

### Validate Credentials
```
POST /api/v1/exchanges/validate
Content-Type: application/json

{
  "exchange_name": "trade_republic",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret"
}
```

Validates API credentials without creating a connection.

### Sync Data
```
POST /api/v1/exchanges/trade-republic/sync/{connection_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "sync_transactions": true,
  "transaction_days": 90
}
```

Syncs portfolio data and transactions from Trade Republic.

## Known Limitations

1. **No Real-time WebSocket**: The integration uses polling, not real-time updates
2. **API Unofficial**: Trade Republic doesn't have an official public API
3. **Limited Historical Data**: Some historical data may not be available
4. **Crypto Withdrawals**: Crypto withdrawal transactions may not be tracked
5. **Fractional Shares**: Some fractional share data may be rounded

## Troubleshooting

### Connection Fails Validation

1. Verify API key and secret are correct
2. Check that your Trade Republic account is active
3. Ensure you have trading permissions enabled
4. Check the error message for specific issues

### Sync Returns Empty Data

1. Verify you have holdings in your Trade Republic account
2. Check that the connection is active
3. Review the sync logs for errors
4. Try syncing with a different date range

### Rate Limit Errors

1. Reduce sync frequency
2. Wait for the retry-after period
3. Check if other integrations are also using the API
4. Contact Trade Republic if limits are too restrictive

## Testing

The integration includes comprehensive tests in `backend/tests/test_trade_republic.py`:

```bash
# Run Trade Republic tests
cd backend
pytest tests/test_trade_republic.py -v
```

Tests cover:
- Authentication (success/failure)
- Portfolio sync
- Transaction import
- Rate limiting
- Error handling
- Data normalization

## Security Considerations

1. **API Credentials**: Stored encrypted in the database
2. **HTTPS Only**: All API calls use HTTPS
3. **Token Expiry**: Access tokens are short-lived
4. **No Credential Logging**: API keys are never logged
5. **User Isolation**: Users can only access their own connections

## Support

For issues with the Trade Republic integration:

1. Check the troubleshooting section above
2. Review the application logs for error details
3. File an issue in the Money Maker repository
4. Contact Trade Republic support for API-related issues

## Future Enhancements

Planned improvements for the Trade Republic integration:

- [ ] Webhook support for real-time updates
- [ ] Support for more asset types (bonds, options)
- [ ] Automatic dividend tracking
- [ ] Tax document integration
- [ ] Multi-currency support
