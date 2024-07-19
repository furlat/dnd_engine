from typing import Dict, Tuple

def update_or_concat_to_dict(d: Dict[str, list], kv: Tuple[str, list]) -> Dict[str, list]:
    key, value = kv
    if key in d:
        d[key] += value
    else:
        d[key] = value
    return d

def update_or_sum_to_dict(d: Dict[str, int], kv: Tuple[str, int]) -> Dict[str, int]:
    key, value = kv
    if key in d:
        d[key] += value
    else:
        d[key] = value
    return d