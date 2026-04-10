# Coinbase Integration

This document describes the Coinbase exchange integration for Money Maker.

## Overview

Coinbase is a popular cryptocurrency exchange that allows users to buy, sell, and store various cryptocurrencies. This integration enables you to sync your Coinbase portfolio holdings and transaction history into Money Maker.

## Supported Features

| Feature | Status | Description |
|---------|--------|-------------|
| Portfolio Sync | ✅ | Sync cryptocurrency holdings across all wallets |
| Transaction Import | ✅ | Import buy, sell, transfer, and reward transactions |
| Real-time Prices | ✅ | Fetch current market prices |
| Rate Limit Handling | ✅ | Automatic retry with backoff |
| Error Handling | ✅ | Comprehensive error messages |
| Multi-Currency Support | ✅ | Supports all Coinbase-supported cryptocurrencies |

## API Key Setup

### Obtaining API Credentials

To use the Coinbase integration, you need to create API credentials:

1. **Log in to your Coinbase account:**
   - Go to [Coinbase](https://www.coinbase.com) and sign in

2. **Navigate to API settings:**
   - Go to **Settings > API**
   - Or visit [Coinbase API Settings](https://www.coinbase.com/settings/api)

3. **Create a new API key:**
   - Click **+ New API Key**
   - Select the accounts you want to grant access to
   - Choose the appropriate permissions:
     - `wallet:accounts:read` - View your accounts
     - `wallet:transactions:read` - View your transactions
     - `wallet:buys:read` - View your buys
     - `wallet:sells:read` - View your sells

4. **Generate and save credentials:**
   - Copy the **API Key** (starts with `organizations/` or similar)
   - Copy the **API Secret** shown only once
   - **Important:** Store the secret securely, it won't be shown again

### Configuration

1. Go to **Settings > Exchange Connections** in Money Maker
2. Click **Add Connection**
3. Select **Coinbase** from the list
4. Enter your API key and secret
5. Click **Validate** to test the connection
6. Save the connection

## Sync Behavior

### Holdings Sync

When you sync your Coinbase connection, the following data is imported:

- **Cryptocurrencies**: Currency code, name, quantity, current price, total value
- **Wallets**: Each currency wallet is tracked separately
- **Balances**: Both crypto and native currency values

The sync process:
1. Authenticates with Coinbase API
2. Fetches your account/wallet list
3. Filters accounts with non-zero balances
4. Fetches current market prices for each currency
5. Normalizes the data to Money Maker's format
6. Stores the holdings in your portfolio

### Transaction Import

Transaction sync imports your historical transactions:

- **Transaction types**:
  - `buy` - Cryptocurrency purchases
  - `sell` - Cryptocurrency sales
  - `transfer` - Outgoing transfers (send)
  - `receive` - Incoming transfers
  - `deposit` - Fiat deposits
  - `withdrawal` - Fiat withdrawals
  - `reward` - Earn payouts and staking rewards

- **Data imported**: Transaction ID, type, symbol, quantity, price, fees, timestamp, status
- **Default range**: Last 90 days (configurable: 1-365 days)

The sync process:
1. Fetches all accounts with non-zero activity
2. Retrieves transactions within the specified date range for each account
3. Enriches transactions with account currency information
4. Normalizes transaction data
5. Stores transactions linked to your assets

## Rate Limits

Coinbase implements rate limiting to prevent abuse:

| Endpoint | Limit | Window |
|----------|-------|--------|
| General API calls | 3,000 | per hour |
| Authentication | 10 | per minute |
| Price requests | 10 | per second |

When rate limits are hit, the integration will:
1. Raise a `CoinbaseRateLimitError`
2. Include the `Retry-After` header value
3. Fail gracefully with a user-friendly message

**Best practices:**
- Don't sync more frequently than every 5 minutes
- Use the `last_synced_at` timestamp to avoid unnecessary syncs
- Implement exponential backoff in your sync scheduling

## Error Handling

The integration handles various error scenarios:

### Authentication Errors (`CoinbaseAuthError`)

- Invalid API key or secret
- Expired API keys
- Insufficient permissions

**Resolution:** Verify your API credentials and regenerate if necessary. Ensure the key has the required permissions.

### Rate Limit Errors (`CoinbaseRateLimitError`)

- Too many requests
- Includes `retry_after` seconds to wait

**Resolution:** Wait for the specified time before retrying.

### API Errors (`CoinbaseAPIError`)

- Network issues
- Server errors (5xx)
- Invalid responses

**Resolution:** Retry the request or check Coinbase's service status.

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
  "exchange_name": "coinbase",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "is_active": true
}
```

Creates a new Coinbase connection.

### Validate Credentials
```
POST /api/v1/exchanges/validate
Content-Type: application/json

{
  "exchange_name": "coinbase",
  "api_key": "your_api_key",
  "api_secret": "your_api_secret"
}
```

Validates API credentials without creating a connection.

### Sync Data
```
POST /api/v1/exchanges/coinbase/sync/{connection_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "sync_transactions": true,
  "transaction_days": 90
}
```

Syncs portfolio data and transactions from Coinbase.

## Known Limitations

1. **No Real-time WebSocket**: The integration uses polling, not real-time updates
2. **Price Lookup Limitations**: Some obscure cryptocurrencies may not have price data available
3. **Historical Data**: Very old transactions may not be accessible through the API
4. **Staking Rewards**: Some staking rewards may be reported with delays
5. **Coinbase Pro/Advanced Trade**: Separate API endpoints; this integration focuses on standard Coinbase

## Troubleshooting

### Connection Fails Validation

1. Verify API key and secret are correct
2. Check that your Coinbase account is active (not suspended or closed)
3. Ensure you have the required API permissions enabled
4. Check the error message for specific issues

### Sync Returns Empty Data

1. Verify you have holdings in your Coinbase account
2. Check that the connection is active
3. Review the sync logs for errors
4. Try syncing with a different date range
5. Ensure your API key has access to the accounts with holdings

### Rate Limit Errors

1. Reduce sync frequency (wait at least 5 minutes between syncs)
2. Wait for the retry-after period
3. Check if other integrations are also using the Coinbase API
4. Consider upgrading to Coinbase Prime for higher rate limits

### Authentication Errors

1. Verify the API key format (should start with `organizations/`)
2. Check that the API secret is complete (not truncated)
3. Ensure the API key hasn't been deleted or revoked
4. Regenerate the API key if necessary

## Testing

The integration includes comprehensive tests in `backend/tests/test_coinbase.py`:

```bash
# Run Coinbase tests
cd backend
pytest tests/test_coinbase.py -v
```

Tests cover:
- Client initialization
- Authentication (success/failure)
- Account retrieval
- Holdings sync
- Transaction import (single account and all accounts)
- Rate limiting
- Error handling
- Data normalization
- Connection validation
- Context manager usage

## Security Considerations

1. **API Credentials**: Stored encrypted in the database
2. **HTTPS Only**: All API calls use HTTPS
3. **Read-only Access**: Integration only requires read permissions
4. **No Credential Logging**: API keys are never logged
5. **User Isolation**: Users can only access their own connections
6. **API Key Rotation**: Consider rotating your API key periodically

## Privacy Considerations

- The integration syncs your Coinbase portfolio data into Money Maker
- Transaction data includes amounts, prices, and timestamps
- No personal information from Coinbase is stored
- API calls are made directly from the Money Maker backend

## Support

For issues with the Coinbase integration:

1. Check the troubleshooting section above
2. Review the application logs for error details
3. Verify Coinbase API status at [Coinbase Status](https://status.coinbase.com/)
4. File an issue in the Money Maker repository
5. Contact Coinbase support for API-related issues

## Future Enhancements

Planned improvements for the Coinbase integration:

- [ ] Coinbase Pro/Advanced Trade API support
- [ ] Webhook support for real-time updates
- [ ] Recurring buy tracking
- [ ] Tax document integration
- [ ] Multi-portfolio support (for business accounts)
- [ ] Price alerts integration
