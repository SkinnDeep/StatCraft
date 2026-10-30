"""Calc Patterned Data & Random Data Generation.

Provides:
- Make Patterned Data:
  * Simple Set of Numbers
  * Arbitrary Set of Numbers
  * Text Values
- Random Data Generation: Normal, Uniform, Exponential, Poisson, Binomial
"""
from __future__ import annotations

import math
import random


def make_patterned_numbers(from_val: float, to_val: float, step: float = 1.0,
                           repeat_each: int = 1, repeat_sequence: int = 1) -> list[float]:
    if step == 0:
        raise ValueError("Step value cannot be zero.")
    if repeat_each < 1:
        repeat_each = 1
    if repeat_sequence < 1:
        repeat_sequence = 1

    # Generate basic sequence
    seq = []
    curr = float(from_val)
    if step > 0:
        while curr <= to_val + 1e-9:
            seq.append(round(curr, 8))
            curr += step
    else:
        while curr >= to_val - 1e-9:
            seq.append(round(curr, 8))
            curr += step

    if not seq:
        seq = [float(from_val)]

    # Repeat each
    expanded = []
    for val in seq:
        expanded.extend([val] * repeat_each)

    # Repeat sequence
    result = []
    for _ in range(repeat_sequence):
        result.extend(expanded)

    return result


def make_patterned_arbitrary_numbers(items: list[float], repeat_each: int = 1, repeat_sequence: int = 1) -> list[float]:
    if not items:
        raise ValueError("At least one number is required.")
    if repeat_each < 1:
        repeat_each = 1
    if repeat_sequence < 1:
        repeat_sequence = 1

    expanded = []
    for val in items:
        expanded.extend([val] * repeat_each)

    result = []
    for _ in range(repeat_sequence):
        result.extend(expanded)
    return result


def make_patterned_text(items: list[str], repeat_each: int = 1, repeat_sequence: int = 1) -> list[str]:
    if not items:
        raise ValueError("At least one text value is required.")
    if repeat_each < 1:
        repeat_each = 1
    if repeat_sequence < 1:
        repeat_sequence = 1

    expanded = []
    for val in items:
        expanded.extend([val] * repeat_each)

    result = []
    for _ in range(repeat_sequence):
        result.extend(expanded)
    return result


def generate_random_normal(n: int, mean: float = 0.0, stdev: float = 1.0, seed: int | None = None) -> list[float]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if stdev <= 0:
        raise ValueError("Standard deviation must be positive.")

    rng = random.Random(seed) if seed is not None else random.Random()
    return [round(rng.gauss(mean, stdev), 6) for _ in range(n)]


def generate_random_uniform(n: int, low: float = 0.0, high: float = 1.0, seed: int | None = None) -> list[float]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if high <= low:
        raise ValueError("Upper endpoint must be greater than lower endpoint.")

    rng = random.Random(seed) if seed is not None else random.Random()
    return [round(rng.uniform(low, high), 6) for _ in range(n)]


def generate_random_exponential(n: int, scale: float = 1.0, seed: int | None = None) -> list[float]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if scale <= 0:
        raise ValueError("Scale (mean) must be positive.")

    rng = random.Random(seed) if seed is not None else random.Random()
    return [round(rng.expovariate(1.0 / scale), 6) for _ in range(n)]


def generate_random_poisson(n: int, mean: float = 1.0, seed: int | None = None) -> list[int]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if mean <= 0:
        raise ValueError("Mean must be positive.")

    rng = random.Random(seed) if seed is not None else random.Random()
    L = math.exp(-mean)
    result = []
    for _ in range(n):
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= rng.random()
            if p <= L:
                break
        result.append(k - 1)
    return result


def generate_random_binomial(n: int, trials: int = 10, prob: float = 0.5, seed: int | None = None) -> list[int]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if trials < 1:
        raise ValueError("Number of trials must be at least 1.")
    if not (0.0 <= prob <= 1.0):
        raise ValueError("Event probability must be between 0 and 1.")

    rng = random.Random(seed) if seed is not None else random.Random()
    result = []
    for _ in range(n):
        successes = sum(1 for _ in range(trials) if rng.random() < prob)
        result.append(successes)
    return result
