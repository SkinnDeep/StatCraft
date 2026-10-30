"""Finite, readable 1/2/2.5/5 tick spacing for model diagnostic plots."""
import math


def _step(span,count,integer=False):
    raw=span/max(1,count-1)
    if not math.isfinite(raw) or raw<=0:return None
    exponent=math.floor(math.log10(raw))
    unit=10.**exponent
    if unit==0:return None
    fraction=raw/unit
    multiplier=next((value for value in (1.,2.,2.5,5.,10.) if value>=fraction*(1-1e-12)),10.)
    step=multiplier*unit
    if integer:step=max(1.,math.ceil(step))
    return step if math.isfinite(step) and step>0 else None


def nice_limits(low,high,count=6,integer=False):
    """Round automatic limits outward; caller keeps user-set limits unchanged."""
    if not all(math.isfinite(value) for value in (low,high,high-low)) or high<=low:return low,high
    step=_step(high-low,count,integer)
    if step is None:return low,high
    try:lower=math.floor(low/step+1e-12)*step;upper=math.ceil(high/step-1e-12)*step
    except (OverflowError,ValueError):return low,high
    if not all(math.isfinite(value) for value in (lower,upper,upper-lower)) or upper<=lower:return low,high
    return (0. if lower==0 else lower,0. if upper==0 else upper)


def tick_values(low,high,count=6,integer=False):
    if not all(math.isfinite(value) for value in (low,high,high-low)) or high<=low:return []
    step=_step(high-low,count,integer)
    if step is None:return [low,high]
    start=math.ceil(low/step-1e-12);end=math.floor(high/step+1e-12)
    if end-start>100:return [low,high]
    values=[]
    for index in range(start,end+1):
        value=index*step
        if low-step*1e-10<=value<=high+step*1e-10:values.append(0. if abs(value)<step*1e-12 else value)
    return values or [low,high]
