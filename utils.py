__author__ = 'Nathan.Woodrow'

import math
from qgis.core import QgsPoint
from collections import namedtuple

PointT = namedtuple("Point", "x y z")

def Point(x, y, z=0):
    return PointT(x,y,z)

def to_qgspoints(points, repeatfirst=False):
    """
    Generate a QgsPoint list from a list of x,y pairs
    :param repeatfirst: Repeat the first item in the list for each other point
    :return:
    """
    if not repeatfirst:
        # Just return a full list like normal
        return [QgsPoint(point[0], point[1]) for point in points]
    else:
        pointlist = []

        # Pop the first point
        points = iter(points)
        v0 = points.next()
        v0 = QgsPoint(v0[0], v0[1])

        # Loop the rest
        for point in points:
            p = QgsPoint(point[0], point[1])
            pointlist.append(v0)
            pointlist.append(p)
        return pointlist


def pairs(points, matchtail):
    """
    Return a list of pairs from a list of points
    :param matchtail: The HEAD of the next pair will be the TAIL of the current pair e.g pair[1] == next[0]
    :param points: List of points to process
    :return:
    """
    if matchtail:
        it = zip(points, points[1:])
    else:
        it = zip(points[::2], points[1::2])

    for start, end in it:
        yield [start, end]


def nextvertex(reference_point, distance, angle, virtical_anagle=90):
    """
    Return the next vertex given a start, angle, distance.
    :param reference_point: Start point
    :param distance: Distance to the next vertex
    :param angle: Angle is assumed to already include north correction
    :param virtical_anagle: Virtical angle for height correction
    :return: A tuple of x,y,z for the next point.
    """
    angle = math.radians(angle)
    virtical_anagle = math.radians(virtical_anagle)
    d1 = distance * math.sin(virtical_anagle)
    x = reference_point[0] + d1 * math.sin(angle)
    y = reference_point[1] + d1 * math.cos(angle)
    z = reference_point[2] + distance * math.cos(virtical_anagle)
    return Point(x, y, z)


def arc_length(radius, c_angle):
    """
    The length of the total arc given the radius and central angle.
    :param radius: Radius
    :param c_angle: Central angle of the circle
    :return: The length of the arc
    """
    return 2 * math.pi * radius * ( c_angle / 360 )


def points_on_arc(count, center, radius, start, end):
    pass


def angle_to(p1, p2):
    xDiff = p1.x - p2.x
    yDiff = p1.y - p2.y
    rads = math.atan2(xDiff, yDiff)
    angle = math.degrees(rads)
    if angle < 0:
        angle += 360
    return angle


def calculate_center(start, end, radius, distance):
    def func(diff):
        half = distance / 2
        return math.sqrt(radius ** 2 - half ** 2) * diff / distance

    midpoint = calculate_midpoint(start, end)
    return Point(midpoint.x - func(start.y - end.y), midpoint.y - func(end.x - start.x))


def calculate_midpoint(start, end):
    midpoint = Point((start.x + end.x) / 2, (start.y + end.y) / 2)
    return midpoint

class Direction:
    CLOCKWISE = 0
    ANTICLOCKWISE = 1

    @classmethod
    def resolve(cls, value):
        if value == 'a' or value == "anticlockwise":
            return Direction.ANTICLOCKWISE
        else:
            return Direction.CLOCKWISE


def arc_points(start, end, distance, radius, point_count=20, direction=Direction.CLOCKWISE):
    center = calculate_center(start, end, radius, distance)

    first_angle = angle_to(start, center)
    last_angle = angle_to(end, center)
    if direction == Direction.ANTICLOCKWISE:
        last_angle, first_angle = first_angle, last_angle

    if first_angle < last_angle:
        sweep = last_angle - first_angle
    elif first_angle > last_angle:
        last_angle += 360
        sweep = last_angle - first_angle
    else:
        sweep = 0

    alpha = sweep / float(point_count)
    if sweep < 0:
        alpha *= -1.0

    print "First:", first_angle
    print "Last:", last_angle
    print "Sweep", sweep
    print "Alpha", alpha

    a = first_angle
    for i in range(point_count + 1):
        a += alpha
        if not a >= last_angle and not a <= first_angle:
            yield nextvertex(center, radius, a)


