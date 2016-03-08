import os
import re
from qgis.core import QgsMapLayerRegistry, QgsVectorLayer

_layerreg = QgsMapLayerRegistry.instance()


def map_layers(name=None, type=None):
    """
    Return all the loaded layers.  Filters by name (optional) first and then type (optional)
    :param name: (optional) name of layer to return..
    :param type: (optional) The QgsMapLayer type of layer to return.
    :return: List of loaded layers. If name given will return all layers with matching name.
    """
    layers = _layerreg.mapLayers().values()
    _layers = []
    if name or type:
        if name:
            _layers = [layer for layer in layers if re.match(name, layer.name())]
        if type:
            _layers += [layer for layer in layers if layer.type() == type]
        return _layers
    else:
        return layers


def add_layer(layer, load_in_legend=True):
    """
    Add a open layer to the QGIS session and layer registry.
    :param layer: The layer object to add the QGIS layer registry and session.
    :param load_in_legend: True if this layer should be added to the legend.
    :return: The added layer
    """
    if not hasattr(layer, "__iter__"):
        layer = [layer]
    QgsMapLayerRegistry.instance().addMapLayers(layer, load_in_legend)
    return layer


def load_vector(path, name=None, provider="ogr"):
    """
    Load a vector layer and return the QgsVectorLayer instance.
    :param path: Path to the vector layer.
    :param name: The name of the new layer.
    :param provider: The provider to open this layer with defaults to ogr.
    :return: A QgsVectorLayer instance for the layer.
    """
    if not name:
        name = os.path.basename(path)
    layer = QgsVectorLayer(path, name, provider)
    return layer

