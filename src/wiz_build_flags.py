"""Build flags. build.py --release writes RELEASE = True for the release exe
and puts this file back afterwards. Keep it False in the repository.

RELEASE turns off the developer files: untranslated_strings.log,
wiz_party_debug.log, monster_seen.log, wiz_maze_dump.bin and the F8 memory dump.
wiz_overlay_error.log is kept: it is written only when something fails.
"""
RELEASE = False
