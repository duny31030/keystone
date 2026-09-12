"""支持 `python3 -m keystone.hook <event>` 调用方式。"""

import sys

from keystone.hook.cli import main

sys.exit(main())
