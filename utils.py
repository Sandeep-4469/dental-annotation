import math
def line_length(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def midpoint(p1, p2):
    return ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)