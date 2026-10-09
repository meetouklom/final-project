# DormFix ER Diagram

This diagram is based on the Django models in `accounts/models.py` and
`repairs/models.py`. It shows the application's main entities and relationships;
Django's built-in authentication tables and fields are omitted for clarity.

If the Mermaid preview appears blank, open the [standalone SVG diagram](./DORMFIX_ER_DIAGRAM.svg).

```mermaid
erDiagram
    USER {
        int id PK
        string username
        string email
        string password
        string role
        string room_number
    }

    REPAIR_REQUEST {
        int id PK
        int reported_by_id FK
        int assigned_to_id FK
        string title
        string description
        string category
        string location
        string status
        int rating
        string image
        string supervisor_note
        string ai_summary
        string ai_suggested_category
        string ai_urgency
        datetime ai_analyzed_at
        datetime created_at
        datetime updated_at
    }

    REPAIR_COMMENT {
        int id PK
        int repair_id FK
        int author_id FK
        string body
        datetime created_at
    }

    NOTIFICATION {
        int id PK
        int user_id FK
        int reference_id FK
        string title
        string message
        string type
        boolean is_read
        datetime created_at
    }

    ACCOUNT_AUDIT_LOG {
        int id PK
        int actor_id FK
        int target_id FK
        string actor_username
        string target_username
        string action
        string old_value
        string new_value
        datetime created_at
    }

    USER ||--o{ REPAIR_REQUEST : reports
    USER o|--o{ REPAIR_REQUEST : assigned_to
    USER ||--o{ REPAIR_COMMENT : writes
    REPAIR_REQUEST ||--o{ REPAIR_COMMENT : has
    USER ||--o{ NOTIFICATION : receives
    REPAIR_REQUEST o|--o{ NOTIFICATION : references
    USER o|--o{ ACCOUNT_AUDIT_LOG : performs
    USER o|--o{ ACCOUNT_AUDIT_LOG : is_target_of
```

`assigned_to_id`, `reference_id`, `actor_id`, and `target_id` may be empty.
Passwords are stored as hashes by Django, not as plain text.
