#ifndef config_h
#define config_h

// define class name and unique id
#define MODEL_IDENTIFIER BatteryModel  // must exactly match the name of this files' parent.
#define INSTANTIATION_TOKEN "{BD403596-3166-4232-ABC2-132BDF73E645}"

#define CO_SIMULATION
#define MODEL_EXCHANGE

// define model size
#define NX 2 // Number of States (SOC,Temp)
#define NZ 0 // Number of event indicators

#define SET_FLOAT64

// #define GET_PARTIAL_DERIVATIVE  // neglected

#define FIXED_SOLVER_STEP 1.0

typedef enum
{
    vr_time,
    vr_SOC,
    vr_der_SOC,
    vr_Temp,
    vr_der_Temp,
    vr_I,    // can also be input_I since no strict naming conventions for inputs in FMI 2.0 doc
    vr_a_Ri,
    vr_b_Ri,
    vr_c_Ri,
    vr_U0Nom,
    vr_dU0,
    vr_Cap0,
    vr_Cap_heat,
    vr_Cdiss_heat,
    vr_Voltage,
    vr_Temp_surf,
    vr_T_amb
} ValueReference;

typedef struct
{
    double SOC;
    double der_SOC;
    double Temp;
    double der_Temp;
    double I;
    double a_Ri;
    double b_Ri;
    double c_Ri;
    double U0Nom;
    double dU0;
    double Cap0;
    double Cap_heat;
    double Cdiss_heat;
    double Voltage;
    double Temp_surf;
    double T_amb;
} ModelData;

#endif /* config_h */
