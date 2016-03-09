#!/usr/bin/env bash

QGIS_PREFIX_PATH=/Applications/QGIS.app/contents/MacOS;
PYTHONPATH=$PYTHONPATH:/Applications/QGIS.app/contents/Resources/python:/Applications/QGIS.app/Contents/Resources/python/plugins/;
PYTHONUNBUFFERED=1;
TERM=screen

./ascii_qgis.py

