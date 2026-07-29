---
inclusion: always
---

# API Standards

## RESTful API Conventions

### URL Structure

- Use kebab-case for URLs: `/api/v1/project-tasks`
- Resource-based URLs: `/api/v1/projects/{id}/documents`
- Version in URL path: `/api/v1/`
- No trailing slashes

### HTTP Methods

- `GET`: Retrieve resources (idempotent)
- `POST`: Create new resources
- `PUT`: Update entire resource (idempotent)
- `PATCH`: Partial resource updates
- `DELETE`: Remove resources (idempotent)

### Response Format

```json
{
  "success": true,
  "data": {},
  "message": "Operation completed successfully",
  "timestamp": "2025-01-08T10:30:00Z"
}
```

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "repositoryUrl",
        "message": "Must be a valid Git URL"
      }
    ]
  },
  "timestamp": "2025-01-08T10:30:00Z"
}
```

### HTTP Status Codes

- `200`: Success (GET, PUT, PATCH)
- `201`: Created (POST)
- `204`: No Content (DELETE)
- `400`: Bad Request (validation errors)
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `409`: Conflict (duplicate resources)
- `422`: Unprocessable Entity (business logic errors)
- `500`: Internal Server Error

### Pagination

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "size": 20,
    "total": 100,
    "totalPages": 5
  }
}
```

### Authentication

- No authentication required for MVP
- Future: JWT tokens in Authorization header
- Format: `Authorization: Bearer <token>`
