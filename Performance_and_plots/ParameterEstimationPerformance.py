import numpy as np
from Performance_and_plots.plots_parameters_KF import plots_parameters_KF

def ParameterEstimationPerformance(t, parameters_true, Parameters_UKF, name, parameters_name, Covariance_bounds_flag, Covariance_parameters, 
                                   deltaT_m_multiples, Y_dropped):
    """
    Calculate and display parameter estimation performance metrics such as RMSE and MAE.

    Parameters:
    - t: Time steps array.
    - parameters_true: True parameter values.
    - Parameters_UKF: Estimated parameter vector.
    - name: Identifier for the estimator (e.g., 'UKF').
    - parameters_name: Names of the estimated parameters.
    - covariance_flag: Boolean to indicate whether to plot covariance bounds.
    - Covariance_parameters: Covariance of the estimated parameters.
    - deltaT_m_multiples: Delta T measurement multiples.
    - Y_dropped: Array indicating missing measurements for initial configuration.
    
    """
    no_timesteps = len(t)
    half_time = no_timesteps // 2
    n_p = Parameters_UKF.shape[0]

    RMSE = np.zeros(n_p)
    MAE = np.zeros(n_p)
    MAE_change = np.zeros(n_p)
    MAE_change50 = np.zeros(n_p)

    consecutive_conv_time = 2 * no_timesteps // 3   # to check if the Relative error for joint_states lie below 5 % for the last (1/3*no_timesteps) iteration steps.
    Relerror = np.zeros((n_p, no_timesteps))

    parameters_true_array = np.stack([parameters_true[name] for name in parameters_name])
    print(f"\nEstimated parameters with {name} are:\n")
    for i in range(n_p):
        print(f"{parameters_name[i]} = {Parameters_UKF[i, -1]}")

    print(f"\nMean Absolute Error with {name} parameter estimation:\n")
    print(f"\nMAE (parameters): [{', '.join(map(str, deltaT_m_multiples))}]\n")
    for i in range(n_p):
        # Calculate error (replace NaNs in Parameters_UKF with 0 error)
        err = parameters_true_array[i, :] - Parameters_UKF[i, :]
        err = np.nan_to_num(err, nan=0.0)
        RMSE[i] = np.sqrt(np.mean(err ** 2))
        MAE[i] = np.mean(np.abs(err))

        # Relative error: treat NaNs in estimate as 0% error
        Relerror[i, :] = 100 * np.abs(Parameters_UKF[i, :] - parameters_true_array[i, :]) / (np.abs(parameters_true_array[i, :]) + 1e-12)
        Relerror[i, :] = np.nan_to_num(Relerror[i, :], nan=0.0)

        if np.all(Relerror[i, consecutive_conv_time:] <= 5):
            print(f'{MAE[i]:.6f}', end='    ')
        else:
            print(f'\033[91m{MAE[i]:.6f}\033[0m', end='    ')

    plots_parameters_KF(t, parameters_true_array, Parameters_UKF, name, parameters_name, deltaT_m_multiples, Covariance_parameters,
                        Y_dropped)
    