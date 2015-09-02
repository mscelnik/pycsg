# import math
# import operator
# from csg.geom import *


class CSG(object):
    """
    Constructive Solid Geometry (CSG) is a modeling technique that uses Boolean
    operations like union and intersection to combine 3D solids. This library
    implements CSG operations on meshes elegantly and concisely using BSP trees,
    and is meant to serve as an easily understandable implementation of the
    algorithm. All edge cases involving overlapping coplanar polygons in both
    solids are correctly handled.

    Example usage::

        from csg.core import CSG

        cube = CSG.cube();
        sphere = CSG.sphere({'radius': 1.3});
        polygons = cube.subtract(sphere).toPolygons();

    ## Implementation Details

    All CSG operations are implemented in terms of two functions, `clipTo()` and
    `invert()`, which remove parts of a BSP tree inside another BSP tree and
    swap solid and empty space, respectively. To find the union of `a` and `b`,
    we want to remove everything in `a` inside `b` and everything in `b` inside
    `a`, then combine polygons from `a` and `b` into one solid::

        a.clipTo(b);
        b.clipTo(a);
        a.build(b.allPolygons());

    The only tricky part is handling overlapping coplanar polygons in both
    trees. The code above keeps both copies, but we need to keep them in one
    tree and remove them in the other tree. To remove them from `b` we can clip
    the inverse of `b` against `a`. The code for union now looks like this::

        a.clipTo(b);
        b.clipTo(a);
        b.invert();
        b.clipTo(a);
        b.invert();
        a.build(b.allPolygons());

    Subtraction and intersection naturally follow from set operations. If
    union is `A | B`, subtraction is `A - B = ~(~A | B)` and intersection is
    `A & B = ~(~A | ~B)` where `~` is the complement operator.

    ## License

    Copyright (c) 2011 Evan Wallace (http://madebyevan.com/), under the MIT
    license.

    Python port Copyright (c) 2012 Tim Knip (http://www.floorplanner.com), under
    the MIT license. Additions by Alex Pletzer The Pennsylvania State
    University.  Updated (2015) for Python 3.4 compatibility and removing PEP8
    errors by Matthew Celnik, on his own time.
    """
    def __init__(self):
        self.polygons = []

    @classmethod
    def fromPolygons(cls, polygons):
        csg = CSG()
        csg.polygons = polygons
        return csg

    def clone(self):
        csg = CSG()
        csg.polygons = list(map(lambda p: p.clone(), self.polygons))
        return csg

    def toPolygons(self):
        return self.polygons

    def translate(self, disp):
        """
        Translate Geometry.
           disp: displacement (array of floats)
        """
        from . import geom
        d = geom.Vector(disp[0], disp[1], disp[2])
        for poly in self.polygons:
            for v in poly.vertices:
                v.pos = v.pos.plus(d)
                # no change to the normals

    def rotate(self, axis, angleDeg):
        """
        Rotate geometry.
           axis: axis of rotation (array of floats)
           angleDeg: rotation angle in degrees
        """
        import math
        from . import geom
        ax = geom.Vector(axis[0], axis[1], axis[2]).unit()
        cosAngle = math.cos(math.pi * angleDeg / 180.)
        sinAngle = math.sin(math.pi * angleDeg / 180.)

        def newVector(v):
            vA = v.dot(ax)
            vPerp = v.minus(ax.times(vA))
            vPerpLen = vPerp.length()
            if vPerpLen > 0:
                u1 = vPerp.unit()
                u2 = u1.cross(ax)
                vCosA = vPerpLen*cosAngle
                vSinA = vPerpLen*sinAngle
                return ax.times(vA).plus(u1.times(vCosA).plus(u2.times(vSinA)))
            else:
                # zero distance to axis, no need to rotate
                return v

        for poly in self.polygons:
            for vert in poly.vertices:
                vert.pos = newVector(vert.pos)
                normal = vert.normal
                if normal.length() > 0:
                    # print (vert.normal)
                    vert.normal = newVector(vert.normal)

    def toVerticesAndPolygons(self):
        """
        Return list of vertices, polygons (cells), and the total
        number of vertex indices in the polygon connectivity list
        (count).
        """
        import operator
        verts = []
        polys = []
        vertexIndexMap = {}
        count = 0
        for poly in self.polygons:
            verts = poly.vertices
            cell = []
            for v in poly.vertices:
                p = v.pos
                vKey = (p[0], p[1], p[2])
                if vKey not in vertexIndexMap:
                    vertexIndexMap[vKey] = len(vertexIndexMap)
                index = vertexIndexMap[vKey]
                cell.append(index)
                count += 1
            polys.append(cell)
        # sort by index
        sortedVertexIndex = sorted(vertexIndexMap.items(),
                                   key=operator.itemgetter(1))
        verts = [v[0] for v in sortedVertexIndex]
        return verts, polys, count

    def saveVTK(self, filename):
        """
        Save polygons in VTK file.
        """
        with open(filename, 'w') as f:
            f.write('# vtk DataFile Version 3.0\n')
            f.write('pycsg output\n')
            f.write('ASCII\n')
            f.write('DATASET POLYDATA\n')

            verts, cells, count = self.toVerticesAndPolygons()

            f.write('POINTS {} float\n'.format(len(verts)))
            for v in verts:
                f.write('{} {} {}\n'.format(v[0], v[1], v[2]))
            numCells = len(cells)
            f.write('POLYGONS {} {}\n'.format(numCells, count + numCells))
            for cell in cells:
                f.write('{} \n'.format(len(cell)))
                for index in cell:
                    f.write('{} \n'.format(index))

    def union(self, csg):
        """
        Return a new CSG solid representing space in either this solid or in the
        solid `csg`. Neither this solid nor the solid `csg` are modified.::

            A.union(B)

            +-------+            +-------+
            |       |            |       |
            |   A   |            |       |
            |    +--+----+   =   |       +----+
            +----+--+    |       +----+       |
                 |   B   |            |       |
                 |       |            |       |
                 +-------+            +-------+
        """
        from . import geom
        a = geom.BSPNode(self.clone().polygons)
        b = geom.BSPNode(csg.clone().polygons)
        a.clipTo(b)
        b.clipTo(a)
        b.invert()
        b.clipTo(a)
        b.invert()
        a.build(b.allPolygons())
        return CSG.fromPolygons(a.allPolygons())

    def __add__(self, csg):
        return self.union(csg)

    def subtract(self, csg):
        """
        Return a new CSG solid representing space in this solid but not in the
        solid `csg`. Neither this solid nor the solid `csg` are modified.::

            A.subtract(B)

            +-------+            +-------+
            |       |            |       |
            |   A   |            |       |
            |    +--+----+   =   |    +--+
            +----+--+    |       +----+
                 |   B   |
                 |       |
                 +-------+
        """
        from . import geom
        a = geom.BSPNode(self.clone().polygons)
        b = geom.BSPNode(csg.clone().polygons)
        a.invert()
        a.clipTo(b)
        b.clipTo(a)
        b.invert()
        b.clipTo(a)
        b.invert()
        a.build(b.allPolygons())
        a.invert()
        return CSG.fromPolygons(a.allPolygons())

    def __sub__(self, csg):
        return self.subtract(csg)

    def intersect(self, csg):
        """
        Return a new CSG solid representing space both this solid and in the
        solid `csg`. Neither this solid nor the solid `csg` are modified.::

            A.intersect(B)

            +-------+
            |       |
            |   A   |
            |    +--+----+   =   +--+
            +----+--+    |       +--+
                 |   B   |
                 |       |
                 +-------+
        """
        from . import geom
        a = geom.BSPNode(self.clone().polygons)
        b = geom.BSPNode(csg.clone().polygons)
        a.invert()
        b.clipTo(a)
        b.invert()
        a.clipTo(b)
        b.clipTo(a)
        a.build(b.allPolygons())
        a.invert()
        return CSG.fromPolygons(a.allPolygons())

    def __mul__(self, csg):
        return self.intersect(csg)

    def inverse(self):
        """
        Return a new CSG solid with solid and empty space switched. This solid
        is not modified.
        """
        csg = self.clone()
        map(lambda p: p.flip(), csg.polygons)
        return csg

    @classmethod
    def cube(cls, center=[0, 0, 0],  radius=[1, 1, 1]):
        """
        Construct an axis-aligned solid cuboid. Optional parameters are `center`
        and `radius`, which default to `[0, 0, 0]` and `[1, 1, 1]`. The radius
        can be specified using a single number or a list of three numbers, one
        for each axis.

        Example code::

            cube = CSG.cube(
              center=[0, 0, 0],
              radius=1
            )
        """
        from . import geom
        c = geom.Vector(0, 0, 0)
        r = [1, 1, 1]
        if isinstance(center, list):
            c = geom.Vector(center)

        if isinstance(radius, list):
            r = radius
        else:
            r = [radius, radius, radius]

        vertex_data = [
            [[0, 4, 6, 2], [-1, 0, 0]],
            [[1, 3, 7, 5], [+1, 0, 0]],
            [[0, 1, 5, 4], [0, -1, 0]],
            [[2, 6, 7, 3], [0, +1, 0]],
            [[0, 2, 3, 1], [0, 0, -1]],
            [[4, 5, 7, 6], [0, 0, +1]]]

        polygons = []
        for v in vertex_data:
            vertices = []
            for i in v[0]:
                vector = geom.Vector(
                    c.x + r[0] * (2 * bool(i & 1) - 1),
                    c.y + r[1] * (2 * bool(i & 2) - 1),
                    c.z + r[2] * (2 * bool(i & 4) - 1))
                vertex = geom.Vertex(vector, None)
                vertices.append(vertex)
            polygon = geom.Polygon(vertices)
            polygons.append(polygon)

        # polygons = map(
        #     lambda v: geom.Polygon(
        #         list(map(lambda i:
        #              geom.Vertex(
        #                 geom.Vector(
        #                     c.x + r[0] * (2 * bool(i & 1) - 1),
        #                     c.y + r[1] * (2 * bool(i & 2) - 1),
        #                     c.z + r[2] * (2 * bool(i & 4) - 1)
        #                 ),
        #                 None
        #             ), v[0]))),
        #             [
        #                 [[0, 4, 6, 2], [-1, 0, 0]],
        #                 [[1, 3, 7, 5], [+1, 0, 0]],
        #                 [[0, 1, 5, 4], [0, -1, 0]],
        #                 [[2, 6, 7, 3], [0, +1, 0]],
        #                 [[0, 2, 3, 1], [0, 0, -1]],
        #                 [[4, 5, 7, 6], [0, 0, +1]]
        #             ])

        return CSG.fromPolygons(list(polygons))

    @classmethod
    def sphere(cls, **kwargs):
        """ Returns a sphere.

            Kwargs:
                center (list): Center of sphere, default [0, 0, 0].

                radius (float): Radius of sphere, default 1.0.

                slices (int): Number of slices, default 16.

                stacks (int): Number of stacks, default 8.
        """
        import math
        from . import geom
        center = kwargs.get('center', [0.0, 0.0, 0.0])
        if isinstance(center, float):
            center = [center, center, center]
        c = geom.Vector(center)
        r = kwargs.get('radius', 1.0)
        if isinstance(r, list) and len(r) > 2:
            r = r[0]
        slices = kwargs.get('slices', 16)
        stacks = kwargs.get('stacks', 8)
        polygons = []
        def appendVertex(vertices, theta, phi):
            d = geom.Vector(
                center[0] + r * math.cos(theta) * math.sin(phi),
                center[1] + r * math.cos(phi),
                center[2] + r * math.sin(theta) * math.sin(phi))
            vertices.append(geom.Vertex(c.plus(d.times(r)), d))

        dTheta = math.pi * 2.0 / float(slices)
        dPhi = math.pi / float(stacks)
        for i in range(0, slices):
            for j in range(0, stacks):
                vertices = []
                appendVertex(vertices, i * dTheta, j * dPhi)
                i1, j1 = (i + 1) % slices, j + 1
                if j > 0:
                    appendVertex(vertices, i1 * dTheta, j * dPhi)
                if j < stacks - 1:
                    appendVertex(vertices, i1 * dTheta, j1 * dPhi)
                appendVertex(vertices, i * dTheta, j1 * dPhi)
                polygons.append(geom.Polygon(vertices))

        return CSG.fromPolygons(polygons)

    @classmethod
    def cylinder(cls, **kwargs):
        """ Returns a cylinder.

            Kwargs:
                start (list): Start of cylinder, default [0, -1, 0].

                end (list): End of cylinder, default [0, 1, 0].

                radius (float): Radius of cylinder, default 1.0.

                slices (int): Number of slices, default 16.
        """
        import math
        from . import geom
        s = kwargs.get('start', geom.Vector(0.0, -1.0, 0.0))
        e = kwargs.get('end', geom.Vector(0.0, 1.0, 0.0))
        if isinstance(s, list):
            s = geom.Vector(*s)
        if isinstance(e, list):
            e = geom.Vector(*e)
        r = kwargs.get('radius', 1.0)
        slices = kwargs.get('slices', 16)
        ray = e.minus(s)

        axisZ = ray.unit()
        isY = (math.fabs(axisZ.y) > 0.5)
        axisX = geom.Vector(float(isY), float(not isY), 0).cross(axisZ).unit()
        axisY = axisX.cross(axisZ).unit()
        start = geom.Vertex(s, axisZ.negated())
        end = geom.Vertex(e, axisZ.unit())
        polygons = []

        def point(stack, angle, normalBlend):
            out = axisX.times(math.cos(angle)).plus(
                axisY.times(math.sin(angle)))
            pos = s.plus(ray.times(stack)).plus(out.times(r))
            normal = out.times(1.0 - math.fabs(normalBlend)).plus(
                axisZ.times(normalBlend))
            return geom.Vertex(pos, normal)

        dt = math.pi * 2.0 / float(slices)
        for i in range(0, slices):
            t0 = i * dt
            i1 = (i + 1) % slices
            t1 = i1 * dt
            polygons.append(geom.Polygon([start.clone(),
                                         point(0., t0, -1.),
                                         point(0., t1, -1.)]))
            polygons.append(geom.Polygon([point(0., t1, 0.),
                                         point(0., t0, 0.),
                                         point(1., t0, 0.),
                                         point(1., t1, 0.)]))
            polygons.append(geom.Polygon([end.clone(),
                                         point(1., t1, 1.),
                                         point(1., t0, 1.)]))

        return CSG.fromPolygons(polygons)

    @classmethod
    def cone(cls, **kwargs):
        """ Returns a cone.

            Kwargs:
                start (list): Start of cone, default [0, -1, 0].

                end (list): End of cone, default [0, 1, 0].

                radius (float): Maximum radius of cone at start, default 1.0.

                slices (int): Number of slices, default 16.
        """
        import math
        from . import geom
        s = kwargs.get('start', geom.Vector(0.0, -1.0, 0.0))
        e = kwargs.get('end', geom.Vector(0.0, 1.0, 0.0))
        if isinstance(s, list):
            s = geom.Vector(*s)
        if isinstance(e, list):
            e = geom.Vector(*e)
        r = kwargs.get('radius', 1.0)
        slices = kwargs.get('slices', 16)
        ray = e.minus(s)

        axisZ = ray.unit()
        isY = (math.fabs(axisZ.y) > 0.5)
        axisX = geom.Vector(float(isY), float(not isY), 0).cross(axisZ).unit()
        axisY = axisX.cross(axisZ).unit()
        startNormal = axisZ.negated()
        start = geom.Vertex(s, startNormal)
        polygons = []

        taperAngle = math.atan2(r, ray.length())
        sinTaperAngle = math.sin(taperAngle)
        cosTaperAngle = math.cos(taperAngle)
        def point(angle):
            # radial direction pointing out
            out = axisX.times(math.cos(angle)).plus(
                axisY.times(math.sin(angle)))
            pos = s.plus(out.times(r))
            # normal taking into account the tapering of the cone
            normal = out.times(cosTaperAngle).plus(axisZ.times(sinTaperAngle))
            return pos, normal

        dt = math.pi * 2.0 / float(slices)
        for i in range(0, slices):
            t0 = i * dt
            i1 = (i + 1) % slices
            t1 = i1 * dt
            # coordinates and associated normal pointing outwards of the cone's
            # side
            p0, n0 = point(t0)
            p1, n1 = point(t1)
            # average normal for the tip
            nAvg = n0.plus(n1).times(0.5)
            # polygon on the low side (disk sector)
            polyStart = geom.Polygon([start.clone(),
                                 geom.Vertex(p0, startNormal),
                                 geom.Vertex(p1, startNormal)])
            polygons.append(polyStart)
            # polygon extending from the low side to the tip
            polySide = geom.Polygon([geom.Vertex(p0, n0),
                                     geom.Vertex(e, nAvg),
                                     geom.Vertex(p1, n1)])
            polygons.append(polySide)

        return CSG.fromPolygons(polygons)
