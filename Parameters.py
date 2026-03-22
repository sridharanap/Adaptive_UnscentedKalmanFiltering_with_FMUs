##################################################
# This class defines the parameters of one string of the battery
# The parameters are based on the battery data sheet and some assumptions
# The parameters are used in the battery model and the aging model
# this function scales all battery parameters , as long as a clear physical relations exist
##################################################### 

import numpy as np
from scipy.optimize import fsolve

class Parameters:
    def __init__(self):
        self.U0Nom = np.float64(679)
        # self.U0Nom = np.float64(650)
        self.dU0 = np.float64(1.20)
        self.UmaxInVolt = np.float64(787)
        self.UminInVolt = np.float64(595)

        # Current limit adjustment based on State of Charge (SOC)
        self.I_maxOfSOC = np.array([210, 210, 130, 70, 20, 0], dtype=np.float64)
        self.SOC_I_max = np.array([0.0, 85, 90, 96, 99, 100], dtype=np.float64)
        self.I_minOfSOC = np.array([0, -200, -272], dtype=np.float64)
        self.SOC_I_min = np.array([0.0, 10, 100.0], dtype=np.float64)

        # Temperature dependencies for current limits
        self.ImaxTemperatureDependency_TinCelsius = np.array([-10.15, 4.85, 25], dtype=np.float64)
        self.ImaxTemperatureDependency_factor = np.array([0.07, 0.3, 1], dtype=np.float64)

        # Temperature settings
        self.T_max = np.float64(80)
        self.T_min = np.float64(-10)
        self.T_amb = np.float64(22)
        self.dT_safety = np.float64(15)

        # Resistance calculations based on temperature
        self.Ri_1 = np.float64(0.22)
        self.T_1 = np.float64(10)
        self.Ri_2 = np.float64(0.162)
        self.T_2 = np.float64(25)
        self.Ri_3 = np.float64(0.136)
        self.T_3 = np.float64(40)

        # Solve for b_Ri
        self.Rx = (self.Ri_1 - self.Ri_2) / (self.Ri_1 - self.Ri_3)
        self.b_Ri = self.solve_b_Ri()

        # Calculate a_Ri and c_Ri using the solved b_Ri
        self.a_Ri = (self.Ri_1 - self.Ri_2) / (np.exp(-self.b_Ri * self.T_1) - np.exp(-self.b_Ri * self.T_2))
        self.c_Ri = self.Ri_1 - self.a_Ri * np.exp(-self.b_Ri * self.T_1)

        # Resistance factor based on SOC
        self.ResistanceOfSOCFactor_SOC = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90], dtype=np.float64)
        self.ResistanceOfSOCFactor_Factor = np.array([1.4, 1.1, 0.99, 0.97, 0.96, 0.95, 0.94, 0.93, 0.91], dtype=np.float64)

        # Heat capacity and dissipation
        self.Cap_heat = np.float64(500000)
        self.Cdiss_heat = np.float64(1.2e-04)
        self.C_diss_ratio = np.float64(10)

        # State of Charge (SOC) settings
        self.SOC0 = np.float64(50)
        self.SOCmin = np.float64(0)
        self.SOCmax = np.float64(100)

        # SOC minimum temperature dependency
        self.SoCminTemperatureDependency_TinCelsius = np.array([-25, -10, 0, 10, 25, 40], dtype=np.float64)
        self.SoCminTemperatureDependency_SOCadd = np.array([0.200, 0.1300, 0.100, 0.0600, 0, 0], dtype=np.float64)

        # Battery capacity and cost
        self.Cap_orig = np.float64(60)
        self.Cap0 = self.Cap_orig * np.float64(1)
        self.Cost = np.float64(0.00001)                      # unknown
        self.P_nom_provider = np.float64(25000000 / 260)

        # Aging parameters
        self.Aging_calendaric_lifetime1_atT1 = np.float64(20)
        self.Aging_calendaric_T1 = np.float64(25)
        self.Aging_calendaric_lifetime2_atT2 = np.float64(3)
        self.Aging_calendaric_T2 = np.float64(60)
        self.Aging_calendaric_SOC = np.array([0, 100], dtype=np.float64)
        self.Aging_calendaric_lifetime = np.array([20, 18], dtype=np.float64) * np.float64(1)
        self.Aging_calendaric_eol = np.float64(80)
        self.Aging_calendaric_T0 = np.float64(25)

        # Cyclic aging properties
        self.AgingCyclicCyclelifeAtTemperature1_T = np.float64(25)
        self.AgingCyclicCyclelifeAtTemperature1_Cycles = np.float64(6000)
        self.AgingCyclicCyclelifeAtTemperature2_T = np.float64(45)
        self.AgingCyclicCyclelifeAtTemperature2_Cycles = np.float64(3000)
        self.Aging_cyclic_DoD = np.array([20, 50, 100], dtype=np.float64)
        self.Aging_cyclic_lifetime = np.array([79000, 22000, 6000], dtype=np.float64)
        self.Aging_cyclic_T0 = np.float64(25)
        self.Aging_cyclic_eol = np.float64(80)
        self.Aging_cyclic_DoD_cutoff = np.float64(90)
        self.AgingCyclicCurrentDependency_I = np.array([-85, 68, 136], dtype=np.float64)
        self.AgingCyclicCurrentDependency_factor = np.array([1, 1, 1.5], dtype=np.float64)

        # End of life parameters
        self.AgingResistanceProportionalConstant = np.float64(0.9)
        self.endOfLifeCapacityInPercent = np.float64(80)

    def solve_b_Ri(self):
        """Solve for b_Ri using fsolve."""
        def equation(b):
            return self.Rx - (1 - np.exp(b * (self.T_1 - self.T_2))) / (1 - np.exp(b * (self.T_1 - self.T_3)))
        b_Ri_solution, = fsolve(equation, 0.0001)
        return b_Ri_solution