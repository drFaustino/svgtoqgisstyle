# -*- coding: utf-8 -*-
"""
Classe principale del plugin SVG to QGIS Style.

Si occupa di:
  - registrare l'azione nella toolbar e nel menu Plugin di QGIS;
  - caricare la traduzione (.qm) corrispondente alla lingua dell'interfaccia
    di QGIS, se disponibile in i18n/;
  - istanziare e mostrare la finestra di dialogo principale.
"""

import os.path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction


class SvgToQgisStyle:
    """Classe principale (plugin entry point) registrata da QGIS."""

    def __init__(self, iface):
        """
        :param iface: interfaccia QGIS.
        :type iface: QgisInterface
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # --- Gestione traduzioni -------------------------------------------------
        # QGIS espone la lingua dell'interfaccia tramite QSettings; se esiste un
        # file .qm compilato per quella lingua in i18n/, viene installato.
        locale = QSettings().value('locale/userLocale', 'en')
        locale = locale[0:2] if locale else 'en'
        locale_path = os.path.join(
            self.plugin_dir, 'i18n', 'svgtoqgisstyle_{}.qm'.format(locale)
        )

        self.translator = None
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr('SVG to QGIS Style')
        self.toolbar = self.iface.addToolBar('SvgToQgisStyle')
        self.toolbar.setObjectName('SvgToQgisStyle')

        self.dlg = None

    # ------------------------------------------------------------------ util --
    def tr(self, message):
        """Restituisce la traduzione della stringa per il contesto del plugin.

        :param message: stringa sorgente (inglese).
        :type message: str
        :rtype: str
        """
        return QCoreApplication.translate('SvgToQgisStyle', message)

    # --------------------------------------------------------------- QGIS API --
    def initGui(self):
        """Chiamato da QGIS al caricamento del plugin: crea l'azione GUI."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        action = QAction(
            QIcon(icon_path),
            self.tr('Convert SVG to QGIS Style'),
            self.iface.mainWindow()
        )
        action.setWhatsThis(self.tr('Convert SVG symbols to a QGIS style file'))
        action.setStatusTip(self.tr('Convert SVG symbols to a QGIS style file'))
        action.triggered.connect(self.run)

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

    def unload(self):
        """Chiamato da QGIS quando il plugin viene disattivato/rimosso."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
        del self.toolbar

        if self.translator is not None:
            QCoreApplication.removeTranslator(self.translator)

    def run(self):
        """Mostra (creandola se necessario) la finestra di dialogo principale."""
        if self.dlg is None:
            from .svgtoqgisstyle_dialog import SvgToQgisStyleDialog
            self.dlg = SvgToQgisStyleDialog(parent=self.iface.mainWindow())

        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
