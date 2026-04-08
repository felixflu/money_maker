# Authentication API

This document describes the authentication endpoints for the Money Maker API.

## Overview

The API uses JWT (JSON Web Tokens) for authentication. There are two types of tokens:

- **Access Token**: Short-lived token (30 minutes) used to authenticate API requests
- **Refresh Token**: Long-lived token (7 days) used to obtain new access tokens

## Endpoints

### POST /api/v1/auth/register

Register a new user account.

#### Request

```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Constraints:**
- `email`: Must be a valid email address, unique in the system
- `password`: Minimum 8 characters

#### Response (201 Created)

```json
{
  "id": 1,
  "email": "user@example.com",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00"
}
```

#### Error Responses

- **400 Bad Request**: Email already registered
- **422 Validation Error**: Invalid email format or password too short

---

### POST /api/v1/auth/login

Authenticate a user and receive access and refresh tokens.

#### Request

```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

#### Response (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Error Responses

- **401 Unauthorized**: Invalid email or password
- **422 Validation Error**: Missing or invalid fields

---

### POST /api/v1/auth/login/form

OAuth2-compatible login endpoint for form-based authentication. Used by Swagger UI.

#### Request

Content-Type: `application/x-www-form-urlencoded`

```
username=user@example.com&password=securepassword123
```

Note: OAuth2 uses `username` field for the email address.

#### Response (200 OK)

Same as `/api/v1/auth/login`.

---

### POST /api/v1/auth/refresh

Get a new access token using a valid refresh token.

#### Request

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Response (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Note: Both tokens are rotated (new refresh token issued).

#### Error Responses

- **401 Unauthorized**: Invalid or expired refresh token

---

## Authentication

To access protected endpoints, include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

## Token Lifetimes

| Token Type | Lifetime | Usage |
|------------|----------|-------|
| Access Token | 30 minutes | API request authentication |
| Refresh Token | 7 days | Obtain new access tokens |

## Security Considerations

1. **Password Storage**: Passwords are hashed using bcrypt with salt
2. **Token Storage**: Store tokens securely on the client (httpOnly cookies recommended)
3. **HTTPS**: Always use HTTPS in production to protect tokens in transit
4. **Token Refresh**: Implement token refresh before access token expires
5. **Logout**: To "logout", simply discard the tokens on the client side

## Testing

### Example: Register a new user

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123"
  }'
```

### Example: Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123"
  }'
```

### Example: Access protected endpoint

```bash
curl -X GET "http://localhost:8000/api/v1/protected" \
  -H "Authorization: Bearer <access_token>"
```
