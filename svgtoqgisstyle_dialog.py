# -*- coding: utf-8 -*-
"""
Finestra di dialogo principale del plugin "SVG to QGIS Style".

Contiene tutta la logica dell'interfaccia utente:
  - selezione di una cartella o di singoli file SVG;
  - lista con anteprima 64x64 delle icone caricate;
  - applicazione/ripristino di colori di sfondo e riempimento in anteprima;
  - selezione del file di destinazione dello stile QGIS;
  - avvio della conversione con avanzamento su progress bar.
"""

import os

from qgis.PyQt.QtCore import Qt, QSize, QCoreApplication
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QToolButton,
    QMenu,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QLineEdit,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QProgressBar,
    QFileDialog,
    QColorDialog,
    QMessageBox,
    QWidget,
)

from . import svg_utils


ICON_SIZE = 64
DEFAULT_BG_COLOR = QColor('#2c7fb8')
DEFAULT_FG_COLOR = QColor('#ffffff')


class SvgEntry:
    """Rappresenta un singolo file SVG caricato nella lista, con il testo
    originale e quello (eventualmente) ricolorato correntemente in anteprima.
    """

    def __init__(self, path):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            self.original_text = f.read()
        self.current_text = self.original_text

    @property
    def is_modified(self):
        return self.current_text != self.original_text


class SvgToQgisStyleDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr('SVG to QGIS Style'))
        self.resize(720, 640)

        self.entries = []  # list[SvgEntry], stesso ordine della QListWidget
        self.output_path = ''
        self.bg_color = QColor(DEFAULT_BG_COLOR)
        self.fg_color = QColor(DEFAULT_FG_COLOR)

        self._build_ui()
        self._connect_signals()
        self._update_color_buttons()
        self._update_convert_button_state()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Selezione sorgente SVG -----------------------------------------
        source_layout = QHBoxLayout()
        self.btn_select_source = QToolButton(self)
        self.btn_select_source.setText(self.tr('Select SVG folder or file…'))
        self.btn_select_source.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_select_source.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        source_menu = QMenu(self.btn_select_source)
        self.action_select_folder = source_menu.addAction(self.tr('Select folder…'))
        self.action_select_files = source_menu.addAction(self.tr('Select SVG file(s)…'))
        self.btn_select_source.setMenu(source_menu)

        self.lbl_source_count = QLabel(self.tr('No SVG file loaded'), self)

        source_layout.addWidget(self.btn_select_source)
        source_layout.addWidget(self.lbl_source_count)
        source_layout.addStretch(1)

        self.btn_clear_list = QPushButton(self.tr('Clear list'), self)
        source_layout.addWidget(self.btn_clear_list)

        main_layout.addLayout(source_layout)

        # --- Lista con anteprime ---------------------------------------------
        self.list_widget = QListWidget(self)
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setSpacing(10)
        self.list_widget.setWordWrap(True)
        self.list_widget.setMinimumHeight(260)
        main_layout.addWidget(self.list_widget, stretch=1)

        # --- Gruppo colori -------------------------------------------------
        color_group = QGroupBox(self.tr('Preview colors'), self)
        color_layout = QGridLayout(color_group)

        self.chk_apply_bg = QCheckBox(self.tr('Apply background color'), color_group)
        self.btn_bg_color = QPushButton('', color_group)
        self.btn_bg_color.setFixedWidth(60)

        self.chk_apply_fg = QCheckBox(self.tr('Apply fill color'), color_group)
        self.btn_fg_color = QPushButton('', color_group)
        self.btn_fg_color.setFixedWidth(60)

        color_layout.addWidget(self.chk_apply_bg, 0, 0)
        color_layout.addWidget(self.btn_bg_color, 0, 1)
        color_layout.addWidget(self.chk_apply_fg, 1, 0)
        color_layout.addWidget(self.btn_fg_color, 1, 1)

        # Ambito di applicazione: tutti o solo selezionati
        scope_label = QLabel(self.tr('Apply to:'), color_group)
        self.radio_apply_all = QRadioButton(self.tr('All icons'), color_group)
        self.radio_apply_selected = QRadioButton(self.tr('Selected icons only'), color_group)
        self.radio_apply_all.setChecked(True)
        self.scope_group = QButtonGroup(color_group)
        self.scope_group.addButton(self.radio_apply_all)
        self.scope_group.addButton(self.radio_apply_selected)

        color_layout.addWidget(scope_label, 0, 2)
        color_layout.addWidget(self.radio_apply_all, 0, 3)
        color_layout.addWidget(self.radio_apply_selected, 1, 3)

        buttons_layout = QHBoxLayout()
        self.btn_apply_preview = QPushButton(self.tr('Apply preview'), color_group)
        self.btn_reset_colors = QPushButton(self.tr('Reset original colors'), color_group)
        buttons_layout.addWidget(self.btn_apply_preview)
        buttons_layout.addWidget(self.btn_reset_colors)
        buttons_layout.addStretch(1)
        color_layout.addLayout(buttons_layout, 2, 0, 1, 4)

        main_layout.addWidget(color_group)

        # --- Destinazione file di stile -------------------------------------
        output_group = QGroupBox(self.tr('QGIS style file'), self)
        output_layout = QHBoxLayout(output_group)

        self.line_output = QLineEdit(output_group)
        self.line_output.setReadOnly(True)
        self.line_output.setPlaceholderText(self.tr('No destination selected'))
        self.btn_select_output = QPushButton(self.tr('Select destination…'), output_group)

        output_layout.addWidget(self.line_output, stretch=1)
        output_layout.addWidget(self.btn_select_output)

        main_layout.addWidget(output_group)

        # --- Conversione e progress bar --------------------------------------
        convert_layout = QHBoxLayout()
        self.btn_convert = QPushButton(self.tr('Start conversion'), self)
        self.btn_convert.setMinimumHeight(32)
        convert_layout.addWidget(self.btn_convert)
        main_layout.addLayout(convert_layout)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel('', self)
        main_layout.addWidget(self.lbl_status)

        # --- Chiudi ---------------------------------------------------------
        close_layout = QHBoxLayout()
        close_layout.addStretch(1)
        self.btn_close = QPushButton(self.tr('Close'), self)
        close_layout.addWidget(self.btn_close)
        main_layout.addLayout(close_layout)

    def _connect_signals(self):
        self.action_select_folder.triggered.connect(self.select_folder)
        self.action_select_files.triggered.connect(self.select_files)
        self.btn_clear_list.clicked.connect(self.clear_list)

        self.btn_bg_color.clicked.connect(lambda: self._pick_color('bg'))
        self.btn_fg_color.clicked.connect(lambda: self._pick_color('fg'))

        self.btn_apply_preview.clicked.connect(self.apply_preview)
        self.btn_reset_colors.clicked.connect(self.reset_colors)

        self.btn_select_output.clicked.connect(self.select_output)
        self.btn_convert.clicked.connect(self.convert)
        self.btn_close.clicked.connect(self.close)

        self.list_widget.model().rowsInserted.connect(lambda *a: self._update_convert_button_state())
        self.list_widget.model().rowsRemoved.connect(lambda *a: self._update_convert_button_state())

    # ------------------------------------------------------------ selezione --
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.tr('Select folder containing SVG files')
        )
        if not folder:
            return
        paths = svg_utils.find_svg_files(folder)
        if not paths:
            QMessageBox.information(
                self, self.tr('No SVG file found'),
                self.tr('No .svg file was found in the selected folder.')
            )
            return
        self._add_svg_paths(paths)

    def select_files(self):
        paths, _filter = QFileDialog.getOpenFileNames(
            self, self.tr('Select SVG file(s)'), '',
            self.tr('SVG files (*.svg)')
        )
        if not paths:
            return
        self._add_svg_paths(paths)

    def clear_list(self):
        self.entries = []
        self.list_widget.clear()
        self.progress_bar.setValue(0)
        self.lbl_status.setText('')
        self._update_convert_button_state()

    def _add_svg_paths(self, paths):
        existing_paths = {e.path for e in self.entries}
        added = 0
        skipped = 0
        for path in paths:
            if path in existing_paths:
                continue
            try:
                entry = SvgEntry(path)
            except Exception:
                skipped += 1
                continue
            self.entries.append(entry)
            self._add_list_item(entry)
            added += 1

        self._refresh_source_label()

        if skipped:
            QMessageBox.warning(
                self, self.tr('Some files were skipped'),
                self.tr('{count} file(s) could not be read and were skipped.').format(count=skipped)
            )

    def _add_list_item(self, entry):
        pixmap = svg_utils.render_svg_pixmap(entry.current_text, ICON_SIZE)
        item = QListWidgetItem(QIcon(pixmap), entry.name)
        item.setSizeHint(QSize(ICON_SIZE + 40, ICON_SIZE + 34))
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        item.setToolTip(entry.path)
        self.list_widget.addItem(item)

    def _refresh_source_label(self):
        count = len(self.entries)
        if count == 0:
            self.lbl_source_count.setText(self.tr('No SVG file loaded'))
        else:
            self.lbl_source_count.setText(
                self.tr('{count} SVG file(s) loaded').format(count=count)
            )

    # ------------------------------------------------------------------ colori --
    def _pick_color(self, which):
        current = self.bg_color if which == 'bg' else self.fg_color
        color = QColorDialog.getColor(
            current, self,
            self.tr('Choose background color') if which == 'bg'
            else self.tr('Choose fill color')
        )
        if not color.isValid():
            return
        if which == 'bg':
            self.bg_color = color
            self.chk_apply_bg.setChecked(True)
        else:
            self.fg_color = color
            self.chk_apply_fg.setChecked(True)
        self._update_color_buttons()

    def _update_color_buttons(self):
        self.btn_bg_color.setStyleSheet(
            'background-color: {}; border: 1px solid #555;'.format(self.bg_color.name())
        )
        self.btn_fg_color.setStyleSheet(
            'background-color: {}; border: 1px solid #555;'.format(self.fg_color.name())
        )

    def _target_indexes(self):
        """Restituisce gli indici (nella lista self.entries) su cui operare,
        in base alla scelta "Tutti gli elementi" / "Solo selezionati".
        """
        if self.radio_apply_selected.isChecked():
            return sorted(
                self.list_widget.row(item) for item in self.list_widget.selectedItems()
            )
        return list(range(len(self.entries)))

    def apply_preview(self):
        if not self.entries:
            return

        apply_bg = self.chk_apply_bg.isChecked()
        apply_fg = self.chk_apply_fg.isChecked()
        if not apply_bg and not apply_fg:
            QMessageBox.information(
                self, self.tr('No color selected'),
                self.tr('Enable at least one of "Apply background color" or '
                         '"Apply fill color" before applying the preview.')
            )
            return

        indexes = self._target_indexes()
        if not indexes:
            QMessageBox.information(
                self, self.tr('No icon selected'),
                self.tr('Select at least one icon in the list, or choose '
                         '"All icons".')
            )
            return

        bg_hex = svg_utils.qcolor_to_hex(self.bg_color) if apply_bg else None
        fg_hex = svg_utils.qcolor_to_hex(self.fg_color) if apply_fg else None

        for idx in indexes:
            entry = self.entries[idx]
            entry.current_text = svg_utils.recolor_svg_text(
                entry.original_text, bg_hex=bg_hex, fg_hex=fg_hex
            )
            self._refresh_item_icon(idx)

    def reset_colors(self):
        if not self.entries:
            return

        modified_count = sum(1 for e in self.entries if e.is_modified)
        if modified_count == 0:
            return

        reply = QMessageBox.question(
            self, self.tr('Reset original colors'),
            self.tr('This will discard the color preview and restore the '
                     'original colors for all icons. Continue?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for idx, entry in enumerate(self.entries):
            if entry.is_modified:
                entry.current_text = entry.original_text
                self._refresh_item_icon(idx)

    def _refresh_item_icon(self, idx):
        entry = self.entries[idx]
        pixmap = svg_utils.render_svg_pixmap(entry.current_text, ICON_SIZE)
        item = self.list_widget.item(idx)
        if item is not None:
            item.setIcon(QIcon(pixmap))

    # ------------------------------------------------------------ destinazione --
    def select_output(self):
        path, _filter = QFileDialog.getSaveFileName(
            self, self.tr('Select destination for the QGIS style file'),
            self.output_path or 'style.xml',
            self.tr('QGIS style file (*.xml)')
        )
        if not path:
            return
        if not path.lower().endswith('.xml'):
            path += '.xml'
        self.output_path = path
        self.line_output.setText(path)
        self._update_convert_button_state()

    def _update_convert_button_state(self):
        self.btn_convert.setEnabled(bool(self.entries) and bool(self.output_path))

    # ------------------------------------------------------------------ convert --
    def convert(self):
        if not self.entries:
            QMessageBox.warning(
                self, self.tr('No SVG file'),
                self.tr('Load at least one SVG file before starting the conversion.')
            )
            return
        if not self.output_path:
            QMessageBox.warning(
                self, self.tr('No destination'),
                self.tr('Select the destination file for the QGIS style before '
                         'starting the conversion.')
            )
            return

        total = len(self.entries)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self._set_controls_enabled(False)

        svg_out_dir = None
        if any(e.is_modified for e in self.entries):
            base = os.path.splitext(os.path.basename(self.output_path))[0]
            svg_out_dir = os.path.join(os.path.dirname(self.output_path), base + '_svg')
            try:
                os.makedirs(svg_out_dir, exist_ok=True)
            except OSError as exc:
                self._set_controls_enabled(True)
                QMessageBox.critical(
                    self, self.tr('Error'),
                    self.tr('Could not create folder for recolored SVG files:\n{error}').format(error=str(exc))
                )
                return

        used_names = set()
        symbol_elements = []
        errors = []

        fill_rgba = svg_utils.qcolor_to_qgis_rgba(
            self.fg_color if self.chk_apply_fg.isChecked() else QColor(0, 0, 0, 255)
        )
        outline_rgba = svg_utils.qcolor_to_qgis_rgba(
            self.bg_color if self.chk_apply_bg.isChecked() else QColor(35, 35, 35, 255)
        )

        for i, entry in enumerate(self.entries):
            self.lbl_status.setText(
                self.tr('Processing: {name}').format(name=entry.name)
            )
            self.progress_bar.setValue(i)
            QCoreApplication.processEvents()

            try:
                if entry.is_modified and svg_out_dir:
                    out_svg_path = os.path.join(svg_out_dir, os.path.basename(entry.path))
                    # Sicurezza: il file SVG originale non deve MAI essere
                    # sovrascritto. Nel caso limite in cui il percorso di
                    # destinazione coincida con quello del file di origine
                    # (ad es. se la cartella di destinazione dei colori
                    # applicati coincidesse con quella sorgente), si
                    # aggiunge un suffisso per garantire che la copia
                    # ricolorata venga scritta altrove.
                    if os.path.abspath(out_svg_path) == os.path.abspath(entry.path):
                        base, ext = os.path.splitext(out_svg_path)
                        out_svg_path = '{}_color{}'.format(base, ext)
                    out_svg_path = self._ensure_unique_path(out_svg_path)
                    with open(out_svg_path, 'w', encoding='utf-8') as f:
                        f.write(entry.current_text)
                    referenced_path = out_svg_path
                else:
                    referenced_path = entry.path

                symbol_name = svg_utils.unique_symbol_name(
                    svg_utils.sanitize_symbol_name(entry.name), used_names
                )
                referenced_path = referenced_path.replace(os.sep, '/')

                symbol_elements.append(
                    svg_utils.build_svg_marker_symbol_element(
                        symbol_name, referenced_path, fill_rgba, outline_rgba
                    )
                )
            except Exception as exc:
                errors.append('{}: {}'.format(entry.name, str(exc)))

        self.progress_bar.setValue(total)
        QCoreApplication.processEvents()

        if not symbol_elements:
            self._set_controls_enabled(True)
            QMessageBox.critical(
                self, self.tr('Conversion failed'),
                self.tr('No symbol could be generated. Please check the source files.')
            )
            return

        try:
            xml_content = svg_utils.build_style_document(symbol_elements)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
        except Exception as exc:
            self._set_controls_enabled(True)
            QMessageBox.critical(
                self, self.tr('Error while writing the style file'),
                str(exc)
            )
            return

        self._set_controls_enabled(True)
        self.lbl_status.setText(
            self.tr('Conversion completed: {count} symbol(s) written.').format(
                count=len(symbol_elements)
            )
        )

        message = self.tr('QGIS style file successfully created:\n{path}').format(
            path=self.output_path
        )
        if errors:
            message += '\n\n' + self.tr('The following files were skipped due to errors:') + '\n'
            message += '\n'.join(errors)
        QMessageBox.information(self, self.tr('Conversion completed'), message)

        # Una volta raggiunto il valore massimo (conversione completata),
        # la barra di avanzamento torna a zero, pronta per un nuovo utilizzo.
        self.progress_bar.setValue(0)

    @staticmethod
    def _ensure_unique_path(path):
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        candidate = '{}_{}{}'.format(base, counter, ext)
        while os.path.exists(candidate):
            counter += 1
            candidate = '{}_{}{}'.format(base, counter, ext)
        return candidate

    def _set_controls_enabled(self, enabled):
        for widget in (
            self.btn_select_source, self.btn_clear_list, self.list_widget,
            self.chk_apply_bg, self.chk_apply_fg, self.btn_bg_color, self.btn_fg_color,
            self.radio_apply_all, self.radio_apply_selected,
            self.btn_apply_preview, self.btn_reset_colors,
            self.btn_select_output, self.btn_convert, self.btn_close,
        ):
            widget.setEnabled(enabled)
        if enabled:
            self._update_convert_button_state()
