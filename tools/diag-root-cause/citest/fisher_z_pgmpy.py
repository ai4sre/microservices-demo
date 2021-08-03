import numpy as np
import pandas as pd
from scipy import stats


def fisher_z(X, Y, Z, data, boolean=True, **kwargs):
    # Step 1: Test if the inputs are correct
    if not hasattr(Z, "__iter__"):
        raise ValueError(f"Variable Z. Expected type: iterable. Got type: {type(Z)}")
    else:
        Z = list(Z)

    if not isinstance(data, pd.DataFrame):
        raise ValueError(
            f"Variable data. Expected type: pandas.DataFrame. Got type: {type(data)}"
        )

    n = data.shape[0]
    zs = zstat(X, Y, Z, data, n)
    p_val = 2.0 * stats.norm.sf(np.absolute(zs))
    if boolean:
        if p_val >= kwargs["significance_level"]:
            return True
        else:
            return False
    else:
        return zs, p_val


def zstat(X, Y, Z, data, n):
    r = pcor_order(X, Y, Z, data)
    zv = np.sqrt(n - len(Z) - 3) * 0.5 * log_q1pm(r)
    if np.isnan(zv):
        return 0
    else:
        return zv


def log_q1pm(r):
    if r == 1:
        r = 1 - 1e-10
    return np.log1p((2 * r) / (1 - r))


def pcor_order(X, Y, Z, data):
    if len(Z) == 0:
        coef, _ = stats.pearsonr(data.loc[:, X], data.loc[:, Y])
    else:
        X_coef = np.linalg.lstsq(data.loc[:, Z], data.loc[:, X], rcond=None)[0]
        Y_coef = np.linalg.lstsq(data.loc[:, Z], data.loc[:, Y], rcond=None)[0]

        residual_X = data.loc[:, X] - data.loc[:, Z].dot(X_coef)
        residual_Y = data.loc[:, Y] - data.loc[:, Z].dot(Y_coef)
        coef, _ = stats.pearsonr(residual_X, residual_Y)
    return coef
