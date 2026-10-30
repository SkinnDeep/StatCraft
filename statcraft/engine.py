"""Original, limited numeric primitives for StatCraft.

These implement selected ordinary decoded contracts; full compatibility is unverified.
Only normalize_numeric has reference-runtime evidence (the observed public
SetData/GetData path). Distribution/kernel checks are analytical checks of static
interpretations. Alternate Weibull parameterization, mutable class flags, native
error objects and fuzzy negative-base rounding are intentionally not emulated.
No installed application binary, resource, automation object or code is loaded.
"""

import math
import numbers
import sys
from typing import Iterable, List, NamedTuple, Optional, Sequence


MISSING_SENTINEL = 1.23456e30
ADAPTER_LOG_BOUND = 709.7827128933839
MIN_NORMAL = sys.float_info.min

EVIDENCE_IDS = {
    "weibull_initializer": "ev_b4ec01c4d7c5df5ef231dccc369af47464289228f12b10a682e56000bd77c6bf",
    "weibull_pdf": "ev_c7488b5363d3923176fb313a5e2b9ee702d591f2422d64aa4ba8e80731ef7628",
    "weibull_mean": "ev_e1ae605693b8da47515fff1a5c44ff15ac0c57427f8ae0f82ab4d26d5e5ac16c",
    "weibull_cdf": "ev_d4a3177f23b347ebb7e8b0fa578020bdc163cef9f3a6f17464dde027e5b84089",
    "power_adapter": "ev_1a803e63c0531defc1fe80ca6da4b4a4c6fb7dbb0a59ee4d367761ed1d13f92f",
    "exp_adapter": "ev_f5764b7954a139bb919e3ca09b9ebd27315b344f3b30a14cb36b8403508834da",
    "exponential_cdf": "ev_0b337cb70c89e53efc1a2f1f7b5e8bd7bf4c60e01c988c0bea0335506c6cf2ae",
    "givens": "ev_7167ae8179c290c60a78c80b5881e5f6cbc007017914f2d7123d310e703f36a1",
    "triangular_solve": "ev_56ed0c9049428e0f66ccc6a65f8a6a5c4aefa80339da4e9fdce9f0d526e42856",
}


def normalize_numeric(value: Optional[float]) -> Optional[float]:
    """Return a finite float, canonical +0.0, or None for numeric missing.

    None, NaN, either infinity and the exact observed sentinel become None.
    Text/bool/complex inputs are rejected rather than silently coerced. None is
    StatCraft's internal representation; the observed external representation
    was the sentinel. Huge integers outside binary64 conversion are rejected.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError("A real numeric scalar or None is required.")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("Numeric input exceeds binary64 conversion range.") from exc
    if not math.isfinite(result) or result == MISSING_SENTINEL:
        return None
    return 0.0 if result == 0.0 else result


def normalize_numbers(values: Iterable[Optional[float]]) -> List[Optional[float]]:
    return [normalize_numeric(value) for value in values]


def _finite(value: float, label: str) -> float:
    result = normalize_numeric(value)
    if result is None:
        raise ValueError(label + " must be finite and nonmissing.")
    return result


def exp_adapter(value: float) -> float:
    """Decoded finite-input clamp, with an explicit StatCraft overflow policy.

    Below -ADAPTER_LOG_BOUND return zero. Above the positive bound raise
    OverflowError: the original flag-dependent error route is unresolved.
    Nonfinite/missing inputs raise ValueError; native error objects are not used.
    """
    value = _finite(value, "Exponential argument")
    if value < -ADAPTER_LOG_BOUND:
        return 0.0
    if value > ADAPTER_LOG_BOUND:
        raise OverflowError("Exponential exceeds the decoded adapter bound.")
    return math.exp(value)


def power_adapter(base: float, exponent: float) -> float:
    """Decoded zero/positive-base contract and exact-integer negative powers.

    Zero to a negative power produces NaN, the decoded invalid-operation result.
    For nonzero bases, magnitude is clamped using exponent*log(abs(base)).
    Overflow raises; native flag-dependent overflow policy is unresolved.
    Negative bases require an *exact* integer exponent. The native fuzzy-rounding
    helper and extreme integer-conversion policy are not reproduced here.
    """
    base = _finite(base, "Power base")
    exponent = _finite(exponent, "Power exponent")
    if base == 0.0:
        if exponent > 0.0:
            return 0.0
        return 1.0 if exponent == 0.0 else math.nan
    if base < 0.0 and not exponent.is_integer():
        return math.nan
    log_magnitude = exponent * math.log(abs(base))
    if log_magnitude < -ADAPTER_LOG_BOUND:
        return 0.0
    if log_magnitude > ADAPTER_LOG_BOUND:
        raise OverflowError("Power exceeds the decoded adapter bound.")
    return math.pow(base, exponent)


def _weibull_parameters(shape: float, scale: float, location: float):
    shape = _finite(shape, "Weibull shape")
    scale = _finite(scale, "Weibull scale")
    location = _finite(location, "Weibull location")
    if shape <= 0.0 or scale <= 0.0:
        raise ValueError("Weibull shape and scale must be positive.")
    return shape, scale, location


def _standardized(value: float, scale: float, location: float) -> float:
    z = (value - location) / scale
    if not math.isfinite(z):
        raise OverflowError("Standardized Weibull argument exceeds binary64 range.")
    return z


def weibull_pdf(value: Optional[float], shape: float, scale: float,
                location: float = 0.0) -> Optional[float]:
    """Ordinary Weibull PDF; zero at/below location for *every* positive shape.

    Missing numeric observations return None. Parameters are always validated.
    The location boundary follows the decoded kernel, not the usual limiting
    density chosen for shape <= 1. Intermediate overflow raises explicitly.
    """
    shape, scale, location = _weibull_parameters(shape, scale, location)
    value = normalize_numeric(value)
    if value is None:
        return None
    if value <= location:
        return 0.0
    z = _standardized(value, scale, location)
    t = power_adapter(z, shape)
    density = (shape * exp_adapter(-t) * power_adapter(z, shape - 1.0)) / scale
    if not math.isfinite(density):
        raise OverflowError("Weibull density intermediate exceeds binary64 range.")
    return density


def weibull_cdf(value: Optional[float], shape: float, scale: float,
                location: float = 0.0, upper_tail: bool = False) -> Optional[float]:
    """Ordinary lower CDF or survival tail; missing observations return None.

    The small-lower-tail branch uses standard-library expm1. This is an original
    stable evaluation of the decoded algebra, not the original chi-square helper
    and not a claim of identical rounding. The exponential adapter clamp is kept.
    """
    shape, scale, location = _weibull_parameters(shape, scale, location)
    if not isinstance(upper_tail, bool):
        raise TypeError("upper_tail must be Boolean.")
    value = normalize_numeric(value)
    if value is None:
        return None
    if value <= location:
        return 1.0 if upper_tail else 0.0
    z = _standardized(value, scale, location)
    t = power_adapter(z, shape)
    upper = exp_adapter(-t)
    if upper_tail:
        return upper
    return -math.expm1(-t) if upper > 0.999 else 1.0 - upper


def weibull_mean(shape: float, scale: float, location: float = 0.0) -> float:
    """Mean of the ordinary parameterization; alternate model form excluded."""
    shape, scale, location = _weibull_parameters(shape, scale, location)
    result = location + exp_adapter(math.log(scale)) * math.gamma(1.0 + 1.0 / shape)
    if not math.isfinite(result):
        raise OverflowError("Weibull mean exceeds binary64 range.")
    return result


class GivensResult(NamedTuple):
    r: float
    c: float
    s: float
    z: float


def givens_rotation(a: float, b: float) -> GivensResult:
    """Decoded finite-input rotation, including the unusual signed-b selector.

    r/z are the decoded overwritten input references; c/s form the rotation.
    Scale <= minimum normal collapses to r=0,c=1,s=0; zero pair yields z=1.
    Nonfinite/missing inputs and overflowing scale sums are rejected because the
    original behavior for those cases has not been validated.
    Signed zero is preserved for the sign selector in this internal kernel.
    """
    # Do not use canonical-zero normalization here: raw sign bits matter.
    _finite(a, "Givens a")
    _finite(b, "Givens b")
    a, b = float(a), float(b)
    sign_source = a if b < abs(a) else b
    scale = abs(a) + abs(b)
    if not math.isfinite(scale):
        raise OverflowError("Givens scale sum exceeds binary64 range.")
    if scale > MIN_NORMAL:
        r = math.copysign(1.0, sign_source) * math.sqrt((a / scale) ** 2 + (b / scale) ** 2) * scale
        c, s = a / r, b / r
    else:
        r, c, s = 0.0, 1.0, 0.0
    z = 1.0
    if abs(b) < abs(a):
        z = s
    if abs(a) <= abs(b) and abs(c) > MIN_NORMAL:
        z = 1.0 / c
    return GivensResult(r, c, s, z)


class TriangularResult(NamedTuple):
    status: int
    solution: List[float]


def packed_triangular_solve(packed: Sequence[float], rhs: Sequence[float],
                            transpose: bool = False) -> TriangularResult:
    """Solve U*x=b or U.T*x=b using column-major packed upper storage.

    Element U[i,j] is at j*(j+1)//2+i. An exact zero diagonal returns its
    first zero-based index and the unchanged RHS; success status is -1.
    Inputs are copied, finite/nonmissing and size-validated. Empty systems are
    rejected: the decoded caller's zero-size contract has not been established.
    These validation/overflow exceptions are StatCraft safeguards, not recovered
    native error behavior. No implicit rank tolerance or regularization is added.
    """
    if not isinstance(transpose, bool):
        raise TypeError("transpose must be Boolean.")
    n = len(rhs)
    if n < 1 or len(packed) != n * (n + 1) // 2:
        raise ValueError("A nonempty RHS and exactly n*(n+1)/2 packed entries are required.")
    data = [_finite(v, "Packed matrix value") for v in packed]
    x = [_finite(v, "Right-hand-side value") for v in rhs]

    def at(i, j):
        return data[j * (j + 1) // 2 + i]

    for j in range(n):
        if at(j, j) == 0.0:
            return TriangularResult(j, x)
    if not transpose:
        for j in range(n - 1, -1, -1):
            x[j] /= at(j, j)
            for i in range(j):
                x[i] -= x[j] * at(i, j)
    else:
        for j in range(n):
            subtotal = 0.0
            for i in range(j):
                subtotal += at(i, j) * x[i]
            x[j] = (x[j] - subtotal) / at(j, j)
    if not all(math.isfinite(v) for v in x):
        raise OverflowError("Triangular solve arithmetic exceeded binary64 range.")
    return TriangularResult(-1, x)
