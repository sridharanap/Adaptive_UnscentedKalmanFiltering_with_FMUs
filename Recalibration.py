import numpy as np

# Simple Prototype of the UKF Recalibration feature
class Recalibration:
    @staticmethod
    def initiate_add(current_ukf, iteration_step): # 'current_ukf' is an object of the current JointUKF class
                                                   # 'iteration_step' is the next time-step of recalibration triggered time-step
        """
        Prompt user for parameters to recalibrate and their initial uncertainties.
        Updates the FMU interface and the UKF object.
        """
        print(f"[INFO] INCONSISTENCY TRIGGER at iteration step {iteration_step-1}")
        print("\nEstimated model inconsistency detected via 100-Time-averaged NIS test ...\n[INFO] Option to add parameters to be recalibrated ...")


        # Step 1: Get tunable parameters (Exclude already estimated parameters from selection list)
        current_fmu_interface = current_ukf.fmu_interface # current BatteryFMUInterface object
        Recalibration.print_current_fmu_parameters(current_fmu_interface) # Print current values of all parameters in the FMU, to aid user
        already_estimated = set(current_fmu_interface.estimated_parameters)
        available_for_recalibration = [p for p in current_fmu_interface.all_parameters if p not in already_estimated]
        if not available_for_recalibration:
            print("\nNo parameters available for recalibration. Continuing with existing estimator!")
            current_ukf.recalibration_active = True
            current_ukf.recalibration_consistent_counter = 0
            current_ukf.recalibration_steps_counter = 0
            current_ukf.recalibration_triggered = False
            return current_ukf.fmu_interface, current_ukf
        print(f"Please select parameters to recalibrate from iteration-step {iteration_step} onwards ...")
        print("\nList of Parameters available for recalibration:")
        for i, name in enumerate(available_for_recalibration):
            print(f"[{i}] - {name}") # Print all available parameters with indices

        while True: # Input validation Loop
            # Only continues if the input is successfully parsed and indices are valid.
            indices = input("Enter indices of corresponding parameter(s) to recalibrate (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to skip adding):").strip() # Indices can be entered by user in any order 
            if not indices:
                print("[INFO] User chose not to recalibrate any parameters. Continuing with existing estimator.")
                current_ukf.recalibration_active = True
                current_ukf.recalibration_consistent_counter = 0
                current_ukf.recalibration_steps_counter = 0
                current_ukf.recalibration_triggered = False # it is True only at the time-step of Recalibration trigger
                return current_ukf.fmu_interface, current_ukf  # return existing UKF unchanged
            
            # try-except block to handle Invalid input
            try:
                selected_idx = [int(idx.strip()) for idx in indices.split(',')] # Make idx Type-castable
                # Validate: all indices are in valid range
                if any((i < 0 or i >= len(available_for_recalibration)) for i in selected_idx):
                    raise ValueError("Index out of range.")
                selected_params = [available_for_recalibration[i] for i in selected_idx]  # list of parameters to be recalibrated (list of strings)
                break  # Exit loop if input is valid and in-range
            except Exception as e: # Enter input again change
                print(f"[ERROR] Invalid input: {e}. Please enter valid indices (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to skip adding)")

        # Prompt for initial uncertainties for the selected parameters
        uncertainties = []
        for name in selected_params:
            val = float(input(f"Enter initial uncertainty for parameter '{name}': "))
            uncertainties.append(val)                                # list of uncertainties of the selected parameters

        # Step 2: Modify FMUInterface to reflect selected parameters and corresponding uncertainties (is then passed to a new recursive JointUKF object)
        Recalibration._update_fmu_interface_add(current_fmu_interface, selected_params, uncertainties)

        # Step 3: Modify UKF instance with resized state
        return Recalibration._initialize_updated_ukf_add(current_ukf, current_fmu_interface)



    @staticmethod
    def initiate_remove(current_ukf, iteration_step):
        """
        Prompt user to remove parameters after consistency is reached.
        Returns updated FMUInterface and JointUKF instance.
        """
        print(f"[INFO] CONSISTENCY REACHED at iteration step {iteration_step-1}")
        print(f"\n[INFO] Option to remove parameters from the currently estimated parameters from iteration step {iteration_step} onwards ...")

        # Step 1: Get Estimated parameters
        current_fmu_interface = current_ukf.fmu_interface # current BatteryFMUInterface object
        Recalibration.print_current_fmu_parameters(current_fmu_interface) # Print current values of all parameters in the FMU, to aid user
        if not current_fmu_interface.estimated_parameters:
            print("No parameters currently estimated, to be able to be removed. Continuing with existing estimator!")
            current_ukf.recalibration_remove = False
            return current_fmu_interface, current_ukf  # return existing UKF unchanged

        print("\nList of currently estimated parameters:")
        for i, name in enumerate(current_fmu_interface.estimated_parameters): # Note that parameters in estimated_parameters may be in any order
            print(f"[{i}] - {name}")
        
        while True: # Input validation Loop
            # Only continues to removal if the input is successfully parsed and indices are valid.
            indices = input("Enter indices of corresponding parameter(s) to remove (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to keep all):").strip() # Indices can be entered by user in any order
            if not indices:
                print("[INFO] User chose not to remove any parameters. Continuing with existing estimator.")
                current_ukf.recalibration_remove = False
                return current_fmu_interface, current_ukf  # return existing UKF unchanged

            # try-except block to handle Invalid input
            try:
                selected_idx = [int(idx.strip()) for idx in indices.split(',')]  # Make idx Type-castable
                # Validate: all indices are in valid range
                if any((i < 0 or i >= len(current_fmu_interface.estimated_parameters)) for i in selected_idx):
                    raise ValueError("Index out of range.")
                selected_params = [current_fmu_interface.estimated_parameters[i] for i in selected_idx]  # list of parameters to be removed (list of strings)
                break  # Exit loop if input is valid and in-range
            except Exception as e:
                print(f"[ERROR] Invalid input: {e}. Please enter valid indices (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to keep all)")
        
        # Step 2: Modify FMUInterface to reflect removed parameters
        old_params = current_fmu_interface.estimated_parameters.copy()
        Recalibration._update_fmu_interface_remove(current_fmu_interface, selected_params)

        # Step 3: Modify UKF instance with resized state
        return Recalibration._initialize_updated_ukf_remove(current_ukf, current_fmu_interface, old_params)


    @staticmethod
    def initiate_dynamic(current_ukf, iteration_step):
        """
        Prompt user to add or remove estimated parameters.
        For removals, user can choose to reset FMU value or keep latest value.
        Returns updated FMUInterface and UKF.
        """
        print(f"[INFO] PERSISTENT INCONSISTENCY TRIGGER at iteration step {iteration_step-1}")
        print(f"In the following, you can Add/Remove/Keep parameters, in the currently estimated parameters from iteration step {iteration_step} onwards ...")
        current_fmu_interface = current_ukf.fmu_interface
        Recalibration.print_current_fmu_parameters(current_fmu_interface) # Print current values of all parameters in the FMU, to aid user
        # ----- ADD PARAMETERS -----
        # As in initiate_add: prompt to add new parameters
        already_estimated = set(current_fmu_interface.estimated_parameters)
        available_for_recalibration = [p for p in current_fmu_interface.all_parameters if p not in already_estimated]
        add_params, uncertainties = [], []
        if available_for_recalibration:
            print("\nList of Parameters available for recalibration addition:")
            for i, name in enumerate(available_for_recalibration):
                print(f"[{i}] - {name}")

            while True:  # Input validation Loop
                indices_add = input("If you would like to add any parameter(s), (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to skip adding)").strip()
                if not indices_add:
                    break
                try:
                    selected_idx_add = [int(idx.strip()) for idx in indices_add.split(',')]
                    if any((i < 0 or i >= len(available_for_recalibration)) for i in selected_idx_add):
                        raise ValueError("Index out of range.")
                    add_params = [available_for_recalibration[i] for i in selected_idx_add]
                    break
                except Exception as e:
                    print(f"[ERROR] Invalid input: {e}. Please enter valid indices (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to skip adding)")
            
            for name in add_params:
                val = float(input(f"Enter initial uncertainty for parameter '{name}': "))
                uncertainties.append(val)
        else:
            print("No parameters available for Recalibration Addition. Jumping to parameter Removal prompt ...")
        
        # ----- REMOVE PARAMETERS -----
        rem_params = []
        reset_map = {}  # Map from param name to value or None (None means keep FMU value)
        if current_fmu_interface.estimated_parameters:
            print("\nList of currently estimated parameters:")
            for i, name in enumerate(current_fmu_interface.estimated_parameters):
                print(f"[{i}] - {name}")
            while True:  # Input validation Loop
                indices_rem = input("If you would like to remove any parameter(s), " \
                    "enter their indices (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to keep all)").strip()
                if not indices_rem:
                    break
                try:
                    selected_idx_remove = [int(idx.strip()) for idx in indices_rem.split(',')]
                    if any((i < 0 or i >= len(current_fmu_interface.estimated_parameters)) for i in selected_idx_remove):
                        raise ValueError("Index out of range.")
                    rem_params = [current_fmu_interface.estimated_parameters[i] for i in selected_idx_remove]
                    break
                except Exception as e:
                    print(f"[ERROR] Invalid input: {e}. Please enter valid indices (In any index order | comma-separated if multiple (Ex. - num1,num2,etc.) | Or press Enter to keep all)")
            
            for name in rem_params: # For each to-be-removed param, ask for reset
                while True:
                    response = input(f"\nDo you want to reset the value of parameter '{name}' to a specific value in the FMU after removal? (Enter y/n):").strip().lower()
                    if response == 'y':
                        while True:
                            try:
                                new_val = float(input(f"Enter reset value for '{name}': "))
                                reset_map[name] = new_val
                                break
                            except Exception:
                                print("[ERROR] Invalid value. Please enter a valid numeric value!")
                        break
                    elif response == 'n':
                        reset_map[name] = None
                        break
                    else:
                        print("Please enter only 'y' or 'n'.")

        # ---- Copy current estimated parameters in FMUInterface for later use ----
        old_params = current_fmu_interface.estimated_parameters.copy()  # Copy current estimated parameters for later use in _initialize_updated_ukf_remove
        
        # ---- APPLY ADDITIONS ----
        if add_params:
            Recalibration._update_fmu_interface_add(current_fmu_interface, add_params, uncertainties)
            current_fmu_interface, current_ukf = Recalibration._initialize_updated_ukf_add(current_ukf, current_fmu_interface)
        
        # ---- APPLY REMOVALS ----
        if rem_params:
            Recalibration._update_fmu_interface_remove(current_fmu_interface, rem_params)
            current_fmu_interface, current_ukf = Recalibration._initialize_updated_ukf_remove(current_ukf, current_fmu_interface, old_params)

            # For each removed param: reset FMU value if requested
            vr_dict = current_fmu_interface.variable_dict
            for name in rem_params:
                if reset_map[name] is not None:
                    vref = vr_dict[name].valueReference
                    current_fmu_interface.fmu.setReal([vref], [reset_map[name]])
                    print(f"[INFO] Parameter '{name}' reset to {reset_map[name]} in FMU!")

        # Final state
        current_ukf.recalibration_dynamic = False
        current_ukf.recalibration_active = True
        current_ukf.recalibration_remove = False
        current_ukf.recalibration_consistent_counter = 0
        current_ukf.recalibration_steps_counter = 0

        return current_fmu_interface, current_ukf



    @staticmethod
    def _update_fmu_interface_add(fmu_interface, selected_params, uncertainties):
        fmu_interface.estimated_parameters.extend(selected_params)  # Append to list of parameters to be estimated in the FMUInterface 
        
        param_vrefs = [fmu_interface.variable_dict[name].valueReference for name in selected_params]
        current_vals = fmu_interface.fmu.getReal(param_vrefs) # returns a list of current values of the selected parameters from the FMU at the current time_step
        fmu_interface.params_init = np.concatenate((fmu_interface.params_init, np.array(current_vals, dtype=np.float64)))        
        
        fmu_interface.k_scale = fmu_interface.compute_kscale() # Recompute scaling matrix after new params addition
        fmu_interface.InitialEstErrorParameters = np.concatenate(
            (fmu_interface.InitialEstErrorParameters, np.array(uncertainties, dtype=np.float64))
        )
        q_new = np.full(len(selected_params), np.float64(1.0e-4))  # Hyper-parameter for optimal Recalibration - hiked parameter process noise std. deviation for new parameters.
        fmu_interface._q_parameters = np.concatenate((fmu_interface._q_parameters, q_new)) # Update parameter process noise std. deviation array


    @staticmethod
    def _update_fmu_interface_remove(fmu_interface, selected_params):
        for name in selected_params:
            idx = fmu_interface.estimated_parameters.index(name)  # Get index of the parameter to be removed
            fmu_interface.estimated_parameters.pop(idx)  # Remove from estimated parameters list
            fmu_interface.params_init = np.delete(fmu_interface.params_init, idx)
            fmu_interface.InitialEstErrorParameters = np.delete(fmu_interface.InitialEstErrorParameters, idx)
            fmu_interface._q_parameters = np.delete(fmu_interface._q_parameters, idx)
        
        fmu_interface.k_scale = fmu_interface.compute_kscale()

    

    @staticmethod
    def _initialize_updated_ukf_add(ukf_obj, fmu_interface):
        """
        Modify the existing UKF object with extended joint-state vector and updated arrays.
        """

        # Step 1: Combine previous joint-states with newly added 'to-be-recalibrated' parameters
        x_existing = ukf_obj.x_state.copy()
        num_new = fmu_interface.n_kf - ukf_obj.n_kf
        k_scale_new = fmu_interface.k_scale[-num_new:, -num_new:] # Extract bottom-right block of k_scale
        k_scale_new_inv = np.linalg.inv(k_scale_new).astype(np.float64)  # Invert the sliced block
        param_vals_new = fmu_interface.params_init[-num_new:]  # Extract new parameter values
        x_new = np.dot(k_scale_new_inv, param_vals_new)
        x_ukf = np.concatenate((x_existing, x_new))

        # Step 2: Extend prior P with new block-diagonal uncertainty
        P_existing = ukf_obj.P.copy()
        P_new = np.zeros((fmu_interface.n_kf, fmu_interface.n_kf), dtype=np.float64)
        P_new[:ukf_obj.n_kf, :ukf_obj.n_kf] = P_existing
        uncertainty_new = fmu_interface.InitialEstErrorParameters[-num_new:]
        P_block = np.dot(np.diag(uncertainty_new).astype(np.float64), k_scale_new_inv) ** 2
        for i in range(num_new):
            for j in range(num_new):
                P_new[ukf_obj.n_kf + i, ukf_obj.n_kf + j] = P_block[i, j]

        # Step 3: Q update (R remains same)
        Q = np.diag(fmu_interface.q**2).astype(np.float64)
        
        # Step 4: Modify existing UKF instance
        ukf_obj.x_state = x_ukf
        ukf_obj.P = P_new
        ukf_obj.Q = Q
        ukf_obj.recalibration_active = True
        ukf_obj.recalibration_triggered = False # it is True only at the time-step of Recalibration trigger
        ukf_obj.recalibration_consistent_counter = 0
        ukf_obj.recalibration_steps_counter = 0
        ukf_obj.ukf_weights()  # Recalculate UKF weights based on the new state vector size

        return fmu_interface, ukf_obj
    


    @staticmethod
    def _initialize_updated_ukf_remove(ukf_obj, fmu_interface, old_params):
        """
        Modify the existing UKF object with reduced joint-state vector and updated arrays.
        """
        param_indices = [old_params.index(p) for p in fmu_interface.estimated_parameters]
        keep_indices = list(range(fmu_interface.n_s)) + [fmu_interface.n_s + idx for idx in param_indices]

        x_new = ukf_obj.x_state[keep_indices]  # Keep only the states and parameters that are still estimated
        P_new = ukf_obj.P[np.ix_(keep_indices, keep_indices)]

        ukf_obj.x_state = x_new
        ukf_obj.P = P_new
        ukf_obj.Q = np.diag(fmu_interface.q**2).astype(np.float64)
        ukf_obj.recalibration_active = False
        ukf_obj.recalibration_remove = False
        ukf_obj.recalibration_consistent_counter = 0
        ukf_obj.recalibration_steps_counter = 0
        ukf_obj.ukf_weights()

        return fmu_interface, ukf_obj
    
    @staticmethod
    def print_current_fmu_parameters(fmu_interface):
        """
        Prints the current value of all parameters (from all_parameters) in the FMU,
        to aid user in knowing the current values of parameters during the start 
        of any Recalibration cycle.
        """
        param_names = fmu_interface.all_parameters
        vrefs = [fmu_interface.variable_dict[name].valueReference for name in param_names]
        values = fmu_interface.fmu.getReal(vrefs)
        print("\n[INFO] List of all Parameter in the FMU:")
        print("-" * 45)
        for name, val in zip(param_names, values):
            print(f"{name:20s}: {val: .6g}")
        print("-" * 45)