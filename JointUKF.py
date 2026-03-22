import numpy as np
from scipy.linalg import cholesky, solve_triangular
from scipy.stats import chi2
from Recalibration import Recalibration

class JointUKF:
    def __init__(self, simulationtime_min, x_ukf, u, Y_dropped, P0, Q, R, deltaT, fmu_interface, cfg):
        self.cfg = cfg
        self.simulationtime_min = simulationtime_min
        self.x_state = x_ukf
        self.u = u
        self.Y = Y_dropped
        self.P = P0
        self.Q = Q
        self.R = R
        self.deltaT = deltaT
        self.fmu_interface = fmu_interface
        self.f_observer = fmu_interface.battery_dynamics_observer_states
        self.h_observer = fmu_interface.battery_dynamics_observer_outputs
        self.num_steps = round((self.simulationtime_min * 60) / deltaT)

        self.n_kf_full = fmu_interface.n_s + len(fmu_interface.all_parameters)  # Full joint-state dimension (state + parameters)
        self.X_estimated = np.full((self.n_kf_full, self.num_steps), np.nan, dtype=np.float64)  # To store joint-state estimates
        self.P_estimated_all = np.full((self.n_kf_full, self.n_kf_full, self.num_steps), np.nan, dtype=np.float64)  # To store covariance matrices

        # Assign correct initial joint-state x_ukf0 and covariance P0 into the full-size buffers
        self.X_estimated[:fmu_interface.n_s, 0] = x_ukf[:fmu_interface.n_s]  # Initial state vector for states
        for i, param in enumerate(fmu_interface.estimated_parameters):
            full_index = fmu_interface.n_s + fmu_interface.all_parameters.index(param)
            self.X_estimated[full_index, 0] = x_ukf[fmu_interface.n_s + i]  # Initial state vector for parameters
        for i in range(self.n_kf):
            for j in range(self.n_kf):
                if i < fmu_interface.n_s:
                    row = i
                else:
                    row = fmu_interface.n_s + fmu_interface.all_parameters.index(fmu_interface.estimated_parameters[i - fmu_interface.n_s])
                if j < fmu_interface.n_s:
                    col = j
                else:
                    col = fmu_interface.n_s + fmu_interface.all_parameters.index(fmu_interface.estimated_parameters[j - fmu_interface.n_s])
                self.P_estimated_all[row, col, 0] = P0[i, j]

        self.NIS_all = np.zeros(self.num_steps, dtype=np.float64)  # Normalized Innovation Squared (NIS) for all measurements
        self.NIS_all[0] = 0.0
        self.chi2_threshold_upper = np.zeros(self.num_steps, dtype=np.float64)  # Chi-squared threshold for the NIS test
        self.chi2_threshold_upper[0] = 0.0
        self.chi2_threshold_lower = np.zeros(self.num_steps, dtype=np.float64)  # Chi-squared threshold for the NIS test
        self.chi2_threshold_lower[0] = 0.0
        self.NIS_mean = np.zeros(self.num_steps, dtype=np.float64)  # Mean of time-averaged NIS
        self.NIS_mean[0] = 0.0
        self.confidence = 0.997  # Confidence level for the NIS test

        self.recalibrate_feature = bool(cfg["ukf"].get("recalibration_feature", False))  # Switch to enable/disable recalibration functionality (can only be set from yaml config)
        self.recalibration_triggered = False  # Flag to indicate if recalibration is triggered
        self.recalibration_active = False  # Flag to indicate if recalibration is active
        self.recalibration_consistent_counter = 0  # Counter for consistent NIS metric while recalibration
        self.recalibration_steps_counter = 0  # Counter for the number of steps since a recalibration trigger
        self.recalibration_remove = False  # Flag to prompt user of the option to remove calibrated parameters post consistency
        self.recalibration_dynamic = False  # Flag to indicate if recalibration is dynamic (allows adding/removing parameters)

        # === New feature toggle: UKF Causal-Covariance Estimation + back-out ===
        self.use_causal_covariance = False
        # Diagnostics vector: marks timesteps where back-out (revert update) occurred
        self.backout_flags = np.zeros(self.num_steps, dtype=bool)

        # ------------- SpikeGuard (abrupt-update detector) -------------
        # SpikeGuard is a heuristic to detect and suppress large, abrupt parameter jumps
        self.spikeguard_enable = False
        self.spikeguard_window = 20
        self.spikeguard_thresh = {
            "py_ratio": 50.0,     # trace(Pyy) jump
            "pxy_ratio": 100.0,   # ||Pxy(params)|| jump
            "k_ratio": 8.0,       # ||K(params)|| jump (or 4x if sign flip)
            "nu_ratio": 20.0      # |nu| jump
        }
        self.spikeguard_flags = np.zeros(self.num_steps, dtype=bool)

        # rolling history
        self._hist_py = []       # scalar: trace(Pyy)
        self._hist_pxy = []      # scalar: ||Pxy(params)||
        self._hist_k = []        # scalar: ||K(params)||
        self._hist_nu = []       # scalar: |nu|
        self._prev_kparam_vec = None  # for sign-flip test

        self.ukf_weights()  # Calculate weights for the sigma points
    
    @property
    def n_kf(self): # Number of states and parameters in the joint-state vector.
        """
        Update n_kf dynamically based on the updated state vector size
        """
        return len(self.x_state)
    
    def perform_estimation(self):
        """
        Perform the UKF estimation by iterating over the time steps.
        Supports real-time parameter recalibration based on NIS consistency tests.
        """

        recalibration_event = 0  # Initialize recalibration cycle counter
        for l in range(1, self.num_steps):
            if self.recalibration_remove and self.recalibrate_feature:
                recalibration_event += 1
                print(f"\n\n\n[INFO] RECALIBRATION EVENT: {recalibration_event} ...")
                self.fmu_interface, self = Recalibration.initiate_remove(self, l) # Option to remove/keep parameters from the currently estimated parameters post UKF Consistency
            if self.recalibration_triggered and self.recalibrate_feature:
                recalibration_event += 1
                print(f"\n\n\n[INFO] RECALIBRATION EVENT: {recalibration_event} ...")
                self.fmu_interface, self = Recalibration.initiate_add(self, l) # Option to add/keep parameters to be recalibrated post UKF Inconsistency
            if self.recalibration_dynamic and self.recalibrate_feature:
                recalibration_event += 1
                print(f"\n\n\n[INFO] RECALIBRATION EVENT: {recalibration_event} ...")
                self.fmu_interface, self = Recalibration.initiate_dynamic(self, l) # Option to add/remove parameters from the currently estimated parameters post persistent UKF Inconsistency (n iteration-steps) during any Recalibration Cycle

            uk = self.u[:, l-1]          # Input of the previous time step
            uk1 = self.u[:, l]           # Input of the current time step
            y = self.Y[:, l-1]           # Measurement at this time step
                
            # Perform the UKF update for this timestep
            self.x_state, self.P = self.ukf(
                self.f_observer, self.h_observer, self.x_state, uk, uk1, y, self.P, self.Q, self.R, self.deltaT, l
            )

            # Store the results into correct full-dimension locations
            self.X_estimated[:self.fmu_interface.n_s, l] = self.x_state[:self.fmu_interface.n_s]
            for i, param in enumerate(self.fmu_interface.estimated_parameters):
                full_idx = self.fmu_interface.n_s + self.fmu_interface.all_parameters.index(param)
                self.X_estimated[full_idx, l] = self.x_state[self.fmu_interface.n_s + i]

            for i in range(self.n_kf):
                for j in range(self.n_kf):
                    if i < self.fmu_interface.n_s:
                        row = i
                    else:
                        row = self.fmu_interface.n_s + self.fmu_interface.all_parameters.index(
                            self.fmu_interface.estimated_parameters[i - self.fmu_interface.n_s])
                    if j < self.fmu_interface.n_s:
                        col = j
                    else:
                        col = self.fmu_interface.n_s + self.fmu_interface.all_parameters.index(
                            self.fmu_interface.estimated_parameters[j - self.fmu_interface.n_s])
                    self.P_estimated_all[row, col, l] = self.P[i, j]

    def ukf(self, f_observer, h_observer, x_kf, uk, uk1, y, P, Q, R, deltaT, iteration_step):
        """
        UKF prediction and update step.
        Perform posteriori state and covariance estimation using the UKF algorithm.
        with optional UKF Causal-Covariance Estimation + back-out.
        """

        # State estimate/covariance time update
        xSigmaPts = self.sigmas(x_kf, P, self.lambda_)
        xMeanUT, P_apriori = self.ut_f(f_observer, xSigmaPts, uk, self.Wm, self.Wc, Q, deltaT, self.n_kf)
        
        if np.all(np.isnan(y)):  # Case handling when all measurements are missing
            return xMeanUT, P_apriori
        
        # Second sigma-transformation
        xSigmaPts2 = self.sigmas(xMeanUT, P_apriori, self.lambda_)
        X_diff2 = xSigmaPts2 - xMeanUT[:, np.newaxis]
        yMeanUT, Y = self.ut(h_observer, xSigmaPts2, uk1, self.Wm, deltaT, y)
        Y_diff = Y - yMeanUT[:, np.newaxis]
        
        # Handle missing measurements
        y_mod = y[~np.isnan(y)]
        nu = (y_mod - yMeanUT)  # innovation residual
        R_mod = R[~np.isnan(y), :][:, ~np.isnan(y)]

        Py = np.dot(Y_diff, np.dot(np.diag(self.Wc).astype(np.float64), Y_diff.T)) + R_mod
        Pxy = np.dot(X_diff2, np.dot(np.diag(self.Wc).astype(np.float64), Y_diff.T))
        K = np.dot(Pxy, np.linalg.inv(Py))  # Kalman gain matrix

        if self.recalibrate_feature is True:
            self.NIS_all[iteration_step] = (nu @ np.linalg.inv(Py) @ nu)
            dof = len(y_mod)  # Degrees of freedom for the NIS test
            window_size = 100 # window_size = 1 corresponds to no time-averaging
            start_idx = max(1, iteration_step - window_size + 1)
            nis_window = self.NIS_all[start_idx:iteration_step+1]
            K_dof = len(nis_window)
            self.NIS_mean[iteration_step] = np.mean(nis_window) # Time-averaged NIS for the current iteration step
            dof_total = K_dof * dof
            alpha = 1 - self.confidence
            self.chi2_threshold_upper[iteration_step] = chi2.ppf(1 - alpha / 2, dof_total) / K_dof # upper Chi-squared threshold for the time-averaged NIS test
            self.chi2_threshold_lower[iteration_step] = chi2.ppf(alpha / 2, dof_total) / K_dof     # lower Chi-squared threshold for the time-averaged NIS test  
        
            if iteration_step >= int(self.cfg["ukf"]["consistency_check_start"]): # Start NIS consistency checks after this iteration step to avoid false positives during initial transient
                if self.recalibration_active:
                    self.recalibration_steps_counter += 1 # count the number of steps since current recalibration trigger cycle
                    # During recalibration, continue posterior updates, but monitor consistency count to trigger recalibration deactivation    
                    if (0.95*self.chi2_threshold_lower[iteration_step]) <= self.NIS_mean[iteration_step] <= (1.05*self.chi2_threshold_upper[iteration_step]):
                        self.recalibration_consistent_counter += 1
                    else:
                        self.recalibration_consistent_counter = 0

                    if self.recalibration_consistent_counter == int(self.cfg["ukf"]["consistency_steps_retrigger"]):
                        """
                        option to manually remove one or more parameter(s) from the currently estimated parameters or
                        leave the estimations be! (ofcourse, no need to add more parameters to be recalibrated,
                        as we are already hit consistency!)
                        """
                        print("\n[INFO] UKF consistent for 400 continuous iteration-steps post Recalibration Trigger...")
                        self.recalibration_active = False
                        self.recalibration_remove = True
                        self.recalibration_steps_counter = 0
                        self.recalibration_consistent_counter = 0

                    if self.recalibration_steps_counter >= int(self.cfg["ukf"]["inconsistency_steps_retrigger"]) and self.recalibration_consistent_counter < (int(self.cfg["ukf"]["consistency_steps_retrigger"]) - 20):
                        """
                        This includes, apart from current Recalibration.initiate_add() feature
                        (that allows either 'add parameters to be recalibrated'
                        or 'add no parameter for recalibration'), the feature Recalibration.initiate_remove()
                        (that allows user to 'Remove parameters from the currently estimated parameters WHILE allowing
                        to either manually reset the value of the removed parameter(s) to users' choice (in case wrong parameter(s) was chosen for Recalibration) or continue to use the
                        current value of the parameter(s) in the FMU at the current time_step (in which case, the user is warned that the current FMU values of the "anomalous parameters" MIGHT be deviated from initial!)')
                
                        """
                        print(f"[INFO] UKF Inconsistent for {self.recalibration_steps_counter} continuous iteration-steps since Recalibration cycle start ...")
                        print(f"NOTE: \nCurrent iteration step of Inconsistency: [{iteration_step}]\nCount of consistent (100 Time-averaged NIS) recorded at current iteration-step: [{self.recalibration_consistent_counter}] \
                              \nThis information is to aid the User in deciding whether to add more parameters for recalibration or remove existing parameters!")
                        self.recalibration_dynamic = True  # Invoke dynamic recalibration from next step
                        

                # relaxing the consistency bounds by 10% to allow for some fluctuations
                elif (self.NIS_mean[iteration_step] < (0.9*self.chi2_threshold_lower[iteration_step]) or
                    self.NIS_mean[iteration_step] > (1.1*self.chi2_threshold_upper[iteration_step])):
                    self.recalibration_triggered = True
        
        # ---- SpikeGuard: detect abrupt, harmful update pattern ----
        freeze = False
        if self.spikeguard_enable:
            freeze = self._freeze_update(Py, Pxy, K, nu)
            self.spikeguard_flags[iteration_step] = freeze

        # Apply: freeze mean update for this step if flagged
        if freeze:
            nu = np.zeros_like(nu)

        # Joint-State and Covariance update
        x_kf_updated = xMeanUT + np.dot(K, nu)
        if freeze or not self.use_causal_covariance:
            # Regular covariance update
            P_updated = P_apriori - np.dot(K, np.dot(Py, K.T))

            # update histories for next step
            self._hist_py.append(float(np.trace(Py)))
            self._hist_k.append(float(np.linalg.norm(K[self.fmu_interface.n_s:, :].reshape(-1))) 
                                if self.n_kf > self.fmu_interface.n_s else 0.0)
            self._hist_pxy.append(float(np.linalg.norm(Pxy[self.fmu_interface.n_s:, :].reshape(-1))) 
                                if self.n_kf > self.fmu_interface.n_s else 0.0)
            self._hist_nu.append(float(np.linalg.norm(nu)))
            
            return x_kf_updated, P_updated
        
        # ----- Causal covariance estimation with back-out ----
        XSigmaPts3 = xSigmaPts2 + (np.dot(K, nu))[:, np.newaxis] # Shift sigma points by the same update (broadcast across columns)
        # Re-evaluate measurement sigma cloud at updated mean (still using P_apriori)
        yMeanUT2, Y_post = self.ut(h_observer, XSigmaPts3, uk1, self.Wm, deltaT, y)
        Y_diff2 = Y_post - yMeanUT2[:, np.newaxis]
        X_diff3 = XSigmaPts3 - x_kf_updated[:, np.newaxis]
        Py2 = np.dot(Y_diff2, np.dot(np.diag(self.Wc).astype(np.float64), Y_diff2.T)) + R_mod
        Pxy2 = np.dot(X_diff3, np.dot(np.diag(self.Wc).astype(np.float64), Y_diff2.T))
        # Recalculated Covariance
        P_causal = P_apriori + np.dot(K, np.dot(Py2, K.T)) - np.dot(Pxy2, K.T) - np.dot(K, Pxy2.T)
        # Back-out: if covariance worsens, revert to prior
        if np.trace(P_causal) > np.trace(P_apriori):
            self.backout_flags[iteration_step] = True

            # ---- histories (use pre-update Py/Pxy and nu) ----
            self._hist_py.append(float(np.trace(Py)))
            self._hist_k.append(float(np.linalg.norm(K[self.fmu_interface.n_s:, :].reshape(-1)))
                                if self.n_kf > self.fmu_interface.n_s else 0.0)
            self._hist_pxy.append(float(np.linalg.norm(Pxy[self.fmu_interface.n_s:, :].reshape(-1)))
                                if self.n_kf > self.fmu_interface.n_s else 0.0)
            self._hist_nu.append(float(np.linalg.norm(nu)))

            return xMeanUT, P_apriori
        else:
            self.backout_flags[iteration_step] = False

            # ---- histories (still use pre-update Py/Pxy and nu for baseline consistency) ----
            self._hist_py.append(float(np.trace(Py)))
            self._hist_k.append(float(np.linalg.norm(K[self.fmu_interface.n_s:, :].reshape(-1)))
                                if self.n_kf > self.fmu_interface.n_s else 0.0)
            self._hist_pxy.append(float(np.linalg.norm(Pxy[self.fmu_interface.n_s:, :].reshape(-1)))
                                if self.n_kf > self.fmu_interface.n_s else 0.0)
            self._hist_nu.append(float(np.linalg.norm(nu)))

            return x_kf_updated, P_causal

    def ukf_weights(self):
        """
        Calculate weight constants Wc & Wm for joint-state estimation.
        """
        alpha = np.float64(self.cfg["ukf"]["alpha"])
        beta = np.float64(self.cfg["ukf"]["beta"])
        if self.n_kf >= 3:
            ki = np.float64(self.cfg["ukf"]["kappa"])
        else:
            ki = np.float64(3 - self.n_kf)
        
        lambda_ = alpha**2 * np.float64(self.n_kf + ki) - np.float64(self.n_kf)
        c = np.float64(0.5) / (np.float64(self.n_kf) + lambda_)
        self.Wc = np.full(2*self.n_kf + 1, c, dtype=np.float64)
        self.Wm = np.full(2*self.n_kf + 1, c, dtype=np.float64)
        self.Wc[0] = (lambda_ / (np.float64(self.n_kf) + lambda_)) + (np.float64(1) - alpha**2 + beta)
        self.Wm[0] = lambda_ / (np.float64(self.n_kf) + lambda_)
        self.lambda_ = lambda_

    def sigmas(self, x, P, lambda_):
        """
        Compute sigma points around x.
        """
        P = np.atleast_2d(P).astype(np.float64)
        gamma = np.sqrt((lambda_ + np.float64(self.n_kf))).astype(np.float64)
        A = gamma * cholesky(P).T
        Y = np.tile(x[:, np.newaxis], (1, len(x)))
        sigmas = np.hstack((x[:, np.newaxis], Y + A, Y - A))

        return sigmas

    def ut_f(self, f, X, uk, Wm, Wc, Q, deltaT, n):
        """
        Unscented transformation through function f (dynamics).
        """
        L = X.shape[1]  # Number of sigma points
        x_estimate = np.zeros(n, dtype=np.float64)
        X_after = np.zeros((n, L), dtype=np.float64)

        for k in range(L):
            X_after[:, k] = f(X[:, k], uk, deltaT)
            x_estimate += Wm[k] * X_after[:, k]

        X_diff = X_after - x_estimate[:, np.newaxis]
        P_apriori = np.dot(X_diff, np.dot(np.diag(Wc).astype(np.float64), X_diff.T)) + Q

        XD_norm = np.linalg.norm(X_diff)
        if XD_norm > 50:
            print('Numerical error in UKF', 'Norm:', XD_norm)
            return x_estimate, P_apriori

        return x_estimate, P_apriori

    def ut(self, h, X, uk1, Wm, deltaT, y):
        """
        Unscented transformation through function h (measurements).
        """
        L = X.shape[1]
        m_hat = np.sum(~np.isnan(y))
        Y = np.zeros((m_hat, L), dtype=np.float64)
        y_estimate = np.zeros(m_hat, dtype=np.float64)
        
        for k in range(L):
            y_hat = h(X[:, k], uk1, deltaT)
            Y[:, k] = y_hat[~np.isnan(y)]
            y_estimate += Wm[k] * Y[:, k]

        return y_estimate, Y

    def get_results(self):
        """
        Return the results of the UKF estimation process.
        """
        return self.X_estimated, self.P_estimated_all
    
    def _median_or(self, arr, fallback):
        """
        Gives a stable “baseline” value (over the specified window), so one sudden spike doesnt inflate the reference.
        """
        return (np.median(arr[-self.spikeguard_window:]) if len(arr) else fallback)

    def _freeze_update(self, Py, Pxy, K, nu):
        # use trace(Py); focus on parameter rows for Pxy, K.
        eps = 1e-15
        py_scalar = float(np.trace(Py)) # Sum of diagonals (UKF calculated total measurement model uncertainty)
        n_s = self.fmu_interface.n_s

        # extract only parameter-related rows
        kparam_vec = K[n_s:, :].reshape(-1) # flatten to 1D (n,) vector
        pxy_param_vec = Pxy[n_s:, :].reshape(-1)
        kparam_norm = float(np.linalg.norm(kparam_vec)) # length/magnitude (the overall size) of the parameter-gain vector.
        pxy_param_norm = float(np.linalg.norm(pxy_param_vec)) # length/magnitude (the overall size) of the parameter cross-covariance vector.
        nu_abs = float(np.linalg.norm(nu))

        # median baselines
        med_py  = self._median_or(self._hist_py,  py_scalar)
        med_k   = self._median_or(self._hist_k,   max(kparam_norm, eps))
        med_pxy = self._median_or(self._hist_pxy, max(pxy_param_norm, eps))
        med_nu  = self._median_or(self._hist_nu,  max(nu_abs, eps))

        # ratios
        r_py  = py_scalar      / max(med_py,  eps) # 'eps' - avoid div-by-zero
        r_k   = kparam_norm    / max(med_k,   eps)
        r_pxy = pxy_param_norm / max(med_pxy, eps)
        r_nu  = nu_abs         / max(med_nu,  eps)

        # sign flip test for parameter gain vector
        sign_flip = False
        if self._prev_kparam_vec is not None and self._prev_kparam_vec.size == kparam_vec.size:
            sign_flip = (np.dot(kparam_vec, self._prev_kparam_vec) < 0.0)
        self._prev_kparam_vec = kparam_vec.copy()

        # decision: need at least 2 triggers
        trig = 0
        if r_py  > self.spikeguard_thresh["py_ratio"]:  trig += 1
        if r_pxy > self.spikeguard_thresh["pxy_ratio"]: trig += 1
        if r_k   > self.spikeguard_thresh["k_ratio"] or (sign_flip and r_k > 4.0): trig += 1
        if r_nu  > self.spikeguard_thresh["nu_ratio"]: trig += 1
        return trig >= 2
