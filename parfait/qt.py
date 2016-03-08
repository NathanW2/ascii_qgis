import os
import inspect

from PyQt4 import uic

def load_ui(name):
    if os.path.exists(name):
        uifile = name
    else:
        frame = inspect.stack()[1]
        filename = inspect.getfile(frame[0])
        uifile = os.path.join(os.path.dirname(filename), name)
        if not os.path.exists(uifile):
            uifile = os.path.join(os.path.dirname(filename), "ui", name)

    widget, base = uic.loadUiType(uifile)
    return widget, base
