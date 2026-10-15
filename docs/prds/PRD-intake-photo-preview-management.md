# Product Requirements Document (PRD): Intake Photo Preview Management & Individual Deletion

## 1. Executive Summary
Provide an intuitive, mobile-optimized photo management experience directly on the secondhand product intake form (`/intake/`).

Currently, when a sourcing assistant selects or captures photos on mobile, standard HTML `<input type="file" multiple>` handles the selection as an atomic, immutable batch. If the assistant uploads 4 photos and realizes that one is blurry, upside-down, or of the wrong product tag, they cannot remove only the flawed photo. Instead, clicking the upload zone or file picker replaces the entire batch, forcing them to re-select or re-photograph all items from scratch.

This feature introduces individual photo management in the live preview grid:
1. Each thumbnail preview card includes a prominent, accessible delete button ("✕") with a comfortable mobile touch target.
2. Tapping "✕" immediately removes that specific photo from memory and synchronizes the HTML `<input type="file">` via the modern standard `DataTransfer` Web API.
3. The preview grid re-indexes the remaining photos (`#1`, `#2`, ...), updates the photo count (`X / 10`), and updates the AI pre-flight identify trigger button state.
4. Assistants can also accumulate photos incrementally across multiple camera snaps without losing previously captured photos, capped at the 10-image maximum.

---

## 2. Problem Statement
1. **Frustrating All-or-Nothing Mobile Uploads:** In high-volume secondhand sourcing, assistants frequently take quick photos on their phones. If one photo out of five is unreadable or mistaken, replacing the whole selection wastes significant time.
2. **Lack of Individual Inspection & Pruning:** Assistants cannot easily verify and cull their photos before submitting to the server or triggering AI identification.
3. **Bandwidth & Storage Waste:** Without single-photo deletion, assistants either submit unnecessary/faulty photos (wasting mobile upload bandwidth and cloud storage) or abandon the draft to re-photograph everything.
4. **Desktop & Mobile Consistency:** The feature must feel native and responsive on both touchscreens (iPhone/Android, 360–390px) and desktop browsers with mouse/keyboard accessibility.

---

## 3. User Personas & Scenarios

### Persona 1: Field Sourcing Assistant (User A)
- **Device:** iPhone 14 / Android smartphone in a warehouse or secondhand flea market.
- **Scenario:** The assistant takes 3 photos of a vintage leather jacket: front view, care tag, and back. Looking at the thumbnails, they notice the care tag photo is completely blurry due to low lighting.
- **Workflow:**
  1. The assistant taps the "✕" button on thumbnail `#2` (the blurry tag).
  2. The blurry photo disappears with immediate visual feedback.
  3. The remaining photos automatically re-index to `#1` and `#2`.
  4. The assistant taps the dropzone camera picker, takes a new, crisp photo of the tag, which appends to the list as `#3`.
  5. The assistant proceeds to AI identification and form submission without losing work.

### Persona 2: Store Manager / Lister (User B)
- **Device:** Desktop PC / laptop creating manual inventory entries.
- **Scenario:** The manager drags 4 images from a desktop folder into the dropzone. One image belongs to a different product. The manager clicks the "✕" button on the unwanted image thumbnail, immediately pruning it prior to saving.

---

## 4. Scope & Technical Architecture

### 4.1 Client-Side File State & DataTransfer Synchronization
- **Internal State:** Maintain an in-memory array `selectedFiles: File[]` in `inventory/templates/inventory/intake.html`.
- **Synchronization Engine (`syncFileInput()`):**
  - Uses the standard HTML5 `DataTransfer` API:
    ```javascript
    function syncFileInput() {
      const dt = new DataTransfer();
      selectedFiles.forEach(file => dt.items.add(file));
      imageInput.files = dt.files;
      renderPreviews();
      updatePhotoCount();
      updateIdentifyButton();
    }
    ```
  - When `selectedFiles.length === 0`:
    - `imageInput.value = ''` resets the native input.
    - `#previewContainer` is hidden.
    - `#photoCount` displays `0 / 10 selected`.
    - `#identifyBtn` is disabled.
- **Cumulative / Incremental Selection:**
  - When the assistant selects additional files via the file input or camera picker, newly chosen files are appended to `selectedFiles` (validating max 10 images and max 10MB per file).
  - If a duplicate file (same name, size, lastModified) is selected, it is ignored to prevent accidental double-selection.

### 4.2 Interactive Thumbnail Preview Card Design
Each thumbnail rendered inside `#previewGrid` features:
```
┌──────────────────────────────┐
│ [#1]                    [✕]  │ <- Index badge (left) & Delete button (right)
│                              │
│                              │
│        [Image Preview]       │
│                              │
│                              │
└──────────────────────────────┘
```
- **Index Badge:** `#N` badge in top-left (`bg-black/60 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full`).
- **Delete Button ("✕"):**
  - Minimum 44×44px accessible touch target (via padding and relative container) conforming to WCAG 2.1 AA.
  - Visual pill: 28×28px circular button with red/rose accent (`bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white shadow-md`).
  - SVG icon: clean 14×14px cross icon (`stroke-width="2.5"`).
  - ARIA attributes: `type="button"`, `aria-label="{% trans 'Remove photo' %} #N"`, `title="{% trans 'Remove photo' %}"`.
  - Delete interaction: Stops propagation to prevent re-opening the file dialog, removes item at index `idx` from `selectedFiles`, and invokes `syncFileInput()`.

### 4.3 Form State Machine Protection
- During asynchronous operations (`formState === 'identifying'` or `'submitting'`):
  - All thumbnail delete buttons are locked (`pointer-events-none opacity-50 cursor-not-allowed`).
  - Dropzone is locked to prevent file mutation while AI vision or form POST is in-flight.
- When `formState === 'idle'`, delete buttons and dropzone are fully interactive.

---

## 5. Non-Functional Requirements
- **WCAG 2.1 AA Compliance:** Minimum 44×44px touch target for delete buttons, high contrast against dark/light image backgrounds, full keyboard focus states (`focus:ring-2 focus:ring-rose-500`).
- **Zero Heavy Dependencies:** Implemented in lightweight vanilla JavaScript (~40 lines of code) without third-party frameworks.
- **Universal Browser Compatibility:** Compatible with all modern mobile and desktop browsers supporting `DataTransfer` (iOS Safari 14.5+, Chrome, Edge, Firefox).
- **Backend Compatibility:** The server receives the standard `request.FILES.getlist('images')` with exactly the curated list of files, requiring zero backend schema or model changes.

---

## 6. Success Metrics & Acceptance Criteria
1. Selecting photos displays thumbnails with an accessible "✕" delete button on each image.
2. Clicking/tapping "✕" removes only that specific photo from the preview grid and from `imageInput.files`.
3. Remaining thumbnails dynamically re-index (`#1`, `#2`, ...) and update the counter (`X / 10 selected`).
4. Removing all photos hides the preview grid, resets the file input to empty, and disables the AI identify button.
5. Deleting photos while AI vision or form submission is in flight is strictly prevented.
6. Submitting the form uploads only the remaining, curated photos to the backend.
7. All automated unit, view, and real Chrome browser tests pass with 100% green.
