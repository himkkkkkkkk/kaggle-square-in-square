import json, math, sys, time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.spatial import cKDTree
from evaluator import evaluate_layout

ROOT = Path(__file__).resolve().parents[1]
INCUMBENTS = Path(__file__).with_name("incumbents.json")
BLOCKS_FILE = Path(__file__).with_name("blocks.json")
RESULT = Path(__file__).with_name("result.json")

TIME_LIMIT = 8.1
START_TIME = time.time()
EXTRA_BLOCKS = {}

LOCAL_N_MAX = 360
CHECK_RADIUS = 1.75
OPT_RADIUS = 2.8


def time_left():
    return TIME_LIMIT - (time.time() - START_TIME)


def bounds(arr):
    xy = arr[:, :2]
    th = arr[:, 2]
    h = 0.5 * (np.abs(np.cos(th)) + np.abs(np.sin(th)))
    return (
        float(np.min(xy[:, 0] - h)), float(np.max(xy[:, 0] + h)),
        float(np.min(xy[:, 1] - h)), float(np.max(xy[:, 1] + h)),
    )


def layout_side(layout):
    arr = np.asarray(layout, dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 3 or len(arr) == 0:
        return 0.0
    minx, maxx, miny, maxy = bounds(arr)
    return float(max(maxx - minx, maxy - miny))


def center_layout(layout):
    arr = np.asarray(layout, dtype=float).copy()
    if arr.ndim != 2 or len(arr) == 0:
        return arr
    minx, maxx, miny, maxy = bounds(arr)
    arr[:, 0] -= 0.5 * (minx + maxx)
    arr[:, 1] -= 0.5 * (miny + maxy)
    return arr


def wrap_angles(layout):
    arr = np.asarray(layout, dtype=float).copy()
    if len(arr):
        arr[:, 2] = (arr[:, 2] + np.pi / 4.0) % (np.pi / 2.0) - np.pi / 4.0
    return arr


def rotate_layout(layout, angle):
    arr = np.asarray(layout, dtype=float).copy()
    if len(arr) and abs(angle) > 1e-15:
        c = math.cos(angle)
        s = math.sin(angle)
        x = arr[:, 0].copy()
        y = arr[:, 1].copy()
        arr[:, 0] = c * x - s * y
        arr[:, 1] = s * x + c * y
        arr[:, 2] += angle
    return wrap_angles(center_layout(arr))


def rotated_side(arr, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    xr = c * arr[:, 0] - s * arr[:, 1]
    yr = s * arr[:, 0] + c * arr[:, 1]
    th = arr[:, 2] + angle
    h = 0.5 * (np.abs(np.cos(th)) + np.abs(np.sin(th)))
    return float(max(
        np.max(xr + h) - np.min(xr - h),
        np.max(yr + h) - np.min(yr - h),
    ))


def best_global_rotation(layout, coarse=96, fine=24):
    arr = center_layout(np.asarray(layout, dtype=float))
    if len(arr) <= 1:
        return arr
    cnum = max(12, int(coarse))
    angles = np.linspace(0.0, math.pi / 2.0, cnum, endpoint=False)
    sides = np.array([rotated_side(arr, float(a)) for a in angles])
    order = np.argsort(sides)
    minima = []
    for idx in range(cnum):
        if sides[idx] <= sides[(idx - 1) % cnum] + 1e-12 and sides[idx] <= sides[(idx + 1) % cnum] + 1e-12:
            minima.append(idx)
    minima = sorted(minima or [int(order[0])], key=lambda i: sides[i])
    span = math.pi / (2.0 * cnum)
    best_angle = float(angles[int(order[0])])
    best_side = float(sides[int(order[0])])
    for idx in minima[:min(len(minima), 8 if cnum >= 64 else 3)]:
        a0 = float(angles[idx])
        try:
            res = minimize_scalar(
                lambda a: rotated_side(arr, float(a)),
                bounds=(a0 - span, a0 + span),
                method="bounded",
                options={"xatol": 1e-13, "maxiter": 48},
            )
            a_ref, s_ref = float(res.x), float(res.fun)
        except Exception:
            a_ref, s_ref = a0, float(sides[idx])
        for a_test, s_test in ((a_ref, s_ref), (a0, float(sides[idx]))):
            if s_test < best_side - 1e-13:
                best_side, best_angle = s_test, a_test
    for a in np.linspace(best_angle - span, best_angle + span, max(4, int(fine)), endpoint=True):
        s = rotated_side(arr, float(a))
        if s < best_side - 1e-13:
            best_side, best_angle = s, float(a)
    return rotate_layout(arr, best_angle)


def grid_layout(n):
    if n <= 0:
        return np.zeros((0, 3), dtype=float)
    w = math.isqrt(n - 1) + 1
    arr = np.array([[i % w + 0.5, i // w + 0.5, 0.0] for i in range(n)], dtype=float)
    return center_layout(arr)


def neighbor_pairs(layout, radius=OPT_RADIUS, max_pairs=40000):
    arr = np.asarray(layout, dtype=float)
    n = len(arr)
    if n <= 1:
        return np.array([], dtype=int), np.array([], dtype=int)
    if n <= 24:
        return np.triu_indices(n, 1)
    try:
        tree = cKDTree(np.ascontiguousarray(arr[:, :2]))
        pairs = tree.query_pairs(r=float(radius), output_type="ndarray")
    except Exception:
        return np.array([], dtype=int), np.array([], dtype=int)
    if pairs is None or len(pairs) == 0:
        return np.array([], dtype=int), np.array([], dtype=int)
    pairs = np.asarray(pairs, dtype=int).reshape(-1, 2)
    if len(pairs) > max_pairs:
        d = arr[pairs[:, 0], :2] - arr[pairs[:, 1], :2]
        dd = d[:, 0] * d[:, 0] + d[:, 1] * d[:, 1]
        keep = np.argsort(dd)[:max_pairs]
        pairs = pairs[keep]
    return np.ascontiguousarray(pairs[:, 0]), np.ascontiguousarray(pairs[:, 1])


def _pair_terms(x, y, c, s, first, second):
    ci, si, cj, sj = c[first], s[first], c[second], s[second]
    ui = np.stack((ci, si), axis=1)
    vi = np.stack((-si, ci), axis=1)
    uj = np.stack((cj, sj), axis=1)
    vj = np.stack((-sj, cj), axis=1)
    axes = np.stack((ui, vi, uj, vj), axis=1)
    dui = np.sum(axes * ui[:, None, :], axis=2)
    dvi = np.sum(axes * vi[:, None, :], axis=2)
    duj = np.sum(axes * uj[:, None, :], axis=2)
    dvj = np.sum(axes * vj[:, None, :], axis=2)
    hi = 0.5 * (np.abs(dui) + np.abs(dvi))
    hj = 0.5 * (np.abs(duj) + np.abs(dvj))
    delta = np.stack((x[first] - x[second], y[first] - y[second]), axis=1)
    dot_d = np.sum(axes * delta[:, None, :], axis=2)
    sep = hi + hj - np.abs(dot_d)
    return axes, delta, dui, dvi, duj, dvj, hi, hj, dot_d, sep


def max_overlap(layout, first, second):
    arr = np.asarray(layout, dtype=float)
    if len(arr) <= 1 or len(first) == 0:
        return -1.0
    th = arr[:, 2]
    sep = _pair_terms(arr[:, 0], arr[:, 1], np.cos(th), np.sin(th), first, second)[-1]
    return float(np.max(np.min(sep, axis=1)))


def is_overlap_free(layout, radius=CHECK_RADIUS, tol=1e-7):
    arr = np.asarray(layout, dtype=float)
    n = len(arr)
    if n <= 1:
        return True
    f, s = neighbor_pairs(arr, radius=radius, max_pairs=90000)
    if len(f) == 0:
        return True
    return bool(max_overlap(arr, f, s) <= tol)


def perturb_layout(layout, rng, pos_sigma, ang_sigma, rotate_prob=0.0):
    arr = center_layout(np.asarray(layout, dtype=float)).copy()
    n = len(arr)
    arr[:, :2] += rng.normal(0.0, pos_sigma, (n, 2))
    arr[:, 2] += rng.normal(0.0, ang_sigma, n)
    if rotate_prob > 0.0 and n:
        mask = rng.random(n) < rotate_prob
        if np.any(mask):
            arr[mask, 2] += rng.choice([-np.pi / 2.0, -np.pi / 4.0, np.pi / 4.0, np.pi / 2.0],
                                       size=int(np.sum(mask)))
    return wrap_angles(center_layout(arr))


def pbd_repair(layout, target_side, n, first, second, rng=None,
               iters=120, damp=0.72, shake=0.003):
    if n <= 1 or target_side <= 1e-9:
        return None
    arr = center_layout(np.asarray(layout, dtype=float)).copy()
    if len(arr) != n or not np.all(np.isfinite(arr)):
        return None
    half = 0.5 * float(target_side)
    if half <= 0.0:
        return None
    tol = 1e-9
    prev_max = float("inf")
    stuck = 0
    for _ in range(iters):
        th = arr[:, 2]
        c, s = np.cos(th), np.sin(th)
        h = 0.5 * (np.abs(c) + np.abs(s))
        lo, hi = -half + h, half - h
        if np.any(lo > hi + 1e-12):
            return None
        arr[:, 0] = np.clip(arr[:, 0], lo, hi)
        arr[:, 1] = np.clip(arr[:, 1], lo, hi)
        if len(first) == 0:
            break
        axes, delta, _, _, _, _, _, _, dot_d, sep = _pair_terms(arr[:, 0], arr[:, 1], c, s, first, second)
        min_sep = np.min(sep, axis=1)
        cur_max = float(np.max(min_sep))
        if cur_max <= tol:
            break
        if cur_max > prev_max - 1e-7:
            stuck += 1
        else:
            stuck, prev_max = 0, cur_max
        if stuck > 14 and rng is not None:
            arr[:, :2] += rng.normal(0.0, shake, (n, 2))
            arr[:, 2] += rng.normal(0.0, 0.018, n)
            stuck, prev_max = 0, float("inf")
            continue
        active = min_sep > tol
        if not np.any(active):
            break
        idx = np.where(active)[0]
        k = np.argmin(sep[idx], axis=1)
        a = axes[idx, k]
        sign_s = np.where(np.sum(a * delta[idx], axis=1) >= 0.0, 1.0, -1.0)
        push = (0.5 * damp * min_sep[idx])[:, None] * sign_s[:, None] * a
        np.add.at(arr[:, 0], first[idx], push[:, 0])
        np.add.at(arr[:, 1], first[idx], push[:, 1])
        np.add.at(arr[:, 0], second[idx], -push[:, 0])
        np.add.at(arr[:, 1], second[idx], -push[:, 1])
    th = arr[:, 2]
    h = 0.5 * (np.abs(np.cos(th)) + np.abs(np.sin(th)))
    lo, hi = -half + h, half - h
    if np.any(lo > hi + 1e-12):
        return None
    arr[:, 0] = np.clip(arr[:, 0], lo, hi)
    arr[:, 1] = np.clip(arr[:, 1], lo, hi)
    if max_overlap(arr, first, second) <= 2e-8:
        arr = center_layout(arr)
        side = layout_side(arr)
        if side <= target_side + 1e-6:
            return arr, side
    return None


def _add_overlap_grad(gx, gy, gth, x, y, cos, sin, first, second, penalty, energy):
    axes, delta, dui, dvi, duj, dvj, _, _, dot_d, sep = _pair_terms(x, y, cos, sin, first, second)
    e = np.maximum(np.min(sep, axis=1), 0.0)
    energy += penalty * float(np.sum(e ** 2))
    active = e > 0.0
    if not np.any(active):
        return energy
    idx = np.where(active)[0]
    k = np.argmin(sep[idx], axis=1)
    coeff = 2.0 * penalty * e[idx]
    a = axes[idx, k]
    d = delta[idx]
    sg = np.sign(dot_d[idx, k])
    ax, ay = a[:, 0], a[:, 1]
    np.add.at(gx, first[idx], coeff * (-sg * ax))
    np.add.at(gy, first[idx], coeff * (-sg * ay))
    np.add.at(gx, second[idx], coeff * (sg * ax))
    np.add.at(gy, second[idx], coeff * (sg * ay))
    du, dv = dui[idx, k], dvi[idx, k]
    duj_s, dvj_s = duj[idx, k], dvj[idx, k]
    owner_i = k <= 1
    if np.any(owner_i):
        ii, kk, cf = idx[owner_i], k[owner_i], coeff[owner_i]
        ss, dd = sg[owner_i], d[owner_i]
        duj_i, dvj_i = duj_s[owner_i], dvj_s[owner_i]
        c_i, s_i = cos[first[ii]], sin[first[ii]]
        c_j, s_j = cos[second[ii]], sin[second[ii]]
        apx = np.where(kk == 0, -s_i, -c_i)
        apy = np.where(kk == 0, c_i, -s_i)
        h_a = 0.5 * (np.sign(duj_i) * (apx * c_j + apy * s_j) +
                     np.sign(dvj_i) * (apx * (-s_j) + apy * c_j))
        ap_d = apx * dd[:, 0] + apy * dd[:, 1]
        np.add.at(gth, first[ii], cf * (h_a - ss * ap_d))
        np.add.at(gth, second[ii], cf * 0.5 * (np.sign(duj_i) * dvj_i - np.sign(dvj_i) * duj_i))
    owner_j = ~owner_i
    if np.any(owner_j):
        jj, kk, cf = idx[owner_j], k[owner_j], coeff[owner_j]
        ss, dd = sg[owner_j], d[owner_j]
        du_i, dv_i = du[owner_j], dv[owner_j]
        c_j, s_j = cos[second[jj]], sin[second[jj]]
        c_i, s_i = cos[first[jj]], sin[first[jj]]
        apx = np.where(kk == 2, -s_j, -c_j)
        apy = np.where(kk == 2, c_j, -s_j)
        h_i = 0.5 * (np.sign(du_i) * (apx * c_i + apy * s_i) +
                     np.sign(dv_i) * (apx * (-s_i) + apy * c_i))
        ap_d = apx * dd[:, 0] + apy * dd[:, 1]
        np.add.at(gth, second[jj], cf * (h_i - ss * ap_d))
        np.add.at(gth, first[jj], cf * 0.5 * (np.sign(du_i) * dv_i - np.sign(dv_i) * du_i))
    return energy


def energy_grad(flat, n, first, second, half_side):
    sq = flat.reshape(n, 3)
    x, y, th = sq[:, 0], sq[:, 1], sq[:, 2]
    c, s = np.cos(th), np.sin(th)
    h = 0.5 * (np.abs(c) + np.abs(s))
    h_prime = 0.5 * (-np.sign(c) * s + np.sign(s) * c)
    bx, by = np.abs(x) + h - half_side, np.abs(y) + h - half_side
    bx_pos, by_pos = np.maximum(bx, 0.0), np.maximum(by, 0.0)
    energy = float(np.sum(bx_pos ** 2) + np.sum(by_pos ** 2))
    gx = 2.0 * bx_pos * np.sign(x)
    gy = 2.0 * by_pos * np.sign(y)
    gth = 2.0 * (bx_pos + by_pos) * h_prime
    if n > 1 and len(first):
        energy = _add_overlap_grad(gx, gy, gth, x, y, c, s, first, second, 1.0, energy)
    grad = np.empty(3 * n)
    grad[0::3], grad[1::3], grad[2::3] = gx, gy, gth
    return energy, grad


def relax_energy(layout, side, n, first, second, maxiter=90):
    layout = center_layout(np.asarray(layout, dtype=float))
    half = side / 2.0
    x0 = layout.ravel().copy()
    x0[0::3] = np.clip(x0[0::3], -half, half)
    x0[1::3] = np.clip(x0[1::3], -half, half)
    x0[2::3] = np.clip(x0[2::3], -np.pi / 4.0, np.pi / 4.0)
    try:
        res = minimize(
            energy_grad, x0, args=(n, first, second, half), method="L-BFGS-B", jac=True,
            bounds=[(-half, half), (-half, half), (-np.pi / 4.0, np.pi / 4.0)] * n,
            options={"maxiter": maxiter, "ftol": 1e-15, "gtol": 1e-10, "maxls": 35, "maxcor": 20},
        )
        return center_layout(np.asarray(res.x, dtype=float).reshape(n, 3)), res
    except Exception:
        return layout, None


def direct_energy_grad(flat, n, first, second, penalty):
    sq = flat.reshape(n, 3)
    x, y, th = sq[:, 0], sq[:, 1], sq[:, 2]
    c, s = np.cos(th), np.sin(th)
    h = 0.5 * (np.abs(c) + np.abs(s))
    h_prime = 0.5 * (-np.sign(c) * s + np.sign(s) * c)
    xmin, xmax, ymin, ymax = x - h, x + h, y - h, y + h
    ixmin, ixmax = int(np.argmin(xmin)), int(np.argmax(xmax))
    iymin, iymax = int(np.argmin(ymin)), int(np.argmax(ymax))
    wx, wy = float(xmax[ixmax] - xmin[ixmin]), float(ymax[iymax] - ymin[iymin])
    gx, gy, gth = np.zeros(n), np.zeros(n), np.zeros(n)
    if wx >= wy:
        side, coeff = wx, 2.0 * wx
        gx[ixmax] += coeff
        gx[ixmin] -= coeff
        gth[ixmax] += coeff * h_prime[ixmax]
        gth[ixmin] += coeff * h_prime[ixmin]
    else:
        side, coeff = wy, 2.0 * wy
        gy[iymax] += coeff
        gy[iymin] -= coeff
        gth[iymax] += coeff * h_prime[iymax]
        gth[iymin] += coeff * h_prime[iymin]
    energy = side * side
    if n > 1 and len(first):
        energy = _add_overlap_grad(gx, gy, gth, x, y, c, s, first, second, penalty, energy)
    grad = np.empty(3 * n)
    grad[0::3], grad[1::3], grad[2::3] = gx, gy, gth
    return energy, grad


def direct_relax(layout, n, first, second, penalty=80.0, maxiter=140):
    arr = center_layout(np.asarray(layout, dtype=float))
    if n <= 0:
        return arr, 0.0, -1.0
    if n <= 1:
        return arr, layout_side(arr), -1.0
    limit = max(5.0, math.sqrt(n) * 1.8 + 2.0)
    x0 = arr.ravel().copy()
    x0[0::3] = np.clip(x0[0::3], -limit, limit)
    x0[1::3] = np.clip(x0[1::3], -limit, limit)
    x0[2::3] = np.clip(x0[2::3], -np.pi / 4.0, np.pi / 4.0)
    try:
        res = minimize(
            direct_energy_grad, x0, args=(n, first, second, float(penalty)),
            method="L-BFGS-B", jac=True,
            bounds=[(-limit, limit), (-limit, limit), (-np.pi / 4.0, np.pi / 4.0)] * n,
            options={"maxiter": int(maxiter), "ftol": 1e-15, "gtol": 1e-10, "maxls": 40, "maxcor": 20},
        )
        out = wrap_angles(center_layout(np.asarray(res.x, dtype=float).reshape(n, 3)))
        ov = max_overlap(out, first, second) if (n > 1 and len(first)) else -1.0
        return out, layout_side(out), float(ov)
    except Exception:
        return arr, layout_side(arr), 1.0


def get_cached(m, layouts):
    key = str(m)
    for pool in (layouts, EXTRA_BLOCKS):
        if key in pool and isinstance(pool[key], (list, np.ndarray)) and len(pool[key]) == m:
            try:
                arr = np.asarray(pool[key], dtype=float)
            except Exception:
                continue
            if arr.ndim == 2 and arr.shape[1] == 3 and np.all(np.isfinite(arr)):
                return center_layout(wrap_angles(arr))
    return None


def compose_corner(n, b, block_layout, corner=0, mirror_x=False, mirror_y=False):
    k = math.isqrt(n)
    r = n - k * k
    if r <= 0:
        return None
    m = b * b + r
    blk = center_layout(np.asarray(block_layout, dtype=float)).copy()
    if b < 1 or b >= k or len(blk) != m or not np.all(np.isfinite(blk)):
        return None
    if mirror_x:
        blk[:, 0] *= -1.0
        blk[:, 2] *= -1.0
    if mirror_y:
        blk[:, 1] *= -1.0
        blk[:, 2] *= -1.0
    try:
        blk = best_global_rotation(wrap_angles(center_layout(blk)), coarse=40, fine=12)
    except Exception:
        blk = wrap_angles(center_layout(blk))
    minx, maxx, miny, maxy = bounds(blk)
    x0 = 0 if corner in (0, 2) else k - b
    y0 = 0 if corner in (0, 1) else k - b
    if x0 == 0:
        blk[:, 0] += b - maxx
    else:
        blk[:, 0] += (k - b) - minx
    if y0 == 0:
        blk[:, 1] += b - maxy
    else:
        blk[:, 1] += (k - b) - miny
    rest = []
    for row in range(k):
        for col in range(k):
            if x0 <= col < x0 + b and y0 <= row < y0 + b:
                continue
            rest.append([col + 0.5, row + 0.5, 0.0])
    if rest:
        arr = np.vstack([blk, np.asarray(rest, dtype=float)])
    else:
        arr = blk
    return wrap_angles(center_layout(arr))


def build_composition_seeds(n, layouts, rng, deadline, budget=56):
    seeds = []
    k = math.isqrt(n)
    r = n - k * k
    if r <= 0 or k < 3 or n > 1800:
        return seeds
    b_candidates = []
    for b in range(k - 1, max(1, k - 7), -1):
        b_candidates.append(b)
    for b in (2, 3, 4, 5, 6, 7, 8):
        if b < k:
            b_candidates.append(b)
    seen_b = set()
    for b in b_candidates:
        if b in seen_b or b < 2 or b >= k:
            continue
        seen_b.add(b)
        m = b * b + r
        if m <= 0 or m >= n:
            continue
        blk = get_cached(m, layouts)
        if blk is None or len(blk) != m:
            continue
        for mx in (False, True):
            for my in (False, True):
                for corner in range(4):
                    if budget <= 0:
                        return seeds
                    if time_left() < 2.0 or time.time() > deadline:
                        return seeds
                    cand = compose_corner(n, b, blk, corner=corner, mirror_x=mx, mirror_y=my)
                    if cand is not None and len(cand) == n and np.all(np.isfinite(cand)):
                        seeds.append(cand)
                        budget -= 1
    base = get_cached(n - 1, layouts) if n > 1 else None
    if base is not None and len(base) == n - 1 and budget > 0:
        arr = center_layout(base)
        minx, maxx, miny, maxy = bounds(arr)
        for kk in range(8):
            if time_left() < 2.0:
                break
            if kk < 4:
                x = rng.uniform(minx - 0.3, maxx + 0.3)
                y = rng.uniform(miny - 0.3, maxy + 0.3)
            else:
                side_id, u, off = kk % 4, rng.uniform(miny, maxy), 0.55
                if side_id == 0:
                    x, y = maxx + off, u
                elif side_id == 1:
                    x, y = minx - off, u
                elif side_id == 2:
                    x, y = rng.uniform(minx, maxx), maxy + off
                else:
                    x, y = rng.uniform(minx, maxx), miny - off
            theta = float(rng.choice([0.0, np.pi / 4.0, -np.pi / 4.0])) + rng.normal(0.0, 0.02)
            cand = np.vstack([arr, [x, y, theta]])
            seeds.append(wrap_angles(center_layout(cand)))
    return seeds


def improve_local(n, layout, side, rng, deadline):
    if n <= 1:
        return center_layout(np.asarray(layout, dtype=float)), float(side)
    best_layout = center_layout(np.asarray(layout, dtype=float)).copy()
    best_side = float(side)

    def attempt(cand):
        nonlocal best_layout, best_side
        try:
            cand = center_layout(np.asarray(cand, dtype=float))
        except Exception:
            return False
        if len(cand) != n or not np.all(np.isfinite(cand)):
            return False
        if layout_side(cand) >= best_side - 1e-12:
            return False
        if not is_overlap_free(cand):
            return False
        try:
            er = evaluate_layout(n, cand.tolist())
        except Exception:
            return False
        if not er.valid:
            return False
        es = float(er.side_length)
        if es >= best_side - 1e-12:
            return False
        best_layout = cand
        best_side = es
        return True

    first, second = neighbor_pairs(best_layout, radius=OPT_RADIUS)

    try:
        rot = best_global_rotation(best_layout, coarse=96, fine=30)
        if attempt(rot):
            first, second = neighbor_pairs(best_layout, radius=OPT_RADIUS)
    except Exception:
        pass

    delta = 0.003
    fails = 0
    it = 0
    while time.time() < deadline and time_left() > 0.5 and it < 300:
        it += 1
        target = best_side * (1.0 - delta)
        if target <= 1e-9:
            break
        improved = False
        move = int(rng.integers(0, 100))
        try:
            if move < 30:
                cand = pbd_repair(best_layout, target, n, first, second, rng, iters=150)
                if cand is not None:
                    improved = attempt(cand[0])
            elif move < 55:
                out, s, ov = direct_relax(best_layout, n, first, second, penalty=110.0, maxiter=110)
                if ov <= 1e-8:
                    improved = attempt(out)
                    if not improved and s < best_side - 1e-9 and time_left() > 0.9:
                        cand = pbd_repair(out, min(s, target), n, first, second, rng, iters=120)
                        if cand is not None:
                            improved = attempt(cand[0])
            elif move < 78:
                sigma = 0.003 + 0.012 / math.sqrt(n)
                start = perturb_layout(best_layout, rng, sigma * (1.0 + rng.random()),
                                       0.02 + 0.05 * rng.random(), rotate_prob=0.04)
                rel, _ = relax_energy(start, target, n, first, second, maxiter=110)
                cand = pbd_repair(rel, target, n, first, second, rng, iters=130)
                if cand is not None:
                    improved = attempt(cand[0])
            elif move < 92:
                rel, _ = relax_energy(best_layout, target, n, first, second, maxiter=120)
                cand = pbd_repair(rel, target, n, first, second, rng, iters=130)
                if cand is not None:
                    improved = attempt(cand[0])
            else:
                ang = float(rng.normal(0.0, 0.03))
                start = rotate_layout(best_layout, ang)
                rel, _ = relax_energy(start, target, n, first, second, maxiter=100)
                cand = pbd_repair(rel, target, n, first, second, rng, iters=120)
                if cand is not None:
                    improved = attempt(cand[0])
        except Exception:
            improved = False
        if improved:
            fails = 0
            delta = min(0.05, delta * 1.5)
            first, second = neighbor_pairs(best_layout, radius=OPT_RADIUS)
        else:
            fails += 1
            delta *= 0.72
            if delta < 2e-6:
                delta = 0.003
            if fails > 45:
                break
    return best_layout, best_side


def main():
    puzzles = json.loads((ROOT / "puzzles.json").read_text())
    requested = int(sys.argv[1]) if len(sys.argv) > 1 else None
    cached = {}
    if INCUMBENTS.exists():
        try:
            loaded = json.loads(INCUMBENTS.read_text())
            if isinstance(loaded, dict):
                cached = loaded
        except Exception:
            cached = {}
    if BLOCKS_FILE.exists():
        try:
            extra = json.loads(BLOCKS_FILE.read_text())
            if isinstance(extra, dict):
                for kk, val in extra.items():
                    if isinstance(val, list):
                        EXTRA_BLOCKS[kk] = val
        except Exception:
            pass

    layouts = {kk: val for kk, val in cached.items() if isinstance(val, list)}
    rng = np.random.default_rng()

    def write_output(key, layout):
        arr = center_layout(wrap_angles(np.asarray(layout, dtype=float)))
        merged = dict(cached)
        merged[key] = arr.tolist()
        try:
            INCUMBENTS.write_text(json.dumps(merged))
        except Exception:
            pass
        out = {}
        try:
            if RESULT.exists():
                prev = json.loads(RESULT.read_text())
                if isinstance(prev, dict):
                    out = prev
        except Exception:
            out = {}
        out[key] = merged[key]
        try:
            RESULT.write_text(json.dumps(out))
        except Exception:
            pass

    if requested is None:
        out = {}
        for n in puzzles:
            key = str(n)
            layout = layouts.get(key)
            if layout is None:
                layout = grid_layout(n).tolist()
            else:
                try:
                    er = evaluate_layout(n, layout)
                    if not er.valid:
                        layout = grid_layout(n).tolist()
                except Exception:
                    layout = grid_layout(n).tolist()
            out[key] = center_layout(np.asarray(layout, dtype=float)).tolist()
        merged = dict(cached)
        merged.update(out)
        try:
            INCUMBENTS.write_text(json.dumps(merged))
        except Exception:
            pass
        try:
            RESULT.write_text(json.dumps(out))
        except Exception:
            pass
        return

    n = requested
    key = str(n)

    best_layout = None
    best_side = float("inf")
    best_result = None
    layout = layouts.get(key)
    if layout is not None:
        try:
            arr = center_layout(wrap_angles(np.asarray(layout, dtype=float)))
            if arr.ndim == 2 and arr.shape[1] == 3 and len(arr) == n and np.all(np.isfinite(arr)):
                er = evaluate_layout(n, arr.tolist())
                if er.valid:
                    best_layout, best_side, best_result = arr, float(er.side_length), er
        except Exception:
            best_layout = None
    if best_layout is None:
        g = center_layout(grid_layout(n))
        try:
            er = evaluate_layout(n, g.tolist())
            if er.valid:
                best_layout, best_side, best_result = g, float(er.side_length), er
            else:
                best_layout, best_side = g, layout_side(g)
        except Exception:
            best_layout, best_side = g, layout_side(g)

    if n <= 1:
        write_output(key, best_layout if len(best_layout) == n else grid_layout(n))
        return

    root = math.isqrt(n)
    if root * root == n:
        target = float(root)
        if best_side > target + 1e-9:
            g = center_layout(grid_layout(n))
            try:
                er = evaluate_layout(n, g.tolist())
                if er.valid and float(er.side_length) < best_side - 1e-12:
                    best_layout, best_side, best_result = g, float(er.side_length), er
            except Exception:
                pass
        write_output(key, best_layout)
        return

    deadline = START_TIME + TIME_LIMIT - 0.7

    def certify(cand):
        try:
            arr = center_layout(wrap_angles(np.asarray(cand, dtype=float)))
        except Exception:
            return None
        if arr.ndim != 2 or arr.shape[1] != 3 or len(arr) != n or not np.all(np.isfinite(arr)):
            return None
        if not is_overlap_free(arr):
            return None
        try:
            er = evaluate_layout(n, arr.tolist())
        except Exception:
            return None
        if not er.valid:
            return None
        return arr, float(er.side_length), er

    # 1. Global-rotation polish of the incumbent.
    try:
        if time_left() > 1.2:
            rot = best_global_rotation(best_layout, coarse=96, fine=30)
            if layout_side(rot) < best_side - 1e-12:
                res = certify(rot)
                if res is not None and res[1] < best_side - 1e-12:
                    best_layout, best_side, best_result = res
    except Exception:
        pass

    # 2. Composition seeds (corner blocks + insertion of a single square).
    seeds = []
    if n >= 6 and time_left() > 2.6:
        try:
            seeds = build_composition_seeds(n, layouts, rng, deadline)
        except Exception:
            seeds = []
    clean = []
    for s in seeds:
        try:
            arr = np.asarray(s, dtype=float)
        except Exception:
            continue
        if arr.ndim == 2 and arr.shape[1] == 3 and len(arr) == n and np.all(np.isfinite(arr)):
            clean.append(center_layout(arr))
    clean.sort(key=layout_side)
    seeds = clean[:36]

    # 3. Cheap acceptance of the most promising seeds, plus one local polish pass.
    for idx, seed in enumerate(seeds[:48]):
        if time_left() < 1.1:
            break
        if layout_side(seed) >= best_side - 1e-9:
            continue
        if idx < 4:
            try:
                rot = best_global_rotation(seed, coarse=56, fine=16)
                if layout_side(rot) < layout_side(seed):
                    seed = rot
            except Exception:
                pass
        res = certify(seed)
        if res is not None and res[1] < best_side - 1e-12:
            best_layout, best_side, best_result = res

    # 4. Choose a starting point (randomised between incumbent and best seed).
    start_layout, start_side = best_layout, best_side
    if seeds and time_left() > 2.2:
        seed = seeds[0]
        s_seed = layout_side(seed)
        pick = False
        if s_seed < best_side * 0.998:
            pick = True
        elif s_seed < best_side * 1.05 and rng.random() < 0.35:
            pick = True
        if pick:
            res = certify(seed)
            if res is not None:
                if res[1] < best_side - 1e-12:
                    best_layout, best_side, best_result = res
                    start_layout, start_side = best_layout, best_side
                else:
                    start_layout, start_side = res[0], res[1]

    # 5. Main shrink / shake / relax search.
    if n <= LOCAL_N_MAX and time_left() > 1.0:
        if time_left() > 1.4:
            try:
                sl, ss = improve_local(n, start_layout, start_side, rng, deadline)
                if ss < best_side - 1e-12:
                    res = certify(sl)
                    if res is not None and res[1] < best_side - 1e-12:
                        best_layout, best_side, best_result = res
            except Exception:
                pass
    elif n > LOCAL_N_MAX and time_left() > 2.4:
        # Light squeeze for large n using neighbourhood-restricted contacts.
        try:
            f, s2 = neighbor_pairs(best_layout, radius=OPT_RADIUS, max_pairs=40000)
            for _ in range(4):
                if time_left() < 1.8 or time.time() > deadline:
                    break
                target = best_side * 0.997
                cand = pbd_repair(best_layout, target, n, f, s2, rng, iters=50)
                if cand is None:
                    break
                res = certify(cand[0])
                if res is None or res[1] >= best_side - 1e-12:
                    break
                best_layout, best_side, best_result = res
                f, s2 = neighbor_pairs(best_layout, radius=OPT_RADIUS, max_pairs=40000)
        except Exception:
            pass

    # 6. Final certification, global rotation, write.
    final = center_layout(np.asarray(best_layout, dtype=float))
    try:
        if time_left() > 0.42:
            rot = best_global_rotation(final, coarse=150, fine=52)
            if layout_side(rot) < best_side - 1e-12:
                er = evaluate_layout(n, rot.tolist())
                if er.valid and float(er.side_length) < best_side - 1e-12:
                    final = center_layout(rot)
                    best_side = float(er.side_length)
                    best_result = er
    except Exception:
        pass

    ok = False
    try:
        er = evaluate_layout(n, final.tolist())
        ok = bool(getattr(er, "valid", False))
    except Exception:
        ok = False
    if not ok:
        if best_result is not None and getattr(best_result, "valid", False):
            final = center_layout(np.asarray(best_layout, dtype=float))
        else:
            final = center_layout(grid_layout(n))
    write_output(key, final)


if __name__ == "__main__":
    main()
