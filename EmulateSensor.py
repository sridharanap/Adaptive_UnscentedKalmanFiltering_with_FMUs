import numpy as np
import shutil
from fmpy import read_model_description, extract, instantiate_fmu
import scipy
import copy

class EmulateSensor:
    """
    Generic Sensor module that emulates the "true" system by simulating an FMU with
    (optionally drifting) parameters, process noise on the states and measurement noise
    on the outputs, and configurable measurement dropping patterns.

    All system-specific configuration is provided via the YAML config (cfg).
    """
    def __init__(self, fmu_path, simulationtime_min, u, deltaT, cfg):
        """
        *** ENSURED TYPE DOUBLE (FLOAT64) FOR ALL STORED VARIABLES ***
        Inside emulate() method, the "True" system is simulated.

        Args:
        - fmu_path: Path (string) to the FMU file used for "true" system emulation.
        - simulationtime_min: Simulation time in minutes.
        - u: Input array of shape (n_inputs, iteration_steps) (float64).
        - deltaT: Time-step size (seconds).
        - cfg: Full YAML configuration dictionary (same as for FMUInterface).
        """
        self.fmu_path = fmu_path
        self.model_description = read_model_description(fmu_path)
        self.unzip_dir = extract(fmu_path)
        self.fmu = instantiate_fmu(self.unzip_dir, self.model_description, fmi_type=cfg["fmu"]["model_type"])
        self.cfg = cfg

        self.variable_dict = {var.name: var for var in self.model_description.modelVariables} # extract and store all model variables from FMU-xml file in a dictionary.

        # ---- basic config ----
        self.iteration_steps = round((simulationtime_min * 60) / deltaT)   # Number of time-steps
        self.deltaT = np.float64(deltaT)                                   # Sampling/Step size in seconds
        self.u = u                                                         # Input current sequence

        # ---- states config ----
        states_cfg = cfg["states"]
        self.state_names = states_cfg["names"]
        self.n_s = len(self.state_names)

        # ---- measurements config ----
        meas_cfg = cfg["measurements"]
        self.all_measurements = list(meas_cfg["all"])
        self.scale_factors_meas_all = np.array(meas_cfg["scale_factors_measurement_all"], dtype=np.float64)
        assert len(self.all_measurements) == len(self.scale_factors_meas_all), \
            "'measurements.scale_factors_measurement_all' must have the same length as 'measurements.all' in the YAML file."

        self.measurements_list = list(meas_cfg["available_measurements"])  # List of measured Sensor signals from the system
        assert len(self.measurements_list) > 0, \
            "'measurements.available_measurements' must contain at least one measurement in the YAML file."
        self.m = len(self.measurements_list)           # number of sensor signal measurements

        # ---- inputs config ----
        inputs_cfg = cfg["inputs"]
        self.input_names = list(inputs_cfg.get("fmu_input_names", []))
        assert len(self.input_names) > 0, \
            "'inputs.fmu_input_names' must contain at least one input variable in the YAML file."
        for name in self.input_names:
            assert name in self.variable_dict, \
                f"Input variable '{name}' specified in YAML 'inputs.fmu_input_names' not found in FMU-xml model description file (case-sensitive match required)."
        
        # ---- sensor-specific config ----
        sensor_cfg = cfg["sensor"]

        # true initial states of the physical system
        self.x0 = np.array(sensor_cfg["initial_states_true"],dtype=np.float64)        # Initial state vector
        assert len(self.x0) == self.n_s, \
            "'sensor.initial_states_true' must have the same length as 'states.names' in the YAML file."

        self.q_true = np.array(sensor_cfg["process_noise_std_true"], dtype=np.float64) # True Process noise std. deviation (to be added as random walk)
        assert len(self.q_true) == self.n_s, \
            "'sensor.process_noise_std_true' must have the same length as 'states.names' in the YAML file."
        
        self.r_true = np.array(sensor_cfg["measurement_noise_std_true"], dtype=np.float64) # True Measurement noise std. deviation (to be added as random walk)
        assert len(self.r_true) == self.m, \
            "'sensor.measurement_noise_std_true' must have the same length as 'measurements.available_measurements' in the YAML file."
        
        self.StateRange = np.array(states_cfg["scale_factors_state"], dtype=np.float64)  # Range of each state variable for normalization of random walk noise
        assert len(self.StateRange) == self.n_s, \
            "'states.scale_factors_state' must have the same length as 'states.names' in the YAML file."

        self.OutputRange = np.array([], dtype=np.float64)  # Build OutputRange from YAML measurements.scale_factors_measurement_all
        for output in self.measurements_list:
            assert output in self.all_measurements, \
                f"Invalid output '{output}' in 'measurements.available_measurements'. Must be one of 'measurements.all'."
            idx = self.all_measurements.index(output)
            self.OutputRange = np.append(self.OutputRange, self.scale_factors_meas_all[idx])
        
        # ---- Dropping measurements configuration ----
        deltaT_m_cfg = sensor_cfg.get("deltaT_m_multiples", [1] * self.m)
        self.deltaT_m_multiples = np.array(deltaT_m_cfg, dtype=int)
        assert len(self.deltaT_m_multiples) == self.m, \
            "'sensor.deltaT_m_multiples' must have the same length as 'measurements.available_measurements' in the YAML file."

         # ---- parameter drift ----
        param_cfg = cfg["parameters"]
        self.param_start_values = {}
        self.all_parameters = list(param_cfg["all"])
        for i, name in enumerate(self.all_parameters):
            assert name in self.variable_dict, \
                f"Parameter '{name}' specified in 'parameters.all' in the YAML file, not found in the xml file of FMU modelVariables."
            self.param_start_values[name] = sensor_cfg["parameters_true"][i]

        param_drifts_cfg = sensor_cfg["parameter_drifts"]
        assert len(param_drifts_cfg.keys()) == len(param_cfg["all"]), \
            "All parameters in 'parameters.all' must have a corresponding entry in 'sensor.parameter_drifts' in the YAML file " \
            "(Set sensor.parameter_drifts.enabled to false to disable drift for a parameter)."

        self.drift_config = {}
        for param in self.all_parameters:
            cfg_p = param_drifts_cfg.get(param, {})  # dict with keys: enabled, windows from YAML file 
            enabled = bool(cfg_p.get("enabled", False)) 
            windows = cfg_p.get("windows", [])   # list of dicts with keys: t_start, t_end, drift_final_factor from YAML file
            self.drift_config[param] = {"enabled": enabled, "windows": windows}

        # store drifting true parameters over time
        self.True_parameters = {param: np.array([self.param_start_values[param]], dtype=np.float64) for param in self.drift_config.keys()} # To store the "True" drifting parameters at all time-steps (now initialized with initial parameter values)

#       --------------- True-System Simulation variables -----------------
        self.X = np.zeros((self.n_s, self.iteration_steps), dtype=np.float64)   # True states matrix
        self.X[:, 0] = self.x0
        self.Y = np.zeros((self.m, self.iteration_steps - 1), dtype=np.float64) # True outputs matrix
        self.Y_noised = np.zeros_like(self.Y, dtype=np.float64)                 # Noised outputs matrix
        self.Y_mod = np.full(self.Y.shape, np.nan, dtype=np.float64)            # Dropped Noised outputs matrix


    def apply_parameter_drift(self, time_step:int) -> dict:
        """
        Compute drifting parameter values at a given time step.

        Returns a dict: {param_name: value_at_time_step}
        and appends the values into self.True_parameters[param].
        """
        drifted_parameters = {}
        for param, cfg_p in self.drift_config.items():
            enabled = cfg_p.get("enabled", False)
            windows = cfg_p.get("windows", [])

            base = self.param_start_values[param]
            latest_value = base
            drift_applied_flag = False

            if enabled and windows:
                # Apply windows in order; each window is a dict with keys like
                # t_start, t_end, drift_final_factor
                for window in windows:
                    t_start = int(window["t_start"])
                    t_end = int(window["t_end"])
                    final_factor = window.get("drift_final_factor", None)
                    
                    target = np.float64(final_factor) * base  # determine target value for this window

                    if time_step > t_end:
                        # window already finished: parameter has reached target
                        latest_value = target
                        continue
                    elif t_start <= time_step <= t_end:
                        # within this window: linearly interpolate from latest_value to target
                        if t_end > t_start:
                            interval = (time_step - t_start) / (t_end - t_start)
                        else:
                            interval = 1.0
                        new_value = latest_value * (1.0 - interval) + target * interval
                        latest_value = new_value
                        drift_applied_flag = True
                        break
                
            # if no drift applied or no enabled windows, keep latest_value
            drifted_parameters[param] = latest_value
            self.True_parameters[param] = np.append(self.True_parameters[param], latest_value)

        return drifted_parameters

    def emulate(self):
        """
        Emulate the "true" system using the FMU, including:
        - process noise random walk on the states,
        - measurement noise random walk on the outputs,
        - parameter drifts according to the sensor.parameter_drifts config in YAML file, and
        - measurement dropping according to sensor.deltaT_m_multiples config in YAML file.

        Returns:
        - X: True state trajectories (number of system states , iteration_steps)
        - Y: True outputs (number of system measurements , (iteration_steps - 1))
        - Y_noised: Noised outputs (same shape as Y)
        - Y_mod: Dropped-measurement outputs (same shape as Y, with NaNs for missing samples (set via sensor.deltaT_m_multiples config in YAML file))
        - True_parameters: dict of true parameters over time {name: np.ndarray} (includes drifted parameter values if drift was enabled in YAML file)
        """
        
        model_description = read_model_description(self.fmu_path) # Read the FMU-xml file (xxx.xml) to get the model description
        unzipdir = extract(self.fmu_path)                         # Extract the .fmu file to a temporary directory

        vr_map = {v.name: v.valueReference for v in model_description.modelVariables} # v is an object of each modelVariable in the FMU-xml file (States, Parameters, Inputs, Outputs)

        fmu = instantiate_fmu(unzipdir, model_description, fmi_type="ModelExchange")  # Instantiate the ModelExchange-FMU using the extracted directory and model description
        fmu.setupExperiment()

        # Initialize tunable parameters (True parameters for the Sensor measurements Emulation)
        fmu.enterInitializationMode()
        # No 'once-and-for-all' initialising parameters here, as they are not constant anymore but are set 
        # drifted at different time-steps during True-system emulation.
        fmu.exitInitializationMode()
        fmu.enterContinuousTimeMode()  # Enable state setting during simulation

        for k in range(1, self.iteration_steps):
            # set states at previous time-step
            for i, state_name in enumerate(self.state_names):
                fmu.setReal([vr_map[state_name]], [self.X[i, k-1]])

            # apply parameter drift at time step k-1
            current_parameters = self.apply_parameter_drift(k-1)
            for param_name, value in current_parameters.items():
                fmu.setReal([vr_map[param_name]], [value])
            
            # set inputs at previous time-step (row-order of u)
            u_prev = self.u[:, k-1]
            for val, name in zip(u_prev, self.input_names):
                fmu.setReal([vr_map[name]], [val])

            # --- Get computed derivatives from FMU using the set states and inputs ---
            dx = np.zeros(self.n_s, dtype=np.float64)
            fmu.getDerivatives(np.ctypeslib.as_ctypes(dx), self.n_s)  # dx must be passed as a double* pointer, which np.ctypeslib.as_ctypes() provides.
            derivatives = dx

            # --- Euler Integration ---
            self.X[:, k] = self.X[:, k-1] + derivatives * self.deltaT

            # --- add process noise ---
            self.X[:, k] += (self.q_true * self.StateRange * np.random.randn(self.n_s) * np.sqrt(self.deltaT))

            # --- Inject noised states back for output calculation ---
            u_curr = self.u[:, k]
            for val, name in zip(u_curr, self.input_names):
                fmu.setReal([vr_map[name]], [val])
            x_k_contig = np.ascontiguousarray(self.X[:, k], dtype=np.float64)   # FMU does not support sliced arrays, so we need to create a contiguous copy
            x_k_ctypes = np.ctypeslib.as_ctypes(x_k_contig)
            fmu.setContinuousStates(x_k_ctypes, self.n_s)  # sets the contiguous ctype arry of noised states and then triggers calculateValues() as defined in the FMU model.c file

            # --- Provide outputs based on self.measurements_list ---
            y_k = np.array([], dtype=np.float64)
            for output in self.measurements_list:
                assert output in vr_map, \
                    f"{output} specified in measurements_list does not match any FMU modelVariable name (case-sensitive) in the FMU-xml file."
                y_k = np.append(y_k, fmu.getReal([vr_map[output]]))
            self.Y[:, k-1] = y_k

            # add measurement noise random walk
            self.Y_noised[:, k-1] = (self.Y[:, k-1] + self.r_true * self.OutputRange * np.random.randn(self.m) * np.sqrt(self.deltaT))

        # --- Configure Dropping measurements based on deltaT_m_multiples from YAML file ---
        for p, step in enumerate(self.deltaT_m_multiples):
                retained_indices = range(0, self.Y_mod.shape[1], step)  # first measurement retained
                self.Y_mod[p, list(retained_indices)] = self.Y_noised[p, list(retained_indices)]

        # --- Clean up extracted FMU directory ---
        shutil.rmtree(unzipdir, ignore_errors=True)

        return self.X, self.Y, self.Y_noised, self.Y_mod, self.True_parameters