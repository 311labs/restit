_run = []
_cleanup = []

def register_run(func):
    global _run
    if not func in _run:
        _run.append(func)

def register_cleanup(func):
    global _cleanup
    if not func in _cleanup:
        _cleanup.append(func)

def run():
    global _run
    global _cleanup
    for f in _run:
        f()
    for f in _cleanup:
        f()
    _run = []
    _cleanup = []
