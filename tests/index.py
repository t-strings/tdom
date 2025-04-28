failed = False

from test import demo, viewdom_expressions, viewdom_static_string, viewdom_variables
for module in [demo, viewdom_expressions, viewdom_static_string, viewdom_variables]:
    print(f"\x1b[1m{module.__name__}\x1b[0m")
    for method in dir(module):
        if not method.startswith('test_'):
            continue
        print(f"  \x1b[3m{method}\x1b[0m")
        try:
            getattr(module, method)()
        except Exception as e:
            print(f"  \x1b[31m{e}\x1b[0m")
            failed = True

import js
body = js.document.body

if not failed:
    body.textContent = "OK"

body.classList.add("done")
