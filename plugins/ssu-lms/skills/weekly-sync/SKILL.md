---
name: weekly-sync
description: Sync user-selected Soongsil LMS weekly lecture files to matching Google Drive course and week folders, skipping duplicates.
---

# Weekly LMS to Drive sync

Use the `ssu-lms` MCP and the connected Google Drive tools. The LMS MCP stages files temporarily; it does not upload to Drive by itself.

1. Check `auth_status`, then list term 50 courses and each course's materials. If authentication fails, follow the sibling `auth-recovery/SKILL.md`: use LearningX first, verify the restored session, and retry the interrupted read. If recovery fails, report that login is needed; do not claim the run succeeded.
2. Process only courses and weeks the user requests. Find the existing `숭실대 / 3-2` Drive folder by name and reuse matching course folders; create only missing course or week folders. If multiple matching parent folders exist, ask which one to use.
3. For each LMS material, list the target week folder first. Compare filenames after Unicode NFC normalization. If the name is already present, skip it without staging or uploading. Treat each course/week separately.
4. For a missing file, call `stage_material(course_id, content_id, week)`. For PowerPoint materials, convert the staged file to PDF with LibreOffice in headless mode and verify the output is a readable PDF; upload only the PDF. Upload other staged files as-is. Verify the uploaded Drive file's name, parent, and byte size with metadata readback. Always call `delete_staged_material(staging_id)` after the attempt, including if the upload fails, and remove any converted temporary PDF.
5. Report counts of uploaded, skipped, and failed files with affected course/week names. Never call a staged file a Drive upload. Do not save lecture files in `~/Downloads` or create a second Drive hierarchy.

The LMS may invalidate its own login session. First try the normal LearningX authentication recovery; ask for browser login only if it fails or the app is unavailable. Never bypass LMS authentication.
