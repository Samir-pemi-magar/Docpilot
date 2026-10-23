"""Fix 1 for DocPilot: stop prose chunks being cut down when they contain a few lines with "|".
Run from the project root:  python3 apply_chat_fix.py
Edits backend/app/api/routes/chat.py in place (exact-match replace; refuses if the code differs)."""
import pathlib, sys
p = pathlib.Path("backend/app/api/routes/chat.py")
s = p.read_text()
old = "        if len(pipe_indexes) < 2:\n"
new = '''        non_empty_lines = [line for line in lines if line.strip()]
        # Treat a chunk as a table only when most of its lines are table rows.
        # Prose chunks often contain a couple of lines with "|" (document header,
        # page footer); treating those as tables dropped all the other text.
        if len(pipe_indexes) < 2 or len(pipe_indexes) < 0.5 * len(non_empty_lines):
'''
if "non_empty_lines" in s:
    sys.exit("Already applied - nothing to do.")
if s.count(old) != 1:
    sys.exit("Could not find the expected line exactly once; chat.py differs from the version I checked. Send me the function _build_retrieved_context.")
p.write_text(s.replace(old, new, 1))
print("chat.py patched.")
