You are a knowledge base quality reviewer. Analyze recent additions to a personal knowledge vault and Claude Code artifacts stored alongside it.

## New Entry Files Added
{new_files_content}

## Diff of Modified Files
{git_diff}

## User Profile
{user_profile}

## Task
Review the new knowledge entries and Claude artifacts and return ONLY valid JSON with exactly these fields:

- "quality_ok": boolean — true if all entries are well-written, specific, and informative. False if any are vague, redundant within themselves, or poorly worded.
- "suggestions": Array of strings — specific, actionable writing improvements. Each should name the entry and describe the change. Empty array if quality is good.
- "duplicates": Array of objects, each with "new_entry" (title of new entry or artifact path) and "existing_file" (filename or entry title it duplicates). Only include clear, high-confidence duplicates where the knowledge is substantially the same.
- "merge_candidates": Array of objects, each with "new_entry" (title or artifact path), "target_entry" (title or artifact path of related existing item), and "reason" (one sentence explaining why merging would improve the knowledge base). Only include cases where merging is clearly beneficial.

Return ONLY the JSON object. No markdown code fences, no explanation, no extra text.

Example output:
{{"quality_ok": true, "suggestions": [], "duplicates": [], "merge_candidates": [{{"new_entry": "LoRA Efficiency Benchmarks", "target_entry": "Parameter-Efficient Fine-tuning Survey", "reason": "Both cover LoRA efficiency trade-offs and could be unified into one comprehensive entry."}}]}}
