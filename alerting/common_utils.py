import numpy as np
import math


def percentage_limit(t):
    """
    Input: time in minutes, output: minimal percentage change for raising alert
    """
    initial_threshold = 1.5
    threshold_multiplier = 1.1
    time_multiplier = 1.5
    return initial_threshold * threshold_multiplier ** (np.log(t / 5) / np.log(time_multiplier) - 1)


def smart_float_format(x):
    if x >= 1 or x == 0:
        return f"{round(x, 2):.2f}"
    precision = -math.floor(math.log(x, 10)) + 3
    return f"{x:.{precision}f}"


def smart_time_duration_format(duration):
    """
    Input: duration in minutes
    """
    if duration <= 90:
        return f"{int(duration)} minutes"
    elif duration <= 60 * 33:
        return f"{int(round(duration / 60, 0))} hours"
    else:
        return f"{int(round(duration / (60 * 24), 0))} days"


def rectified_root(x, degree):
    """
    For x <= 1 an identity, otherwise a root function of the specified degree (smoothed out so that
    the derivative is continuous).
    """
    if x <= 1:
        return x
    return (x - 1 + degree ** (1 / (1 / degree - 1))) ** (1 / degree) - degree ** (1 / (1 - degree)) + 1
