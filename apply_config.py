"""Adds the thinking settings to backend/app/core/config.py (run from the project root)."""
import pathlib, re, sys
p = pathlib.Path("backend/app/core/config.py")
s = p.read_text()
if "llm_thinking_mode" in s:
    sys.exit("Already applied - nothing to do.")
m = re.search(r"^([ \t]+)llm_timeout_seconds: float = [^\n]*\n", s, re.M)
if not m:
    sys.exit("Could not find the llm_timeout_seconds line; send me config.py.")
i = m.group(1)
add = (f"{i}llm_thinking_mode: str = \"auto\"  # auto | always | never\n"
       f"{i}llm_thinking_timeout_seconds: float = 75.0\n"
       f"{i}llm_thinking_max_tokens: int = 3000\n"
       f"{i}llm_max_tokens: int = 700\n")
p.write_text(s[:m.end()] + add + s[m.end():])
print("config.py patched.")
