"""Which TS/JS blocks of the React / Next / React Native / UI / UI-test packs are checked together, and which are
skipped (with why). Run `python3 harness.py --list` to see every block ref.

Block refs are "<pack file stem>#<n>", n = 1-based index of the TS/JS block in that file (```tsx / ts /
typescript / jsx / javascript / js, in document order).

A block lands at the path in its `// path` header comment; `place` overrides that for fragments: a path, an
optional slice (`from` inclusive / `until` exclusive, a line number or the start of a line), a `prelude`, a
`wrap`, and `auto` (a name -> (module, kind) map: the LIBRARY and shadcn/ui names an excerpt uses without
importing get imported — never declared). Declarations in preludes and the files under shims/ stand in for
APP-LEVEL code only: a project's payload types, its screens, its test fixtures, its copied shadcn/ui
components. A block may sit in several units (the real api-client.ts compiles under every hook that uses it).
"""

SCOPE = [
    "frameworks/react.md", "frameworks/nextjs.md", "frameworks/tanstack-query.md",
    "frameworks/react-native.md", "frameworks/react-native-app-patterns.md",
    "ui/*.md",
    "testing/msw.md", "testing/playwright.md", "testing/react-native-testing-library.md", "testing/detox.md",
    "testing/appium-mobile.md", "testing/mobile-testing-strategy.md", "testing/test-case-generation.md",
    "testing/test-case-traceability.md",
    "../agents/templates/ui_developer.tmpl",   # its React 4-states example is what ui_developer copies first
]

# Expected number of TS/JS blocks per file. A mismatch fails the run: a block was added or removed, so the
# units below must be updated to cover it.
FILES = {
    "frameworks/react.md": 4,
    "frameworks/nextjs.md": 3,
    "frameworks/tanstack-query.md": 7,
    "frameworks/react-native.md": 0,
    "frameworks/react-native-app-patterns.md": 1,
    "ui/README.md": 0,
    "ui/accessibility-patterns.md": 6,
    "ui/advanced-state-patterns.md": 11,
    "ui/api-integration-patterns.md": 8,
    "ui/component-composition.md": 5,
    "ui/error-handling-patterns.md": 6,
    "ui/form-patterns.md": 3,
    "ui/form-validation-protocol.md": 11,
    "ui/loading-states.md": 5,
    "ui/professional-ui-standards.md": 5,
    "ui/responsive-patterns.md": 7,
    "ui/secure-rendering.md": 1,
    "ui/shadcn.md": 15,
    "ui/stitch-design.md": 0,
    "ui/structured-wireframe-format.md": 0,
    "ui/tailwind.md": 5,
    "ui/type-generation-protocol.md": 4,
    "ui/vertix-portal-design-system.md": 2,
    "testing/msw.md": 7,
    "testing/playwright.md": 9,
    "testing/react-native-testing-library.md": 9,
    "testing/detox.md": 2,
    "testing/appium-mobile.md": 2,
    "testing/mobile-testing-strategy.md": 0,
    "testing/test-case-generation.md": 0,
    "testing/test-case-traceability.md": 1,
    "../agents/templates/ui_developer.tmpl": 1,
}

SKIP = {
    "accessibility-patterns#5": "comment-only block (what the shadcn Dialog does for focus); there is no code in it",
    "professional-ui-standards#1": "a reference list of Tailwind class strings (typography scale), not code",
    "professional-ui-standards#3": "a reference list of Tailwind class strings (interactive states), not code",
    "tailwind#3": "a reference list of Tailwind class strings (interactive states), not code",
    "vertix-portal-design-system#1": "imports @portal/contracts, a private package of that product (not on npm)",
    "vertix-portal-design-system#2": "imports @portal/components, a private package of that product (not on npm)",
}

# ----------------------------------------------------------------------------------------------- shared
# The one envelope (api/response-envelope.md, extracted at run time) + the payload types a project's
# data-contracts.md would generate (app-level: User, Order, …), wire names in snake_case.
PAYLOAD = """
// HARNESS STUB (app-level): payload types a project's data-contracts.md defines and
// ui/type-generation-protocol.md generates next to the envelope. Wire names, snake_case.
export type Role = "admin" | "member" | "viewer";
export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  avatar_url: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}
export interface CreateUserRequest { name: string; email: string; role: Role }
export interface UpdateUserRequest { name?: string; email?: string; role?: Role }
export type CreateUserInput = CreateUserRequest;
export interface Item { id: string; name: string; status: "active" | "inactive"; created_at: string; updated_at: string }
export type CreateItemInput = Pick<Item, "name" | "status">;
export interface Order { id: string; status: "open" | "paid" | "shipped"; total_cents: number; note: string; created_at: string }
export interface Resource { id: string; name: string; status: "active" | "inactive" }
export type CreateResourceInput = Pick<Resource, "name">;
"""


def envelope(path="src/types/api.ts", payload=True):
    return {"doc": "api/response-envelope.md", "prefix": "export type ApiSuccess<T>", "path": path,
            **({"append": PAYLOAD} if payload else {})}


def named(module, *names):
    return {n: (module, "named") for n in names}


SHADCN = {
    **named("@/components/ui/button", "Button", "buttonVariants"),
    **named("@/components/ui/input", "Input"),
    **named("@/components/ui/label", "Label"),
    **named("@/components/ui/field", "Field", "FieldLabel", "FieldDescription", "FieldError", "FieldGroup", "FieldSet",
            "FieldLegend", "FieldContent", "FieldTitle", "FieldSeparator"),
    **named("@/components/ui/separator", "Separator"),
    **named("@/components/ui/select", "Select", "SelectContent", "SelectItem", "SelectTrigger", "SelectValue"),
    **named("@/components/ui/card", "Card", "CardHeader", "CardTitle", "CardDescription", "CardContent", "CardFooter"),
    **named("@/components/ui/badge", "Badge"),
    **named("@/components/ui/skeleton", "Skeleton"),
    **named("@/components/ui/dialog", "Dialog", "DialogContent", "DialogDescription", "DialogFooter", "DialogHeader",
            "DialogTitle", "DialogTrigger"),
    **named("@/components/ui/sheet", "Sheet", "SheetContent", "SheetHeader", "SheetTitle", "SheetTrigger"),
    **named("@/components/ui/alert-dialog", "AlertDialog", "AlertDialogAction", "AlertDialogCancel",
            "AlertDialogContent", "AlertDialogDescription", "AlertDialogFooter", "AlertDialogHeader",
            "AlertDialogTitle", "AlertDialogTrigger"),
    **named("@/components/ui/avatar", "Avatar", "AvatarFallback", "AvatarImage"),
    **named("@/components/ui/tooltip", "Tooltip", "TooltipContent", "TooltipProvider", "TooltipTrigger"),
    **named("@/components/ui/dropdown-menu", "DropdownMenu", "DropdownMenuContent", "DropdownMenuItem",
            "DropdownMenuSeparator", "DropdownMenuTrigger"),
    **named("@/components/ui/table", "Table", "TableBody", "TableCell", "TableHead", "TableHeader", "TableRow"),
    **named("@/components/ui/checkbox", "Checkbox"),
    **named("@/lib/utils", "cn"),
}
LUCIDE = named("lucide-react", "Trash", "Trash2", "TrashIcon", "ChevronDown", "Plus", "MoreHorizontal", "Menu",
               "Settings", "Loader2", "AlertCircle", "RefreshCw", "Inbox", "Sun", "Moon")
REACT = {**named("react", "useState", "useEffect", "useRef", "useCallback", "useMemo", "Suspense"),
         "React": ("react", "namespace"), "Link": ("next/link", "default"),
         **named("@/lib/safe-render", "safeHref", "SafeHtml", "safeReturnTo")}
TANSTACK = named("@tanstack/react-query", "useQuery", "useMutation", "useQueryClient", "useInfiniteQuery",
                 "QueryClient", "QueryClientProvider", "MutationCache", "keepPreviousData", "queryOptions",
                 "infiniteQueryOptions", "onlineManager")
TANSTACK["InfiniteData"] = ("@tanstack/react-query", "type")
FORMS = {**named("react-hook-form", "useForm"), **named("@hookform/resolvers/zod", "zodResolver"),
         **named("zod", "z"), **named("sonner", "toast")}
WEB = {**SHADCN, **LUCIDE, **REACT, **TANSTACK, **FORMS}
VITEST = named("vitest", "describe", "it", "test", "expect", "vi", "beforeAll", "afterAll", "afterEach", "beforeEach")
RTL = {**named("@testing-library/react", "render", "screen", "waitFor", "within"),
       "userEvent": ("@testing-library/user-event", "default")}
MSW = named("msw", "http", "HttpResponse", "delay", "passthrough")

UTILS = {"path": "src/lib/utils.ts", "until": "// Usage:"}   # tailwind.md's cn() — every shadcn unit uses the real one


def frag(path, wrap="jsx", prelude="", **kw):
    return {"path": path, "wrap": wrap, "prelude": prelude.strip("\n"), **kw}


def shadcn_unit(name, refs, place, **kw):
    return {"name": name, "project": "web", "blocks": ["tailwind#1", *refs], "place": {"tailwind#1": UTILS, **place},
            "shims": ["shadcn"], "external": [envelope()], "auto": WEB, **kw}


def rn_unit(variant):
    """react-native-testing-library.md's two setups. msw2 (project rn/): its default Jest config + jest.setup.ts.
    msw3 (project rn-msw3/): its MSW 3 variant config + setup. The same screen, providers and tests run in both, plus a
    probe that an un-mocked request is rejected (the option name each major reads)."""
    rntl = "react-native-testing-library"
    msw3 = variant == "msw3"
    own = [6, 7] if msw3 else [1, 5, 8]          # the config/setup blocks of this variant (+ the type-only navigation)
    blocks = ["react-native-app-patterns#1", *[f"{rntl}#{n}" for n in sorted({2, 3, 4, 5, 9, *own})], "msw#1"]
    place = {
        "react-native-app-patterns#1": {"path": "screens/OrdersScreen.tsx"},
        f"{rntl}#3": {"path": "screens/OrdersScreen.test.tsx"},
        # one block, two files (its `// jest.setup.ts` line starts the second); the MSW 3 setup replaces the second
        f"{rntl}#5": [{"path": "test/msw-server.ts", "until": "// jest.setup.ts"},
                      *([] if msw3 else [{"path": "jest.setup.ts", "from": "// jest.setup.ts"}])],
        f"{rntl}#4": frag("screens/LoginScreen.test.tsx", wrap="custom",
                          open='test("harness: the userEvent excerpt, on a stub LoginScreen", async () => {', close="});"),
        f"{rntl}#9": frag("screens/SaveOrder.test.tsx", wrap="custom",
                          open='test("harness: the accessibility excerpt, on a stub button", async () => {\n'
                               "  await render(<SaveOrderButton />);", close="});"),
        "msw#1": {"path": "test/envelope.ts"},
    }
    if not msw3:
        place[f"{rntl}#8"] = frag("samples/navigation.tsx", wrap="async",
                                  prelude="declare const user: ReturnType<typeof userEvent.setup>;")
    return {"name": "react-native-msw3" if msw3 else "react-native", "project": "rn-msw3" if msw3 else "rn",
            "blocks": blocks, "external": [envelope("api/types.ts")], "shims": ["rn-app", "rn-probes"],
            "auto": {**named("@testing-library/react-native", "render", "screen", "userEvent", "fireEvent", "act"),
                     **named("@shopify/flash-list", "FlashList"), **named("@react-navigation/native", "NavigationContainer"),
                     **named("./orders-parts", "useOrders", "OrdersSkeleton", "ErrorState", "EmptyState", "OrderRow"),
                     **named("./other-screens", "LoginScreen", "SaveOrderButton"),
                     **named("../screens/other-screens", "RootStack")},
            "jest": ["screens"], "place": place,
            "executed_blocks": [b for b in blocks if b != f"{rntl}#8"]}


USER = 'import type { User } from "@/types/api";'
SAFE = {"path": "src/lib/safe-render.tsx"}   # secure-rendering.md's helpers, used where a pack binds a URL from data
# api-integration-patterns.md writes `// lib/…`, `// hooks/…` with an "@/" alias for src/
REMAP = {"lib/": "src/lib/", "hooks/": "src/hooks/", "components/": "src/components/", "app/": "src/app/"}

# app-level: the items resource the advanced-state samples call (a project's typed api object)
ITEMS_API = """
declare const api: {
  items: {
    list(params: { cursor?: string; limit: number; search: string; status: string; sort: string; order: string }): Promise<import("@/types/api").ApiSuccess<import("@/types/api").Item[]>>;
    create(input: import("@/types/api").CreateItemInput): Promise<import("@/types/api").ApiSuccess<import("@/types/api").Item>>;
    update(id: string, patch: Partial<import("@/types/api").Item>): Promise<import("@/types/api").ApiSuccess<import("@/types/api").Item>>;
    delete(id: string): Promise<void>;
  };
};
type CreateItemInput = import("@/types/api").CreateItemInput;"""

TYPEGEN_USAGE = """
import type { ReactNode } from "react";
declare function UserCard(props: { user: import("@/types/api").UserResponse }): ReactNode;
declare function listUsers(): Promise<import("@/types/api").ListUsersResponse>;"""

# type-generation-protocol.md says its envelope is "copied verbatim" from api/response-envelope.md: prove the
# four types are identical (mutual assignability is not enough; this is the exact-equality idiom).
ENVELOPE_IDENTITY = """
// HARNESS CHECK: the envelope types type-generation-protocol.md generates == api/response-envelope.md's.
import type * as Gen from "./api";
import type * as Ref from "./envelope-ref";
type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
type Payload = { id: string };
export const identical: [
  Equal<Gen.ApiSuccess<Payload>, Ref.ApiSuccess<Payload>>,
  Equal<Gen.ApiErrorBody, Ref.ApiErrorBody>,
  Equal<Gen.Pagination, Ref.Pagination>,
  Equal<Gen.FieldError, Ref.FieldError>,
] = [true, true, true, true];
"""

UNITS: list[dict] = [
    shadcn_unit("shadcn-pack", ["secure-rendering#1", *[f"shadcn#{n}" for n in range(1, 16)]], {
        "secure-rendering#1": SAFE,
        "shadcn#1": frag("src/samples/button-variants.tsx"),
        "shadcn#2": frag("src/samples/dialog.tsx", prelude="""
import type { FormEvent } from "react";
declare const user: { name: string };
declare function handleSubmit(e: FormEvent<HTMLFormElement>): void;"""),
        "shadcn#3": {"path": "src/components/create-user-form.tsx", "auto": WEB},
        "shadcn#4": frag("src/samples/data-table.tsx", prelude=USER + "\ndeclare const users: User[];"),
        "shadcn#5": frag("src/samples/class-name.tsx"),
        "shadcn#6": frag("src/samples/as-child.tsx"),
        "shadcn#7": frag("src/samples/skeleton.tsx"),
        "shadcn#8": frag("src/samples/sheet.tsx"),
        "shadcn#9": frag("src/samples/alert-dialog.tsx", prelude="declare function handleDelete(): void;"),
        "shadcn#10": frag("src/samples/badge.tsx"),
        "shadcn#11": frag("src/samples/avatar.tsx", prelude=USER + "\ndeclare const user: User;"),
        "shadcn#12": frag("src/samples/tooltip.tsx"),
        "shadcn#13": frag("src/samples/dropdown-menu.tsx"),
        "shadcn#14": frag("src/samples/toast.tsx", wrap="function", prelude="""
declare const payload: { name: string };
declare function saveData(p: { name: string }): Promise<void>;"""),
        "shadcn#15": frag("src/samples/card.tsx"),
    }, shims=["shadcn", "probes-shadcn"], vitest=["src/probes"], executed_blocks=["tailwind#1", "shadcn#3"]),
    shadcn_unit("accessibility-patterns", [f"accessibility-patterns#{n}" for n in (1, 2, 3, 4, 6)], {
        "accessibility-patterns#1": frag("src/samples/icon-buttons.tsx"),
        "accessibility-patterns#2": frag("src/samples/form-inputs.tsx"),
        "accessibility-patterns#3": frag("src/samples/live-regions.tsx", prelude="""
declare const results: { id: string }[];
declare const error: Error;"""),
        "accessibility-patterns#4": frag("src/samples/expandable.tsx", prelude="""
declare const expanded: boolean;
declare function setExpanded(next: boolean): void;"""),
        "accessibility-patterns#6": frag("src/samples/page-elements.tsx", prelude="""
import type { ReactNode } from "react";
declare const children: ReactNode;"""),
    }),
    shadcn_unit("component-composition", [f"component-composition#{n}" for n in range(1, 6)], {
        "component-composition#1": {"path": "src/components/common/status-badge.tsx", "auto": WEB},
        "component-composition#2": {"path": "src/components/common/alert.tsx", "auto": WEB},
        "component-composition#3": {"path": "src/components/common/custom-input.tsx", "auto": WEB},
        "component-composition#4": frag("src/samples/card-composition.tsx", prelude="""
type Member = { id: string; name: string };
declare const members: Member[];
declare function MemberRow(props: { member: Member }): React.JSX.Element;"""),
        "component-composition#5": frag("src/samples/data-table-composition.tsx", prelude=USER + """
import { StatusBadge } from "@/components/common/status-badge";
declare const users: User[];
declare const search: string;
declare function setSearch(value: string): void;
declare const roleFilter: string;
declare function setRoleFilter(value: string): void;
declare const hasNextPage: boolean;
declare const isFetchingNextPage: boolean;
declare function fetchNextPage(): void;
declare function SearchInput(props: { value: string; onChange: (value: string) => void; placeholder?: string }): React.JSX.Element;"""),
    }),
    shadcn_unit("responsive-patterns", ["secure-rendering#1", *[f"responsive-patterns#{n}" for n in range(1, 8)]], {
        "secure-rendering#1": SAFE,
        "responsive-patterns#1": frag("src/samples/grid.tsx", prelude="declare const items: { id: string }[];"),
        "responsive-patterns#2": frag("src/samples/sidebar.tsx", prelude="""
import type { ReactNode } from "react";
declare const children: ReactNode;"""),
        "responsive-patterns#3": {"path": "src/components/layout/main-nav.tsx", "auto": WEB, "prelude": """
declare function Logo(): React.JSX.Element;
declare function NavLink(props: { href: string; children: React.ReactNode }): React.JSX.Element;"""},
        "responsive-patterns#4": frag("src/samples/table-to-cards.tsx", prelude=USER + """
declare const users: User[];
declare const columns: unknown[];
declare function DataTable(props: { columns: unknown[]; data: User[] }): React.JSX.Element;"""),
        "responsive-patterns#5": frag("src/samples/modal-to-sheet.tsx"),
        "responsive-patterns#6": frag("src/samples/touch-targets.tsx"),
        "responsive-patterns#7": frag("src/samples/typography.tsx"),
    }),
    shadcn_unit("professional-ui-standards", ["api-integration-patterns#1", *[f"professional-ui-standards#{n}" for n in (2, 4, 5)]], {
        "professional-ui-standards#2": {"path": "src/components/resource-list.tsx", "auto": WEB, "prelude": """
import { resourceQueries } from "@/lib/queries/resources";
import type { Resource } from "@/types/api";
declare function openCreateDialog(): void;
declare function ResourceCard(props: { item: Resource }): React.JSX.Element;"""},
        "professional-ui-standards#4": frag("src/samples/card-structure.tsx", prelude="""
declare const title: string;
declare const subtitle: string;"""),
        "professional-ui-standards#5": frag("src/samples/page-layout.tsx"),
    }, shims=["shadcn", "app-queries"], remap=REMAP),
    # The 4-states example in .claude/agents/templates/ui_developer.tmpl, over the real api-client and the same
    # app-level resourceQueries (an infinite query of envelope pages) the pack examples use.
    shadcn_unit("ui-developer-template", ["api-integration-patterns#1", "ui_developer#1"], {
        "ui_developer#1": {"path": "src/components/resource-list.tsx", "auto": {**WEB, **named("@/lib/api-client", "ApiError")},
                           "prelude": """
import { resourceQueries } from "@/lib/queries/resources";
import type { LucideIcon } from "lucide-react";
import type { Resource } from "@/types/api";
declare function t(key: string): string;
declare function handleCreate(): void;
declare function ResourceListSkeleton(): React.JSX.Element;
declare function ErrorState(props: { message: string; requestId?: string; onRetry: () => void }): React.JSX.Element;
declare function EmptyState(props: { icon: LucideIcon; title: string; description: string; action: { label: string; onClick: () => void } }): React.JSX.Element;
declare function ResourceCard(props: { item: Resource }): React.JSX.Element;"""},
    }, shims=["shadcn", "app-queries"], remap=REMAP),
    shadcn_unit("loading-states", ["api-integration-patterns#1", "api-integration-patterns#4",
                                   *[f"loading-states#{n}" for n in (1, 2, 4, 5)]], {
        "loading-states#1": {"path": "src/components/loading.tsx"},
        "loading-states#2": frag("src/samples/button-loading.tsx", prelude="declare const isPending: boolean;"),
        "loading-states#4": {"path": "src/components/loading.tsx", "prelude": """
declare function StatsGrid(): React.JSX.Element;
declare function RecentActivity(): React.JSX.Element;
declare function QuickActions(): React.JSX.Element;"""},
        "loading-states#5": {"path": "src/components/loading.tsx", "prelude": USER + """
import { userQueries } from "@/lib/queries/users";
declare function UserRow(props: { user: User }): React.JSX.Element;"""},
    }, remap=REMAP),
    shadcn_unit("tailwind", ["tailwind#2", "tailwind#4", "tailwind#5"], {
        "tailwind#1": [UTILS, frag("src/samples/cn-usage.tsx", **{"from": "// Usage:"}, prelude="""
declare const variant: "error" | "default";
declare const className: string | undefined;""")],
        # one JSX element whose // comments sit inside the cn(...) call: an expression, the comments stay JS
        "tailwind#4": frag("src/samples/grouped-classes.tsx", wrap="custom", open="export const GroupedClasses = () => (",
                           close=");"),
        "tailwind#5": frag("src/components/theme-toggle.tsx", wrap="component"),
    }),
    {"name": "react-pack", "project": "web", "blocks": [f"react#{n}" for n in range(1, 5)], "external": [envelope()],
     "auto": WEB, "place": {
        "react#1": {"path": "src/components/user-card.tsx", "prelude": USER},
        "react#2": frag("src/samples/server-state.ts", wrap="function", prelude=USER + """
declare const userId: string;
declare const queryClient: QueryClient;
declare const api: { getUser(id: string): Promise<User>; updateUser(input: { id: string; name: string }): Promise<User> };"""),
        "react#3": {"path": "src/hooks/use-user-form.ts", "prelude": USER + """
type UserFormValues = { name: string };
declare const api: { getUser(id: string): Promise<User>; updateUser(input: { id: string; name: string }): Promise<User> };"""},
        "react#4": frag("src/samples/form.ts", wrap="function"),
    }},
    {"name": "tanstack-query", "project": "web", "blocks": [f"tanstack-query#{n}" for n in range(1, 8)],
     "external": [envelope()], "auto": WEB, "shims": ["probes-tanstack"], "vitest": ["src/probes"],
     "vitest_setup": ["./src/probes/setup.ts"], "executed_blocks": [f"tanstack-query#{n}" for n in (2, 3, 6, 7)],
     "place": {
        "tanstack-query#1": frag("src/App.tsx", wrap="component", prelude="""
import type { ReactNode } from "react";
declare const children: ReactNode;"""),
        "tanstack-query#2": {"path": "src/lib/queries/resources.ts", "prelude": """
import type { ApiSuccess, CreateResourceInput, Resource } from "@/types/api";
import { api, type Filters } from "@/lib/resource-api";"""},
        **{f"tanstack-query#{n}": {"path": "src/lib/queries/resources.ts"} for n in range(3, 8)},
    }},
    shadcn_unit("api-integration-patterns", [f"api-integration-patterns#{n}" for n in (1, 2, 3, 4, 5, 6, 8)], {
        "api-integration-patterns#6": {"path": "src/samples/response-shape.ts"},
    }, remap=REMAP, shims=["shadcn", "probes-api"], vitest=["src/probes"],
       vitest_setup=["./src/probes/setup.ts"], executed_blocks=["api-integration-patterns#1", "api-integration-patterns#2", "api-integration-patterns#8"]),
    {"name": "advanced-state-patterns", "project": "web",
     "blocks": ["api-integration-patterns#1", *[f"advanced-state-patterns#{n}" for n in range(1, 12)]],
     "external": [envelope()], "auto": {**WEB, **named("@/lib/api-client", "fetcher", "ApiError")}, "remap": REMAP,
     "shims": ["probes-state"], "vitest": ["src/probes"], "vitest_setup": ["./src/probes/setup.ts"],
     "executed_blocks": ["api-integration-patterns#1", "advanced-state-patterns#6"],
     "place": {
        "advanced-state-patterns#1": {"path": "src/hooks/items.ts", "prelude": ITEMS_API},
        "advanced-state-patterns#2": {"path": "src/hooks/items.ts"},
        "advanced-state-patterns#3": {"path": "src/hooks/items.ts"},
        "advanced-state-patterns#4": {"path": "src/hooks/use-web-socket.ts"},
        "advanced-state-patterns#5": frag("src/samples/ws-reconcile.ts", wrap="function", prelude="""
declare const ws: WebSocket;
declare const reconnectAttempts: { current: number };
declare const queryClient: QueryClient;"""),
        "advanced-state-patterns#6": {"path": "src/lib/offline-queue.ts"},
        "advanced-state-patterns#7": {"path": "src/lib/conflict.ts"},
        "advanced-state-patterns#8": {"path": "src/hooks/use-url-filters.tsx", "prelude": ITEMS_API + """
declare function SearchInput(props: { value: string; onChange: (value: string) => void }): React.JSX.Element;
declare function StatusFilter(props: { value: "all" | "active" | "inactive"; onChange: (value: "all" | "active" | "inactive") => void }): React.JSX.Element;
declare function SortSelect(props: { value: "name" | "created_at" | "updated_at"; order: "asc" | "desc"; onChange: (sort: "name" | "created_at" | "updated_at", order: "asc" | "desc") => void }): React.JSX.Element;
declare function CursorPager(props: { hasMore: boolean; onNext: () => void; onFirst?: () => void }): React.JSX.Element;"""},
        "advanced-state-patterns#9": {"path": "src/hooks/use-auth-sync.ts"},
        "advanced-state-patterns#10": {"path": "src/lib/synced-query-client.ts"},
        "advanced-state-patterns#11": {"path": "src/hooks/use-legacy-tab-sync.ts"},
    }},
    shadcn_unit("error-handling-patterns", ["api-integration-patterns#1", "api-integration-patterns#4",
                                            *[f"error-handling-patterns#{n}" for n in range(1, 7)]], {
        "error-handling-patterns#2": {"path": "src/components/user-list.tsx", "auto": WEB,
                                      "prelude": 'import { userQueries } from "@/lib/queries/users";'},
        "error-handling-patterns#3": frag("src/samples/mutation-toast.ts", wrap="function", prelude="""
import { api } from "@/lib/api-client";
declare const queryClient: QueryClient;"""),
        # the submit handler and the optimistic delete become hooks (form / mutation / queryClient are the
        # component's), so src/probes/error-handling.test.tsx can drive them against MSW
        "error-handling-patterns#4": frag("src/samples/server-validation.tsx", wrap="custom", prelude="""
import type { UseMutationResult } from "@tanstack/react-query";
import type { ApiSuccess, CreateUserRequest, User } from "@/types/api";""",
            open="export function useCreateUserSubmit(\n  form: UseFormReturn<CreateUserRequest>,\n"
                 "  createUser: UseMutationResult<ApiSuccess<User>, Error, { input: CreateUserRequest; idempotencyKey: string }>,\n) {",
            close="  return { onSubmit };\n}"),
        "error-handling-patterns#5": frag("src/samples/optimistic-delete.ts", wrap="custom", prelude="""
import { api } from "@/lib/api-client";
import type { ApiSuccess, User } from "@/types/api";""",
            open="export function useDeleteUser() {\n  const queryClient = useQueryClient();", close="  return deleteUser;\n}"),
        "error-handling-patterns#6": frag("src/samples/toasts.ts", wrap="function", prelude="""
declare function retry(): void;
declare function saveData(p: { name: string }): Promise<void>;
declare const payload: { name: string };
declare function deleteItem(id: string): void;
declare const id: string;"""),
    }, remap=REMAP, auto={**WEB, **named("react-hook-form", "UseFormReturn")}, shims=["shadcn", "probes-errors"],
       vitest=["src/probes"], vitest_setup=["./src/probes/setup.ts"],
       executed_blocks=["api-integration-patterns#1", "api-integration-patterns#4", "error-handling-patterns#4",
                        "error-handling-patterns#5"]),
    shadcn_unit("form-patterns", ["api-integration-patterns#1", "api-integration-patterns#4", "form-validation-protocol#2",
                                  "form-validation-protocol#3", *[f"form-patterns#{n}" for n in range(1, 4)]], {
        "form-validation-protocol#2": {"path": "src/lib/validations/user.ts"},
        "form-validation-protocol#3": {"path": "src/lib/validations/user.ts"},
        "form-patterns#1": {"path": "src/components/create-user-form.tsx", "auto": WEB},
        "form-patterns#2": {"path": "src/lib/form-errors.ts"},
        "form-patterns#3": {"path": "src/components/edit-user-form.tsx", "auto": WEB, "prelude": """
import { userQueries } from "@/lib/queries/users";
import { updateUserSchema, type UpdateUserInput } from "@/lib/validations/user";
declare function FormSkeleton(props: { fields: number }): React.JSX.Element;"""},
    }, remap=REMAP, shims=["shadcn", "probes-forms"], vitest=["src/probes"], vitest_setup=["./src/probes/setup.ts"],
       executed_blocks=["tailwind#1", "api-integration-patterns#1", "form-validation-protocol#2", "form-patterns#1",
                        "form-patterns#2"]),
    {"name": "form-validation-protocol", "project": "web", "remap": REMAP, "external": [envelope()],
     "blocks": ["api-integration-patterns#1", *[f"form-validation-protocol#{n}" for n in range(1, 12)]],
     "auto": {**WEB, **named("@/lib/api-client", "ApiError", "api")}, "place": {
        "form-validation-protocol#1": {"path": "src/samples/contract.ts"},
        "form-validation-protocol#2": {"path": "src/lib/validations/user.ts"},
        "form-validation-protocol#3": {"path": "src/lib/validations/user.ts"},
        "form-validation-protocol#4": {"path": "src/lib/form-errors.ts"},
        "form-validation-protocol#5": frag("src/samples/submit.ts", wrap="function", prelude="""
import type { UseFormReturn } from "react-hook-form";
import { mapServerErrors } from "@/lib/form-errors";
import type { CreateUserInput } from "@/lib/validations/user";
declare const form: UseFormReturn<CreateUserInput>;
declare const onSuccess: (() => void) | undefined;
declare const idempotencyKey: { current: string };"""),
        **{f"form-validation-protocol#{n}": frag(f"src/samples/zod-{n}.ts", wrap="function") for n in (6, 7, 8, 9)},
        "form-validation-protocol#10": {"path": "src/samples/zod-10.ts", "auto": WEB},
        "form-validation-protocol#11": {"path": "src/samples/zod-11.ts", "auto": WEB},
    }},
    {"name": "type-generation-protocol", "project": "web", "auto": WEB,
     "blocks": [f"type-generation-protocol#{n}" for n in (1, 2, 4)],
     "external": [envelope("src/types/envelope-ref.ts", payload=False)],
     "files": {"src/types/envelope-identity.ts": ENVELOPE_IDENTITY},
     "place": {
        "type-generation-protocol#1": {"path": "src/types/api.ts"},
        # one block, the ✅ and the ❌ version of the same component: one file each
        "type-generation-protocol#2": [
            {"path": "src/samples/usage.tsx", "until": "// ❌ BANNED", "prelude": TYPEGEN_USAGE},
            {"path": "src/samples/usage-banned.tsx", "from": "// ❌ BANNED", "auto": WEB, "prelude": TYPEGEN_USAGE},
        ],
        "type-generation-protocol#4": [
            frag("src/samples/banned.ts", wrap="function", until="// ✅ REQUIRED",
                 prelude='import type { ListUsersResponse, UserResponse } from "@/types/api";\ndeclare const response: ListUsersResponse;'),
            frag("src/samples/required.ts", wrap="function", **{"from": "// ✅ REQUIRED"},
                 prelude='import type { ListUsersResponse, UserResponse } from "@/types/api";\ndeclare const response: ListUsersResponse;'),
        ],
    }},
    {"name": "type-generation-expected-error", "project": "web", "blocks": ["type-generation-protocol#1", "type-generation-protocol#3"],
     "place": {"type-generation-protocol#1": {"path": "src/types/api.ts"},
               "type-generation-protocol#3": {"path": "src/samples/missing-field.ts", "prelude": "declare const user: UserResponse;"}},
     # the block exists to show this compile error: tsc must report exactly it, at the line the doc marks
     "expect_errors": [{"ref": "type-generation-protocol#3", "line": "const avatar = user.avatar;", "code": "TS2339"}]},
    {"name": "secure-rendering", "project": "web", "blocks": ["secure-rendering#1"], "place": {"secure-rendering#1": SAFE},
     "shims": ["probes-render"], "vitest": ["src/probes"], "vitest_setup": ["./src/probes/setup.ts"]},
    # A real Next.js App Router app built with `next build` (Next 16): frameworks/nextjs.md's Server/Client
    # Components and Server Action, api-integration-patterns.md's providers + prefetching page,
    # error-handling-patterns.md's error.tsx and loading-states.md's loading.tsx. Layout, db, auth and the
    # client UserList the prefetching page renders are app-level stubs (shims/next-app).
    {"name": "nextjs-app", "project": "web", "next_build": True, "remap": REMAP,
     "blocks": ["tailwind#1", "nextjs#1", "nextjs#2", "nextjs#3", "api-integration-patterns#1", "api-integration-patterns#3",
                "api-integration-patterns#4", "api-integration-patterns#5", "api-integration-patterns#7",
                "error-handling-patterns#1", "loading-states#3", "form-validation-protocol#2"],
     "external": [envelope()], "shims": ["shadcn", "next-app"], "compilerOptions": {"types": ["node"]},
     "auto": WEB,
     "place": {
        "tailwind#1": UTILS,
        "nextjs#1": [{"path": "src/app/(dashboard)/team/page.tsx", "until": "// app/users/user-list.tsx"},
                     {"path": "src/app/(dashboard)/team/user-list.tsx", "from": "// app/users/user-list.tsx"}],
        "nextjs#2": [frag("src/lib/samples/server-fetch.ts", wrap="async", until="// Client Component", prelude="""
import type { ApiSuccess } from "@/types/api";
type Product = { id: string; name: string; price_cents: number };
declare const id: string;"""),
                     frag("src/lib/samples/client-fetch.ts", wrap="function", **{"from": "// Client Component"}, prelude="""
declare const id: string;
declare const api: { getUser(id: string): Promise<import("@/types/api").ApiSuccess<import("@/types/api").User>> };""")],
        "nextjs#3": {"path": "src/app/(dashboard)/users/actions.ts"},
        "form-validation-protocol#2": {"path": "src/lib/validations/user.ts"},
     }},
    # The Tailwind CSS v4 token CSS: ui/tailwind.md's generated globals.css + its app tokens + ui/shadcn.md's
    # overrides (```css blocks, extracted by their first line) become app/globals.css of a Next.js app built with
    # @tailwindcss/postcss; Playwright (system Chrome) then reads computed styles of every token utility, in light
    # and dark, and runs axe color-contrast on component-composition.md's Alert variants.
    {"name": "shadcn-theme", "project": "web", "next_build": True,
     "blocks": ["tailwind#1", "component-composition#2"],
     "place": {"tailwind#1": UTILS, "component-composition#2": {"path": "src/components/common/alert.tsx", "auto": WEB}},
     "external": [
        envelope(),
        {"doc": "ui/tailwind.md", "langs": ["css"], "prefix": "/* app/globals.css — written by", "path": "src/app/globals.css"},
        {"doc": "ui/tailwind.md", "langs": ["css"], "prefix": "/* app/globals.css (continued)", "path": "src/app/globals.css"},
        {"doc": "ui/shadcn.md", "langs": ["css"], "prefix": "/* app/globals.css — overrides", "path": "src/app/globals.css",
         "append": "/* HARNESS: .units/ is git-ignored, and Tailwind's automatic source detection skips ignored files */\n"
                   '@source "../";'},
     ],
     "shims": ["shadcn", "theme-app"], "compilerOptions": {"types": ["node"]},
     "playwright": {"config": "playwright.config.ts", "server": ["{bin}/next", "start", "-p", "{port}", "-H", "localhost"]}},
    # testing/msw.md + the UI test in test-case-traceability.md: the mocks, server and setup files are the pack's
    # own; the screens they render (UserList, CreateUserForm, OrderList) and the fixtures are app-level stubs.
    {"name": "msw", "project": "web", "blocks": [*[f"msw#{n}" for n in range(1, 8)], "test-case-traceability#1"],
     "external": [envelope("src/api/types.ts")], "shims": ["web-test"],
     "compilerOptions": {"types": ["vite/client"]},
     "auto": {**WEB, **VITEST, **RTL, **MSW, "PathParams": ("msw", "type"), "ReactDOM": ("react-dom/client", "default"),
              **named("../mocks/envelope", "ok", "page", "apiError"), **named("../test/render", "renderWithProviders"),
              **named("./UserList", "UserList"), **named("./CreateUserForm", "CreateUserForm"), **named("./OrderList", "OrderList"),
              **named("../mocks/fixtures", "userFixture", "order", "ordersHandler"), **named("../mocks/server", "server"),
              "CreateUserInput": ("../api/types", "type")},
     "vitest": ["src/features"], "vitest_setup": ["./src/test/setup.ts", "./src/test/jest-dom.ts"],
     "executed_blocks": ["msw#1", "msw#2", "msw#3", "msw#4", "msw#6", "test-case-traceability#1"],
     "place": {
        "msw#4": {"path": "src/features/UserList.test.tsx"},
        "msw#5": [{"path": "src/mocks/browser.ts", "until": "// src/main.tsx"},
                  {"path": "src/main.tsx", "from": "// src/main.tsx", "prelude": "declare function App(): React.JSX.Element;"}],
        "msw#6": {"path": "src/features/CreateUserForm.test.tsx"},
        "msw#7": frag("src/samples/response-helpers.ts", wrap="function"),
        "test-case-traceability#1": {"path": "src/features/OrderList.test.tsx"},
     }},
    # testing/playwright.md: the config and specs are the pack's; they run (system Chrome, both of the config's
    # projects) against shims/pw-support/server.mjs, a tiny stand-in for the deployed app at APP_BASE_URL.
    {"name": "playwright", "project": "web", "blocks": [f"playwright#{n}" for n in range(1, 10)],
     "external": [envelope("src/api/types.ts")], "shims": ["pw-support"], "compilerOptions": {"types": ["node"]},
     "auto": {**named("@playwright/test", "test", "expect"), "Page": ("@playwright/test", "type"),
              **named("./support", "signIn", "persona", "SESSION_COOKIE", "createNoteViaApi")},
     "playwright": {"config": "playwright.harness.config.ts", "server": "server.mjs",
                    # the seeded test users; "{random}" = a fresh password per run (nothing to commit or leak)
                    "env": {"E2E_BUYER_EMAIL": "buyer@example.com", "E2E_BUYER_PASSWORD": "{random}",
                            "E2E_ADMIN_EMAIL": "admin@example.com", "E2E_ADMIN_PASSWORD": "{random}"},
                    "junit": True},
     "executed_blocks": [f"playwright#{n}" for n in (1, 2, 4, 5, 7, 8, 9)],
     "place": {
        "playwright#3": frag("e2e/samples/locators.ts", wrap="function", prelude="declare const page: Page;"),
        "playwright#4": {"path": "e2e/auth.spec.ts"},
        "playwright#5": frag("e2e/assertions.spec.ts", wrap="custom",
                             open='test("harness: the assertions excerpt, on the dashboard", async ({ page }) => {\n  await page.goto("/dashboard");',
                             close="});"),
        "playwright#6": frag("e2e/network.sample.ts", wrap="async", prelude="declare const page: Page;"),
        "playwright#7": {"path": "e2e/a11y.spec.ts"},
        "playwright#8": {"path": "e2e/security.spec.ts"},
     }},
    # React Native: react-native-app-patterns.md's OrdersScreen + react-native-testing-library.md's Jest config,
    # MSW server/setup and tests, run with Jest on @react-native/jest-preset (RN 0.87). msw.md's envelope helpers
    # are the typed helpers the RNTL tests import. The screen's hook/components and LoginScreen are app-level stubs.
    *[rn_unit(variant) for variant in ("msw2", "msw3")],
    # Device tiers: TYPE-CHECK ONLY (no simulator, emulator, Detox server or Appium server is started).
    {"name": "detox", "project": "device", "blocks": ["detox#1", "detox#2"],
     "compilerOptions": {"types": ["detox", "jest", "node"], "lib": ["es2023"]}},
    {"name": "appium", "project": "device", "blocks": ["appium-mobile#1", "appium-mobile#2"],
     "compilerOptions": {"types": ["@wdio/globals/types", "node"], "lib": ["es2023"]},
     "place": {
        "appium-mobile#1": frag("test/capabilities.ts", wrap="none"),
        "appium-mobile#2": frag("test/specs/login.e2e.ts", wrap="async"),
     }},
]
