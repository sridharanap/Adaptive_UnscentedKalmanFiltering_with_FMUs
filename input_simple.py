import numpy as np

def input_simple(simulationtime_min, deltaT):
    """
    Generate a simple battery charging current sequence.

    Input Parameters:
    - simulationtime_min: Total simulation time in minutes
    - deltaT: Sampling time

    Returns:
    - u: 2D Array of input currents for each time step
    """
    num_steps = round(simulationtime_min * 60 / deltaT)
    I_max = np.float64(210.0)     # Maximum charging current in A
    cap0 = np.float64(60.0)       # Battery capacity in Ah
    SOC_predicted = np.float64(50)
    effectOfUOnSOC = deltaT / np.float64(36) / cap0
    flag = 1
    I = I_max
    u = np.zeros((1, num_steps), dtype=np.float64)
    u[0, 0] = I

    for i in range(num_steps - 1):
        u[0, i + 1] = I
        SOC_predicted_old = SOC_predicted
        SOC_predicted += u[0, i] * effectOfUOnSOC

        if (SOC_predicted > 80) and (SOC_predicted_old < 80):
            I = np.float64(0.3) * I_max
            flag = 0

        if (SOC_predicted > 85) and (SOC_predicted_old < 85):
            I = -I_max

        if (SOC_predicted < 20) and (SOC_predicted_old > 20):
            I = np.float64(-0.3) * I_max

        if (SOC_predicted < 15) and (SOC_predicted_old > 15):
            flag = 1
            I = I_max

        if (SOC_predicted < 80) and (SOC_predicted_old < 80) and (flag == 1):
            I = I_max
    
    return u