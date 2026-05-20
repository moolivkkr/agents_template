# Structured Wireframe Format — YAML-Based UI Specifications

## Purpose

Replace text-based markdown tables with a structured YAML format that enables machine-readable wireframe specs. The YAML format provides typed data source references, explicit state definitions, and validates against data-contracts.md.

This format is OPTIONAL — the standard markdown wireframe format remains the default. Use this format when:
- The project has complex multi-component screens
- You need machine-parseable specs for automated validation
- The team prefers structured data over prose

---

## Format Specification

### Top-Level Structure
```yaml
# <screen-name>.wireframe.yaml
screen:
  name: "User List"
  route: "/users"
  purpose:
    story: "As an admin, I want to view all users so that I can manage team membership"
    brd_ref: "FR-UI-001"

layout:
  desktop: { ... }
  mobile: { ... }

components:
  - { ... }

api_bindings:
  - { ... }

states:
  loading: { ... }
  empty: { ... }
  error: { ... }
  populated: { ... }

error_boundaries:
  - { ... }

interactions:
  - { ... }

accessibility:
  heading_hierarchy: { ... }
  landmarks: [ ... ]
  focus_order: [ ... ]
```

---
## Component Tree — Typed Data Source References

### List Page Example
```yaml
screen:
  name: "User List"
  route: "/users"
  purpose:
    story: "As an admin, I want to view all users so that I can manage team membership"
    brd_ref: "FR-UI-001"

layout:
  desktop:
    width: 1280
    regions:
      - name: header
        element: "header"
        children: [page_title, create_button]
      - name: main
        element: "main"
        children: [search_bar, filter_group, user_table, pagination]
      - name: sidebar
        element: "aside"
        children: [stats_widget]
  mobile:
    width: 375
    regions:
      - name: header
        element: "header"
        children: [page_title, create_button_fab]
      - name: main
        element: "main"
        children: [search_bar, user_cards, pagination]
        # sidebar collapses into main on mobile

components:
  - id: page_title
    primitive: "h1"
    text: "Users"
    class: "text-3xl font-bold tracking-tight"

  - id: create_button
    primitive: "Button"
    text: "Add User"
    icon: "Plus"
    variant: "default"
    touch_target: "44px"
    action: { type: "navigate", to: "/users/new" }

  - id: create_button_fab
    primitive: "Button"
    variant: "default"
    icon: "Plus"
    aria_label: "Add User"
    class: "fixed bottom-4 right-4 size-14 rounded-full shadow-lg"
    touch_target: "56px"
    action: { type: "navigate", to: "/users/new" }

  - id: search_bar
    primitive: "Input"
    placeholder: "Search users..."
    icon: "Search"
    debounce_ms: 300
    aria_label: "Search users"
    state_key: "search"

  - id: filter_group
    primitive: "Select"
    options:
      - { value: "all", label: "All Roles" }
      - { value: "admin", label: "Admin" }
      - { value: "member", label: "Member" }
      - { value: "viewer", label: "Viewer" }
    state_key: "role_filter"

  - id: user_table
    primitive: "DataTable"
    data_source:
      $ref: "data-contracts.md#ListUsersResponse"
      endpoint: "GET /api/v1/users"
      response_type: "array"
    columns:
      - field: "data[].name"
        header: "Name"
        sortable: true
        contract_ref: "UserResponse.name"
      - field: "data[].email"
        header: "Email"
        sortable: true
        contract_ref: "UserResponse.email"
      - field: "data[].role"
        header: "Role"
        sortable: true
        contract_ref: "UserResponse.role"
        render: "Badge"
      - field: "data[].created_at"
        header: "Joined"
        sortable: true
        contract_ref: "UserResponse.created_at"
        render: "RelativeDate"
    row_actions:
      - { icon: "Pencil", label: "Edit", action: { type: "navigate", to: "/users/:id/edit" } }
      - { icon: "Trash", label: "Delete", action: { type: "mutation", confirm: true } }

  - id: user_cards
    primitive: "CardList"
    data_source:
      $ref: "data-contracts.md#ListUsersResponse"
      endpoint: "GET /api/v1/users"
      response_type: "array"
    card_fields:
      - { field: "data[].name", role: "title", contract_ref: "UserResponse.name" }
      - { field: "data[].email", role: "subtitle", contract_ref: "UserResponse.email" }
      - { field: "data[].role", role: "badge", contract_ref: "UserResponse.role" }

  - id: pagination
    primitive: "Pagination"
    data_source:
      $ref: "data-contracts.md#ListUsersResponse.meta"
    fields:
      page: "meta.page"
      total: "meta.total"
      per_page: "meta.per_page"

  - id: stats_widget
    primitive: "Card"
    data_source:
      $ref: "data-contracts.md#UserStatsResponse"
      endpoint: "GET /api/v1/users/stats"
      response_type: "object"
    fields:
      - { field: "data.total_users", label: "Total Users", contract_ref: "UserStatsResponse.total_users" }
      - { field: "data.active_users", label: "Active", contract_ref: "UserStatsResponse.active_users" }
```

---

## State Definitions

```yaml
states:
  loading:
    user_table:
      component: "TableSkeleton"
      props: { rows: 5, columns: 4 }
      description: "5-row skeleton matching table column structure"
    stats_widget:
      component: "CardSkeleton"
      props: { fields: 2 }
      description: "Stats card with 2 skeleton metric rows"
    user_cards:  # mobile variant
      component: "CardListSkeleton"
      props: { count: 5 }

  empty:
    user_table:
      component: "EmptyState"
      props:
        icon: "Users"
        title: "No users yet"
        description: "Add your first team member to get started."
        cta:
          text: "Add User"
          action: { type: "navigate", to: "/users/new" }
          icon: "Plus"

  error:
    user_table:
      component: "ErrorState"
      props:
        icon: "AlertCircle"
        message: "Failed to load users"
        retry: true  # shows retry button that calls refetch()
      message_rule: "NEVER expose server error.message — use static user-friendly text"

    stats_widget:
      component: "ErrorState"
      props:
        icon: "AlertCircle"
        message: "Stats unavailable"
        retry: true

  populated:
    user_table:
      description: "Renders DataTable with user rows from API response"
      data_binding: "data-contracts.md#ListUsersResponse.data"
      pagination: "data-contracts.md#ListUsersResponse.meta"
    stats_widget:
      description: "Renders stat metrics from API response"
      data_binding: "data-contracts.md#UserStatsResponse.data"
```

---

## Error Boundary Definitions

```yaml
error_boundaries:
  - component: user_table
    data_source: "GET /api/v1/users"
    scope: "section"
    recovery: "retry_button"
    description: "Only the table shows error; stats widget renders independently"

  - component: stats_widget
    data_source: "GET /api/v1/users/stats"
    scope: "section"
    recovery: "retry_button"
    description: "Stats widget error doesn't affect user table"

  - component: page_layout
    data_source: null  # catches unhandled errors
    scope: "page"
    recovery: "full_page_error"
    description: "Last resort — full page error with Go Home link"
```

---

## Detail Page Example

```yaml
screen:
  name: "User Detail"
  route: "/users/:id"
  purpose:
    story: "As an admin, I want to view user details so that I can review their profile"
    brd_ref: "FR-UI-002"

api_bindings:
  - id: user_detail
    endpoint: "GET /api/v1/users/:id"
    $ref: "data-contracts.md#GetUserResponse"
    response_type: "object"
    params:
      id: { source: "route_param", key: "id" }

components:
  - id: user_header
    primitive: "div"
    children:
      - id: avatar
        primitive: "Avatar"
        data_source: { $ref: "user_detail", field: "data.avatar_url", contract_ref: "UserResponse.avatar_url" }
        fallback: { type: "initials", field: "data.name" }
      - id: user_name
        primitive: "h1"
        data_source: { $ref: "user_detail", field: "data.name", contract_ref: "UserResponse.name" }
      - id: user_email
        primitive: "p"
        data_source: { $ref: "user_detail", field: "data.email", contract_ref: "UserResponse.email" }
        class: "text-muted-foreground"

  - id: user_details_card
    primitive: "Card"
    children:
      - id: role_field
        primitive: "DescriptionItem"
        label: "Role"
        data_source: { $ref: "user_detail", field: "data.role", contract_ref: "UserResponse.role" }
        render: "Badge"
      - id: joined_field
        primitive: "DescriptionItem"
        label: "Joined"
        data_source: { $ref: "user_detail", field: "data.created_at", contract_ref: "UserResponse.created_at" }
        render: "RelativeDate"

states:
  loading:
    user_header:
      component: "HeaderSkeleton"
      props: { avatar: true, lines: 2 }
    user_details_card:
      component: "CardSkeleton"
      props: { fields: 4 }
  empty: null  # detail pages don't have empty state — 404 handled by error
  error:
    user_header:
      component: "ErrorState"
      props:
        message: "User not found"
        action: { type: "navigate", to: "/users", text: "Back to Users" }
  populated:
    description: "Renders user profile with all fields from GetUserResponse"
```

---

## Form Page Example

```yaml
screen:
  name: "Create User"
  route: "/users/new"
  purpose:
    story: "As an admin, I want to create a new user so that I can add team members"
    brd_ref: "FR-UI-003"

api_bindings:
  - id: create_user
    endpoint: "POST /api/v1/users"
    $ref: "data-contracts.md#CreateUserRequest"
    method: "mutation"

components:
  - id: form
    primitive: "Form"
    validation_schema:
      $ref: "lib/validations/user.ts#createUserSchema"
      source: "data-contracts.md#CreateUserRequest"
    fields:
      - id: name_field
        primitive: "FormField"
        name: "name"
        type: "text"
        label: "Full Name"
        placeholder: "Jane Doe"
        contract_ref: "CreateUserRequest.name"
        validation: { min: 2, max: 50 }

      - id: email_field
        primitive: "FormField"
        name: "email"
        type: "email"
        label: "Email Address"
        placeholder: "jane@company.com"
        contract_ref: "CreateUserRequest.email"
        validation: { format: "email" }

      - id: role_field
        primitive: "FormField"
        name: "role"
        type: "select"
        label: "Role"
        options:
          - { value: "admin", label: "Admin" }
          - { value: "member", label: "Member" }
          - { value: "viewer", label: "Viewer" }
        contract_ref: "CreateUserRequest.role"
        validation: { enum: ["admin", "member", "viewer"] }

    submit:
      text: "Create User"
      loading_text: "Creating..."
      icon: "Plus"

interactions:
  - trigger: "form_submit_success"
    action: { type: "navigate", to: "/users" }
    feedback: { type: "toast", variant: "success", message: "User created" }

  - trigger: "form_submit_422"
    action: { type: "map_server_errors" }
    feedback: { type: "field_errors" }

  - trigger: "form_submit_error"
    action: null
    feedback: { type: "toast", variant: "error", message: "Failed to create user" }

accessibility:
  heading_hierarchy:
    h1: "Create User"
  landmarks:
    - { element: "main", contains: ["form"] }
    - { element: "nav", contains: ["breadcrumb"] }
  focus_order:
    - "name_field"
    - "email_field"
    - "role_field"
    - "submit_button"
    - "cancel_link"
```

---

## Validation Rules

When using this YAML format, the following validation rules apply:

1. **Every `$ref`** must resolve to an actual type in data-contracts.md
2. **Every `contract_ref`** must match a field name in the referenced type
3. **`response_type: "array"`** components must use list primitives (DataTable, CardList, List)
4. **`response_type: "object"`** components must use detail primitives (Card, DescriptionList)
5. **All 4 states** must be defined for every data-fetching component
6. **Error boundaries** must be defined for every data-fetching component
7. **Validation constraints** in form fields must match data-contracts.md annotations
8. **Touch targets** must be >= 44px for all interactive elements on mobile layout

The `design_quality_reviewer` can parse this YAML format to automate all 10 dimension checks.
