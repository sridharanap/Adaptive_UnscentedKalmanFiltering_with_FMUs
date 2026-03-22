import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d

def plots_measured_output(t, Y, outputs_vector):
    """
    Plots measurement data provided to the KF, including [Voltage; Temperature; SOC].

    Arguments:
    - t: Time steps vector.
    - Y: Measurement matrix, where each row is a different measurement type and might contain missing NaN measurements.
    - outputs_vector: Sensor module variable containing the list of sensor measurements (which is to be displayed here).
    """
    title_fontsize = 20
    label_fontsize = 16
    m = Y.shape[0]

    fig, axs = plt.subplots(m, 1, figsize=(10, 6))
    if m == 1:
        axs = [axs]  # Ensure axs is iterable when only one subplot
    
    ## Prepare measurement-wise data for interpolation
    # For measurement 1
    non_NaN_indices1 = ~np.isnan(Y[0, :])
    time1 = t[non_NaN_indices1]
    Y1 = Y[0, non_NaN_indices1]
    spline1 = interp1d(time1, Y1, kind='cubic', fill_value="extrapolate")   # Interpolation to fill missing data
    Y_filled1 = spline1(t)
    axs[0].plot(t, Y_filled1)
    axs[0].grid(True)
    axs[0].set_xlabel('Time in [sec]', fontsize=label_fontsize)
    axs[0].set_title(f"Measured {outputs_vector[0]}", fontsize=title_fontsize, fontweight='normal')
    axs[0].set_ylabel(f"{outputs_vector[0]}", fontsize=label_fontsize)

    if m > 1:
        # For measurement 2
        non_NaN_indices2 = ~np.isnan(Y[1, :])
        time2 = t[non_NaN_indices2]
        Y2 = Y[1, non_NaN_indices2]
        spline2 = interp1d(time2, Y2, kind='cubic', fill_value="extrapolate")   # Interpolation to fill missing data
        Y_filled2 = spline2(t)
        axs[1].plot(t, Y_filled2)
        axs[1].grid(True)
        axs[1].set_xlabel('Time in [sec]', fontsize=label_fontsize)
        axs[1].set_title(f"Measured {outputs_vector[1]}", fontsize=title_fontsize, fontweight='normal')
        axs[1].set_ylabel(f"{outputs_vector[1]}", fontsize=label_fontsize)

    if m > 2:
        # For measurement 3
        non_NaN_indices3 = ~np.isnan(Y[2, :])
        time3 = t[non_NaN_indices3]
        Y3 = Y[2, non_NaN_indices3]
        spline3 = interp1d(time3, Y3, kind='cubic', fill_value="extrapolate")   # Interpolation to fill missing data
        Y_filled3 = spline3(t)
        axs[2].plot(t, Y_filled3)
        axs[2].grid(True)
        axs[2].set_xlabel('Time in [sec]', fontsize=label_fontsize)
        axs[2].set_title(f"Measured {outputs_vector[2]}", fontsize=title_fontsize, fontweight='normal')
        axs[2].set_ylabel(f"{outputs_vector[2]}", fontsize=label_fontsize)

    plt.tight_layout()