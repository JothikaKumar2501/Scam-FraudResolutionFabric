## UI Guide

Design
- Minimal, modern, neutral palette with a single accent.
- Rounded corners, soft shadows, generous spacing.
- Dark mode supported (next-themes) with smooth toggle.

Key Components
- `NavBar`: sticky top bar with blur and theme toggle.
- `Markdown`: safe markdown renderer (GFM). Use for agent outputs, SOP snippets.
- `ChatBubble`: message bubbles for assistant, user, and risk assessments.
- `Modal`: animated modal for details (e.g., XAI JSON). Use:

```tsx
const [open, setOpen] = useState(false)
<Modal open={open} onOpenChange={setOpen} title="Details">{children}</Modal>
```
- `Skeleton`: loading placeholders.

Usage
- Render `.md` strings from agents via `<Markdown>{content}</Markdown>`.
- For streaming chat, map `dialogue_history` to `ChatBubble` with role and badge.
- Use `Card` for sections; add subtle hover shadow.

Accessibility
- All inputs/buttons have focus styles; add `aria-label` where meaningful.
- Ensure sufficient contrast in both themes.

Performance
- Markdown is dynamically imported; heavy sections can be lazy loaded.
- Use Next.js `Image` for assets.


