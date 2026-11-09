# -*- coding: utf-8 -*-
"""QGIS Export Information plugin."""

def classFactory(iface):
    from .export_information import ExportInformationPlugin
    return ExportInformationPlugin(iface)
