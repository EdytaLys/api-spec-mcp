---
name: repo-to-openapi
description: >
  Scans a Java Spring Boot repository and generates a complete OpenAPI 3.0 YAML specification
  with all endpoints, parameters, request/response schemas, Bean Validation constraints, and
  security requirements. Use this whenever the user wants to generate an OpenAPI spec, Swagger
  file, or API documentation from a Spring Boot codebase.
---

# repo-to-openapi (Spring Boot)

Generate a complete, valid OpenAPI 3.0.3 YAML from a Spring Boot codebase.

## Step 1: Find all controllers

Grep for controller files:
```
@RestController
@Controller
@RequestMapping
```
List every `*Controller.java` / `*Controller.kt` file.

## Step 2: For each controller, extract endpoints

Read each controller and record:

| Field | How to find it |
|-------|---------------|
| Base path | `@RequestMapping("/base")` on the class |
| HTTP method | `@GetMapping`, `@PostMapping`, `@PutMapping`, `@PatchMapping`, `@DeleteMapping` |
| Path | Annotation value, e.g. `@GetMapping("/{id}")` — combine with base path |
| Path params | `@PathVariable Type name` in method signature |
| Query params | `@RequestParam(required=?, defaultValue=?)` in method signature |
| Request body | `@RequestBody ClassName body` — find that class |
| Response type | Method return type or `ResponseEntity<T>` |
| Auth | `@PreAuthorize`, `@Secured`, or class-level security annotations |

## Step 3: Find DTO/request classes and map Bean Validation

For each request/response class, read its fields and annotations:

```
@NotNull, @NotBlank, @NotEmpty  → required field
@Size(min=N, max=M)             → minLength/maxLength (strings) or minItems/maxItems (arrays)
@Min(N) / @Max(N)               → minimum / maximum
@Email                          → format: email
@Pattern(regexp="...")          → pattern: "..."
@Positive                       → minimum: 1
@PositiveOrZero                 → minimum: 0
@Digits(integer=N, fraction=M)  → type: number, description with precision
@URL                            → format: uri
@Past / @Future                 → type: string, format: date-time (add note in description)
```

Also check Jackson annotations: `@JsonProperty("name")` → use that as the field name.

## Step 4: Determine response status codes

```
ResponseEntity.ok(...)          → 200
ResponseEntity.created(uri)     → 201
ResponseEntity.noContent()      → 204
ResponseEntity.notFound()       → 404
ResponseEntity.badRequest()     → 400
@ResponseStatus(HttpStatus.X)   → use that code
void return type with no annotation → 200
```

Always include `400` for endpoints with `@Valid @RequestBody`.

## Step 5: Check security config

Look for `SecurityConfig.java` or `WebSecurityConfig.java`:
- `.permitAll()` routes → no security
- `.authenticated()` routes → require auth
- `.oauth2ResourceServer(...)` or `JwtDecoder` bean → BearerAuth (JWT)
- `@PreAuthorize("isAuthenticated()")` on controller/method → require auth

## Step 6: Write the OpenAPI YAML

```yaml
openapi: "3.0.3"
info:
  title: <from application.properties spring.application.name, or infer from project>
  version: "1.0.0"

servers:
  - url: http://localhost:8080
    description: Local

tags:
  - name: <controller name without "Controller">

paths:
  /api/users/{id}:
    get:
      tags: [users]
      summary: <from Javadoc or method name>
      operationId: getUserById
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
            format: int64
      responses:
        "200":
          description: Success
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/UserResponse"
        "404":
          description: Not found

components:
  schemas:
    UserResponse:
      type: object
      required: [id, email]
      properties:
        id:
          type: integer
          format: int64
        email:
          type: string
          format: email
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

Rules:
- Status codes must be **strings**: `"200"`, not `200`
- Path params always have `required: true`
- Schemas used in more than one place go in `components/schemas` with `$ref`
- Java types → OpenAPI: `Long/long` → `integer/int64`, `Integer/int` → `integer/int32`, `String` → `string`, `Boolean` → `boolean`, `Double/Float` → `number`, `List<T>` → `array`, `LocalDate` → `string/date`, `LocalDateTime/Instant` → `string/date-time`, `UUID` → `string/uuid`

## Output

Save as `openapi.yaml` in the repo root (or user-specified location). Print a brief summary:
```
Generated openapi.yaml
  Endpoints : N
  Schemas   : N
  Auth      : Bearer JWT / none
```
