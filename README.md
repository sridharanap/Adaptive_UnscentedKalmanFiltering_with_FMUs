UKF–FMU Framework
A Generic Unscented Kalman Filter Framework for FMI 2.0 Model-Exchange FMUs

# Overview
This project provides a generic, system-agnostic Unscented Kalman Filter (UKF) framework for:

- State estimation
- Parameter estimation
- Online recalibration
- Consistency monitoring (NIS-based)
- Sensor emulation (noise, drops, drift)
using FMI 2.0 ModelExchange FMUs.

The framework is not tied to any specific physical system. Any system can be used as long as the FMU satisfies the requirements listed below.

All system configuration is centralized in a single YAML file.

# Quick start
1. Place your FMU in the project (e.g. ./build/fmus/MyModel.fmu)
2. Create or edit a YAML config (e.g. UKF_examplesystem.yaml)
3. Set the YAML path in main.py
4. Provide an input function that returns a 2D NumPy array
5. Then run:
```python
python main.py
```

## Central Configuration: The YAML File
The YAML file is the single source of truth for:
- FMU metadata
- States
- Parameters
- Measurements
- Inputs
- UKF hyperparameters
- Recalibration behavior
- Sensor emulation behavior

## YAML Configuration – Detailed Guide
'!' denotes mandatory.

### Set Random Seed
```yaml
random:
  seed: 1
```

### Configure FMU
```yaml
fmu:
  path: "./build/fmus/SystemModel.fmu"
  model_type: "ModelExchange"
```
- path: ! the exact .\xxx.fmu FMU file path
- model_type: ! "ModelExchange" or "CoSimulation" (CoSimulation is currently not supported)

### Set simulation settings
```yaml
simulation:
  time_min: 100.0
  delta_T: 1.0
```
- time_min: ! total simulation time in minutes
- delta_T: ! sampling time in seconds

### Set inputs
```yaml
inputs:
  module: "input_simple"
  function: "input_simple"
  fmu_input_names: ["Input1"]
```
- module: ! .py python inputs module name on project root
- function: ! "name_of_inputs_function" inside inputs module - like def name_of_inputs_function(time_min, delta_T) -> np.ndarray
Must return a 2D array of shape (number of inputs, num of iteration steps). num of iteration steps can be determined by (num_steps = time_min * 60 / delta_T).
- fmu_input_names: ! list of input names in "row-order" of the returned 2D array (must match the ModelVariable names that have causality = "input" in the FMU-xml file case-sensitively), e.g., if there are two ModelVariable inputs named name="Input1" and name="Input2", then the yaml field is fmu_input_names: ["Input1", "Input2"]

### JOINTUKF - UKF Hyperparameters
```yaml
ukf:
  normalize_states: true
  plot_covariance: true
  alpha: 1.0e-4
  beta: 2.0
  kappa: 0.0
```
- normalize_states: ! UKF calculations take place internally with normalized state and parameter values.
- plot_covariance: ! allows plotting estimation covariance tube in the post-estimation plots.
- alpha, beta, kappa: ! UKF hyperparameters.

### JOINTUKF - UKF Recalibration & Consistency Monitoring
```yaml
ukf:
  recalibration_feature: true
  consistency_check_start: 700
  consistency_steps_retrigger: 400
  inconsistency_steps_retrigger: 100
```
- recalibration_feature: ! (true/false) Enables recalibration. Detects inconsistency via the Normalized innovation squared (NIS) and prompts user to recalibrate system parameters.
- consistency_check_start: ! iteration step to start NIS consistency checks (to avoid false positives during initial transient).
- consistency_steps_retrigger: ! number of consecutive consistent iteration steps to automatically stop recalibration and prompt user for optionally removing current estimated parameter(s).
- inconsistency_steps_retrigger: ! number of consecutive inconsistent iteration steps to re-activate recalibration.

These variables control the recalibration workflow -- Automatic detection of model inconsistency, option for user to interactively add/remove parameters.
If recalibration_feature = false, the UKF behaves as a standard UKF.

### JOINTUKF - UKF States Configuration
```yaml
states:
  names: ["state1", "state2"]
  initial_values: [25.0, 12.5]
  initial_error: [25.0, 12.5]
  process_noise_std: [1.0e-5, 1.0e-5]
  scale_factors_state: [100.0, 90.0]
```
- names: ! system states (must match the ModelVariable name in the FMU-xml file case-sensitively).
- initial_values: ! initial state value(s) x0 for the JointUKF.
- initial_error: ! initial state uncertainty value(s) P0 for the JointUKF.
- process_noise_std: ! assumed process noise for states (Q_states).
- scale_factors_state: ! scale factors for state normalization (division occurs by these scale_factors, i.e. x_normalized = x / scale_factor) (only used if normalize_states == true).

### JOINTUKF - UKF Parameters Configuration
```yaml
parameters:
  config_mode: "yaml"
  all: ["param1", "param2", "param3", "param4", "param5"]
  scale_factors_parmeter_all: [200.0, 300.0, 60.0, 5.0e5, 1.2e-04]
```
- config_mode: ! "yaml" or "prompt" (This is to configure the 'estimated' parameters array below -- "prompt": query user input during runtime || "yaml": use the values in the yaml file).
- all: ! all tunable parameters present in the FMU (must match the ModelVariable name in the FMU-xml file case-sensitively).
- scale_factors_parameter_all: ! scale factors for normalization of 'all' parameters (division occurs by these scale_factors, i.e. x_normalized = x / scale_factor) (only used if normalize_states == true).


YAML Mode (config_mode: "yaml")
```yaml
parameters:
  estimated: ["param2", "param3"]
  initial_values: [30.0, 118.5]
  initial_error: [20.0, 30.0]
  process_noise_std: [1.0e-6, 1.0e-6]
```
- estimated: parameters that need to be estimated (choose from "all" list in any order).
- initial_values: initial parameter value(s) x0 for the JointUKF (len(initial_values) != len(estimated)).
- initial_error: initial parameter values uncertainty(s) P0 for the JointUKF (len(initial_std) != len(estimated)).
- process_noise_std: small assumed process noise for all estimated parameters (Q_parameters). (len(process_noise_std) != len(estimated))

Prompt Mode (config_mode: "prompt")

### Measurements Configuration
```yaml
measurements:
  config_mode: "yaml"
  all: ["meas1", "meas2", "meas3", "meas4"]
  scale_factors_measurement_all: [192.0, 90.0, 90.0, 100.0]
```
- config_mode: ! "yaml" or "prompt" (This is to configure the 'available_measurements' array -- "prompt": query user input during runtime || "yaml": use the values in the yaml file).
- all: ! List of all possible Sensor signals from the system (must match the model variable names defined in the FMU-xml file).
- scale_factors_measurement_all: ! scale factors for all possible measurements (assumed measurement noise is scaled internally by these scale_factors. These are also used for adding noise as a random walk if sensor emulation of true system is to be opted).

YAML Mode (config_mode: "yaml")
```yaml
measurements:
  available_measurements: ["meas1", "meas3"]
  measurement_noise_std: [1.0e-6, 1.0e-5]
```
- available_measurements: List of available Sensor signals to the JointUKF (choose from "all" list in any order).
- measurement_noise_std: assumed measurement noise for available sensors (R_measurements) (len(measurement_noise_std) != len(names)).

### Sensor Emulation (Optional)
```yaml
sensor:
  sensor_emulation: true
  initial_states_true: [50.0, 25.0]
  process_noise_std_true: [1.0e-5, 1.0e-5]
  measurement_noise_std_true: [1.0e-6]
  parameters_true: [679.0, 1.2, 60.0, 500000.0, 1.2e-04]
```
- sensor_emulation: ! flag to enable/disable sensor emulation module

By disabling, you can use Real Sensor Data Instead of Emulation. Here is how:
1. In main(), under # Emulate battery system FMU model (with missing measurements), replace 'pass' with data variables X_true, Y_true, Y_noised, Y_dropped, parameters_true.
2. For each of these real sensor data variables, the required format for the datatype is as follows:
> All must be a NumPy float64 array.
> X_true must contain the true state values (without any noise) of shape (len(sensor.initial_states_true), num of iteration steps).
> Y_true must contain the true measured signal values (without any noise) of shape (len(ukf.measurements.available_measurements), num of iteration steps - 1).
> Y_dropped - noised measured signal values, with same shape as that of Y_true.
> parameters_true - dictionary of true values of all parameters across all iteration steps.  Dict keys must denote all parameter names as in (ukf.parameters.all) and the key values of each parameter must be an numpy ndarray of shape (num of iteration steps,).

If sensor_emulation is enabled,
- initial_states_true: ! initial true state value(s) x0 for the sensor emulation module (same order as ukf.states.names).
- process_noise_std_true: ! process noise as "random walk" for true states in the sensor emulation module.
- measurement_noise_std_true: ! measurement noise as "random walk" for emulated sensor signals (same order and size as measurements.available_measurements).
- parameters_true: ! true parameter values for the sensor emulation module (!! must be entered in the same order as parameters.all).

### Sensor Emulation - Configuring measurement drops
```yaml
sensor:
    deltaT_m_multiples: [1]
```
The measurement at initial-time is always available.
- deltaT_m_multiples: ! list of dropping integers for each measurement signal. Must equal len(measurements.available_measurements)
For example, deltaT_m_multiples = [k, j]  -> keep/retain every k-th sample of the first measurement and every j-th sample of the second measurement in ukf.measurements.available_measurements list.

### Sensor Emulation - Configuring parameter drifts (OPTIONAL but keys must be exact names in ukf.parameters.all)
```yaml
parameter_drifts:
    param1:
      enabled: true
      windows:
        - t_start: 2000
          t_end: 3000
          drift_final_factor: 1.05
        - t_start: 3500
          t_end: 4000
          drift_final_factor: 1.1
    
    param2:
        enabled: false
      windows:
        - t_start: 2000
          t_end: 3000
          drift_final_factor: 1.05
```
- enabled: flag to enable/disable drift for any given parameter.
- Under windows, the drift characteristics can be set. For example, to drift a parameter (with an initial value of 'example_val') between iteration steps 2000 and 2700 by 0.9 times its initial value (i.e., reduce 10% of 'example_val') -> t_start: 2000; t_end: 2700; drift_final_factor: 0.9.
- For all drift windows per parameter, the 'drift_final_factor' are relative to it's initial value 'example_val'.
- Therefore, many such drift windows can be set as needed, provided the shown .yaml format is followed correctly.  

## FMU Requirements
For this framework to work correctly, the FMU must satisfy all conditions below.

### FMI Standard
- FMI 2.0
- ModelExchange only.
- CoSimulation is currently not supported.

### States
- All states listed under states.names must be continuous states in the FMU.
- States must be settable via:
```c
setContinuousStates(...)
```
- State ordering in the FMU must be consistent with the order provided in YAML.

### Inputs
All inputs listed under inputs.fmu_input_names must:
- exist in the FMU
- be of type `Real`
- be writable via `setReal`
Inputs are applied in row-order of the input array `u`.

### Outputs / Measurements
All outputs listed under measurements.all must:
- exist as FMU `Real` variables.
- be readable via `getReal`
- Outputs must be algebraic outputs or computed during
```c
calculateValues()
```

### Parameters
All parameters listed under parameters.all must:
- exist in the FMU XML
- have a valid `start` value.
- not have `variability="fixed"`
- Parameters must be writable via
```c
setReal
```