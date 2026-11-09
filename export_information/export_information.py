# -*- coding: utf-8 -*-
"""QGIS plugin entry point."""

from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
import os


class ExportInformationPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def tr(self, message):
        return QCoreApplication.translate('ExportInformation', message)

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.svg')
        self.action = QAction(QIcon(icon_path), self.tr('Export Information'), self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.tr('&Export Information'), self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu(self.tr('&Export Information'), self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        try:
            from .export_dialog import ExportInformationDialog
            if self.dialog is None:
                self.dialog = ExportInformationDialog(self.iface)
            self.dialog.refresh_layers()
            self.dialog.show()
            self.dialog.raise_()
            self.dialog.activateWindow()
        except Exception as exc:
            QMessageBox.critical(self.iface.mainWindow(), self.tr('Export Information'),
                                 self.tr('Cannot open plugin window:\n{}').format(exc))
