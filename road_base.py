# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
from mathutils import Vector, Matrix
import bmesh
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from mathutils.geometry import intersect_line_plane
from pyclothoids import Clothoid
from math import pi
from math import ceil

def get_new_id_opendrive(context):
    '''
        Generate and return new ID for OpenDRIVE objects using a dummy object
        for storage.
    '''
    dummy_obj = context.scene.objects.get('id_xodr_next')
    if dummy_obj is None:
        dummy_obj = bpy.data.objects.new('id_xodr_next',None)
        # Do not render
        dummy_obj.hide_viewport = True
        dummy_obj.hide_render = True
        dummy_obj['id_xodr_next'] = 1
        link_object_opendrive(context, dummy_obj)
    id_next = dummy_obj['id_xodr_next']
    dummy_obj['id_xodr_next'] += 1
    return id_next

def get_new_id_openscenario(context):
    '''
        Generate and return new ID for OpenSCENARIO objects using a dummy object
        for storage.
    '''
    dummy_obj = context.scene.objects.get('id_xosc_next')
    if dummy_obj is None:
        dummy_obj = bpy.data.objects.new('id_xosc_next',None)
        # Do not render
        dummy_obj.hide_viewport = True
        dummy_obj.hide_render = True
        dummy_obj['id_xosc_next'] = 0
        link_object_openscenario(context, dummy_obj, subcategory=None)
    id_next = dummy_obj['id_xosc_next']
    dummy_obj['id_xosc_next'] += 1
    return id_next

def ensure_collection_opendrive(context):
    if not 'OpenDRIVE' in bpy.data.collections:
        collection = bpy.data.collections.new('OpenDRIVE')
        context.scene.collection.children.link(collection)

def ensure_collection_openscenario(context):
    if not 'OpenSCENARIO' in bpy.data.collections:
        collection = bpy.data.collections.new('OpenSCENARIO')
        context.scene.collection.children.link(collection)

def ensure_subcollection_openscenario(context, subcollection):
    ensure_collection_openscenario(context)
    collection_osc = bpy.data.collections['OpenSCENARIO']
    if not subcollection in collection_osc.children:
        collection = bpy.data.collections.new(subcollection)
        collection_osc.children.link(collection)

def collection_exists(collection_path):
    '''
        Check if a (sub)collection with path given as list exists.
    '''
    if not isinstance(collection_path, list):
        collection_path = [collection_path]
    root = collection_path.pop(0)
    if not root in bpy.data.collections:
        return False
    else:
        if len(collection_path) == 0:
            return True
        else:
            return collection_exists(collection_path)

def link_object_opendrive(context, obj):
    '''
        Link object to OpenDRIVE scene collection.
    '''
    ensure_collection_opendrive(context)
    collection = bpy.data.collections.get('OpenDRIVE')
    collection.objects.link(obj)

def link_object_openscenario(context, obj, subcategory=None):
    '''
        Link object to OpenSCENARIO scene collection.
    '''
    if subcategory is None:
        ensure_collection_openscenario(context)
        collection = bpy.data.collections.get('OpenSCENARIO')
        collection.objects.link(obj)
    else:
        ensure_subcollection_openscenario(context, subcategory)
        collection = bpy.data.collections.get('OpenSCENARIO').children.get(subcategory)
        collection.objects.link(obj)

def get_object_xodr_by_id(id_xodr):
    '''
        Get reference to OpenDRIVE object by ID, return None if not found.
    '''
    collection = bpy.data.collections.get('OpenDRIVE')
    for obj in collection.objects:
        if 'id_xodr' in obj:
            if obj['id_xodr'] == id_xodr:
                return obj

def create_object_xodr_links(obj, link_type, cp_type_other, id_other, id_junction):
    '''
        Create OpenDRIVE predecessor/successor linkage for current object with
        other object.
    '''

    # TODO try to refactor this whole method and better separate all cases:
    #   1. Road to road with all start and end combinations
    #   2. Junction to road and road to junction with start and end combinations
    #   3. Road to direct junction and direct junction to road
    #   4. Unify old and new junction implementation or implement as separate
    #      case

    # Case: road to junction or junction to junction
    if id_junction != None:
        obj_junction = get_object_xodr_by_id(id_junction)

    # 1. Set the link parameters of the object itself
    if 'road' in obj.name:
        if link_type == 'start':
            obj['link_predecessor_id_l'] = id_other
            obj['link_predecessor_cp_l'] = cp_type_other
            if id_junction != None:
                if obj['dsc_type'] == 'junction_connecting_road':
                    # Case: connecting road to junction + incoming road
                    obj['id_junction'] = id_junction
                elif obj_junction['dsc_type'] == 'junction_direct':
                    # Case: road to direct junction
                    obj['id_direct_junction_start'] = id_junction
        else:
            obj['link_successor_cp_l'] = cp_type_other
            obj['link_successor_id_l'] = id_other
            if id_junction != None:
                if obj['dsc_type'] == 'junction_connecting_road':
                    # Case: connecting road to junction + incoming road
                    obj['id_junction'] = id_junction
                elif obj_junction['dsc_type'] == 'junction_direct':
                    # Case: road to direct junction
                    obj['id_direct_junction_end'] = id_junction
    elif 'junction' in obj.name:
        # Case: junction to road
        if link_type == 'start':
            obj['incoming_roads']['cp_left'] = id_other
        else:
            obj['incoming_roads']['cp_right'] = id_other

    # 2. Set the link parameters of the other object we are linking with
    obj_other = get_object_xodr_by_id(id_other)
    if 'road' in obj_other.name:
        if 'road' in obj.name:
            # Case: road to road
            if link_type == 'start':
                cp_type = 'cp_start_l'
            else:
                cp_type = 'cp_end_l'
        if 'junction' in obj.name:
            # Case: junction to road
            if link_type == 'start':
                cp_type = 'cp_left'
            else:
                cp_type = 'cp_right'
        if cp_type_other == 'cp_start_l':
            obj_other['link_predecessor_id_l'] = obj['id_xodr']
            obj_other['link_predecessor_cp_l'] = cp_type
            if id_junction != None:
                obj_other['id_direct_junction_start'] = id_junction
        elif cp_type_other == 'cp_start_r':
            obj_other['link_predecessor_id_r'] = obj['id_xodr']
            obj_other['link_predecessor_cp_r'] = cp_type
            if id_junction != None:
                obj_other['id_direct_junction_start'] = id_junction
        elif cp_type_other == 'cp_end_l':
            obj_other['link_successor_id_l'] = obj['id_xodr']
            obj_other['link_successor_cp_l'] = cp_type
            if id_junction != None:
                obj_other['id_direct_junction_end'] = id_junction
        elif cp_type_other == 'cp_end_r':
            obj_other['link_successor_id_r'] = obj['id_xodr']
            obj_other['link_successor_cp_r'] = cp_type
            if id_junction != None:
                obj_other['id_direct_junction_end'] = id_junction
    elif obj_other.name.startswith('junction'):
        # Case: road to junction or junction to junction
        obj_other['incoming_roads'][cp_type_other] = obj['id_xodr']

def get_width_road_sides(obj):
    '''
        Return the width of the left and right road sid e calculated by suming up
        all lane widths.
    '''
    # TODO take edge lines and opening/closing lanes into account
    width_left = 0
    width_right = 0
    for width_lane_left in obj['lanes_left_widths']:
        width_left += width_lane_left
    for width_lane_right in obj['lanes_right_widths']:
        width_right += width_lane_right
    return width_left, width_right

def select_activate_object(context, obj):
    '''
        Select and activate object.
    '''
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(state=True)
    context.view_layer.objects.active = obj

def remove_duplicate_vertices(context, obj):
    '''
        Remove duplicate vertices from a object's mesh
    '''
    context.view_layer.objects.active = obj
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.001,
                use_unselected=True, use_sharp_edge_from_normals=False)
    bpy.ops.object.editmode_toggle()

def get_mouse_vectors(context, event):
    '''
        Return view vector and ray origin of mouse pointer position.
    '''
    region = context.region
    rv3d = context.region_data
    co2d = (event.mouse_region_x, event.mouse_region_y)
    view_vector_mouse = region_2d_to_vector_3d(region, rv3d, co2d)
    ray_origin_mouse = region_2d_to_origin_3d(region, rv3d, co2d)
    return view_vector_mouse, ray_origin_mouse

def mouse_to_xy_parallel_plane(context, event, z):
    '''
        Convert mouse pointer position to 3D point in plane parallel to xy-plane
        at height z.
    '''
    view_vector_mouse, ray_origin_mouse = get_mouse_vectors(context, event)
    point = intersect_line_plane(ray_origin_mouse, ray_origin_mouse + view_vector_mouse,
        (0, 0, z), (0, 0, 1), False)
    # Fix parallel plane issue
    if point is None:
        point = intersect_line_plane(ray_origin_mouse, ray_origin_mouse + view_vector_mouse,
            (0, 0, 0), view_vector_mouse, False)
    return point

def mouse_to_elevation(context, event, point):
    '''
        Convert mouse pointer position to elevation above point projected to xy plane.
    '''
    view_vector_mouse, ray_origin_mouse = get_mouse_vectors(context, event)
    point_elevation = intersect_line_plane(ray_origin_mouse, ray_origin_mouse + view_vector_mouse,
        point.to_2d().to_3d(), view_vector_mouse.to_2d().to_3d(), False)
    if point_elevation == None:
        return 0
    else:
        return point_elevation.z

def raycast_mouse_to_object(context, event, filter=None):
    '''
        Convert mouse pointer position to hit obj of DSC type.
    '''
    view_vector_mouse, ray_origin_mouse = get_mouse_vectors(context, event)
    hit, point, normal, index_face, obj, matrix_world = context.scene.ray_cast(
        depsgraph=context.view_layer.depsgraph,
        origin=ray_origin_mouse,
        direction=view_vector_mouse)
    # Filter object type
    if hit:
        if filter is not None:
            # Return hit only if not filtered out
            if filter in obj:
                return True, point, obj
            else:
                return False, point, None
        else:
            # No filter, return any hit
            return True, point, obj
    else:
        # No hit
        return False, point, None

def point_to_road_connector(obj, point):
    '''
        Get a snapping point and heading from an existing road.
    '''
    dist_start_l = (Vector(obj['cp_start_l']) - point).length
    dist_start_r = (Vector(obj['cp_start_r']) - point).length
    dist_end_l = (Vector(obj['cp_end_l']) - point).length
    dist_end_r = (Vector(obj['cp_end_r']) - point).length
    distances = [dist_start_l, dist_start_r, dist_end_l, dist_end_r]
    arg_min_dist = distances.index(min(distances))
    width_left, width_right = get_width_road_sides(obj)
    if arg_min_dist == 0:
        return 'cp_start_l', Vector(obj['cp_start_l']), obj['geometry']['heading_start'] - pi, \
            obj['geometry']['curvature_start'], obj['geometry']['slope_start'], \
            width_left, width_right
    if arg_min_dist == 1:
        return 'cp_start_r', Vector(obj['cp_start_r']), obj['geometry']['heading_start'] - pi, \
            obj['geometry']['curvature_start'], obj['geometry']['slope_start'], \
            width_left, width_right
    elif arg_min_dist == 2:
        return 'cp_end_l', Vector(obj['cp_end_l']), obj['geometry']['heading_end'], \
            obj['geometry']['curvature_end'], obj['geometry']['slope_end'], \
            width_left, width_right
    else:
        return 'cp_end_r', Vector(obj['cp_end_r']), obj['geometry']['heading_end'], \
            obj['geometry']['curvature_end'], obj['geometry']['slope_end'], \
            width_left, width_right

def point_to_junction_joint(obj, point):
    '''
        Get joint parameters from closest joint including incoming road ID,
        contact point type, vector and heading from an existing junction.
    '''
    # Calculate which connecting point is closest to input point
    joints = obj['joints']
    distances = []
    cp_vectors = []
    for idx, joint in enumerate(joints):
        cp_vectors.append(Vector(joint['contact_point_vec']))
        distances.append((Vector(joint['contact_point_vec']) - point).length)
    arg_min_dist = distances.index(min(distances))
    return joints[arg_min_dist]['id_incoming'], joints[arg_min_dist]['contact_point'], \
        cp_vectors[arg_min_dist], joints[arg_min_dist]['heading']

def point_to_junction_connector(obj, point):
    '''
        Get a snapping point and heading from an existing junction.
        # TODO later remove this path and unify junctions
    '''
    # Calculate which connecting point is closest to input point
    cps = ['cp_left', 'cp_down', 'cp_right', 'cp_up']
    distances = []
    cp_vectors = []
    for cp in cps:
        distances.append((Vector(obj[cp]) - point).length)
        cp_vectors.append(Vector(obj[cp]))
    headings = [obj['hdg_left'], obj['hdg_down'], obj['hdg_right'], obj['hdg_up']]
    arg_min_dist = distances.index(min(distances))
    return cps[arg_min_dist], cp_vectors[arg_min_dist], headings[arg_min_dist]

def point_to_object_connector(obj, point):
    '''
        Get a snapping point and heading from a dynamic object.
    '''
    return 'cp_axle_rear', Vector(obj['position']), obj['hdg']

def project_point_vector(point_start, heading_start, point_selected):
    '''
        Project selected point to vector.
    '''
    vector_selected = point_selected - point_start
    if vector_selected.length > 0:
        vector_object = Vector((1.0, 0.0, 0.0))
        vector_object.rotate(Matrix.Rotation(heading_start, 4, 'Z'))
        return point_start + vector_selected.project(vector_object)
    else:
        return point_selected

def mouse_to_object_params(context, event, filter):
    '''
        Check if an object is hit and return a connection (snapping) point. In
        case of OpenDRIVE objects including heading, curvature and slope. Filter
        may be used to distinguish between OpenDRIVE, OpenSCENARIO and any
        object (set filter to None).
    '''
    # Initialize with some defaults in case nothing is hit
    hit = False
    id_obj = None
    id_junction = None
    point_type = None
    snapped_point = Vector((0.0,0.0,0.0))
    heading = 0
    curvature = 0
    slope = 0
    width_left = 0
    width_right = 0
    # Do the raycasting
    if filter is None:
        dsc_hit, point_raycast, obj = raycast_mouse_to_object(context, event, filter=None)
    else:
        dsc_hit, point_raycast, obj = raycast_mouse_to_object(context, event, filter='dsc_category')
    if dsc_hit:
        # DSC mesh hit
        if filter == 'OpenDRIVE':
            if obj['dsc_category'] == 'OpenDRIVE':
                if obj['dsc_type'] == 'road':
                    hit = True
                    point_type, snapped_point, heading, curvature, \
                    slope, width_left, width_right = point_to_road_connector(obj, point_raycast)
                    id_obj = obj['id_xodr']
                    if obj['road_split_type'] == 'end':
                        if point_type == 'cp_end_l' or point_type == 'cp_end_r':
                            if 'id_direct_junction_end' in obj:
                                id_junction = obj['id_direct_junction_end']
                    if obj['road_split_type'] == 'start':
                        if point_type == 'cp_start_l' or point_type == 'cp_start_r':
                            if 'id_direct_junction_start' in obj:
                                id_junction = obj['id_direct_junction_start']
        if filter == 'OpenDRIVE':
            if obj.name.startswith('junction_4way'):
                # TODO later remove this path and unify junctions
                hit = True
                point_type, snapped_point, heading = point_to_junction_connector(obj, point_raycast)
                # For the legacy junction we do not explicitly model the
                # connecting roads hence we set both IDs to the junction ID
                id_obj = obj['id_xodr']
                id_junction = obj['id_xodr']
        if filter == 'OpenDRIVE_junction':
            if obj.name.startswith('junction_area'):
                hit = True
                id_incoming, point_type, snapped_point, heading = point_to_junction_joint(obj, point_raycast)
                id_obj = id_incoming
                id_junction = obj['id_xodr']
        elif filter == 'OpenSCENARIO':
            if obj['dsc_category'] == 'OpenSCENARIO':
                hit = True
                point_type, snapped_point, heading = point_to_object_connector(obj, point_raycast)
                id_obj = obj.name
        elif filter == 'surface':
            hit = True
            point_type = 'surface'
            snapped_point = point_raycast
            id_obj = obj.name
    return hit ,{'id_obj': id_obj,
                 'id_junction': id_junction,
                 'point': snapped_point,
                 'type': point_type,
                 'heading': heading,
                 'curvature': curvature,
                 'slope': slope,
                 'width_left': width_left,
                 'width_right': width_right,}

def assign_road_materials(obj):
    '''
        Assign materials for asphalt and markings to object.
    '''
    default_materials = {
        'road_asphalt': [.3, .3, .3, 1],
        'road_mark_white': [.9, .9, .9, 1],
        'road_mark_yellow': [.85, .63, .0, 1],
        'grass': [.05, .6, .01, 1],
    }
    for key in default_materials.keys():
        material = bpy.data.materials.get(key)
        if material is None:
            material = bpy.data.materials.new(name=key)
            material.diffuse_color = (default_materials[key][0],
                                      default_materials[key][1],
                                      default_materials[key][2],
                                      default_materials[key][3])
        obj.data.materials.append(material)

def assign_object_materials(obj, color):
    # Get road material
    material = bpy.data.materials.get(get_paint_material_name(color))
    if material is None:
        # Create material
        material = bpy.data.materials.new(name=get_paint_material_name(color))
        material.diffuse_color = color
    obj.data.materials.append(material)

def get_paint_material_name(color):
    '''
        Calculate material name from name string and Blender color
    '''
    return 'vehicle_paint' + '_{:.2f}_{:.2f}_{:.2f}'.format(*color[0:4])

def get_material_index(obj, material_name):
    '''
        Return index of material slot based on material name.
    '''
    for idx, material in enumerate(obj.data.materials):
        if material.name == material_name:
            return idx
    return None

def replace_mesh(obj, mesh):
    '''
        Replace existing mesh
    '''
    # Delete old mesh data
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    verts = [v for v in bm.verts]
    bmesh.ops.delete(bm, geom=verts, context='VERTS')
    bm.to_mesh(obj.data)
    bm.free()
    # Set new mesh data
    obj.data = mesh

def triangulate_quad_mesh(obj):
    '''
        Triangulate then quadify the ngon mesh of an object.
    '''
    # Triangulate
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    # Tris to quads is missing in bmesh so use bpy.ops.mesh instead
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.tris_convert_to_quads(materials=True)
    bpy.ops.object.mode_set(mode='OBJECT')

def kmh_to_ms(speed):
    return speed / 3.6

def get_obj_custom_property(dsc_category, subcategory, obj_name, property):
    if collection_exists([dsc_category,subcategory]):
        for obj in bpy.data.collections[dsc_category].children[subcategory].objects:
            if obj.name == obj_name:
                if property in obj:
                    return obj[property]
                else:
                    return None
    else:
        return None

# ======================================= Class definitions =======================================
params_cross_section = {
    'two_lanes_default': {
        'sides': ['left', 'left', 'center', 'right', 'right'],
        'widths': [0.20, 3.75, 0.0, 3.75, 0.20],
        'widths_change': ['none', 'none', 'none', 'none', 'none'],
        'types': ['border', 'driving', 'center', 'driving', 'border'],
        'road_mark_types': ['none', 'solid', 'broken', 'solid', 'none'],
        'road_mark_weights': ['none', 'standard', 'standard', 'standard', 'none'],
        'road_mark_widths': [0.0, 0.12, 0.12, 0.12, 0.0],
        'road_mark_colors': ['none', 'white', 'white', 'white', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 5,
    },
    # Typical German road cross sections
    # See:
    #   https://de.wikipedia.org/wiki/Richtlinien_f%C3%BCr_die_Anlage_von_Stra%C3%9Fen_%E2%80%93_Querschnitt
    #   https://de.wikipedia.org/wiki/Richtlinien_f%C3%BCr_die_Anlage_von_Autobahnen
    #   https://de.wikipedia.org/wiki/Entwurfsklasse
    #   https://www.beton.wiki/index.php?title=Regelquerschnitt_im_Stra%C3%9Fenbau
    #   https://www.vsvi-mv.de/fileadmin/Medienpool/Seminarunterlagen/Seminare_2012/Vortrag_1_-_neue_RAL_Frau_Vetters.pdf
    #   https://dsgs.de/leitfaden-fahrbahnmarkierung1.html
    #
    'ekl4_rq9': {
        'sides': ['left', 'left', 'center', 'right', 'right', 'right'],
        'widths': [1.5, 0.5, 0.0, 3.5, 0.5, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'border', 'center', 'driving', 'border', 'shoulder'],
        'road_mark_types': ['none', 'none', 'broken', 'broken', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'standard', 'standard', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.12, 0.12, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'white', 'white', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 6,
    },
    'ekl3_rq11': {
        'sides': ['left', 'left', 'left', 'center', 'right', 'right', 'right'],
        'widths': [1.5, 0.50, 3.5, 0.0, 3.5, 0.50, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'border', 'driving', 'center', 'driving', 'border', 'shoulder'],
        'road_mark_types': ['none', 'none', 'solid', 'broken', 'solid', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'standard', 'standard', 'standard', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.12, 0.12, 0.12, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'white', 'white', 'white', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 7,
    },
    'eka1_rq31': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right', 'right', 'right', 'right'],
        'widths': [1.5, 3.0, 0.75, 3.75, 3.75, 0.75, 2.0, 0.0, 2.0, 0.75, 3.75, 3.75, 0.75, 3.0, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 15,
    },
    'eka1_rq31_exit_right_open': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'],
        'widths': [1.5, 3.0, 0.75, 3.75, 3.75, 0.75, 2.0, 0.0, 2.0, 0.75, 3.75, 3.75, 3.75, 0.75, 3.0, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'open', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving', 'exit', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'broken', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'bold', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 16,
    },
    'eka1_rq31_exit_right': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'],
        'widths': [1.5, 3.0, 0.75, 3.75, 3.75, 0.75, 2.0, 0.0, 2.0, 0.75, 3.75, 3.75, 3.75, 0.75, 3.0, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving', 'exit', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'broken', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'bold', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'end',
        'road_split_lane_idx': 12,
    },
    'eka1_rq31_exit_right_continuation': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right'],
        'widths': [1.5, 3.0, 0.75, 3.75, 3.75, 0.75, 2.0, 0.0, 2.0, 0.75, 3.75, 3.75],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'solid'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'bold'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.30],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white'],
        'road_split_type': 'none',
        'road_split_lane_idx': 12,
    },
    'eka1_rq31_entry_right': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'],
        'widths': [1.5, 3.0, 0.75, 3.75, 3.75, 0.75, 2.0, 0.0, 2.0, 0.75, 3.75, 3.75, 3.75, 0.75, 3.0, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving', 'exit', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'broken', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'bold', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'start',
        'road_split_lane_idx': 12,
    },
    'eka1_rq31_entry_right_close': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'],
        'widths': [1.5, 3.0, 0.75, 3.75, 3.75, 0.75, 2.0, 0.0, 2.0, 0.75, 3.75, 3.75, 3.75, 0.75, 3.0, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'close', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving', 'exit', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'broken', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'bold', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.30, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 16,
    },
    'eka1_rq36': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'],
        'widths': [1.5, 2.5, 0.5, 3.75, 3.5, 3.5, 0.75, 2.0, 0.0, 2.0, 0.75, 3.5, 3.5, 3.75, 0.5, 2.5, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving', 'driving', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'broken', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'standard', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.15, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 17,
    },
    'eka1_rq43_5': {
        'sides': ['left', 'left', 'left', 'left', 'left', 'left', 'left', 'left', 'left', 'center', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right'],
        'widths': [2.5, 2.5, 0.5, 3.75, 3.75, 3.5, 3.5, 0.75, 2.0, 0.0, 2.0, 0.75, 3.5, 3.5, 3.75, 3.75, 0.5, 2.5, 2.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none', 'none'],
        'types': ['shoulder', 'stop', 'border', 'driving', 'driving', 'driving', 'driving', 'border', 'median', 'center', 'median', 'border', 'driving', 'driving', 'driving', 'driving', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['none', 'none', 'none', 'solid', 'broken', 'broken', 'broken', 'solid', 'none', 'none', 'none', 'solid', 'broken', 'broken', 'broken', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['none', 'none', 'none', 'bold', 'standard', 'standard', 'standard', 'bold', 'none', 'none', 'none', 'bold', 'standard', 'standard', 'standard', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.0, 0.0, 0.0, 0.30, 0.15, 0.15, 0.15, 0.30, 0.0, 0.0, 0.0, 0.30, 0.15, 0.15, 0.15, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['none', 'none', 'none', 'white', 'white', 'white', 'white', 'white', 'none', 'none', 'none', 'white', 'white', 'white', 'white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 19,
    },
    'on_ramp': {
        'sides': ['left', 'center', 'right', 'right', 'right'],
        'widths': [3.75, 0.0, 0.75, 3.0, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none'],
        'types': ['onRamp', 'center', 'border', 'stop','shoulder'],
        'road_mark_types': ['solid', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['bold', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.30, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 5,
    },
    'off_ramp': {
        'sides': ['left', 'center', 'right', 'right', 'right'],
        'widths': [3.75, 0.0, 0.75, 3.0, 1.5],
        'widths_change': ['none', 'none', 'none', 'none', 'none'],
        'types': ['offRamp', 'center', 'border', 'stop', 'shoulder'],
        'road_mark_types': ['solid', 'solid', 'none', 'none', 'none'],
        'road_mark_weights': ['bold', 'bold', 'none', 'none', 'none'],
        'road_mark_widths': [0.30, 0.30, 0.0, 0.0, 0.0],
        'road_mark_colors': ['white', 'white', 'none', 'none', 'none'],
        'road_split_type': 'none',
        'road_split_lane_idx': 5,
    },
}
# We need global wrapper callbacks due to Blender update callback implementation
def callback_cross_section(self, context):
    self.update_cross_section()
def callback_lane_width(self, context):
    self.update_lane_width(context)
def callback_road_mark_weight(self, context):
    self.update_road_mark_weight(context)
def callback_num_lanes(self, context):
    self.update_num_lanes()
def callback_road_split(self, context):
    self.update_road_split(context)

class PR_enum_lane(bpy.types.PropertyGroup):
    idx: bpy.props.IntProperty(min=0)
    side: bpy.props.EnumProperty(
        items=(('left', 'left', '', 0),
               ('right', 'right', '', 1),
               ('center', 'center', '', 2),
              ),
        default='right',
    )
    width: bpy.props.FloatProperty(
        name='Width',
        default=4.0, min=0.01, max=10.0, step=1
    )
    # Used to open up a new lane or end a lane
    width_change: bpy.props.EnumProperty(
        name = 'Width change',
        items=(('none', 'None', '', 0),
               ('open', 'Open', '', 1),
               ('close', 'Close', '', 2),
              ),
        default='none',
    )
    type: bpy.props.EnumProperty(
        name = 'Type',
        items=(('driving', 'Driving', '', 0),
               #('bidirectional', 'Bidirectional', '', 1),
               #('bus', 'Bus', '', 2),
               ('stop', 'Stop', '', 3),
               #('parking', 'Parking', '', 4),
               #('biking', 'Biking', '', 5),
               #('restricted', 'Restricted', '', 6),
               #('roadWorks', 'Road works', '', 7),
               ('border', 'Border', '', 8),
               #('curb', 'Curb', '', 9),
               #('sidewalk', 'Sidewalk', '', 10),
               ('shoulder', 'Shoulder', '', 11),
               ('median', 'Median', '', 12),
               ('entry', 'Entry', '', 13),
               ('exit', 'Exit', '', 14),
               ('onRamp', 'On ramp', '', 15),
               ('offRamp', 'Off ramp', '', 16),
               #('connectingRamp', 'Connecting ramp', '', 17),
               ('none', 'None', '', 18),
               ('center', 'Center', '', 19),
              ),
        default='driving',
        update=callback_lane_width,
    )
    road_mark_type: bpy.props.EnumProperty(
        name = 'Type',
        items=(('none', 'None', '', 0),
               ('solid', 'Solid', '', 1),
               ('broken', 'Broken', '', 2),
               ('solid_solid', 'Double solid solid', '', 3),
               #('solid_broken', 'Double solid broken', '', 4),
               #('broken_solid', 'Double broken solid', '', 5),
              ),
        default='none',
    )
    road_mark_color: bpy.props.EnumProperty(
        name = 'Color',
        items=(('none', 'None', '', 0),
               ('white', 'White', '', 1),
               ('yellow', 'Yellow', '', 2),
              ),
        default='none',
    )
    road_mark_weight: bpy.props.EnumProperty(
        name = 'Weight',
        items=(('none', 'None', '', 0),
               ('standard', 'Standard', '', 1),
               ('bold', 'Bold', '', 2),
              ),
        default='none',
        update=callback_road_mark_weight,
    )
    road_mark_width: bpy.props.FloatProperty(
        name='Width of road mark line',
        default=0.12, min=0.0, max=10.0, step=1
    )

    # False for the lanes/lanes going left, True for those going right
    split_right: bpy.props.BoolProperty(description='Split above here', update=callback_road_split)

    def update_lane_width(self, context):
        mapping_width_type_lane = {
            'driving' : context.scene.road_properties.width_driving,
            'entry' : context.scene.road_properties.width_driving,
            'exit' : context.scene.road_properties.width_driving,
            'onRamp' : context.scene.road_properties.width_driving,
            'offRamp' : context.scene.road_properties.width_driving,
            'stop' : context.scene.road_properties.width_stop,
            'border' : context.scene.road_properties.width_border,
            'shoulder' : context.scene.road_properties.width_shoulder,
            'median' : context.scene.road_properties.width_median,
            'none' : context.scene.road_properties.width_none,
            'center': 0,
        }
        self.width = mapping_width_type_lane[self.type]

    def update_road_mark_weight(self, context):
        mapping_width_type_road_mark = {
            'none' : 0,
            'standard' : context.scene.road_properties.width_line_standard,
            'bold' : context.scene.road_properties.width_line_bold,
        }
        self.road_mark_width = mapping_width_type_road_mark[self.road_mark_weight]

    def update_road_split(self, context):
        # Avoid updating recursively
        if context.scene.road_properties.lock_lanes:
            return
        context.scene.road_properties.lock_lanes = True
        # Toggle
        if self.split_right == True:
            self.split_right = True
            road_split_lane_idx = self.idx
        else:
            self.split_right = False
            road_split_lane_idx = self.idx + 1
        # Store new split index
        context.scene.road_properties.road_split_lane_idx = road_split_lane_idx
        # Split at the desired lane
        for idx, lane in enumerate(context.scene.road_properties.lanes):
            if idx < road_split_lane_idx:
                lane.split_right = False
            else:
                lane.split_right = True
        # Unlock updating
        context.scene.road_properties.lock_lanes = False
# =============================== Road properties =================================================
class PR_road_properties(bpy.types.PropertyGroup):
    width_line_standard: bpy.props.FloatProperty(default=0.12, min=0.01, max=10.0, step=1)
    width_line_bold: bpy.props.FloatProperty(default=0.25, min=0.01, max=10.0, step=1)
    length_broken_line: bpy.props.FloatProperty(default=3.0, min=0.01, max=10.0, step=1)
    ratio_broken_line_gap: bpy.props.IntProperty(default=1, min=1, max=3)
    width_driving: bpy.props.FloatProperty(default=3.75, min=0.01, max=10.0, step=1)
    width_border: bpy.props.FloatProperty(default=0.5, min=0.01, max=1.0, step=1)
    # width_curb: bpy.props.FloatProperty(default=0.16, min=0.10, max=0.30, step=1)
    width_median: bpy.props.FloatProperty(default=2.0, min=0.01, max=10.0, step=1)
    width_stop: bpy.props.FloatProperty(default=2.5, min=0.01, max=10.0, step=1)
    width_shoulder: bpy.props.FloatProperty(default=1.5, min=0.01, max=10.0, step=1)
    width_none: bpy.props.FloatProperty(default=2.5, min=0.01, max=10.0, step=1)

    design_speed: bpy.props.FloatProperty(default=130.0, min=1.00, max=400.0, step=1)

    num_lanes_left: bpy.props.IntProperty(default=2, min=0, max=20, update=callback_num_lanes)
    num_lanes_right: bpy.props.IntProperty(default=2, min=0, max=20, update=callback_num_lanes)

    road_split_type: bpy.props.EnumProperty(
        name = 'Split type',
        items=(('none', 'None', '', 0),
               ('start', 'Start', '', 1),
               ('end', 'End', '', 2),
              ),
        default='none',
    )
    # Lane idx of first right lane in case of a split road (counting in -t direction)
    road_split_lane_idx: bpy.props.IntProperty(default=0, min=0)

    lane_idx_current: bpy.props.IntProperty(default=0, min=0)
    lanes: bpy.props.CollectionProperty(type=PR_enum_lane)

    cross_section_preset: bpy.props.EnumProperty(
            items=(
                ('two_lanes_default','Two lanes (default)','Two lanes (default)'),
                # Typical German road cross sections
                ('ekl4_rq9', 'EKL 4, RQ 9', 'EKL 4, RQ 9'),
                ('ekl3_rq11', 'EKL 3, RQ 11', 'EKL 3, RQ 11'),
                # ('ekl2_rq11.5', 'EKL 2, RQ 11.5', 'EKL 2, RQ 11.5'),
                # ('ekl1_rq15_5', 'EKL 1, RQ 15.5', 'EKL 1, RQ 15.5'),
                # ('eka3_rq25', 'EKA 3, RQ 25', 'EKA 3, RQ 25'),
                # ('eka3_rq31_5', 'EKA 3, RQ 31_5', 'EKA 3, RQ 31_5'),
                # ('eka3_rq38_5', 'EKA 3, RQ 38_5', 'EKA 3, RQ 38_5'),
                # ('eka2_rq28', 'EKA 1, RQ 28', 'EKA 1, RQ 28'),
                ('eka1_rq31', 'EKA 1, RQ 31', 'EKA 1, RQ 31'),
                ('eka1_rq31_exit_right_open', 'EKA 1, RQ 31 - exit right open', 'EKA 1, RQ 31 - exit right open'),
                ('eka1_rq31_exit_right', 'EKA 1, RQ 31 - exit right', 'EKA 1, RQ 31 - exit right'),
                ('eka1_rq31_exit_right_continuation', 'EKA 1, RQ 31 - exit right continuation', 'EKA 1, RQ 31 - exit right continuation'),
                ('eka1_rq31_entry_right', 'EKA 1, RQ 31 - entry right', 'EKA 1, RQ 31 - entry right'),
                ('eka1_rq31_entry_right_close', 'EKA 1, RQ 31 - entry right close', 'EKA 1, RQ 31 - entry right close'),
                ('eka1_rq36', 'EKA 1, RQ 36', 'EKA 1, RQ 36'),
                ('eka1_rq43_5', 'EKA 1, RQ 43.5', 'EKA 1, RQ 43.5'),
                ('on_ramp', 'On ramp', 'On ramp'),
                ('off_ramp', 'Off ramp', 'Off ramp'),
            ),
            name='cross_section',
            description='Road cross section presets',
            default='two_lanes_default',
            update=callback_cross_section,
            )

    # A lock for deactivating callbacks
    lock_lanes: bpy.props.BoolProperty(default=False)

    def init(self):
        self.update_cross_section()

    def clear_lanes(self):
        self.lanes.clear()
        self.lane_idx_current = 0
        self.road_split_type = 'none'
        self.road_split_lane_idx = 1

    def update_num_lanes(self):
        # Do not update recursively when switching presets
        if self.lock_lanes:
            return
        # Avoid callbacks
        self.lock_lanes = True
        self.clear_lanes()
        # Left lanes
        for idx in range(self.num_lanes_left - 1,-1,-1):
            if self.num_lanes_left == 1:
                self.add_lane('left', 'driving', self.width_driving, 'none', 'solid', 'standard', 0.12, 'white')
            else:
                if idx == self.num_lanes_left - 1:
                    self.add_lane('left', 'border', self.width_border, 'none', 'none', 'none', 0.0, 'none')
                elif idx == 0:
                    self.add_lane('left', 'driving', self.width_driving, 'none', 'solid', 'standard', 0.12, 'white')
                else:
                    self.add_lane('left', 'driving', self.width_driving, 'none', 'broken', 'standard', 0.12, 'white')
        # Center line
        if self.num_lanes_left == 0:
            self.add_lane('center', 'driving', 0.0, 'none', 'solid', 'standard', 0.12, 'white')
        elif self.num_lanes_right == 0:
            self.add_lane('center', 'driving', 0.0, 'none', 'solid', 'standard', 0.12, 'white')
        else:
            self.add_lane('center', 'driving', 0.0, 'none', 'broken', 'standard', 0.12, 'white')
        # Right lanes
        for idx in range(self.num_lanes_right):
            if self.num_lanes_right == 1:
                self.add_lane('right', 'driving', self.width_driving, 'none', 'solid', 'standard', 0.12, 'white')
            else:
                if idx == self.num_lanes_right - 1:
                    self.add_lane('right', 'border', self.width_border, 'none', 'none', 'none', 0.0, 'none')
                elif idx == self.num_lanes_right - 2:
                    self.add_lane('right', 'driving', self.width_driving, 'none', 'solid', 'standard', 0.12, 'white')
                else:
                    self.add_lane('right', 'driving', self.width_driving, 'none', 'broken', 'standard', 0.12, 'white')
        self.road_split_type = 'none'
        # Set split index one above maximum to make all lanes go left
        self.road_split_lane_idx = self.num_lanes_left + self.num_lanes_right + 1
        # Allow callbacks again
        self.lock_lanes = False

    def add_lane(self, side, type, width, width_change,
                 road_mark_type, road_mark_weight, road_mark_width, road_mark_color,
                 split_right=False):
        lane = self.lanes.add()
        lane.idx = self.lane_idx_current
        self.lane_idx_current += 1
        lane.side = side
        lane.type = type
        lane.width = width
        lane.width_change = width_change
        lane.road_mark_type = road_mark_type
        lane.road_mark_weight = road_mark_weight
        lane.road_mark_width = road_mark_width
        lane.road_mark_color = road_mark_color
        lane.split_right = split_right

    def update_cross_section(self):
        # Do not update recursively when switching presets
        if self.lock_lanes:
            return
        # Avoid callbacks
        self.lock_lanes = True
        # Reset
        self.clear_lanes()
        num_lanes_left = 0
        num_lanes_right = 0
        # Build up cross section
        params = params_cross_section[self.cross_section_preset]
        for idx in range(len(params['sides'])):
            self.add_lane(params['sides'][idx], params['types'][idx],
                params['widths'][idx], params['widths_change'][idx], params['road_mark_types'][idx],
                params['road_mark_weights'][idx], params['road_mark_widths'][idx],
                params['road_mark_colors'][idx])
            if params['sides'][idx] == 'left':
                num_lanes_left += 1
            if params['sides'][idx] == 'right':
                num_lanes_right += 1
        self.road_split_type = params['road_split_type']
        self.road_split_lane_idx = params['road_split_lane_idx']
        for idx, lane in enumerate(self.lanes):
            if idx < self.road_split_lane_idx:
                lane.split_right = False
            else:
                lane.split_right = True
        self.print_cross_section()
        # Block recursive callbacks
        self.num_lanes_left = num_lanes_left
        self.num_lanes_right = num_lanes_right
        # Allow callbacks again
        self.lock_lanes = False

    def print_cross_section(self):
        print('New cross section:', self.cross_section_preset)
        sides = []
        widths = []
        types = []
        road_mark_types = []
        for lane in self.lanes:
            sides.append(lane.side)
            widths.append(lane.width)
            types.append(lane.type)
            road_mark_types.append(lane.road_mark_type)

#Classes to define geometries
class DSC_geometry():

    params = {
        'curve': None,
        'length': 0,
        'point_start': Vector((0.0,0.0,0.0)),
        'heading_start': 0,
        'curvature_start': 0,
        'slope_start':0,
        'point_end': Vector((0.0,0.0,0.0)),
        'heading_end': 0,
        'curvature_end': 0,
        'slope_end': 0,
        'elevation': [{'s': 0, 'a': 0, 'b': 0, 'c': 0, 'd': 0}],
        'valid': True,
    }

    def sample_cross_section(self, s, t):
        '''
            Return a list of samples x, y = f(s, t) and curvature c in local
            coordinates.
        '''
        raise NotImplementedError()

    def update(self, params_input, geometry_solver):
        '''
            Update parameters of the geometry and local to global tranformation
            matrix.
        '''
        self.update_plan_view(params_input, geometry_solver)
        self.update_elevation(params_input)

    def update_local_to_global(self, point_start, heading_start, point_end, heading_end):
        '''
            Calculate matrix for local to global transform of the geometry.
        '''
        mat_translation = Matrix.Translation(point_start)
        mat_rotation = Matrix.Rotation(heading_start, 4, 'Z')
        self.matrix_world = mat_translation @ mat_rotation
        self.point_end_local = self.matrix_world.inverted() @ point_end
        self.heading_end_local = heading_end - heading_start

    def update_plan_view(self, params):
        '''
            Update plan view (2D) geometry of road.
        '''
        raise NotImplementedError()

    def update_elevation(self, params_input):
        '''
            Update elevation of road geometry based on predecessor, successor,
            start and end point.

            TODO: Later allow elevations across multiple geometries for now we
            use
                parabola
                parabola - line
                parablola - line - parablola
                line - parabola
            curve combination inside one geometry.

            Symbols and equations used:
                Slope of incoming road: m_0
                Parabola (Curve 0): h_p1 = a_p1 + b_p1 * s + c_p1 * s^2
                Line (Curve 1): h_l = a_l + b_l * s
                Parabola (Curve 2): h_p2 = a_p2 + b_p2 * s + c_p2 * s^2
                Slope of outgoing road: m_3
        '''
        if (params_input['point_start'].z == params_input['point_end'].z
            and params_input['slope_start'] == 0
            and params_input['slope_end'] == 0):
            # No elevation
            self.params['elevation'] = [{'s': 0, 'a': 0, 'b': 0, 'c': 0, 'd': 0}]
        else:
            # TODO: get slope of predecessor and succesor
            m_0 = params_input['slope_start']
            m_3 = params_input['slope_end']

            # Convert to local (s, z) coordinate system [x_1, y_1] = [0, 0]
            h_start = params_input['point_start'].z
            s_end = self.params['length']
            h_end = params_input['point_end'].z - h_start

            # End of parabola/beginning of straight line
            # TODO: Find correct equation for the parabola length from the literature
            s_1 = max(abs(m_0)/10, abs(h_end)/s_end) * params_input['design_speed']**2 / 120
            if s_1 > 0:
                if s_1 < s_end:
                    # Case: parobla - line
                    c_p1 = (h_end - m_0 * s_end) / (2 * s_1 * s_end - s_1**2)
                    h_1 = m_0 * s_1 + c_p1 * s_1**2
                    b_l = (h_end - h_1) / (s_end - s_1)
                    a_l = h_end - b_l * s_end
                    self.params['elevation'] = [{'s': 0, 'a': 0, 'b': m_0, 'c': c_p1, 'd': 0}]
                    self.params['elevation'].append({'s': s_1, 'a': a_l, 'b': b_l, 'c': 0, 'd': 0})
                else:
                    # Case: parablola
                    c_p1 = (h_end - m_0 * s_end) / s_end**2
                    self.params['elevation'] = [{'s': 0, 'a': 0, 'b': m_0, 'c': c_p1, 'd': 0}]
            else:
                self.params['elevation'] = [{'s': 0, 'a': 0, 'b': 0, 'c': 0, 'd': 0}]

        self.params['slope_start'] = self.get_slope_start()
        self.params['slope_end'] = self.get_slope_end()

    def get_slope_start(self):
        '''
            Return slope at beginning of geometry.
        '''
        return self.params['elevation'][0]['b']

    def get_slope_end(self):
        '''
            Return slope at end of geometry.
        '''
        length = self.params['length']
        slope = self.params['elevation'][-1]['b'] + \
            2 * self.params['elevation'][-1]['c'] * length + \
            3 * self.params['elevation'][-1]['d'] * length**2
        return slope


    def sample_plan_view(self, s):
        '''
            Return x(s), y(s), curvature(s), hdg_t(s)
        '''
        return NotImplementedError()

    def get_elevation(self, s):
        '''
            Return the elevation coefficients for the given value of s.
        '''
        idx_elevation = 0
        while idx_elevation < len(self.params['elevation'])-1:
            if s >= self.params['elevation'][idx_elevation+1]['s']:
                idx_elevation += 1
            else:
                break
        return self.params['elevation'][idx_elevation]

    def sample_cross_section(self, s, t_vec):
        '''
            Sample a cross section (multiple t values) in the local coordinate
            system.
        '''
        x_s, y_s, curvature_plan_view, hdg_t = self.sample_plan_view(s)
        elevation = self.get_elevation(s)
        # Calculate curvature of the elevation function
        d2e_d2s = 2 * elevation['c'] + 3 * elevation['d'] * s
        if d2e_d2s != 0:
            de_ds = elevation['b']+ 2 * elevation['c'] * s + 3 * elevation['d'] * s
            curvature_elevation = (1 + de_ds**2)**(3/2) / d2e_d2s
        else:
            curvature_elevation = 0
        # FIXME convert curvature for t unequal 0
        curvature_abs = max(abs(curvature_plan_view), abs(curvature_elevation))
        vector_hdg_t = Vector((1.0, 0.0))
        vector_hdg_t.rotate(Matrix.Rotation(hdg_t, 2))
        xyz = []
        for t in t_vec:
            xy_vec = Vector((x_s, y_s)) + t * vector_hdg_t
            z = elevation['a'] + \
                elevation['b'] * s + \
                elevation['c'] * s**2 + \
                elevation['d'] * s**3
            xyz += [(xy_vec.x, xy_vec.y, z)]
        return xyz, curvature_abs

class DSC_geometry_line(DSC_geometry):

    def update_plan_view(self, params, geometry_solver):
        if params['connected_start']:
            point_end = project_point_vector(params['point_start'].to_2d(),
                params['heading_start'], params['point_end'].to_2d())
            # Add height back to end point
            point_end = point_end.to_3d()
            point_end.z = params['point_end'].z
        else:
            point_end = params['point_end']

        # Note: For the line geometry heading_start and heading_end input is ignored
        # since the degrees of freedom are to low.
        # Hence, recalculate start heading
        heading_start_line = (point_end.to_2d() - \
            params['point_start'].to_2d()).angle_signed(Vector((1.0, 0.0)))
        # Calculate transform between global and local coordinates
        self.update_local_to_global(params['point_start'], heading_start_line,
            point_end, heading_start_line,)
        # Local starting point is 0 vector so length becomes length of end point vector
        length = self.point_end_local.to_2d().length

        # Remember geometry parameters
        self.params['curve'] = 'line'
        self.params['point_start'] = params['point_start']
        self.params['heading_start'] = heading_start_line
        self.params['curvature_start'] = 0
        self.params['point_end'] = point_end
        self.params['heading_end'] = heading_start_line
        self.params['curvature_end'] = 0
        self.params['length'] = length

    def sample_plan_view(self, s):
        x_s = s
        y_s = 0
        curvature = 0
        hdg_t = pi/2
        return x_s, y_s, curvature, hdg_t

class DSC_geometry_clothoid(DSC_geometry):

    def update_plan_view(self, params, geometry_solver='default'):
        # Calculate transform between global and local coordinates
        self.update_local_to_global(params['point_start'], params['heading_start'],
            params['point_end'], params['heading_end'])

        # Calculate geometry
        if geometry_solver == 'hermite' or geometry_solver == 'default':
            self.geometry_base = Clothoid.G1Hermite(0, 0, 0,
                self.point_end_local.x, self.point_end_local.y, self.heading_end_local)

            # When the heading of start and end point is colinear the curvature
            # becomes very small and the length becomes huge (solution is a gigantic
            # circle). Therefore as a workaround we limit the length to 10 km.
            if self.geometry_base.length < 10000.0:
                self.params['valid'] = True
            else:
                # Use old parameters
                self.update_local_to_global(self.params['point_start'], self.params['heading_start'],
                    self.params['point_end'], self.params['heading_end'])
                self.geometry_base = Clothoid.G1Hermite(0, 0, 0,
                    self.point_end_local.x, self.point_end_local.y, self.heading_end_local)
                self.params['valid'] = False
        elif geometry_solver == 'forward':
            self.geometry_base = Clothoid.Forward(0, 0, 0,
                params['curvature_start'], self.point_end_local.x, self.point_end_local.y)
            # Check for a valid solution based on the length
            if self.geometry_base.length > 0.0:
                self.params['valid'] = True
            else:
                # Use old parameters
                self.update_local_to_global(self.params['point_start'], self.params['heading_start'],
                    self.params['point_end'], self.params['heading_end'])
                self.geometry_base = Clothoid.Forward(0, 0, 0,
                    self.params['curvature_start'], self.point_end_local.x, self.point_end_local.y)
                self.params['valid'] = False

        # Remember geometry parameters
        if self.params['valid']:
            self.params['curve'] = 'spiral'
            self.params['point_start'] = params['point_start']
            self.params['heading_start'] = params['heading_start']
            self.params['point_end'] = params['point_end']
            self.params['heading_end'] = params['heading_start'] + self.geometry_base.ThetaEnd
            self.params['length'] = self.geometry_base.length
            self.params['curvature_start'] = self.geometry_base.KappaStart
            self.params['curvature_end'] = self.geometry_base.KappaEnd
            self.params['angle_end'] = self.geometry_base.ThetaEnd

    def sample_plan_view(self, s):
        x_s = self.geometry_base.X(s)
        y_s = self.geometry_base.Y(s)
        curvature = self.geometry_base.KappaStart + self.geometry_base.dk * s
        hdg_t = self.geometry_base.Theta(s) + pi/2
        return x_s, y_s, curvature, hdg_t

## =========================== Road definition classes =================================
class PR_OT_road(bpy.types.Operator):
    bl_idname = 'pr.road'
    bl_label = 'Road'
    bl_description = 'Create road mesh'
    bl_options = {'REGISTER', 'UNDO'}

    snap_filter = 'OpenDRIVE'
    geometry = DSC_geometry_line()
    
    params = {}

    geometry_solver: bpy.props.StringProperty(
        name='Geometry solver',
        description='Solver used to determine geometry parameters.',
        options={'HIDDEN'},
        default='default')

    #Define the two param dictionaries. These decide how the road will be constructed.
    def init_state(self):
        self.params_input = {
            'point_start': Vector((0.0,0.0,0.0)),
            'point_end': Vector((0.0,30.0,0.0)),
            'heading_start': 0,
            'heading_end': 0,
            'curvature_start': 0,
            'curvature_end': 0,
            'slope_start': 0,
            'slope_end': 0,
            'connected_start': False,
            'connected_end': False,
            'design_speed': 130.0,
        }
        self.params_snap = {
            'id_obj': None,
            'point': Vector((0.0,0.0,0.0)),
            'type': 'cp_none',
            'heading': 0,
            'curvature': 0,
            'slope': 0,
        }
    
    def create_3d_object(self, context):
        '''
            Create the Blender road object
        '''
        if len(context.scene.road_properties.lanes) == 0:
            context.scene.road_properties.init()
        valid, mesh_road, matrix_world, materials = self.update_params_get_mesh(context)
        if not valid:
            return None
        else:
            # Create road object
            id_obj = get_new_id_opendrive(context)
            mesh_road.name = str(id_obj)
            obj = bpy.data.objects.new(mesh_road.name, mesh_road)
            obj.matrix_world = matrix_world
            link_object_opendrive(context, obj)

            # Assign materials
            assign_road_materials(obj)
            for idx in range(len(obj.data.polygons)):
                if idx in materials['road_mark_white']:
                    obj.data.polygons[idx].material_index = \
                        get_material_index(obj, 'road_mark_white')
                elif idx in materials['grass']:
                    obj.data.polygons[idx].material_index = \
                        get_material_index(obj, 'grass')
                elif idx in materials['road_mark_yellow']:
                    obj.data.polygons[idx].material_index = \
                        get_material_index(obj, 'road_mark_yellow')
                else:
                    obj.data.polygons[idx].material_index = \
                        get_material_index(obj, 'road_asphalt')
            # Remove double vertices from road lanes and lane lines to simplify mesh
            remove_duplicate_vertices(context, obj)
            # Make it active for the user to see what he created last
            select_activate_object(context, obj)

            # Convert the ngons to tris and quads to get a defined surface for elevated roads
            triangulate_quad_mesh(obj)

            # Metadata
            obj['dsc_category'] = 'OpenDRIVE'
            obj['dsc_type'] = 'road'

            # Number lanes which split to the left side at road end
            obj['road_split_lane_idx'] = self.params['road_split_lane_idx']

            # Remember connecting points for road snapping
            if self.params['road_split_type'] == 'start':
                obj['cp_start_l'], obj['cp_start_r'] = self.get_split_cps('start')
                obj['cp_end_l'], obj['cp_end_r']= self.geometry.params['point_end'], self.geometry.params['point_end']
            elif self.params['road_split_type'] == 'end':
                obj['cp_start_l'], obj['cp_start_r'] = self.geometry.params['point_start'], self.geometry.params['point_start']
                obj['cp_end_l'], obj['cp_end_r']= self.get_split_cps('end')
            else:
                obj['cp_start_l'], obj['cp_start_r'] = self.geometry.params['point_start'], self.geometry.params['point_start']
                obj['cp_end_l'], obj['cp_end_r']= self.geometry.params['point_end'], self.geometry.params['point_end']

            # A road split needs to create an OpenDRIVE direct junction
            obj['road_split_type'] = self.params['road_split_type']
            if self.params['road_split_type'] != 'none':
                direct_junction_id = get_new_id_opendrive(context)
                direct_junction_name = 'direct_junction' + '_' + str(direct_junction_id)
                obj_direct_junction = bpy.data.objects.new(direct_junction_name, None)
                obj_direct_junction.empty_display_type = 'PLAIN_AXES'
                if self.params['road_split_lane_idx'] > self.params['lanes_left_num']:
                    if self.params['road_split_type'] == 'start':
                        obj_direct_junction.location = obj['cp_start_r']
                    else:
                        obj_direct_junction.location = obj['cp_end_r']
                else:
                    if self.params['road_split_type'] == 'start':
                        obj_direct_junction.location = obj['cp_start_l']
                    else:
                        obj_direct_junction.location = obj['cp_end_l']
                # FIXME also add rotation based on road heading and slope
                link_object_opendrive(context, obj_direct_junction)
                obj_direct_junction['id_xodr'] = direct_junction_id
                obj_direct_junction['dsc_category'] = 'OpenDRIVE'
                obj_direct_junction['dsc_type'] = 'junction_direct'
                if self.params['road_split_type'] == 'start':
                    obj['id_direct_junction_start'] = direct_junction_id
                else:
                    obj['id_direct_junction_end'] = direct_junction_id

            # Set OpenDRIVE custom properties
            obj['id_xodr'] = id_obj

            obj['geometry'] = self.geometry.params

            obj['lanes_left_num'] = self.params['lanes_left_num']
            obj['lanes_right_num'] = self.params['lanes_right_num']
            obj['lanes_left_types'] = self.params['lanes_left_types']
            obj['lanes_right_types'] = self.params['lanes_right_types']
            obj['lanes_left_widths'] = self.params['lanes_left_widths']
            obj['lanes_left_widths_change'] = self.params['lanes_left_widths_change']
            obj['lanes_right_widths'] = self.params['lanes_right_widths']
            obj['lanes_right_widths_change'] = self.params['lanes_right_widths_change']
            obj['lanes_left_road_mark_types'] = self.params['lanes_left_road_mark_types']
            obj['lanes_left_road_mark_weights'] = self.params['lanes_left_road_mark_weights']
            obj['lanes_left_road_mark_colors'] = self.params['lanes_left_road_mark_colors']
            obj['lanes_right_road_mark_types'] = self.params['lanes_right_road_mark_types']
            obj['lanes_right_road_mark_weights'] = self.params['lanes_right_road_mark_weights']
            obj['lanes_right_road_mark_colors'] = self.params['lanes_right_road_mark_colors']
            obj['lane_center_road_mark_type'] = self.params['lane_center_road_mark_type']
            obj['lane_center_road_mark_weight'] = self.params['lane_center_road_mark_weight']
            obj['lane_center_road_mark_color'] = self.params['lane_center_road_mark_color']

            return obj

    def update_params_get_mesh(self, context):
        '''
            Calculate and return the vertices, edges, faces and parameters to create a road mesh.
        '''
        # Update parameters based on selected points
        self.geometry.update(self.params_input, self.geometry_solver)
        if self.geometry.params['valid'] == False:
            self.report({'WARNING'}, 'No valid road geometry solution found!')
        length_broken_line = context.scene.road_properties.length_broken_line
        self.set_lane_params(context.scene.road_properties)
        lanes = context.scene.road_properties.lanes
        # Get values in t and s direction where the faces of the road start and end
        strips_s_boundaries = self.get_strips_s_boundaries(lanes, length_broken_line)
        # Calculate meshes for Blender
        road_sample_points = self.get_road_sample_points(lanes, strips_s_boundaries)
        vertices, edges, faces = self.get_road_vertices_edges_faces(road_sample_points)
        materials = self.get_face_materials(lanes, strips_s_boundaries)

        '''
        if wireframe:
            # Transform start and end point to local coordinate system then add
            # a vertical edge down to the xy-plane to make elevation profile
            # more easily visible
            point_start = (self.geometry.params['point_start'])
            point_start_local = (0.0, 0.0, 0.0)
            point_start_bottom = (0.0, 0.0, -point_start.z)
            point_end = self.geometry.params['point_end']
            point_end_local = self.geometry.matrix_world.inverted() @ point_end
            point_end_local.z = point_end.z - point_start.z
            point_end_bottom = (point_end_local.x, point_end_local.y, -point_start.z)
            vertices += [point_start_local[:], point_start_bottom, point_end_local[:], point_end_bottom]
            edges += [[len(vertices)-1, len(vertices)-2], [len(vertices)-3, len(vertices)-4]]
        '''

        # Create blender mesh
        mesh = bpy.data.meshes.new('temp_road')
        mesh.from_pydata(vertices, edges, faces)
        valid = True
        return valid, mesh, self.geometry.matrix_world, materials

    def set_lane_params(self, road_properties):
        '''
            Set the lane parameters dictionary for later export.
        '''
        self.params = {'lanes_left_num': road_properties.num_lanes_left,
                       'lanes_right_num': road_properties.num_lanes_right,
                       'lanes_left_widths': [],
                       'lanes_left_widths_change': [],
                       'lanes_right_widths': [],
                       'lanes_right_widths_change': [],
                       'lanes_left_types': [],
                       'lanes_right_types': [],
                       'lanes_left_road_mark_types': [],
                       'lanes_left_road_mark_weights': [],
                       'lanes_left_road_mark_colors': [],
                       'lanes_right_road_mark_types': [],
                       'lanes_right_road_mark_weights': [],
                       'lanes_right_road_mark_colors': [],
                       'lane_center_road_mark_type': [],
                       'lane_center_road_mark_weight': [],
                       'lane_center_road_mark_color': [],
                       'road_split_type': road_properties.road_split_type,
                       'road_split_lane_idx': road_properties.road_split_lane_idx}
        for idx, lane in enumerate(road_properties.lanes):
            if lane.side == 'left':
                self.params['lanes_left_widths'].insert(0, lane.width)
                self.params['lanes_left_widths_change'].insert(0, lane.width_change)
                self.params['lanes_left_types'].insert(0, lane.type)
                self.params['lanes_left_road_mark_types'].insert(0, lane.road_mark_type)
                self.params['lanes_left_road_mark_weights'].insert(0, lane.road_mark_weight)
                self.params['lanes_left_road_mark_colors'].insert(0, lane.road_mark_color)
            elif lane.side == 'right':
                self.params['lanes_right_widths'].append(lane.width)
                self.params['lanes_right_widths_change'].append(lane.width_change)
                self.params['lanes_right_types'].append(lane.type)
                self.params['lanes_right_road_mark_types'].append(lane.road_mark_type)
                self.params['lanes_right_road_mark_weights'].append(lane.road_mark_weight)
                self.params['lanes_right_road_mark_colors'].append(lane.road_mark_color)
            else:
                # lane.side == 'center'
                self.params['lane_center_road_mark_type'] = lane.road_mark_type
                self.params['lane_center_road_mark_weight'] = lane.road_mark_weight
                self.params['lane_center_road_mark_color'] = lane.road_mark_color

    def get_split_cps(self, road_split_type):
        '''
            Return the two connection points for a split road.
        '''
        road_split_lane_idx = self.params['road_split_lane_idx']
        t_cp_split = self.road_split_lane_idx_to_t(road_split_lane_idx)
        if road_split_type == 'start':
            t = 0
            cp_base = self.geometry.params['point_start']
        else:
            t = self.geometry.params['length']
            cp_base = self.geometry.params['point_end']
        # Split
        cp_split = self.geometry.matrix_world @ Vector(self.geometry.sample_cross_section(
            t, [t_cp_split])[0][0])
        # Check which part of the split contains the center lane, that part
        # gets the contact point on the center lane
        if t_cp_split < 0:
            return cp_base, cp_split
        else:
            return cp_split, cp_base

    def road_split_lane_idx_to_t(self, road_split_lane_idx):
        '''
            Convert index of first splitting lane to t coordinate of left/right
            side of the split lane border. Return 0 if there is no split.
        '''
        t_cp_split = 0
        # Check if there really is a split
        if self.params['road_split_type'] != 'none':
            # Calculate lane ID from split index
            if self.params['lanes_left_num'] > 0:
                lane_id_split = -1 * (road_split_lane_idx - self.params['lanes_left_num'])
            else:
                lane_id_split = -1 * road_split_lane_idx
            # Calculate t coordinate of split connecting point
            for idx in range(abs(lane_id_split)):
                    if lane_id_split > 0:
                        # Do not add lanes with 0 width
                        if not ((self.params['road_split_type'] == 'start' and
                                 self.params['lanes_left_widths_change'][idx] == 'open') or
                                (self.params['road_split_type'] == 'end' and \
                                 self.params['lanes_left_widths_change'][idx] == 'close')):
                            t_cp_split += self.params['lanes_left_widths'][idx]
                    else:
                        # Do not add lanes with 0 width
                        if not ((self.params['road_split_type'] == 'start' and
                                 self.params['lanes_right_widths_change'][idx] == 'open') or
                                (self.params['road_split_type'] == 'end' and \
                                 self.params['lanes_right_widths_change'][idx] == 'close')):
                            t_cp_split -= self.params['lanes_right_widths'][idx]
        return t_cp_split

    def get_width_road_left(self, lanes):
        '''
            Return the width of the left road side calculated by suming up all
            lane widths.
        '''
        width_road_left = 0
        for idx, lane in enumerate(lanes):
            if idx == 0:
                if lane.road_mark_type != 'none':
                    # If first lane has a line we need to add half its width
                    width_line = lane.road_mark_width
                    if lane.road_mark_type == 'solid_solid' or \
                        lane.road_mark_type == 'solid_broken' or \
                        lane.road_mark_type == 'broken_solid':
                            width_road_left += width_line * 3.0 / 2.0
                    else:
                        width_road_left += width_line / 2.0
            # Stop when reaching the right side
            if lane.side == 'right':
                break
            if lane.side == 'left':
                width_road_left += lane.width
        return width_road_left

    def get_strips_t_values(self, lanes, s):
        '''
            Return list of t values of strip borders.
        '''
        t = self.get_width_road_left(lanes)
        t_values = []
        for idx_lane, lane in enumerate(lanes):
            s_norm = s / self.geometry.params['length']
            if lane.width_change == 'open':
                lane_width_s = (3.0 * s_norm**2 - 2.0 * s_norm**3) * lane.width
            elif lane.width_change == 'close':
                lane_width_s = (1.0 - 3.0 * s_norm**2 + 2.0 * s_norm**3) * lane.width
            else:
                lane_width_s = lane.width
            # Add lane width for right side of road BEFORE (in t-direction) road mark lines
            if lane.side == 'right':
                width_left_lines_on_lane = 0.0
                if lanes[idx_lane - 1].road_mark_type != 'none':
                    width_line = lanes[idx_lane - 1].road_mark_width
                    if lanes[idx_lane - 1].road_mark_type == 'solid_solid' or \
                            lanes[idx_lane - 1].road_mark_type == 'solid_broken' or \
                            lanes[idx_lane - 1].road_mark_type == 'broken_solid':
                        width_left_lines_on_lane = width_line * 3.0 / 2.0
                    else:
                        width_left_lines_on_lane = width_line / 2.0
                width_right_lines_on_lane = 0.0
                if lane.road_mark_type != 'none':
                    width_line = lane.road_mark_width
                    if lane.road_mark_type == 'solid_solid' or \
                            lane.road_mark_type == 'solid_broken' or \
                            lane.road_mark_type == 'broken_solid':
                        width_right_lines_on_lane = width_line * 3.0 / 2.0
                    else:
                        width_right_lines_on_lane = width_line / 2.0
                t -= lane_width_s - width_left_lines_on_lane - width_right_lines_on_lane
            # Add road mark lines
            if lane.road_mark_type != 'none':
                width_line = lane.road_mark_width
                if lane.road_mark_type == 'solid_solid' or \
                        lane.road_mark_type == 'solid_broken' or \
                        lane.road_mark_type == 'broken_solid':
                    t_values.append(t)
                    t_values.append(t -       width_line)
                    t_values.append(t - 2.0 * width_line)
                    t_values.append(t - 3.0 * width_line)
                    t = t - 3.0 * width_line
                else:
                    t_values.append(t)
                    t_values.append(t - width_line)
                    t -= width_line
            else:
                t_values.append(t)
            # Add lane width for left side of road AFTER (in t-direction) road mark lines
            if lane.side == 'left':
                width_left_lines_on_lane = 0
                if lane.road_mark_type != 'none':
                    width_line = lane.road_mark_width
                    if lane.road_mark_type == 'solid_solid' or \
                            lane.road_mark_type == 'solid_broken' or \
                            lane.road_mark_type == 'broken_solid':
                        width_left_lines_on_lane = width_line * 3.0 / 2.0
                    else:
                        width_left_lines_on_lane = width_line / 2.0
                width_right_lines_on_lane = 0
                if lanes[idx_lane + 1].road_mark_type != 'none':
                    width_line = lanes[idx_lane + 1].road_mark_width
                    if lanes[idx_lane + 1].road_mark_type == 'solid_solid' or \
                            lanes[idx_lane + 1].road_mark_type == 'solid_broken' or \
                            lanes[idx_lane + 1].road_mark_type == 'broken_solid':
                        width_right_lines_on_lane = width_line * 3.0 / 2.0
                    else:
                        width_right_lines_on_lane = width_line / 2.0
                t -= lane_width_s - width_left_lines_on_lane - width_right_lines_on_lane
        return t_values

    def get_strips_s_boundaries(self, lanes, length_broken_line):
        '''
            Return list of tuples with a line marking toggle flag and a list
            with the start and stop values of the faces in each strip.
        '''
        # Calculate line parameters
        # TODO offset must be provided by predecessor road for each marking
        length = self.geometry.params['length']
        offset = 0.5
        if offset < length_broken_line:
            offset_first = offset
            line_toggle_start = True
        else:
            offset_first = offset % length_broken_line
            line_toggle_start = False
        s_values = []
        
        for lane in lanes:
            # Calculate broken line parameters
            if lane.road_mark_type == 'broken':
                num_faces_strip_line = ceil((length \
                                        - (length_broken_line - offset_first)) \
                                       / length_broken_line)
                # Add one extra step for the shorter first piece
                if offset_first > 0:
                    num_faces_strip_line += 1
                length_first = min(length, length_broken_line - offset_first)
                if num_faces_strip_line > 1:
                    length_last = length - length_first - (num_faces_strip_line - 2) * length_broken_line
                else:
                    length_last = length_first
            else:
                num_faces_strip_line = 1

            # Go in s direction along lane and calculate the start and stop values
            # ASPHALT
            if lane.side == 'right':
                s_values.append((line_toggle_start, [0, length]))
            # ROAD MARK
            if lane.road_mark_type != 'none':
                s_values_strip = [0]
                for idx_face_strip in range(num_faces_strip_line):
                    # Calculate end points of the faces
                    s_stop = length
                    if lane.road_mark_type == 'broken':
                        if idx_face_strip == 0:
                            # First piece
                            s_stop = length_first
                        elif idx_face_strip > 0 and idx_face_strip + 1 == num_faces_strip_line:
                            # Last piece and more than one piece
                            s_stop = length_first + (idx_face_strip - 1) * length_broken_line \
                                    + length_last
                        else:
                            # Middle piece
                            s_stop = length_first + idx_face_strip * length_broken_line
                    s_values_strip.append(s_stop)
                if lane.road_mark_type == 'solid_solid':
                    s_values.append((line_toggle_start, s_values_strip))
                    s_values.append((line_toggle_start, s_values_strip))
                s_values.append((line_toggle_start, s_values_strip))
            # ASPHALT
            if lane.side == 'left':
                s_values.append((line_toggle_start, [0, length]))
        return s_values

    def get_road_sample_points(self, lanes, strips_s_boundaries):
        '''
            Adaptively sample road in s direction based on local curvature.
        '''
        length = self.geometry.params['length']
        s = 0
        strips_t_values = self.get_strips_t_values(lanes, s)
        # Obtain first curvature value
        xyz_samples, curvature_abs = self.geometry.sample_cross_section(0, strips_t_values)
        # We need 2 vectors for each strip to later construct the faces with one
        # list per face on each side of each strip
        sample_points = [[[]] for _ in range(2 * (len(strips_t_values) - 1))]
        t_offset = 0
        for idx_t in range(len(strips_t_values) - 1):
            sample_points[2 * idx_t][0].append((0, strips_t_values[idx_t], 0))
            sample_points[2 * idx_t + 1][0].append((0, strips_t_values[idx_t + 1], 0))
        # Concatenate vertices until end of road
        idx_boundaries_strips = [0] * len(strips_s_boundaries)
        while s < length:
            # TODO: Make hardcoded sampling parameters configurable
            if curvature_abs == 0:
                step = 5
            else:
                step = max(1, min(5, 0.1 / abs(curvature_abs)))
            s += step
            if s >= length:
                s = length

            # Sample next points along road geometry (all t values for current s value)
            strips_t_values = self.get_strips_t_values(lanes, s)
            xyz_samples, curvature_abs = self.geometry.sample_cross_section(s, strips_t_values)
            point_index = -2
            while point_index < len(sample_points) - 2:
                point_index = point_index + 2
                if not sample_points[point_index][0]:
                    continue
                idx_strip = point_index//2
                # Get the boundaries of road marking faces for current strip plus left and right
                idx_boundaries = [0, 0, 0]
                s_boundaries_next = [length, length, length]
                # Check if there is a strip left and/or right to take into account
                if idx_strip > 0:
                    idx_boundaries[0] = idx_boundaries_strips[idx_strip - 1]
                    s_boundaries_next[0] = strips_s_boundaries[idx_strip - 1][1][idx_boundaries[0] + 1]
                idx_boundaries[1] = idx_boundaries_strips[idx_strip]
                s_boundaries_next[1] = strips_s_boundaries[idx_strip][1][idx_boundaries[1] + 1]
                if idx_strip < len(strips_s_boundaries) - 1:
                    idx_boundaries[2] = idx_boundaries_strips[idx_strip + 1]
                    s_boundaries_next[2] = strips_s_boundaries[idx_strip + 1][1][idx_boundaries[2] + 1]

                # Check if any face boundary is smaller than sample point
                smaller, idx_smaller = self.compare_boundaries_with_s(s, s_boundaries_next)
                if smaller:
                    # Find all boundaries in between
                    while smaller:
                        # Sample the geometry
                        t_values = [strips_t_values[idx_strip], strips_t_values[idx_strip + 1]]
                        xyz_boundary, curvature_abs = self.geometry.sample_cross_section(
                            s_boundaries_next[idx_smaller], t_values)
                        if idx_smaller == 0:
                            # Append left extra point
                            sample_points[2 * idx_strip][idx_boundaries[1]].append(xyz_boundary[0])
                        if idx_smaller == 1:
                            # Append left and right points
                            sample_points[2 * idx_strip][idx_boundaries[1]].append(xyz_boundary[0])
                            sample_points[2 * idx_strip + 1][idx_boundaries[1]].append(xyz_boundary[1])
                            # Start a new list for next face
                            sample_points[2 * idx_strip].append([xyz_boundary[0]])
                            sample_points[2 * idx_strip + 1].append([xyz_boundary[1]])
                        if idx_smaller == 2:
                            # Append right extra point
                            sample_points[2 * idx_strip + 1][idx_boundaries[1]].append(xyz_boundary[1])
                        # Get the next boundary (relative to this strip)
                        idx_boundaries[idx_smaller] += 1
                        idx_strip_relative = idx_strip + idx_smaller - 1
                        s_boundaries_next[idx_smaller] = \
                            strips_s_boundaries[idx_strip_relative][1][idx_boundaries[idx_smaller] + 1]
                        # Check again
                        smaller, idx_smaller = self.compare_boundaries_with_s(s, s_boundaries_next)
                    # Write back indices to global array (only left strip to avoid cross interference!)
                    if idx_strip > 0:
                        idx_boundaries_strips[idx_strip - 1] = idx_boundaries[0]

                # Now there is no boundary in between anymore so append the samples
                sample_points[2 * idx_strip][idx_boundaries[1]].append(xyz_samples[idx_strip])
                sample_points[2 * idx_strip + 1][idx_boundaries[1]].append(xyz_samples[idx_strip + 1])
        return sample_points

    def compare_boundaries_with_s(self, s, s_boundaries_next):
        '''
            Return True if any boundary is smaller than s, also return the index
            to the boundary.
        '''
        smaller = False
        idx_sorted = sorted(range(len(s_boundaries_next)), key=s_boundaries_next.__getitem__)
        if s_boundaries_next[idx_sorted[0]] < s:
            smaller = True

        return smaller, idx_sorted[0]

    def get_road_vertices_edges_faces(self, road_sample_points):
        '''
           generate mesh from samplepoints
        '''
        vertices = []
        edges = []
        faces = []
        idx_vertex = 0
        point_index = 0
        while point_index < len(road_sample_points):
            for idx_face_strip in range(len(road_sample_points[point_index])):
                # ignore empty samplepoints, it may be none type line or any thing that doesn't need to build a mesh
                if not road_sample_points[point_index][0]:
                    continue
                samples_right = road_sample_points[point_index + 1][idx_face_strip]
                samples_left = road_sample_points[point_index][idx_face_strip]
                num_vertices = len(samples_left) + len(samples_right)
                vertices += samples_right + samples_left[::-1]
                edges += [[idx_vertex + n, idx_vertex + n + 1] for n in range(num_vertices - 1)] \
                         + [[idx_vertex + num_vertices - 1, idx_vertex]]
                faces += [[idx_vertex + n for n in range(num_vertices)]]
                idx_vertex += num_vertices
            point_index = point_index + 2
        return vertices, edges, faces

    def get_strip_to_lane_mapping(self, lanes):
        '''
            Return list of lane indices for strip indices.
        '''
        strip_to_lane = []
        strip_is_road_mark = []
        for idx_lane, lane in enumerate(lanes):
            if lane.side == 'left':
                if lane.road_mark_type != 'none':
                    if lane.road_mark_type == 'solid' or \
                        lane.road_mark_type == 'broken':
                        strip_to_lane.append(idx_lane)
                        strip_is_road_mark.append(True)
                    else:
                        # Double line
                        strip_to_lane.append(idx_lane)
                        strip_to_lane.append(idx_lane)
                        strip_to_lane.append(idx_lane)
                        strip_is_road_mark.append(True)
                        strip_is_road_mark.append(False)
                        strip_is_road_mark.append(True)
                strip_to_lane.append(idx_lane)
                strip_is_road_mark.append(False)
            elif lane.side == 'center':
                if lane.road_mark_type != 'none':
                    strip_to_lane.append(idx_lane)
                    strip_is_road_mark.append(True)
            else:
                # lane.side == 'right'
                strip_to_lane.append(idx_lane)
                strip_is_road_mark.append(False)
                if lane.road_mark_type != 'none':
                    if lane.road_mark_type == 'solid' or \
                        lane.road_mark_type == 'broken':
                        strip_to_lane.append(idx_lane)
                        strip_is_road_mark.append(True)
                    else:
                        # Double line
                        strip_to_lane.append(idx_lane)
                        strip_to_lane.append(idx_lane)
                        strip_to_lane.append(idx_lane)
                        strip_is_road_mark.append(True)
                        strip_is_road_mark.append(False)
                        strip_is_road_mark.append(True)
        return strip_to_lane, strip_is_road_mark

    def get_road_mark_material(self, color):
        '''
            Return material name for road mark color.
        '''
        mapping_color_material = {
            'white': 'road_mark_white',
            'yellow': 'road_mark_yellow',
        }
        return mapping_color_material[color]

    def get_face_materials(self, lanes, strips_s_boundaries):
        '''
            Return dictionary with index of faces for each material.
        '''
        materials = {'asphalt': [], 'road_mark_white': [], 'road_mark_yellow': [], 'grass': []}
        idx_face = 0
        strip_to_lane, strip_is_road_mark = self.get_strip_to_lane_mapping(lanes)
        for idx_strip in range(len(strips_s_boundaries)):
            idx_lane = strip_to_lane[idx_strip]
            if strip_is_road_mark[idx_strip]:
                line_toggle = strips_s_boundaries[idx_strip][0]
                num_faces = int(len(strips_s_boundaries[idx_strip][1]) - 1)
                material = self.get_road_mark_material(lanes[idx_lane].road_mark_color)
                # Step through faces of a road mark strip
                for idx in range(num_faces):
                    # Determine material
                    if lanes[idx_lane].road_mark_type == 'solid':
                        materials[material].append(idx_face)
                        idx_face += 1
                    elif lanes[idx_lane].road_mark_type == 'broken':
                        if line_toggle:
                            materials[material].append(idx_face)
                            line_toggle = False
                        else:
                            materials['asphalt'].append(idx_face)
                            line_toggle = True
                        idx_face += 1
                    elif lanes[idx_lane].road_mark_type == 'solid_solid':
                        materials[material].append(idx_face)
                        materials['asphalt'].append(idx_face + 1)
                        materials[material].append(idx_face + 2)
                        idx_face += 3
            else:
                if lanes[idx_lane].type == 'median':
                    materials['grass'].append(idx_face)
                elif lanes[idx_lane].type == 'shoulder':
                    materials['grass'].append(idx_face)
                else:
                    materials['asphalt'].append(idx_face)
                idx_face += 1

        return materials
    
    def execute(self, context):
        '''
        Called every time your operator runs
        '''
        self.init_state()
        self.create_3d_object(context)
        return {'FINISHED'}

def register():
    bpy.utils.register_class(PR_OT_road)
    bpy.utils.register_class(PR_enum_lane)
    bpy.utils.register_class(PR_road_properties)   
    # Register property groups
    bpy.types.Scene.road_properties = bpy.props.PointerProperty(type=PR_road_properties)

def unregister():
    bpy.utils.unregister_class(PR_OT_road)
    bpy.utils.unregister_class(PR_enum_lane)
    bpy.utils.unregister_class(PR_road_properties)
    # Get rid of property groups
    del bpy.types.Scene.road_properties

if __name__ == '__main__':
    register()
