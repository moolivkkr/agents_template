# Page Archetype: Settings Page

## When to Use
Any configuration screen with tabbed sections: user settings, project settings, org admin.

## Component Tree — Desktop (1280px)
```
div.space-y-6
├── PageHeader
│   ├── h1.text-3xl.font-bold.tracking-tight → "Settings"
│   └── p.text-muted-foreground → "Manage your account preferences."
│
├── Tabs(defaultValue="profile")
│   ├── TabsList.grid.grid-cols-4 (or inline flex)
│   │   ├── TabsTrigger → "Profile"
│   │   ├── TabsTrigger → "Notifications"
│   │   ├── TabsTrigger → "Security"
│   │   └── TabsTrigger → "Billing"
│   │
│   ├── TabsContent(profile)
│   │   └── Card
│   │       ├── CardHeader
│   │       │   ├── CardTitle → "Profile"
│   │       │   └── CardDescription → "Update your personal information."
│   │       └── CardContent
│   │           └── Form(profileForm)
│   │               └── form.space-y-6
│   │                   ├── div.flex.items-center.gap-6
│   │                   │   ├── Avatar(lg) > AvatarImage + AvatarFallback
│   │                   │   └── Button(outline) → "Change avatar"
│   │                   ├── div.grid.gap-4.sm:grid-cols-2
│   │                   │   ├── FormField(name) > Input
│   │                   │   └── FormField(email) > Input(type=email)
│   │                   ├── FormField(bio) > Textarea
│   │                   └── Button(type=submit) → "Save profile"
│   │
│   ├── TabsContent(notifications)
│   │   └── Card
│   │       ├── CardHeader > CardTitle + CardDescription
│   │       └── CardContent
│   │           └── Form(notificationForm)
│   │               └── div.space-y-4
│   │                   └── NotificationToggle (×N)
│   │                       └── div.flex.items-center.justify-between.rounded-lg.border.p-4
│   │                           ├── div
│   │                           │   ├── p.font-medium → "Email notifications"
│   │                           │   └── p.text-sm.text-muted-foreground → description
│   │                           └── Switch
│   │
│   ├── TabsContent(security)
│   │   └── Card
│   │       ├── CardHeader > CardTitle + CardDescription
│   │       └── CardContent
│   │           └── Form(securityForm)
│   │               └── form.space-y-6
│   │                   ├── FormField(currentPassword) > Input(type=password)
│   │                   ├── FormField(newPassword) > Input(type=password)
│   │                   ├── FormField(confirmPassword) > Input(type=password)
│   │                   ├── Separator
│   │                   ├── div.flex.items-center.justify-between
│   │                   │   ├── div > label + description for 2FA
│   │                   │   └── Switch → enable/disable 2FA
│   │                   └── Button(type=submit) → "Update security"
│   │
│   └── TabsContent(billing)
│       └── Card > billing info + plan selection
```

## Component Tree — Mobile (375px)
- TabsList: scrollable horizontal (`overflow-x-auto`) or Select dropdown
- Form grids: single column
- Save buttons: full-width

## Data Flow
```tsx
// Each tab loads its OWN data independently
const profile = useQuery(settingsQueries.profile());
const notifications = useQuery(settingsQueries.notifications());
const security = useQuery(settingsQueries.security());

// Each tab has its OWN form + submit
const profileForm = useForm({ resolver: zodResolver(profileSchema), values: profile.data });
const notifForm = useForm({ resolver: zodResolver(notifSchema), values: notifications.data });

// Per-section save (NOT page-level save)
async function onSaveProfile(data) {
  await updateProfile.mutateAsync(data);
  toast.success("Profile updated");
}
```

Key pattern: **each tab is independent** — own query, own form, own submit, own toast. No page-level save button.

## 4 States (per tab, NOT per page)

### Loading (per tab)
Show skeleton ONLY for the active tab. Inactive tabs don't load until selected.
```tsx
<TabsContent value="profile">
  {profile.isLoading ? <FormSkeleton fields={4} /> : <ProfileForm data={profile.data} />}
</TabsContent>
```

### Empty
Settings pages are never truly empty — show default values or "not set" placeholders.

### Error (per tab)
- Failed tab shows error + retry inline
- Other tabs unaffected
- "Failed to load profile settings" + Retry button

### Success (per section)
- `toast.success("Profile updated")` — per section, not per page
- Form stays visible with updated values (no redirect)

## Tab URL State
```tsx
// Persist active tab in URL for deep linking
const [tab, setTab] = useQueryState("tab", parseAsString.withDefault("profile"));
<Tabs value={tab} onValueChange={setTab}>
```
