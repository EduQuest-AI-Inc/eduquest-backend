## 📘 HTTP Status Codes Reference

This API uses standard HTTP status codes to indicate the success or failure of an API request.

| Status Code | Name                  | When to Use                                                                  |
| ----------- | --------------------- | ---------------------------------------------------------------------------- |
| `200`       | OK                    | Successful GET or PUT request                                                |
| `201`       | Created               | Resource successfully created via POST                                       |
| `204`       | No Content            | Request successful, but no content to return (e.g., DELETE)                  |
| `400`       | Bad Request           | The request is malformed or missing required parameters                      |
| `401`       | Unauthorized          | Authentication failed or missing                                             |
| `403`       | Forbidden             | Authenticated but not allowed to access the resource                         |
| `404`       | Not Found             | The requested resource does not exist                                        |
| `409`       | Conflict              | Conflict with existing data (e.g., duplicate entry)                          |
| `422`       | Unprocessable Entity  | Request is syntactically correct but semantically invalid (e.g., validation) |
| `429`       | Too Many Requests     | Rate limit exceeded                                                          |
| `500`       | Internal Server Error | A generic error occurred on the server                                       |
| `503`       | Service Unavailable   | Server is temporarily unavailable (e.g., maintenance or overload)            |
