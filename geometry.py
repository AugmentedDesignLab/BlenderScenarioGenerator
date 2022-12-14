from math import pi, ceil, cos, inf, sin, pi, degrees, atan2, radians, sqrt
import bpy
from mathutils import Vector, Matrix, Euler
import helper
from pyclothoids import Clothoid

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
            point_end = helper.project_point_vector(params['point_start'].to_2d(),
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
    
    # Since for this geometry, sample_plan_view below doesn't make sense,
    # I'm writing another function just to get an xyz point somewhere along the road
    def get_xyz_point_given_st(self, s=2.0, t=0.0):
        x_start = self.params['point_start'].x
        y_start = self.params['point_start'].y
        x_end = self.params['point_end'].x
        y_end = self.params['point_end'].y

        start = Vector((x_start, y_start, 0.0))
        end = Vector((x_end, y_end, 0.0))
        road_vec = end - start
        road_vec = road_vec.normalized()
        road_point = road_vec * s
        angle = atan2(s,t)
        rotation_angle = (pi/2)-angle
        eu = Euler((0.0, 0.0, rotation_angle), 'XYZ')
        road_vec.rotate(eu)
        xyz = road_vec * (sqrt((s**2) + (t**2)))
        return xyz

    def sample_plan_view(self, s):
        x_s = s
        y_s = 0.0
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

class Arc():

    def __init__(self, point_end):
        valid, self.radius, self.angle, self.determinant = \
            self.get_radius_angle_det(Vector((0.0, 0.0, 0.0)), point_end)
        if valid:
            if self.determinant > 0:
                self.offset_angle = 0
                self.curvature = 1/self.radius
                self.offset_y = self.radius
                if self.angle < 0:
                    # Limit angle to 180 degrees
                    self.heading_end  = pi
                    self.angle = pi
                else:
                    self.heading_end  = self.angle
            else:
                self.offset_angle = pi
                self.curvature = -1/self.radius
                self.offset_y = -self.radius
                if self.angle > 0:
                    # Limit angle to 180 degrees
                    self.heading_end = pi
                    self.angle = -pi
                else:
                    self.heading_end = self.angle
            self.length = self.radius * abs(self.angle)
        else:
            self.radius = inf
            self.curvature = 0
            self.offset_y = self.radius
            self.angle = 0
            self.offset_angle = 0
            self.heading_end = 0
            self.length = point_end.length


    def get_radius_angle_det(self, point_start, point_end):
        '''
            Calculate center and radius of the arc that is defined by the
            starting point (predecessor connecting point), the start heading
            (heading of the connected road) and the end point. Also return
            determinant that tells us if point end is left or right of heading
            direction.
        '''
        # The center of the arc is the crossing point of line orthogonal to the
        # predecessor road in the connecting point and the perpendicular
        # bisector of the connection between start and end point.
        p = point_start.to_2d()
        a = Vector((0.0, 1.0))
        q = 0.5 * (point_start + point_end).to_2d()
        b_normal = (point_start - point_end)
        b = Vector((-b_normal[1], b_normal[0]))
        if a.orthogonal() @ b != 0:
            # See https://mathepedia.de/Schnittpunkt.html for crossing point equation
            center = 1 / (a @ b.orthogonal()) * ((q @ b.orthogonal()) * a - (p @ a.orthogonal()) * b)
            radius = (center - p).length
            # Calculate determinant to know where to start drawing the arc {0, pi}
            vec_hdg = Vector((1.0, 0.0, 0.0))
            determinant = Matrix([vec_hdg.to_2d(), (point_end - point_start).to_2d()]).transposed().determinant()
            angle = (point_end.to_2d() - center).angle_signed(point_start.to_2d() - center)
            return True, radius, angle, determinant
        else:
            return False, 0, 0, 0

class DSC_geometry_arc(DSC_geometry):

    def update_plan_view(self, params, geometry_solver):
        # Calculate transform between global and local coordinates
        self.update_local_to_global(params['point_start'], params['heading_start'],
            params['point_end'], params['heading_end'])

        # Transform end point to local coordinates, constrain and transform back
        if self.point_end_local.x < 0:
            self.point_end_local.x = 0
        point_end_global = self.matrix_world @ self.point_end_local

        # Calculate geometry
        self.geometry_base = Arc(self.point_end_local)

        # Remember geometry parameters
        self.params['curve'] = 'arc'
        self.params['point_start'] = params['point_start']
        self.params['heading_start'] = params['heading_start']
        self.params['point_end'] = point_end_global
        self.params['heading_end'] = params['heading_start'] + self.geometry_base.heading_end
        self.params['curvature_start'] = self.geometry_base.curvature
        self.params['curvature_end'] = self.geometry_base.curvature
        self.params['length'] = self.geometry_base.length

    def sample_plan_view(self, s):
        if self.geometry_base.radius == inf:
            # Circle degenerates into a straight line
            x_s = s
            y_s = 0
            hdg_t = pi/2
        else:
            # We have a circle
            angle_s = s / self.geometry_base.radius
            if self.geometry_base.determinant > 0:
                x_s = cos(angle_s + self.geometry_base.offset_angle - pi/2) \
                        * self.geometry_base.radius
                y_s = sin(angle_s + self.geometry_base.offset_angle - pi/2) \
                        * self.geometry_base.radius + self.geometry_base.offset_y
                hdg_t = angle_s + pi/2
            else:
                x_s = cos(-angle_s + self.geometry_base.offset_angle - pi/2) \
                        * self.geometry_base.radius
                y_s = sin(-angle_s + self.geometry_base.offset_angle - pi/2) \
                        * self.geometry_base.radius + self.geometry_base.offset_y
                hdg_t = -angle_s + pi/2
        curvature = self.geometry_base.curvature
        return x_s, y_s, curvature, hdg_t