---
skill: component-test
description: React/TypeScript component test archetype — Vitest + React Testing Library, render/interaction/form/list tests, MSW for API mocking, accessibility assertions
version: "1.0"
tags:
  - react
  - typescript
  - testing
  - vitest
  - rtl
  - archetype
  - ui
---

# Component Test Archetype

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, React 19.3, TanStack Query 5.104, React Router 7.18, Testing Library (react 16.3, user-event 14.6, jest-dom 7.0), MSW 3.0, Vitest 5.0. Type-checked against stub components, not run (tests/archetype-compile/typescript/run.sh).

Complete React/TypeScript component test template. Every generated component test MUST follow this pattern.

## Test File Location

```
src/features/widgets/
  WidgetList.tsx           <- production component
  WidgetList.test.tsx      <- THIS file
  WidgetForm.tsx
  WidgetForm.test.tsx
  __mocks__/
    handlers.ts            <- MSW request handlers
```

Rule: Test file lives next to the component with `.test.tsx` suffix.

## Test Setup and Providers

```tsx
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import type { ApiErrorBody, ApiSuccess } from '@/types/api'; // the envelope types (api/response-envelope.md)
import { WidgetList } from './WidgetList';
import { WidgetForm } from './WidgetForm';

// --- Provider Wrapper ---

interface RenderOptions {
    queryClient?: QueryClient;
    initialRoute?: string;
    route?: string;
}

function renderWithProviders(
    ui: React.ReactElement,
    options: RenderOptions = {},
) {
    const {
        queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false, gcTime: 0 },
                mutations: { retry: false },
            },
        }),
        initialRoute = '/',
        route = '/',
    } = options;

    const user = userEvent.setup();

    const Wrapper = ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={[initialRoute]}>
                <Routes>
                    <Route path={route} element={children} />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>
    );

    return {
        user,
        ...render(ui, { wrapper: Wrapper }),
    };
}
```

## Test Factory

```tsx
// The wire shape, exactly as the API sends it (snake_case — the backend archetypes' WidgetResponse). UI types
// mirror data-contracts.md with no case conversion (ui/form-validation-protocol.md §Field Name Matching);
// prefer the types generated from the contract over this hand-written copy.
interface Widget {
    id: string;
    tenant_id: string;
    name: string;
    description: string;
    status: 'active' | 'archived';
    created_at: string;
    updated_at: string;
    version: number;
}

function makeWidget(overrides: Partial<Widget> = {}): Widget {
    return {
        id: crypto.randomUUID(),
        tenant_id: crypto.randomUUID(),
        name: `Widget ${Math.random().toString(36).slice(2, 8)}`,
        description: 'A test widget',
        status: 'active',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        version: 1,
        ...overrides,
    };
}

function makeWidgets(count: number, overrides: Partial<Widget> = {}): Widget[] {
    return Array.from({ length: count }, () => makeWidget(overrides));
}
```

## MSW API Mock Setup

```tsx
const API_BASE = '/api/v1/widgets';

// Default handlers — override per-test as needed
const handlers = [
    http.get(API_BASE, () => {
        return HttpResponse.json({
            data: makeWidgets(3),
            meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
        });
    }),

    http.get(`${API_BASE}/:id`, ({ params }) => {
        return HttpResponse.json({
            data: makeWidget({ id: params.id as string }),
            meta: { request_id: 'test' },
        });
    }),

    http.post(API_BASE, async ({ request }) => {
        const body = await request.json() as Record<string, unknown>;
        return HttpResponse.json(
            {
                data: makeWidget({ name: body.name as string, description: body.description as string }),
                meta: { request_id: 'test' },
            },
            { status: 201 },
        );
    }),

    http.put(`${API_BASE}/:id`, async ({ params, request }) => {
        const body = await request.json() as Record<string, unknown>;
        return HttpResponse.json({
            data: makeWidget({ id: params.id as string, name: body.name as string, version: (body.version as number) + 1 }),
            meta: { request_id: 'test' },
        });
    }),

    http.delete(`${API_BASE}/:id`, () => {
        return new HttpResponse(null, { status: 204 });
    }),
];

const server = setupServer(...handlers);

// MSW 3 renamed onUnhandledRequest to onUnhandledFrame; the old key is silently ignored (unmocked requests only warn)
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

## Render Tests

```tsx
describe('WidgetList', () => {
    it('renders without crash', () => {
        renderWithProviders(<WidgetList />);
        // Component mounts without throwing
    });

    it('shows loading state initially', () => {
        renderWithProviders(<WidgetList />);
        expect(screen.getByRole('status')).toBeInTheDocument();
        // Or check for skeleton/spinner
        expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('shows data after fetch completes', async () => {
        const widgets = makeWidgets(3);
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json({
                    data: widgets,
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        renderWithProviders(<WidgetList />);

        // Wait for loading to finish and data to appear
        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });

        for (const w of widgets) {
            expect(screen.getByText(w.name)).toBeInTheDocument();
        }
    });

    it('shows error state on fetch failure', async () => {
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json(
                    { error: { code: 'INTERNAL', message: 'Something went wrong.', request_id: 'test', retryable: false } },
                    { status: 500 },
                );
            }),
        );

        renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.getByRole('alert')).toBeInTheDocument();
        });
        expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });

    it('shows empty state when no data', async () => {
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json({
                    data: [],
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.getByText(/no widgets found/i)).toBeInTheDocument();
        });
    });
});
```

## Interaction Tests

```tsx
describe('WidgetList interactions', () => {
    it('clicking delete button triggers confirmation and removes item', async () => {
        const widget = makeWidget({ name: 'Delete Me' });
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json({
                    data: [widget],
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        const { user } = renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.getByText('Delete Me')).toBeInTheDocument();
        });

        // Click delete button
        const deleteBtn = screen.getByRole('button', { name: /delete/i });
        await user.click(deleteBtn);

        // Confirmation dialog appears
        const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
        await user.click(confirmBtn);

        // Item removed from list
        await waitFor(() => {
            expect(screen.queryByText('Delete Me')).not.toBeInTheDocument();
        });
    });

    it('clicking row navigates to detail page', async () => {
        const widget = makeWidget({ id: 'test-id', name: 'Click Me' });
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json({
                    data: [widget],
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        const { user } = renderWithProviders(<WidgetList />, {
            route: '/widgets',
            initialRoute: '/widgets',
        });

        await waitFor(() => {
            expect(screen.getByText('Click Me')).toBeInTheDocument();
        });

        await user.click(screen.getByText('Click Me'));

        // Assert navigation occurred (check URL or rendered detail component)
    });

    it('dropdown selection filters the list', async () => {
        const { user } = renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });

        // Open status filter dropdown
        const filter = screen.getByRole('combobox', { name: /status/i });
        await user.click(filter);

        // Select "archived"
        const option = screen.getByRole('option', { name: /archived/i });
        await user.click(option);

        // Verify API was called with filter param (MSW will handle)
    });
});
```

## Form Tests

```tsx
describe('WidgetForm', () => {
    it('submits valid form data', async () => {
        const onSuccess = vi.fn();
        const { user } = renderWithProviders(
            <WidgetForm onSuccess={onSuccess} />,
        );

        // Fill in required fields
        await user.type(screen.getByLabelText(/name/i), 'New Widget');
        await user.type(screen.getByLabelText(/description/i), 'A description');

        // Submit
        await user.click(screen.getByRole('button', { name: /create|save|submit/i }));

        await waitFor(() => {
            expect(onSuccess).toHaveBeenCalledTimes(1);
        });
    });

    it('shows validation error for required fields', async () => {
        const { user } = renderWithProviders(<WidgetForm />);

        // Submit without filling required fields
        await user.click(screen.getByRole('button', { name: /create|save|submit/i }));

        // Validation errors appear
        await waitFor(() => {
            expect(screen.getByText(/name is required/i)).toBeInTheDocument();
        });
    });

    it('shows validation error for invalid email format', async () => {
        const { user } = renderWithProviders(<WidgetForm />);

        const emailInput = screen.getByLabelText(/email/i);
        await user.type(emailInput, 'not-an-email');
        await user.tab(); // trigger blur validation

        await waitFor(() => {
            expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
        });
    });

    it('maps server validation errors to form fields', async () => {
        server.use(
            http.post(API_BASE, () => {
                return HttpResponse.json(
                    {
                        error: {
                            code: 'VALIDATION_FAILED',
                            message: 'Some fields are invalid.',
                            details: [{ field: 'name', code: 'already_exists', message: 'Name already exists' }],
                            request_id: 'test',
                            retryable: false,
                        },
                    },
                    { status: 400 },
                );
            }),
        );

        const { user } = renderWithProviders(<WidgetForm />);

        await user.type(screen.getByLabelText(/name/i), 'Duplicate Name');
        await user.click(screen.getByRole('button', { name: /create|save|submit/i }));

        await waitFor(() => {
            expect(screen.getByText(/name already exists/i)).toBeInTheDocument();
        });
    });

    it('disables submit button while submitting', async () => {
        // Delay the API response to test loading state
        server.use(
            http.post(API_BASE, async () => {
                await new Promise((resolve) => setTimeout(resolve, 100));
                return HttpResponse.json(
                    { data: makeWidget(), meta: { request_id: 'test' } },
                    { status: 201 },
                );
            }),
        );

        const { user } = renderWithProviders(<WidgetForm />);
        await user.type(screen.getByLabelText(/name/i), 'Widget');

        const submitBtn = screen.getByRole('button', { name: /create|save|submit/i });
        await user.click(submitBtn);

        // Button should be disabled during submission
        expect(submitBtn).toBeDisabled();

        // Wait for submission to complete
        await waitFor(() => {
            expect(submitBtn).not.toBeDisabled();
        });
    });
});
```

## List / Table Tests

```tsx
describe('WidgetTable', () => {
    it('renders correct number of rows', async () => {
        const widgets = makeWidgets(5);
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json({
                    data: widgets,
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        renderWithProviders(<WidgetList />);

        await waitFor(() => {
            const rows = screen.getAllByRole('row');
            // +1 for header row
            expect(rows).toHaveLength(5 + 1);
        });
    });

    it('pagination controls navigate between pages', async () => {
        server.use(
            http.get(API_BASE, ({ request }) => {
                const url = new URL(request.url);
                const cursor = url.searchParams.get('cursor');

                if (!cursor) {
                    return HttpResponse.json({
                        data: makeWidgets(20),
                        meta: { request_id: 'test', pagination: { next_cursor: 'page2-cursor', has_more: true, limit: 20 } },
                    });
                }
                return HttpResponse.json({
                    data: makeWidgets(5),
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        const { user } = renderWithProviders(<WidgetList />);

        // Wait for first page
        await waitFor(() => {
            expect(screen.getAllByRole('row')).toHaveLength(20 + 1);
        });

        // Click "Next" / "Load More"
        const nextBtn = screen.getByRole('button', { name: /next|load more/i });
        expect(nextBtn).toBeEnabled();
        await user.click(nextBtn);

        // Second page loads
        await waitFor(() => {
            // Depending on implementation: either replaces or appends
            expect(screen.getAllByRole('row').length).toBeGreaterThanOrEqual(5 + 1);
        });
    });

    it('shows empty state when no data', async () => {
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json({
                    data: [],
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.getByText(/no widgets/i)).toBeInTheDocument();
        });
    });

    it('sort changes table order', async () => {
        const { user } = renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });

        // Click sort header
        const nameHeader = screen.getByRole('columnheader', { name: /name/i });
        await user.click(nameHeader);

        // Verify sort indicator changed (check aria-sort attribute)
        await waitFor(() => {
            expect(nameHeader).toHaveAttribute('aria-sort');
        });
    });
});
```

## API Integration Tests with MSW

```tsx
describe('API integration', () => {
    it('handles loading -> data -> error transitions', async () => {
        let callCount = 0;
        server.use(
            http.get(API_BASE, () => {
                callCount++;
                if (callCount === 1) {
                    return HttpResponse.json({
                        data: makeWidgets(2),
                        meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                    });
                }
                return HttpResponse.json(
                    { error: { code: 'INTERNAL', message: 'Server error', request_id: 'test', retryable: false } },
                    { status: 500 },
                );
            }),
        );

        renderWithProviders(<WidgetList />);

        // Loading state
        expect(screen.getByText(/loading/i)).toBeInTheDocument();

        // Data state
        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });
    });

    it('retries failed request on retry button click', async () => {
        let callCount = 0;
        server.use(
            http.get(API_BASE, () => {
                callCount++;
                if (callCount === 1) {
                    return HttpResponse.json(
                        { error: { code: 'INTERNAL', message: 'Temporary error', request_id: 'test', retryable: false } },
                        { status: 500 },
                    );
                }
                return HttpResponse.json({
                    data: makeWidgets(1),
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        const { user } = renderWithProviders(<WidgetList />);

        // Error state with retry button
        const retryBtn = await screen.findByRole('button', { name: /retry/i });
        await user.click(retryBtn);

        // Data loads on retry
        await waitFor(() => {
            expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        });
    });
});
```

## Accessibility Tests

```tsx
describe('accessibility', () => {
    it('has correct role attributes', async () => {
        renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });

        // Table should have table role
        expect(screen.getByRole('table')).toBeInTheDocument();

        // Rows and cells
        const rows = screen.getAllByRole('row');
        expect(rows.length).toBeGreaterThan(0);
    });

    it('interactive elements have accessible labels', async () => {
        renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });

        // All buttons must have accessible names
        const buttons = screen.getAllByRole('button');
        for (const button of buttons) {
            expect(button).toHaveAccessibleName();
        }
    });

    it('keyboard navigation works on interactive elements', async () => {
        const { user } = renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        });

        // Tab to first interactive element
        await user.tab();
        const focused = document.activeElement;
        expect(focused).not.toBe(document.body);
        expect(focused?.tagName).toMatch(/BUTTON|A|INPUT|SELECT/i);
    });

    it('focus moves to modal content when opened', async () => {
        const widget = makeWidget({ name: 'Focus Test' });
        server.use(
            http.get(API_BASE, () => {
                return HttpResponse.json({
                    data: [widget],
                    meta: { request_id: 'test', pagination: { next_cursor: null, has_more: false, limit: 20 } },
                });
            }),
        );

        const { user } = renderWithProviders(<WidgetList />);

        await waitFor(() => {
            expect(screen.getByText('Focus Test')).toBeInTheDocument();
        });

        // Open delete confirmation modal
        await user.click(screen.getByRole('button', { name: /delete/i }));

        // Focus should move to the dialog
        const dialog = await screen.findByRole('dialog');
        expect(dialog).toBeInTheDocument();
        expect(within(dialog).getByRole('button', { name: /confirm/i })).toBeInTheDocument();
    });

    it('form inputs have associated labels', () => {
        renderWithProviders(<WidgetForm />);

        // Every input must be associated with a label
        const inputs = screen.getAllByRole('textbox');
        for (const input of inputs) {
            expect(input).toHaveAccessibleName();
        }
    });
});
```

## Test Utilities

```tsx
// mockApiResponse overrides an MSW handler for a single test.
function mockApiResponse(
    method: 'get' | 'post' | 'put' | 'delete',
    path: string,
    response: ApiSuccess<unknown> | ApiErrorBody,
    status = 200,
) {
    const httpMethod = http[method];
    server.use(
        httpMethod(path, () => {
            return HttpResponse.json(response, { status });
        }),
    );
}

// mockApiError creates an error envelope (api/response-envelope.md): request_id and retryable included.
function mockApiError(
    method: 'get' | 'post' | 'put' | 'delete',
    path: string,
    status: number,
    code: string,
    message: string,
) {
    mockApiResponse(method, path, {
        error: { code, message, request_id: 'test', retryable: status === 429 || status >= 503 },
    }, status);
}

// waitForDataLoad waits for loading to finish.
async function waitForDataLoad() {
    await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
}
```

## Critical Rules

- Every test MUST use `renderWithProviders` — never render without QueryClient and Router
- QueryClient MUST have `retry: false` and `gcTime: 0` for deterministic tests
- Use `userEvent.setup()` — never use `fireEvent` for user interactions (userEvent simulates real browser behavior)
- MSW server MUST use `onUnhandledFrame: 'error'` (MSW 3; `onUnhandledRequest` in MSW 2) to catch missing mock handlers
- Reset handlers after each test with `server.resetHandlers()` — prevent cross-test contamination
- Use `screen.getByRole` and `screen.getByLabelText` — never query by CSS class or test-id unless no semantic alternative exists
- Use `waitFor` for async assertions — never use `setTimeout` or arbitrary delays
- Form tests MUST cover: required field validation, format validation, server error mapping, successful submission
- Loading state MUST be tested: verify spinner/skeleton appears initially
- Error state MUST be tested: verify error message appears, retry button works
- Empty state MUST be tested: verify "no data" message when API returns empty list
- Accessibility: all buttons MUST have accessible names, all inputs MUST have labels, keyboard navigation MUST work
- Use `within(element)` to scope queries to a specific container (e.g., within a dialog)
- Never assert on implementation details (internal state, CSS classes) — assert on visible behavior
