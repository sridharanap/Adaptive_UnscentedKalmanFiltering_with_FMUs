import matplotlib.pyplot as plt
import numpy as np

def plots_parameters_KF(t, parameters_true, Parameters_UKF, name, parameters_name, deltaT_m_multiples, 
                        Covariance_parameters, Y_dropped):
    """
    Plots the state estimation results for the Kalman Filter.

    parameters_true: array matrix of true parameter values for all time steps 
    """
    title_fontsize = 20
    label_fontsize = 16
    legend_fontsize = 16
    minutes = t

    beg, last = 0, 5999
    sec = t[beg:last]
    m = Y_dropped.shape[0]

    n_p, num_steps = parameters_true.shape 
    non_nan_indices_m = [~np.isnan(Y_dropped[i, beg:last]) for i in range(m)]
    # n_p = Parameters_UKF.shape[0]
    # colors = ['c*', 'ms', 'bd']  # Cloud 'c*', Magenta 'ms', Blue 'bd'
    # markersizes = [8, 8, 8]
    n_p = Parameters_UKF.shape[0]
    styles = [
        ('c', '*'),   # Cyan star
        ('m', 's'),   # Magenta square
        ('b', 'd')    # Blue diamond
    ]
    markersizes = [8, 8, 8]

    for i in range(n_p):
        # Select parameter traces (true and estimated)
        param_true = parameters_true[i, :]
        param_ukf = Parameters_UKF[i, :]
        mask = ~np.isnan(param_ukf)
        stddev = np.sqrt(Covariance_parameters[i, :])
        upper = param_ukf + 2 * stddev
        lower = param_ukf - 2 * stddev

        # Compute relative error, handling NaNs (set error to zero where estimate is NaN)
        err = param_ukf - param_true
        # err = np.nan_to_num(err, nan=0.0)
        err_rel = 100 * err / (param_true + 1e-12)
        # err_rel = np.nan_to_num(err_rel, nan=0.0)

        plt.figure(f'{parameters_name[i]} Parameter Estimation')
        # Plot True and Estimated Parameters
        plt.subplot(2, 1, 1)
        plt.plot(minutes, param_true, '-b', label='True Value')
        plt.plot(minutes, param_ukf, '-r', label=f'estimation with {name}')
        plt.fill_between(minutes[mask], lower[mask], upper[mask], color='gray', alpha=0.2, label='±2σ - 95.45% confidence')
        # plt.fill_between(minutes[valid_mask], lower[valid_mask], upper[valid_mask], color='gray', alpha=0.2, label='±2σ - 95.45% confidence')
        plt.title(f'{name} Parameter Estimation: {parameters_name[i]}', fontsize=title_fontsize)
        plt.xlabel('Time [min]', fontsize=label_fontsize)
        plt.legend(fontsize=legend_fontsize)
        plt.grid(True)

        plt.subplot(2, 1, 2)
        plt.plot(minutes, err_rel, '-r', label='Relative Error')
        plt.xlim([minutes[0], minutes[-1]])  # Ensure full x-axis is displayed
        plt.title('Relative Estimation Error', fontsize=title_fontsize)
        plt.xlabel('Time [min]', fontsize=label_fontsize)
        plt.ylabel('Error (%)', fontsize=label_fontsize)
        plt.legend(fontsize=legend_fontsize)
        plt.grid(True)

        # Plot in a window, with markers for measurement availability
        param_true_window = parameters_true[i, beg:last]
        param_ukf_window = Parameters_UKF[i, beg:last]
        mask_window = ~np.isnan(param_ukf_window)
        stddev_window = np.sqrt(Covariance_parameters[i, beg:last])
        upper_window = param_ukf_window + 2 * stddev_window
        lower_window = param_ukf_window - 2 * stddev_window

        err_window = param_ukf_window - param_true_window
        # err_window = np.nan_to_num(err_window, nan=0.0)
        err_rel_window = 100 * err_window / (param_true_window + 1e-12)
        # err_rel_window = np.nan_to_num(err_rel_window, nan=0.0)
        
        plt.figure(f'{parameters_name[i]} Parameter Estimation (Window 1)')
        plt.subplot(2, 1, 1)
        plt.plot(sec, param_true_window, '-b', label='True Value')
        plt.plot(sec, param_ukf_window, '-r', label=f'estimation with {name}')
        for j in range(m):
            color, marker = styles[j]
            plt.plot(sec[non_nan_indices_m[j]], param_ukf_window[non_nan_indices_m[j]], color=color, marker=marker, linestyle='None', markersize=markersizes[j])
            # plt.plot(sec[non_nan_indices_m[j]], param_ukf_window[non_nan_indices_m[j]], colors[j], markersize=markersizes[j])
        plt.fill_between(sec[mask_window], lower_window[mask_window], upper_window[mask_window], color='gray', alpha=0.2, label='±2σ - 95.45% confidence')
        plt.title(f'{name} Parameter Estimation: {parameters_name[i]}', fontsize=title_fontsize)
        plt.xlabel('Time [s]', fontsize=label_fontsize)
        plt.legend(fontsize=legend_fontsize)
        plt.grid(True)

        plt.subplot(2, 1, 2)
        plt.plot(sec, err_rel_window, '-r', label='Relative Error Initial Estimation')
        plt.xlim([sec[0], sec[-1]]) # Ensure full x-axis is displayed
        for j in range(m):
            if np.any(non_nan_indices_m[j]):
                color, marker = styles[j]
                plt.plot(sec[non_nan_indices_m[j]], err_rel_window[non_nan_indices_m[j]], color=color, marker=marker, linestyle='None', markersize=markersizes[j])
                # plt.plot(sec[non_nan_indices_m[j]], err_rel_window[non_nan_indices_m[j]], colors[j], markersize=markersizes[j])
        plt.title('Relative Estimation Error', fontsize=title_fontsize)
        plt.xlabel('Time [s]', fontsize=label_fontsize)
        plt.ylabel('Error (%)', fontsize=label_fontsize)
        plt.legend(fontsize=legend_fontsize)
        plt.grid(True)

        plt.tight_layout()
