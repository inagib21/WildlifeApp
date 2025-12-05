# Keyboard Shortcuts

This document lists all available keyboard shortcuts in the Wildlife Camera System application.

## Navigation Shortcuts (Double-Key Sequences)

All navigation shortcuts use **double-key sequences** - press the same key twice quickly (within 500ms):

| Shortcut | Action | Description |
|----------|--------|-------------|
| `DD` (double-press D) | Go to Detections | Navigate to the Detections page |
| `CC` (double-press C) | Go to Cameras | Navigate to the Cameras page |
| `AA` (double-press A) | Go to Analytics | Navigate to the Analytics page |
| `GG` (double-press G) | Go to Dashboard | Navigate to the Dashboard/Home page |
| `B` | Go Back | Navigate back in browser history |
| `F` | Go Forward | Navigate forward in browser history |

## Search & Focus

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+K` (or `Cmd+K` on Mac) | Focus Search | Focus the search input field (if available on the current page) |

## General Actions

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+R` (or `Cmd+R` on Mac) | Refresh Page | Reload the current page |

## Help

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Shift+?` | Show Help | Display a toast notification with available keyboard shortcuts |
| `Ctrl+Shift+?` | Open Documentation | Open the full keyboard shortcuts documentation |

## How Double-Key Sequences Work

Double-key sequences are designed for power users who want fast, intentional navigation:

1. **Press the same key twice quickly** (within 500ms)
2. The first press starts the timer
3. If you press the same key again within 500ms, the action triggers
4. If you press a different key or wait too long, nothing happens

**Examples:**
- Press `D` twice quickly → Navigate to Detections
- Press `G` twice quickly → Navigate to Dashboard
- Press `C` twice quickly → Navigate to Cameras

This design prevents accidental navigation while typing, as single key presses won't trigger any actions.

## Notes

- **No Single-Key Shortcuts**: All navigation shortcuts require double-key sequences to prevent accidental triggers while typing.

- **Input Fields**: Keyboard shortcuts are automatically disabled when typing in input fields, text areas, or any content-editable elements. This prevents accidental navigation while searching or entering data.

- **Modifier Keys**: Shortcuts that use modifier keys (Ctrl, Cmd, Shift) will still work even when focused in input fields. This allows you to use `Ctrl+K` to focus search from anywhere.

- **Double-Key Timing**: Double-key sequences must be pressed within 500ms of each other. This timing is optimized for fast typing while preventing accidental triggers.

- **Browser Compatibility**: 
  - On Windows/Linux: Use `Ctrl` key
  - On Mac: Use `Cmd` key (automatically handled)

## Usage Tips

1. **Quick Navigation**: Use double-key sequences (`DD`, `CC`, `AA`, `GG`) to quickly navigate between main sections of the application.

2. **Intentional Actions**: The double-key requirement ensures you intentionally want to navigate, preventing accidents while typing.

3. **Search Focus**: Press `Ctrl+K` (or `Cmd+K`) to quickly focus the search box on any page that has one.

4. **Help**: Press `Shift+?` to see a reminder of all available shortcuts, or `Ctrl+Shift+?` to open the full documentation.

5. **Safe Typing**: You can safely type in search boxes and input fields without worrying about triggering navigation shortcuts. Single key presses will never trigger navigation.

6. **Page Refresh**: Use `Ctrl+R` to quickly refresh the current page if data seems stale.

## Implementation Details

Keyboard shortcuts are implemented in:
- `wildlife-app/hooks/use-keyboard-shortcuts.ts` - Core shortcut handling logic with double-key sequence support
- `wildlife-app/components/keyboard-shortcuts-provider.tsx` - Provider component that enables shortcuts app-wide

The shortcuts are active throughout the application and are automatically enabled when the app loads.

## Shortcut Reference Card

**Quick Reference:**
- `DD` → Detections
- `CC` → Cameras  
- `AA` → Analytics
- `GG` → Dashboard
- `Ctrl+K` → Focus Search
- `Ctrl+R` → Refresh
- `Shift+?` → Help
