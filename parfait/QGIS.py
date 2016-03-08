import sys
from qgis.core import QgsApplication


def init(args=None, guienabled=True, configpath=None, sysexit=True):
    """
    Create a new QGIS Qt application.

    You should use this before creating any Qt widgets or QGIS objects for
    your custom QGIS based application.

    usage:
        from wrappers import QGIS

        QGIS.init()

    args - args passed to the underlying QApplication.
    guienabled - True by default will create a QApplication with a GUI. Pass
                 False if you wish to create no GUI based app, e.g a server app.
    configpath - Custom config path QGIS will use to load settings.
    sysexit - Call sys.exit on app exit. True by default.
    """
    if not args:
        args = []
    if not configpath:
        configpath = ''
    app = QgsApplication(args, guienabled, configpath)
    QgsApplication.initQgis()
    return app
