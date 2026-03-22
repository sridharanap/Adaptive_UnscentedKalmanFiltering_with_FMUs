import matplotlib.pyplot as plt

def plots_input(t, u):
    """
    Plots battery input current.

    Parameters:
    - t: Time steps vector in seconds
    - u: Input sequence vector.
    """
    title_fontsize = 20
    label_fontsize = 16

    plt.figure('Input Current')
    plt.plot(t, u[0, :])
    plt.title('Input Current', fontsize=title_fontsize, fontweight='normal')
    plt.xlabel('Time in [sec]', fontsize=label_fontsize)
    plt.ylabel('I [Ampere]', fontsize=label_fontsize)

    plt.grid(True)
    plt.box(True)