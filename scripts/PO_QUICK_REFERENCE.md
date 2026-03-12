# Product Owner Quick Reference

## Before You Start

Set up your JIRA credentials (one-time setup):
```bash
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens

## Running the Script

```bash
python create_api_update_story.py
```

## What You'll Be Asked

### 1. Story Type
- Choose 1 for NEW API endpoint
- Choose 2 for UPDATE to existing API

### 2. Basic Information
- **Endpoint path**: e.g., /api/users, /api/tasks/{id}
- **HTTP method**: GET, POST, PUT, PATCH, DELETE
- **Purpose**: What does this API do? (plain English)

### 3. Fields (for both new and update)

Format: `fieldName, type, required/optional`

**Common types:**
- string - text
- integer - whole numbers
- number - decimals
- boolean - true/false
- date - dates
- enum (VALUE1/VALUE2) - predefined choices

**Examples:**
```
email, string, required
age, integer, optional
price, number, required
isActive, boolean, required
status, enum (ACTIVE/INACTIVE/PENDING), required
createdAt, date, required
```

### 4. Validation Rules (plain English)

Describe business rules without technical jargon.

**Examples:**
```
Email must be valid format and unique
Age must be between 18 and 100
Title must be unique within the project
Password must be at least 8 characters
Price must be greater than zero
Due date must be in the future
Username can only contain letters, numbers, and underscores
```

### 5. Error Scenarios

Format: `HTTP_CODE - Error message`

**Common HTTP codes:**
- 400 - Bad Request (invalid input)
- 401 - Unauthorized (not logged in)
- 403 - Forbidden (no permission)
- 404 - Not Found (resource doesn't exist)
- 409 - Conflict (duplicate/constraint violation)
- 422 - Unprocessable Entity (validation failed)
- 500 - Internal Server Error (system error)

**Examples:**
```
400 - Invalid email format
400 - Age must be at least 18
404 - User not found
409 - Email already registered
409 - Title already exists in project
422 - Password does not meet complexity requirements
```

## Tips for Success

### Be Specific
❌ Bad: "Email should be valid"
✅ Good: "Email must be valid format and unique in the system"

### Include All Constraints
❌ Bad: "Age is required"
✅ Good: "Age must be between 18 and 100"

### Describe Business Rules
❌ Bad: "Validate the title"
✅ Good: "Title must be unique within the project and max 200 characters"

### Think About Edge Cases
- What happens if a field is empty?
- What happens if a value already exists?
- What happens if a related resource doesn't exist?
- What are the min/max values?

## Example: Complete New API

```
Endpoint: /api/products
Method: POST
Purpose: create new products in the catalog

Fields:
  name, string, required
  description, string, optional
  price, number, required
  category, enum (ELECTRONICS/CLOTHING/FOOD), required
  inStock, boolean, required

Validation Rules:
  Name must be unique and max 100 characters
  Price must be greater than zero
  Description max 500 characters if provided

Error Scenarios:
  400 - Invalid price (must be greater than zero)
  400 - Invalid category value
  409 - Product name already exists
```

## Example: Update Existing API

```
Endpoint: PATCH /api/products/{id}
Changes:
  Add support for partial updates
  Only provided fields are updated
  Keep PUT for full replacement

Fields:
  name, string, optional
  price, number, optional
  inStock, boolean, optional

Validation Rules:
  Name must be unique if provided
  Price must be greater than zero if provided

Error Scenarios:
  400 - Invalid price value
  404 - Product not found
  409 - Product name already exists

Acceptance Criteria:
  PATCH with only price updates price, other fields unchanged
  PATCH with empty body returns 200 with unchanged product
  updatedAt timestamp is refreshed on every successful PATCH
```

## Common Mistakes to Avoid

### 1. Mixing Technical and Business Language
❌ "Validate regex pattern for email"
✅ "Email must be valid format"

### 2. Forgetting Required vs Optional
❌ "email, string"
✅ "email, string, required"

### 3. Vague Validation Rules
❌ "Title should be good"
✅ "Title must be 5-200 characters and unique within project"

### 4. Missing Error Scenarios
Always think about:
- Invalid input (400)
- Not found (404)
- Duplicates (409)
- Permission issues (403)

## Need Help?

- See `EXAMPLE_NEW_API_STORY.md` for a complete new API example
- See `EXAMPLE_PATCH_STORY.md` for an update API example
- See `API_UPDATE_STORY_GUIDE.md` for detailed documentation
