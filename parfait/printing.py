from PyQt4.QtXml import QDomDocument
from qgis.core import QgsComposition


class Composer():
    pass

class ComposerTemplate():
    """
    Contains methods for working with loading/saving QGIS composer template files
    """
    def __init__(self, composition):
        self.composition = composition

    @classmethod
    def from_file(cls, template_path, mapsettings, data=None):
        """
        Create a template object from the given template path, map setttings, and data.
        :param template_path: The template path.
        :param mapsettings: QgsMapSettings used to render the map.
        :param data: A dict of data to use for labels.
        :return: A ComposerTemplate obect which wraps the created template.
        """
        if not data:
            data = {}

        with open(template_path) as f:
            template_content = f.read()

        document = QDomDocument()
        document.setContent(template_content)
        composition = QgsComposition(mapsettings)
        composition.loadFromTemplate(document, data)
        return cls(composition)

    def __getitem__(self, item):
        """
        Return the composer item with the given name.

        The same as doing getComposerItemById(item)
        """
        return self.composition.getComposerItemById(item)

    def export(self, outpath):
        self.composition.refreshItems()
        self.composition.exportAsPDF(outpath)


def render_template(template_path, settings, canvas, outpath, data=None):
    """
    Render the template at the given path using the settings and the export to the output path.

    Template assumes there is a map and legend objet in the template.
    :param template_path: The path to the template.
    :param settings: The QgsMapSettings used to render the template
    :param canvas: QgsMapCanvas item used to render the template. (This is gross but needed for now)
    :param outpath: The output path. Current only exports to PDF.
    :param data: A dict of data to use for labels.
    :return:
    """
    template = ComposerTemplate.from_file(template_path, canvas.mapSettings(), data)

    map_item = template['map']
    map_item.setMapCanvas(canvas)
    map_item.zoomToExtent(settings.extent())

    legend_item = template['legend']
    legend_item.updateLegend()
    template.export(outpath)
