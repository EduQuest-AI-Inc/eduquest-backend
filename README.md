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

## 📈 Sequence Diagram

Below is a visual representation of the system's flow:

![Sequence Diagram](EduQuestBackendDiagram.png)

[🖊️ Edit this diagram on SequenceDiagram.org](https://sequencediagram.org/index.html#initialData=IYYwLg9gTgBAwgGwJYFMB2YBQAHYUxIhK4YwDKKUAbpTngUSWDABLBoAmCtu+hx7ZhWqEUdPo0EwAIsDDAAgiBAoAzqswc5wAEbBVKGBx2ZM6MFACeq3ETQBzGAAYAdAE5M9qBACu2GADEaMBUljAASij2SKoWckgQaIEA7gAWSGBiiKikALQAfOSUNFAAXDAA2gAKAPJkACoAujAA9MA+YKktqkj2aH4AOmgA3kMARD4GUMEAtihj5WMwYwA047jqydAcC8vLa2hj3ty7Y7E+HOZL0MuZoKmUq+MAZkhQsQD6s-OL++MI+jAX2Ac1Of0OKBmwCQCDBYyGAF9MMISjACqx2FxKOVRodJpRvnCDmMNqotlAdr8nodjj9ludLhhrrAxncQA8oNSxq93kDCVTiQDPvy9lzIdDYVTEZg2JxuLB0SjROUoFEYpkoB98VAABSRaKxSiRACOPjUYAAlMjiqI0YVZPIlCp1OV7CggQzzDrtd8LTAhjBA4HoEM3UC2RzvVNfZgHYplGpVHajDpSgAxJCcGAAVSmcZgOjCPpBYkwOlVwAA1jmpjBkhlUjBi3MYMAEBWOGEUAAPdUaONOxNoxU2lTlXOUOPWkQqYeFFHYmAKdsoYCd+pV9AAUW7KmwBES09RuXR2XM5QALE43ENhmM5upgG7ThPpiXWyu113e7FVGMkegHCmAOCbqHORQzig5T9AgCBHra6Igc6qilGuHAfJ6GA6mQYAXOYFoBkGMAhsEHDoRGlA6vUq7spQVpIUO6LGKUChkTWk7aPBs4noUspYmUERqoaUCRKoPgIFgfHyuBC4CcMADkD6qE+KDyeU8mvjAqoGhqKAcDAYmgaozziQgljyUisngWeGDlAATE4ACMt6KYmKlqTAGm1tp6qUHpBk+EZJmweZAGcKYpheL4-gBNA7BujAAAyEDREkARpBkWTIOYyayeU1R1E0rTtJ0LQIClma3uMzZ0ksXKkuSlKisStKnJhYDMrcNEcvCaCWcUlDJlJi64hM0YlkS6z6GS2yTTSEAnIs7Wday3WPNKw0KvOo5Qa2HQPBghByCgWpTDqyWpSaZqxFaSrcfa2iDi6MBhhhuGMmAUYEiWfqEUGJGvRRuo1fRj1GcmzEZlmr75oWTbjXMpjlqu1YAJJoFQbZIPpcCqh9SBtv2YPITJO3QaZXGGDxEElOU6OY8gON4+YBMIBoVnUzZYCXk5t73m5z6LK+3wfh2359v+ZjhbGxOMSOkHjnmnF3VThTMUubEUOoCRoFOKvgZt5QXZmoniZJmLSdTeUwApkCVugHmgMhHx2+g-XUINnPZbZMAOU4Lmu2gjtGS7ED231UtAZ43h+IEXgoOgSUpb4zDpekmSYFzuUDQJFTSFuiVbvUW7NN0iY60MJWpPUYfoJHkUxzFeMwOjGQE5k8CJCUykHkkzw3MAMBVJQCT6WnmWZ97zDy7TlQAOJF6XIBCqoLSV-tNfh-X0fRYE2A+FA2DcDmnAoK8aD+ePGdZzPi4FQ0pf2CW6+dJv6C3k-cwAHIlmFUdRbHAIlgUCwQgMkE+lxz6Xx0ACEAlZJ45GnttD2ucqjZiKi0T+KAX7V1rmgW8R9gDAKgHABa0AVgvRLKjaQf8G67wCF4IhECz6Zkvhla+U9s4oPyvnQuxdS7GHrkAA)
