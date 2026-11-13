from __future__ import annotations

import contextlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import takewhile

import mpmath

MEASUREMENT_DPS = 60
CERTIFICATION_DPS = (50, 100, 200, 500)
UNIT_SQUARE_HALF_SIDE = 0.5
BROAD_PHASE_PADDING = 1e-7
FLOAT_CONTACT_TOLERANCE = 1e-8

Interval = mpmath.ctx_iv.ivmpf
Point = tuple[float, float]
IntervalPoint = tuple[Interval, Interval]
FloatCorners = tuple[Point, Point, Point, Point]
IntervalCorners = tuple[IntervalPoint, IntervalPoint, IntervalPoint, IntervalPoint]


@dataclass(frozen=True)
class Square:
    x: str
    y: str
    angle: str


@dataclass(frozen=True)
class FloatSquare:
    corners: FloatCorners
    angle: float


@contextlib.contextmanager
def working_precision(dps: int):
    previous_mp_dps = mpmath.mp.dps
    previous_iv_dps = mpmath.iv.dps
    try:
        mpmath.mp.dps = dps
        mpmath.iv.dps = dps
        yield
    finally:
        mpmath.mp.dps = previous_mp_dps
        mpmath.iv.dps = previous_iv_dps


def float_corners(x: float, y: float, angle: float) -> FloatCorners:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    first_dx = UNIT_SQUARE_HALF_SIDE * (cosine - sine)
    first_dy = UNIT_SQUARE_HALF_SIDE * (sine + cosine)
    second_dx = UNIT_SQUARE_HALF_SIDE * (-cosine - sine)
    second_dy = UNIT_SQUARE_HALF_SIDE * (-sine + cosine)
    return (
        (x + first_dx, y + first_dy),
        (x + second_dx, y + second_dy),
        (x - first_dx, y - first_dy),
        (x - second_dx, y - second_dy),
    )


def prepare_float_squares(squares: Sequence[Square]) -> tuple[FloatSquare, ...]:
    with working_precision(MEASUREMENT_DPS):
        origin_x = mpmath.mpf(squares[0].x)
        origin_y = mpmath.mpf(squares[0].y)
        full_turn = 2 * mpmath.pi
        poses = tuple(
            (
                float(mpmath.mpf(square.x) - origin_x),
                float(mpmath.mpf(square.y) - origin_y),
                float(mpmath.mpf(square.angle) % full_turn),
            )
            for square in squares
        )
    return tuple(FloatSquare(float_corners(x, y, angle), angle) for x, y, angle in poses)


def measure_side_length(squares: Sequence[Square], dps: int = MEASUREMENT_DPS) -> mpmath.mpf:
    with working_precision(dps):
        origin_x = mpmath.mpf(squares[0].x)
        origin_y = mpmath.mpf(squares[0].y)
        corners = tuple(
            corner
            for square in squares
            for corner in mp_corners(
                mpmath.mpf(square.x) - origin_x,
                mpmath.mpf(square.y) - origin_y,
                mpmath.mpf(square.angle),
            )
        )
        x_coordinates = tuple(x for x, _ in corners)
        y_coordinates = tuple(y for _, y in corners)
        return max(
            max(x_coordinates) - min(x_coordinates),
            max(y_coordinates) - min(y_coordinates),
        )


def mp_corners(x: mpmath.mpf, y: mpmath.mpf, angle: mpmath.mpf):
    cosine = mpmath.cos(angle)
    sine = mpmath.sin(angle)
    half_side = mpmath.mpf(1) / 2
    first_dx = half_side * (cosine - sine)
    first_dy = half_side * (sine + cosine)
    second_dx = half_side * (-cosine - sine)
    second_dy = half_side * (-sine + cosine)
    return (
        (x + first_dx, y + first_dy),
        (x + second_dx, y + second_dy),
        (x - first_dx, y - first_dy),
        (x - second_dx, y - second_dy),
    )


def interval_corners(square: Square) -> IntervalCorners:
    x = mpmath.iv.mpf(square.x)
    y = mpmath.iv.mpf(square.y)
    angle = mpmath.iv.mpf(square.angle)
    cosine = mpmath.iv.cos(angle)
    sine = mpmath.iv.sin(angle)
    half_side = mpmath.iv.mpf("0.5")
    first_dx = half_side * (cosine - sine)
    first_dy = half_side * (sine + cosine)
    second_dx = half_side * (-cosine - sine)
    second_dy = half_side * (-sine + cosine)
    return (
        (x + first_dx, y + first_dy),
        (x + second_dx, y + second_dy),
        (x - first_dx, y - first_dy),
        (x - second_dx, y - second_dy),
    )


def candidate_pairs(squares: Sequence[FloatSquare]) -> tuple[tuple[int, int], ...]:
    bounds = tuple(enumerate(tuple(padded_bounds(square.corners) for square in squares)))
    ordered_bounds = tuple(sorted(bounds, key=lambda item: item[1][0]))
    return tuple(
        (min(first_index, second_index), max(first_index, second_index))
        for first_position, (first_index, first_bounds) in enumerate(ordered_bounds)
        for second_index, second_bounds in takewhile(
            lambda item: item[1][0] <= first_bounds[2],
            ordered_bounds[first_position + 1 :],
        )
        if bounds_overlap(first_bounds, second_bounds)
    )


def padded_bounds(corners: FloatCorners) -> tuple[float, float, float, float]:
    x_coordinates = tuple(x for x, _ in corners)
    y_coordinates = tuple(y for _, y in corners)
    return (
        min(x_coordinates) - BROAD_PHASE_PADDING,
        min(y_coordinates) - BROAD_PHASE_PADDING,
        max(x_coordinates) + BROAD_PHASE_PADDING,
        max(y_coordinates) + BROAD_PHASE_PADDING,
    )


def bounds_overlap(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> bool:
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def float_pair_status(first: FloatSquare, second: FloatSquare) -> str:
    axes = separation_axes(first.angle, second.angle)
    projections = tuple(
        projection_overlap(first.corners, second.corners, axis)
        for axis in axes
    )
    if min(projections) < -FLOAT_CONTACT_TOLERANCE:
        return "separated"
    if min(projections) > FLOAT_CONTACT_TOLERANCE:
        return "overlapping"
    return "undecided"


def separation_axes(first_angle: float, second_angle: float) -> tuple[Point, ...]:
    first_cosine, first_sine = math.cos(first_angle), math.sin(first_angle)
    second_cosine, second_sine = math.cos(second_angle), math.sin(second_angle)
    return (
        (first_cosine, first_sine),
        (-first_sine, first_cosine),
        (second_cosine, second_sine),
        (-second_sine, second_cosine),
    )


def projection_overlap(first: FloatCorners, second: FloatCorners, axis: Point) -> float:
    axis_x, axis_y = axis
    first_projections = tuple(axis_x * x + axis_y * y for x, y in first)
    second_projections = tuple(axis_x * x + axis_y * y for x, y in second)
    return min(max(first_projections), max(second_projections)) - max(
        min(first_projections), min(second_projections)
    )


def certified_pair_separated(first: Square, second: Square) -> bool | None:
    first_corners = interval_corners(first)
    second_corners = interval_corners(second)
    first_angle = mpmath.iv.mpf(first.angle)
    second_angle = mpmath.iv.mpf(second.angle)
    first_cosine, first_sine = mpmath.iv.cos(first_angle), mpmath.iv.sin(first_angle)
    second_cosine, second_sine = mpmath.iv.cos(second_angle), mpmath.iv.sin(second_angle)
    axes = (
        (first_cosine, first_sine),
        (-first_sine, first_cosine),
        (second_cosine, second_sine),
        (-second_sine, second_cosine),
    )
    undecided_axis_found = False
    for axis_x, axis_y in axes:
        first_projections = tuple(axis_x * x + axis_y * y for x, y in first_corners)
        second_projections = tuple(axis_x * x + axis_y * y for x, y in second_corners)
        first_minimum, first_maximum = interval_span(first_projections)
        second_minimum, second_maximum = interval_span(second_projections)
        overlap = interval_min((first_maximum, second_maximum)) - interval_max(
            (first_minimum, second_minimum)
        )
        comparison = interval_less_or_equal(overlap, mpmath.iv.mpf("0"))
        if comparison is True:
            return True
        if comparison is None:
            undecided_axis_found = True
    return None if undecided_axis_found else False


def interval_span(values: Sequence[Interval]) -> tuple[Interval, Interval]:
    return interval_min(values), interval_max(values)


def interval_min(values: Sequence[Interval]) -> Interval:
    return mpmath.iv.mpf((min(value.a for value in values), min(value.b for value in values)))


def interval_max(values: Sequence[Interval]) -> Interval:
    return mpmath.iv.mpf((max(value.a for value in values), max(value.b for value in values)))


def interval_less_or_equal(first: Interval, second: Interval) -> bool | None:
    try:
        return first <= second
    except ValueError:
        return None


def certify_pair_separation(first: Square, second: Square) -> bool | None:
    for dps in CERTIFICATION_DPS:
        with working_precision(dps):
            separated = certified_pair_separated(first, second)
        if separated is not None:
            return separated
    return None
