---
name: weekly-sync
description: Sync selected Soongsil LMS weekly lecture files to the existing Google Drive 숭실대 / 3-2 course and week folders, skipping files already present and converting PowerPoint materials to PDF.
---

# Weekly LMS to Drive sync

Use the `ssu-lms` MCP and connected Google Drive tools. LMS files are staged temporarily and must be uploaded through Drive.

1. Check `auth_status`, then list term 50 courses and materials. If authentication fails, follow `auth-recovery/SKILL.md`, verify the restored session, and retry. If recovery fails, report that login is needed.
2. Process only courses and weeks the user requests. Find the existing Drive parent folder by name and reuse matching course folders; create only missing course or week folders. If multiple matches exist, ask which one to use.
3. For each material, list the destination week folder first. Compare filenames after Unicode NFC normalization. If the target filename already exists, skip it without staging. For `.ppt` and `.pptx`, compare and save the corresponding `.pdf` filename instead.
4. Stage missing material with `stage_material(course_id, content_id, week)`. For `.ppt` or `.pptx`, convert the staged file to PDF using LibreOffice in headless mode (`soffice --headless --convert-to pdf --outdir <staging-directory> <staged-file>`); verify the output exists and is a readable PDF before upload. Upload only the PDF, using the original basename with `.pdf`, to the same week folder. For other file types, upload the staged file as-is.
5. Verify the uploaded Drive metadata: name, parent folder, and byte size. Always call `delete_staged_material(staging_id)` after the attempt for the original staged file. If conversion created a PDF in the staging directory, delete that temporary PDF too (use its `lms-...pdf` staging filename). Clean up after failures as well.
6. Report uploaded, skipped, and failed counts with course/week names. Never call a staged or converted file an upload until Drive metadata confirms it. Do not save lecture files in `~/Downloads` or create a second Drive hierarchy.
