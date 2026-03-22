import numpy as np
from Performance_and_plots.plots_states_KF import plots_states_KF

def StateEstimationPerformance(t, X, States_KF, name, Covariance_bounds_flag, Covariance_states, 
                               deltaT_m_multiples, P_kf_all, Y_dropped):
    """
    Calculate and display state estimation performance metrics such as RMSE and MAE.

    Parameters:
    - t: Time steps array.
    - X: True state vector.
    - States_KF: Estimated state vectors.
    - name: Identifier for the estimator (e.g., 'UKF').
    - covariance_flag: Boolean to indicate whether to plot covariance bounds.
    - Covariance_state: Covariance of the estimated states.
    - deltaT_m_multiples: Original deltaT measurement multiples.
    - P_ukf_all: UKF covariance over all timesteps for primary estimation.
    - Y_dropped: Array indicating missing measurements for initial configuration

    """

    no_timesteps = len(t)
    half_time = no_timesteps // 2
    n_s = States_KF.shape[0]

    RMSE = np.zeros(n_s)
    MAE = np.zeros(n_s)

    consecutive_conv_time = 2 * no_timesteps // 3 # to check if the MAE for all joint_states lie below 5 % for the last (1/3*no_timesteps) iteration steps.
    Relerror = np.zeros((n_s, no_timesteps))

    print(f"\nMean Absolute Error with {name} state estimation:\n")
    print(f"\nMAE (states): [{', '.join(map(str, deltaT_m_multiples))}]\n")
    for i in range(n_s):
        err = X[i, :] - States_KF[i, :]
        err = np.nan_to_num(err, nan=0.0)  # Replace NaNs with 0
        RMSE[i] = np.sqrt(np.mean(err ** 2))
        MAE[i] = np.mean(np.abs(err))

        Relerror[i, :] = 100 * np.abs((States_KF[i, :] - X[i, :])) / np.abs((X[i, :] + 1e-12))
        Relerror[i, :] = np.nan_to_num(Relerror[i, :], nan=0.0)

        if np.all(Relerror[i, consecutive_conv_time:] <= 5): # to investigate further
            print(f'{MAE[i]:.6f}', end='    ')
        else:
            print(f'\033[91m{MAE[i]:.6f}\033[0m', end='    ')

    plots_states_KF(t, X, States_KF, name, deltaT_m_multiples, P_kf_all, Covariance_states, Y_dropped)
    