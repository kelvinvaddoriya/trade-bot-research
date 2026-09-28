import sys

if sys.argv[1:2] == ["watchdog"]:       # runs every minute, often while memory is short: no pandas (see watchdog.py)
    from .watchdog import main
else:
    from .cli import main

main()
