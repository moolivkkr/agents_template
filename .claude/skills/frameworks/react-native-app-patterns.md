# React Native App Patterns — implementing screens for iOS + Android

How `mobile_developer` builds a React Native app that the pipeline can test and review. Platform
facts (versions, networking, permissions, build variants): `react-native.md`. Test contract (testIDs,
device tiers): `../testing/mobile-testing-strategy.md`.

> **Library status, verified 2026-09-29; re-check against the project's `package.json`.**
> - **Expo Router v56** (SDK 56, 2026-05-28) forked the React Navigation pieces it uses. In an Expo
>   Router app, navigation imports come from `expo-router` / `expo-router/react-navigation`, not
>   `@react-navigation/*`. A codemod exists: `npx expo-codemod sdk-56-expo-router-react-navigation-replace src`.
>   Apps that use React Navigation directly (no Expo Router) are unaffected.
> - **FlashList v2** is a New-Architecture-only rewrite with no size estimates (`estimatedItemSize` is gone).
> - **Reanimated 4** is New-Architecture-only and depends on `react-native-worklets`, which must be installed and configured.
> - The React Compiler is stable and opt-in in Expo (`"experiments": { "reactCompiler": true }`).
>   Follow the project's decision; don't enable it unilaterally.

---

## 1. Project layout

```
{{MOBILE_APP_DIR}}/
  app/                    # Expo Router: file-based routes (app/(tabs)/orders/[id].tsx)
  src/
    api/                  # generated types + typed client (one file per resource)
    features/<feature>/   # screens, hooks, components for one feature
    components/           # shared, presentational only
    lib/                  # storage, permissions, linking, env
  .maestro/               # device flows (written by mobile_test_agent)
```

- **Bare React Navigation**: `src/navigation/` holds typed stacks with a single `RootStackParamList`.
- Screens are thin. Data fetching lives in feature hooks (`useOrders()`), and presentational
  components take props. That keeps each screen's four states testable in RNTL without a device.
- **Monorepo with a web app**: share `src/api` types and validation schemas through a workspace
  package. Share **no UI components** with web unless the project decided on RN-Web.

## 2. Types and the API client (single source of truth)

- Generate TypeScript types from `docs/design/phases/N/specs/data-contracts.md` (same protocol as web:
  `../ui/type-generation-protocol.md`). Never hand-write a response type that already exists there.
- One typed client wraps `fetch`. It:
  - builds base URLs from env config: iOS simulator `http://localhost:PORT`, Android emulator
    `http://10.0.2.2:PORT`, and real hosts in release;
  - adds the bearer token from secure storage;
  - unwraps the `{ data, error, meta }` envelope exactly as `api-contracts.md` defines it;
  - maps 401 to a single refresh-or-logout path.
- Server state lives in **TanStack Query** (`../frameworks/tanstack-query.md`). Refetch on app focus
  through `focusManager` + `AppState`, and pause queries when offline through `onlineManager` +
  NetInfo. Only client-only UI state goes in local state or a small store.

## 3. Navigation and deep links

- Every route in the screen specs gets a typed route and a **linking entry**. Expo Router derives
  links from files; bare React Navigation needs an explicit `linking` config.
- Authenticated routes sit behind an auth gate that redirects to login and then **returns to the
  deep-linked target** (TC-MPLT deep-link-logged-out case).
- Android hardware back must do the right thing on every screen: close modals, and ask before
  discarding a dirty form (`usePreventRemove` / `beforeRemove`). Never exit the app from inside a flow.
- Universal Links / App Links need the associated-domains entitlement and `autoVerify` intent filters
  in native config (`app.json` for Expo). Hosting `apple-app-site-association` / `assetlinks.json`
  is a deploy task; list it in the progress report.

## 4. Screens: the four states and the testID contract

Every data screen renders **loading, error (with retry), empty (with next action), and data**, the
same rule as web. Every interactive element and every assertion target gets
`testID="<screen>.<element>"`, taken from the screen spec. The device tests select only by testID.

```tsx
export function OrdersScreen() {
  const { data, isPending, isError, refetch, isRefetching } = useOrders();
  if (isPending) return <OrdersSkeleton testID="orders.loading" />;
  if (isError)   return <ErrorState testID="orders.error" onRetry={refetch} />;
  if (data.length === 0) return <EmptyState testID="orders.empty" actionLabel="Create order" />;
  return (
    <FlashList
      testID="orders.list"
      data={data}
      keyExtractor={(o) => o.id}
      renderItem={({ item }) => <OrderRow order={item} testID={`orders.row.${item.id}`} />}
      onRefresh={refetch}
      refreshing={isRefetching}
    />
  );
}
```

## 5. Accessibility (built in, not bolted on)

- `Pressable`/touchables get `accessibilityRole="button"` (or `role="button"`) and a label that
  describes the action. Icon-only buttons must have a label. Pick one prop style (`accessibility*`
  or `role`/`aria-*`) per project and use it consistently.
- Touch targets are at least 44×44 pt / 48×48 dp; use `hitSlop` to enlarge small icons.
- Leave font scaling ON. Design layouts that wrap at the largest accessibility size.
  `allowFontScaling={false}` needs a spec'd reason.
- Group related text (`accessible` on the row container) so a screen reader reads one sentence, not five fragments.
- Announce async results that don't move focus (`AccessibilityInfo.announceForAccessibility`).

## 6. Forms and keyboard

- Validate with schemas derived from `data-contracts.md` request types (`../ui/form-validation-protocol.md`).
- Every field is visible above the keyboard on the smallest device: use `KeyboardAvoidingView`
  (iOS `padding`) or a keyboard-aware scroll view, and `keyboardShouldPersistTaps="handled"`.
- Set `returnKeyType` + `onSubmitEditing` to chain fields, and `textContentType` / `autoComplete`
  so the OS offers autofill and password managers.
- Disable submit while a request is in flight (no double submit), and show server-side field errors on their fields.

## 7. Platform integration

| Concern | Do | Never |
|---|---|---|
| Tokens / credentials | `expo-secure-store` or `react-native-keychain` (Keychain/Keystore) | AsyncStorage/MMKV for secrets |
| Permissions | Request at point of use; handle granted / denied / blocked; offer a Settings link when blocked; iOS usage string for each (`app.json` `ios.infoPlist` or `Info.plist`) | Request everything at launch; dead-end on denial |
| Network (E2E build) | Cleartext allowed only to `10.0.2.2` / localhost via network security config in the E2E/debug variant | `usesCleartextTraffic=true` or `NSAllowsArbitraryLoads` in release |
| Offline | Detect with NetInfo, render an offline state, queue or disable mutations visibly | Spinners that never end |
| Lifecycle | Persist in-progress drafts; restore navigation state after Android process death where the spec requires it | Assume the process survives backgrounding |
| Secrets in bundle | Only public config in `extra`/env | API keys with write scope in JS |
| Safe areas | `react-native-safe-area-context` insets on every screen edge | Hard-coded status-bar heights |

## 8. Performance defaults

- Long lists use **FlashList** (v2 on the New Architecture) or `FlatList` with stable `keyExtractor`.
  Never `ScrollView` + `.map()` over unbounded data.
- Images: `expo-image` (or an equivalent cache-backed component) with explicit dimensions.
- Animations: Reanimated 4 runs on the UI thread and needs `react-native-worklets` set up. Avoid
  JS-driven `setInterval` animations; they also block Detox's idle sync.
- Memoize list rows. Keep work out of render. Measure with reassure for screens that have an NFR-PERF target.

## 9. Native changes

- **Expo (CNG)**: native config goes in `app.json` / `app.config.ts` and config plugins. Run
  `npx expo prebuild --clean` to verify it generates. Never hand-edit a generated `ios/` / `android/`.
- **Bare**: native edits are reviewed like source. Run `pod install` after adding a native dependency.
  Record every new native dependency in the progress report, because it changes the build.

## 10. Verify before hand-off

1. `npx tsc --noEmit` passes, and lint passes (with `eslint-plugin-react-native-a11y` if configured).
2. `npx jest` passes. The existing tests still pass; new tests belong to `mobile_test_agent`.
3. Both platforms build: an iOS simulator build (macOS only) and an Android emulator build. If the
   host can't build iOS, say so explicitly. It is not a silent pass.
4. Cold launch on one simulator/emulator reaches the first screen with no red box.
