#!/usr/bin/env python
import curses
import curses.panel
import os
import sys
import json
from collections import namedtuple
from curses.textpad import Textbox, rectangle
from qgis.core import QgsMapLayerRegistry, QgsProject, QgsMapRendererParallelJob, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsRectangle, QgsPoint, QgsMapSettings
from qgis.gui import QgsMapCanvas, QgsLayerTreeMapCanvasBridge
from PyQt4.QtCore import QSize
from PyQt4.QtGui import QColor, QImage
from parfait import QGIS, projects

import logging
logging.basicConfig(filename='render.log',level=logging.DEBUG)

# Bunch of good old globals......for now
scr = None
project = None
status = None
edit = None
pad = None
legendwindow = None
ascii_mode_enabled = False
aboutwindow = None
mapwindow = None
canvas = None
lastcmd = ''

class QuestionTypes:
    QUESTION = 3
    QUESTIOnERROR = 4

QAndA = namedtuple("QAndA", ['question', 'type'])

TOPBORDER = 4
BOTTOMBORDER = 2

config = {}


class AboutWindow():
    def __init__(self):
        y, x = scr.getmaxyx()
        self.infowin = curses.newwin(y / 2, x / 2, y / 4, x / 4)
        self.infopanel = curses.panel.new_panel(self.infowin)

    def display(self, title, content):
        curses.curs_set(0)
        self.infowin.clear()
        y, x = self.infowin.getmaxyx()
        self.infowin.bkgd(" ", curses.color_pair(6))
        self.infowin.box()
        self.infowin.addstr(0, 0, title, curses.A_UNDERLINE | curses.A_BOLD)
        for count, line in enumerate(content.split('\n'), start=1):
            try:
                self.infowin.addstr(count, 1, line)
            except:
                pass

        self.infopanel.show()
        curses.panel.update_panels()
        curses.doupdate()
        while self.infowin.getch() != 27:
            pass
        curses.curs_set(1)

    def hide(self):
        self.infopanel.hide()
        curses.panel.update_panels()
        curses.doupdate()


class Legend():
    def __init__(self):
        y, x = scr.getmaxyx()
        self.win = curses.newwin(y - TOPBORDER, 30, BOTTOMBORDER, 0)

    def render_legend(self):
        def render_item(node, row, col):
            nodestr = str(node)

            if isinstance(node, QgsLayerTreeLayer):
                nodestr = "(L) " + node.layerName()
            if isinstance(node, QgsLayerTreeGroup):
                nodestr = "(G) " + node.name()

            state = "[ ]"
            if node.isVisible():
                state = "[x]"

            expanded = '+'
            if node.isExpanded():
                expanded = '-'

            name = "{} {} {}".format(expanded, state, nodestr)

            y, maxsize = self.win.getmaxyx()
            logging.info(name)
            if len(name) > maxsize - 2:
                name = name[:maxsize - 2]
                logging.info(name)

            self.win.addstr(row, col, name)

        def render_nodes(root, row, col):
            for node in root.children():
                row += 1
                render_item(node, row, col)

        size = 30
        self.win.clear()
        self.win.box()
        self.win.addstr(0, size / 2, "Layers")
        # Only top level for now
        root = QgsProject.instance().layerTreeRoot()
        row = 1
        col = 1
        render_nodes(root, row, col)
        self.win.refresh()

def show_commands():
    cmds = "\n".join(commands)
    aboutwindow.display(title="Commands - ESC to close", content=cmds)
    aboutwindow.hide()
    mapwindow.render_map()
    legendwindow.render_legend()
    edit.clear()
    edit.refresh()

def show_help():
    abouttxt = """

    YAY ASCII!

    Type commands into the bottom
     to take action.

    Try something like open-project
    which can take a name
    of a project or a path.
    (Config the paths in ascii_qgis.config

    Once a project is loaded you can
    use these to move the map around

    CTRL + UP - Pan Up
    CTRL + DOWN - Pan Down
    CTRL + LEFT - Pan Left
    CTRL + RIGHT - Pan Right

    CTRL + PAGE UP - Zoom In
    CTRL + PAGE DOWN - Zoom Out

    """
    aboutwindow.display(title="Help - ESC to close", content=abouttxt)
    aboutwindow.hide()
    mapwindow.render_map()
    legendwindow.render_legend()
    edit.clear()
    edit.refresh()

def show_about():
    abouttxt = """
    > What the heck is this?
    A ASCII map thingo for QGIS projects

    > Why did you make this?
    Because........ I can

    > What commands can I use?
    Command-list to see

    > Does this really have any use?
    Maybe...maybe not

    > Really?
    Yes indeed because ASCII!
    """
    aboutwindow.display(title="FAQ - ESC to close", content=abouttxt)
    aboutwindow.hide()
    mapwindow.render_map()
    legendwindow.render_legend()
    edit.clear()
    edit.refresh()

def _exit():
    curses.endwin()
    sys.exit()

def _resolve_project_path(name):
    for path in config['paths']:
        if not name.endswith(".qgs"):
            name = name + ".qgs"

        fullpath = os.path.join(path, name)
        if os.path.exists(fullpath):
            return fullpath
    return None


def _open_project(fullpath):
    global project
    project = projects.open_project(fullpath)


def open_project():
    project = yield QAndA(question="Which project to open?",type=QuestionTypes.QUESTION)
    fullpath = _resolve_project_path(project)
    while not _resolve_project_path(project):
        project = yield QAndA(question="Couldn't find project {}. Check name".format(project), type=QuestionTypes.QUESTIOnERROR)
        fullpath = _resolve_project_path(project)

    answer = yield QAndA(question="Really load ({}) | Y/N ".format(fullpath),type=QuestionTypes.QUESTION)
    while not answer or answer[0].upper() not in ['Y', 'N']:
        answer = yield QAndA(question="Really load ({}) | Y/N ".format(fullpath),type=QuestionTypes.QUESTIOnERROR)

    if answer[0].upper() == "Y":
        _open_project(fullpath)
        legendwindow.render_legend()
        mapwindow.render_map()

def ascii_mode():
    answer = yield QAndA("Enable ascii rendering mode? Y/N", type=QuestionTypes.QUESTION)
    while not answer or answer[0].upper() not in ['Y', 'N']:
        answer = yield QAndA("Enable ascii rendering mode? Y/N", type=QuestionTypes.QUESTION)

    global ascii_mode_enabled
    if answer.upper() == "Y":
        ascii_mode_enabled = True
    else:
        ascii_mode_enabled = False
    mapwindow.render_map()

def zoom_out():
    factor = yield QAndA("By how much?", type=QuestionTypes.QUESTION)
    mapwindow.zoom_out(float(factor))

def zoom_in():
    factor = yield QAndA("By how much?", type=QuestionTypes.QUESTION)
    mapwindow.zoom_in(float(factor))


commands = {
    "open-project": open_project,
    "exit": _exit,
    "quit": _exit,
    "?": show_help,
    "help": show_help,
    "about": show_about,
    "faq": show_about,
    "command-list": show_commands,
    "zoom-out": zoom_out,
    "zoom-in": zoom_in,
    "ascii-map-mode": ascii_mode,
}


def get_pixel_value(pixels, x, y):
    if ascii_mode_enabled:
        color = "MNHQ$OC?7>!:-;. "
    else:
        color = "" * 16
    rgba = QColor(pixels.pixel(x, y))
    rgb = rgba.red(), rgba.green(), rgba.blue()
    index = int(sum(rgb) / 3.0 / 256.0 * 16)
    pair = curses.color_pair(index + 10)
    if ascii_mode_enabled:
        pair = 1

    try:
        return color[index], pair
    except IndexError:
        return " ", pair


class Map():
    def __init__(self):
        y, x = scr.getmaxyx()
        self.mapwin = curses.newwin(y - TOPBORDER, x - 30, BOTTOMBORDER, 30)
        self.settings = None

    def render_map(self):
        y, x = scr.getmaxyx()
        x -= 30

        self.mapwin.clear()
        self.mapwin.box()
        self.mapwin.addstr(0, x / 2, "Map", curses.A_BOLD)

        height, width = self.mapwin.getmaxyx()
        # Only render the image if we have a open project
        if project:
            img = self.render_qgis_map()
            for row in range(1, height - 1):
                for col in range(1, width - 1):
                    value, color = get_pixel_value(img, col, row)
                    # + 10 is the map color pair offset
                    # Finding a closer colour match would be nicer
                    self.mapwin.addstr(row, col, value, color)
        self.mapwin.refresh()

    def render_qgis_map(self):
        logging.info("Rendering QGIS map")
        # Gross. Fix me
        if not self.settings and project:
            self.settings = project.map_settings

        # TODO We should only get visible layers here but this will do for now
        self.settings.setLayers(QgsMapLayerRegistry.instance().mapLayers().keys())
        self.settings.setFlags(self.settings.flags() ^ QgsMapSettings.Antialiasing)
        logging.info(self.settings.flags())
        logging.info(self.settings.testFlag(QgsMapSettings.Antialiasing))
        height, width = self.mapwin.getmaxyx()
        logging.info("Setting output size to {}, {}".format(width, height))
        self.settings.setOutputSize(QSize(width, height))
        job = QgsMapRendererParallelJob(self.settings)
        job.start()
        job.waitForFinished()
        image = job.renderedImage()
        logging.info("Saving rendered image for checks...")
        image.save(r"F:\dev\qgis-term\render.jpg")
        return image

    def zoom_out(self, factor):
        if not self.settings:
            return
        extent = self.settings.extent()
        extent.scale(float(factor), None)
        self.settings.setExtent(extent)
        self.render_map()

    def zoom_in(self, factor):
        if not self.settings:
            return
        extent = self.settings.extent()
        extent.scale(1 / float(factor), None)
        self.settings.setExtent(extent)
        self.render_map()

    def pan(self, direction):
        if not self.settings:
            return

        def setCenter(point):
            x, y = point.x(), point.y()
            rect = QgsRectangle(x - extent.width() / 2.0, y - extent.height() / 2.0,
                                x + extent.width() / 2.0, y + extent.height() / 2.0)
            self.settings.setExtent(rect)
            self.render_map()

        extent = self.settings.visibleExtent()
        dx = abs(extent.width() / 4)
        dy = abs(extent.height() / 4)
        extent = self.settings.extent()
        center = extent.center()

        if direction == "up":
            newpoint = QgsPoint(center.x() + 0, center.y() + dy)
            setCenter(newpoint)
        if direction == "down":
            newpoint = QgsPoint(center.x() - 0, center.y() - dy)
            setCenter(newpoint)
        if direction == "left":
            newpoint = QgsPoint(center.x() - dx, center.y() - 0)
            setCenter(newpoint)
        if direction == "right":
            newpoint = QgsPoint(center.x() + dx, center.y() + 0)
            setCenter(newpoint)

if hasattr(curses, "CTL_UP"):
    UP = curses.CTL_UP
    DOWN = curses.CTL_DOWN
    LEFT = curses.CTL_LEFT
    RIGHT = curses.CTL_RIGHT
    PAGEUP = curses.CTL_PGUP
    PAGEDOWN = curses.CTL_PGDN
else:
    UP = 566
    DOWN = 525
    LEFT = 545
    RIGHT = 560
    PAGEUP = 555
    PAGEDOWN = 550

def handle_key_event(event):
    # TAB
    logging.info("Key Event:{}".format(event))
    if event == curses.KEY_UP:
        edit.clear()
        edit.addstr(0,0, lastcmd)
        edit.refresh()

    if event == UP:
        mapwindow.pan("up")
    if event == DOWN:
        mapwindow.pan("down")
    if event == LEFT:
        mapwindow.pan("left")
    if event == RIGHT:
        mapwindow.pan("right")

    if event == PAGEDOWN:
        mapwindow.zoom_out(5)

    if event == PAGEUP:
        mapwindow.zoom_in(5)

    if event == 9:
        logging.info("Calling auto complete on TAB key")
        data = pad.gather().strip()
        cmds = {key[:len(data)]: key for key in commands.keys()}
        logging.info("Options are")
        for cmd, fullname in cmds.iteritems():
            if cmd == data:
                logging.info("Grabbed the first match which was {}".format(fullname))
                edit.clear()
                edit.addstr(0, 0, fullname)
                edit.refresh()
                break
    return event


def update_cmd_status(message, color=None):
    if not color:
        color = curses.color_pair(1)
    status.clear()
    try:
        status.addstr(0, 0, message, color)
        status.refresh()
    except:
        pass

colors = {
}

def init_colors():
    """
    Init the colors for the screen
    """
    curses.use_default_colors()

    # Colors we use for messages, etc
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(7, curses.COLOR_RED, curses.COLOR_BLACK)
    colors['white'] = curses.color_pair(1)
    colors['green'] = curses.color_pair(2)
    colors['cyan'] = curses.color_pair(3)
    colors['yellow'] = curses.color_pair(4)
    colors['green-black'] = curses.color_pair(5)
    colors['black-white'] = curses.color_pair(6)
    colors['red'] = curses.color_pair(7)

    # Allocate colour ranges here for the ma display.
    maprange = 10
    for i in range(curses.COLORS - maprange):
        curses.init_pair(i + maprange, 0, i)


def main(screen):
    """
    Main entry point
    :param screen:
    :return:
    """
    logging.info("Supports color: {}".format(curses.can_change_color()))
    logging.info("Colors: {}".format(curses.COLORS))
    logging.info("Color Pairs: {}".format(curses.COLOR_PAIRS))
    logging.info("Loading config")
    with open("ascii_qgis.config") as f:
        global config
        config = json.load(f)

    entercommandstr = "Enter command. TAB for auto complete. (command-list for command help or ? for general help)"

    init_colors()

    screen.refresh()

    y, x = screen.getmaxyx()

    global scr, edit, status, pad, aboutwindow, legendwindow, mapwindow
    scr = screen
    edit = curses.newwin(1, x, y - 1, 0)
    status = curses.newwin(1, x, y - 2, 0)
    pad = Textbox(edit, insert_mode=True)
    mapwindow = Map()
    legendwindow = Legend()
    aboutwindow = AboutWindow()

    legendwindow.render_legend()
    mapwindow.render_map()

    screen.addstr(0, 0, "ASCII")
    screen.addstr(0, 5, " QGIS Enterprise", curses.color_pair(4))
    screen.refresh()

    update_cmd_status(entercommandstr)

    if config.get('showhelp', True):
        show_help()

    # Main event loop
    while True:
        message = pad.edit(validate=handle_key_event).strip()
        try:
            cmd = commands[message]
        except KeyError:
            update_cmd_status("Unknown command: {}".format(message), colors['red'])
            continue

        global lastcmd
        lastcmd = message

        func = cmd()
        if not func:
            update_cmd_status(entercommandstr)
            continue

        try:
            qanda = func.send(None)
            while True:
                edit.clear()
                update_cmd_status(qanda.question, color=curses.color_pair(qanda.type))
                message = pad.edit(validate=handle_key_event).strip()
                qanda = func.send(message)
        except StopIteration:
            edit.clear()
            edit.refresh()
            update_cmd_status(entercommandstr)

app = QGIS.init(guienabled=False)

if __name__ == "__main__":
    logging.info("Staring QGIS ASCII :)")
    logging.info("ASCII QGIS because we can")
    curses.wrapper(main)
