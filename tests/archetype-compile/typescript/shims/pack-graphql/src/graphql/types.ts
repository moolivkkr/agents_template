// HARNESS STUB: the project's GraphQL domain types and data access that frameworks/graphql.md's resolvers use.
export interface Widget {
  id: string;
  name: string;
  createdById: string;
}
export interface User {
  id: string;
  name: string;
}
export interface Tag {
  id: string;
  widgetId: string;
  label: string;
}
export interface WidgetFilter {
  status?: "ACTIVE" | "DRAFT";
}
export interface CreateWidgetInput {
  name: string;
  description?: string;
}
export interface UserError {
  field: string | null;
  message: string;
  code: "VALIDATION_ERROR" | "NOT_FOUND" | "CONFLICT" | "FORBIDDEN";
}
export interface Database {
  users: { findByIds(ids: string[]): Promise<User[]> };
  tags: { findByWidgetIds(widgetIds: string[]): Promise<Tag[]> };
}
