import numpy as np
import matplotlib.pyplot as plt
import sys
import time
import os, re
import pickle
from pathlib import Path
from scipy.stats import chi2
from typing import List, Tuple, Dict, Optional
import openpyxl

import yaml
import importlib

from EmulateSensor import EmulateSensor
from FMUInterface import UKF_FMU_Interface
from JointUKF import JointUKF

from Performance_and_plots.plots_input import plots_input
from Performance_and_plots.plots_measured_output import plots_measured_output
from Performance_and_plots.StateEstimationPerformance import StateEstimationPerformance
from Performance_and_plots.ParameterEstimationPerformance import ParameterEstimationPerformance

def load_config(path: str = "UKF_battery.yaml") -> dict: # ! USER MUST SET THE YAML FILE HERE
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    # Load configuration from YAML file
    cfg = load_config("UKF_battery.yaml")                # ! USER MUST SET THE YAML FILE HERE

    # set seed for reproducibility
    seed = int(cfg["random"]["seed"])
    np.random.seed(seed)

    # Simulation parameters
    fmu = cfg["fmu"]["path"]                                           # FMU file path
    simulation_time_min = int(cfg["simulation"]["time_min"])           # Simulation time in minutes
    delta_T = np.float64(cfg["simulation"]["delta_T"])                 # Sampling time in seconds
    flagScaleSystem = int(bool(cfg["ukf"]["normalize_states"]))        # Flag for system normalization
    flagCovariance = int(bool(cfg["ukf"]["plot_covariance"]))          # Flag for plotting UKF covariance bounds in estimation plots

    # ------------- Input: single function from YAML ---------------
    inp_module = importlib.import_module(cfg["inputs"]["module"])
    input_function = getattr(inp_module, cfg["inputs"]["function"])

    u = input_function(simulation_time_min, delta_T)
    u = np.asarray(u, dtype=np.float64)
    
    num_steps = round((simulation_time_min * 60) / delta_T)           # Number of time-steps
    t = np.arange(num_steps) * delta_T                                # Time-steps vector (seconds)
    n_inputs = len(cfg["inputs"].get("fmu_input_names", []))
    if u.ndim != 2:
        raise ValueError(
            f"Input array u must be 2D with shape ({n_inputs}, {num_steps}), "
            f"got shape {u.shape}"
        )
    if u.shape[1] != num_steps:
        raise ValueError(
            f"Input array u must have {num_steps} columns (one per iteration step), "
            f"got shape {u.shape}"
        )
    if u.shape[0] != n_inputs:
        raise ValueError(
            f"Input array u has {u.shape[0]} rows, but YAML "
            f"inputs.fmu_input_names has length {n_inputs}."
        )

    sensor_cfg = cfg["sensor"]

    def load_sensor_data_from_excel(cfg, sensor_cfg, num_steps) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
        """
        Multi-sheet Excel layout (sheet names configured in YAML under sensor.excel.sheet.*):

        - X_true sheet: TRUE STATE VALUES; columns = len(cfg["states"]["names"]), rows = iteration_steps
        Returns X_true as (n_states, iteration_steps)
        Assertions:
            number of columns must match len(states.names) in YAML.

        - Y_true / Y_noised / Y_dropped sheets: MEASUREMENT VALUES; columns = cfg["measurements"]["available_measurements"], rows = iteration_steps-1
        Returns each as (n_meas, iteration_steps-1)
        Assertions: 
            first sample (row 0) must NOT contain NaN for any measurement.
            number of columns must match len(measurements.available_measurements) in YAML.

        - parameters_true sheet: PARAMETER VALUES ALONG TIME_STEPS; columns = len(cfg["parameters"]["all"]), rows = iteration_steps
        Returns parameters_true dict {name: (iteration_steps,)} and asserts columns are not all-NaN.
        Assertions:
            number of columns must match len(parameters.all) in YAML.

        File must be located in ./Inputs/<file>.

        Args:
            - cfg: full configuration dict from YAML
            - sensor_cfg: sensor-specific configuration dict from YAML
            - num_steps: number of iteration steps

        Returns:
            - X_true: (n_states, iteration_steps)
            - Y_true: (n_meas, iteration_steps-1)
            - Y_noised: (n_meas, iteration_steps-1)
            - Y_dropped: (n_meas, iteration_steps-1)
            - parameters_true: dict[name] -> (iteration_steps,)
        """
    
        excel_cfg = sensor_cfg.get("excel", {})
        file_str = excel_cfg.get("file")
        sheet_cfg = excel_cfg.get("sheet", {})

        if not file_str:
            raise ValueError("sensor.sensor_emulation is false, but 'sensor.excel.file' is not set in YAML.")

        repo_root = Path(__file__).resolve().parent
        # User MUST place file inside ./Inputs
        file_path = repo_root / "Inputs" / file_str
        if not file_path.exists():
            raise FileNotFoundError(f"Sensor input file not found at: {file_path}."
                "Ensure the sensor file is placed inside the './Inputs' folder.")

        # Required names from YAML
        state_names = cfg["states"]["names"]
        meas_names = cfg["measurements"]["available_measurements"]
        param_names = cfg["parameters"]["all"]

        it_steps = int(num_steps)
        y_steps = it_steps - 1

        # Required sheet names from YAML
        required_sheet_keys = ["X_true", "Y_true", "Y_noised", "Y_dropped", "parameters_true"]  # These keys are present and fixed under sensor.excel.sheet in YAML
        missing_sheet_keys = [k for k in required_sheet_keys if not sheet_cfg.get(k)]
        if missing_sheet_keys:
            raise ValueError(f"Missing required YAML entries under sensor.excel.sheet for: {missing_sheet_keys}")

        sh_X = sheet_cfg["X_true"]
        sh_Yt = sheet_cfg["Y_true"]
        sh_Yn = sheet_cfg["Y_noised"]
        sh_Yd = sheet_cfg["Y_dropped"]
        sh_P = sheet_cfg["parameters_true"]

        # Load workbook and sheets
        wb = openpyxl.load_workbook(file_path, data_only=True)

        def read_table(sheet_name: str, required_cols: List[str], n_rows: int) -> np.ndarray:
            if sheet_name not in wb.sheetnames:
                raise ValueError(f"Excel sheet '{sheet_name}' not found. Available sheets: {wb.sheetnames}")

            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))   # List of rows, where each row is a tuple of cell values.
                                                          # First row is header.
            if len(rows) < 2:
                raise ValueError(f"Excel sheet '{sheet_name}' must contain a header row and values.")

            header = [str(c).strip() if c is not None else "" for c in rows[0]]
            col_index = {name: i for i, name in enumerate(header) if name}

            missing = [c for c in required_cols if c not in col_index]
            if missing:
                raise ValueError(
                    f"Excel sheet '{sheet_name}' is missing required columns: {missing}. "
                    f"Found columns: {header}"
                )

            data_rows = rows[1:]
            if len(data_rows) < n_rows:
                raise ValueError(
                    f"Excel sheet '{sheet_name}' has {len(data_rows)} data rows, but {n_rows} are required.") # missing cells become None and are converted to NaN below. 

            out = np.full((len(required_cols), n_rows), np.nan, dtype=np.float64)
            for r in range(n_rows):
                row = data_rows[r]
                for j, c in enumerate(required_cols):
                    idx = col_index[c]
                    val = row[idx] if idx < len(row) else None
                    out[j, r] = np.nan if val is None else np.float64(val)
            return out
        
        # Read matrices in (n_vars, n_time) format directly
        X_true = read_table(sh_X, state_names, it_steps)           # (n_states, it_steps)
        Y_true = read_table(sh_Yt, meas_names, y_steps)            # (n_meas, y_steps)
        Y_noised = read_table(sh_Yn, meas_names, y_steps)          # (n_meas, y_steps)
        Y_dropped = read_table(sh_Yd, meas_names, y_steps)         # (n_meas, y_steps)

        # First-sample NaN assertion for Y_* matrices
        def assert_first_sample_not_nan(name: str, Y: np.ndarray):
            if np.isnan(Y[:,0]).any():
                bad = np.where(np.isnan(Y[:, 0]))[0].tolist()
                bad_names = [meas_names[i] for i in bad]
                raise AssertionError(
                f"{name}: first sample contains NaN for measurement(s): {bad_names}."
                "Requirement: first sample must always be available (no NaNs).")
        
        assert_first_sample_not_nan("Y_true", Y_true)
        assert_first_sample_not_nan("Y_noised", Y_noised)
        assert_first_sample_not_nan("Y_dropped", Y_dropped)

        P_mat = read_table(sh_P, param_names, it_steps)  # (n_params, it_steps)

        parameters_true: Dict[str, np.ndarray] = {p: P_mat[i, :].copy() for i, p in enumerate(param_names)}

        return X_true, Y_true, Y_noised, Y_dropped, parameters_true

#   ------- Emulate battery system FMU model (with missing measurements) -----------
    if bool(sensor_cfg.get("sensor_emulation", True)) is True:
        print("\n--- Emulating sensor measurements from the EmulateSensor module ---")
        Sensors = EmulateSensor(fmu, simulation_time_min, u, delta_T, cfg)
        X_true, Y_true, Y_noised, Y_dropped, parameters_true = Sensors.emulate()
    else:
        # Read sensor signals from Excel in /Inputs (configurable via YAML)
        print("\n--- Reading sensor measurements from file ---")
        X_true, Y_true, Y_noised, Y_dropped, parameters_true =  load_sensor_data_from_excel(cfg, sensor_cfg, num_steps)
    tic = time.time()

#   ------- Perform UKF estimation for the FMU battery model ------------
    ukf_fmu_interface = UKF_FMU_Interface(fmu, flagScaleSystem, cfg)
    x_ukf, P0, Q, R = ukf_fmu_interface.initialise()

    ukf_estimator = JointUKF(simulation_time_min, x_ukf, u, Y_dropped, P0, Q, R, delta_T, ukf_fmu_interface, cfg)
    
    ukf_estimator.perform_estimation()  # The class JointUKF (whose object here is 'ukf_estimator') only performs the core UKF computations and stores the predictions.
    ukf_fmu_interface.terminate()
    XNormalized_UKF, P_ukf_all = ukf_estimator.get_results()

    k_scale_full = np.diag(np.concatenate((ukf_fmu_interface.scale_factors_states, ukf_fmu_interface.scale_factors_params))).astype(np.float64)  # full-spectrum k_scale matrix

    X_UKF = k_scale_full.diagonal()[:, None] * XNormalized_UKF # Broadcasted
    States_UKF = X_UKF[:ukf_fmu_interface.n_s, :]
    
    Covariance = k_scale_full.diagonal()[:, None]**2 * np.diagonal(P_ukf_all, axis1=0, axis2=1).T
    Covariance_states = Covariance[:ukf_fmu_interface.n_s, :]

    toc = time.time()
    ET = toc - tic
    print(f"\n\nElapsed time: {ET:.2f} seconds")

#   ------- Display the estimation set-ups ----------
    m = Y_dropped.shape[0]
    deltaT_m_cfg = sensor_cfg.get("deltaT_m_multiples", [1] * m)
    deltaT_m_multiples = np.array(deltaT_m_cfg, dtype=int)
    print(f"Available Measurements: {ukf_fmu_interface.measurements_list} was chosen. Number of outputs: {m}")
    print(f"Missing measurement multiples: {deltaT_m_multiples}")
    print(f"System normalization: {flagScaleSystem} (1 for normalized, 0 for not-normalized)")

    print("\nAll Parameters in the system:")
    for name in ukf_fmu_interface.all_parameters:
        print(f"{name}", end="  ") # Print all available parameters

#   -----------------------------------------------------------------------------------------------------------------
#   ------------------------------ USER CAN CARRY OUT THE CUSTOM PLOTTING BELOW -------------------------------------
#   -----------------------------------------------------------------------------------------------------------------
    
    # -------- Plot the time-averaged Normalized Innovation Squared (NIS) ---------
    plt.figure("Time-averaged Normalized Innovation Squared (NIS)")
    plt.plot(t, ukf_estimator.NIS_mean, label='Time-averaged NIS (100 time-steps)')
    # Original confidence bounds
    plt.plot(t, ukf_estimator.chi2_threshold_upper,
        color='red', linestyle='--', label=f"{float(ukf_estimator.confidence*100)}% upper confidence Chi-square threshold")
    plt.plot(t, ukf_estimator.chi2_threshold_lower,
        color='green', linestyle='--', label=f"{float(ukf_estimator.confidence*100)}% lower confidence Chi-square threshold")
    plt.plot(t, 1.1*ukf_estimator.chi2_threshold_upper,
        color='red', linestyle=':', linewidth=1.1,
        label="Upper relaxed (1.1x) Chi-sq bound - INCONSISTENCY DETECTION")
    plt.plot(t, 0.9*ukf_estimator.chi2_threshold_lower,
        color='green', linestyle=':', linewidth=1.1,
        label="Lower relaxed (0.9x) Chi-sq bound - INCONSISTENCY DETECTION")
    plt.xlabel('Time Step (seconds)')
    plt.ylabel('Time-avg NIS Value')
    plt.title('Time-averaged Normalized Innovation Squared (NIS) vs Time')
    plt.legend(fontsize=9)
    plt.grid()

    #   ------- Plot the input and measured output ----------
    plots_input(t, u)                                                            # Plot input current
    plots_measured_output(t[:-1],Y_dropped, ukf_fmu_interface.measurements_list) # Plot measurements (maybe noisy and/or inconsistent)

    #   ------- Calculate and plot performance of the UKF ----------
    StateEstimationPerformance(t, X_true, States_UKF, 'UKF', flagCovariance, Covariance_states, 
                               deltaT_m_multiples, P_ukf_all, Y_dropped)
    
    Parameters_UKF = X_UKF[ukf_fmu_interface.n_s:, :]
    Covariance_parameters = Covariance[ukf_fmu_interface.n_s:, :]
    ParameterEstimationPerformance(t, parameters_true, Parameters_UKF, 'UKF', ukf_fmu_interface.all_parameters, 
                                    flagCovariance, Covariance_parameters, deltaT_m_multiples, Y_dropped)

    plt.show()

if __name__ == "__main__":
    main()
