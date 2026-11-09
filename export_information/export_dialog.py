# -*- coding: utf-8 -*-
"""Dialog for selecting project layers and exporting ODN information."""

import os
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QFileDialog, QMessageBox,
    QGroupBox, QDoubleSpinBox, QLineEdit, QProgressDialog
)
from qgis.core import QgsProject, QgsMapLayerType
from .exporter import export_information


class ExportInformationDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle('Export Information - ODN Excel Export')
        self.resize(620, 620)
        self._build_ui()
        self.refresh_layers()

    def _build_ui(self):
        root = QVBoxLayout(self)
        intro = QLabel(
            '根据 SUB BOX 名称自动识别 HUB BOX / L 链路 / S 序号；\n'
            'HUB BOX 和 SUB BOX 分别匹配 Poles 组内 3 米范围内最近的杆子。'
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        layer_box = QGroupBox('1. 图层选择')
        layer_form = QFormLayout(layer_box)
        self.hub_combo = QComboBox()
        self.sub_combo = QComboBox()
        self.cable_combo = QComboBox()
        layer_form.addRow('HUB BOX 图层:', self.hub_combo)
        layer_form.addRow('SUB BOX 图层:', self.sub_combo)
        layer_form.addRow('Distribution Cable 图层:', self.cable_combo)
        root.addWidget(layer_box)

        poles_box = QGroupBox('Poles 组（New Pole + Exsiting Pole）')
        poles_layout = QVBoxLayout(poles_box)
        self.poles_list = QListWidget()
        self.poles_list.setMaximumHeight(120)
        poles_layout.addWidget(self.poles_list)
        root.addWidget(poles_box)

        field_box = QGroupBox('2. 字段映射（自动识别，可手动调整）')
        field_form = QFormLayout(field_box)
        self.hub_name_field = QComboBox()
        self.sub_name_field = QComboBox()
        self.pole_name_field = QComboBox()
        self.hp_field = QComboBox()
        self.span_field = QComboBox()
        field_form.addRow('HUB BOX Name 字段:', self.hub_name_field)
        field_form.addRow('SUB BOX Name 字段:', self.sub_name_field)
        field_form.addRow('Pole Name 字段:', self.pole_name_field)
        field_form.addRow('SUB BOX HP Count 字段:', self.hp_field)
        field_form.addRow('Distribution Cable Span 字段:', self.span_field)
        root.addWidget(field_box)

        match_box = QGroupBox('3. 匹配与导出')
        match_form = QFormLayout(match_box)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0.1, 100.0)
        self.radius_spin.setDecimals(1)
        self.radius_spin.setValue(3.0)
        self.radius_spin.setSuffix(' m')
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText('选择 Excel 保存位置')
        browse_row = QHBoxLayout()
        browse_row.addWidget(self.output_edit, 1)
        browse_btn = QPushButton('浏览...')
        browse_btn.clicked.connect(self._browse_output)
        browse_row.addWidget(browse_btn)
        match_form.addRow('杆子匹配半径:', self.radius_spin)
        match_form.addRow('Excel 输出文件:', browse_row)
        root.addWidget(match_box)

        note = QLabel('说明：未匹配到 3 米内杆子的记录仍会导出，杆号/坐标留空，并写入 QA Report 工作表。')
        note.setWordWrap(True)
        note.setStyleSheet('color:#555;')
        root.addWidget(note)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton('重新识别图层')
        self.refresh_btn.clicked.connect(self.refresh_layers)
        self.export_btn = QPushButton('导出 Excel')
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self._export)
        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self.hub_combo.currentIndexChanged.connect(self._update_fields)
        self.sub_combo.currentIndexChanged.connect(self._update_fields)
        self.cable_combo.currentIndexChanged.connect(self._update_fields)
        self.poles_list.itemChanged.connect(self._update_fields)

    def _all_vector_layers(self):
        return [lyr for lyr in QgsProject.instance().mapLayers().values()
                if lyr.type() == QgsMapLayerType.VectorLayer and lyr.isValid()]

    def _layer_path_label(self, layer):
        # Include the layer-tree group path so identically named layers remain distinguishable.
        root = QgsProject.instance().layerTreeRoot()
        node = root.findLayer(layer.id())
        parts = [layer.name()]
        parent = node.parent() if node else None
        while parent and parent != root:
            if hasattr(parent, 'name') and parent.name():
                parts.insert(0, parent.name())
            parent = parent.parent()
        return ' / '.join(parts)

    @staticmethod
    def _norm(text):
        return ''.join(ch.lower() for ch in str(text or '') if ch.isalnum())

    def _find_default_layer(self, combo, names, contains=None):
        target_names = {self._norm(n) for n in names}
        contains = [self._norm(x) for x in (contains or [])]
        chosen = -1
        for i in range(combo.count()):
            layer = combo.itemData(i)
            n = self._norm(layer.name())
            if n in target_names or any(token in n for token in contains):
                chosen = i
                break
        if chosen >= 0:
            combo.setCurrentIndex(chosen)

    def refresh_layers(self):
        combos = (self.hub_combo, self.sub_combo, self.cable_combo)
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('-- 请选择图层 --', None)
        layers = self._all_vector_layers()
        for combo in combos:
            for lyr in layers:
                combo.addItem(self._layer_path_label(lyr), lyr)
            combo.blockSignals(False)
        self._find_default_layer(self.hub_combo, ['HUB BOX'], ['hubbox'])
        self._find_default_layer(self.sub_combo, ['SUB BOX'], ['subbox'])
        self._find_default_layer(self.cable_combo, ['Distribution Cable'], ['distributioncable'])

        self.poles_list.blockSignals(True)
        self.poles_list.clear()
        pole_candidates = []
        root = QgsProject.instance().layerTreeRoot()
        poles_group = None
        def find_poles_group(node):
            nonlocal poles_group
            for child in node.children():
                if hasattr(child, 'name') and self._norm(child.name()) == 'poles' and hasattr(child, 'children'):
                    poles_group = child
                    return
                if hasattr(child, 'children'):
                    find_poles_group(child)
                if poles_group:
                    return
        find_poles_group(root)
        if poles_group:
            def collect(node):
                for child in node.children():
                    if hasattr(child, 'layer') and child.layer() and child.layer().isValid():
                        lyr = child.layer()
                        if lyr.type() == QgsMapLayerType.VectorLayer:
                            pole_candidates.append(lyr)
                    elif hasattr(child, 'children'):
                        collect(child)
            collect(poles_group)
        # Fallback: locate expected pole layer names project-wide if Poles group is absent.
        if not pole_candidates:
            for lyr in layers:
                n = self._norm(lyr.name())
                if n in ('newpole', 'exsitingpole', 'existingpole'):
                    pole_candidates.append(lyr)
        seen = set()
        for lyr in pole_candidates:
            if lyr.id() in seen:
                continue
            seen.add(lyr.id())
            item = QListWidgetItem(self._layer_path_label(lyr))
            item.setData(Qt.UserRole, lyr)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if self._norm(lyr.name()) in ('newpole', 'exsitingpole', 'existingpole') else Qt.Unchecked)
            self.poles_list.addItem(item)
        self.poles_list.blockSignals(False)
        self._update_fields()

    def _selected_layer(self, combo):
        return combo.currentData()

    def _set_field_combo(self, combo, layer, candidates):
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        if layer:
            names = [f.name() for f in layer.fields()]
            for name in names:
                combo.addItem(name)
            wanted = {self._norm(x) for x in candidates}
            selected = -1
            for idx, name in enumerate(names):
                if self._norm(name) in wanted:
                    selected = idx
                    break
            if selected < 0 and current in names:
                selected = names.index(current)
            if selected >= 0:
                combo.setCurrentIndex(selected)
        combo.blockSignals(False)

    def _selected_poles(self):
        result = []
        for i in range(self.poles_list.count()):
            item = self.poles_list.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.data(Qt.UserRole))
        return result

    def _update_fields(self, *_):
        hub = self._selected_layer(self.hub_combo)
        sub = self._selected_layer(self.sub_combo)
        cable = self._selected_layer(self.cable_combo)
        poles = self._selected_poles()
        self._set_field_combo(self.hub_name_field, hub, ['Name', 'Hub_Box_Name', 'Hub Box Name'])
        self._set_field_combo(self.sub_name_field, sub, ['Name', 'Subbox_Name', 'Sub Box Name'])
        self._set_field_combo(self.hp_field, sub, ['HP Count', 'HP_Count', 'HPs', 'HP_Counts'])
        self._set_field_combo(self.span_field, cable, ['Span', 'SPAN'])
        pole_layer = poles[0] if poles else None
        self._set_field_combo(self.pole_name_field, pole_layer, ['Name', 'Pole_Name', 'Pole No', 'Pole_No'])

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save Excel Workbook',
                                               self.output_edit.text() or 'ODN_Export_Information.xlsx',
                                               'Excel Workbook (*.xlsx)')
        if path:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            self.output_edit.setText(path)

    def _export(self):
        hub = self._selected_layer(self.hub_combo)
        sub = self._selected_layer(self.sub_combo)
        cable = self._selected_layer(self.cable_combo)
        poles = self._selected_poles()
        output = self.output_edit.text().strip()
        if not all([hub, sub, cable]) or not poles:
            QMessageBox.warning(self, 'Missing layers', '请选择 HUB BOX、SUB BOX、Distribution Cable 图层，并至少勾选一个杆子图层。')
            return
        if not output:
            self._browse_output()
            output = self.output_edit.text().strip()
        if not output:
            return
        if not output.lower().endswith('.xlsx'):
            output += '.xlsx'
            self.output_edit.setText(output)

        mappings = {
            'hub_name': self.hub_name_field.currentText(),
            'sub_name': self.sub_name_field.currentText(),
            'pole_name': self.pole_name_field.currentText(),
            'hp_count': self.hp_field.currentText(),
            'span': self.span_field.currentText(),
        }
        if not all(mappings.values()):
            QMessageBox.warning(self, 'Missing fields', '请检查 Name、HP Count、Pole Name 和 Span 字段映射。')
            return
        progress = QProgressDialog('正在读取图层并生成 Excel...', '取消', 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        try:
            result = export_information(
                hub_layer=hub, sub_layer=sub, cable_layer=cable,
                pole_layers=poles, fields=mappings,
                output_path=output, pole_radius_m=float(self.radius_spin.value()),
                progress=progress
            )
            progress.close()
            if result.get('cancelled'):
                QMessageBox.information(self, 'Cancelled', '导出已取消，未生成完整文件。')
                return
            msg = ('Excel 导出完成。\n\n'
                   'SUB BOX 记录：{rows}\n'
                   '杆子匹配成功：{matched}/{total}\n'
                   '名称解析失败：{parse_errors}\n'
                   'HUB BOX 未找到：{hub_missing}\n'
                   '未匹配到 Distribution Cable：{cable_missing}\n\n'
                   'Excel：{path}\n'
                   '第二个工作表为 QA Report。').format(**result, path=output)
            QMessageBox.information(self, 'Export complete', msg)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, 'Export failed', '导出失败：\n{}'.format(exc))
