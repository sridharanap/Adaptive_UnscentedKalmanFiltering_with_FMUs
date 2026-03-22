import matplotlib.pyplot as plt
import numpy as np

def plots_states_KF(t, X, States_KF, name, deltaT_m, 
                    P_kf_all, Covariance, Y_dropped):
    """
    Plots the state estimation results for the Kalman Filter.
    """
    title_fontsize = 16
    label_fontsize = 14
    legend_fontsize = 14
    minutes = t

    beg, last = 0, 5999
    sec = t[beg:last]
    m = Y_dropped.shape[0]

    non_nan_indices_m1 = ~np.isnan(Y_dropped[0, beg:last])
    if m > 1:
        non_nan_indices_m2 = ~np.isnan(Y_dropped[1, beg:last])
    if m > 2:
        non_nan_indices_m3 = ~np.isnan(Y_dropped[2, beg:last])

    SOC = X[0, :]
    SOC_KF = States_KF[0, :]

    SOC_temp = SOC[beg:last]
    SOC_KF_temp = SOC_KF[beg:last]

    err_rel_SOC = 100 * (SOC_KF - SOC) / SOC
    err_rel_SOC_temp = 100 * (SOC_KF_temp - SOC_temp) / SOC_temp

    T = X[1, :]
    T_KF = States_KF[1, :]

    T_temp = T[beg:last]
    T_KF_temp = T_KF[beg:last]

    err_rel_T = 100 * (T_KF - T) / T
    err_rel_T_temp = 100 * (T_KF_temp - T_temp) / T_temp

#   --------------- Plotting States: SOC ------------------

    plt.figure('Battery states: SOC')
    plt.subplot(2, 1, 1)
    plt.plot(minutes, SOC, '-b', label='true value')
    plt.plot(minutes, SOC_KF, '-r', label=f'estimation with {name}')
    plt.title(f'Battery state: SOC, estimation with {name}', fontsize=title_fontsize)
    plt.xlabel('Time [min]', fontsize=label_fontsize)
    plt.ylabel('SOC(%)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(minutes, err_rel_SOC, 'r', label='Relative error initial estimation')
    plt.title('Relative estimation error', fontsize=title_fontsize)
    plt.xlabel('Time [min]', fontsize=label_fontsize)
    plt.ylabel('err (%)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)

#   --------------- Plotting States: SOC (Plot with missing measurement markers and specified window size) ------------------

    plt.figure('Battery states: SOC (Missing measurements-window size)')
    plt.subplot(2, 1, 1)
    plt.plot(sec, SOC_temp, '-b', label='true value')
    plt.plot(sec, SOC_KF_temp, '-r', label=f'estimation with {name}')
    plt.plot(sec[non_nan_indices_m1], SOC_KF_temp[non_nan_indices_m1], 'c*', markersize=8, label='measurement available')
    if m > 1:
        plt.plot(sec[non_nan_indices_m2], SOC_KF_temp[non_nan_indices_m2], 'ms', markersize=8, label='measurement available')
    if m > 2:
        plt.plot(sec[non_nan_indices_m3], SOC_KF_temp[non_nan_indices_m3], 'bd', markersize=8, label='measurement available')
    plt.title(f'Battery state: SOC, estimation with {name}', fontsize=title_fontsize)
    plt.xlabel('time in [min]', fontsize=label_fontsize)
    plt.ylabel('SOC(%)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(sec, err_rel_SOC_temp, 'r', label='Relative error - initial estimation')
    plt.plot(sec[non_nan_indices_m1], err_rel_SOC_temp[non_nan_indices_m1], 'c*', markersize=8, label='measurement available')
    if m > 1:
        plt.plot(sec[non_nan_indices_m2], err_rel_SOC_temp[non_nan_indices_m2], 'ms', markersize=8, label='measurement available')
    if m > 2:
        plt.plot(sec[non_nan_indices_m3], err_rel_SOC_temp[non_nan_indices_m3], 'bd', markersize=8, label='measurement available')
    plt.title('Relative estimation error', fontsize=title_fontsize)
    plt.xlabel('time in [min]', fontsize=label_fontsize)
    plt.ylabel('err (%)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)

#   --------------- Plotting States: Temperature (T) ------------------
    plt.figure('Battery states: Core Temperature-T_core')
    plt.subplot(2, 1, 1)
    plt.plot(minutes, T, '-b', label='true value')
    plt.plot(minutes, T_KF, '-r', label=f'estimation with {name}')
    plt.title(f'Battery state: Core Temperature, estimation with {name}', fontsize=title_fontsize)
    plt.xlabel('time in [min]', fontsize=label_fontsize)
    plt.ylabel('T_core (°C)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(minutes, err_rel_T, 'r', label='Relative error initial estimation')
    plt.title('Relative estimation error', fontsize=title_fontsize)
    plt.xlabel('time in [min]', fontsize=label_fontsize)
    plt.ylabel('err (%)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)

#   --------------- Plotting States: Temperature T (Plot with missing measurement markers and specified window size) ------------------

    plt.figure('Battery states: Core Temperature-T_core (Missing measurements-window size)')
    plt.subplot(2, 1, 1)
    plt.plot(sec, T_temp, '-b', label='true value')
    plt.plot(sec, T_KF_temp, '-r', label=f'estimation with {name}')
    plt.plot(sec[non_nan_indices_m1], T_KF_temp[non_nan_indices_m1], 'c*', markersize=8, label='measurement available')
    if m > 1:
        plt.plot(sec[non_nan_indices_m2], T_KF_temp[non_nan_indices_m2], 'ms', markersize=8, label='measurement available')
    if m > 2:
        plt.plot(sec[non_nan_indices_m3], T_KF_temp[non_nan_indices_m3], 'bd', markersize=8, label='measurement available')
    plt.title(f'Battery state: Core Temperature, estimation with {name}', fontsize=title_fontsize)
    plt.xlabel('time in [min]', fontsize=label_fontsize)
    plt.ylabel('T_core (°C)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(sec, err_rel_T_temp, 'r', label='Relative error - initial estimation')
    plt.plot(sec[non_nan_indices_m1], err_rel_T_temp[non_nan_indices_m1], 'c*', markersize=8, label='measurement available')
    if m > 1:
        plt.plot(sec[non_nan_indices_m2], err_rel_T_temp[non_nan_indices_m2], 'ms', markersize=8, label='measurement available')
    if m > 2:
        plt.plot(sec[non_nan_indices_m3], err_rel_T_temp[non_nan_indices_m3], 'bd', markersize=8, label='measurement available')
    plt.title('Relative estimation error', fontsize=title_fontsize)
    plt.xlabel('time in [min]', fontsize=label_fontsize)
    plt.ylabel('err (%)', fontsize=label_fontsize)
    plt.legend(fontsize=legend_fontsize)
    plt.grid(True)
