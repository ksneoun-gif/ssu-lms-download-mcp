---
name: weekly-sync
description: Sync Soongsil LMS weekly lecture files to the user's existing Google Drive 숭실대 / 3-2 course and week folders, skipping files already present.
---

# Weekly LMS to Drive sync

Use the `ssu-lms` MCP and the connected Google Drive tools. The LMS MCP stages files temporarily; it does not upload to Drive by itself.

1. Check `auth_status`, then list term 50 courses and each course's materials. If authentication fails, follow the sibling `auth-recovery/SKILL.md`: use LearningX first, verify the restored session, and retry the interrupted read. If recovery fails, report that login is needed; do not claim the run succeeded.
2. Process only courses and weeks the user requests. Find the existing Drive parent folder by name and reuse matching course folders; create only missing course or week folders. If multiple matches exist, ask which one to use.
3. For each LMS material, list the target week folder first. Compare filenames after Unicode NFC normalization. If the name is already present, skip it without staging or uploading. Treat each course/week separately.
4. For a missing file, call `stage_material(course_id, content_id, week)`, then Google Drive `upload_file` with its absolute `path`, `filename`, and the week folder ID. Verify the uploaded Drive file's name, parent, and byte size with metadata readback. Always call `delete_staged_material(staging_id)` after the attempt, including if the upload fails.
5. Report counts of uploaded, skipped, and failed files with affected course/week names. Never call a staged file a Drive upload. Do not save lecture files in `~/Downloads` or create a second Drive hierarchy.

The LMS may invalidate its own login session. First try the normal LearningX authentication recovery; ask for browser login only if it fails or the app is unavailable. Never bypass LMS authentication.
