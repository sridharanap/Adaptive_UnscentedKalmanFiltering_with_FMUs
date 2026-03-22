#include "model.h"
#include "config.h"
#include <math.h>

void setStartValues(ModelInstance *comp) {
    // Battery States
    M(SOC) = 0.0;       // Initial State of Charge (SOC)
    M(Temp) = 0.0;      // Initial temperature (T)

    // // Define (Temperature-Resistance) sample experimental values
    // double Ri_1 = 0.22;
    // double T_1 = 10.0;
    // double Ri_2 = 0.162;
    // double T_2 = 25.0;
    // double Ri_3 = 0.136;
    // double T_3 = 40.0;

    // // Solve for b_Ri
    // double Rx = (Ri_1 - Ri_2) / (Ri_1 - Ri_3);
    // double b_Ri = 0.0;
    // {
    //     double tolerance = 1e-9;
    //     double guess = 0.0001;
    //     int max_iter = 10000;
    //     for (int i = 0; i < max_iter; i++)
    //     {
    //         double f = Rx - (1 - exp(guess * (T_1 - T_2))) / (1 - exp(guess * (T_1 - T_3)));
    //         double df = ((exp(guess * (T_1 - T_2)) * (T_1 - T_2)) / (1 - exp(guess * (T_1 - T_3)))) - ((1 - exp(guess * (T_1 - T_2))) * exp(guess * (T_1 - T_3)) * (T_1 - T_3)) / pow((1 - exp(guess * (T_1 - T_3))), 2);
    //         double delta = -f / df;
    //         guess += delta;
    //         if (fabs(delta) < tolerance)
    //         {
    //             b_Ri = guess;
    //             break;
    //         }
    //     }
    // }

    // M(b_Ri) = b_Ri; // Parameter for temperature effect on resistance

    // // Calculate a_Ri and c_Ri
    // double a_Ri = (Ri_1 - Ri_2) / (exp(-b_Ri * T_1) - exp(-b_Ri * T_2));
    // M(a_Ri) = a_Ri; // Parameter for internal resistance
    // double c_Ri = Ri_1 - a_Ri * exp(-b_Ri * T_1);
    // M(c_Ri) = c_Ri; // Base internal resistance

    M(I) = 0.0;          // Input current (Ampere)

    // // Known Parameters
    // M(a_Ri) = 0.179477126196722;
    // M(b_Ri) = 0.053489763689233;
    // M(c_Ri) = 0.114874998532036;

    // Known Parameters (fsolve python values)
    M(a_Ri) = 0.17947712574688843;
    M(b_Ri) = 0.053489764834995665;
    M(c_Ri) = 0.11487499999999978;

    // Parameters to be externally set
    M(U0Nom) = 1018.5;      // Nominal voltage (V)
    // M(U0Nom) = 679;      // Nominal voltage (V)
    // M(dU0) = 1.8;        // Voltage change per SOC unit (V/Ah)
    M(dU0) = 1.2;        // Voltage change per SOC unit (V/Ah)
    M(Cap0) = 90.0;       // Nominal capacity (Ah)
    // M(Cap0) = 60.0;       // Nominal capacity (Ah)
    M(Cap_heat) = 750000.0;   // Heat capacity constant (J/K)
    // M(Cap_heat) = 500000.0;   // Heat capacity constant (J/K)
    M(Cdiss_heat) = 0.00018; // Heat dissipation constant (J/K)
    // M(Cdiss_heat) = 0.00012; // Heat dissipation constant (J/K)
    M(T_amb) = 22.0;      // Ambient temperature (°C)

    // Output quantities (Includes SOC and Temp as well)
    M(Temp_surf) = 0.0; // Surface temperature (°C)
    M(Voltage) = 0.0; // Voltage (V)
}

static double interpolateSOCFactor(double SOC) {
    static const double SOC_values[] = {10, 20, 30, 40, 50, 60, 70, 80, 90};
    static const double Factor_values[] = {1.4, 1.1, 0.99, 0.97, 0.96, 0.95, 0.94, 0.93, 0.91};
    size_t length = sizeof(SOC_values) / sizeof(SOC_values[0]);

    if (SOC <= SOC_values[0]) {
        return Factor_values[0];
    }
    if (SOC >= SOC_values[length - 1]) {
        return Factor_values[length - 1];
    }
    for (size_t i = 0; i < length - 1; i++) {
        if (SOC >= SOC_values[i] && SOC < SOC_values[i + 1]) {
            double t = (SOC - SOC_values[i]) / (SOC_values[i + 1] - SOC_values[i]);
            return Factor_values[i] + t * (Factor_values[i + 1] - Factor_values[i]);
        }
    }
    return Factor_values[length - 1];
}

Status calculateValues(ModelInstance *comp) {
    // Continuous time Equations
    // SOC dynamics
    M(der_SOC) = M(I) / (M(Cap0) * 36.0);

    // Internal resistance dynamics
    double RiOfT = M(a_Ri) * exp(-M(b_Ri) * M(Temp)) + M(c_Ri);
    double Ri = RiOfT * interpolateSOCFactor(M(SOC));

    // Temperature dynamics
    M(der_Temp) = (Ri * pow(M(I), 2) / M(Cap_heat)) - 
                  (M(Cdiss_heat) * (M(Temp) - M(T_amb)));
    
    // --- Measurement model ---

    // Surface temperature (derived from core temperature Temp)
    double Cdiss_ratio = 10.0;
    M(Temp_surf) = (Cdiss_ratio / (Cdiss_ratio + 1.0)) * M(Temp) + (1.0 / (1.0 + Cdiss_ratio)) * M(T_amb);
    // Voltage dynamics
    double U0 = M(U0Nom) + M(dU0) * (M(SOC) - 50.0);
    M(Voltage) = U0 + Ri * M(I);

    return OK;
}

Status getFloat64(ModelInstance *comp, ValueReference vr, double values[], size_t nValues, size_t *index) {
    ASSERT_NVALUES(1);

    switch (vr) {
        case vr_time:
            values[(*index)++] = comp->time;  // to access current simulation time 
            return OK;
        case vr_SOC:
            values[(*index)++] = M(SOC);
            return OK;
        case vr_der_SOC:   // if we plan to access the state derivatives during run-time
            values[(*index)++] = M(der_SOC);
            return OK;
        case vr_Temp:
            values[(*index)++] = M(Temp);
            return OK;
        case vr_der_Temp:
            values[(*index)++] = M(der_Temp);
            return OK;
        case vr_Temp_surf:
            values[(*index)++] = M(Temp_surf);
            return OK;
        case vr_Voltage:
            values[(*index)++] = M(Voltage);
            return OK;
        case vr_I:
            values[(*index)++] = M(I);
            return OK;
        case vr_a_Ri:
            values[(*index)++] = M(a_Ri);
            return OK;
        case vr_b_Ri:
            values[(*index)++] = M(b_Ri);
            return OK;
        case vr_c_Ri:
            values[(*index)++] = M(c_Ri);
            return OK;
        case vr_U0Nom:
            values[(*index)++] = M(U0Nom);
            return OK;
        case vr_dU0:
            values[(*index)++] = M(dU0);
            return OK;
        case vr_Cap0:
            values[(*index)++] = M(Cap0);
            return OK;
        case vr_Cap_heat:
            values[(*index)++] = M(Cap_heat);
            return OK;
        case vr_Cdiss_heat:
            values[(*index)++] = M(Cdiss_heat);
            return OK;
        case vr_T_amb:
            values[(*index)++] = M(T_amb);
            return OK;

        default:
            logError(comp, "Invalid variable reference %u for getFloat64.", vr);
            return Error;
    }
}

Status setFloat64(ModelInstance *comp, ValueReference vr, const double values[], size_t nValues, size_t *index) {
    ASSERT_NVALUES(1);
    switch (vr) {
        case vr_I:
            M(I) = values[(*index)++];
            return OK;
        case vr_SOC:
            M(SOC) = values[(*index)++];
            return OK;
        case vr_Temp:
            M(Temp) = values[(*index)++];
            return OK;
        // case vr_a_Ri:
        //     if (comp->type == ModelExchange && comp->state != Instantiated && comp->state != InitializationMode &&
        //         comp->state != EventMode)
        //     {
        //         logError(comp, "Variable can only be set after instantiation, in initialization mode and event mode.");
        //         return Error;
        //     }
        //     M(a_Ri) = values[(*index)++];
        //     return OK;
        // case vr_b_Ri:
        //     if (comp->type == ModelExchange && comp->state != Instantiated && comp->state != InitializationMode &&
        //         comp->state != EventMode)
        //     {
        //         logError(comp, "Variable can only be set after instantiation, in initialization mode and event mode.");
        //         return Error;
        //     }
        //     M(b_Ri) = values[(*index)++];
        //     return OK;
        // case vr_c_Ri:
        //     if (comp->type == ModelExchange && comp->state != Instantiated && comp->state != InitializationMode &&
        //         comp->state != EventMode)
        //     {
        //         logError(comp, "Variable can only be set after instantiation, in initialization mode and event mode.");
        //         return Error;
        //     }
        //     M(c_Ri) = values[(*index)++];
        //     return OK;
        case vr_Cap0:
            M(Cap0) = values[(*index)++];
            return OK;
        case vr_U0Nom:
            M(U0Nom) = values[(*index)++];
            return OK;
        case vr_dU0:
            M(dU0) = values[(*index)++];
            return OK;
        case vr_Cap_heat:
            M(Cap_heat) = values[(*index)++];
            return OK;
        case vr_Cdiss_heat:
            M(Cdiss_heat) = values[(*index)++];
            return OK;
        case vr_T_amb:
            M(T_amb) = values[(*index)++];
            return OK;
        default:
            logError(comp, "Invalid variable reference %u for setFloat64.", vr);
            return Error;
    }
}

void getContinuousStates(ModelInstance *comp, double x[], size_t nx) {
    UNUSED(nx);
    x[0] = M(SOC);
    x[1] = M(Temp);
}

void setContinuousStates(ModelInstance *comp, const double x[], size_t nx) {
    UNUSED(nx);
    M(SOC) = x[0];
    M(Temp) = x[1];
    calculateValues(comp);
}

void getDerivatives(ModelInstance *comp, double dx[], size_t nx) {
    UNUSED(nx);
    calculateValues(comp);
    dx[0] = M(der_SOC);
    dx[1] = M(der_Temp);
}

void eventUpdate(ModelInstance *comp)  // not necessary 
{
    comp->valuesOfContinuousStatesChanged   = false;
    comp->nominalsOfContinuousStatesChanged = false;
    comp->terminateSimulation               = false;
    comp->nextEventTimeDefined              = false;
}
