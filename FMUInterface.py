import shutil
import numpy as np
from fmpy import read_model_description, extract, instantiate_fmu
import scipy

class UKF_FMU_Interface:
    """
    The FMUInterface class is an intermediary between the FMU and the JointUKF algorithm.
    
    It handles the extraction and instantiation of the FMU, initializations of necessary inputs for the UKF (via the initialise() method), 
    scaling matrix computations (via compute_kscale() method) and provides methods for Process and Output Observer model transitions.
    """
    def __init__(self, fmu_path, flagScaleSystem, cfg):
        """
        Initializes the class.

        Parameters:
        - fmu_path: Path to the file containing the .fmu (string)
        - flagScaleSystem: Flag to decide whether to scale the system or not (1: Scale, 0: No scaling)
        - cfg: yaml file containing the entire co-simulation configuration
        """
        self.flagScale = flagScaleSystem       # Decides whether to scale the system or not (1: Scale, 0: No scaling)
        self.cfg = cfg

        # FMU EXTRACTION AND INSTANTIATION
        self.fmu_path = fmu_path
        self.model_description = read_model_description(fmu_path)
        self.unzip_dir = extract(fmu_path)
        self.fmu = instantiate_fmu(self.unzip_dir, self.model_description, fmi_type=cfg["fmu"]["model_type"])

        self.fmu.setupExperiment()
        self.fmu.enterInitializationMode()
        self.fmu.exitInitializationMode()
        self.fmu.enterContinuousTimeMode()

        self.variable_dict = {var.name: var for var in self.model_description.modelVariables} # extract and store all model variables from FMU-xml file in a dictionary.

        states_cfg = cfg["states"]
        self.state_names = states_cfg["names"]
        self.x_init_states = np.array(states_cfg["initial_values"], dtype=np.float64)         # initial states for the UKF set
        self.InitialEstErrorStates = np.array(states_cfg["initial_error"], dtype=np.float64)  # initial estimation error for the states (approximate deviations of the user-defined initial states x_init_states from the true initial states)
        assert self.x_init_states.shape == self.InitialEstErrorStates.shape, "'states.initial_error', 'states.initial_values' & 'states.names' must have the same shape in the yaml file."
        
        self.InitialEstErrorStates[self.InitialEstErrorStates == 0] = np.float64(0.01)
        self.n_s = len(self.x_init_states)                           # Number of system states
        self.q_states = np.array(states_cfg["process_noise_std"], dtype=np.float64)   # Assumed Process noise std. deviation for states
        assert self.q_states.shape == self.x_init_states.shape, "'states.process_noise_std' must have the same shape as 'states.initial_values' in the yaml file."

        # INPUTS CONFIGURATION
        inputs_cfg = cfg["inputs"]
        self.input_names = list(inputs_cfg.get("fmu_input_names", []))  # list of FMU input variable names (row-order of u)
        assert len(self.input_names) > 0, \
            "'inputs.fmu_input_names' must contain at least one input variable in the YAML file."
        for name in self.input_names:
            assert name in self.variable_dict, \
                f"Input variable '{name}' specified in YAML 'inputs.fmu_input_names' not found in FMU-xml model description file (case-sensitive match required)."

        param_cfg = cfg["parameters"]
        self.all_parameters = list(param_cfg["all"])  # all tunable parameters in the FMU (matched case-sensitively in yaml to ModelVariable names in FMU-xml file)
        mode = param_cfg.get("config_mode", "yaml")
        
        for name in self.all_parameters:
            assert name in self.variable_dict, f"Parameter '{name}' specified in YAML 'parameters.all' not found in FMU-xml model description file (must also ensure case-sensitive match)"
            assert hasattr(self.variable_dict[name], 'start') and self.variable_dict[name].start is not None, f"Parameter '{name}' in FMU-xml model description file does not have a start attribute."

        if mode == "yaml":
            self.estimated_parameters = list(param_cfg["estimated"])  # parameters that need to be estimated (set from all_parameters in yaml)
            self.params_init = np.array(param_cfg["initial_values"], dtype=np.float64)
            self.InitialEstErrorParameters = np.array(param_cfg["initial_error"], dtype=np.float64)
            self._q_parameters = np.array(param_cfg["process_noise_std"], dtype=np.float64)
            assert self._q_parameters.shape == self.params_init.shape, "'parameters.process_noise_std' must have the same shape as 'parameters.initial_values' in the yaml file."
            assert self.InitialEstErrorParameters.shape == self.params_init.shape, "'parameters.initial_error', 'parameters.initial_values' & 'parameters.estimated' must have the same shape in the yaml file."
        elif mode == "prompt":
            # Interactive configuration of parameters
            self._configure_parameters_via_prompt()
        else:
            raise ValueError(f"Unknown 'parameters.config_mode': '{mode}' in YAML.")
        
        self.InitialEstErrorParameters[self.InitialEstErrorParameters == 0] = np.float64(0.01)

        for name in self.estimated_parameters:
            assert name in self.variable_dict, f"Parameter '{name}' specified in YAML 'parameters.estimated' not found in FMU-xml model description file (must also ensure case-sensitive match)"
            assert hasattr(self.variable_dict[name], 'start') and self.variable_dict[name].start is not None, f"Parameter '{name}' does not have a start attribute."
            assert self.variable_dict[name].variability != "fixed", f"Parameter '{name}' has its variability='fixed' and cannot be estimated. Please set it to 'tunable' in modelDescription.xml."

        meas_cfg = cfg["measurements"]
        self.all_measurements = list(meas_cfg["all"])
        self.scale_factors_meas_all = np.array(meas_cfg["scale_factors_measurement_all"], dtype=np.float64)
        assert len(self.all_measurements) == len(self.scale_factors_meas_all), \
            "'measurements.scale_factors_measurement_all' must have the same length as 'measurements.all' in the YAML file."

        mode_meas = meas_cfg.get("config_mode", "yaml")

        if mode_meas == "yaml":
            # YAML mode
            self.measurements_list = list(meas_cfg["available_measurements"])  # List of measured Sensor signals from the system
            assert len(self.measurements_list) > 0, \
                "'measurements.available_measurements' must contain at least one measurement."
            self.r = np.array(meas_cfg["measurement_noise_std"], dtype=np.float64)  # Assumed Measurement noise std. deviation
            assert len(self.r) == len(self.measurements_list), \
                "'measurements.measurement_noise_std' must have the same length as 'measurements.available_measurements' in the YAML file."
        elif mode_meas == "prompt":
            # interactive measurement selection
            self._configure_measurements_via_prompt()
            assert len(self.measurements_list) > 0, \
                "At least one measurement must be selected in prompt mode."
        else:
            raise ValueError(f"Unknown 'measurements.config_mode': '{mode_meas}' in YAML.")

        self.m = len(self.measurements_list) # number of measurements / outputs in the measurement model
        
        self.OutputRange = np.array([], dtype=np.float64)  # Build OutputRange from YAML measurements.scale_factors_measurement_all
        for output in self.measurements_list:
            assert output in self.all_measurements, \
                f"Invalid output '{output}' in 'measurements.available_measurements'. Must be one of 'measurements.all'."
            idx = self.all_measurements.index(output)
            self.OutputRange = np.append(self.OutputRange, self.scale_factors_meas_all[idx])           
    
        self.k_scale = self.compute_kscale()
    
    def _configure_parameters_via_prompt(self):
        """
        Interactive configuration of estimated parameters via user prompts in real-time.
        """
        print("\n[PARAMETERS] Available FMU parameters:")
        for i, name in enumerate(self.all_parameters):
            print(f"[{i}] - {name}")

        while True:
            indices_str = input(
                "Enter the indices of parameters to initially estimate (comma-separated), "
                "or press Enter for none: "
            ).strip()
            if not indices_str:
                self.estimated_parameters = []
                self.params_init = np.array([], dtype=np.float64)
                self.InitialEstErrorParameters = np.array([], dtype=np.float64)
                self._q_parameters = np.array([], dtype=np.float64)
                return
            try:
                indices = [int(s.strip()) for s in indices_str.split(",")]
                self.estimated_parameters = [self.all_parameters[i] for i in indices]
                break
            except Exception as e:
                print(f"[ERROR] {e}. Please try again.")

        init_vals = []
        init_errs = []
        q_std = []
        for name in self.estimated_parameters:
            v0 = float(input(f"Enter nitial value for parameter '{name}': "))
            e0 = float(input(f"Enter initial uncertainty value for '{name}': "))
            q0 = float(input(f"Enter process noise standard deviation for '{name}': "))
            init_vals.append(v0)
            init_errs.append(e0)
            q_std.append(q0)

        self.params_init = np.array(init_vals, dtype=np.float64)
        self.InitialEstErrorParameters = np.array(init_errs, dtype=np.float64)
        self._q_parameters = np.array(q_std, dtype=np.float64)

    def _configure_measurements_via_prompt(self):
        """
        Interactive configuration of available measurements via user prompts in real-time.
        """
        print("\n[MEASUREMENTS] Available FMU outputs:")
        for i, name in enumerate(self.all_measurements):
            print(f"[{i}] - {name}")
            
        while True:
            indices_str = input(
                "Enter indices of outputs to use as measurements (comma-separated), "
                "must contain at least one index: "
            ).strip()
            if not indices_str:
                print("[ERROR] At least one measurement must be entered and provided.")
                continue
            try:
                indices = [int(s.strip()) for s in indices_str.split(",")]
                self.measurements_list = [self.all_measurements[i] for i in indices]
                break
            except Exception as e:
                print(f"[ERROR] {e}. Please try again.")

        r_list = []
        for name in self.measurements_list:
            r_val = float(input(f"Enter Measurement noise standard deviation for '{name}': "))
            r_list.append(r_val)
        self.r = np.array(r_list, dtype=np.float64)

    @property
    def n_p(self):
        return len(self.estimated_parameters)
    
    @property
    def n_kf(self):
        return self.n_s + self.n_p          # Total number of joint-states
    
    @property
    def q_parameters(self):
        return self._q_parameters           # Assumed Process noise std. deviation for parameters

    @property
    def q(self):
        return np.concatenate((self.q_states, self.q_parameters))
    
    def initialise(self):
        """
        Initialize the Joint-states and covariance matrices for the UKF.

        Returns:
        - x_ukf: Initial joint-state vector for the UKF (numpy.ndarray)
        - P0: Initial joint-state covariance matrix for the UKF (numpy.ndarray)
        - Q: Process noise covariance matrix for the UKF (numpy.ndarray)
        - R: Measurement noise covariance matrix for the UKF (numpy.ndarray)
        """
        InitialUncertainty = np.abs(np.concatenate((self.InitialEstErrorStates,self.InitialEstErrorParameters)))
        x_init = np.concatenate((self.x_init_states, self.params_init))
        x_ukf = np.dot(np.linalg.inv(self.k_scale).astype(np.float64), x_init)
        P0 = np.dot(np.diag(InitialUncertainty).astype(np.float64), np.linalg.inv(self.k_scale).astype(np.float64))**2
        Q = np.diag(self.q**2).astype(np.float64) # Q isn't scaled up here with the joint-state ranges as the UKF equations are already normalized.
        R = np.dot(np.diag(self.r**2).astype(np.float64),np.diag(self.OutputRange**2).astype(np.float64)) # R is scaled by range of output values because the measurements are predicted in a non-normalised manner.

        return x_ukf, P0, Q, R

    def compute_kscale(self):
        """"
        "Computes the scaling matrix for the UKF."
        The scaling matrix is computed based on the state and parameter ranges.

        Returns:
        - k_scale: Scaling matrix (numpy.ndarray)
        """
        if self.flagScale == 1:
            states_cfg = self.cfg["states"]
            params_cfg = self.cfg["parameters"]

            self.scale_factors_states = np.array(states_cfg["scale_factors_state"], dtype=np.float64)
            assert self.scale_factors_states.shape == self.x_init_states.shape

            self.scale_factors_params = np.array(params_cfg["scale_factors_parameter_all"], dtype=np.float64)
            assert len(self.scale_factors_params) == len(self.all_parameters), \
                "'parameters.scale_factors_parameter_all' must have the same length as 'parameters.all' in the YAML file." 

            if self.estimated_parameters:
                estimated_indices = [self.all_parameters.index(p) for p in self.estimated_parameters]
                scale_factors_params = self.scale_factors_params[estimated_indices]
            else:
                scale_factors_params = np.array([], dtype=np.float64)
            
            scale_factors = np.concatenate((self.scale_factors_states, scale_factors_params))
            k_scale = np.diag(scale_factors).astype(np.float64)
        else:
            k_scale = np.identity(self.n_kf).astype(np.float64)
            
        return k_scale
    
    def battery_dynamics_observer_states(self, xk_tilde, uk, deltaT):
        """
        Process-model transition function (propagates every sigma-point using the FMU)
        
        Arguments:
        - xk_tilde: Joint-state vector of a single sigma-point from the sigma-points matrix
        - uk: Input vector at current time step
        - deltaT: Step-size

        Returns:
        - xk_tilde: Updated joint-state vector after applying the transition function (Transformed sigma-point vector)
        """
        xk_orig = np.dot(self.k_scale, xk_tilde)  # Scale back the joint-states using the scaling matrix
        inv_k_scale = np.linalg.inv(self.k_scale)

        # --- Set the states, estimated parameters and input in the FMU ---
        for i, state_name in enumerate(self.state_names):
            self.fmu.setReal([self.variable_dict[state_name].valueReference], [xk_orig[i]]) # Set the states in the FMU (generic over self.state_names)

        uk_vec = np.atleast_1d(uk).astype(np.float64)
        assert uk_vec.shape[0] == len(self.input_names), \
            f"Expected {len(self.input_names)} inputs, got {uk_vec.shape[0]}."
        for val, name in zip(uk_vec, self.input_names):
            self.fmu.setReal([self.variable_dict[name].valueReference], [val])   # Set the inputs in the FMU (row-order of u)

        for j, name in enumerate(self.estimated_parameters):
            self.fmu.setReal([self.variable_dict[name].valueReference], [xk_orig[self.n_s+j]]) # Set the estimated parameters in the FMU
        
        # --- Get computed derivatives from FMU using the set joint-states and inputs ---
        dx = np.zeros(self.n_s, dtype=np.float64)
        self.fmu.getDerivatives(np.ctypeslib.as_ctypes(dx), self.n_s) # dx must be passed as a double* pointer, which np.ctypeslib.as_ctypes() provides.
        derivatives = dx

        # --- Euler Integration (generic for n_s states) ---
        dxk_tilde = inv_k_scale[:self.n_s, :self.n_s] @ (derivatives * deltaT)
        xk_tilde[:self.n_s] = xk_tilde[:self.n_s] + dxk_tilde

        if self.n_kf > self.n_s:
            for i in range(self.n_s, self.n_kf):
                xk_tilde[i] = xk_tilde[i] # Parameter estimations driven purely by process noise covariance Q

        return xk_tilde
    
    def battery_dynamics_observer_outputs(self, xk1_tilde, uk1, _):
        """
        Compute the Outputs Measurement-model transition function, propagating the "augmented" sigma-points using the FMU.

        Arguments:
        - xk1_tilde: Joint-state vector of a single sigma-point of the augmented sigma-point matrix
        - uk1: Input (Feedthrough) at current time step

        Returns:
        - y: Outputs vector after applying the measurement transition function
        """
        xk1_orig = np.dot(self.k_scale, xk1_tilde)   # Scale back the joint-states using the scaling matrix
        
        # --- Set the joint-states and the feedthru-input in the FMU ---
        uk1_vec = np.atleast_1d(uk1).astype(np.float64)
        assert uk1_vec.shape[0] == len(self.input_names), \
            f"Expected {len(self.input_names)} feedthrough inputs, got {uk1_vec.shape[0]}."
        for val, name in zip(uk1_vec, self.input_names):
            self.fmu.setReal([self.variable_dict[name].valueReference], [val])  # Set the feedthrough inputs in the FMU (row-order of u)

        for j, name in enumerate(self.estimated_parameters):
            self.fmu.setReal([self.variable_dict[name].valueReference], [xk1_orig[self.n_s + j]])

        # Calculate measurement model outputs (via calculateValues() in FMU model.c file)
        xk1_contig = np.ascontiguousarray(xk1_orig[:self.n_s], dtype=np.float64)  # FMU does not support sliced arrays, so we need to create a contiguous copy
        xk1_ctypes = np.ctypeslib.as_ctypes(xk1_contig)
        self.fmu.setContinuousStates(xk1_ctypes, self.n_s)  # setContinuousStates() first sets the states and then triggers calculateValues() (see FMU model.c file)

        # Provide outputs based on self.measurements_list
        y = np.array([], dtype=np.float64)
        for output in self.measurements_list:
            assert output in self.variable_dict, f"{output} specified in measurements_list does not match (also case-sensitively) any modelvariable name defined in the FMU-xml file."
            y = np.append(y, self.fmu.getReal([self.variable_dict[output].valueReference]))
        return y
    
    def terminate(self):
        """
        Clean up the temporary FMU extraction directory from disk and release resources.
        """
        shutil.rmtree(self.unzip_dir, ignore_errors=True)