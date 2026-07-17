# Core Data Contract

This contract defines the shared MongoDB records used by all four research components. Component-specific code must preserve these public identifiers and canonical field names.

## Collections

### `users`

- `user_id`: opaque ID beginning with `U`
- `email`: normalized lowercase email, unique
- `full_name`
- `hashed_password`: Argon2 hash; plaintext passwords are never stored
- `role`: `customer`, `provider`, or `admin`
- `is_active`
- `created_at`: UTC datetime

### `providers`

- `provider_id`: opaque ID beginning with `P`, unique
- `user_id`: owning provider account, unique
- `provider_name`
- `category`
- `district`
- `city`
- `experience_years`
- `rating`: normalized range `0..5`
- `review_count`
- `booking_success_rate`: normalized range `0..1`
- `interaction_count`
- `skills`: list of normalized skill names
- `description`
- `created_at`, `updated_at`: UTC datetimes

The field names match the Component 1 provider dataset. The research dataset stores `skills` as a comma-separated string; the application API stores it as a list and the future ingestion adapter is responsible for splitting it.

### `service_requests`

- `request_id`: opaque ID beginning with `R`, unique
- `user_id`: owning customer
- `request_text`
- `category`
- `district`
- `city`
- `urgency`: `normal`, `urgent`, or `emergency`
- `created_at`: UTC datetime

These fields exactly match the Component 1 request pipeline contract.

### `customer_profiles`

- `customer_id`: opaque ID beginning with `C`, unique
- `user_id`: owning customer account, unique
- `phone`, `district`, `city`, `preferred_language`
- `created_at`, `updated_at`: UTC datetimes

A basic customer profile is created automatically with customer registration and may be
completed through the authenticated customer API.

### `interactions`

- `interaction_id`: opaque ID beginning with `I`, unique
- `request_id`, `user_id`, `provider_id`, `category`
- `interaction_type`: `impression`, `click`, `selected`, `booking_requested`,
  `booking_completed`, `booking_cancelled`, or `rated`
- optional `rating` in the range `1..5`
- `timestamp`: UTC datetime

Component 1 records recommendation impressions automatically. Explicit customer actions
are retained as weighted collaborative-filtering preferences for later requests.

## Ownership

- The core backend owns user authentication and canonical records.
- Component 1 reads providers, service requests, and interactions to produce Top-20 candidates.
- Components 2-4 may enrich pipeline payloads but must not rewrite shared IDs.
- Password hashes and authentication tokens are never passed to ML components.

## Indexes

- Unique: `users.user_id`, `users.email`
- Unique: `providers.provider_id`, `providers.user_id`
- Unique: `service_requests.request_id`
- Unique: `customer_profiles.customer_id`, `customer_profiles.user_id`
- Unique: `interactions.interaction_id`
- Search: provider and request `category`, `district`, `city`
- History: `service_requests(user_id, created_at desc)`
- History: `interactions(user_id, timestamp desc)`, `interactions(provider_id, timestamp desc)`
