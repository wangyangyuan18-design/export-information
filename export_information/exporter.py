# -*- coding: utf-8 -*-
"""ODN layer matching and export business logic."""

import math
from .naming import parse_subbox_name as _parse_subbox_name, natural_hub_key as _natural_hub_key
import os
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject
from .xlsx_writer import write_workbook

_WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')


def _text(value):
    if value is None:
        return ''
    return str(value).strip()


def _key(value):
    return ''.join(ch.upper() for ch in _text(value) if ch.isalnum())


def _to_wgs84_point(layer, feature, project):
    geom = feature.geometry()
    if geom is None or geom.isNull() or geom.isEmpty():
        return None
    geom = QgsGeometry(geom)
    src = layer.crs()
    if src.isValid() and src != _WGS84:
        transform = QgsCoordinateTransform(src, _WGS84, project)
        geom.transform(transform)
    if geom.isNull() or geom.isEmpty():
        return None
    if geom.type() == 0:  # Point
        if geom.isMultipart():
            pts = geom.asMultiPoint()
            if not pts:
                return None
            p = pts[0]
            return (float(p.x()), float(p.y()))
        p = geom.asPoint()
        return (float(p.x()), float(p.y()))
    p = geom.centroid().asPoint()
    return (float(p.x()), float(p.y()))


def _to_wgs84_geometry(layer, feature, project):
    geom = feature.geometry()
    if geom is None or geom.isNull() or geom.isEmpty():
        return None
    geom = QgsGeometry(geom)
    src = layer.crs()
    if src.isValid() and src != _WGS84:
        transform = QgsCoordinateTransform(src, _WGS84, project)
        geom.transform(transform)
    if geom.isNull() or geom.isEmpty():
        return None
    return geom


def _haversine_m(a, b):
    """Geodesic point-to-point distance in metres; points are (lon, lat)."""
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return 6371008.8 * 2.0 * math.asin(min(1.0, math.sqrt(h)))


def _geom_point_distance_m(point, geom):
    if geom is None or geom.isEmpty():
        return None
    point_geom = QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1]))
    try:
        closest = geom.closestPoint(point_geom)
        if closest is None or closest.isEmpty():
            return None
        p = closest.asPoint()
        return _haversine_m(point, (float(p.x()), float(p.y())))
    except Exception:
        return None


def _attribute(feature, field_name):
    if not field_name:
        return ''
    try:
        return feature[field_name]
    except Exception:
        return ''


def _nearest_pole(point, pole_records, radius_m):
    if point is None:
        return None, None
    best = None
    best_distance = None
    for record in pole_records:
        distance = _haversine_m(point, record['point'])
        if best_distance is None or distance < best_distance:
            best = record
            best_distance = distance
    if best is not None and best_distance <= radius_m:
        return best, best_distance
    return None, best_distance


def _as_excel_number(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return ''
        return value
    text = _text(value)
    if not text:
        return ''
    try:
        number = float(text.replace(',', ''))
        if number.is_integer():
            return int(number)
        return number
    except Exception:
        return text


def _build_cable_records(cable_layer, span_field, project):
    records = []
    for feature in cable_layer.getFeatures():
        geom = _to_wgs84_geometry(cable_layer, feature, project)
        attrs = []
        for field in cable_layer.fields():
            val = _text(_attribute(feature, field.name()))
            if val:
                attrs.append((field.name(), val))
        records.append({
            'feature': feature,
            'span': _as_excel_number(_attribute(feature, span_field)),
            'geom': geom,
            'attrs': attrs,
            'fid': feature.id(),
        })
    return records


def _match_cable(point, hub_name, link_no, cable_records):
    if not cable_records:
        return None, None, 'Distribution Cable 图层没有有效要素'
    # Prefer an explicit HUB/L identifier found in any cable attribute.
    target = _key('{}L{}'.format(hub_name, link_no))
    strong = []
    for record in cable_records:
        matched = False
        for _, value in record['attrs']:
            if target and target in _key(value):
                matched = True
                break
        if matched:
            strong.append(record)
    candidates = strong
    match_method = '按属性名称匹配'
    if not candidates:
        # Some projects store only L1/L2... in a link/port field.
        token = 'L{}'.format(link_no).upper()
        for record in cable_records:
            if any(('link' in field.lower() or 'port' in field.lower()) and value.upper() == token
                   for field, value in record['attrs']):
                candidates.append(record)
        match_method = '按链路字段匹配'
    if not candidates:
        candidates = cable_records
        match_method = '按空间最近要素匹配'

    ranked = []
    for record in candidates:
        distance = _geom_point_distance_m(point, record['geom']) if point is not None else None
        if distance is not None:
            ranked.append((distance, record))
    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1]['fid']))
        distance, record = ranked[0]
        return record, distance, match_method
    # Attribute match still provides a Span if the cable geometry is missing.
    if candidates:
        candidates.sort(key=lambda rec: rec['fid'])
        return candidates[0], None, match_method + '（无有效几何）'
    return None, None, '无法匹配 Distribution Cable'


def _format_coord(point):
    if point is None:
        return ''
    lon, lat = point
    return '{:.6f}, {:.6f}'.format(lat, lon)


def _progress_cancelled(progress):
    return bool(progress and progress.wasCanceled())


def export_information(hub_layer, sub_layer, cable_layer, pole_layers, fields,
                       output_path, pole_radius_m=3.0, progress=None):
    project = QgsProject.instance()
    qa = []

    # Build a pooled pole index from every checked pole layer.
    pole_records = []
    pole_name_field = fields.get('pole_name')
    for pole_layer in pole_layers:
        for feature in pole_layer.getFeatures():
            point = _to_wgs84_point(pole_layer, feature, project)
            if point is None:
                qa.append(['WARNING', pole_layer.name(), str(feature.id()), '杆子几何无效', '无法读取点坐标'])
                continue
            name = _text(_attribute(feature, pole_name_field))
            if not name:
                for candidate in ('Name', 'Pole_Name', 'Pole No', 'Pole_No'):
                    name = _text(_attribute(feature, candidate))
                    if name:
                        break
            pole_records.append({'name': name, 'point': point, 'layer': pole_layer.name(), 'fid': feature.id()})

    # Index HUB BOX features by their Name value.
    hubs = {}
    for feature in hub_layer.getFeatures():
        hub_name = _text(_attribute(feature, fields['hub_name']))
        if not hub_name:
            continue
        hubs.setdefault(_key(hub_name), []).append({
            'feature': feature,
            'name': hub_name,
            'point': _to_wgs84_point(hub_layer, feature, project),
        })

    cable_records = _build_cable_records(cable_layer, fields['span'], project)
    sub_features = list(sub_layer.getFeatures())
    total = len(sub_features)
    rows = []
    matched_box_poles = 0
    total_box_pole_checks = 0
    parse_errors = 0
    hub_missing = 0
    cable_missing = 0
    seen_names = set()

    for idx, feature in enumerate(sub_features):
        if _progress_cancelled(progress):
            return {'cancelled': True}
        sub_name = _text(_attribute(feature, fields['sub_name']))
        parsed = _parse_subbox_name(sub_name)
        sub_point = _to_wgs84_point(sub_layer, feature, project)
        hp_count = _as_excel_number(_attribute(feature, fields['hp_count']))

        hub_name = ''
        link_no = None
        sequence_no = None
        if parsed:
            hub_name, link_no, sequence_no = parsed
        else:
            parse_errors += 1
            qa.append(['ERROR', 'SUB BOX', sub_name or str(feature.id()), 'SUB BOX 名称解析失败',
                       '要求格式类似 KIM-HB09L4S4（HUB ID + L编号 + S编号）'])

        hub_entry = None
        hub_candidates = hubs.get(_key(hub_name), []) if hub_name else []
        if len(hub_candidates) == 1:
            hub_entry = hub_candidates[0]
        elif len(hub_candidates) > 1:
            hub_entry = hub_candidates[0]
            qa.append(['WARNING', 'HUB BOX', hub_name, 'HUB BOX Name 重复',
                       '找到 {} 个同名要素，暂取图层中的第一个。'.format(len(hub_candidates))])
        else:
            if parsed:
                hub_missing += 1
                qa.append(['ERROR', 'SUB BOX', sub_name, '所属 HUB BOX 未找到',
                           '按名称前缀查找 HUB BOX：{}'.format(hub_name)])

        hub_pole_name = ''
        hub_location = ''
        if hub_entry:
            total_box_pole_checks += 1
            pole, distance = _nearest_pole(hub_entry['point'], pole_records, pole_radius_m)
            if pole:
                matched_box_poles += 1
                hub_pole_name = pole['name']
                hub_location = _format_coord(pole['point'])
            else:
                qa.append(['WARNING', 'HUB BOX', hub_name, '3 米范围内未匹配到杆子',
                           '最近杆子距离：{}'.format('{:.2f} m'.format(distance) if distance is not None else '不可计算')])

        sub_pole_name = ''
        sub_location = ''
        total_box_pole_checks += 1
        pole, pole_distance = _nearest_pole(sub_point, pole_records, pole_radius_m)
        if pole:
            matched_box_poles += 1
            sub_pole_name = pole['name']
            sub_location = _format_coord(pole['point'])
        else:
            qa.append(['WARNING', 'SUB BOX', sub_name or str(feature.id()), '3 米范围内未匹配到杆子',
                       '最近杆子距离：{}'.format('{:.2f} m'.format(pole_distance) if pole_distance is not None else '不可计算')])

        span = ''
        if parsed and sub_point is not None:
            cable_record, cable_distance, cable_method = _match_cable(sub_point, hub_name, link_no, cable_records)
            if cable_record:
                span = cable_record['span']
                if cable_method.startswith('按空间最近'):
                    qa.append(['INFO', 'Distribution Cable', sub_name, 'Span 使用空间最近匹配',
                               '匹配方式：{}；距离：{}'.format(cable_method,
                                   '{:.2f} m'.format(cable_distance) if cable_distance is not None else '不可计算')])
                if cable_distance is not None and cable_distance > 3.0:
                    qa.append(['WARNING', 'Distribution Cable', sub_name, '最近 Distribution Cable 距离超过 3 米',
                               '{:.2f} m；请复核 Span 是否属于该 SUB BOX。'.format(cable_distance)])
                if span == '':
                    qa.append(['WARNING', 'Distribution Cable', sub_name, '匹配到光缆但 Span 为空',
                               '请检查所选 Span 字段及该要素属性。'])
            else:
                cable_missing += 1
                qa.append(['WARNING', 'SUB BOX', sub_name, '未匹配到 Distribution Cable', cable_method or ''])
        elif parsed:
            cable_missing += 1
            qa.append(['WARNING', 'SUB BOX', sub_name, 'SUB BOX 几何无效，无法空间匹配光缆', ''])

        if sub_name and _key(sub_name) in seen_names:
            qa.append(['WARNING', 'SUB BOX', sub_name, 'SUB BOX Name 重复', '自然排序后仍保留重复记录。'])
        seen_names.add(_key(sub_name))

        rows.append({
            'sort_hub': hub_name,
            'sort_link': link_no if link_no is not None else 999999,
            'sort_seq': sequence_no if sequence_no is not None else 999999,
            'sort_name': sub_name.upper(),
            'values': [
                hub_location,
                hub_pole_name,
                hub_name,
                'L{}'.format(link_no) if link_no is not None else '',
                span,
                1,
                sub_location,
                sub_pole_name,
                sub_name,
                hp_count,
                1,
            ]
        })
        if progress:
            progress.setLabelText('正在处理 SUB BOX：{} / {}'.format(idx + 1, total))
            if total:
                progress.setValue(int((idx + 1) * 100.0 / total))

    rows.sort(key=lambda row: (_natural_hub_key(row['sort_hub']), row['sort_link'], row['sort_seq'], row['sort_name']))
    data = [row['values'] for row in rows]

    if _progress_cancelled(progress):
        return {'cancelled': True}
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    write_workbook(output_path, data, qa, pole_radius_m)

    return {
        'cancelled': False,
        'rows': len(data),
        'matched': matched_box_poles,
        'total': total_box_pole_checks,
        'parse_errors': parse_errors,
        'hub_missing': hub_missing,
        'cable_missing': cable_missing,
        'path': output_path,
    }
