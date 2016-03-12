#!/usr/bin/env python
import time
import curses
import curses.panel
import os
import sys
import json
from collections import namedtuple
from curses.textpad import Textbox, rectangle
from qgis.core import QgsMapLayerRegistry, QgsProject, QgsMapRendererParallelJob, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsRectangle, QgsPoint, QgsMapSettings, \
    QgsMapLayer, QGis
from qgis.gui import QgsMapCanvas, QgsLayerTreeMapCanvasBridge
from PyQt4.QtCore import QSize, Qt
from PyQt4.QtGui import QColor, QImage
from parfait import QGIS, projects

import logging
logging.basicConfig(filename='render.log', level=logging.DEBUG)

# Bunch of good old globals......for now
scr = None
project = None
pad = None
legendwindow = None
color_mode_enabled = True
ascii_mode_enabled = False
aboutwindow = None
modeline = None
mapwindow = None
canvas = None

layercolormapping = {}
colors = {}

config = {}
commands = {}

TOPBORDER = 5
BOTTOMBORDER = 2

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

codes = [
    '@', # Point
    '.', # Line
    '#', # Polygon
    ' ', # Unsupported
    ' ' # Unknown
]

def command(names=None, *args, **kwargs):
    def escape_name(funcname):
        """
        Escape the name of the given function.
        """
        funcname = funcname.replace("_", "-")
        funcname = funcname.replace(" ", "-")
        return funcname.lower()

    if not names:
        names = []
    def _command(func):
        name = escape_name(func.__name__)
        commands[name] = func
        for name in names:
            commands[name] = func
        return func
    return _command


class QAndA:
    QUESTION = 3
    QUESTIOnERROR = 4

    def __init__(self, question, type=QUESTION, completions=None):
        self.question = question
        self.type = type
        if not completions:
            completions = []
        self.completions = completions


@command(names=['command-list'])
def show_commands():
    cmds = "\n".join(commands)
    aboutwindow.display(title="Commands", content=cmds)
    aboutwindow.hide()
    redraw_main_stuff()


@command(names=["help", "?"])
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

    Details:

    Running QGIS Version: {}

    """.format(QGis.QGIS_VERSION)
    aboutwindow.display(title="Help", content=abouttxt)
    aboutwindow.hide()
    redraw_main_stuff()


@command(names=['about', 'faq', 'wat!?'])
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
    redraw_main_stuff()


def redraw_main_stuff():
    """
    Redraw the map, legend, and clear the edit bar
    :return:
    """
    mapwindow.render_map()
    legendwindow.render_legend()
    pad.clear()


@command(names=['exit', 'quit'])
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
    return project


@command(names=['load-project'])
def open_project():
    projectq = QAndA(question="Which project to open?", type=QAndA.QUESTION)
    project = yield projectq
    fullpath = _resolve_project_path(project)
    while not _resolve_project_path(project):
        projectq.type = QAndA.QUESTIOnERROR
        project = yield projectq
        fullpath = _resolve_project_path(project)

    answerq = QAndA(question="Really load ({}) | Y/N ".format(fullpath), type=QAndA.QUESTION)
    answer = yield answerq
    while not answer or answer[0].upper() not in ['Y', 'N']:
        answer = yield answerq

    if answer[0].upper() == "Y":
        _open_project(fullpath)
        assign_layer_colors()
        legendwindow.render_legend()
        mapwindow.render_map()

@command()
def toggle_ascii_mode():
    global ascii_mode_enabled
    ascii_mode_enabled = not ascii_mode_enabled
    mapwindow.render_map()
    legendwindow.render_legend()

@command()
def toggle_color_mode():
    global color_mode_enabled
    color_mode_enabled = not color_mode_enabled
    global ascii_mode_enabled
    ascii_mode_enabled = not color_mode_enabled
    mapwindow.render_map()
    legendwindow.render_legend()

@command()
def zoom_out():
    factor = yield QAndA("By how much?", type=QAndA.QUESTION)
    mapwindow.zoom_out(float(factor))

@command()
def zoom_in():
    factor = yield QAndA("By how much?", type=QAndA.QUESTION)
    mapwindow.zoom_in(float(factor))


def assign_layer_colors():
    """
    Assign all the colors for each layer up front so we can use
    it though the application.
    """
    import itertools
    colors = itertools.cycle(range(11, curses.COLORS - 10))
    layercolormapping.clear()
    root = QgsProject.instance().layerTreeRoot()
    layers = [node.layer() for node in root.findLayers()]
    for layer in reversed(layers):
        if not layer.type() == QgsMapLayer.VectorLayer:
            continue
        layercolormapping[layer.id()] = colors.next()


def timeme(func):
    def wrap(*args, **kwargs):
        time1 = time.time()
        ret = func(*args, **kwargs)
        time2 = time.time()
        logging.info('%s function took %0.3f ms' % (func.func_name, (time2-time1)*1000.0))
        return ret
    return wrap


class AboutWindow():
    def __init__(self):
        y, x = scr.getmaxyx()
        self.infowin = curses.newwin(y / 2, x / 2, y / 4, x / 4)
        self.infopanel = curses.panel.new_panel(self.infowin)
        self.infowin.keypad(1)

    def display(self, title, content):
        curses.curs_set(0)
        self.infowin.clear()
        y, x = self.infowin.getmaxyx()
        self.infowin.bkgd(" ", curses.color_pair(6))
        self.infowin.box()
        self.infowin.addstr(0, 0, title + " - 'q' to close", curses.A_UNDERLINE | curses.A_BOLD)
        for count, line in enumerate(content.split('\n'), start=1):
            try:
                self.infowin.addstr(count, 1, line)
            except:
                pass

        self.infopanel.show()
        curses.panel.update_panels()
        curses.doupdate()
        while self.infowin.getch() != ord('q'):
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
        self.win.keypad(1)
        self.items = []
        self.title = "Layers (F5)"

    def render_legend(self):
        def render_item(node, row, col):
            nodestr = str(node)

            color = 0
            char = ' '
            islayer = False
            if isinstance(node, QgsLayerTreeLayer):
                nodestr = "(L) " + node.layerName()
                if ascii_mode_enabled:
                    char = codes[node.layer().geometryType()]
                if color_mode_enabled:
                    color = layercolormapping.get(node.layerId(), 0)
                islayer = True
            if isinstance(node, QgsLayerTreeGroup):
                nodestr = "(G) " + node.name()


            state = "[ ]"
            if node.isVisible():
                state = "[x]"

            expanded = ' '
            if not islayer:
                if node.isExpanded():
                    expanded = '-'
                else:
                    expanded = '+'

            # This could be made generic for reuse in other places
            parts = [
                (expanded, 0),
                (state, 0),
                (char * 2, color),
                (nodestr, 0),
            ]

            currentx = col
            y, maxsize = self.win.getmaxyx()
            for part, color in parts:
                tempx = currentx + len(part)
                oversize = tempx > maxsize - 1
                if oversize:
                    diff = tempx - (maxsize - 1)
                    part = part[:-diff]
                self.win.addstr(row, currentx, part, curses.color_pair(color))
                currentx += len(part)
                if oversize:
                    break
            self.items.append((nodestr, row, col + len(expanded) + 1, node))

        def render_nodes(node):
            self.items = []
            depth = [1, 1]

            def wrapped(box):
                render_item(box, depth[0], depth[1])

                if box.isExpanded():
                    depth[1] += 1
                    for child in box.children():
                        depth[0] += 1
                        wrapped(child)
                    depth[1] -= 1

            for child in node.children():
                wrapped(child)
                depth[0] += 1

        size = 30
        self.win.clear()
        self.win.box()
        self.win.addstr(0, 2, self.title, curses.A_BOLD)
        root = QgsProject.instance().layerTreeRoot()
        render_nodes(root)
        self.win.refresh()

    def focus(self):
        def move_item(index):
            try:
                item = self.items[index]
            except IndexError:
                return
            itemrow = item[1]
            logging.info("Selected legend item {} at row {}".format(item[0], itemrow))
            self.win.move(itemrow, item[2])

        modeline.update_activeWindow("Legend")
        index = 0
        move_item(index)
        self.win.nodelay(1)
        curses.curs_set(1)
        while True:
            char = self.win.getch()
            if char == -1:
                continue

            logging.info(char)

            try_handle_global_event(char)

            if char == curses.KEY_DOWN:
                logging.info("Down we go")
                index += 1
                maxindex = len(self.items)
                if index > maxindex:
                    index = maxindex
                move_item(index)
            if char == curses.KEY_UP:
                logging.info("Up we go")
                index -= 1
                if index < 0:
                    index = 0
                move_item(index)
            if char == 32:
                item = self.items[index]
                if item[3].isVisible():
                    item[3].setVisible(Qt.Unchecked)
                else:
                    item[3].setVisible(Qt.Checked)
                mapwindow.render_map()
                self.render_legend()
                move_item(index)
            if char in (curses.KEY_LEFT, curses.KEY_RIGHT):
                item = self.items[index]
                close = char == curses.KEY_RIGHT
                item[3].setExpanded(close)
                self.render_legend()
                move_item(index)


#NOTE: Unused at the moment. Translates color into a pixel code
# def get_pixel_value(pixels, x, y):
#     if ascii_mode_enabled:
#         color = "MNHQ$OC?7>!:-;. "
#     else:
#         color = "" * 16
#     rgba = QColor(pixels.pixel(x, y))
#     rgb = rgba.red(), rgba.green(), rgba.blue()
#     index = int(sum(rgb) / 3.0 / 256.0 * 16)
#     pair = curses.color_pair(index + 10)
#     if ascii_mode_enabled:
#         pair = 1
#
#     try:
#         return color[index], pair
#     except IndexError:
#         return " ", pair

@timeme
def stack(layers, fill=(' ', 0)):
    """
    Stack a bunch of arrays and return a single array.
    :param layers:
    :param fill:
    :return:
    """
    output_array = []
    for row_stack in zip(*layers):
        o_row = []
        for pixel_stack in zip(*row_stack):
            opaque_pixels = [_p for _p in pixel_stack if _p[0] != ' ']
            if len(opaque_pixels) is 0:
                o_row.append(fill)
            else:
                o_row.append(opaque_pixels[-1])
        output_array.append(o_row)
    return output_array

@timeme
def generate_layers_ascii(setttings, width, height):
    root = QgsProject.instance().layerTreeRoot()
    layers = [node.layer() for node in root.findLayers()
              if node.layer().type() == QgsMapLayer.VectorLayer and node.isVisible()]

    layersdata = []
    for layer in reversed(layers):
        colorpair = layercolormapping[layer.id()]
        char = codes[layer.geometryType()]
        image = render_layer(setttings, layer, width, height)
        layerdata = []
        for row in range(1, height - 1):
            rowdata = []
            for col in range(1, width - 1):
                color = QColor(image.pixel(col, row))
                # All non white is considered a feature.
                # Should pull background colour from project file
                if not color == QColor(255, 255, 255):
                    rowdata.append((char, colorpair))
                    rowdata.append((char, colorpair))
                else:
                    rowdata.append((' ', 8))
                    rowdata.append((' ', 8))
            layerdata.append(rowdata)
        layersdata.append(layerdata)
    return stack(layersdata)


@timeme
def render_layer(settings, layer, width, height):
    settings.setLayers([layer.id()])
    settings.setFlags(settings.flags() ^ QgsMapSettings.Antialiasing)
    settings.setOutputSize(QSize(width, height))
    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    image = job.renderedImage()
    # image.save(r"/media/nathan/Data/dev/qgis-term/{}.jpg".format(layer.name()))
    return image


class Map():
    """
    Map window
    """
    def __init__(self):
        y, x = scr.getmaxyx()
        self.mapwin = curses.newwin(y - TOPBORDER, x - 30, BOTTOMBORDER, 30)
        self.mapwin.keypad(1)
        self.settings = None
        self.title = "Map (F6)"

    def render_map(self):
        y, x = scr.getmaxyx()
        x -= 30

        self.mapwin.clear()
        self.mapwin.box()
        self.mapwin.addstr(0, 2, self.title, curses.A_BOLD)

        height, width = self.mapwin.getmaxyx()
        # Only render the image if we have a open project
        if not self.settings and project:
            self.settings = project.map_settings

        if project:
            settings = self.settings
            data = generate_layers_ascii(self.settings, width, height)
            for row, rowdata in enumerate(data, start=1):
                if row >= height:
                    break

                for col, celldata in enumerate(rowdata, start=1):
                    if col >= width - 1:
                        break

                    value, color = celldata[0], celldata[1]
                    if value == ' ':
                        color = 8
                    if not ascii_mode_enabled:
                        value = ' '

                    if not color_mode_enabled:
                        color = 0

                    self.mapwin.addstr(row, col, value, curses.color_pair(color))

        self.mapwin.refresh()

    def focus(self):
        modeline.update_activeWindow("Map")
        curses.curs_set(0)
        while True:
            event = self.mapwin.getch()
            # if event == -1:
            #     continue
            logging.info(event)
            try_handle_global_event(event)

            if event == curses.KEY_UP:
                self.pan("up")
            if event == curses.KEY_DOWN:
                self.pan("down")
            if event == curses.KEY_LEFT:
                self.pan("left")
            if event == curses.KEY_RIGHT:
                self.pan("right")
            if event == curses.KEY_NPAGE:
                self.zoom_out(5)
            if event == curses.KEY_PPAGE:
                self.zoom_in(5)

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

class ModeLine():
    def __init__(self):
        y, x = scr.getmaxyx()
        self.modeline = curses.newwin(1, x, y - 1, 0)
        self.modeline.bkgd(curses.color_pair(6))
        self.modeline.refresh()

    def update_activeWindow(self, name):
        self.modeline.erase()
        self.modeline.addstr(0, 0, "Window: {}".format(name))
        self.modeline.refresh()


class EditPad():
    def __init__(self):
        y, x = scr.getmaxyx()
        self.edit = curses.newwin(1, x, y - 2, 0)
        self.status = curses.newwin(1, x, y - 3, 0)
        self.pad = Textbox(self.edit, insert_mode=True)
        self.lastcmd = []

    def update_cmd_status(self, message, color=None):
        if not color:
            color = curses.color_pair(1)
        self.status.clear()
        try:
            self.status.addstr(0, 0, message, color)
            self.status.refresh()
        except:
            pass

    def focus(self):
        modeline.update_activeWindow("Command Entry")
        self.edit.erase()
        entercommandstr = "Enter command. TAB for auto complete. (command-list for command help or ? for general help)"
        pad.update_cmd_status(entercommandstr)

        curses.curs_set(1)
        while True:
            message = self.pad.edit(validate=self.handle_key_event).strip()
            try:
                cmd = commands[message]
            except KeyError:
                self.update_cmd_status("Unknown command: {}".format(message), colors['red'])
                continue

            if message not in self.lastcmd:
                self.lastcmd.append(message)

            func = cmd()
            if not func:
                self.update_cmd_status(entercommandstr)
                self.edit.clear()
                self.edit.refresh()
                continue

            try:
                qanda = func.send(None)
                while True:
                    self.edit.clear()
                    self.update_cmd_status(qanda.question, color=curses.color_pair(qanda.type))
                    message = self.pad.edit(validate=self.handle_key_event).strip()
                    qanda = func.send(message)
            except StopIteration:
                pass

            self.update_cmd_status(entercommandstr)
            self.edit.erase()

    def clear(self):
        self.edit.erase()

    def handle_key_event(self, event):
        """
        Handle edit pad key events
        :param event:
        :return:
        """
        logging.info("Key Event:{}".format(event))
        if event == curses.KEY_UP:
            try:
                cmd = self.lastcmd[0]
            except IndexError:
                return event

            self.edit.clear()
            self.edit.addstr(0, 0, cmd)
            self.edit.refresh()

        try_handle_global_event(event)

        if event == 9:
            logging.info("Calling auto complete on TAB key")
            data = self.pad.gather().strip()
            cmds = {key[:len(data)]: key for key in commands.keys()}
            logging.info("Options are")
            for cmd, fullname in cmds.iteritems():
                if cmd == data:
                    logging.info("Grabbed the first match which was {}".format(fullname))
                    self.edit.clear()
                    self.edit.addstr(0, 0, fullname)
                    self.edit.refresh()
                    break
        return event


def try_handle_global_event(event):
    if event == curses.KEY_F5:
        legendwindow.focus()
    if event == curses.KEY_F6:
        mapwindow.focus()
    if event == curses.KEY_F7:
        pad.focus()


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
    curses.init_pair(8, curses.COLOR_WHITE, curses.COLOR_WHITE)
    colors['white'] = curses.color_pair(1)
    colors['green'] = curses.color_pair(2)
    colors['cyan'] = curses.color_pair(3)
    colors['yellow'] = curses.color_pair(4)
    colors['green-black'] = curses.color_pair(5)
    colors['black-white'] = curses.color_pair(6)
    colors['red'] = curses.color_pair(7)
    colors['white-white'] = curses.color_pair(8)

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


    init_colors()

    screen.refresh()

    global scr, pad, aboutwindow, legendwindow, mapwindow, modeline
    scr = screen
    pad = EditPad()
    modeline = ModeLine()
    mapwindow = Map()
    legendwindow = Legend()
    aboutwindow = AboutWindow()

    legendwindow.render_legend()
    mapwindow.render_map()

    screen.addstr(0, 0, "ASCII")
    screen.addstr(0, 5, " QGIS Enterprise", curses.color_pair(4))
    screen.refresh()

    if config.get('showhelp', True):
        show_help()

    pad.focus()


app = QGIS.init(guienabled=False)

if __name__ == "__main__":
    logging.info("Staring QGIS ASCII :)")
    logging.info("ASCII QGIS because we can")
    curses.wrapper(main)
