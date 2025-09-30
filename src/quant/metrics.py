import numpy as np
def information_coefficient(x, y):
    # 簡化：皮爾森相關
    if len(x) < 2:
        return np.nan
    return float(np.corrcoef(x, y)[0,1])
